#!/bin/bash
# Manual deployment script for Cloud Run (alternative to GitHub Actions)

set -e

# Configuration
PROJECT_ID="${GCP_PROJECT_ID:-mss-tts}"
SERVICE_NAME="mss-api"
REGION="us-central1"
ARTIFACT_REGISTRY="${GCP_ARTIFACT_REGISTRY:-mss}"

echo "=== MSS Cloud Run Deployment ==="
echo "Project: $PROJECT_ID"
echo "Service: $SERVICE_NAME"
echo "Region: $REGION"
echo ""

# Verify gcloud is authenticated
echo "1. Verifying GCP authentication..."
gcloud auth list || {
    echo "ERROR: Not authenticated to GCP. Run: gcloud auth login"
    exit 1
}

# Set project
echo "2. Setting GCP project..."
gcloud config set project $PROJECT_ID

# Configure Docker for Artifact Registry
echo "3. Configuring Docker for Artifact Registry..."
gcloud auth configure-docker ${REGION}-docker.pkg.dev

# Build Docker image
echo "4. Building Docker image..."
docker build -f Dockerfile.app \
    -t ${REGION}-docker.pkg.dev/${PROJECT_ID}/${ARTIFACT_REGISTRY}/${SERVICE_NAME}:latest \
    -t ${REGION}-docker.pkg.dev/${PROJECT_ID}/${ARTIFACT_REGISTRY}/${SERVICE_NAME}:$(git rev-parse --short HEAD) \
    . || {
    echo "ERROR: Docker build failed!"
    exit 1
}

# Push to Artifact Registry
echo "5. Pushing to Artifact Registry..."
docker push ${REGION}-docker.pkg.dev/${PROJECT_ID}/${ARTIFACT_REGISTRY}/${SERVICE_NAME}:latest
docker push ${REGION}-docker.pkg.dev/${PROJECT_ID}/${ARTIFACT_REGISTRY}/${SERVICE_NAME}:$(git rev-parse --short HEAD)

# Deploy to Cloud Run
echo "6. Deploying to Cloud Run..."

DATABASE_URL_ENV="${DATABASE_URL:-}"
DATABASE_URL_SECRET="${DATABASE_URL_SECRET:-}"

SET_ENV_ARGS=""
SET_SECRET_ARGS="OPENAI_API_KEY=openai-api-key:latest,STRIPE_SECRET_KEY=stripe-secret-key:latest,STRIPE_WEBHOOK_SECRET=stripe-webhook-secret:latest"

if [ -n "$DATABASE_URL_ENV" ]; then
    echo " - Using DATABASE_URL from environment"
    SET_ENV_ARGS="--set-env-vars \"DATABASE_URL=$DATABASE_URL_ENV\""
elif [ -n "$DATABASE_URL_SECRET" ]; then
    echo " - Using DATABASE_URL secret: $DATABASE_URL_SECRET"
    SET_SECRET_ARGS="$SET_SECRET_ARGS,DATABASE_URL=$DATABASE_URL_SECRET"
else
    echo "WARNING: DATABASE_URL not provided; service will default to SQLite."
fi

eval gcloud run deploy $SERVICE_NAME \
    --image ${REGION}-docker.pkg.dev/${PROJECT_ID}/${ARTIFACT_REGISTRY}/${SERVICE_NAME}:latest \
    --region $REGION \
    --platform managed \
    --allow-unauthenticated \
    --memory 2Gi \
    --cpu 2 \
    --timeout 300 \
    --max-instances 10 \
    --min-instances 0 \
    $SET_ENV_ARGS \
    --set-secrets "$SET_SECRET_ARGS" \
    || {
    echo "ERROR: Deployment failed!"
    exit 1
}

# Get service URL
echo ""
echo "7. Getting service URL..."
SERVICE_URL=$(gcloud run services describe $SERVICE_NAME --region $REGION --format 'value(status.url)')
echo "Service deployed at: $SERVICE_URL"

# Health check
echo ""
echo "8. Testing health endpoint..."
sleep 5
curl -f "$SERVICE_URL/healthz" && echo "" || {
    echo "WARNING: Health check failed, but service may still be starting..."
}

echo ""
echo "=== Deployment Complete ==="
echo "Service URL: $SERVICE_URL"
echo "Health check: $SERVICE_URL/healthz"
echo "View logs: gcloud run services logs read $SERVICE_NAME --region $REGION"






