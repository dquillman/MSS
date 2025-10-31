# Google Cloud Platform Deployment Guide for MSS

This guide walks through deploying MSS to Google Cloud Run.

## Prerequisites

1. Google Cloud account with billing enabled
2. gcloud CLI installed locally ([install guide](https://cloud.google.com/sdk/docs/install))
3. Docker installed locally
4. GitHub repository with Actions enabled

## Step 1: Create GCP Project

```bash
# Create new project
gcloud projects create mss-production --name="MSS Production"

# Set as active project
gcloud config set project mss-production

# Enable billing (replace BILLING_ACCOUNT_ID)
gcloud billing projects link mss-production --billing-account=BILLING_ACCOUNT_ID

# Enable required APIs
gcloud services enable \
  run.googleapis.com \
  artifactregistry.googleapis.com \
  secretmanager.googleapis.com \
  storage.googleapis.com \
  cloudbuild.googleapis.com
```

## Step 2: Create Artifact Registry

```bash
# Create Docker repository
gcloud artifacts repositories create mss \
  --repository-format=docker \
  --location=us-central1 \
  --description="MSS Docker images"

# Configure Docker authentication
gcloud auth configure-docker us-central1-docker.pkg.dev
```

## Step 3: Create Cloud Storage Bucket

```bash
# Create bucket for media files
gsutil mb -p mss-production -l us-central1 gs://mss-media-production

# Set bucket permissions (optional: make public for media files)
gsutil iam ch allUsers:objectViewer gs://mss-media-production
```

## Step 4: Create Service Account

```bash
# Create service account
gcloud iam service-accounts create mss-runner \
  --display-name="MSS Cloud Run Service Account"

# Grant permissions
gcloud projects add-iam-policy-binding mss-production \
  --member="serviceAccount:mss-runner@mss-production.iam.gserviceaccount.com" \
  --role="roles/storage.objectAdmin"

gcloud projects add-iam-policy-binding mss-production \
  --member="serviceAccount:mss-runner@mss-production.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"
```

## Step 5: Store Secrets in Secret Manager

```bash
# Create secrets
echo -n "your-openai-api-key" | gcloud secrets create openai-api-key \
  --data-file=- \
  --replication-policy="automatic"

echo -n "your-stripe-secret-key" | gcloud secrets create stripe-secret-key \
  --data-file=- \
  --replication-policy="automatic"

echo -n "your-stripe-webhook-secret" | gcloud secrets create stripe-webhook-secret \
  --data-file=- \
  --replication-policy="automatic"

# Add more secrets as needed:
# - stripe-publishable-key
# - stripe-price-starter
# - stripe-price-pro
# - stripe-price-agency
# - stripe-price-lifetime
# - sendgrid-api-key
# - shotstack-api-key
# - etc.
```

## Step 6: Create CI/CD Service Account (for GitHub Actions)

```bash
# Create service account for GitHub Actions
gcloud iam service-accounts create github-actions \
  --display-name="GitHub Actions CI/CD"

# Grant Cloud Run Admin role
gcloud projects add-iam-policy-binding mss-production \
  --member="serviceAccount:github-actions@mss-production.iam.gserviceaccount.com" \
  --role="roles/run.admin"

# Grant Artifact Registry Writer role
gcloud projects add-iam-policy-binding mss-production \
  --member="serviceAccount:github-actions@mss-production.iam.gserviceaccount.com" \
  --role="roles/artifactregistry.writer"

# Grant Service Account User role (to deploy as mss-runner)
gcloud projects add-iam-policy-binding mss-production \
  --member="serviceAccount:github-actions@mss-production.iam.gserviceaccount.com" \
  --role="roles/iam.serviceAccountUser"

# Create and download key
gcloud iam service-accounts keys create github-actions-key.json \
  --iam-account=github-actions@mss-production.iam.gserviceaccount.com
```

## Step 7: Configure GitHub Secrets

Add these secrets to your GitHub repository (Settings → Secrets and variables → Actions):

- `GCP_PROJECT_ID`: `mss-production`
- `GCP_SA_KEY`: Contents of `github-actions-key.json`
- `GCP_ARTIFACT_REGISTRY`: `mss` (or your repository name)
- `GCP_SERVICE_ACCOUNT_EMAIL`: `mss-runner@mss-production.iam.gserviceaccount.com`

## Step 8: Deploy Manually (First Time)

```bash
# Build image locally
docker build -f Dockerfile.app -t us-central1-docker.pkg.dev/mss-production/mss/mss-api:latest .

# Push to Artifact Registry
docker push us-central1-docker.pkg.dev/mss-production/mss/mss-api:latest

# Deploy to Cloud Run
gcloud run deploy mss-api \
  --image us-central1-docker.pkg.dev/mss-production/mss/mss-api:latest \
  --region us-central1 \
  --platform managed \
  --allow-unauthenticated \
  --memory 2Gi \
  --cpu 2 \
  --timeout 300 \
  --max-instances 10 \
  --min-instances 0 \
  --set-env-vars "PORT=8080,GCS_BUCKET_NAME=mss-media-production,GCS_BUCKET_REGION=us-central1" \
  --set-secrets "OPENAI_API_KEY=openai-api-key:latest,STRIPE_SECRET_KEY=stripe-secret-key:latest,STRIPE_WEBHOOK_SECRET=stripe-webhook-secret:latest" \
  --service-account mss-runner@mss-production.iam.gserviceaccount.com
```

## Step 9: Verify Deployment

```bash
# Get service URL
SERVICE_URL=$(gcloud run services describe mss-api --region us-central1 --format 'value(status.url)')
echo "Service URL: $SERVICE_URL"

# Test health endpoint
curl "$SERVICE_URL/healthz"

# Should return: {"status":"ok"}
```

## Environment Variables

Set these via Cloud Run console or gcloud CLI:

**Required:**
- `PORT=8080` (set automatically)
- `GCS_BUCKET_NAME=mss-media-production`
- `GCS_BUCKET_REGION=us-central1`
- `ENVIRONMENT=production`

**Via Secrets:**
- `OPENAI_API_KEY`
- `STRIPE_SECRET_KEY`
- `STRIPE_WEBHOOK_SECRET`
- `STRIPE_PUBLISHABLE_KEY`
- `SHOTSTACK_API_KEY`
- `SENDGRID_API_KEY`
- `GOOGLE_APPLICATION_CREDENTIALS` (if not using Workload Identity)

**Optional:**
- `OPENAI_MODEL_SEO=gpt-4o-mini`
- `OPENAI_MODEL_SCRIPT=gpt-4o-mini`
- `TTS_VOICE_NAME=en-US-Neural2-C`
- `ENABLE_STOCK_FOOTAGE=true`
- `PEXELS_API_KEY=...`
- etc.

## Monitoring & Logs

```bash
# View logs
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=mss-api" --limit 50

# View metrics in Cloud Console
# https://console.cloud.google.com/run/detail/us-central1/mss-api/metrics
```

## Rollback

```bash
# List revisions
gcloud run revisions list --service mss-api --region us-central1

# Rollback to previous revision
gcloud run services update-traffic mss-api \
  --to-revisions REVISION_NAME=100 \
  --region us-central1
```

## Cost Estimation

**Cloud Run:**
- Free tier: 2 million requests/month, 360,000 GB-seconds
- After free tier: ~$0.40 per million requests, $0.0000025 per GB-second

**Cloud Storage:**
- First 5 GB/month free
- After: $0.020 per GB/month

**Secret Manager:**
- First 6 secrets free
- After: $0.06 per secret per month

**Estimated monthly cost for small-medium usage:**
- Cloud Run: $5-20
- Storage: $1-5
- Secrets: $0-1
- **Total: ~$10-30/month**

## Troubleshooting

### Build fails
```bash
# Check build logs
gcloud builds list --limit=5

# View specific build
gcloud builds describe BUILD_ID
```

### Service won't start
```bash
# Check logs
gcloud run services logs read mss-api --region us-central1 --limit=50

# Check service status
gcloud run services describe mss-api --region us-central1
```

### Permission errors
```bash
# Verify service account permissions
gcloud projects get-iam-policy mss-production \
  --filter="bindings.members:serviceAccount:mss-runner@mss-production.iam.gserviceaccount.com"
```

### Health check fails
- Verify `/healthz` endpoint returns 200 OK
- Check Cloud Run logs for errors
- Verify environment variables are set correctly

