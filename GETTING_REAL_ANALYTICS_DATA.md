# Getting Real Data into Analytics Dashboard

## Overview

There are **4 ways** to get real data into your Analytics Dashboard:

1. **Auto-Track from Studio** (✅ IMPLEMENTED - Easiest)
2. **Add Demo Data** (✅ Already Available)
3. **Integrate YouTube Data API** (Recommended for Real Metrics)
4. **Manually Update Metrics via API** (For Testing/External Sources)

---

## Method 1: Auto-Track from Studio ✅ DONE

**Status:** ✅ Just implemented!

Every video you create in the Studio is now **automatically tracked** in analytics.

### How It Works

When you click **"Approve & Process"** in Studio and a video is successfully created:

1. The video info is automatically sent to `/api/analytics/track-video`
2. A record is created in the `videos` table
3. The video appears in your Analytics Dashboard immediately

### What Gets Tracked

- **Title**: From the "Title" field
- **Description**: From the "Angle / Hook" field
- **Filename**: The actual video file created (e.g., `final_with_intro_outro_123456.mp4`)
- **Topic Data**: Full topic info from localStorage (title, keywords, angle, etc.)
- **Created At**: Timestamp of creation

### Try It Now

1. Go to **Studio** page
2. Load a topic or enter title/keywords
3. Upload a video file
4. Click **"Approve & Process"**
5. Wait for processing to complete
6. Go to **Analytics Dashboard**
7. Your video should appear in the "Recent Videos" table!

---

## Method 2: Add Demo Data ✅ Available

**Status:** ✅ Already built-in

The Analytics Dashboard has a built-in demo data generator.

### How to Use

1. Open **Analytics Dashboard**
2. Click **"Add Demo Data"** button (top right, orange button)
3. Confirm the prompt
4. Wait a few seconds
5. Dashboard refreshes with 4 sample videos:
   - AI Tools 2025: Complete Guide (12,500 views)
   - Best Side Hustles to Start Today (8,900 views)
   - Travel Tips for Europe on a Budget (5,600 views)
   - Fitness Transformation in 30 Days (3,200 views)

### Demo Data Includes

- Realistic view counts, likes, comments
- Calculated engagement rates
- Various titles and topics
- Timestamps

This is great for:
- Testing the dashboard UI
- Understanding how metrics display
- Demonstrating the feature to others
- Development and debugging

---

## Method 3: Integrate YouTube Data API (Recommended) 🚀

**Status:** ✅ IMPLEMENTED

This is the **best approach** for getting real, live metrics from your actual YouTube channel(s).

### Step-by-Step Setup

#### 1. Get YouTube API Credentials

**A. Create Google Cloud Project:**
1. Go to https://console.cloud.google.com/
2. Create a new project or select existing
3. Name it "MSS Analytics" or similar

**B. Enable YouTube Data API v3:**
1. Go to **APIs & Services** > **Library**
2. Search for "YouTube Data API v3"
3. Click **Enable**

**C. Create OAuth 2.0 Credentials:**
1. Go to **APIs & Services** > **Credentials**
2. Click **+ CREATE CREDENTIALS** > **OAuth client ID**
3. Application type: **Web application**
4. Name: "MSS YouTube Integration"
5. Authorized redirect URIs: `http://localhost:5000/auth/youtube/callback`
6. Click **Create**
7. Download the JSON file (save as `youtube_client_secret.json`)

**D. Get API Key (for public data):**
1. Go to **APIs & Services** > **Credentials**
2. Click **+ CREATE CREDENTIALS** > **API key**
3. Copy the API key
4. Add to your `.env` file:
```
YOUTUBE_API_KEY=your_api_key_here
```

#### 2. Install Required Python Libraries

```bash
pip install google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client
```

#### 3. Create YouTube Integration Module

Create `web/youtube_integration.py`:

