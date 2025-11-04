# Cloud Run Deployment Checklist

## ✅ Pre-Deployment Checklist

### 1. Code Fixes (Already Done)
- [x] Fixed `/healthz` endpoint for Cloud Run health checks
- [x] Improved entrypoint script with better logging
- [x] Added database initialization error handling
- [x] Verified Dockerfile.app is correct
- [x] Verified entrypoint script is executable

### 2. GitHub Secrets (REQUIRED - Verify These)

Go to: **GitHub Repo → Settings → Secrets and variables → Actions**

Required secrets:
- [ ] `GCP_PROJECT_ID` - Your GCP project ID (e.g., `mss-tts`)
- [ ] `GCP_SA_KEY` - Service account key JSON content
- [ ] `GCP_ARTIFACT_REGISTRY` - Registry name (default: `mss`)
- [ ] `GCP_SERVICE_ACCOUNT_EMAIL` - Service account email

### 3. GCP Prerequisites (Verify These)

```bash
# Check if you're authenticated
gcloud auth list

# Verify project is set
gcloud config get-value project

# Check Artifact Registry exists
gcloud artifacts repositories list --location=us-central1

# Verify required APIs are enabled
gcloud services list --enabled | grep -E "(run|artifactregistry|secretmanager|storage)"
```

## 🚀 Deployment Options

### Option 1: Automatic via GitHub Actions (Recommended)

1. **Verify all GitHub secrets are set** (see above)
2. **Commit and push to main/master branch:**
   ```bash
   git add .
   git commit -m "Fix Cloud Run deployment - add healthz endpoint and improve entrypoint"
   git push origin main
   ```
3. **Monitor deployment:**
   - Go to GitHub → Actions tab
   - Watch the "Build and Deploy to Google Cloud Run" workflow
   - Check for any errors

### Option 2: Manual Deployment

Use the provided script:
```bash
# Make executable (Linux/Mac)
chmod +x deploy-to-cloud-run.sh
./deploy-to-cloud-run.sh

# Or on Windows with Git Bash
bash deploy-to-cloud-run.sh
```

Or manually:
```bash
# Set your project
export GCP_PROJECT_ID=mss-tts  # or your project name
export GCP_ARTIFACT_REGISTRY=mss

# Build and deploy
docker build -f Dockerfile.app -t us-central1-docker.pkg.dev/$GCP_PROJECT_ID/$GCP_ARTIFACT_REGISTRY/mss-api:latest .
docker push us-central1-docker.pkg.dev/$GCP_PROJECT_ID/$GCP_ARTIFACT_REGISTRY/mss-api:latest

gcloud run deploy mss-api \
  --image us-central1-docker.pkg.dev/$GCP_PROJECT_ID/$GCP_ARTIFACT_REGISTRY/mss-api:latest \
  --region us-central1 \
  --platform managed \
  --allow-unauthenticated \
  --memory 2Gi \
  --cpu 2 \
  --timeout 300 \
  --set-env-vars "PORT=8080"
```

## ✅ Post-Deployment Verification

### 1. Check Service Status
```bash
gcloud run services describe mss-api --region us-central1
```

### 2. Test Health Endpoint
```bash
SERVICE_URL=$(gcloud run services describe mss-api --region us-central1 --format 'value(status.url)')
curl "$SERVICE_URL/healthz"
```

Expected response:
```json
{
  "status": "ok",
  "service": "MSS API",
  "version": "5.5.7",
  ...
}
```

### 3. View Logs
```bash
gcloud run services logs read mss-api --region us-central1 --limit=50
```

Look for:
- `[ENTRYPOINT] Starting MSS Flask application...`
- `[ENTRYPOINT] Starting gunicorn on 0.0.0.0:8080...`
- No error messages

### 4. Test Authentication Endpoints
```bash
# Test signup
curl -X POST "$SERVICE_URL/api/signup" \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"testpass123"}'

# Test login
curl -X POST "$SERVICE_URL/api/login" \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"testpass123"}'

# Test health
curl "$SERVICE_URL/healthz"
```

## 🔍 Troubleshooting

### If deployment fails:

1. **Check GitHub Actions logs:**
   - Go to Actions tab → Latest workflow run
   - Check each step for errors

2. **Check Cloud Run logs:**
   ```bash
   gcloud run services logs read mss-api --region us-central1 --limit=100
   ```

3. **Common issues:**
   - **"database is locked"** → Database timeout already fixed in code
   - **"gunicorn not found"** → Check Dockerfile installs dependencies
   - **"Failed to import app"** → Check PYTHONPATH is set correctly
   - **"Port not listening"** → Check entrypoint binds to 0.0.0.0:8080

4. **Test locally first:**
   ```bash
   docker build -f Dockerfile.app -t mss-test .
   docker run -p 8080:8080 -e PORT=8080 mss-test
   curl http://localhost:8080/healthz
   ```

## 📝 Next Steps After Successful Deployment

1. Update any frontend URLs to point to the new service URL
2. Configure custom domain (if needed)
3. Set up monitoring and alerts
4. Configure autoscaling if needed
5. Set up CI/CD for automatic deployments

## 🎯 Deployment Configuration Summary

- **Service Name:** `mss-api`
- **Region:** `us-central1`
- **Port:** `8080`
- **Health Check:** `/healthz`
- **Memory:** `2Gi`
- **CPU:** `2`
- **Timeout:** `300s`
- **Min Instances:** `0`
- **Max Instances:** `10`






