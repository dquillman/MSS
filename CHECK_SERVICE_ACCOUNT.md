# Check Existing Service Account Permissions

## Quick Decision

You have `mss-tts@mss-tts.iam.gserviceaccount.com` - let's check if we can use it!

---

## Step 1: Check Permissions (2 minutes)

1. **In Google Cloud Console** (you're already there)
2. **Click on**: `mss-tts@mss-tts.iam.gserviceaccount.com` (the email address)
3. **Go to**: **PERMISSIONS** tab (at the top)
4. **Look for these roles**:
   - ✅ **Cloud Run Admin** (or "Cloud Run Admin")
   - ✅ **Service Account User** (or "Service Account User")
   - ✅ **Artifact Registry Writer** (or "Artifact Registry Writer")

---

## Step 2: Choose Your Path

### Path A: If `mss-tts` Account Has All 3 Roles ✅

**Use it! Skip creating a new account.**

1. **Check if it has a JSON key:**
   - Go to **"KEYS"** tab
   - If you see a key listed → You can use it
   - If you see "No keys" → Create a new key:
     - Click **"ADD KEY"** → **"Create new key"**
     - Select **JSON**
     - Download and save it

2. **Use these values for GitHub secrets:**
   - `GCP_SERVICE_ACCOUNT_EMAIL` = `mss-tts@mss-tts.iam.gserviceaccount.com`
   - `GCP_SA_KEY` = (the JSON key you downloaded)

3. **Skip Step 1 in the deployment guide** and go straight to Step 2 (Add GitHub Secrets)

---

### Path B: If `mss-tts` Account is Missing Roles ❌

**Option 1: Add Missing Roles** (Quick)
1. Still on the **"PERMISSIONS"** tab
2. Click **"GRANT ACCESS"** button
3. Add the missing roles:
   - Cloud Run Admin
   - Service Account User
   - Artifact Registry Writer
4. Click **"SAVE"**
5. Then follow **Path A** above

**Option 2: Create New `mss-runner` Account** (Clean separation)
1. Follow `SIMPLE_DEPLOYMENT_GUIDE.md` Step 1 as written
2. Creates a dedicated deployment account

---

## Step 3: Check for JSON Key

Even if permissions are good, you need a JSON key:

1. **In the service account page**, go to **"KEYS"** tab
2. **If you see a key** (like `b2177ce` for mss-tts):
   - Click the **three dots** (⋮) next to it
   - Click **"Download"** or **"Manage keys"**
   - Or just create a new one (safer)

3. **If you see "No keys"**:
   - Click **"ADD KEY"** → **"Create new key"**
   - Select **JSON**
   - Click **"CREATE"**
   - Download and save the JSON file

---

## My Recommendation

**Check `mss-tts@mss-tts.iam.gserviceaccount.com` first:**

1. If it has **Cloud Run Admin** → Use it!
2. If not → Add that role, then use it

This is simpler than creating a new account.

---

## What to Tell Me

After checking, tell me:
- ✅ "mss-tts account has Cloud Run Admin" → Use it
- ❌ "mss-tts account missing permissions" → I'll help add them or create new account






