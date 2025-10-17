# Platform API Setup Guide

This guide shows you how to set up OAuth credentials for YouTube, TikTok, and Instagram so you can publish videos directly from MSS.

---

## Prerequisites

1. **Install Required Python Packages:**

```bash
pip install google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client
```

2. **Create credentials directory:**

The platform API manager will auto-create `web/platform_credentials/` directory.

---

## YouTube Data API v3 Setup

### Step 1: Create Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (e.g., "MSS YouTube Publisher")
3. Enable **YouTube Data API v3**:
   - Go to "APIs & Services" → "Enable APIs and Services"
   - Search for "YouTube Data API v3"
   - Click "Enable"

### Step 2: Create OAuth 2.0 Credentials

1. Go to "APIs & Services" → "Credentials"
2. Click "Create Credentials" → "OAuth client ID"
3. If prompted, configure OAuth consent screen:
   - User Type: **External**
   - App name: "MSS Studio"
   - User support email: Your email
   - Scopes: Add `youtube.upload`, `youtube`, `youtube.force-ssl`
   - Test users: Add your email
4. Application type: **Web application**
5. Name: "MSS YouTube OAuth"
6. Authorized redirect URIs:
   - `http://localhost:5000/api/oauth/youtube/callback`
   - `http://127.0.0.1:5000/api/oauth/youtube/callback`
   - Add your production URLs if deployed
7. Click "Create"
8. Download the JSON file

### Step 3: Save Credentials

1. Rename the downloaded file to `youtube_client_secrets.json`
2. Move it to `web/platform_credentials/youtube_client_secrets.json`

The file should look like:
```json
{
  "web": {
    "client_id": "YOUR_CLIENT_ID.apps.googleusercontent.com",
    "project_id": "your-project-id",
    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
    "token_uri": "https://oauth2.googleapis.com/token",
    "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
    "client_secret": "YOUR_CLIENT_SECRET",
    "redirect_uris": ["http://localhost:5000/api/oauth/youtube/callback"]
  }
}
```

### Step 4: Test Connection

1. Start MSS server: `python web/api_server.py`
2. Go to Multi-Platform Publisher
3. Click "Connect YouTube"
4. Authorize the app
5. You should see "YouTube Connected Successfully!"

---

## TikTok API Setup

### Step 1: Register TikTok Developer Account

