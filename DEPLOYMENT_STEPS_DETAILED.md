# Step-by-Step: Deploy MSS to MSS-STT (mss-tts project)

## Overview
- **Project ID**: `mss-tts`
- **Account**: `dquillman2112@gmail.com`
- **Service Name**: `mss-api`
- **Version**: 5.5.7

---

## STEP 1: Create Service Account in Google Cloud (5 minutes)

### 1.1 Go to Google Cloud Console
1. Open: https://console.cloud.google.com
2. **Make sure you're signed in as**: `dquillman2112@gmail.com`
3. **Select project**: `mss-tts` (top dropdown)

### 1.2 Create Service Account
1. Go to: **IAM & Admin** → **Service Accounts**
2. Click **"+ CREATE SERVICE ACCOUNT"**
3. Fill in:
   - **Service account name**: `mss-runner`
   - **Service account ID**: (auto-filled) `mss-runner`
   - Click **"CREATE AND CONTINUE"**

### 1.3 Grant Permissions
On the "Grant this service account access" page:
1. Click **"+ ADD ANOTHER ROLE"** for each role below:
   - Role: **Cloud Run Admin**
   - Role: **Service Account User**
   - Role: **Artifact Registry Writer**
   - Role: **Storage Admin** (if you use Google Cloud Storage)
2. Click **"CONTINUE"**
3. Click **"DONE"**

