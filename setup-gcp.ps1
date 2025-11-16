# Google Cloud Platform Setup Script for MSS
# Run this script to set up all required GCP resources

param(
    [string]$ProjectId = "mss-deployment-447320",
    [string]$Region = "us-central1",
    [string]$ServiceName = "mss-api",
    [string]$ArtifactRegistry = "mss"
)

Write-Host "🚀 Setting up Google Cloud Platform for MSS" -ForegroundColor Cyan
Write-Host ""

# Check if gcloud is installed
try {
    $gcloudVersion = gcloud --version 2>&1 | Select-Object -First 1
    Write-Host "✅ gcloud found: $gcloudVersion" -ForegroundColor Green
} catch {
    Write-Host "❌ gcloud CLI not found. Install from: https://cloud.google.com/sdk/docs/install" -ForegroundColor Red
    exit 1
}

# Check if authenticated
$account = gcloud auth list --filter=status:ACTIVE --format="value(account)" 2>$null
if (-not $account) {
    Write-Host "⚠️  Not authenticated. Running: gcloud auth login" -ForegroundColor Yellow
    gcloud auth login
}

# Set project
Write-Host "📦 Setting project to: $ProjectId" -ForegroundColor Cyan
gcloud config set project $ProjectId

# Get project number
$projectNumber = gcloud projects describe $ProjectId --format="value(projectNumber)"
Write-Host "   Project Number: $projectNumber" -ForegroundColor Gray

# Step 1: Enable APIs
Write-Host "`n🔌 Enabling required APIs..." -ForegroundColor Cyan
$apis = @(
    "run.googleapis.com",
    "artifactregistry.googleapis.com",
    "secretmanager.googleapis.com",
    "sqladmin.googleapis.com",
    "cloudbuild.googleapis.com",
    "iamcredentials.googleapis.com"
)

foreach ($api in $apis) {
    Write-Host "   Enabling $api..." -ForegroundColor Gray
    gcloud services enable $api --project=$ProjectId 2>&1 | Out-Null
}
Write-Host "✅ APIs enabled" -ForegroundColor Green

# Step 2: Create Artifact Registry
Write-Host "`n📦 Creating Artifact Registry repository..." -ForegroundColor Cyan
$repoExists = gcloud artifacts repositories describe $ArtifactRegistry --location=$Region --project=$ProjectId 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Host "   Repository '$ArtifactRegistry' already exists" -ForegroundColor Yellow
} else {
    gcloud artifacts repositories create $ArtifactRegistry `
        --repository-format=docker `
        --location=$Region `
        --description="MSS Docker images" `
        --project=$ProjectId
    Write-Host "✅ Artifact Registry repository created" -ForegroundColor Green
}

# Step 3: Create Service Account
Write-Host "`n👤 Creating service account..." -ForegroundColor Cyan
$saName = "github-actions-deployer"
$saEmail = "$saName@$ProjectId.iam.gserviceaccount.com"

