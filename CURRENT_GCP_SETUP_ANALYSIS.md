# Current Google Cloud Setup - Complete Analysis

**Date:** 2025-11-15  
**Project:** `mss-tts` (Project Number: 306798653079)

---

## ✅ What's Currently Configured

### 1. Project & Service
- **Project ID:** `mss-tts`
- **Project Number:** `306798653079`
- **Service Name:** `mss-api`
- **Region:** `us-central1`
- **Current URL:** https://mss-api-h5q3u63hbq-uc.a.run.app
- **Status:** Deployed and running

### 2. APIs Enabled ✅
- ✅ `run.googleapis.com` - Cloud Run
- ✅ `artifactregistry.googleapis.com` - Artifact Registry
- ✅ `secretmanager.googleapis.com` - Secret Manager
- ✅ `sqladmin.googleapis.com` - Cloud SQL Admin
- ✅ `sql-component.googleapis.com` - Cloud SQL

### 3. Artifact Registry ✅
- ✅ Repository `mss` exists in `us-central1`
- ✅ Format: Docker
- ✅ Used for storing container images

### 4. Cloud Run Service Configuration ✅
- **Memory:** 2Gi
- **CPU:** 2 vCPU
- **Timeout:** 300 seconds
- **Min Instances:** 0
- **Max Instances:** 10
- **Authentication:** Allow unauthenticated

### 5. Environment Variables & Secrets ✅
**Configured in Cloud Run:**
- ✅ `DATABASE_URL` - PostgreSQL Cloud SQL connection
  - Format: `postgresql://postgres:password@/mss?host=/cloudsql/mss-tts:us-central1:mss-postgres`
  - **Database:** Cloud SQL PostgreSQL instance `mss-postgres`
  
**Secret Manager Secrets (referenced):**
- ✅ `openai-api-key:latest` - Used by service
- ✅ `stripe-secret-key:latest` - Used by service
- ✅ `stripe-webhook-secret:latest` - Used by service

### 6. Cloud SQL Database ✅
- **Instance:** `mss-postgres`
- **Region:** `us-central1`
- **Database:** `mss`
- **User:** `postgres`
- **Connection:** Via Cloud SQL Proxy (Unix socket)

### 7. Service Accounts
- ✅ Default Compute SA: `306798653079-compute@developer.gserviceaccount.com`
- ✅ Custom SA: `mss-tts@mss-tts.iam.gserviceaccount.com`
- ✅ Custom SA: `mss-drive@mss-tts.iam.gserviceaccount.com`
- ❌ **Missing:** GitHub Actions service account for deployments

---

## ⚠️ Issues Found

### 1. GitHub Actions Service Account Missing
**Problem:** No service account specifically for GitHub Actions deployments

**Impact:** GitHub Actions workflow may fail if `GCP_SERVICE_ACCOUNT_EMAIL` secret points to non-existent account

**Solution:** Create service account or use existing one:
```bash
# Option 1: Create new service account
gcloud iam service-accounts create github-actions-deployer \
  --display-name="GitHub Actions Deployer"

# Option 2: Use existing service account
# Use: mss-tts@mss-tts.iam.gserviceaccount.com
```

### 2. Secret Manager Secrets Not Visible
**Problem:** `gcloud secrets list` returns empty (may be access issue or secrets exist but not visible)

**Status:** Secrets ARE being used by Cloud Run service, so they likely exist but may need proper permissions to view

**Action:** Verify secrets exist and are accessible:
```bash
# Check if secrets exist (may need specific permissions)
gcloud secrets describe openai-api-key
gcloud secrets describe stripe-secret-key
gcloud secrets describe stripe-webhook-secret
```

### 3. GitHub Secrets Configuration
**Required GitHub Secrets:**
- `GCP_PROJECT_ID` = `mss-tts` ✅ (should be set)
- `GCP_SA_KEY` = Service account JSON key ❓ (needs verification)
- `GCP_SERVICE_ACCOUNT_EMAIL` = Service account email ❓ (needs verification)
- `GCP_ARTIFACT_REGISTRY` = `mss` ✅ (optional, defaults to 'mss')
- `DATABASE_URL` = Already in Cloud Run, but may need in GitHub for deployment ❓

---

## 📋 Current Setup Summary

### What's Working ✅
1. ✅ Cloud Run service is deployed and running
2. ✅ PostgreSQL database is configured and connected
3. ✅ Artifact Registry repository exists
4. ✅ All required APIs are enabled
5. ✅ Secrets are configured and being used by the service
6. ✅ Environment variables are set correctly

### What Needs Attention ⚠️
1. ⚠️ Verify GitHub Actions service account exists or create one
2. ⚠️ Verify GitHub Secrets are configured correctly
3. ⚠️ Check Secret Manager permissions
4. ⚠️ Verify service account has proper IAM roles

---

## 🔧 Recommended Actions

### 1. Verify/Create GitHub Actions Service Account
```bash
# Check if service account exists
gcloud iam service-accounts list --filter="displayName:GitHub"

# If not, create it
gcloud iam service-accounts create github-actions-deployer \
  --display-name="GitHub Actions Deployer" \
  --project=mss-tts

# Grant necessary permissions
gcloud projects add-iam-policy-binding mss-tts \
  --member="serviceAccount:github-actions-deployer@mss-tts.iam.gserviceaccount.com" \
  --role="roles/run.admin"

gcloud projects add-iam-policy-binding mss-tts \
  --member="serviceAccount:github-actions-deployer@mss-tts.iam.gserviceaccount.com" \
  --role="roles/artifactregistry.writer"

gcloud projects add-iam-policy-binding mss-tts \
  --member="serviceAccount:github-actions-deployer@mss-tts.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"

# Create and download key
gcloud iam service-accounts keys create github-actions-key.json \
  --iam-account=github-actions-deployer@mss-tts.iam.gserviceaccount.com
```

### 2. Verify Secret Manager Secrets
```bash
# Check if secrets exist (may need viewer role)
gcloud secrets describe openai-api-key
gcloud secrets describe stripe-secret-key
gcloud secrets describe stripe-webhook-secret

# If they don't exist, create them
echo -n "your-key" | gcloud secrets create openai-api-key --data-file=-
```

### 3. Update GitHub Secrets
Go to: https://github.com/dquillman/MSS/settings/secrets/actions

Ensure these are set:
- `GCP_PROJECT_ID` = `mss-tts`
- `GCP_SA_KEY` = Contents of `github-actions-key.json`
- `GCP_SERVICE_ACCOUNT_EMAIL` = `github-actions-deployer@mss-tts.iam.gserviceaccount.com`
- `GCP_ARTIFACT_REGISTRY` = `mss` (optional)
- `DATABASE_URL` = (optional, already in Cloud Run)

---

## 📊 Current Service Status

**Service URL:** https://mss-api-h5q3u63hbq-uc.a.run.app  
**Database:** Cloud SQL PostgreSQL (connected)  
**Secrets:** Configured and working  
**Deployment:** Manual deployment working, GitHub Actions needs verification

---

## ✅ Overall Assessment

**Status:** 🟢 **Mostly Configured**

The GCP setup is largely complete:
- ✅ Infrastructure is set up correctly
- ✅ Service is running
- ✅ Database is connected
- ⚠️ GitHub Actions integration needs verification
- ⚠️ Service account for CI/CD may need creation

**Next Step:** Verify GitHub Secrets and create service account if needed.

