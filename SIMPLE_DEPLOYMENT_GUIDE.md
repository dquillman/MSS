# 🚀 Simple Step-by-Step: Deploy MSS to Cloud Run

## What We're Doing
Deploy MSS version 5.5.7 to Google Cloud Run in your `mss-tts` project.

---

## ✅ STEP 1: Create Service Account (5 minutes)

### A. Go to Google Cloud Console
1. Open: https://console.cloud.google.com
2. **Sign in as**: `dquillman2112@gmail.com`
3. **Select project** (top dropdown): `mss-tts`

### B. Create Service Account
1. Click **"IAM & Admin"** in left menu
2. Click **"Service Accounts"**
3. Click **"+ CREATE SERVICE ACCOUNT"** (blue button)
4. Fill in:
   - **Service account name**: `mss-runner`
   - Click **"CREATE AND CONTINUE"**

### C. Add Permissions
1. Click **"+ ADD ANOTHER ROLE"**
2. Type and select: **Cloud Run Admin**
3. Click **"+ ADD ANOTHER ROLE"** again
4. Type and select: **Service Account User**
5. Click **"+ ADD ANOTHER ROLE"** again
6. Type and select: **Artifact Registry Writer**
7. Click **"CONTINUE"**
8. Click **"DONE"**

### D. Create Key (IMPORTANT!)
1. You'll see `mss-runner@mss-tts.iam.gserviceaccount.com` in the list
2. **Click on it** (the email address)
3. Go to **"KEYS"** tab (top of page)
4. Click **"ADD KEY"** → **"Create new key"**
5. Select **JSON** radio button
6. Click **"CREATE"**
7. **SAVE THE DOWNLOADED FILE** - you'll need it next!

---

## ✅ STEP 2: Add GitHub Secrets (5 minutes)

### A. Go to GitHub
1. Open: https://github.com/dquillman/MSS
2. Click **"Settings"** tab (very top right of page)
3. In left sidebar, click **"Secrets and variables"**
4. Click **"Actions"**

### B. Add Secret 1: Project ID
1. Click **"New repository secret"**
2. **Name**: Type exactly: `GCP_PROJECT_ID`
3. **Secret**: Type exactly: `mss-tts`
4. Click **"Add secret"**

### C. Add Secret 2: Service Account Key (THE BIG ONE)
1. Click **"New repository secret"**
2. **Name**: Type exactly: `GCP_SA_KEY`
3. **Secret**: 
   - Open the JSON file you downloaded in Step 1
   - **Select ALL** (Ctrl+A) and **Copy** (Ctrl+C)
   - **Paste it here** (should be a long JSON block starting with `{`)
4. Click **"Add secret"**

### D. Add Secret 3: Service Account Email
1. Click **"New repository secret"**
2. **Name**: Type exactly: `GCP_SERVICE_ACCOUNT_EMAIL`
3. **Secret**: Type exactly: `mss-runner@mss-tts.iam.gserviceaccount.com`
4. Click **"Add secret"**

### E. Add Secret 4: Artifact Registry
1. Click **"New repository secret"**
2. **Name**: Type exactly: `GCP_ARTIFACT_REGISTRY`
3. **Secret**: Type exactly: `mss`
4. Click **"Add secret"**

### F. Verify You Have 4 Secrets
You should see these 4 secrets listed:
- ✅ GCP_PROJECT_ID
- ✅ GCP_SA_KEY
- ✅ GCP_SERVICE_ACCOUNT_EMAIL
- ✅ GCP_ARTIFACT_REGISTRY

---

## ✅ STEP 3: Create Artifact Registry (2 minutes)

### A. Go to Artifact Registry
1. In Google Cloud Console, type **"Artifact Registry"** in search bar
2. Click **"Artifact Registry"** result
3. Make sure project is **`mss-tts`** (top dropdown)

### B. Check if Repository Exists
- Look for repository named **`mss`** in location **`us-central1`**
- **If you see it**: ✅ Skip to Step 4
- **If you DON'T see it**: Continue below

### C. Create Repository (if needed)
1. Click **"+ CREATE REPOSITORY"**
2. Fill in:
   - **Repository name**: `mss`
   - **Format**: Select **Docker**
   - **Mode**: Select **Standard**
   - **Location**: Select **us-central1**
