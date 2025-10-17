# YouTube API Setup - Quick Start

## Error: "Failed to generate auth URL. Check YouTube credentials."

This means you need to set up YouTube API credentials first.

---

## Option 1: Automated Setup (Easiest)

Run the setup helper script:

```bash
python setup_youtube_credentials.py
```

Follow the prompts. The script will guide you through the entire process.

---

## Option 2: Manual Setup (5 minutes)

### Step 1: Get Credentials from Google Cloud Console

1. **Go to Google Cloud Console:**
   https://console.cloud.google.com/

2. **Create a new project** (or select existing):
   - Click the project dropdown at the top
   - Click "New Project"
   - Name it: "MSS YouTube Integration"
   - Click "Create"

3. **Enable YouTube Data API v3:**
   - In the left menu, go to: **APIs & Services** → **Library**
   - Search for: **YouTube Data API v3**
   - Click on it, then click **Enable**

4. **Create OAuth 2.0 Credentials:**
   - Go to: **APIs & Services** → **Credentials**
   - Click: **+ CREATE CREDENTIALS**
   - Select: **OAuth client ID**

   - **If prompted to configure consent screen:**
     - Click "Configure Consent Screen"
     - User Type: **External**
     - App name: "MSS Studio"
     - User support email: (your email)
     - Developer contact: (your email)
     - Click "Save and Continue"
     - Scopes: Skip (click "Save and Continue")
     - Test users: Add your email
     - Click "Save and Continue" → "Back to Dashboard"

   - **Now create the OAuth client:**
     - Go back to: **Credentials** → **+ CREATE CREDENTIALS** → **OAuth client ID**
     - Application type: **Web application**
     - Name: "MSS YouTube Integration"
     - **Authorized redirect URIs** (click "+ ADD URI" for each):
       - `http://localhost:5000/api/oauth/youtube/callback`
       - `http://127.0.0.1:5000/api/oauth/youtube/callback`
     - Click **Create**

5. **Download the JSON file:**
   - A dialog will appear with your credentials
   - Click **DOWNLOAD JSON**
   - Save the file

### Step 2: Add Credentials to MSS

**Option A: Copy the downloaded file**

```bash
# Copy your downloaded file to:
G:\Users\daveq\mss\web\platform_credentials\youtube_client_secrets.json
```

**Option B: Create the file manually**

1. Create file: `web/platform_credentials/youtube_client_secrets.json`

2. Paste this structure (replace YOUR_CLIENT_ID and YOUR_CLIENT_SECRET):

```json
{
  "web": {
    "client_id": "YOUR_CLIENT_ID.apps.googleusercontent.com",
    "project_id": "your-project-id",
    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
    "token_uri": "https://oauth2.googleapis.com/token",
    "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
    "client_secret": "YOUR_CLIENT_SECRET",
    "redirect_uris": [
      "http://localhost:5000/api/oauth/youtube/callback",
      "http://127.0.0.1:5000/api/oauth/youtube/callback"
    ]
  }
}
```

### Step 3: Restart MSS Server

```bash
# Stop the server (Ctrl+C if running)
# Restart it:
python web/api_server.py
```

You should see:
```
[PLATFORM_API] ✓ PlatformAPIManager loaded successfully
```

### Step 4: Connect Your YouTube Channel

1. Open MSS in your browser: http://localhost:5000
2. Go to: **Analytics** → **Channels** button
3. Click: **+ Add YouTube Channel**
4. Sign in with your Google account
5. Grant permissions to MSS
6. Done! Your channel will appear in the list

---

## Verification

Check if credentials are loaded:

```bash
# The file should exist:
ls -la web/platform_credentials/youtube_client_secrets.json

# Should show the file with ~400-600 bytes
```

Check server logs when starting:
```
[PLATFORM_API] Using database: web/mss_users.db
[PLATFORM_API] Credentials dir: web/platform_credentials
[PLATFORM_API] ✓ PlatformAPIManager loaded successfully
```

---

## Troubleshooting

### Error: "Client secrets file not found"

**Cause:** The `youtube_client_secrets.json` file is missing or in the wrong location.

**Solution:**
```bash
# Check if file exists:
ls web/platform_credentials/youtube_client_secrets.json

# If not, follow Step 2 above to create it
```

### Error: "Invalid JSON"

**Cause:** The credentials file is malformed.

**Solution:**
- Make sure you copied the ENTIRE JSON file
- Use a JSON validator: https://jsonlint.com/
- Check for missing quotes, commas, or brackets

### Error: "Redirect URI mismatch"

**Cause:** The redirect URI in Google Cloud Console doesn't match MSS.

**Solution:**
- Go to: Google Cloud Console → Credentials
- Edit your OAuth client
- Make sure these EXACT URIs are listed:
  - `http://localhost:5000/api/oauth/youtube/callback`
  - `http://127.0.0.1:5000/api/oauth/youtube/callback`

### Error: "Access not configured"

**Cause:** YouTube Data API v3 is not enabled.

**Solution:**
- Go to: Google Cloud Console → APIs & Services → Library
- Search: "YouTube Data API v3"
- Click it, then click "Enable"

---

## Quick Reference

**Credentials File Location:**
```
G:\Users\daveq\mss\web\platform_credentials\youtube_client_secrets.json
```

**Required Structure:**
```json
{
  "web": {
    "client_id": "...",
    "client_secret": "...",
    "redirect_uris": ["http://localhost:5000/api/oauth/youtube/callback"]
  }
}
```

**Google Cloud Console:**
https://console.cloud.google.com/

**After Setup:**
- Restart MSS server
- Go to Channel Manager
- Click "Add YouTube Channel"
- Sign in and grant permissions

---

## Need Help?

Check the full guide: `PLATFORM_API_SETUP_GUIDE.md`

Or run the setup script: `python setup_youtube_credentials.py`
