# 🚀 Quick Start: Using Existing Service Account

## ✅ What We're Using

**Service Account:** `mss-tts@mss-tts.iam.gserviceaccount.com`
- ✅ Has Cloud Run Admin
- ✅ Has Service Account User
- ✅ Has Artifact Registry Writer

**No need to create a new account!**

---

## Step 1: Get JSON Key (2 minutes)

### A. Get the Key
1. In Google Cloud Console, go to **Service Accounts**
2. Click on: `mss-tts@mss-tts.iam.gserviceaccount.com`
3. Go to **"KEYS"** tab
4. **If you see a key listed:**
   - Click the **three dots** (⋮) next to it
   - Click **"Manage keys"** or download it
   - OR create a new one (safer for deployment)

5. **If you see "No keys":**
   - Click **"ADD KEY"** → **"Create new key"**
   - Select **JSON**
   - Click **"CREATE"**
   - **SAVE THE DOWNLOADED FILE**

---

## Step 2: Add GitHub Secrets (3 minutes)

### A. Go to GitHub
1. Open: https://github.com/dquillman/MSS
2. Click **"Settings"** (top right)
3. Click **"Secrets and variables"** → **"Actions"**

### B. Add/Update These 4 Secrets

#### Secret 1: GCP_PROJECT_ID
- **Name**: `GCP_PROJECT_ID`
- **Value**: `mss-tts`
- Click **"Add secret"** or **"Update secret"**

#### Secret 2: GCP_SA_KEY (THE IMPORTANT ONE!)
- **Name**: `GCP_SA_KEY`
- **Value**: Open the JSON file you downloaded
  - **Select ALL** (Ctrl+A) and **Copy** (Ctrl+C)
  - **Paste the entire JSON** here (should start with `{` and end with `}`)
- Click **"Add secret"** or **"Update secret"**

#### Secret 3: GCP_SERVICE_ACCOUNT_EMAIL
- **Name**: `GCP_SERVICE_ACCOUNT_EMAIL`
- **Value**: `mss-tts@mss-tts.iam.gserviceaccount.com`
- Click **"Add secret"** or **"Update secret"**

#### Secret 4: GCP_ARTIFACT_REGISTRY
- **Name**: `GCP_ARTIFACT_REGISTRY`
- **Value**: `mss`
- Click **"Add secret"** or **"Update secret"**

---

## Step 3: Create Artifact Registry (if needed)

1. Go to: **Artifact Registry** in Google Cloud Console
2. Make sure project is **`mss-tts`**
3. Look for repository named **`mss`** in **`us-central1`**
4. **If you see it:** ✅ Skip to Step 4
5. **If not:** 
   - Click **"+ CREATE REPOSITORY"**
   - Name: `mss`
   - Format: **Docker**
   - Mode: **Standard**
   - Location: **us-central1**
   - Click **"CREATE"**

---

## Step 4: Deploy! (10 minutes)

### A. Go to GitHub Actions
1. Open: https://github.com/dquillman/MSS/actions
2. Click **"Build and Deploy to Google Cloud Run"** (left sidebar)

### B. Run Workflow
1. Click **"Run workflow"** (top right, purple button)
2. **Branch**: Select **`master`**
3. Click green **"Run workflow"** button

### C. Watch Progress
- Yellow circle = Running (5-10 minutes)
- Green checkmark ✅ = Success!
- Red X ❌ = Error (click to see details)

### D. Get Your URL
1. When workflow completes, scroll to **"Get service URL"** step
2. You'll see: `Service deployed at: https://mss-api-XXXXX-uc.a.run.app`
3. **Copy that URL!**

### E. Test It
1. Open: `https://YOUR-URL/healthz`
2. Should see:
   ```json
   {
     "status": "ok",
     "service": "MSS API",
     "version": "5.5.7"
   }
   ```

---

## ✅ Checklist

- [ ] Got JSON key from `mss-tts@mss-tts.iam.gserviceaccount.com`
- [ ] Added GitHub secret: `GCP_PROJECT_ID` = `mss-tts`
- [ ] Added GitHub secret: `GCP_SA_KEY` = (full JSON content)
- [ ] Added GitHub secret: `GCP_SERVICE_ACCOUNT_EMAIL` = `mss-tts@mss-tts.iam.gserviceaccount.com`
- [ ] Added GitHub secret: `GCP_ARTIFACT_REGISTRY` = `mss`
- [ ] Created Artifact Registry `mss` repository (if needed)
- [ ] Triggered GitHub Actions workflow
- [ ] Workflow completed successfully ✅
- [ ] Got service URL
- [ ] Tested `/healthz` endpoint - shows version 5.5.7

---

## 🆘 Troubleshooting

### "Workflow failed at Authenticate to Google Cloud"
- Check `GCP_SA_KEY` - make sure you copied the ENTIRE JSON file (starts with `{`)

### "Workflow failed at Deploy to Cloud Run"
- Verify service account has "Cloud Run Admin" role ✅ (already confirmed)

### "Artifact Registry not found"
- Make sure repository `mss` exists in `us-central1` location

---

## 🎯 You're Ready!

Follow Steps 1-4 above, and you'll have MSS deployed in about 15 minutes!