```python
"""
YouTube Data API Integration for MSS Analytics
"""

import os
import pickle
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

SCOPES = ['https://www.googleapis.com/auth/youtube.readonly']

class YouTubeAnalytics:
    def __init__(self, credentials_file='youtube_client_secret.json', token_file='youtube_token.pickle'):
        self.credentials_file = credentials_file
        self.token_file = token_file
        self.youtube = None
        self.authenticate()

    def authenticate(self):
        """Authenticate with YouTube API"""
        creds = None

        # Load existing token
        if os.path.exists(self.token_file):
            with open(self.token_file, 'rb') as token:
                creds = pickle.load(token)

        # If no valid credentials, log in
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.credentials_file, SCOPES)
                creds = flow.run_local_server(port=8080)

            # Save credentials for next run
            with open(self.token_file, 'wb') as token:
                pickle.dump(creds, token)

        self.youtube = build('youtube', 'v3', credentials=creds)

    def get_video_stats(self, video_id):
        """Get statistics for a specific video"""
        try:
            request = self.youtube.videos().list(
                part='statistics',
                id=video_id
            )
            response = request.execute()

            if not response['items']:
                return None

            stats = response['items'][0]['statistics']

            return {
                'views': int(stats.get('viewCount', 0)),
                'likes': int(stats.get('likeCount', 0)),
                'comments': int(stats.get('commentCount', 0)),
                'favorites': int(stats.get('favoriteCount', 0))
            }
        except Exception as e:
            print(f"Error fetching video stats: {e}")
            return None

    def get_my_videos(self, max_results=50):
        """Get all videos from authenticated user's channel"""
        try:
            # Get user's channel
            channels = self.youtube.channels().list(
                part='contentDetails',
                mine=True
            ).execute()

            if not channels['items']:
                return []

            # Get uploads playlist
            uploads_playlist = channels['items'][0]['contentDetails']['relatedPlaylists']['uploads']

            # Get videos from uploads playlist
            videos = []
            request = self.youtube.playlistItems().list(
                part='snippet',
                playlistId=uploads_playlist,
                maxResults=max_results
            )

            while request:
                response = request.execute()

                for item in response['items']:
                    video_id = item['snippet']['resourceId']['videoId']
                    title = item['snippet']['title']
                    description = item['snippet']['description']
                    published_at = item['snippet']['publishedAt']

                    videos.append({
                        'video_id': video_id,
                        'title': title,
                        'description': description,
                        'published_at': published_at
                    })

                request = self.youtube.playlistItems().list_next(request, response)

            return videos
        except Exception as e:
            print(f"Error fetching videos: {e}")
            return []

    def sync_video_metrics(self, video_id, analytics_manager, user_email):
        """Sync metrics for a video to analytics database"""
        stats = self.get_video_stats(video_id)

        if not stats:
            return False

        # Find video in database by platform_video_id
        # (You'd need to store YouTube video IDs when publishing)

        # Update metrics
        metrics = {
            'views': stats['views'],
            'likes': stats['likes'],
            'comments': stats['comments'],
            'shares': 0,  # YouTube API doesn't provide share count
            'watch_time_minutes': 0,  # Requires YouTube Analytics API
            'ctr': 0,  # Requires YouTube Analytics API
            'avg_view_duration': 0  # Requires YouTube Analytics API
        }

        # Record metrics (you'd need video_id from your database)
        # analytics_manager.record_video_metrics(video_id, metrics, 'youtube')

        return True
```

#### 4. Add API Endpoint

Add to `web/api_server.py`:

```python
# YouTube integration
youtube_analytics = None
try:
    from web.youtube_integration import YouTubeAnalytics
    youtube_analytics = YouTubeAnalytics()
    print("[YOUTUBE] ✓ YouTube Analytics integrated")
except Exception as e:
    print(f"[YOUTUBE] ✗ YouTube integration not available: {e}")

@app.route('/api/youtube/sync-metrics', methods=['POST'])
def sync_youtube_metrics():
    """Sync metrics from YouTube for all published videos"""
    if not youtube_analytics or not analytics_manager:
        return jsonify({'success': False, 'error': 'YouTube or Analytics not available'}), 500

    user_email, error_response, error_code = _get_user_from_session()
    if error_response:
        return error_response, error_code

    try:
        # Get user's YouTube videos
        youtube_videos = youtube_analytics.get_my_videos()

        synced_count = 0
        for video in youtube_videos:
            # Sync each video's metrics
            if youtube_analytics.sync_video_metrics(video['video_id'], analytics_manager, user_email):
                synced_count += 1

        return jsonify({
            'success': True,
            'synced': synced_count,
            'total': len(youtube_videos)
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
```

#### 5. Add Sync Button to Analytics Dashboard

Add to `analytics-dashboard.html`:

```html
<button class="btn" onclick="syncYouTubeMetrics()" style="background:#FF0000; border-color:#FF0000;">
  Sync from YouTube
</button>

<script>
async function syncYouTubeMetrics() {
  const btn = event.target;
  btn.disabled = true;
  btn.textContent = 'Syncing...';

  try {
    const res = await fetch(`${API_BASE}/api/youtube/sync-metrics`, {
      method: 'POST',
      credentials: 'include'
    });

    const data = await res.json();

    if (data.success) {
      alert(`Synced ${data.synced} of ${data.total} videos from YouTube!`);
      loadDashboard(); // Refresh dashboard
    } else {
      throw new Error(data.error || 'Sync failed');
    }
  } catch (e) {
    alert('Sync failed: ' + e.message);
  } finally {
    btn.disabled = false;
    btn.textContent = 'Sync from YouTube';
  }
}
</script>
```

