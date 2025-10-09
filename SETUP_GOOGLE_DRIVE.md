# Google Drive API Setup Guide

## Quick Setup (10 minutes)

Google Drive is used to host the TTS audio files publicly so Shotstack can access them.

### Step 1: Use Existing Google Cloud Project

You already have a project from the TTS setup (`mss-tts`). We'll use the same one.

**Go to**: https://console.cloud.google.com/

Make sure **mss-tts** (or your project name) is selected at the top.

### Step 2: Enable Google Drive API

1. Search for "**Google Drive API**" in the search bar
2. Click on **Google Drive API**
3. Click **ENABLE**

### Step 3: Create OAuth Client ID

1. Go to **APIs & Services** → **Credentials**
   - Direct link: https://console.cloud.google.com/apis/credentials

2. Click **+ CREATE CREDENTIALS** → **OAuth client ID**

3. **If you see "Configure consent screen":**
   - Click **CONFIGURE CONSENT SCREEN**
   - Select **External**
   - Click **CREATE**
   - Fill in:
     * **App name**: `MSS YouTube Automation`
     * **User support email**: (your email)
     * **Developer contact**: (your email)
   - Click **SAVE AND CONTINUE** (skip optional fields)
   - Click **SAVE AND CONTINUE** again (skip scopes)
   - Click **SAVE AND CONTINUE** again (skip test users)
   - Click **BACK TO DASHBOARD**

4. **Now create OAuth client ID:**
   - Go back to **Credentials**
   - Click **+ CREATE CREDENTIALS** → **OAuth client ID**
   - **Application type**: Select **Desktop app**
   - **Name**: `MSS Desktop Client`
   - Click **CREATE**

5. **Download the credentials:**
   - A dialog will appear with your client ID
   - Click **DOWNLOAD JSON**
   - Save the file

### Step 4: Save Credentials to MSS Directory

1. **Rename** the downloaded file to `client_secrets.json`
2. **Move it** to:
   ```
   G:\Users\daveq\MSS\client_secrets.json
   ```

### Step 5: First-Time Authorization

The first time you generate a video with Drive upload:

1. A browser window will open automatically
2. Sign in with your Google account
3. Click **Continue** (ignore "Google hasn't verified this app" warning)
4. Click **Allow** to grant Drive access
5. The authorization will be saved to `token.drive.pickle`

After this first time, it will work automatically!

### Step 6: Test Drive Upload

Generate a video and watch the Flask console. You should see:

```
✓ Audio uploaded: https://drive.google.com/uc?export=download&id=...
```

## What Gets Uploaded

- **Audio files**: TTS-generated voiceover.mp3
- **Videos** (optional): Rendered MP4 files
- **Folder structure**:
  ```
  /autopilot/
    /audio/
      voiceover.mp3
    /renders/
      shorts.mp4
      wide.mp4
  ```

## Troubleshooting

**Error: "No such file or directory: 'client_secrets.json'"**
- Make sure `client_secrets.json` is in the MSS root directory
- Check the filename (must be exactly `client_secrets.json`)

**Error: "The user did not consent to the scopes required"**
- Delete `token.drive.pickle`
- Run the script again to re-authorize

**Browser doesn't open for authorization**
- Check the console for a URL
- Copy and paste it into your browser manually

**Error: "Access denied" or "Invalid scope"**
- Make sure you enabled the Google Drive API (Step 2)
- Try deleting `token.drive.pickle` and re-authorizing

## Files Created (Already in .gitignore)

- `client_secrets.json` - OAuth credentials (kept secret)
- `token.drive.pickle` - Authorization token (kept secret)

Both are already excluded from git, so they won't be committed.

## Pricing

- **Google Drive**: 15 GB free (plenty for audio files)
- **Audio files**: ~500 KB each (30,000+ files before hitting limit)

## Next Steps

Once Drive is set up:
1. Generate a video
2. TTS audio will be uploaded to Drive automatically
3. Shotstack will download the audio from Drive's public URL
4. Your videos will have real voiceover! 🎉