1. Go to [TikTok for Developers](https://developers.tiktok.com/)
2. Sign up / Log in
3. Create a new app:
   - App name: "MSS Studio"
   - Description: "Video publishing automation"

### Step 2: Get API Credentials

1. Go to your app dashboard
2. Copy the **Client Key** and **Client Secret**
3. Add redirect URI:
   - `http://localhost:5000/api/oauth/tiktok/callback`
   - `http://127.0.0.1:5000/api/oauth/tiktok/callback`

### Step 3: Save Credentials

Create `web/platform_credentials/tiktok_config.json`:

```json
{
  "client_key": "YOUR_CLIENT_KEY",
  "client_secret": "YOUR_CLIENT_SECRET"
}
```

### Step 4: Request API Access

TikTok requires manual approval for video upload API access:

1. Go to your TikTok Developer Dashboard
2. Navigate to "Manage Apps" → Your App → "Products"
3. Request access to "Content Posting API"
4. Fill out the use case form
5. Wait for approval (can take 1-2 weeks)

**Note:** Until approved, TikTok publishing will fail with authorization errors.

---

## Instagram Graph API Setup

### Step 1: Create Facebook App

1. Go to [Facebook for Developers](https://developers.facebook.com/)
2. Create new app:
   - Type: **Business**
   - Name: "MSS Studio"
3. Add **Instagram** product to your app

### Step 2: Configure Instagram Basic Display

1. In app dashboard, go to "Instagram" → "Basic Display"
2. Create New App
3. Configure:
   - Valid OAuth Redirect URIs:
     - `http://localhost:5000/api/oauth/instagram/callback`
     - `http://127.0.0.1:5000/api/oauth/instagram/callback`
   - Deauthorize Callback URL: `http://localhost:5000/api/oauth/deauth`
   - Data Deletion Request URL: `http://localhost:5000/api/oauth/delete`

### Step 3: Add Instagram Test Users

1. Go to "Instagram" → "Basic Display" → "Roles"
2. Add Instagram Testers
3. Instagram users must accept invitation

### Step 4: Get App Credentials

1. Go to "Settings" → "Basic"
2. Copy **App ID** and **App Secret**

### Step 5: Save Credentials

Create `web/platform_credentials/instagram_config.json`:

```json
{
  "app_id": "YOUR_APP_ID",
  "app_secret": "YOUR_APP_SECRET"
}
```

### Step 6: Submit for App Review (Optional)

For production use, submit your app for review to access:
- `instagram_content_publish`
- `pages_show_list`
- `instagram_basic`

Until approved, only test users can connect.

---

## Security Best Practices

### 1. Secure Credentials

```bash
# Add to .gitignore
web/platform_credentials/*.json
web/platform_credentials/*.key
```

### 2. Environment Variables (Production)

Instead of JSON files, use environment variables:

```python
# In platform_apis.py
import os

youtube_client_id = os.environ.get('YOUTUBE_CLIENT_ID')
youtube_client_secret = os.environ.get('YOUTUBE_CLIENT_SECRET')
```

### 3. Token Encryption

For production, encrypt stored tokens:

```python
from cryptography.fernet import Fernet

# Generate key once
key = Fernet.generate_key()

# Encrypt token before storing
fernet = Fernet(key)
encrypted_token = fernet.encrypt(token.encode())

# Decrypt when retrieving
decrypted_token = fernet.decrypt(encrypted_token).decode()
```

### 4. Token Refresh

OAuth tokens expire. Implement automatic refresh:

```python
# Check if token expired
if datetime.now() >= token_expiry:
    # Refresh token
    new_token = refresh_oauth_token(refresh_token)
    # Update in database
```

---

## Testing Your Setup

### Quick Test Script

Create `test_platforms.py`:

```python
from web.platform_apis import PlatformAPIManager

api = PlatformAPIManager()

# Test OAuth URL generation
youtube_url = api.get_youtube_auth_url('test@example.com', 'http://localhost:5000/callback')
print(f"YouTube Auth URL: {youtube_url}")

tiktok_url = api.get_tiktok_auth_url('test@example.com', 'http://localhost:5000/callback')
print(f"TikTok Auth URL: {tiktok_url}")

instagram_url = api.get_instagram_auth_url('test@example.com', 'http://localhost:5000/callback')
print(f"Instagram Auth URL: {instagram_url}")
```

Run:
```bash
python test_platforms.py
```

If URLs are generated successfully, your credentials are configured correctly!

---

## Troubleshooting

### YouTube Errors

**Error:** "The request is missing a required parameter: redirect_uri"
**Fix:** Ensure redirect URI in Google Cloud Console matches exactly (including http/https, localhost/127.0.0.1)

**Error:** "Access Not Configured"
**Fix:** Enable YouTube Data API v3 in Google Cloud Console

**Error:** "invalid_grant"
**Fix:** Token expired or revoked. Re-authorize the app.

### TikTok Errors

**Error:** "insufficient_permissions"
**Fix:** Request Content Posting API access from TikTok (requires manual approval)

**Error:** "invalid_client"
**Fix:** Check client_key and client_secret in tiktok_config.json

### Instagram Errors

**Error:** "Invalid OAuth access token"
**Fix:** Token expired. Implement refresh token logic.

**Error:** "Permissions error"
**Fix:** App not approved for `instagram_content_publish` permission. Use test users or submit for review.

### General Errors

**Error:** "Platform API not available"
**Fix:**
1. Check Flask console for import errors
2. Ensure `web/platform_apis.py` exists
3. Install required packages
4. Restart Flask server

**Error:** "Credentials file not found"
**Fix:**
1. Check file exists in `web/platform_credentials/`
2. Verify filename matches exactly
3. Check file is valid JSON

---

## API Rate Limits

### YouTube
- **Quota:** 10,000 units/day (default)
- **Upload cost:** 1600 units per video
- **Limit:** ~6 videos/day
- **Increase:** Request quota increase in Google Cloud Console

### TikTok
- **Limit:** Varies by app approval status
- **Typical:** 50-100 uploads/day
- **Rate limit:** 1 request/second

### Instagram
- **Limit:** 25 API calls/hour per user
- **Videos:** No strict limit, but rate limited
- **Best practice:** Space out uploads by 30+ minutes

---

## Next Steps

1. ✅ Set up credentials for each platform
2. ✅ Test OAuth flow
3. ✅ Upload a test video
4. 📊 Monitor analytics
5. 🚀 Automate publishing workflow

---

## Support Resources

- **YouTube API Docs:** https://developers.google.com/youtube/v3
- **TikTok API Docs:** https://developers.tiktok.com/doc/
- **Instagram API Docs:** https://developers.facebook.com/docs/instagram-api
- **MSS Issues:** Check Flask console logs for detailed error messages

---

## Production Deployment

When deploying to production:

1. Use HTTPS for all redirect URIs
2. Store credentials in environment variables or secret manager
3. Implement token refresh logic
4. Set up monitoring and alerting
5. Handle API rate limits gracefully
6. Log all API interactions for debugging

---

**Version:** 1.0.0
**Last Updated:** January 16, 2025
**Created by:** Claude Code AI Assistant