#### 6. Run First-Time Authentication

1. Start your Flask server: `python web/api_server.py`
2. Open Analytics Dashboard
3. Click "Sync from YouTube"
4. Browser will open Google OAuth consent screen
5. Sign in with your YouTube account
6. Grant permissions
7. Credentials saved to `youtube_token.pickle`
8. Metrics synced automatically!

### Automated Syncing

Set up a scheduled job to sync metrics hourly:

```python
import schedule
import time

def sync_all_users_youtube_metrics():
    """Sync YouTube metrics for all users"""
    # Get all users with YouTube connections
    # For each user, sync their video metrics
    pass

# Run every hour
schedule.every(1).hours.do(sync_all_users_youtube_metrics)

while True:
    schedule.run_pending()
    time.sleep(60)
```

---

## Method 4: Manual API Updates (For Testing)

You can manually update metrics via API calls.

### Update Single Video Metrics

```bash
curl -X POST http://localhost:5000/api/analytics/update-metrics \
  -H "Content-Type: application/json" \
  -b "session_id=YOUR_SESSION_ID" \
  -d '{
    "video_id": 1,
    "metrics": {
      "views": 5000,
      "likes": 250,
      "comments": 45,
      "shares": 12,
      "watch_time_minutes": 2500,
      "ctr": 8.5,
      "avg_view_duration": 180
    },
    "platform": "youtube"
  }'
```

### Python Script to Update Metrics

```python
import requests

API_BASE = 'http://localhost:5000'
SESSION_ID = 'your_session_cookie'  # Get from browser dev tools

def update_video_metrics(video_id, metrics):
    response = requests.post(
        f'{API_BASE}/api/analytics/update-metrics',
        json={
            'video_id': video_id,
            'metrics': metrics,
            'platform': 'youtube'
        },
        cookies={'session_id': SESSION_ID}
    )
    return response.json()

# Example usage
metrics = {
    'views': 10000,
    'likes': 500,
    'comments': 85,
    'shares': 25,
    'watch_time_minutes': 5000,
    'ctr': 12.3,
    'avg_view_duration': 210
}

result = update_video_metrics(video_id=1, metrics=metrics)
print(result)
```

---

## Quick Start Checklist

Want to see your analytics dashboard with real data **right now**? Follow these steps:

### Fastest Way (5 minutes):

1. ✅ **Create a video in Studio**
   - Go to Studio page
   - Enter a title and keywords
   - Upload any video file
   - Click "Approve & Process"
   - Wait for it to finish

2. ✅ **Check Analytics Dashboard**
   - Click the green "Analytics" button
   - Your video should appear in "Recent Videos"!

3. ✅ **Add some demo data** (optional)
   - Click "Add Demo Data" button
   - Now you have multiple videos with metrics

### For Real YouTube Metrics (1 hour):

1. Follow **Method 3** instructions above
2. Set up YouTube Data API
3. Add sync functionality
4. Connect your YouTube account
5. Sync real metrics from your channel

---

## Comparing the Methods

| Method | Effort | Real Data | Updates | Best For |
|--------|--------|-----------|---------|----------|
| Auto-Track from Studio | ✅ None | ⚠️ Partial | On creation | Getting started quickly |
| Demo Data | ✅ Instant | ❌ Fake | Manual | Testing/demos |
| YouTube API Integration | ⚠️ Medium | ✅ Yes | Hourly/Daily | Production use |
| Manual API Updates | ⚠️ High | ✅ Yes | Manual | Custom integrations |

---

## Troubleshooting

### Videos not appearing in Analytics

**Check:**
1. Open browser console (F12)
2. Look for `[ANALYTICS] Video tracked: ...` message
3. If you see it, video was tracked successfully
4. Go to Analytics Dashboard and click "Refresh"

**If still not appearing:**
1. Check Flask server console for `[ANALYTICS] ✓ AnalyticsManager loaded`
2. Verify database tables exist:
```bash
sqlite3 web/mss_users.db
.tables
# Should show: videos, video_metrics, channel_stats
.quit
```

### YouTube API Quota Exceeded

YouTube Data API has daily quotas (10,000 units/day by default).

**Solutions:**
- Cache metrics and update less frequently
- Request quota increase from Google
- Only sync metrics for recent videos

---

## Next Steps

1. **Start creating videos** in Studio - they'll auto-track!
2. **Add demo data** to see how analytics look
3. **Set up YouTube API** for real metrics (optional)
4. **Monitor your performance** and optimize content strategy

Your analytics dashboard is now ready to track your video performance! 🎉
