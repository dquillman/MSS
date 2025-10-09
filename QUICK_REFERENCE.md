# MSS Quick Reference Card

## 🚀 Most Common Commands

### Create Video from Blog Post
```bash
python scripts/make_video.py --url https://example.com/article --brand "My Channel"
```

### Create Video from AI Topics (Recommended)
```bash
python scripts/topics_to_video.py
# Pick from 5 AI-generated topics
# Automatically creates shorts + wide formats with thumbnails
```

### Skip YouTube Upload (Testing)
```bash
python scripts/make_video.py --url https://example.com/article --no-upload
```

### Schedule Video Publish
```bash
python scripts/topics_to_video.py --schedule "2025-10-01T16:00:00Z" --privacy private
```

### Check Video Performance
```bash
python scripts/analytics.py <video_id>
```

---

## ⚙️ Environment Variables Cheat Sheet

### Must Have (Required)
```bash
OPENAI_API_KEY=sk-...
GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json
SHOTSTACK_API_KEY=...
```

### Recommended (Free)
```bash
PEXELS_API_KEY=...              # Get at pexels.com/api (FREE)
ENABLE_STOCK_FOOTAGE=true       # Professional B-roll
ENABLE_SSML=true                # Natural voice (default: true)
```

### Voice Customization
```bash
TTS_VOICE_NAME=en-US-Neural2-C  # female (default)
TTS_VOICE_NAME=en-US-Neural2-A  # male professional
TTS_VOICE_NAME=en-US-Neural2-D  # male deep
TTS_VOICE_NAME=en-US-Neural2-F  # female energetic

TTS_SPEAKING_RATE=1.03          # Speed (0.25-4.0)
```

### Optional
```bash
YOUTUBE_API_KEY=...             # Trending topics
THUMBNAIL_VARIANTS=3            # Number of thumbnail styles
GSHEET_ID=...                   # Google Sheets logging
DISABLE_YT_UPLOAD=1             # Skip YouTube upload
```

---

## 🎨 Voice Options Quick Guide

| Voice Code | Gender | Style | Best For |
|------------|--------|-------|----------|
| `en-US-Neural2-C` | Female | Warm, clear | News, education (DEFAULT) |
| `en-US-Neural2-A` | Male | Professional | Business, tech |
| `en-US-Neural2-D` | Male | Deep, authoritative | Documentaries, serious topics |
| `en-US-Neural2-F` | Female | Energetic, young | Entertainment, lifestyle |
| `en-US-Studio-O` | Neutral | Premium quality | High-end productions |

**Test voices:** https://cloud.google.com/text-to-speech

---

## 📁 Output Files Explained

After running `topics_to_video.py`:

```
out/
├── topics.json              # 5 AI-generated topic ideas
├── topic_selected.json      # Your chosen topic
├── script.json              # Full script + metadata
├── voiceover.mp3            # SSML-enhanced voice
├── shorts.mp4               # 1080x1920 (vertical)
├── wide.mp4                 # 1920x1080 (horizontal)
├── thumb_variant_1.jpg      # Thumbnail option 1
├── thumb_variant_2.jpg      # Thumbnail option 2
├── thumb_variant_3.jpg      # Thumbnail option 3
└── summary.json             # All URLs and IDs
```

---

## 🎯 Workflow: Blog to YouTube

### Option 1: From URL (Fast)
```bash
python scripts/make_video.py \
  --url https://example.com/article \
  --brand "My Channel Name"

# Output: out/video.mp4 + YouTube link (if enabled)
```

### Option 2: From AI Topics (Best Quality)
```bash
# 1. Generate topics and pick one
python scripts/topics_to_video.py

# 2. System automatically:
#    - Fetches stock footage (if enabled)
#    - Creates SSML-enhanced voice
#    - Renders shorts + wide in parallel
#    - Generates 3 thumbnail variants
#    - Uploads to YouTube with chapters

# 3. Check performance (24-48h later)
python scripts/analytics.py <video_id>
```

---

## 🔧 Quick Fixes

### Stock Footage Not Appearing?
```bash
# Check these in order:
echo $PEXELS_API_KEY              # Should show your key
cat out/script.json | grep visual_cues  # Should have keywords
ENABLE_STOCK_FOOTAGE=true python scripts/topics_to_video.py
```

