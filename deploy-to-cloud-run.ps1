# PowerShell deployment script for Cloud Run (Windows)
# Alternative to bash script - no WSL needed

# Don't stop on all errors - some commands may have warnings
$ErrorActionPreference = "Continue"

# Configuration
$PROJECT_ID = if ($env:GCP_PROJECT_ID) { $env:GCP_PROJECT_ID } else { "mss-tts" }
$SERVICE_NAME = "mss-api"
$REGION = "us-central1"
$ARTIFACT_REGISTRY = if ($env:GCP_ARTIFACT_REGISTRY) { $env:GCP_ARTIFACT_REGISTRY } else { "mss" }

Write-Host "=== MSS Cloud Run Deployment ===" -ForegroundColor Cyan
Write-Host "Project: $PROJECT_ID"
Write-Host "Service: $SERVICE_NAME"
Write-Host "Region: $REGION"
Write-Host ""

# Verify gcloud is installed
Write-Host "1. Checking gcloud CLI..." -ForegroundColor Yellow
try {
    $gcloudVersion = gcloud --version 2>&1 | Select-Object -First 1
    Write-Host "   Found: $gcloudVersion" -ForegroundColor Green
} catch {
    Write-Host "ERROR: gcloud CLI not found!" -ForegroundColor Red
    Write-Host "Install from: https://cloud.google.com/sdk/docs/install" -ForegroundColor Yellow
    exit 1
}

# Verify Docker is installed and running
Write-Host "2. Checking Docker..." -ForegroundColor Yellow
try {
    $dockerVersion = docker --version 2>&1
    Write-Host "   Found: $dockerVersion" -ForegroundColor Green
    
    # Test if Docker daemon is actually running
    Write-Host "   Testing Docker connection..." -ForegroundColor Gray
    $dockerTest = docker info 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: Docker is installed but not running!" -ForegroundColor Red
        Write-Host "Please start Docker Desktop and wait for it to fully start." -ForegroundColor Yellow
        Write-Host "Look for the Docker whale icon in your system tray (bottom-right)." -ForegroundColor Yellow
        Write-Host "Then run this script again." -ForegroundColor Yellow
        exit 1
    }
    Write-Host "   ✅ Docker daemon is running" -ForegroundColor Green
} catch {
    Write-Host "ERROR: Docker not found or not running!" -ForegroundColor Red
    Write-Host "Install from: https://www.docker.com/products/docker-desktop" -ForegroundColor Yellow
    Write-Host "Or start Docker Desktop if already installed." -ForegroundColor Yellow
    exit 1
}

# Verify gcloud authentication
Write-Host "3. Verifying GCP authentication..." -ForegroundColor Yellow
try {
    $authResult = gcloud auth list 2>&1
    $authOutput = $authResult | Out-String
    
    if ($authOutput -match "No credentialed accounts" -or $authOutput -match "not authenticated") {
        Write-Host "ERROR: Not authenticated to GCP." -ForegroundColor Red
        Write-Host "Run: gcloud auth login" -ForegroundColor Yellow
        exit 1
    }
    
    # Check if we have an active account
    $hasAccount = $authOutput -match "ACTIVE"
    if (-not $hasAccount) {
        Write-Host "WARNING: No active account found. Attempting to authenticate..." -ForegroundColor Yellow
        Write-Host "Please run: gcloud auth login" -ForegroundColor Yellow
        Write-Host "Then run this script again." -ForegroundColor Yellow
        exit 1
    }
    
    Write-Host "   Authenticated" -ForegroundColor Green
} catch {
    Write-Host "WARNING: Could not verify authentication, but continuing..." -ForegroundColor Yellow
    Write-Host "If deployment fails, run: gcloud auth login" -ForegroundColor Yellow
}

# Set project
Write-Host "4. Setting GCP project..." -ForegroundColor Yellow
gcloud config set project $PROJECT_ID
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Failed to set project" -ForegroundColor Red
    exit 1
}
Write-Host "   Project set to: $PROJECT_ID" -ForegroundColor Green

# Configure Docker for Artifact Registry
Write-Host "5. Configuring Docker for Artifact Registry..." -ForegroundColor Yellow
Write-Host "   (This should be quick - if it hangs, you can skip this step)" -ForegroundColor Gray

# Check if Docker is already configured
$dockerConfigExists = Test-Path "$env:USERPROFILE\.docker\config.json"
if ($dockerConfigExists) {
    Write-Host "   Docker config found, checking if already configured..." -ForegroundColor Gray
}

