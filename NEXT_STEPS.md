# 🚀 Next Steps: Cloud Run Deployment

## ✅ What We Fixed

All the fixes for Cloud Run deployment are complete:

1. **Health Endpoint** - Added `/healthz` route (Cloud Run requirement)
2. **Entrypoint Script** - Added comprehensive logging and error checking
3. **Database Timeout** - Added 10-second timeout to prevent locking
4. **Error Handling** - Made database initialization more resilient

## 📋 Step-by-Step Deployment

### Step 1: Verify GitHub Secrets (REQUIRED)

Before deploying, you MUST configure these secrets in GitHub:

1. Go to: **Your GitHub Repo → Settings → Secrets and variables → Actions**

2. Add/verify these secrets:
   - `GCP_PROJECT_ID` = Your GCP project ID (e.g., `mss-tts`)
   - `GCP_SA_KEY` = Service account JSON key (full file content)
   - `GCP_ARTIFACT_REGISTRY` = `mss` (or your registry name)
   - `GCP_SERVICE_ACCOUNT_EMAIL` = `mss-runner@PROJECT_ID.iam.gserviceaccount.com`

   **See `verify-github-secrets.md` for detailed instructions**

### Step 2: Commit and Push Changes

The deployment is triggered by pushing to `main` or `master` branch:

```bash
# Stage the important files
git add web/api_server.py
git add docker/entrypoint-app.sh
git add web/database.py
git add .github/workflows/gcp-deploy.yml
git add Dockerfile.app
git add DEPLOYMENT_CHECKLIST.md

# Commit
git commit -m "Fix Cloud Run deployment: Add healthz endpoint, improve entrypoint logging, fix database timeout"

# Push to trigger deployment
git push origin main
```

### Step 3: Monitor Deployment

1. Go to **GitHub → Actions tab**
2. Click on the running workflow: "Build and Deploy to Google Cloud Run"
3. Watch the progress:
   - ✅ Checkout code
   - ✅ Set up Python
   - ✅ Authenticate to Google Cloud
   - ✅ Build Docker image
   - ✅ Push to Artifact Registry
   - ✅ Deploy to Cloud Run
   - ✅ Health check

### Step 4: Verify Deployment

Once deployment completes, test the service:

```bash
# Get the service URL
gcloud run services describe mss-api --region us-central1 --format 'value(status.url)'

# Test health endpoint (should return JSON)
curl https://YOUR_SERVICE_URL/healthz

# Test authentication
curl -X POST https://YOUR_SERVICE_URL/api/signup \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"testpass123"}'
```

## 📁 Files Changed for Deployment

Key files modified:
- ✅ `web/api_server.py` - Added `/healthz` endpoint, improved error handling
- ✅ `docker/entrypoint-app.sh` - Added logging and verification steps
- ✅ `web/database.py` - Added database connection timeout
- ✅ `.github/workflows/gcp-deploy.yml` - Deployment workflow (already configured)

New helper files:
- 📄 `DEPLOYMENT_CHECKLIST.md` - Complete deployment guide
- 📄 `verify-github-secrets.md` - How to set up GitHub secrets
- 📄 `deploy-to-cloud-run.sh` - Manual deployment script
- 📄 `test-docker-build.sh` - Test Docker build locally

## 🔍 If Something Goes Wrong

### Check Logs

**GitHub Actions logs:**
- GitHub → Actions → Latest workflow → Click on failed step

**Cloud Run logs:**
```bash
gcloud run services logs read mss-api --region us-central1 --limit=100
```

### Common Issues

1. **"Secret not found"** → Verify all GitHub secrets are set
2. **"Permission denied"** → Check service account has correct permissions
3. **"Container failed to start"** → Check Cloud Run logs for startup errors
4. **"Health check failed"** → Verify `/healthz` endpoint returns 200 OK

### Test Locally First

If you want to test before deploying:

```bash
# Build and run locally
docker build -f Dockerfile.app -t mss-test .
docker run -p 8080:8080 -e PORT=8080 mss-test

# In another terminal, test:
curl http://localhost:8080/healthz
```

## ✅ Expected Result

After successful deployment:
- ✅ Service URL will be printed in GitHub Actions
- ✅ Health check at `/healthz` returns: `{"status": "ok", ...}`
- ✅ Authentication endpoints work (`/api/login`, `/api/signup`)
- ✅ Service is accessible without authentication

## 🎯 Quick Commands Reference

```bash
# Check deployment status
gcloud run services describe mss-api --region us-central1

# View logs
gcloud run services logs read mss-api --region us-central1 --limit=50

# Get service URL
gcloud run services describe mss-api --region us-central1 --format 'value(status.url)'

# Test health
curl $(gcloud run services describe mss-api --region us-central1 --format 'value(status.url)')/healthz
```

---

**Ready to deploy?** Follow Step 1 (verify secrets) and Step 2 (commit & push) above! 🚀


