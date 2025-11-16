# Google Cloud Platform Setup Guide for MSS

This guide will help you set up all required Google Cloud services for MSS deployment.

## Prerequisites

1. Google Cloud account (https://cloud.google.com)
2. `gcloud` CLI installed (https://cloud.google.com/sdk/docs/install)
3. GitHub repository access

---

## Step 1: Create/Select GCP Project

```bash
# Login to Google Cloud
gcloud auth login

# Create a new project (or use existing)
gcloud projects create mss-deployment-447320 --name="MSS Production"

# Set as active project
gcloud config set project mss-deployment-447320

# Get your project ID
PROJECT_ID=$(gcloud config get-value project)
echo "Project ID: $PROJECT_ID"
```

**Note:** Replace `mss-deployment-447320` with your actual project ID if different.

---

## Step 2: Enable Required APIs

```bash
# Enable required Google Cloud APIs
gcloud services enable \
  run.googleapis.com \
  artifactregistry.googleapis.com \
  secretmanager.googleapis.com \
  sqladmin.googleapis.com \
  cloudbuild.googleapis.com \
  iamcredentials.googleapis.com
```

---

## Step 3: Create Artifact Registry Repository

```bash
# Create Docker repository for storing container images
gcloud artifacts repositories create mss \
  --repository-format=docker \
  --location=us-central1 \
  --description="MSS Docker images"

# Verify
gcloud artifacts repositories list
```

---

## Step 4: Create Service Account for GitHub Actions

```bash
# Create service account
gcloud iam service-accounts create github-actions-deployer \
  --display-name="GitHub Actions Deployer" \
  --description="Service account for GitHub Actions to deploy to Cloud Run"

# Get service account email
SA_EMAIL=$(gcloud iam service-accounts list --filter="displayName:GitHub Actions Deployer" --format="value(email)")
echo "Service Account Email: $SA_EMAIL"

# Grant necessary permissions
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:$SA_EMAIL" \
  --role="roles/run.admin"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:$SA_EMAIL" \
  --role="roles/artifactregistry.writer"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:$SA_EMAIL" \
  --role="roles/secretmanager.secretAccessor"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:$SA_EMAIL" \
  --role="roles/iam.serviceAccountUser"
```

---

## Step 5: Create Service Account Key

```bash
# Create and download service account key
gcloud iam service-accounts keys create github-actions-key.json \
  --iam-account=$SA_EMAIL

# Display the key (you'll need to copy this to GitHub Secrets)
cat github-actions-key.json

# IMPORTANT: Delete the local file after copying to GitHub Secrets
# rm github-actions-key.json
```

---

## Step 6: Set Up Secret Manager Secrets

```bash
# Create secrets in Secret Manager
# These will be used by Cloud Run

# OpenAI API Key
echo -n "your-openai-api-key-here" | gcloud secrets create openai-api-key \
  --data-file=- \
  --replication-policy="automatic"

# Stripe Secret Key
echo -n "sk_live_your-stripe-secret-key" | gcloud secrets create stripe-secret-key \
  --data-file=- \
  --replication-policy="automatic"

# Stripe Webhook Secret
echo -n "whsec_your-webhook-secret" | gcloud secrets create stripe-webhook-secret \
  --data-file=- \
  --replication-policy="automatic"
```

**Note:** Replace the placeholder values with your actual API keys.

---

## Step 7: Set Up PostgreSQL Database (Optional but Recommended)

### Option A: Cloud SQL (Managed PostgreSQL)

```bash
# Create Cloud SQL instance
gcloud sql instances create mss-postgres \
  --database-version=POSTGRES_15 \
  --tier=db-f1-micro \
  --region=us-central1 \
  --root-password=YOUR_SECURE_PASSWORD

# Create database
gcloud sql databases create mss --instance=mss-postgres

# Create database user
gcloud sql users create mssuser \
  --instance=mss-postgres \
  --password=YOUR_SECURE_PASSWORD

# Get connection name
INSTANCE_CONNECTION_NAME=$(gcloud sql instances describe mss-postgres --format="value(connectionName)")
echo "Connection name: $INSTANCE_CONNECTION_NAME"

# Build DATABASE_URL
# Format: postgresql://user:password@/database?host=/cloudsql/project:region:instance
DATABASE_URL="postgresql://mssuser:YOUR_SECURE_PASSWORD@/mss?host=/cloudsql/$INSTANCE_CONNECTION_NAME"
echo "DATABASE_URL: $DATABASE_URL"
```

### Option B: External PostgreSQL (Neon, Railway, etc.)

If using an external PostgreSQL service:
1. Get connection string from your provider
2. Format: `postgresql://user:password@host:port/database`
3. Store in GitHub Secret (see Step 8)

---

## Step 8: Configure GitHub Secrets

Go to your GitHub repository: https://github.com/dquillman/MSS/settings/secrets/actions

Add these secrets:

### Required Secrets:

1. **GCP_PROJECT_ID**
   - Value: Your GCP project ID (e.g., `mss-deployment-447320`)

2. **GCP_SA_KEY**
   - Value: Contents of `github-actions-key.json` (the entire JSON file)
   - Copy the entire JSON from the file created in Step 5

3. **GCP_SERVICE_ACCOUNT_EMAIL**
   - Value: Service account email (e.g., `github-actions-deployer@mss-deployment-447320.iam.gserviceaccount.com`)

4. **GCP_ARTIFACT_REGISTRY** (Optional)
   - Value: `mss` (or your repository name)
   - Defaults to `mss` if not set

### Optional but Recommended:

5. **DATABASE_URL**
   - Value: PostgreSQL connection string
   - Format: `postgresql://user:password@host:port/database`
   - Or for Cloud SQL: `postgresql://user:password@/database?host=/cloudsql/project:region:instance`

### Secret Manager Secrets (Already Created):

These are automatically used by Cloud Run via `--set-secrets` flag:
- `openai-api-key:latest`
- `stripe-secret-key:latest`
- `stripe-webhook-secret:latest`

---

## Step 9: Grant Cloud Run Access to Secrets

```bash
# Get the Cloud Run service account
CLOUD_RUN_SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"
PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format="value(projectNumber)")

# Grant Secret Manager access
gcloud secrets add-iam-policy-binding openai-api-key \
  --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"

gcloud secrets add-iam-policy-binding stripe-secret-key \
  --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"

gcloud secrets add-iam-policy-binding stripe-webhook-secret \
  --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"
```

---

## Step 10: Test Deployment

1. **Push to GitHub** - This will trigger the deployment workflow
2. **Monitor deployment** at: https://github.com/dquillman/MSS/actions
3. **Check Cloud Run** service: https://console.cloud.google.com/run

---

## Step 11: Get Your Service URL

After deployment, get your service URL:

```bash
gcloud run services describe mss-api \
  --region=us-central1 \
  --format="value(status.url)"
```

Or check in Cloud Console: https://console.cloud.google.com/run

---

## Verification Checklist

- [ ] GCP project created and set as active
- [ ] All required APIs enabled
- [ ] Artifact Registry repository created
- [ ] Service account created with proper permissions
- [ ] Service account key downloaded
- [ ] Secret Manager secrets created (OpenAI, Stripe)
- [ ] PostgreSQL database set up (Cloud SQL or external)
- [ ] GitHub Secrets configured:
  - [ ] GCP_PROJECT_ID
  - [ ] GCP_SA_KEY
  - [ ] GCP_SERVICE_ACCOUNT_EMAIL
  - [ ] DATABASE_URL (optional but recommended)
- [ ] Cloud Run service account has access to secrets
- [ ] Deployment workflow runs successfully
- [ ] Service is accessible at Cloud Run URL

---

## Troubleshooting

### Deployment Fails

1. **Check GitHub Actions logs** for specific errors
2. **Verify all secrets are set** in GitHub repository
3. **Check service account permissions**:
   ```bash
   gcloud projects get-iam-policy $PROJECT_ID \
     --flatten="bindings[].members" \
     --filter="bindings.members:serviceAccount:$SA_EMAIL"
   ```

### Database Connection Issues

1. **Test connection locally**:
   ```bash
   export DATABASE_URL="your-connection-string"
   python -c "from web.database import get_db; conn = get_db(); print('Connected!')"
   ```

2. **For Cloud SQL**, ensure Cloud SQL Admin API is enabled and instance is running

### Secret Manager Access Denied

1. **Verify Cloud Run service account** has `secretAccessor` role
2. **Check secret exists**:
   ```bash
   gcloud secrets list
   ```

---

## Cost Estimation

- **Cloud Run**: Pay per request (~$0.40 per million requests)
- **Artifact Registry**: First 0.5 GB free, then $0.10/GB/month
- **Secret Manager**: $0.06 per secret version per month
- **Cloud SQL** (if used): db-f1-micro starts at ~$7/month

**Estimated monthly cost (light usage):** $10-20/month

---

## Next Steps

1. Set up custom domain (optional)
2. Configure monitoring and alerts
3. Set up database backups
4. Configure email service (SendGrid/Postmark)
5. Set up Stripe webhooks

---

**Last Updated:** 2025-11-15

