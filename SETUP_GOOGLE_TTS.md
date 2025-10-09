# Google Cloud Text-to-Speech Setup Guide

## Quick Setup (5 minutes)

### Step 1: Create Google Cloud Project

1. Go to **https://console.cloud.google.com/**
2. Click **Select a Project** → **New Project**
3. Name it "MSS-TTS" (or any name)
4. Click **Create**

### Step 2: Enable Cloud Text-to-Speech API

1. In the Google Cloud Console, search for "**Text-to-Speech API**" in the search bar
2. Click on **Cloud Text-to-Speech API**
3. Click **Enable**

### Step 3: Create Service Account & Download Key

1. Go to **IAM & Admin** → **Service Accounts** (or search "service accounts")
2. Click **+ CREATE SERVICE ACCOUNT**
3. **Service account name**: `mss-tts`
4. Click **CREATE AND CONTINUE**
5. **Select a role**: Choose **Cloud Text-to-Speech User**
6. Click **CONTINUE** → **DONE**

### Step 4: Generate JSON Key

1. Click on the newly created service account (`mss-tts@...`)
2. Go to the **KEYS** tab
3. Click **ADD KEY** → **Create new key**
4. Select **JSON** format
5. Click **CREATE** - a JSON file will download

### Step 5: Save Credentials to MSS Directory

1. Move the downloaded JSON file to:
   ```
   G:\Users\daveq\MSS\gcp-service-account.json
   ```
2. **Important**: Add this file to `.gitignore` to keep it secret!

### Step 6: Verify Setup

Your `.env` file is already configured with:
```env
GOOGLE_APPLICATION_CREDENTIALS=G:\Users\daveq\MSS\gcp-service-account.json
TTS_VOICE_NAME=en-US-Neural2-C
TTS_SPEAKING_RATE=1.03
```

### Step 7: Test TTS

Run a test to generate audio:

```bash
python -c "from scripts.make_video import google_tts; from pathlib import Path; google_tts('Hello from Google Cloud TTS!', Path('out/test.mp3'), use_ssml=False); print('✓ TTS works! Check out/test.mp3')"
```

## Available Voices

Edit `TTS_VOICE_NAME` in `.env` to change voice:

- `en-US-Neural2-A` - Male (conversational)
- `en-US-Neural2-C` - **Female** (default, warm and clear)
- `en-US-Neural2-D` - Male (deep, authoritative)
- `en-US-Neural2-F` - Female (warm, friendly)
- `en-US-Neural2-I` - Male (young, energetic)
- `en-US-Neural2-J` - Male (professional, news anchor)

Full list: https://cloud.google.com/text-to-speech/docs/voices

## Pricing

- **Free tier**: 0-1 million characters/month FREE
- **After free tier**: $4 per 1 million characters (Neural2 voices)

A typical 60-second video narration ≈ 200 characters = **$0.0008** (less than a penny!)

## Troubleshooting

**Error: "Could not automatically determine credentials"**
- Make sure `gcp-service-account.json` exists in MSS root directory
- Check that path in `.env` matches the actual file location
- Restart Flask server after adding credentials

**Error: "Permission denied" or "API not enabled"**
- Make sure you enabled the Cloud Text-to-Speech API
- Check that service account has "Cloud Text-to-Speech User" role

**Error: "Invalid voice name"**
- Check voice name spelling in `.env` (case-sensitive)
- Visit https://cloud.google.com/text-to-speech/docs/voices for valid names

## Next Steps

Once TTS is set up, your video generation will include:
✓ Professional AI voiceovers (Google Neural2 voices)
✓ SSML support for better speech pacing
✓ Customizable speaking rate and pitch
✓ No more dummy audio!
