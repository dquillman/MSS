# Multi-Channel YouTube Management Guide

## Overview

MSS now supports **multiple YouTube channels** per user. You can:

- Connect multiple YouTube channels (different Google accounts)
- Set a default channel for syncing and publishing
- Track analytics separately for each channel
- Switch between channels easily
- Sync metrics from all connected channels

---

## Quick Start

### 1. Access Channel Manager

From the Analytics Dashboard, click the **"Channels"** button in the header, or navigate directly to:
```
http://localhost:5000/channel-manager
```

### 2. Add Your First Channel

1. Click **"+ Add YouTube Channel"**
2. Sign in with your Google account
3. Grant permissions to MSS
4. Your channel will be automatically detected and added
5. The first channel you add becomes your **default channel**

### 3. Add Additional Channels

1. Click **"+ Add YouTube Channel"** again
2. **Important**: Sign in with a *different* Google account
3. Grant permissions
4. The new channel will be added to your list

---

## Key Features

### Default Channel

- **One channel is always marked as "Default"**
- The default channel is used for:
  - YouTube metrics syncing (when you click "Sync from YouTube")
  - Video uploads (default selection)
  - Analytics dashboard stats (default view)

### Setting a Different Default

1. Go to Channel Manager
2. Find the channel you want to make default
3. Click **"Set as Default"**
4. The channel will be marked with a ⭐ badge

### Removing Channels

1. Go to Channel Manager
2. Click **"Remove"** on the channel you want to remove
3. Confirm the action
4. **Note**: This only removes the channel from MSS, not from YouTube
5. Previously synced videos remain in your analytics

---

## How It Works

### OAuth & Channel Detection

When you connect via OAuth:

1. MSS authenticates with Google using your credentials
2. The YouTube Data API is called to fetch channel information
3. Channel info (ID, name, thumbnail, custom URL) is stored in `channel_accounts` table
4. Each OAuth connection is tied to ONE Google account = ONE YouTube channel

### Multiple Google Accounts

To add multiple channels, you need multiple Google accounts:

- **Account A** → Channel A (e.g., "My Gaming Channel")
- **Account B** → Channel B (e.g., "My Cooking Channel")
- **Account C** → Channel C (e.g., "My Music Channel")

Each account/channel requires its own OAuth flow.

### Channel Syncing

When you click "Sync from YouTube":

1. MSS fetches the YouTube channel info for the currently connected Google account
2. It detects which channel that account owns
3. It syncs metrics (views, likes, comments) for videos from that channel
4. Videos are linked to the specific `channel_account_id` in the database

---

## Database Schema

### `channel_accounts` Table

```sql
CREATE TABLE channel_accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_email TEXT NOT NULL,
    platform TEXT DEFAULT 'youtube',
    channel_id TEXT,                  -- YouTube channel ID (e.g., UCxxxxx)
    channel_name TEXT,                -- Channel display name
    channel_handle TEXT,              -- @handle (if available)
    channel_custom_url TEXT,          -- Custom URL
    channel_description TEXT,
    thumbnail_url TEXT,
    is_active BOOLEAN DEFAULT 1,      -- Soft delete flag
    is_default BOOLEAN DEFAULT 0,     -- One default per user
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_synced_at TIMESTAMP,         -- Last time metrics were synced
    UNIQUE(user_email, platform, channel_id)
);
```

### `videos` Table Enhancement

The `videos` table now has a `channel_account_id` column:

```sql
ALTER TABLE videos ADD COLUMN channel_account_id INTEGER;
```

This links each video to a specific channel, allowing you to:
- Filter analytics by channel
- Track which videos belong to which channel
- Maintain separate metrics per channel

---

## API Endpoints

### Get All Channels

```http
GET /api/channels/list?platform=youtube
```