### 1.4 Create Key
1. Find `mss-runner@mss-tts.iam.gserviceaccount.com` in the list
2. Click on it
3. Go to **"KEYS"** tab
4. Click **"ADD KEY"** → **"Create new key"**
5. Select **JSON**
6. Click **"CREATE"**
7. **IMPORTANT**: The JSON file downloads - **SAVE THIS FILE** (you'll need to copy its contents)

---

## STEP 2: Add GitHub Secrets (3 minutes)

### 2.1 Go to GitHub Repository Settings
1. Open: https://github.com/dquillman/MSS
2. Click **"Settings"** tab (top right)
3. In left sidebar, click **"Secrets and variables"** → **"Actions"**

### 2.2 Add/Update Secrets
For each secret below, click **"New repository secret"** if it doesn't exist, or click the secret name to update it:

#### Secret 1: GCP_PROJECT_ID
- **Name**: `GCP_PROJECT_ID`
- **Value**: `mss-tts`
- Click **"Add secret"** or **"Update secret"**

#### Secret 2: GCP_SA_KEY
- **Name**: `GCP_SA_KEY`
- **Value**: Open the JSON file you downloaded in Step 1.4
  - **Copy the ENTIRE contents** (should start with `{` and end with `}`)
  - Paste it here
- Click **"Add secret"** or **"Update secret"**

#### Secret 3: GCP_SERVICE_ACCOUNT_EMAIL
- **Name**: `GCP_SERVICE_ACCOUNT_EMAIL`
- **Value**: `mss-runner@mss-tts.iam.gserviceaccount.com`
- Click **"Add secret"** or **"Update secret"**

#### Secret 4: GCP_ARTIFACT_REGISTRY
- **Name**: `GCP_ARTIFACT_REGISTRY`
- **Value**: `mss`
- Click **"Add secret"** or **"Update secret"**

### 2.3 Verify All Secrets Exist
You should see these 4 secrets listed:
- ✅ GCP_PROJECT_ID
- ✅ GCP_SA_KEY
- ✅ GCP_SERVICE_ACCOUNT_EMAIL
- ✅ GCP_ARTIFACT_REGISTRY

---

## STEP 3: Create Artifact Registry (if it doesn't exist)

### 3.1 Check if Registry Exists
1. In Google Cloud Console: https://console.cloud.google.com/artifacts
2. Select project: `mss-tts`
3. Look for a repository named `mss` in `us-central1` region

### 3.2 Create Registry (if needed)
If you don't see `mss` repository:
1. Click **"+ CREATE REPOSITORY"**
2. Fill in:
   - **Repository name**: `mss`
   - **Format**: **Docker**
   - **Mode**: **Standard**
   - **Location**: `us-central1`
3. Click **"CREATE"**

---

## STEP 4: Deploy via GitHub Actions (10 minutes)

### 4.1 Go to Actions Tab
1. Open: https://github.com/dquillman/MSS/actions
2. In left sidebar, click **"Build and Deploy to Google Cloud Run"**

### 4.2 Run Workflow
1. Click **"Run workflow"** button (top right)
2. **Branch**: Select `master`
3. Click **"Run workflow"** button (green)

### 4.3 Watch Progress
1. You'll see a new workflow run appear
2. Click on it to see progress
3. Steps to watch:
   - ✅ Checkout code
   - ✅ Set up Python
   - ✅ Authenticate to Google Cloud
   - ✅ Build Docker image
   - ✅ Push Docker image
   - ✅ Deploy to Cloud Run
   - ✅ Get service URL
   - ✅ Health check

### 4.4 Wait for Completion
- **Expected time**: 5-10 minutes
- **Success**: ✅ Green checkmark
- **Failure**: ❌ Red X (click to see error)

---

## STEP 5: Get Your Service URL

### 5.1 From GitHub Actions
1. In the completed workflow run, scroll to **"Get service URL"** step
2. You'll see: `Service deployed at: https://mss-api-XXXXX-uc.a.run.app`
3. **Copy this URL** - this is your MSS service!

### 5.2 Test the Service
1. Open the URL in your browser
2. Add `/healthz` to the end: `https://YOUR-URL/healthz`
3. You should see:
   ```json
   {
     "status": "ok",
     "service": "MSS API",
     "version": "5.5.7"
   }
   ```

### 5.3 Test Login/Signup
1. Go to: `https://YOUR-URL/auth`
2. Try creating a new account
3. Try logging in

---

## STEP 6: Clean Up Old Service (Other Google Account)

### 6.1 Identify Old Service
1. Sign in to Google Cloud Console with the **OTHER** Google account
2. Look for a project that has a Cloud Run service (might be `iatlas-app` or similar)

### 6.2 Stop the Old Service
**Option A: Set Traffic to 0% (Safe - keeps service but stops traffic)**
```bash
gcloud run services update-traffic OLD_SERVICE_NAME \
  --to-latest 0 \
  --region us-central1
```

**Option B: Delete Service (Permanent)**
```bash
gcloud run services delete OLD_SERVICE_NAME \
  --region us-central1 \
  --quiet
```

### 6.3 Remove Old GitHub Secrets (if any)
1. Go to GitHub → Settings → Secrets
2. If you see secrets pointing to the old project, delete them

---

## Troubleshooting

### Workflow Fails at "Authenticate to Google Cloud"
- Check `GCP_SA_KEY` secret - make sure JSON is complete
- Verify service account email matches

### Workflow Fails at "Deploy to Cloud Run"
- Check service account has "Cloud Run Admin" role
- Verify project ID is correct

### Health Check Fails
- Check `/healthz` endpoint exists in `web/api_server.py`
- Look at Cloud Run logs: `gcloud run services logs read mss-api --region us-central1`

### Can't Find Service Account
- Make sure you're in the `mss-tts` project
- Check you're signed in as `dquillman2112@gmail.com`

---

## Summary Checklist

- [ ] Created service account `mss-runner` in `mss-tts` project
- [ ] Granted all required roles to service account
- [ ] Created and downloaded JSON key
- [ ] Added `GCP_PROJECT_ID` secret = `mss-tts`
- [ ] Added `GCP_SA_KEY` secret (full JSON content)
- [ ] Added `GCP_SERVICE_ACCOUNT_EMAIL` secret = `mss-runner@mss-tts.iam.gserviceaccount.com`
- [ ] Added `GCP_ARTIFACT_REGISTRY` secret = `mss`
- [ ] Created Artifact Registry repository `mss` in `us-central1` (if needed)
- [ ] Triggered GitHub Actions workflow
- [ ] Workflow completed successfully ✅
- [ ] Got service URL from workflow output
- [ ] Tested `/healthz` endpoint - shows version 5.5.7
- [ ] Tested login/signup functionality
- [ ] Stopped/deleted old service in other Google account
- [ ] Removed old GitHub secrets (if any)

---

## Need Help?

If you get stuck at any step, let me know which step number and what error you see!