$saExists = gcloud iam service-accounts describe $saEmail --project=$ProjectId 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Host "   Service account already exists" -ForegroundColor Yellow
} else {
    gcloud iam service-accounts create $saName `
        --display-name="GitHub Actions Deployer" `
        --description="Service account for GitHub Actions to deploy to Cloud Run" `
        --project=$ProjectId
    Write-Host "✅ Service account created: $saEmail" -ForegroundColor Green
}

# Step 4: Grant Permissions
Write-Host "`n🔐 Granting permissions to service account..." -ForegroundColor Cyan
$roles = @(
    "roles/run.admin",
    "roles/artifactregistry.writer",
    "roles/secretmanager.secretAccessor",
    "roles/iam.serviceAccountUser"
)

foreach ($role in $roles) {
    Write-Host "   Granting $role..." -ForegroundColor Gray
    gcloud projects add-iam-policy-binding $ProjectId `
        --member="serviceAccount:$saEmail" `
        --role=$role 2>&1 | Out-Null
}
Write-Host "✅ Permissions granted" -ForegroundColor Green

# Step 5: Create Service Account Key
Write-Host "`n🔑 Creating service account key..." -ForegroundColor Cyan
$keyFile = "github-actions-key.json"
if (Test-Path $keyFile) {
    Write-Host "   Key file already exists: $keyFile" -ForegroundColor Yellow
    $overwrite = Read-Host "   Overwrite? (y/N)"
    if ($overwrite -ne "y") {
        Write-Host "   Skipping key creation" -ForegroundColor Yellow
    } else {
        gcloud iam service-accounts keys create $keyFile `
            --iam-account=$saEmail `
            --project=$ProjectId
        Write-Host "✅ Key created: $keyFile" -ForegroundColor Green
    }
} else {
    gcloud iam service-accounts keys create $keyFile `
        --iam-account=$saEmail `
        --project=$ProjectId
    Write-Host "✅ Key created: $keyFile" -ForegroundColor Green
}

# Step 6: Create Secret Manager Secrets (with prompts)
Write-Host "`n🔒 Setting up Secret Manager secrets..." -ForegroundColor Cyan
Write-Host "   You'll be prompted to enter your API keys" -ForegroundColor Yellow
Write-Host ""

$secrets = @(
    @{Name="openai-api-key"; Description="OpenAI API Key"; Prompt="Enter your OpenAI API key"},
    @{Name="stripe-secret-key"; Description="Stripe Secret Key"; Prompt="Enter your Stripe secret key (sk_live_...)"},
    @{Name="stripe-webhook-secret"; Description="Stripe Webhook Secret"; Prompt="Enter your Stripe webhook secret (whsec_...)"}
)

foreach ($secret in $secrets) {
    $exists = gcloud secrets describe $secret.Name --project=$ProjectId 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "   Secret '$($secret.Name)' already exists" -ForegroundColor Yellow
        $update = Read-Host "   Update it? (y/N)"
        if ($update -eq "y") {
            $value = Read-Host "   $($secret.Prompt)" -AsSecureString
            $plainValue = [Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($value))
            echo -n $plainValue | gcloud secrets versions add $secret.Name --data-file=- --project=$ProjectId
            Write-Host "   ✅ Secret updated" -ForegroundColor Green
        }
    } else {
        $value = Read-Host "   $($secret.Prompt)" -AsSecureString
        $plainValue = [Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($value))
        echo -n $plainValue | gcloud secrets create $secret.Name --data-file=- --replication-policy="automatic" --project=$ProjectId
        Write-Host "   ✅ Secret created" -ForegroundColor Green
    }
}

# Step 7: Grant Cloud Run access to secrets
Write-Host "`n🔐 Granting Cloud Run access to secrets..." -ForegroundColor Cyan
$cloudRunSa = "${projectNumber}-compute@developer.gserviceaccount.com"

foreach ($secret in $secrets) {
    Write-Host "   Granting access to $($secret.Name)..." -ForegroundColor Gray
    gcloud secrets add-iam-policy-binding $secret.Name `
        --member="serviceAccount:$cloudRunSa" `
        --role="roles/secretmanager.secretAccessor" `
        --project=$ProjectId 2>&1 | Out-Null
}
Write-Host "✅ Cloud Run has access to secrets" -ForegroundColor Green

# Summary
Write-Host "`n" -NoNewline
Write-Host "=" * 60 -ForegroundColor Cyan
Write-Host "✅ GCP Setup Complete!" -ForegroundColor Green
Write-Host "=" * 60 -ForegroundColor Cyan
Write-Host ""
Write-Host "📋 Next Steps:" -ForegroundColor Yellow
Write-Host ""
Write-Host "1. Add GitHub Secrets:" -ForegroundColor White
Write-Host "   - GCP_PROJECT_ID = $ProjectId" -ForegroundColor Gray
Write-Host "   - GCP_SA_KEY = (contents of $keyFile)" -ForegroundColor Gray
Write-Host "   - GCP_SERVICE_ACCOUNT_EMAIL = $saEmail" -ForegroundColor Gray
Write-Host "   - GCP_ARTIFACT_REGISTRY = $ArtifactRegistry (optional)" -ForegroundColor Gray
Write-Host ""
Write-Host "2. (Optional) Set up PostgreSQL and add DATABASE_URL secret" -ForegroundColor White
Write-Host ""
Write-Host "3. Push to GitHub to trigger deployment" -ForegroundColor White
Write-Host ""
Write-Host "📄 Service Account Key saved to: $keyFile" -ForegroundColor Cyan
Write-Host "⚠️  Keep this file secure! Delete it after adding to GitHub Secrets." -ForegroundColor Yellow
Write-Host ""