**Response:**
```json
{
  "success": true,
  "channels": [
    {
      "id": 1,
      "user_email": "user@example.com",
      "platform": "youtube",
      "channel_id": "UCxxxxx",
      "channel_name": "My Gaming Channel",
      "channel_handle": "mygaming",
      "channel_custom_url": "c/mygaming",
      "thumbnail_url": "https://...",
      "is_active": 1,
      "is_default": 1,
      "added_at": "2025-01-16 10:00:00",
      "last_synced_at": "2025-01-16 11:30:00"
    },
    ...
  ],
  "count": 2
}
```

### Set Default Channel

```http
POST /api/channels/set-default
Content-Type: application/json

{
  "channel_account_id": 2
}
```

**Response:**
```json
{
  "success": true
}
```

### Remove Channel

```http
POST /api/channels/remove
Content-Type: application/json

{
  "channel_account_id": 3
}
```

**Response:**
```json
{
  "success": true
}
```

### Add YouTube Channel

```http
POST /api/channels/add-youtube
```

This endpoint:
1. Gets the currently authenticated YouTube channel info
2. Stores it in `channel_accounts` if not already present
3. Returns channel details

**Response:**
```json
{
  "success": true,
  "channel_id": "UCxxxxx",
  "title": "My New Channel",
  "subscribers": 1250,
  "video_count": 45,
  "view_count": 125000,
  "channel_account_id": 4
}
```

### Sync YouTube Metrics

```http
POST /api/youtube/sync-metrics
```

This endpoint now:
1. Detects the authenticated YouTube channel
2. Adds/updates the channel in `channel_accounts`
3. Syncs all videos from that channel
4. Links videos to the `channel_account_id`
5. Updates `last_synced_at` timestamp

**Response:**
```json
{
  "success": true,
  "synced": 15,
  "updated": 30,
  "total": 45,
  "channel": "My Gaming Channel",
  "message": "Synced 15 new videos, updated 30 existing videos from My Gaming Channel"
}
```

---

## Python API (analytics.py)

### Get User's Channels

```python
from web.analytics import AnalyticsManager

analytics = AnalyticsManager()

# Get all active channels for a user
channels = analytics.get_user_channels('user@example.com', platform='youtube')

for channel in channels:
    print(f"{channel['channel_name']} - Default: {channel['is_default']}")
```

### Get Default Channel

```python
default_channel = analytics.get_default_channel('user@example.com', platform='youtube')

if default_channel:
    print(f"Default: {default_channel['channel_name']}")
```

### Add a Channel

```python
channel_id = analytics.add_channel_account('user@example.com', 'youtube', {
    'channel_id': 'UCxxxxx',
    'channel_name': 'My New Channel',
    'channel_handle': 'mynewchannel',
    'channel_custom_url': 'c/mynewchannel',
    'channel_description': 'A channel about...',
    'thumbnail_url': 'https://...'
})

print(f"Channel added with ID: {channel_id}")
```

### Set Default Channel

```python
success = analytics.set_default_channel('user@example.com', channel_account_id=2)

if success:
    print("Default channel updated!")
```

### Update Sync Time

```python
success = analytics.update_channel_sync_time(channel_account_id=1)
```

### Remove a Channel (Soft Delete)

```python
success = analytics.remove_channel_account('user@example.com', channel_account_id=3)

if success:
    print("Channel removed!")
```

---

## Use Cases

### Use Case 1: Multiple Creator Channels

**Scenario**: You manage 3 YouTube channels:
- **Tech Reviews** (100K subs)
- **Gaming Highlights** (50K subs)
- **Vlog Channel** (10K subs)

**Solution**:
1. Add all 3 channels via different Google accounts
2. Set "Tech Reviews" as default (your main channel)
3. Sync metrics for all channels
4. View combined analytics or filter by channel
5. Publish videos to specific channels by switching default

### Use Case 2: Agency Managing Client Channels

**Scenario**: You're a video production agency managing 10 client YouTube channels.

**Solution**:
1. Each team member has an MSS account
2. Each client's YouTube channel is added via their Google account
3. Set one client channel as default for focused work
4. Switch between clients easily via Channel Manager
5. Track analytics per client channel

### Use Case 3: Personal & Business Channels

