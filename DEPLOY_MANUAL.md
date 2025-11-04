# Manual Deployment Guide (No GitHub Required)

## Quick Deploy Command

```bash
# Set your project (replace with your actual project ID)
export GCP_PROJECT_ID="mss-tts"
export GCP_ARTIFACT_REGISTRY="mss"
export REGION="us-central1"
export SERVICE_NAME="mss-api"

# Build and deploy
gcloud config set project $GCP_PROJECT_ID
gcloud auth configure-docker ${REGION}-docker.pkg.dev

docker build -f Dockerfile.app \
  -t ${REGION}-docker.pkg.dev/${GCP_PROJECT_ID}/${GCP_ARTIFACT_REGISTRY}/${SERVICE_NAME}:latest .

docker push ${REGION}-docker.pkg.dev/${GCP_PROJECT_ID}/${GCP_ARTIFACT_REGISTRY}/${SERVICE_NAME}:latest

gcloud run deploy $SERVICE_NAME \
  --image ${REGION}-docker.pkg.dev/${GCP_PROJECT_ID}/${GCP_ARTIFACT_REGISTRY}/${SERVICE_NAME}:latest \
  --region $REGION \
  --platform managed \
  --allow-unauthenticated \
  --memory 2Gi \
  --cpu 2 \
  --timeout 300
```

## Using the Script (Easier)

```bash
# Make script executable (Git Bash/WSL)
chmod +x deploy-to-cloud-run.sh

# Run it
./deploy-to-cloud-run.sh
```

## Windows PowerShell Version

```powershell
$GCP_PROJECT_ID = "mss-tts"
$SERVICE_NAME = "mss-api"
$REGION = "us-central1"
$ARTIFACT_REGISTRY = "mss"

# Set project
gcloud config set project $GCP_PROJECT_ID

# Configure Docker
gcloud auth configure-docker ${REGION}-docker.pkg.dev

# Build Docker image
docker build -f Dockerfile.app `
  -t ${REGION}-docker.pkg.dev/${GCP_PROJECT_ID}/${ARTIFACT_REGISTRY}/${SERVICE_NAME}:latest .

# Push image
docker push ${REGION}-docker.pkg.dev/${GCP_PROJECT_ID}/${ARTIFACT_REGISTRY}/${SERVICE_NAME}:latest

# Deploy to Cloud Run
gcloud run deploy $SERVICE_NAME `
  --image ${REGION}-docker.pkg.dev/${GCP_PROJECT_ID}/${ARTIFACT_REGISTRY}/${SERVICE_NAME}:latest `
  --region $REGION `
  --platform managed `
  --allow-unauthenticated `
  --memory 2Gi `
  --cpu 2 `
  --timeout 300
```

## Which Method Should You Use?

**Use GitHub Actions if:**
- ✅ You want automatic deployments
- ✅ You're already using Git
- ✅ Multiple people deploy
- ✅ You want deployment history

**Use Manual Deployment if:**
- ✅ You don't use GitHub
- ✅ You want full control
- ✅ You're testing/debugging
- ✅ One-time deployment

## Recommendation

For your fixes (CSP and error handling), I'd recommend:
1. **Quick fix:** Manual deployment (faster, no waiting for GitHub Actions)
2. **Long term:** GitHub Actions (set it and forget it)

The manual script will take ~5-10 minutes depending on your internet speed.





