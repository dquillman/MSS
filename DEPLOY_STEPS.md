# 🚀 Deployment Steps - Ready to Deploy!

## Current Status

✅ Docker Desktop has been launched (but may still be starting)
✅ Deployment script is ready: `deploy-to-cloud-run.ps1`

## Step 1: Wait for Docker Desktop

**Check your system tray** (bottom-right corner):
- Look for the **Docker whale icon** 🐳
- Wait until it's **steady** (not blinking/animating)
- This usually takes 1-2 minutes after launch

**Verify Docker is ready:**
```powershell
docker ps
```

If this command **works without errors**, Docker is ready! ✅

## Step 2: Run Deployment

Once Docker is ready, run:

```powershell
.\deploy-to-cloud-run.ps1
```

The script will:
1. ✅ Verify all prerequisites
2. ✅ Build Docker image (5-10 minutes)
3. ✅ Push to Artifact Registry
4. ✅ Deploy to Cloud Run (2-3 minutes)
5. ✅ Test health endpoint

**Total deployment time: ~10-15 minutes**

## What to Expect

### During Build (Step 6)
- You'll see Docker building layers
- This is normal and takes several minutes
- Look for: `✅ Build complete`

### During Deployment (Step 8)
- Cloud Run is updating your service
- This takes 2-3 minutes
- Look for: `Service deployed at: https://...`

### Success Message
```
=== Deployment Complete! ===
📍 Service URL: https://mss-api-306798653079.us-central1.run.app
✅ Successfully deployed to Cloud Run!
```

## If Something Goes Wrong

### Docker Still Not Ready?
- **Wait another minute** - Docker Desktop can be slow to start
- **Check Windows Services**: Open Services app, look for "Docker Desktop Service"
- **Manual start**: Start Menu → Docker Desktop

### Build Fails?
- Make sure Docker Desktop is **fully running** (steady icon)
- Check Docker has enough resources: Docker Desktop → Settings → Resources
- Try: `docker system prune -a` to free space

### Deployment Fails?
Check logs:
```powershell
gcloud run services logs read mss-api --region us-central1
```

## Quick Commands

**Check Docker:**
```powershell
docker ps
```

**Check GCP auth:**
```powershell
gcloud auth list
```

**Check project:**
```powershell
gcloud config get-value project
```

**View deployed service:**
```powershell
gcloud run services describe mss-api --region us-central1
```

---

**Ready?** Once Docker is running (check with `docker ps`), run:
```powershell
.\deploy-to-cloud-run.ps1
```

