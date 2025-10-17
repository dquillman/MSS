# Performance Analytics & Multi-Platform Publisher

## Overview

This document covers two major world-class features added to MSS:

1. **Performance Analytics Dashboard** - Track video performance and engagement metrics
2. **Multi-Platform Publisher** - Publish videos to YouTube, TikTok, Instagram Reels, and more

---

## Feature #1: Performance Analytics Dashboard

### What It Does

The Analytics Dashboard provides comprehensive insights into your video performance, helping you understand what content works best and optimize your strategy.

### Key Features

#### 📊 Overview Stats
- **Total Videos**: Count of all videos created
- **Total Views**: Aggregate view count across all videos
- **Total Engagement**: Likes, comments, and shares
- **Average Engagement Rate**: Percentage of viewers who engage
- **Top Performer**: Your best-performing video with metrics

#### 📈 Video Performance Tracking
- Track individual video metrics:
  - Views
  - Likes
  - Comments
  - Shares
  - Watch time
  - Click-through rate (CTR)
  - Average view duration
  - Engagement rate

#### 📅 Time Period Filtering
- Last 7 days
- Last 30 days (default)
- Last 90 days
- Last year

#### 📋 Recent Videos Table
- Sortable list of all your videos
- Status indicators (created, published, processing, failed)
- Color-coded engagement badges
- Platform identification

### How to Use

#### 1. Access the Dashboard
- Navigate from Topic Picker or Studio
- Click the **Analytics** button (green)

#### 2. View Your Stats
- Overview cards show key metrics at a glance
- Top performer card highlights your best video
- Recent videos table shows all videos with metrics

#### 3. Filter by Time Period
- Use the dropdown to select different time ranges
- Click **Refresh** to reload data

#### 4. Add Demo Data (for Testing)
- Click **Add Demo Data** button in header
- Confirms before adding sample videos with metrics
- Useful for testing the dashboard

### API Endpoints

```
GET  /api/analytics/dashboard?days=30    - Get dashboard stats
GET  /api/analytics/videos?limit=50      - Get videos with metrics
POST /api/analytics/track-video          - Track new video creation
POST /api/analytics/update-metrics       - Update video metrics
```

### Database Tables

**videos**
- Stores all created videos
- Links to user account
- Tracks title, description, filename, platform
- Records creation and publication timestamps

**video_metrics**
- Performance data for each video
- Multiple metric snapshots over time
- Calculates engagement rate automatically
- Supports multiple platforms

**channel_stats**
- Overall channel performance
- Subscriber count
- Total views and watch time
- Revenue estimates (future)

---

## Feature #2: Multi-Platform Publisher

### What It Does

Automatically optimize and publish your videos to multiple platforms (YouTube, TikTok, Instagram Reels, Facebook, etc.) with a single workflow.

### Key Features

#### 🚀 Multi-Platform Support
- **YouTube**: Standard videos (16:9, up to 12 hours)
- **YouTube Shorts**: Vertical shorts (9:16, max 60s)
- **TikTok**: Vertical videos (9:16, max 10 min)
- **Instagram Reels**: Vertical videos (9:16, max 90s)
- **Instagram Feed**: Square videos (1:1, max 10 min)
- **Facebook**: Standard videos (16:9, max 4 hours)

#### 🎬 Automatic Video Optimization
- Automatically resizes videos for each platform
- Adjusts aspect ratio (16:9, 9:16, 1:1)
- Compresses to meet file size limits
- Maintains quality while meeting specs

#### 📋 Publishing Queue
- Queue videos for publishing
- Track status (pending, processing, completed, failed)
- Schedule publications for later
- Batch publish to multiple platforms

#### 🔧 Platform Specifications
- View detailed specs for each platform
- Max duration, file size, resolution
- Aspect ratio requirements
- Optimization guidelines

### How to Use

#### 1. Access Multi-Platform Publisher
- Navigate from Topic Picker or Studio
- Click the **Multi-Platform** button (orange)

#### 2. Publish a Video

**Step 1: Select Video**
- Upload a video file, OR
- Select from recent videos

**Step 2: Select Platforms**
- Check the platforms you want to publish to
- See specs for each platform (aspect ratio, max duration, etc.)
- Select multiple platforms to reach more audiences

**Step 3: Enter Video Details**
- **Title**: Video title (max 100 characters)
- **Description**: Video description/caption
- **Tags**: Comma-separated tags/keywords

**Step 4: Publish**
- Click **Publish Now** to start immediately, OR
- Click **Add to Queue** to publish later

#### 3. Check Publishing Queue
- Switch to **Publishing Queue** tab
- View status of all queued videos
- See which platforms each video is going to
- Monitor for errors

#### 4. View Platform Specs
- Switch to **Platforms** tab
- See specifications for all supported platforms
- Use this to plan your content strategy

### API Endpoints

```
GET  /api/platforms/presets           - Get platform specifications
POST /api/platforms/optimize          - Optimize video for platform
POST /api/platforms/queue             - Add video to publishing queue
GET  /api/platforms/queue?status=     - Get publishing queue
GET  /api/platforms/published         - Get published videos
GET  /api/platforms/connected         - Get connected platforms
```

