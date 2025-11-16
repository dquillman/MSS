# Check Current Google Cloud Setup for MSS
# This script examines what's currently configured

Write-Host "🔍 Checking Current Google Cloud Setup" -ForegroundColor Cyan
Write-Host ""

# Check if gcloud is installed
try {
    $gcloudVersion = gcloud --version 2>&1 | Select-Object -First 1
    Write-Host "✅ gcloud CLI: $gcloudVersion" -ForegroundColor Green
} catch {
    Write-Host "❌ gcloud CLI not found" -ForegroundColor Red
    exit 1
}

# Check authentication
Write-Host "`n🔐 Authentication Status:" -ForegroundColor Cyan
$account = gcloud auth list --filter=status:ACTIVE --format="value(account)" 2>$null
if ($account) {
    Write-Host "   ✅ Authenticated as: $account" -ForegroundColor Green
} else {
    Write-Host "   ❌ Not authenticated" -ForegroundColor Red
}

# Get current project
Write-Host "`n📦 Current GCP Project:" -ForegroundColor Cyan
$projectId = gcloud config get-value project 2>$null
if ($projectId) {
    Write-Host "   Project ID: $projectId" -ForegroundColor Green
    
    # Get project number
    $projectNumber = gcloud projects describe $projectId --format="value(projectNumber)" 2>$null
    if ($projectNumber) {
        Write-Host "   Project Number: $projectNumber" -ForegroundColor Gray
    }
} else {
    Write-Host "   ❌ No project set" -ForegroundColor Red
}

# Check Cloud Run service
Write-Host "`n☁️  Cloud Run Service:" -ForegroundColor Cyan
$serviceName = "mss-api"
$region = "us-central1"

if ($projectId) {
    $service = gcloud run services describe $serviceName --region=$region --project=$projectId --format="json" 2>$null | ConvertFrom-Json
    if ($service) {
        Write-Host "   ✅ Service exists: $serviceName" -ForegroundColor Green
        Write-Host "   URL: $($service.status.url)" -ForegroundColor Cyan
        Write-Host "   Region: $region" -ForegroundColor Gray
        Write-Host "   Status: $($service.status.conditions[0].status)" -ForegroundColor Gray
    } else {
        Write-Host "   ❌ Service '$serviceName' not found in region '$region'" -ForegroundColor Red
    }
} else {
    Write-Host "   ⚠️  Cannot check - no project set" -ForegroundColor Yellow
}

# Check Artifact Registry
Write-Host "`n📦 Artifact Registry:" -ForegroundColor Cyan
$repoName = "mss"
if ($projectId) {
    $repos = gcloud artifacts repositories list --location=$region --project=$projectId --format="json" 2>$null | ConvertFrom-Json
    $mssRepo = $repos | Where-Object { $_.name -like "*$repoName*" }
    if ($mssRepo) {
        Write-Host "   ✅ Repository '$repoName' exists" -ForegroundColor Green
        Write-Host "   Location: $($mssRepo.format)" -ForegroundColor Gray
    } else {
        Write-Host "   ❌ Repository '$repoName' not found" -ForegroundColor Red
    }
} else {
    Write-Host "   ⚠️  Cannot check - no project set" -ForegroundColor Yellow
}

# Check Secret Manager
Write-Host "`n🔒 Secret Manager Secrets:" -ForegroundColor Cyan
if ($projectId) {
    $secrets = @("openai-api-key", "stripe-secret-key", "stripe-webhook-secret")
    foreach ($secret in $secrets) {
        $exists = gcloud secrets describe $secret --project=$projectId 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-Host "   ✅ $secret exists" -ForegroundColor Green
        } else {
            Write-Host "   ❌ $secret not found" -ForegroundColor Red
        }
    }
} else {
    Write-Host "   ⚠️  Cannot check - no project set" -ForegroundColor Yellow
}

# Check Service Accounts
Write-Host "`n👤 Service Accounts:" -ForegroundColor Cyan
if ($projectId) {
    $sas = gcloud iam service-accounts list --project=$projectId --format="json" 2>$null | ConvertFrom-Json
    $githubSa = $sas | Where-Object { $_.displayName -like "*github*" -or $_.email -like "*github*" }
    if ($githubSa) {
        Write-Host "   ✅ GitHub Actions SA: $($githubSa.email)" -ForegroundColor Green
    } else {
        Write-Host "   ❌ GitHub Actions service account not found" -ForegroundColor Red
    }
    
    # Check default compute SA
    $computeSa = "${projectNumber}-compute@developer.gserviceaccount.com"
    Write-Host "   Default Compute SA: $computeSa" -ForegroundColor Gray
} else {
    Write-Host "   ⚠️  Cannot check - no project set" -ForegroundColor Yellow
}

# Check APIs
Write-Host "`n🔌 Enabled APIs:" -ForegroundColor Cyan
if ($projectId) {
    $requiredApis = @(
        "run.googleapis.com",
        "artifactregistry.googleapis.com",
        "secretmanager.googleapis.com"
    )
    
    $enabledApis = gcloud services list --enabled --project=$projectId --format="value(config.name)" 2>$null
    
    foreach ($api in $requiredApis) {
        if ($enabledApis -contains $api) {
            Write-Host "   ✅ $api" -ForegroundColor Green
        } else {
            Write-Host "   ❌ $api (not enabled)" -ForegroundColor Red
        }
    }
} else {
    Write-Host "   ⚠️  Cannot check - no project set" -ForegroundColor Yellow
}

# Summary
Write-Host "`n" -NoNewline
Write-Host "=" * 60 -ForegroundColor Cyan
Write-Host "📋 Summary" -ForegroundColor Yellow
Write-Host "=" * 60 -ForegroundColor Cyan

if ($projectId) {
    Write-Host "Project ID: $projectId" -ForegroundColor White
    if ($service) {
        Write-Host "Service URL: $($service.status.url)" -ForegroundColor White
    }
} else {
    Write-Host "WARNING: No GCP project configured" -ForegroundColor Yellow
}

Write-Host ""

