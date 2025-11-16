# Automated Setup Script for GitHub Actions
# This script creates the service account and prepares everything for GitHub Secrets

param(
    [switch]$SkipKeyCreation = $false
)

Write-Host "🚀 Setting up GitHub Actions for MSS" -ForegroundColor Cyan
Write-Host ""

# Set project
Write-Host "📦 Setting GCP project..." -ForegroundColor Cyan
gcloud config set project mss-tts
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Failed to set project" -ForegroundColor Red
    exit 1
}

# Check if service account exists
Write-Host "`n👤 Checking for existing service account..." -ForegroundColor Cyan
$SA_EMAIL = "github-actions-deployer@mss-tts.iam.gserviceaccount.com"
$existing = gcloud iam service-accounts describe $SA_EMAIL --project=mss-tts 2>&1

if ($LASTEXITCODE -eq 0) {
    Write-Host "   ✅ Service account already exists: $SA_EMAIL" -ForegroundColor Green
    $createSA = $false
} else {
    Write-Host "   Creating new service account..." -ForegroundColor Yellow
    $createSA = $true
}

# Create service account if needed
if ($createSA) {
    gcloud iam service-accounts create github-actions-deployer `
        --display-name="GitHub Actions Deployer" `
        --project=mss-tts
    
    if ($LASTEXITCODE -ne 0) {
        Write-Host "❌ Failed to create service account" -ForegroundColor Red
        exit 1
    }
    Write-Host "   ✅ Service account created" -ForegroundColor Green
}

# Grant permissions
Write-Host "`n🔐 Granting permissions..." -ForegroundColor Cyan
$roles = @(
    "roles/run.admin",
    "roles/artifactregistry.writer",
    "roles/iam.serviceAccountUser"
)

foreach ($role in $roles) {
    Write-Host "   Granting $role..." -ForegroundColor Gray
    gcloud projects add-iam-policy-binding mss-tts `
        --member="serviceAccount:$SA_EMAIL" `
        --role=$role 2>&1 | Out-Null
}
Write-Host "   ✅ Permissions granted" -ForegroundColor Green

# Create key file
if (-not $SkipKeyCreation) {
    Write-Host "`n🔑 Creating service account key..." -ForegroundColor Cyan
    $keyFile = "github-actions-key.json"
    
    if (Test-Path $keyFile) {
        Write-Host "   ⚠️  Key file already exists: $keyFile" -ForegroundColor Yellow
        $overwrite = Read-Host "   Overwrite? (y/N)"
        if ($overwrite -ne "y") {
            Write-Host "   Skipping key creation" -ForegroundColor Yellow
        } else {
            Remove-Item $keyFile -Force
            gcloud iam service-accounts keys create $keyFile `
                --iam-account=$SA_EMAIL `
                --project=mss-tts
            Write-Host "   ✅ Key created: $keyFile" -ForegroundColor Green
        }
    } else {
        gcloud iam service-accounts keys create $keyFile `
            --iam-account=$SA_EMAIL `
            --project=mss-tts
        Write-Host "   ✅ Key created: $keyFile" -ForegroundColor Green
    }
} else {
    Write-Host "`n⏭️  Skipping key creation (use -SkipKeyCreation to skip)" -ForegroundColor Yellow
}

# Summary
Write-Host "`n" -NoNewline
Write-Host "=" * 60 -ForegroundColor Cyan
Write-Host "✅ Setup Complete!" -ForegroundColor Green
Write-Host "=" * 60 -ForegroundColor Cyan
Write-Host ""
Write-Host "📋 Next Steps:" -ForegroundColor Yellow
Write-Host ""
Write-Host "1. Add GitHub Secrets at:" -ForegroundColor White
Write-Host "   https://github.com/dquillman/MSS/settings/secrets/actions" -ForegroundColor Cyan
Write-Host ""
Write-Host "2. Add these secrets:" -ForegroundColor White
Write-Host "   - GCP_PROJECT_ID = mss-tts" -ForegroundColor Gray
Write-Host "   - GCP_SA_KEY = (contents of github-actions-key.json)" -ForegroundColor Gray
Write-Host "   - GCP_SERVICE_ACCOUNT_EMAIL = $SA_EMAIL" -ForegroundColor Gray
Write-Host "   - GCP_ARTIFACT_REGISTRY = mss (optional)" -ForegroundColor Gray
Write-Host ""
if (-not $SkipKeyCreation -and (Test-Path "github-actions-key.json")) {
    Write-Host "3. Display the key file:" -ForegroundColor White
    Write-Host "   Get-Content github-actions-key.json" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "4. After adding to GitHub, delete the key file:" -ForegroundColor White
    Write-Host "   Remove-Item github-actions-key.json" -ForegroundColor Cyan
    Write-Host ""
}
Write-Host "5. Test deployment by pushing to GitHub" -ForegroundColor White
Write-Host ""