### Voice Sounds Robotic?
```bash
# Enable SSML (adds natural pauses)
ENABLE_SSML=true python scripts/topics_to_video.py

# OR try different voice
TTS_VOICE_NAME=en-US-Neural2-F python scripts/topics_to_video.py
```

### Rendering Too Slow?
```bash
# Use topics_to_video.py (has parallel rendering)
python scripts/topics_to_video.py  # ~90 seconds

# vs make_video.py (sequential)
python scripts/make_video.py --url ...  # ~150 seconds
```

### API Quota Exceeded?
```bash
# Shotstack Stage: 20 renders/month
# Solution 1: Upgrade to Production ($9/mo)
SHOTSTACK_ENV=production

# Solution 2: Reduce usage
# Each topics_to_video.py = 2 renders (shorts + wide)
# So you get 10 videos/month on free tier
```

---

## 📊 Performance Benchmarks

| Metric | Target | Action if Below |
|--------|--------|-----------------|
| Avg View % | 50%+ | Improve hook (first 3s) |
| Engagement Rate | 5%+ | Add stronger CTAs |
| CTR | 4%+ | Test different thumbnails |
| Views (24h) | 100+ | Optimize title/tags |

Check with:
```bash
python scripts/analytics.py <video_id>
```

---

## 🎬 Pro Tips

### 1. Stock Footage = 2x Better Videos
```bash
# Get free Pexels key (takes 2 minutes)
# Impact: Professional look, +50% retention
PEXELS_API_KEY=... ENABLE_STOCK_FOOTAGE=true
```

### 2. Test Thumbnail Variants
```bash
# Generate 3 variants per video
THUMBNAIL_VARIANTS=3

# Upload different videos with different variants
# Track CTR in YouTube Studio
# Use best-performing style going forward
```

### 3. Optimize Publish Times
```bash
# Test different times
--schedule "2025-10-01T14:00:00Z"  # 2 PM UTC
--schedule "2025-10-01T18:00:00Z"  # 6 PM UTC

# Track performance with analytics
python scripts/analytics.py <video_id>
```

### 4. Voice Variety
```bash
# Don't use same voice for every video
# Male voice for serious topics
TTS_VOICE_NAME=en-US-Neural2-D

# Female voice for lifestyle
TTS_VOICE_NAME=en-US-Neural2-F

# Alternate to keep audience engaged
```

### 5. Batch Production
```bash
# Generate 5 topics once
python scripts/topics_to_video.py  # Pick #1

# Save topics.json
cp out/topics.json topics_backup.json

# Later: manually edit topic_selected.json with #2-5
# Run make_video.py with topic as input
```

---

## 📈 Growth Strategy

### Week 1-2: Testing
- Generate 5-10 videos
- Test different voices
- Test all thumbnail variants
- Track which topics get most views

### Week 3-4: Optimization
- Use analytics to find patterns
- Double down on best-performing content types
- Optimize titles/thumbnails based on data
- Adjust voice/pacing based on retention

### Month 2+: Scaling
- Batch create content
- Schedule releases strategically
- Monitor trending topics
- Iterate on proven formulas

---

## 🆘 Emergency Commands

### Clear All Output
```bash
rm -rf out/*
```

### Reset Tokens (OAuth Issues)
```bash
rm token*.pickle
# Re-run script, will prompt for OAuth again
```

### Test Without Uploading
```bash
DISABLE_YT_UPLOAD=1 python scripts/topics_to_video.py
```

### Verbose Error Logging
```bash
python -u scripts/topics_to_video.py 2>&1 | tee debug.log
```

---

## 📞 Quick Links

- **Pexels API:** https://www.pexels.com/api/
- **Google TTS Voices:** https://cloud.google.com/text-to-speech/docs/voices
- **Shotstack Docs:** https://shotstack.io/docs/
- **OpenAI Models:** https://platform.openai.com/docs/models

---

## 💡 Remember

1. **Stock footage = Professional look** (enable it!)
2. **SSML = Natural voice** (already enabled)
3. **Parallel rendering = 40% faster** (automatic in topics_to_video.py)
4. **3 thumbnails = A/B testing** (test them all!)
5. **Analytics = Data-driven growth** (check after 48h)

---

**Need more details?** See `README.md` or `UPGRADE_GUIDE.md`