**Scenario**: You have a personal channel and a business channel.

**Solution**:
1. Connect both channels to MSS
2. Set business channel as default
3. Create and publish videos to business channel by default
4. Switch to personal channel when needed
5. Keep analytics separate for each

---

## Troubleshooting

### Issue: Same Channel Added Twice

**Cause**: You connected the same Google account twice.

**Solution**:
- Channels are deduplicated by `channel_id`
- If you connect the same account again, MSS will recognize it and not create a duplicate
- The `UNIQUE(user_email, platform, channel_id)` constraint prevents duplicates

### Issue: Can't Add Another Channel

**Symptoms**: Clicking "Add YouTube Channel" just re-adds the same channel.

**Cause**: You're signing in with the same Google account.

**Solution**:
1. Click "Add YouTube Channel"
2. When the Google sign-in page appears, click the account dropdown
3. Select "Use another account"
4. Sign in with a **different** Google account that owns a different YouTube channel

### Issue: Channel Not Appearing

**Check**:
1. Verify the Google account you signed in with actually owns a YouTube channel
2. Check browser console for errors (F12)
3. Check Flask server logs for `[YOUTUBE]` messages
4. Ensure OAuth credentials are properly configured

### Issue: Sync Only Works for One Channel

**Cause**: YouTube OAuth credentials are stored per Google account session.

**Explanation**:
- Each OAuth connection is tied to ONE Google account
- When you "Sync from YouTube", it syncs the channel for the currently authenticated Google account
- To sync a different channel, you need to reconnect with that channel's Google account

**Solution**:
- In future updates, we can store separate OAuth tokens per channel
- For now, reconnect with the desired channel's Google account before syncing

---

## Future Enhancements

### Planned Features

1. **Channel Selection in Sync UI**
   - Dropdown to select which channel to sync
   - Sync all channels at once button

2. **Per-Channel OAuth Tokens**
   - Store separate OAuth tokens for each channel
   - No need to re-authenticate when switching

3. **Channel-Specific Analytics Dashboard**
   - Filter analytics by channel
   - Compare performance across channels
   - Channel-specific best performers

4. **Scheduled Auto-Sync**
   - Automatically sync metrics for all channels hourly/daily
   - Background job to refresh tokens and update stats

5. **Channel Groups/Tags**
   - Organize channels into groups (e.g., "Client Channels", "Personal Channels")
   - Bulk operations on channel groups

6. **Channel Settings Per Upload**
   - Choose which channel to upload to when publishing
   - Remember last-used channel per video project

---

## Technical Notes

### OAuth Token Storage

Currently, OAuth tokens are stored in the `platform_connections` table:

```sql
CREATE TABLE platform_connections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_email TEXT NOT NULL,
    platform TEXT NOT NULL,
    credentials TEXT,
    access_token TEXT,
    refresh_token TEXT,
    connected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP,
    status TEXT DEFAULT 'active',
    UNIQUE(user_email, platform)
);
```

**Limitation**: One set of credentials per `(user_email, platform)` pair.

**Future**: Store per-channel credentials:
```sql
ALTER TABLE channel_accounts ADD COLUMN credentials TEXT;
```

### Channel Detection Logic

When a user connects via OAuth:

1. `handle_youtube_callback()` exchanges code for access token
2. Credentials are stored in `platform_connections`
3. On sync, `get_and_store_youtube_channel()` is called
4. It calls YouTube API: `channels().list(mine=True)`
5. The returned channel info is stored in `channel_accounts`
6. If channel already exists (by `channel_id`), it's updated, not duplicated

### Video Linking

Videos are linked to channels via `channel_account_id`:

```python
# When syncing
video_id = analytics_manager.track_video_creation(user_email, video_data)

# Link to channel
conn.execute('UPDATE videos SET channel_account_id = ? WHERE id = ?',
             (channel_account_id, video_id))
```

This allows queries like:

