# YouTube OAuth Setup Guide

This guide walks you through setting up Google OAuth credentials to enable YouTube video uploads from MSS.

## Prerequisites

- A Google account
- Access to your YouTube channel
- The MSS application running locally

## Step 1: Create a Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Click **Select a project** → **New Project**
3. Enter project name: `MSS YouTube Uploader` (or your preferred name)
4. Click **Create**
5. Wait for the project to be created and select it

## Step 2: Enable YouTube Data API v3

1. In your project, go to **APIs & Services** → **Library**
2. Search for `YouTube Data API v3`
3. Click on it and then click **Enable**
4. Wait for the API to be enabled

## Step 3: Configure OAuth Consent Screen

1. Go to **APIs & Services** → **OAuth consent screen**
2. Select **External** (unless you have a Google Workspace account)
3. Click **Create**
4. Fill in the required fields:
   - **App name**: `MSS Studio`
   - **User support email**: Your email address
   - **Developer contact information**: Your email address
5. Click **Save and Continue**
6. On the **Scopes** page, click **Add or Remove Scopes**
7. Filter for `youtube` and select:
   - `https://www.googleapis.com/auth/youtube.upload`
8. Click **Update** → **Save and Continue**
9. On the **Test users** page, click **Add Users**
10. Add your Google/YouTube account email
11. Click **Save and Continue** → **Back to Dashboard**

## Step 4: Create OAuth 2.0 Credentials

1. Go to **APIs & Services** → **Credentials**
2. Click **Create Credentials** → **OAuth client ID**
3. Select **Application type**: `Desktop app`
4. **Name**: `MSS Desktop Client`
5. Click **Create**
6. Click **Download JSON** on the popup (or download from the credentials list)
7. Rename the downloaded file to `client_secrets.json`
8. Move the file to your MSS root directory: `G:\Users\daveq\mss\client_secrets.json`

## Step 5: First-Time Authentication

1. Start the MSS API server:
   ```bash
   cd G:\Users\daveq\mss
   python web/api_server.py
   ```

2. Open MSS Studio in your browser:
   ```
   http://localhost:5000/studio
   ```

3. Process a video as normal
4. When the YouTube upload section appears, fill in the details and click **Upload to YouTube**
5. A browser window will open asking you to sign in to Google
6. Sign in with the Google account you added as a test user
7. Click **Continue** when you see the "Google hasn't verified this app" warning
8. Grant the requested permissions
9. The browser will show "The authentication flow has completed"
10. Close the browser tab and return to MSS Studio

## Step 6: Verify Setup

After authentication:
- A `youtube_token.pickle` file will be created in your MSS directory
- This file stores your authentication credentials
- Future uploads will use this token automatically
- The token will be refreshed automatically when it expires

## Troubleshooting

### Error: "client_secrets.json not found"
- Make sure you downloaded the OAuth credentials JSON file
- Rename it to exactly `client_secrets.json`
- Place it in: `G:\Users\daveq\mss\client_secrets.json`

### Error: "Access blocked: MSS Studio has not completed verification"
- Make sure you added your email as a test user (Step 3, item 9-10)
- Make sure you're signing in with that exact email address
- If still blocked, check that the OAuth consent screen is configured correctly

### Error: "Insufficient permissions"
- Make sure you selected the `youtube.upload` scope in Step 3, item 7
- Delete `youtube_token.pickle` and re-authenticate

### Upload fails with "Invalid credentials"
- Delete the `youtube_token.pickle` file
- Restart the API server
- Try uploading again to trigger re-authentication

### Browser doesn't open for authentication
- Check that port 8080 is not blocked by a firewall
- The authentication server runs on `http://localhost:8080`

## Required Python Packages

Make sure you have installed:
```bash
pip install google-api-python-client google-auth-oauthlib google-auth-httplib2
```

## Security Notes

- **Never commit** `client_secrets.json` to version control
- **Never commit** `youtube_token.pickle` to version control
- Keep these files secure on your local machine only
- The `.gitignore` file already excludes these files

## File Locations

After setup, you should have:
```
G:\Users\daveq\mss\
├── client_secrets.json      (OAuth client credentials - DO NOT COMMIT)
├── youtube_token.pickle     (Cached auth token - DO NOT COMMIT)
├── scripts/
│   └── youtube_upload.py    (Upload script)
└── web/
    └── api_server.py        (API with /upload-to-youtube endpoint)
```

## Privacy Settings

When uploading videos, you can choose:
- **Private**: Only you can see the video
- **Unlisted**: Anyone with the link can see the video
- **Public**: Everyone can find and watch the video

Start with **Private** for testing, then change to **Unlisted** or **Public** later from YouTube Studio.

## Support

For issues with:
- **Google OAuth setup**: Check the [Google OAuth documentation](https://developers.google.com/youtube/v3/guides/authentication)
- **YouTube API**: Check the [YouTube Data API documentation](https://developers.google.com/youtube/v3)
- **MSS application**: Check the MSS repository issues or contact support
