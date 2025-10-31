# Verify GitHub Secrets for Cloud Run Deployment

## Required GitHub Secrets

Go to your GitHub repository → Settings → Secrets and variables → Actions and verify these secrets exist:

### Required Secrets:

1. **GCP_PROJECT_ID**
   - Example: `mss-tts` or `mss-production`
   - Value: Your Google Cloud Project ID

2. **GCP_SA_KEY**
   - Format: JSON content of service account key
   - How to create:
     ```bash
     gcloud iam service-accounts keys create github-actions-key.json \
       --iam-account=mss-runner@PROJECT_ID.iam.gserviceaccount.com
     ```
   - Copy the entire JSON file content into this secret

3. **GCP_ARTIFACT_REGISTRY** (optional, defaults to 'mss')
   - Example: `mss`
   - Value: Your Artifact Registry repository name

4. **GCP_SERVICE_ACCOUNT_EMAIL**
   - Example: `mss-runner@mss-tts.iam.gserviceaccount.com`
   - Format: `SERVICE_ACCOUNT_NAME@PROJECT_ID.iam.gserviceaccount.com`

## Quick Verification

Run these commands to verify your GCP setup:

```bash
# 1. Verify project
gcloud config get-value project

# 2. List service accounts
gcloud iam service-accounts list

# 3. Check Artifact Registry
gcloud artifacts repositories list --location=us-central1

# 4. Verify Cloud Run API is enabled
gcloud services list --enabled | grep run.googleapis.com
```

## Test Deployment Locally

Before deploying, test the Docker build:

**On Windows (PowerShell):**
```powershell
docker build -f Dockerfile.app -t mss-api-test .
docker run -p 8080:8080 -e PORT=8080 mss-api-test
```

**On Linux/Mac:**
```bash
bash test-docker-build.sh
```

Then test:
```bash
curl http://localhost:8080/healthz
```

## Deploy to Cloud Run

Once secrets are verified and local test passes:

1. **Push to main/master branch** - This will trigger automatic deployment
   
   OR

2. **Manual deployment via GitHub Actions:**
   - Go to Actions tab in GitHub
   - Select "Build and Deploy to Google Cloud Run"
   - Click "Run workflow"
   - Select branch and click "Run workflow"

## Verify Deployment

After deployment completes:

```bash
# Get service URL
gcloud run services describe mss-api --region us-central1 --format 'value(status.url)'

# Test health endpoint
curl https://YOUR_SERVICE_URL/healthz
```


