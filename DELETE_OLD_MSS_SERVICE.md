# Delete Old MSS YouTube Integration Service

## ⚠️ What We're Deleting
The old MSS service in the **Dave Quillman** Google account (MSS YouTube Integration project)

## ✅ What We're Keeping
The MSS-STT project (`mss-tts`) in your main account (`dquillman2112@gmail.com`)

---

## Step 1: Identify the Old Service

### A. Sign in to the Other Google Account
1. Go to: https://console.cloud.google.com
2. **Sign in as**: The Dave Quillman account (the one that has "MSS YouTube Integration")
3. Check the top right - you should see a different email address

### B. Find Cloud Run Services
1. In search bar, type: **"Cloud Run"**
2. Click **"Cloud Run"** result
3. Look at the list of services

### C. Identify Which Service to Delete
Look for services like:
- `mss-api` (if it exists in this account)
- `iatlas-app` (the old service we saw earlier)
- Any service with "MSS" in the name

**Note down the service name** - you'll need it!

---

## Step 2: Delete the Service

### Option A: Using Google Cloud Console (Easiest)

1. **Go to Cloud Run**
   - https://console.cloud.google.com/run
   - Make sure you're in the **Dave Quillman** account's project

2. **Find the Service**
   - Click on the service name (e.g., `mss-api` or `iatlas-app`)

3. **Delete It**
   - Click **"DELETE"** button (top of page)
   - Type the service name to confirm
   - Click **"DELETE"** again

### Option B: Using Command Line (Advanced)

```bash
# First, switch to the other Google account
gcloud auth login OTHER_ACCOUNT_EMAIL

# Set the project
gcloud config set project OTHER_PROJECT_ID

# List services to find the one to delete
gcloud run services list --region us-central1

# Delete the service
gcloud run services delete SERVICE_NAME --region us-central1 --quiet
```

**Replace:**
- `OTHER_ACCOUNT_EMAIL` = The Dave Quillman account email
- `OTHER_PROJECT_ID` = The project ID for "MSS YouTube Integration"
- `SERVICE_NAME` = The service name you found (e.g., `mss-api`)

---

## Step 3: Optional Cleanup

### Delete Artifact Registry Images (Optional)
If you want to clean up Docker images too:

1. Go to: **Artifact Registry** in Google Cloud Console
2. Find the repository (might be called `mss` or similar)
3. Select images you don't need
4. Click **"DELETE"**

### Delete the Entire Project (Optional - More Aggressive)
If you want to delete the whole "MSS YouTube Integration" project:

1. Go to: https://console.cloud.google.com/iam-admin/settings
2. Select the project: **"MSS YouTube Integration"**
3. Click **"SHUT DOWN"** button
4. Type project ID to confirm
5. Click **"SHUT DOWN"**

⚠️ **Warning**: This deletes EVERYTHING in that project permanently!

---

## Step 4: Verify Deletion

### Check Services List
1. Go to: **Cloud Run** → **Services**
2. The old service should be gone

### Verify Your Main Service Still Works
1. Sign back in as: `dquillman2112@gmail.com`
2. Go to project: `mss-tts`
3. Check Cloud Run - your main MSS service should still be there (once deployed)

---

## Quick Commands Reference

### List All Services (to find what to delete)
```bash
gcloud run services list --region us-central1
```

### Delete Specific Service
```bash
gcloud run services delete SERVICE_NAME --region us-central1 --quiet
```

### Switch Google Accounts
```bash
gcloud auth login OTHER_ACCOUNT_EMAIL
```

### Switch Projects
```bash
gcloud config set project PROJECT_ID
```

---

## ✅ Checklist

- [ ] Signed in to Dave Quillman Google account
- [ ] Identified old MSS service name
- [ ] Deleted the service from Cloud Run
- [ ] (Optional) Deleted Artifact Registry images
- [ ] (Optional) Deleted entire project
- [ ] Verified deletion completed
- [ ] Signed back in to main account (`dquillman2112@gmail.com`)
- [ ] Verified main project (`mss-tts`) still exists

---

## ⚠️ Important Notes

1. **Backup First?** 
   - If the old service has data you need, export it before deleting
   - Check databases, files, etc.

2. **Double Check**
   - Make sure you're in the **Dave Quillman** account, NOT your main account
   - Don't delete `mss-tts` project accidentally!

3. **No Going Back**
   - Once deleted, services can't be recovered (unless you have backups)
   - Be certain before deleting!

---

## Need Help?

If you're not sure which service to delete, tell me:
- What services you see in Cloud Run
- What project names you see
- I'll help identify which one is the old one