3. Click **"CREATE"**

---

## ✅ STEP 4: Deploy! (10 minutes)

### A. Go to GitHub Actions
1. Open: https://github.com/dquillman/MSS/actions
2. In left sidebar, click **"Build and Deploy to Google Cloud Run"**

### B. Run Workflow
1. Click **"Run workflow"** button (top right, purple button)
2. **Branch** dropdown: Select **`master`**
3. Click green **"Run workflow"** button

### C. Watch It Work
1. You'll see a new workflow run appear (yellow circle = running)
2. **Click on it** to see progress
3. You'll see steps like:
   - ✅ Checkout code
   - ✅ Set up Python
   - ✅ Authenticate to Google Cloud
   - ✅ Build Docker image (this takes 3-5 minutes)
   - ✅ Push Docker image
   - ✅ Deploy to Cloud Run
   - ✅ Get service URL
   - ✅ Health check

### D. Wait for Success
- **Green checkmark** ✅ = Success! (5-10 minutes)
- **Red X** ❌ = Error (click to see what went wrong)

---

## ✅ STEP 5: Get Your URL

### A. Find Service URL
1. In the completed workflow, scroll down
2. Look for step: **"Get service URL"**
3. You'll see: `Service deployed at: https://mss-api-XXXXX-uc.a.run.app`
4. **Copy that URL!**

### B. Test It
1. Open the URL in browser
2. Add `/healthz` to end: `https://YOUR-URL/healthz`
3. You should see:
   ```json
   {
     "status": "ok",
     "service": "MSS API",
     "version": "5.5.7"
   }
   ```

### C. Test Login
1. Go to: `https://YOUR-URL/auth`
2. Try creating an account
3. Try logging in

---

## ✅ STEP 6: Clean Up Old Service (Optional)

If you want to remove the old service from the other Google account:

### A. Find Old Service
1. Sign in to Google Cloud Console with the **OTHER** Google account
2. Look for Cloud Run services (might be called `iatlas-app` or similar)

### B. Delete or Stop It
**Option 1: Stop Traffic (Safe)**
```bash
gcloud run services update-traffic OLD_SERVICE_NAME \
  --to-latest 0 \
  --region us-central1
```

**Option 2: Delete (Permanent)**
```bash
gcloud run services delete OLD_SERVICE_NAME \
  --region us-central1 \
  --quiet
```

---

## ❌ Troubleshooting

### "Workflow failed at Authenticate to Google Cloud"
- **Fix**: Check `GCP_SA_KEY` secret - make sure you copied the ENTIRE JSON file

### "Workflow failed at Deploy to Cloud Run"
- **Fix**: Make sure service account has "Cloud Run Admin" role

### "Can't find project mss-tts"
- **Fix**: Make sure you're signed in as `dquillman2112@gmail.com` in Google Cloud Console

### "Artifact Registry not found"
- **Fix**: Make sure you created the `mss` repository in `us-central1` location

---

## 📋 Quick Checklist

Copy this and check off as you go:

- [ ] Created service account `mss-runner` in `mss-tts` project
- [ ] Added role: Cloud Run Admin
- [ ] Added role: Service Account User
- [ ] Added role: Artifact Registry Writer
- [ ] Created and downloaded JSON key
- [ ] Added GitHub secret: `GCP_PROJECT_ID` = `mss-tts`
- [ ] Added GitHub secret: `GCP_SA_KEY` = (full JSON content)
- [ ] Added GitHub secret: `GCP_SERVICE_ACCOUNT_EMAIL` = `mss-runner@mss-tts.iam.gserviceaccount.com`
- [ ] Added GitHub secret: `GCP_ARTIFACT_REGISTRY` = `mss`
- [ ] Created Artifact Registry repository `mss` in `us-central1`
- [ ] Triggered GitHub Actions workflow
- [ ] Workflow completed successfully ✅
- [ ] Got service URL from workflow
- [ ] Tested `/healthz` - shows version 5.5.7
- [ ] Tested login/signup
- [ ] Cleaned up old service (optional)

---

## 🆘 Need Help?

If stuck, tell me:
1. Which step number?
2. What error message you see?
3. What you were trying to do?

I'll help you fix it!






