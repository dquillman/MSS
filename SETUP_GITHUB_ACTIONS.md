# Setup GitHub Actions for MSS - Step by Step Guide

## Quick Setup (5 minutes)

Follow these steps to enable GitHub Actions deployments.

---

## Step 1: Create GitHub Actions Service Account

Open PowerShell and run these commands:

```powershell
# Make sure you're in the MSS directory
cd G:\Users\daveq\MSS

# Set the correct project
gcloud config set project mss-tts

# Create the service account
gcloud iam service-accounts create github-actions-deployer `
  --display-name="GitHub Actions Deployer" `
  --project=mss-tts

# Grant necessary permissions
$SA_EMAIL = "github-actions-deployer@mss-tts.iam.gserviceaccount.com"

gcloud projects add-iam-policy-binding mss-tts `
  --member="serviceAccount:$SA_EMAIL" `
  --role="roles/run.admin"

gcloud projects add-iam-policy-binding mss-tts `
  --member="serviceAccount:$SA_EMAIL" `
  --role="roles/artifactregistry.writer"

gcloud projects add-iam-policy-binding mss-tts `
  --member="serviceAccount:$SA_EMAIL" `
  --role="roles/iam.serviceAccountUser"

# Create the key file
gcloud iam service-accounts keys create github-actions-key.json `
  --iam-account=$SA_EMAIL

# Display the key (you'll need to copy this)
Write-Host "`n✅ Service account created!" -ForegroundColor Green
Write-Host "Service Account Email: $SA_EMAIL" -ForegroundColor Cyan
Write-Host "Key file: github-actions-key.json" -ForegroundColor Yellow
```

---

## Step 2: Get the Service Account Key

After running Step 1, you'll have a file called `github-actions-key.json`. 

**Display the contents:**
```powershell
Get-Content github-actions-key.json
```

**Copy the entire JSON content** - you'll need it for GitHub Secrets.

---

## Step 3: Add GitHub Secrets

1. **Go to GitHub Secrets:**
   - Open: https://github.com/dquillman/MSS/settings/secrets/actions
   - Or: GitHub → Your Repo → Settings → Secrets and variables → Actions

2. **Add these secrets one by one:**

   **Secret 1: GCP_PROJECT_ID**
   - Name: `GCP_PROJECT_ID`
   - Value: `mss-tts`
   - Click "Add secret"

   **Secret 2: GCP_SA_KEY**
   - Name: `GCP_SA_KEY`
   - Value: (paste the entire contents of `github-actions-key.json`)
   - This is the full JSON file content
   - Click "Add secret"

   **Secret 3: GCP_SERVICE_ACCOUNT_EMAIL**
   - Name: `GCP_SERVICE_ACCOUNT_EMAIL`
   - Value: `github-actions-deployer@mss-tts.iam.gserviceaccount.com`
   - Click "Add secret"

   **Secret 4: GCP_ARTIFACT_REGISTRY** (Optional)
   - Name: `GCP_ARTIFACT_REGISTRY`
   - Value: `mss`
   - Click "Add secret" (or skip, it defaults to 'mss')

   **Secret 5: DATABASE_URL** (Optional - already in Cloud Run)
   - Name: `DATABASE_URL`
   - Value: `postgresql://postgres:0a26q1KtcmufVopA4YOb@/mss?host=/cloudsql/mss-tts:us-central1:mss-postgres`
   - Click "Add secret" (optional, already configured in Cloud Run)

---

## Step 4: Test the Deployment

After adding all secrets:

1. **Trigger a deployment:**
   - Go to: https://github.com/dquillman/MSS/actions
   - Click "Run workflow" → "Run workflow" (on main branch)
   - Or: Make a small commit and push

2. **Monitor the deployment:**
   - Watch the workflow run
   - Check for any errors
   - Should complete successfully

3. **Verify deployment:**
   ```powershell
   # Check the service URL
   gcloud run services describe mss-api --region=us-central1 --format="value(status.url)"
   
   # Test health endpoint
   $url = gcloud run services describe mss-api --region=us-central1 --format="value(status.url)"
   Invoke-RestMethod -Uri "$url/health"
   ```

---

## Step 5: Clean Up (Security)

After adding the key to GitHub Secrets, **delete the local key file**:

```powershell
# Delete the key file (it's now in GitHub Secrets)
Remove-Item github-actions-key.json

# Verify it's deleted
Test-Path github-actions-key.json  # Should return False
```

**Important:** Never commit `github-actions-key.json` to git!

---

## Troubleshooting

### "Service account already exists"
If you get this error, the service account might already exist. Check:
```powershell
gcloud iam service-accounts list --filter="email:github-actions-deployer"
```

If it exists, you can:
- Use the existing one, OR
- Delete and recreate: `gcloud iam service-accounts delete github-actions-deployer@mss-tts.iam.gserviceaccount.com`

### "Permission denied" errors
Make sure you're authenticated:
```powershell
gcloud auth login
gcloud auth list  # Verify you're logged in
```

### GitHub Actions fails
1. Check the workflow logs: https://github.com/dquillman/MSS/actions
2. Verify all secrets are set correctly
3. Check that service account has proper permissions

---

## Verification Checklist

After setup, verify:

- [ ] Service account created: `github-actions-deployer@mss-tts.iam.gserviceaccount.com`
- [ ] Service account has these roles:
  - [ ] `roles/run.admin`
  - [ ] `roles/artifactregistry.writer`
  - [ ] `roles/iam.serviceAccountUser`
- [ ] GitHub Secrets added:
  - [ ] `GCP_PROJECT_ID`
  - [ ] `GCP_SA_KEY`
  - [ ] `GCP_SERVICE_ACCOUNT_EMAIL`
  - [ ] `GCP_ARTIFACT_REGISTRY` (optional)
- [ ] Key file deleted from local machine
- [ ] GitHub Actions workflow runs successfully

---

**That's it!** Once these steps are complete, GitHub Actions will automatically deploy your code to Cloud Run whenever you push to the main branch.