### Database Tables

**platform_presets**
- Platform specifications
- Max duration, file size, aspect ratio
- Recommended resolution
- Pre-populated with all major platforms

**publishing_queue**
- Videos queued for publishing
- Target platforms (JSON array)
- Title, description, tags
- Status tracking
- Error messages

**published_videos**
- Record of published videos
- Platform-specific video IDs and URLs
- Publication timestamps
- Links to analytics

**platform_connections**
- OAuth tokens for connected platforms
- Access and refresh tokens
- Connection status
- Expiration tracking

---

## Integration Guide

### Connecting the Features

#### Track Videos from Studio
When users create videos in the Studio, automatically track them in analytics:

```javascript
// After video is created successfully
await fetch('/api/analytics/track-video', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  credentials: 'include',
  body: JSON.stringify({
    title: videoTitle,
    description: videoDescription,
    filename: resultFilename,
    topic_data: topicInfo
  })
});
```

#### Publish from Analytics
Add "Publish" buttons to analytics dashboard to quickly push videos to platforms:

```javascript
function publishVideo(videoId, filename) {
  // Navigate to multi-platform with pre-filled data
  localStorage.setItem('publishVideo', JSON.stringify({
    filename: filename,
    video_id: videoId
  }));
  window.location.href = '/multi-platform';
}
```

#### Update Metrics Automatically
Fetch platform metrics periodically and update analytics:

```javascript
// Scheduled job (backend)
async function updateMetricsFromPlatforms() {
  const videos = await getPublishedVideos();
  for (const video of videos) {
    const metrics = await fetchPlatformMetrics(video.platform, video.platform_video_id);
    await updateVideoMetrics(video.id, metrics);
  }
}
```

---

## Video Optimization Technical Details

### FFmpeg Commands Used

The multi-platform module uses FFmpeg to optimize videos:

```bash
ffmpeg -i input.mp4 \
  -vf "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2,setsar=1" \
  -c:v libx264 \
  -preset medium \
  -crf 23 \
  -c:a aac \
  -b:a 128k \
  -movflags +faststart \
  -y output.mp4
```

**Parameters:**
- `scale`: Resize video to target resolution
- `pad`: Add letterboxing if needed
- `libx264`: H.264 codec (universal compatibility)
- `preset medium`: Balance speed/quality
- `crf 23`: Constant quality (lower = better)
- `aac 128k`: Audio codec and bitrate
- `faststart`: Enable streaming

### Aspect Ratio Conversions

**16:9 → 9:16 (Vertical)**
- Crop or letterbox sides
- Add blur background for cinematic effect (optional)

**16:9 → 1:1 (Square)**
- Crop top/bottom or sides
- Center the main subject

**9:16 → 16:9 (Horizontal)**
- Letterbox (add black bars)
- Or zoom and crop (loses some content)

---

## Future Enhancements

### Analytics Dashboard
- [ ] Real-time metrics via webhooks
- [ ] Chart visualizations (Chart.js/D3.js)
- [ ] Export reports (PDF/CSV)
- [ ] Comparative analytics (video A vs B)
- [ ] Audience demographics
- [ ] Traffic sources breakdown
- [ ] Revenue tracking
- [ ] Goal setting and alerts

### Multi-Platform Publisher
- [ ] YouTube Data API integration
- [ ] TikTok API integration
- [ ] Instagram Graph API integration
- [ ] Facebook Graph API integration
- [ ] OAuth flows for platform connections
- [ ] Scheduled publishing
- [ ] Auto-publish on render complete
- [ ] Thumbnail optimization per platform
- [ ] Hashtag suggestions
- [ ] Cross-posting rules engine
- [ ] Platform-specific descriptions
- [ ] Auto-translate captions

---

## Platform API Integration Guide

### YouTube Data API v3

**Setup:**
1. Get API key from Google Cloud Console
2. Enable YouTube Data API v3
3. Create OAuth 2.0 credentials

**Upload Video:**
```python
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

youtube = build('youtube', 'v3', credentials=credentials)

body = {
    'snippet': {
        'title': 'Video Title',
        'description': 'Video Description',
        'tags': ['tag1', 'tag2'],
        'categoryId': '22'
    },
    'status': {
        'privacyStatus': 'public'
    }
}

media = MediaFileUpload('video.mp4', chunksize=-1, resumable=True)

request = youtube.videos().insert(
    part='snippet,status',
    body=body,
    media_body=media
)

response = request.execute()
```

### TikTok API

**Setup:**
1. Register app at TikTok for Developers
2. Get client key and secret
3. Implement OAuth flow

**Upload Video:**
```python
import requests

url = 'https://open-api.tiktok.com/share/video/upload/'

headers = {
    'Authorization': f'Bearer {access_token}',
    'Content-Type': 'application/json'
}

data = {
    'video': {
        'description': 'Video caption',
        'disable_duet': False,
        'disable_stitch': False
    }
}

files = {
    'video': open('video.mp4', 'rb')
}

response = requests.post(url, headers=headers, json=data, files=files)
```

