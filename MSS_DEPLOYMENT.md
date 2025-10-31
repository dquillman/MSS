# MSS Deployment Guide

## Current MSS Status

### Local Development
```
http://localhost:5000
```

### Production (After Deployment)
Will be: `https://mss-api-XXXXX-uc.a.run.app`
(Exact URL shown after deployment completes)

## Deployment Configuration

- **Service Name**: `mss-api`
- **Region**: `us-central1`
- **Project**: Set via `GCP_PROJECT_ID` GitHub secret
- **Registry**: `mss`

## Deployment Steps

### 1. Configure GitHub Secrets

Go to: **GitHub Repo → Settings → Secrets and variables → Actions**

Required secrets:
- `GCP_PROJECT_ID` - Your MSS GCP project ID
- `GCP_SA_KEY` - Service account key JSON content
- `GCP_ARTIFACT_REGISTRY` - `mss` (default)
- `GCP_SERVICE_ACCOUNT_EMAIL` - Service account email

### 2. Deploy

```bash
git add .
git commit -m "Fix Cloud Run deployment for MSS"
git push origin main
```

This triggers the GitHub Actions workflow which deploys to `mss-api`.

### 3. Get MSS Service URL

After deployment completes:

```bash
gcloud run services describe mss-api --region us-central1 --format 'value(status.url)'
```

Or check the GitHub Actions output for the service URL.

## Verify Deployment

```bash
# Test health endpoint
SERVICE_URL=$(gcloud run services describe mss-api --region us-central1 --format 'value(status.url)')
curl "$SERVICE_URL/healthz"

# Expected: {"status":"ok","service":"MSS API",...}
```

## Files Configured for MSS

- ✅ `.github/workflows/gcp-deploy.yml` - Deploys `mss-api`
- ✅ `Dockerfile.app` - MSS application container
- ✅ `docker/entrypoint-app.sh` - MSS startup script
- ✅ `web/api_server.py` - MSS Flask application with `/healthz` endpoint

