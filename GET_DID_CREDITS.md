# How to Get D-ID Credits for Talking Avatars

## Step 1: Go to D-ID Studio
https://studio.d-id.com

## Step 2: Sign In
- You're already registered with: dquilllman2112@gmail.com
- Your current API key: `ZHF1aWxsbWFuMjExMkBnbWFpbC5jb20:CdsPdxDEeWWtIVkZXZ69L`

## Step 3: Buy Credits
1. Click "Pricing" or "Buy Credits"
2. Choose a plan:
   - **Trial**: $0 - 20 credits (about 20 videos) - FREE!
   - **Starter**: $5.90/month - 100 credits
   - **Pro**: $29/month - 500 credits
3. Start with the **FREE TRIAL** to test!

## Step 4: After Purchase
Your credits will automatically work with your existing API key - **NO CHANGES NEEDED**

## Step 5: Test It Works
Run this test:
```bash
python test_did_avatar.py
```

Should say: "Credits remaining: XX" (not 0)

## Step 6: Generate Videos
1. Restart server: `python web/api_server.py`
2. Generate a video from the web UI
3. Avatar will now have **REAL LIP-SYNC** talking!

---

## Current Status
- ✅ D-ID API key configured
- ✅ USE_DID_ANIMATION=true (in .env)
- ❌ Credits: 0 (need to purchase)
- ✅ Code ready to use D-ID

Once you have credits, avatars will automatically talk with lip-sync!
