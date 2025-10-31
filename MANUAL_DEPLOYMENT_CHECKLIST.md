# ✅ Manual Deployment Checklist

## Step-by-Step: Trigger Deployment

### 1. Go to GitHub Actions
- Open: https://github.com/dquillman/MSS/actions
- You should see workflow runs listed

### 2. Select the Workflow
- In **left sidebar**, click: **"Build and Deploy to Google Cloud Run"**
- You'll see a list of previous runs (if any)

### 3. Run Workflow
- Look for **"Run workflow"** button (top right, purple button)
- Click it
- **Branch dropdown**: Select **`master`**
- Click green **"Run workflow"** button

### 4. Watch It Run
- A new workflow run appears (yellow circle = running)
- **Click on the run** to see detailed progress
- Watch these steps:
  1. ✅ Checkout code
  2. ✅ Set up Python
  3. ✅ Authenticate to Google Cloud
  4. ⏳ Build Docker image (3-5 minutes - THIS TAKES TIME)
  5. ⏳ Push Docker image (1-2 minutes)
  6. ⏳ Deploy to Cloud Run (2-3 minutes)
  7. ✅ Get service URL (shows your URL!)
  8. ✅ Health check

### 5. Get Your URL
- Scroll to **"Get service URL"** step
- You'll see: `Service deployed at: https://mss-api-XXXXX-uc.a.run.app`
- **Copy that URL!**

### 6. Test It
1. Open: `https://YOUR-URL/healthz`
   - Should show version 5.5.7
2. Open: `https://YOUR-URL/auth`
   - Should show login/signup page
3. Open: `https://YOUR-URL/studio`
   - Should show MSS Studio

---

## What to Expect

### Timeline:
- **0-1 min:** Setup (fast)
- **1-6 min:** Building Docker image (SLOWEST part)
- **6-8 min:** Pushing image
- **8-10 min:** Deploying to Cloud Run
- **10 min:** Done! ✅

### Success Indicators:
- ✅ Green checkmark on all steps
- ✅ "Get service URL" shows a URL
- ✅ "Health check" passes
- ✅ `/healthz` returns version 5.5.7

---

## Troubleshooting

### If It Fails:

**"Failed to authenticate"**
- Check `GCP_SA_KEY` secret has complete JSON
- Verify `GCP_SERVICE_ACCOUNT_EMAIL` is correct

**"Artifact Registry not found"**
- Verify `mss` repository exists in `us-central1`
- Check `GCP_ARTIFACT_REGISTRY` secret = `mss`

**"Cloud Run deployment failed"**
- Check service account has "Cloud Run Admin" role
- Verify `GCP_PROJECT_ID` = `mss-tts`

**"Health check failed"**
- Click on the failed step to see error details
- Check Cloud Run logs in Google Cloud Console

---

## After Deployment Succeeds

1. **Save your URL** - you'll need it!
2. **Test the endpoints:**
   - `/healthz` - should return version 5.5.7
   - `/auth` - login page
   - `/studio` - MSS Studio interface
3. **Bookmark it!** - This is your production MSS URL

---

## Need Help?

If you see any errors:
1. Click on the failed step
2. Read the error message
3. Tell me what it says - I'll help fix it!

---

**You've got this! The deployment will take about 10 minutes.** 🚀

