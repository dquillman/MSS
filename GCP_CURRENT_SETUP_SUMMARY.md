# Current Google Cloud Setup - Complete Analysis

**Date:** 2025-11-15  
**Project:** `mss-tts` (Project Number: 306798653079)

---

## ✅ What's Currently Configured and Working

### 1. Project & Service ✅
- **Project ID:** `mss-tts`
- **Project Number:** `306798653079`
- **Service Name:** `mss-api`
- **Region:** `us-central1`
- **Current URL:** https://mss-api-h5q3u63hbq-uc.a.run.app
- **Status:** ✅ Deployed and running

### 2. APIs Enabled ✅
All required APIs are enabled:
- ✅ `run.googleapis.com` - Cloud Run
- ✅ `artifactregistry.googleapis.com` - Artifact Registry
- ✅ `secretmanager.googleapis.com` - Secret Manager
- ✅ `sqladmin.googleapis.com` - Cloud SQL Admin
- ✅ `sql-component.googleapis.com` - Cloud SQL

### 3. Artifact Registry ✅
- ✅ Repository `mss` exists in `us-central1`
- ✅ Format: Docker
- ✅ Ready for container image storage

### 4. Cloud SQL PostgreSQL Database ✅
- **Instance:** `mss-postgres`
- **Version:** PostgreSQL 15
- **Region:** `us-central1`
- **Tier:** `db-f1-micro`
- **Database:** `mss`
- **User:** `postgres`
- **Connection:** Via Cloud SQL Proxy (Unix socket)
- **Connection String:** `postgresql://postgres:***@/mss?host=/cloudsql/mss-tts:us-central1:mss-postgres`

### 5. Cloud Run Service Configuration ✅
- **Memory:** 2Gi
- **CPU:** 2 vCPU
- **Timeout:** 300 seconds
- **Min Instances:** 0 (scales to zero)
- **Max Instances:** 10
- **Authentication:** Allow unauthenticated
- **Service Account:** `mss-tts@mss-tts.iam.gserviceaccount.com`

### 6. Environment Variables & Secrets ✅
**Environment Variables:**
- ✅ `DATABASE_URL` - PostgreSQL Cloud SQL connection (configured)

**Secret Manager Secrets (used by service):**
- ✅ `openai-api-key:latest` - Referenced and working
- ✅ `stripe-secret-key:latest` - Referenced and working
- ✅ `stripe-webhook-secret:latest` - Referenced and working

### 7. Service Accounts
- ✅ `mss-tts@mss-tts.iam.gserviceaccount.com` - Used by Cloud Run service
- ✅ `mss-drive@mss-tts.iam.gserviceaccount.com` - Custom service account
- ✅ `306798653079-compute@developer.gserviceaccount.com` - Default compute SA

---

## ⚠️ Issues & Missing Components

### 1. GitHub Actions Service Account ❌
**Status:** Not found

**Problem:** No dedicated service account for GitHub Actions deployments

**Impact:** 
- GitHub Actions workflow requires `GCP_SERVICE_ACCOUNT_EMAIL` secret
- Current workflow may fail if secret points to non-existent account

**Solution:** Create service account for GitHub Actions:
```bash
# Create service account
gcloud iam service-accounts create github-actions-deployer \
  --display-name="GitHub Actions Deployer" \
  --project=mss-tts

# Grant permissions
gcloud projects add-iam-policy-binding mss-tts \
  --member="serviceAccount:github-actions-deployer@mss-tts.iam.gserviceaccount.com" \
  --role="roles/run.admin"

gcloud projects add-iam-policy-binding mss-tts \
  --member="serviceAccount:github-actions-deployer@mss-tts.iam.gserviceaccount.com" \
  --role="roles/artifactregistry.writer"

gcloud projects add-iam-policy-binding mss-tts \
  --member="serviceAccount:github-actions-deployer@mss-tts.iam.gserviceaccount.com" \
  --role="roles/iam.serviceAccountUser"

# Create key
gcloud iam service-accounts keys create github-actions-key.json \
  --iam-account=github-actions-deployer@mss-tts.iam.gserviceaccount.com
```

### 2. Secret Manager Access ⚠️
**Status:** Secrets exist (service uses them) but may not be visible due to permissions