```sql
-- Get all videos for a specific channel
SELECT * FROM videos WHERE channel_account_id = 1;

-- Get analytics for a specific channel
SELECT SUM(views), SUM(likes) FROM videos v
JOIN video_metrics vm ON v.id = vm.video_id
WHERE v.channel_account_id = 2;
```

---

## Security Considerations

### OAuth Token Security

- OAuth tokens are stored in SQLite database
- Tokens have access to upload, read, and manage YouTube videos
- **Production**: Encrypt tokens using `cryptography.fernet`
- **Production**: Use environment variables for client secrets
- **Production**: Implement token refresh logic

### Channel Isolation

- Channels are isolated by `user_email`
- Users can only see/manage their own channels
- API endpoints verify session ownership before operations

### Soft Deletes

- Removing a channel sets `is_active = 0`
- Channel data is preserved (not hard deleted)
- Allows recovery and maintains referential integrity with videos

---

## Testing

### Manual Testing

1. **Add First Channel**:
   - Sign in with Google Account A
   - Verify channel appears in Channel Manager
   - Verify marked as default

2. **Add Second Channel**:
   - Sign in with Google Account B (different account)
   - Verify both channels appear
   - Verify first channel still default

3. **Change Default**:
   - Click "Set as Default" on second channel
   - Verify ⭐ badge moves to second channel

4. **Sync Metrics**:
   - Click "Sync from YouTube" in Analytics Dashboard
   - Verify videos from current authenticated channel are synced
   - Verify channel name appears in success message

5. **Remove Channel**:
   - Remove one channel
   - Verify it disappears from list
   - Verify videos remain in analytics

### Automated Testing

```python
import pytest
from web.analytics import AnalyticsManager

@pytest.fixture
def analytics():
    return AnalyticsManager(db_path=':memory:')

def test_add_channel(analytics):
    channel_id = analytics.add_channel_account('test@example.com', 'youtube', {
        'channel_id': 'UCtest123',
        'channel_name': 'Test Channel'
    })
    assert channel_id > 0

def test_default_channel(analytics):
    id1 = analytics.add_channel_account('test@example.com', 'youtube', {
        'channel_id': 'UCtest1',
        'channel_name': 'Channel 1'
    })

    id2 = analytics.add_channel_account('test@example.com', 'youtube', {
        'channel_id': 'UCtest2',
        'channel_name': 'Channel 2'
    })

    # First channel should be default
    default = analytics.get_default_channel('test@example.com')
    assert default['id'] == id1

    # Change default
    analytics.set_default_channel('test@example.com', id2)
    default = analytics.get_default_channel('test@example.com')
    assert default['id'] == id2
```

---

## FAQ

**Q: How many channels can I add?**
A: No limit. Add as many as you have Google accounts for.

**Q: Do I need separate MSS accounts for each channel?**
A: No. One MSS account can manage multiple YouTube channels.

**Q: Can I share a channel with multiple MSS users?**
A: Not directly. Each channel is tied to the Google account that authenticated it. Future versions may support team access.

**Q: What happens if I delete a Google account?**
A: The OAuth token will become invalid. You'll need to re-authenticate or remove the channel from MSS.

**Q: Can I add the same channel twice?**
A: No. Channels are deduplicated by `channel_id`. Attempting to add the same channel again will just update its info.

**Q: Does removing a channel delete my YouTube channel?**
A: No! It only removes the connection in MSS. Your YouTube channel and videos remain untouched.

**Q: How do I sync metrics for a specific channel?**
A: Currently, sync uses the authenticated Google account. Sign in with the desired channel's account, then click "Sync from YouTube". Future versions will allow selecting which channel to sync.

---

## Support

For issues or questions:
- Check Flask server logs for `[YOUTUBE]` and `[ANALYTICS]` messages
- Check browser console (F12) for JavaScript errors
- Verify OAuth credentials are properly configured (see `PLATFORM_API_SETUP_GUIDE.md`)
- Ensure `channel_accounts` table exists (auto-created on first run)

---

**Version:** 1.0.0
**Last Updated:** January 16, 2025
**Created by:** Claude Code AI Assistant
