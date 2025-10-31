# 🔧 Troubleshoot Deployment Failure

## Step 1: Check What Failed

### In GitHub Actions:
1. Go to: https://github.com/dquillman/MSS/actions
2. Click on your **most recent workflow run** (the one with red X)
3. Look for **red X** - which step failed?
4. **Click on the failed step** to see error details

### Common Failure Points:

#### 1. "Authenticate to Google Cloud" Failed
**Error looks like:** "Authentication failed" or "Invalid credentials"

**Fix:**
- Check `GCP_SA_KEY` secret in GitHub
- Make sure JSON is complete (starts with `{` and ends with `}`)
- Verify you copied the entire JSON file content

#### 2. "Build Docker image" Failed
**Error looks like:** "Docker build failed" or "Error building image"

**Fix:**
- Check Dockerfile.app exists
- Verify all files are in repository
- Look at build logs for specific error

#### 3. "Push Docker image" Failed
**Error looks like:** "Artifact Registry not found" or "Permission denied"

**Fix:**
- Verify Artifact Registry `mss` exists in `us-central1`
- Check `GCP_ARTIFACT_REGISTRY` secret = `mss`
- Verify service account has "Artifact Registry Writer" role

#### 4. "Deploy to Cloud Run" Failed
**Error looks like:** "Permission denied" or "Service account not found"

**Fix:**
- Check `GCP_SERVICE_ACCOUNT_EMAIL` = `mss-tts@mss-tts.iam.gserviceaccount.com`
- Verify service account has "Cloud Run Admin" role
- Check `GCP_PROJECT_ID` = `mss-tts`

#### 5. "Health check" Failed
**Error looks like:** "Health check failed" or "Endpoint not responding"

**Fix:**
- Check if service actually deployed (might still be running)
- Verify `/healthz` endpoint exists
- Check Cloud Run logs in Google Cloud Console

---

## Step 2: Get Error Details

### Copy the Error:
1. Click on the **failed step** (red X)
2. Scroll down to see error output
3. **Copy the error message** (or screenshot it)
4. Tell me what it says

### Common Errors:

**"Error: Could not find artifact repository"**
- Artifact Registry `mss` doesn't exist
- Create it: Go to Artifact Registry → Create repository `mss` in `us-central1`

**"Error: Service account not found"**
- Wrong email in secret
- Check `GCP_SERVICE_ACCOUNT_EMAIL` = `mss-tts@mss-tts.iam.gserviceaccount.com`

**"Error: Authentication failed"**
- JSON key is incomplete or invalid
- Re-download key from Service Accounts → KEYS tab

**"Error: Permission denied"**
- Service account missing roles
- Add: Cloud Run Admin, Service Account User, Artifact Registry Writer

---

## Step 3: Quick Fixes

### Fix 1: Verify All Secrets
Go to: https://github.com/dquillman/MSS/settings/secrets/actions

Check these exist:
- ✅ `GCP_PROJECT_ID` = `mss-tts`
- ✅ `GCP_SA_KEY` = (full JSON content)
- ✅ `GCP_SERVICE_ACCOUNT_EMAIL` = `mss-tts@mss-tts.iam.gserviceaccount.com`
- ✅ `GCP_ARTIFACT_REGISTRY` = `mss`

### Fix 2: Verify Artifact Registry
1. Go to: https://console.cloud.google.com/artifacts
2. Select project: `mss-tts`
3. Check if repository `mss` exists in `us-central1`
4. If not, create it:
   - Click "CREATE REPOSITORY"
   - Name: `mss`
   - Format: Docker
   - Location: `us-central1`

### Fix 3: Verify Service Account Permissions
1. Go to: Service Accounts in Google Cloud Console
2. Click: `mss-tts@mss-tts.iam.gserviceaccount.com`
3. Go to: PERMISSIONS tab
4. Verify these roles exist:
   - Cloud Run Admin
   - Service Account User
   - Artifact Registry Writer

---

## Step 4: Retry Deployment

After fixing the issue:

1. Go back to: https://github.com/dquillman/MSS/actions
2. Click: "Build and Deploy to Google Cloud Run"
3. Click: "Run workflow"
4. Select: `master`
5. Click: "Run workflow" again

---

## Tell Me:

**What error did you see?**
1. Which step failed? (Click on red X and tell me the step name)
2. What's the error message? (Copy/paste it or describe it)
3. Did you check the secrets? (All 4 exist?)

I'll help you fix it and retry! 🔧

