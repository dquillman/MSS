# Trends & Content Calendar Feature

## Overview

The Trends & Calendar feature brings AI-powered content intelligence to MSS, helping users discover trending topics and plan their content calendar strategically.

## Features

### 1. **Trend Alerts**
- Real-time trending topics across multiple niches
- View metrics: views, growth rate, difficulty level
- Filter by preferred niches
- Save trends for later reference
- Color-coded difficulty indicators

### 2. **AI Content Calendar**
- AI-generated posting schedule based on trends
- Personalized recommendations using user preferences
- 30-day content suggestions
- Optimal posting days and times
- Topic-to-date matching

### 3. **User Preferences**
- Set preferred content niches
- Configure posting frequency (posts per week)
- Choose best posting days
- Set optimal posting time
- Preferences persist and influence recommendations

## How It Works

### Backend Architecture

**Database Tables:**
- `trend_alerts` - Stores user's saved trend alerts
- `content_calendar` - Stores scheduled content entries
- `user_preferences` - Stores user content preferences

**API Endpoints:**
```
GET  /api/trends                    - Get trending topics
POST /api/trends/save               - Save a trend alert
GET  /api/trends/alerts             - Get user's saved alerts
POST /api/trends/dismiss/:id        - Dismiss an alert

GET  /api/calendar/generate         - Generate AI calendar
GET  /api/calendar                  - Get calendar entries
POST /api/calendar                  - Save calendar entry
PUT  /api/calendar/:id              - Update entry
DELETE /api/calendar/:id            - Delete entry

GET  /api/preferences               - Get user preferences
POST /api/preferences               - Save user preferences
```

### Frontend

**Page:** `/trends-calendar`
**Location:** `web/topic-picker-standalone/trends-calendar.html`

**Three Main Tabs:**
1. **Trending Topics** - Browse and save trending content ideas
2. **Content Calendar** - Generate and manage posting schedule
3. **Preferences** - Configure content preferences

## Usage Guide

### Step 1: Set Your Preferences
1. Navigate to Trends & Calendar from Dashboard
2. Click "Preferences" tab
3. Enter your preferred niches (e.g., "technology, business, gaming")
4. Set posting frequency (how many videos per week)
5. Choose best posting days (e.g., "Monday,Wednesday,Friday")
6. Set preferred posting time
7. Click "Save Preferences"

### Step 2: Explore Trending Topics
1. Click "Trending Topics" tab
2. Browse current trends with metrics
3. Click "Save Alert" on interesting topics
4. Topics are prioritized by your preferred niches

### Step 3: Generate Content Calendar
1. Click "Content Calendar" tab
2. Click "Generate Suggestions"
3. AI analyzes trending topics and your preferences
4. Generates 30-day posting schedule
5. Click "Add to Calendar" on suggestions you like

### Step 4: Create Content
1. Use suggested topics in the Studio
2. Follow the schedule for optimal posting
3. Track performance and adjust preferences

## Implementation Details

### Trend Data Source

Currently uses mock trending data. To integrate real YouTube Data API:

1. Get API key from Google Cloud Console
2. Enable YouTube Data API v3
3. Update `trend_calendar.py` to fetch real-time data:

```python
import googleapiclient.discovery

def fetch_youtube_trends(api_key, region='US'):
    youtube = googleapiclient.discovery.build('youtube', 'v3', developerKey=api_key)

    request = youtube.videos().list(
        part='snippet,statistics',
        chart='mostPopular',
        regionCode=region,
        maxResults=50
    )

    response = request.execute()
    # Process and return trending videos
```

### AI Calendar Algorithm

The calendar generator:
1. Fetches user preferences (frequency, days, time)
2. Gets trending topics filtered by user's niches
3. Maps topics to optimal posting dates
4. Considers:
   - Trend growth rate (faster = higher priority)
   - User's preferred posting days
   - Posting frequency limits
   - Topic difficulty vs. user skill level

### Customization Options

**Add More Niches:**
Edit `MOCK_TRENDING_TOPICS` in `web/trend_calendar.py`

**Change Calendar Logic:**
Modify `generate_content_calendar()` method

**Add Notification System:**
Implement email/push notifications for new trends

## Future Enhancements

### Phase 2 Features:
- [ ] YouTube Data API integration for real trends
- [ ] Email notifications for hot trends
- [ ] Export calendar to Google Calendar
- [ ] Auto-post scheduling (direct YouTube upload)
- [ ] Trend analytics dashboard
- [ ] Competitor tracking
- [ ] Viral content prediction
- [ ] Hashtag recommendations
- [ ] Best thumbnail suggestions from trends

### Phase 3 Features:
- [ ] Multi-platform support (TikTok, Instagram)
- [ ] Team collaboration on calendar
- [ ] Content performance tracking
- [ ] A/B testing for titles
- [ ] Automated content brief generation
- [ ] Voice alerts for breaking trends

## Technical Stack

- **Backend:** Python Flask
- **Database:** SQLite (expandable to PostgreSQL)
- **Frontend:** Vanilla JavaScript
- **Styling:** Custom CSS with dark theme
- **API:** RESTful JSON endpoints

## Files Changed/Created

```
web/trend_calendar.py              (NEW) - Backend logic
web/api_server.py                  (MODIFIED) - API endpoints
web/topic-picker-standalone/
  ├── trends-calendar.html         (NEW) - Frontend UI
  ├── dashboard.html               (MODIFIED) - Added nav link
web/mss_users.db                   (MODIFIED) - New tables
```

## Testing

1. Start Flask server: `python web/api_server.py`
2. Navigate to: `http://localhost:5000/trends-calendar`
3. Set preferences and generate calendar
4. Verify trends are displayed
5. Test saving/dismissing alerts
6. Check calendar entries are saved to DB

## Troubleshooting

**Trends not loading:**
- Check browser console for errors
- Verify user is logged in (session cookie)
- Check Flask server logs

**Calendar not generating:**
- Ensure preferences are saved first
- Check database tables exist
- Verify trend_manager is initialized

**API errors:**
- Check `_get_session()` function
- Verify database path is correct
- Ensure SQLite3 is installed

## Performance Considerations

- Trends cached in database (refresh manually)
- Calendar generation is lightweight (<1s)
- Database indexes on user_email for fast queries
- Future: Add Redis caching for trends

## Security

- All API endpoints require authentication
- User can only access their own data
- SQL injection protected (parameterized queries)
- XSS protection (no eval, sanitized inputs)

## License

Part of MSS (Many Sources Say) application
© 2025 - Internal use

---

**Version:** 1.0.0
**Created:** 2025-01-16
**Author:** Claude Code AI Assistant