# Run with timeout to prevent hanging
try {
    $job = Start-Job -ScriptBlock {
        param($region)
        gcloud auth configure-docker ${region}-docker.pkg.dev 2>&1
    } -ArgumentList $REGION
    
    # Wait max 30 seconds
    $completed = Wait-Job $job -Timeout 30
    
    if ($completed) {
        $dockerConfig = Receive-Job $job
        Remove-Job $job
        
        # Check result
        if ($LASTEXITCODE -eq 0 -or $dockerConfig -match "Successfully|already configured|WARNING") {
            Write-Host "   ✅ Docker configured" -ForegroundColor Green
        } else {
            Write-Host "   ⚠️  Configuration may have issues, but continuing..." -ForegroundColor Yellow
        }
    } else {
        # Timeout - stop the job and continue anyway
        Stop-Job $job
        Remove-Job $job
        Write-Host "   ⚠️  Configuration timed out, but continuing (Docker may already be configured)" -ForegroundColor Yellow
        Write-Host "   You can manually run: gcloud auth configure-docker ${REGION}-docker.pkg.dev" -ForegroundColor Gray
    }
} catch {
    Write-Host "   ⚠️  Skipping Docker config (may already be configured)" -ForegroundColor Yellow
    Write-Host "   Continuing to build step..." -ForegroundColor Gray
}

# Build Docker image
Write-Host "6. Building Docker image (this may take 5-10 minutes)..." -ForegroundColor Yellow
$imageTag = "${REGION}-docker.pkg.dev/${PROJECT_ID}/${ARTIFACT_REGISTRY}/${SERVICE_NAME}:latest"

# Try to get git commit, but don't fail if git isn't available
$gitCommit = $null
try {
    $gitOutput = git rev-parse --short HEAD 2>&1
    if ($LASTEXITCODE -eq 0 -and $gitOutput) {
        $gitCommit = $gitOutput.Trim()
        $imageTagCommit = "${REGION}-docker.pkg.dev/${PROJECT_ID}/${ARTIFACT_REGISTRY}/${SERVICE_NAME}:${gitCommit}"
    } else {
        $imageTagCommit = $imageTag
    }
} catch {
    $imageTagCommit = $imageTag
}

if ($null -eq $gitCommit) {
    Write-Host "   Using 'latest' tag only (git not available or not in repo)" -ForegroundColor Yellow
} else {
    Write-Host "   Building with tags: latest, $gitCommit" -ForegroundColor Gray
}

docker build -f Dockerfile.app -t $imageTag -t $imageTagCommit .
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Docker build failed!" -ForegroundColor Red
    Write-Host "Check Docker Desktop is running and try again." -ForegroundColor Yellow
    exit 1
}
Write-Host "   ✅ Build complete" -ForegroundColor Green

# Push to Artifact Registry
Write-Host "7. Pushing to Artifact Registry..." -ForegroundColor Yellow
docker push $imageTag
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Failed to push image" -ForegroundColor Red
    exit 1
}
if ($imageTagCommit -ne $imageTag) {
    docker push $imageTagCommit
}
Write-Host "   Image pushed" -ForegroundColor Green

# Deploy to Cloud Run
Write-Host "8. Deploying to Cloud Run (this may take 2-3 minutes)..." -ForegroundColor Yellow
gcloud run deploy $SERVICE_NAME `
    --image $imageTag `
    --region $REGION `
    --platform managed `
    --allow-unauthenticated `
    --memory 2Gi `
    --cpu 2 `
    --timeout 300 `
    --max-instances 10 `
    --min-instances 0

if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Deployment failed!" -ForegroundColor Red
    exit 1
}

# Get service URL
Write-Host ""
Write-Host "9. Getting service URL..." -ForegroundColor Yellow
$SERVICE_URL = gcloud run services describe $SERVICE_NAME --region $REGION --format 'value(status.url)' 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "WARNING: Could not get service URL" -ForegroundColor Yellow
} else {
    Write-Host ""
    Write-Host "=== Deployment Complete! ===" -ForegroundColor Green
    Write-Host ""
    Write-Host "📍 Service URL: $SERVICE_URL" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "🔗 Quick Links:" -ForegroundColor Yellow
    Write-Host "   Health:   $SERVICE_URL/health" -ForegroundColor White
    Write-Host "   Healthz:  $SERVICE_URL/healthz" -ForegroundColor White
    Write-Host "   Auth:     $SERVICE_URL/auth" -ForegroundColor White
    Write-Host "   Studio:   $SERVICE_URL/studio" -ForegroundColor White
    Write-Host ""
    
    # Health check
    Write-Host "10. Testing health endpoint..." -ForegroundColor Yellow
    Start-Sleep -Seconds 5
    try {
        $healthResponse = Invoke-WebRequest -Uri "$SERVICE_URL/healthz" -UseBasicParsing -TimeoutSec 10
        Write-Host "   ✅ Health check passed!" -ForegroundColor Green
        Write-Host "   Response: $($healthResponse.Content)" -ForegroundColor Gray
    } catch {
        Write-Host "   ⚠️  Health check failed, but service may still be starting..." -ForegroundColor Yellow
        Write-Host "   Wait 30 seconds and try: $SERVICE_URL/healthz" -ForegroundColor Yellow
    }
    
    Write-Host ""
    Write-Host "==========================================" -ForegroundColor Cyan
    Write-Host "✅ Successfully deployed to Cloud Run!" -ForegroundColor Green
    Write-Host "==========================================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "To view logs:" -ForegroundColor Yellow
    Write-Host "  gcloud run services logs read $SERVICE_NAME --region $REGION" -ForegroundColor White
    Write-Host ""
}

