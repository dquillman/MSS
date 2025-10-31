# 🚀 Quick Deployment Guide

## Pre-Flight Check

Before deploying, verify these are ready:

1. **Docker Desktop is running**
   - Check system tray for Docker whale icon
   - Or run: `docker ps` (should work without errors)

2. **GCP Authentication**
   - Run: `gcloud auth list`
   - Should show an active account

3. **Project ID is correct**
   - Current project: `mss-tts`
   - Verify: `gcloud config get-value project`

## Deploy Now

### Step 1: Start Docker Desktop (if not running)

**Quick check:**
```powershell
.\check-docker.ps1
```

**If Docker is not running:**
- Option A: Open Docker Desktop from Start Menu
- Option B: Run: `.\start-docker.ps1` (if script exists)

### Step 2: Run Deployment Script

```powershell
.\deploy-to-cloud-run.ps1
```

The script will:
1. ✅ Check gcloud CLI
2. ✅ Check Docker (and verify it's running)
3. ✅ Verify GCP authentication
4. ✅ Set GCP project
5. ✅ Configure Docker for Artifact Registry
6. ✅ Build Docker image (~5-10 minutes)
7. ✅ Push to Artifact Registry
8. ✅ Deploy to Cloud Run (~2-3 minutes)
9. ✅ Test health endpoint

**Total time: ~10-15 minutes**

## Troubleshooting

### Docker Not Running
```
ERROR: error during connect: Head "http://%2F%2F.%2Fpipe%2FdockerDesktopLinuxEngine/_ping"
```
**Fix:** Start Docker Desktop and wait 30 seconds, then retry.

### Build Fails
```
ERROR: Docker build failed!
```
**Fix:** 
- Make sure Docker Desktop is fully started
- Check Docker has enough resources (Settings → Resources)
- Try: `docker system prune -a` to free space

### Push Fails
```
ERROR: Failed to push image
```
**Fix:** Run manually:
```powershell
gcloud auth configure-docker us-central1-docker.pkg.dev
```

### Deployment Fails
```
ERROR: Deployment failed!
```
**Fix:** Check Cloud Run logs:
```powershell
gcloud run services logs read mss-api --region us-central1
```

## After Deployment

Your service will be available at:
- **URL:** `https://mss-api-306798653079.us-central1.run.app`
- **Health:** `https://mss-api-306798653079.us-central1.run.app/healthz`

## Next Steps

1. **Update frontend** to use new service URL (if changed)
2. **Test authentication** at `/auth`
3. **Verify secrets** are set in Cloud Run (if needed):
   ```powershell
   gcloud run services describe mss-api --region us-central1
   ```
