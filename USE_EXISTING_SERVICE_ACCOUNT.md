# Using Existing Service Account for Deployment

## Your Current Service Accounts

You already have these service accounts in `mss-tts`:
1. `306798653079-compute@developer.gserviceaccount.com` (Default compute)
2. `mss-drive@mss-tts.iam.gserviceaccount.com` (Drive uploads)
3. `mss-tts@mss-tts.iam.gserviceaccount.com` (General MSS service)

## Option 1: Use Existing `mss-tts` Account (Recommended if it has permissions)

### Check Permissions
1. In Google Cloud Console, click on `mss-tts@mss-tts.iam.gserviceaccount.com`
2. Go to **"PERMISSIONS"** tab
3. Check if it has these roles:
   - ✅ **Cloud Run Admin**
   - ✅ **Service Account User**
   - ✅ **Artifact Registry Writer**

### If It Has All Permissions:
**Use this service account instead of creating a new one!**

**Update GitHub Secrets:**
- `GCP_SERVICE_ACCOUNT_EMAIL` = `mss-tts@mss-tts.iam.gserviceaccount.com`

### If It's Missing Permissions:
1. Click on `mss-tts@mss-tts.iam.gserviceaccount.com`
2. Click **"PERMISSIONS"** tab
3. Click **"GRANT ACCESS"**
4. Add missing roles:
   - Cloud Run Admin
   - Service Account User
   - Artifact Registry Writer
5. Click **"SAVE"**

### Create/Download Key (if needed)
1. Go to **"KEYS"** tab
2. Click **"ADD KEY"** → **"Create new key"**
3. Select **JSON**
4. Download and save the JSON file
5. Use this JSON for `GCP_SA_KEY` secret

---

## Option 2: Create New `mss-runner` Account (As in original guide)

Follow `SIMPLE_DEPLOYMENT_GUIDE.md` Step 1 as written.

**Advantages:**
- Separate permissions for deployment only
- Better security isolation
- Follows best practices

---

## Recommendation

**Use Option 1** (existing `mss-tts` account) if:
- It already has the required permissions
- You want to keep it simple
- It makes sense for your setup

**Use Option 2** (create `mss-runner`) if:
- The existing account is missing permissions
- You want separate accounts for different purposes
- You prefer security isolation

---

## Quick Decision Tree

1. **Check `mss-tts@mss-tts.iam.gserviceaccount.com` permissions**
2. **If it has all 3 roles** → Use it! (Skip creating new account)
3. **If it's missing roles** → Add missing roles OR create `mss-runner`
4. **Make sure it has a JSON key** (download if needed)
5. **Use the email and key for GitHub secrets**

---

## Updated GitHub Secrets (if using existing account)

- `GCP_PROJECT_ID` = `mss-tts`
- `GCP_SA_KEY` = (JSON key from `mss-tts@mss-tts.iam.gserviceaccount.com`)
- `GCP_SERVICE_ACCOUNT_EMAIL` = `mss-tts@mss-tts.iam.gserviceaccount.com`
- `GCP_ARTIFACT_REGISTRY` = `mss`






