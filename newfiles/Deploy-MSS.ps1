# MSS Deployment Automation Script
# This script fixes all deployment issues and prepares your app for Cloud Run
# Run this from G:\Users\daveq\MSS directory

param(
    [switch]$FixFiles,
    [switch]$ValidateEnv,
    [switch]$TestDocker,
    [switch]$Deploy,
    [switch]$All,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

# Colors for output
function Write-Success { Write-Host $args -ForegroundColor Green }
function Write-Info { Write-Host $args -ForegroundColor Cyan }
function Write-Warning { Write-Host $args -ForegroundColor Yellow }
function Write-Error { Write-Host $args -ForegroundColor Red }

Write-Info "=== MSS Deployment Automation ==="
Write-Info "Working Directory: $(Get-Location)"

# Ensure we're on G: drive
if (-not (Get-Location).Path.StartsWith("G:")) {
    Write-Error "ERROR: Must run from G: drive (current: $(Get-Location))"
    Write-Info "Please navigate to G:\Users\daveq\MSS and run again"
    exit 1
}

# Step 1: Fix Dockerfile.app
function Fix-Dockerfile {
    Write-Info "`n[1/5] Fixing Dockerfile.app..."

    $dockerfileContent = @"
# Optimized Dockerfile for MSS Flask Application
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    ffmpeg \
    gcc \
    g++ \
    libfreetype6-dev \
    libjpeg-dev \
    fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY web/ ./web/
COPY scripts/ ./scripts/

# Copy library files
COPY avatar_library.json intro_outro_library.json logo_library.json thumbnail_settings.json ./

# Create necessary directories
RUN mkdir -p tmp out public_audio thumbnails avatars logos web/platform_credentials

# Copy entrypoint script
COPY docker/entrypoint-app.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Set environment variables
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Expose port
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

ENTRYPOINT ["/entrypoint.sh"]
"@

    if ($DryRun) {
        Write-Info "DRY RUN: Would write Dockerfile.app"
    } else {
        Set-Content -Path "Dockerfile.app" -Value $dockerfileContent -Encoding UTF8
        Write-Success "✓ Dockerfile.app fixed"
    }
}

# Step 2: Fix entrypoint script
function Fix-Entrypoint {
    Write-Info "`n[2/5] Fixing entrypoint-app.sh..."

    $entrypointContent = @"
#!/bin/bash
set -e

echo "[ENTRYPOINT] Starting MSS Flask application..."
echo "[ENTRYPOINT] PORT=`${PORT:-8080}"
echo "[ENTRYPOINT] PYTHONPATH=`$PYTHONPATH"

# Wait for Cloud SQL if needed
if [ -n "`$DB_URL" ] && [[ "`$DB_URL" == *"cloudsql"* ]]; then
    echo "[ENTRYPOINT] Waiting for Cloud SQL proxy..."
    sleep 2
fi

# Verify app can be imported
echo "[ENTRYPOINT] Verifying app import..."
python -c "from web import api_server; print('[ENTRYPOINT] App imported successfully')" || {
    echo "[ENTRYPOINT] ERROR: Failed to import app!"
    exit 1
}

echo "[ENTRYPOINT] Starting gunicorn on 0.0.0.0:`${PORT:-8080}..."

# Start gunicorn
exec gunicorn \
    --bind 0.0.0.0:`${PORT:-8080} \
    --workers `${GUNICORN_WORKERS:-2} \
    --threads `${GUNICORN_THREADS:-4} \
    --timeout `${GUNICORN_TIMEOUT:-120} \
    --access-logfile - \
    --error-logfile - \
    --log-level info \
    web.api_server:app
"@

    if ($DryRun) {
        Write-Info "DRY RUN: Would write docker/entrypoint-app.sh"
    } else {
        New-Item -ItemType Directory -Force -Path "docker" | Out-Null
        Set-Content -Path "docker/entrypoint-app.sh" -Value $entrypointContent -Encoding UTF8
        Write-Success "✓ entrypoint-app.sh fixed"
    }
}

# Step 3: Fix GitHub workflow
function Fix-Workflow {
    Write-Info "`n[3/5] Fixing GitHub workflow..."

    $workflowContent = @"
name: Deploy to Cloud Run

on:
  push:
    branches: [ main ]
  workflow_dispatch:

env:
  PROJECT_ID: mss-deployment-447320
  SERVICE_NAME: mss-api
  REGION: us-central1

jobs:
  deploy:
    runs-on: ubuntu-latest

    permissions:
      contents: read
      id-token: write

    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Authenticate to Google Cloud
        uses: google-github-actions/auth@v2
        with:
          credentials_json: `${{ secrets.GCP_SA_KEY }}

      - name: Set up Cloud SDK
        uses: google-github-actions/setup-gcloud@v2

      - name: Configure Docker for GCR
        run: gcloud auth configure-docker

      - name: Build Docker image
        run: |
          docker build -f Dockerfile.app -t gcr.io/`$PROJECT_ID/`$SERVICE_NAME:latest .
          docker build -f Dockerfile.app -t gcr.io/`$PROJECT_ID/`$SERVICE_NAME:`$GITHUB_SHA .

      - name: Push Docker image
        run: |
          docker push gcr.io/`$PROJECT_ID/`$SERVICE_NAME:latest
          docker push gcr.io/`$PROJECT_ID/`$SERVICE_NAME:`$GITHUB_SHA

      - name: Deploy to Cloud Run
        run: |
          gcloud run deploy `$SERVICE_NAME \
            --image gcr.io/`$PROJECT_ID/`$SERVICE_NAME:latest \
            --platform managed \
            --region `$REGION \
            --allow-unauthenticated \
            --set-env-vars FLASK_ENV=production \
            --memory 2Gi \
            --cpu 2 \
            --timeout 300 \
            --max-instances 10 \
            --min-instances 0

      - name: Verify deployment
        run: |
          SERVICE_URL=`$(gcloud run services describe `$SERVICE_NAME --region `$REGION --format 'value(status.url)')
          echo "Service URL: `$SERVICE_URL"
          curl -f `$SERVICE_URL/health || exit 1
"@

    if ($DryRun) {
        Write-Info "DRY RUN: Would write .github/workflows/gcp-deploy.yml"
    } else {
        New-Item -ItemType Directory -Force -Path ".github/workflows" | Out-Null
        Set-Content -Path ".github/workflows/gcp-deploy.yml" -Value $workflowContent -Encoding UTF8
        Write-Success "✓ GitHub workflow fixed"
    }
}

# Step 4: Validate environment
function Validate-Environment {
    Write-Info "`n[4/5] Validating environment..."

    $issues = @()

    # Check .env file
    if (-not (Test-Path ".env")) {
        $issues += "Missing .env file"
    } else {
        Write-Success "✓ .env file exists"

        # Check critical env vars
        $envContent = Get-Content ".env" -Raw
        $requiredVars = @("OPENAI_API_KEY", "GOOGLE_APPLICATION_CREDENTIALS")

        foreach ($var in $requiredVars) {
            if ($envContent -notmatch $var) {
                $issues += "Missing $var in .env"
            } else {
                Write-Success "✓ $var configured"
            }
        }
    }

    # Check required files
    $requiredFiles = @(
        "requirements.txt",
        "web/api_server.py",
        "avatar_library.json",
        "intro_outro_library.json",
        "logo_library.json",
        "thumbnail_settings.json"
    )

    foreach ($file in $requiredFiles) {
        if (-not (Test-Path $file)) {
            $issues += "Missing required file: $file"
        } else {
            Write-Success "✓ $file exists"
        }
    }

    # Check Docker
    try {
        docker --version | Out-Null
        Write-Success "✓ Docker installed"
    } catch {
        $issues += "Docker not installed or not in PATH"
    }

    # Check gcloud
    try {
        gcloud --version | Out-Null
        Write-Success "✓ gcloud CLI installed"
    } catch {
        $issues += "gcloud CLI not installed or not in PATH"
    }

    if ($issues.Count -gt 0) {
        Write-Warning "`nIssues found:"
        $issues | ForEach-Object { Write-Warning "  - $_" }
        return $false
    } else {
        Write-Success "`n✓ All validation checks passed!"
        return $true
    }
}

# Step 5: Test Docker build
function Test-DockerBuild {
    Write-Info "`n[5/5] Testing Docker build..."

    if ($DryRun) {
        Write-Info "DRY RUN: Would test Docker build"
        return
    }

    Write-Info "Building Docker image (this may take a few minutes)..."

    try {
        docker build -f Dockerfile.app -t mss-test:latest . 2>&1 | Tee-Object -Variable buildOutput

        if ($LASTEXITCODE -eq 0) {
            Write-Success "✓ Docker build successful!"

            Write-Info "`nTesting container startup..."
            $containerId = docker run -d -p 8080:8080 -e PORT=8080 mss-test:latest

            Start-Sleep -Seconds 10

            try {
                $response = Invoke-WebRequest -Uri "http://localhost:8080/health" -TimeoutSec 5
                if ($response.StatusCode -eq 200) {
                    Write-Success "✓ Health check passed!"
                } else {
                    Write-Warning "Health check returned status: $($response.StatusCode)"
                }
            } catch {
                Write-Warning "Health check failed: $_"
            } finally {
                docker stop $containerId | Out-Null
                docker rm $containerId | Out-Null
            }
        } else {
            Write-Error "Docker build failed!"
            Write-Error $buildOutput
            return $false
        }
    } catch {
        Write-Error "Docker build error: $_"
        return $false
    }

    return $true
}

# Main execution
if ($All) {
    $FixFiles = $true
    $ValidateEnv = $true
    $TestDocker = $true
}

if ($FixFiles -or $All) {
    Fix-Dockerfile
    Fix-Entrypoint
    Fix-Workflow
}

if ($ValidateEnv -or $All) {
    $valid = Validate-Environment
    if (-not $valid) {
        Write-Warning "`nPlease fix the issues above before proceeding."
        exit 1
    }
}

if ($TestDocker -or $All) {
    $testPassed = Test-DockerBuild
    if (-not $testPassed) {
        Write-Error "`nDocker build/test failed. Please check the errors above."
        exit 1
    }
}

if ($Deploy) {
    Write-Info "`n=== Deploying to Cloud Run ==="
    Write-Warning "This will trigger a GitHub Actions deployment."
    Write-Warning "Make sure you have:"
    Write-Warning "  1. Committed all changes"
    Write-Warning "  2. Set up GCP_SA_KEY secret in GitHub"
    Write-Warning "  3. Enabled Cloud Run API in GCP"

    $confirm = Read-Host "`nProceed with deployment? (yes/no)"
    if ($confirm -eq "yes") {
        git add .
        git commit -m "Fix deployment configuration"
        git push origin main
        Write-Success "`n✓ Changes pushed! Check GitHub Actions for deployment status."
    } else {
        Write-Info "Deployment cancelled."
    }
}

Write-Success "`n=== Automation Complete ==="
Write-Info "Next steps:"
Write-Info "  1. Review the fixed files"
Write-Info "  2. Run with -TestDocker to test locally"
Write-Info "  3. Run with -Deploy to deploy to Cloud Run"
