# YouTube OAuth Redirect URIs to Add

Add ALL of these to your Google Cloud Console OAuth client:

## Development (Local)
- `http://localhost:5000/api/oauth/youtube/callback`
- `http://127.0.0.1:5000/api/oauth/youtube/callback`

## Production (Cloud Run)
- `https://mss-api-306798653079.us-central1.run.app/api/oauth/youtube/callback`

## Important Notes:
- Use **Web application** client type (NOT Desktop, iOS, or Android)
- Make sure the URLs match EXACTLY (including http vs https, trailing slashes, etc.)
- Add all three URLs even if you're only using production right now

## After adding:
1. Click **Save**
2. Download the JSON file
3. Save it as: `web/platform_credentials/youtube_client_secrets.json`
4. The file should have a structure like:
```json
{
  "web": {
    "client_id": "XXXXX.apps.googleusercontent.com",
    "client_secret": "XXXXX",
    "redirect_uris": [
      "http://localhost:5000/api/oauth/youtube/callback",
      "http://127.0.0.1:5000/api/oauth/youtube/callback",
      "https://mss-api-306798653079.us-central1.run.app/api/oauth/youtube/callback"
    ]
  }
}
```