**Action:** Verify secrets are accessible:
```bash
# Try to describe secrets (may need viewer role)
gcloud secrets describe openai-api-key
gcloud secrets describe stripe-secret-key
gcloud secrets describe stripe-webhook-secret
```

### 3. GitHub Secrets Configuration ❓
**Status:** Unknown - needs verification

**Required Secrets:**
- `GCP_PROJECT_ID` = `mss-tts` (should be set)
- `GCP_SA_KEY` = Service account JSON key (needs to be created/verified)
- `GCP_SERVICE_ACCOUNT_EMAIL` = Service account email (needs to be set)
- `GCP_ARTIFACT_REGISTRY` = `mss` (optional, defaults to 'mss')
- `DATABASE_URL` = (optional, already configured in Cloud Run)

**Action:** Verify at: https://github.com/dquillman/MSS/settings/secrets/actions

---

## 📊 Current Configuration Summary

| Component | Status | Details |
|-----------|--------|---------|
| **Project** | ✅ | `mss-tts` (306798653079) |
| **Cloud Run Service** | ✅ | `mss-api` running |
| **Service URL** | ✅ | https://mss-api-h5q3u63hbq-uc.a.run.app |
| **PostgreSQL Database** | ✅ | Cloud SQL `mss-postgres` connected |
| **Artifact Registry** | ✅ | Repository `mss` exists |
| **APIs** | ✅ | All required APIs enabled |
| **Secrets** | ✅ | Configured and working |
| **GitHub Actions SA** | ❌ | Needs to be created |
| **GitHub Secrets** | ❓ | Needs verification |

---

## 🔧 Recommended Fixes

### Priority 1: Create GitHub Actions Service Account
```bash
# Set project
gcloud config set project mss-tts

# Create service account
gcloud iam service-accounts create github-actions-deployer \
  --display-name="GitHub Actions Deployer"

# Grant permissions
SA_EMAIL="github-actions-deployer@mss-tts.iam.gserviceaccount.com"

gcloud projects add-iam-policy-binding mss-tts \
  --member="serviceAccount:$SA_EMAIL" \
  --role="roles/run.admin"

gcloud projects add-iam-policy-binding mss-tts \
  --member="serviceAccount:$SA_EMAIL" \
  --role="roles/artifactregistry.writer"

gcloud projects add-iam-policy-binding mss-tts \
  --member="serviceAccount:$SA_EMAIL" \
  --role="roles/iam.serviceAccountUser"

# Create key file
gcloud iam service-accounts keys create github-actions-key.json \
  --iam-account=$SA_EMAIL

# Display key (copy to GitHub Secrets)
cat github-actions-key.json
```

### Priority 2: Update GitHub Secrets
Go to: https://github.com/dquillman/MSS/settings/secrets/actions

Add/Update:
- `GCP_PROJECT_ID` = `mss-tts`
- `GCP_SA_KEY` = (contents of `github-actions-key.json`)
- `GCP_SERVICE_ACCOUNT_EMAIL` = `github-actions-deployer@mss-tts.iam.gserviceaccount.com`
- `GCP_ARTIFACT_REGISTRY` = `mss` (optional)

### Priority 3: Verify Secret Manager Access
```bash
# Grant Cloud Run SA access to secrets (if not already)
gcloud secrets add-iam-policy-binding openai-api-key \
  --member="serviceAccount:306798653079-compute@developer.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"

gcloud secrets add-iam-policy-binding stripe-secret-key \
  --member="serviceAccount:306798653079-compute@developer.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"

gcloud secrets add-iam-policy-binding stripe-webhook-secret \
  --member="serviceAccount:306798653079-compute@developer.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"
```

---

## ✅ Overall Status

**Infrastructure:** 🟢 **Fully Configured**
- All GCP resources are set up correctly
- Service is running
- Database is connected
- Secrets are working

**CI/CD:** 🟡 **Needs Setup**
- GitHub Actions service account missing
- GitHub Secrets need verification/update

**Next Steps:**
1. Create GitHub Actions service account
2. Update GitHub Secrets
3. Test deployment via GitHub Actions

---

**Last Checked:** 2025-11-15