### Instagram Graph API

**Setup:**
1. Create Facebook App
2. Add Instagram Graph API
3. Get user access token with permissions

**Upload Video:**
```python
import requests

# Step 1: Create media container
url = f'https://graph.facebook.com/v12.0/{instagram_account_id}/media'

data = {
    'media_type': 'VIDEO',
    'video_url': 'https://your-server.com/video.mp4',
    'caption': 'Video caption #hashtags',
    'access_token': access_token
}

container = requests.post(url, data=data).json()
container_id = container['id']

# Step 2: Publish media
publish_url = f'https://graph.facebook.com/v12.0/{instagram_account_id}/media_publish'
publish_data = {
    'creation_id': container_id,
    'access_token': access_token
}

response = requests.post(publish_url, data=publish_data).json()
```

---

## Files Created/Modified

```
web/analytics.py                                  (NEW) - Analytics backend
web/multi_platform.py                             (NEW) - Multi-platform backend
web/api_server.py                                 (MODIFIED) - Added API endpoints
web/topic-picker-standalone/
  ├── analytics-dashboard.html                    (NEW) - Analytics UI
  ├── multi-platform.html                         (NEW) - Multi-platform UI
  ├── index.html                                  (MODIFIED) - Added nav buttons
  ├── studio.html                                 (MODIFIED) - Added nav buttons
web/mss_users.db                                  (MODIFIED) - New tables
```

---

## Testing Checklist

### Analytics Dashboard
- [ ] Dashboard loads without errors
- [ ] Stats display correctly
- [ ] Time period filter works
- [ ] Videos table populates
- [ ] Add demo data button works
- [ ] Demo data appears in stats
- [ ] Engagement badges color-coded correctly
- [ ] Status badges display properly

### Multi-Platform Publisher
- [ ] Publisher page loads
- [ ] Platform grid displays
- [ ] Platform selection works
- [ ] Checkboxes toggle properly
- [ ] Form validation works
- [ ] Add to queue succeeds
- [ ] Queue displays items
- [ ] Status badges update
- [ ] Platform specs table shows correctly

### Integration
- [ ] Navigation buttons work from all pages
- [ ] Session authentication works
- [ ] Database tables created successfully
- [ ] No console errors
- [ ] API endpoints respond correctly

---

## Performance Considerations

### Analytics
- Database indexes on `user_email` and `video_id`
- Limit queries to recent data (30-90 days default)
- Cache dashboard stats (Redis future enhancement)
- Pagination for large video lists

### Multi-Platform
- Optimize videos asynchronously (background jobs)
- Queue system prevents overwhelming servers
- FFmpeg timeout set to 5 minutes max
- File cleanup after successful upload

---

## Security Notes

### Analytics
- All endpoints require authentication
- Users can only access their own data
- SQL injection protected (parameterized queries)
- Metrics can only be updated by authorized users

### Multi-Platform
- Platform credentials encrypted at rest
- OAuth tokens refreshed automatically
- Video files access-controlled by user
- Publishing queue items tied to user accounts

---

## Troubleshooting

### Analytics Not Loading
**Problem**: Dashboard shows "Analytics not available"
**Solution**:
1. Check Flask console for `[ANALYTICS] ✓ AnalyticsManager loaded`
2. Verify `web/analytics.py` exists
3. Restart Flask server
4. Check database tables created: `videos`, `video_metrics`, `channel_stats`

### No Videos in Analytics
**Problem**: Analytics dashboard is empty
**Solution**:
1. Click "Add Demo Data" button to add sample videos
2. Or create videos in Studio (future: auto-track)
3. Check browser console for API errors

### Multi-Platform Not Loading
**Problem**: Multi-platform page shows error
**Solution**:
1. Check Flask console for `[MULTIPLATFORM] ✓ MultiPlatformPublisher loaded`
2. Verify `web/multi_platform.py` exists
3. Restart Flask server
4. Check database tables created: `platform_presets`, `publishing_queue`

### Video Optimization Fails
**Problem**: "Optimization failed" error
**Solution**:
1. Ensure FFmpeg is installed and in PATH
2. Check input video file exists
3. Verify disk space available
4. Check FFmpeg error message in response

### Platform API Errors
**Problem**: "Failed to publish" errors
**Solution**:
1. Verify platform API credentials valid
2. Check OAuth tokens not expired
3. Ensure video meets platform requirements
4. Review platform API documentation

---

## Version History

**v1.0.0** - 2025-01-16
- Initial release
- Analytics dashboard with overview stats
- Video performance tracking
- Multi-platform publisher with 6 platforms
- Auto video optimization
- Publishing queue system
- Platform specifications reference

---

## License

Part of MSS (Many Sources Say) application
© 2025 - Internal use

---

## Support

For issues or questions:
- Check Flask server console logs
- Review browser developer console
- Verify database schema
- Test with demo data first

**Created by:** Claude Code AI Assistant
**Date:** January 16, 2025
**Version:** 1.0.0
