"""
Trend Alerts and AI Content Calendar Module for MSS
Provides YouTube trend monitoring and intelligent content scheduling
"""

import json
import sqlite3
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import os

# YouTube trending topics data source (can be replaced with real API)
# For now, using mock data - integrate with YouTube Data API v3 later
MOCK_TRENDING_TOPICS = [
    {
        "topic": "AI Tools 2025",
        "views": "2.5M",
        "growth": "+125%",
        "niche": "technology",
        "difficulty": "medium",
        "keywords": ["AI", "automation", "ChatGPT", "productivity", "artificial intelligence"],
        "subtopics": ["Best AI Tools for Content Creation", "AI vs Human Workers", "Free AI Tools You Need"]
    },
    {
        "topic": "Side Hustles",
        "views": "1.8M",
        "growth": "+98%",
        "niche": "business",
        "difficulty": "low",
        "keywords": ["passive income", "make money online", "side business", "entrepreneur", "freelance"],
        "subtopics": ["Best Side Hustles for 2025", "How to Start with $0", "Side Hustles That Pay $1000/month"]
    },
    {
        "topic": "Travel Tips Europe",
        "views": "1.2M",
        "growth": "+76%",
        "niche": "travel",
        "difficulty": "medium",
        "keywords": ["Europe travel", "budget travel", "hidden gems", "backpacking", "travel guide"],
        "subtopics": ["Cheapest European Cities", "Europe Travel Mistakes", "Best Time to Visit Europe"]
    },
    {
        "topic": "Fitness Transformation",
        "views": "950K",
        "growth": "+65%",
        "niche": "health",
        "difficulty": "high",
        "keywords": ["weight loss", "gym routine", "fitness journey", "body transformation", "workout plan"],
        "subtopics": ["90-Day Transformation Challenge", "From Beginner to Athlete", "Home Workout Transformations"]
    },
    {
        "topic": "Cryptocurrency Updates",
        "views": "890K",
        "growth": "+54%",
        "niche": "finance",
        "difficulty": "high",
        "keywords": ["crypto", "Bitcoin", "blockchain", "investing", "cryptocurrency news"],
        "subtopics": ["Bitcoin Price Predictions 2025", "Best Crypto to Buy Now", "Crypto Regulation Changes"]
    },
    {
        "topic": "DIY Home Projects",
        "views": "780K",
        "growth": "+43%",
        "niche": "lifestyle",
        "difficulty": "low",
        "keywords": ["DIY", "home improvement", "crafts", "woodworking", "home decor"],
        "subtopics": ["Budget-Friendly Home Upgrades", "DIY Furniture Projects", "Easy Weekend DIY Projects"]
    },
    {
        "topic": "Gaming News",
        "views": "650K",
        "growth": "+38%",
        "niche": "gaming",
        "difficulty": "medium",
        "keywords": ["gaming", "video games", "esports", "game reviews", "new releases"],
        "subtopics": ["Upcoming Game Releases 2025", "Gaming Industry Trends", "Best Games of the Year"]
    },
    {
        "topic": "Productivity Hacks",
        "views": "580K",
        "growth": "+32%",
        "niche": "self-improvement",
        "difficulty": "low",
        "keywords": ["productivity", "time management", "efficiency", "work-life balance", "habits"],
        "subtopics": ["Morning Routines of Successful People", "Top Productivity Apps", "How to Focus Better"]
    },
]

class TrendCalendarManager:
    def __init__(self, db_path: str = None):
        # Auto-detect correct database path
        if db_path is None:
            import os
            # Try common locations
            possible_paths = [
                "mss_users.db",  # When running from web/ directory
                "web/mss_users.db",  # When running from project root
                os.path.join(os.path.dirname(__file__), "mss_users.db")  # Same dir as this file
            ]
            for path in possible_paths:
                if os.path.exists(path):
                    db_path = path
                    break
            else:
                # Default to same directory as this file
                db_path = os.path.join(os.path.dirname(__file__), "mss_users.db")

        self.db_path = db_path
        print(f"[TRENDS] Using database: {self.db_path}")
        self._init_tables()

    def _init_tables(self):
        """Initialize database tables for trends and calendar"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        # Trend alerts table
        c.execute('''
            CREATE TABLE IF NOT EXISTS trend_alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_email TEXT NOT NULL,
                topic TEXT NOT NULL,
                views TEXT,
                growth TEXT,
                niche TEXT,
                difficulty TEXT,
                detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                dismissed BOOLEAN DEFAULT 0,
                FOREIGN KEY (user_email) REFERENCES users(email)
            )
        ''')

        # Content calendar table
        c.execute('''
            CREATE TABLE IF NOT EXISTS content_calendar (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_email TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                scheduled_date DATE NOT NULL,
                scheduled_time TIME,
                topic TEXT,
                niche TEXT,
                status TEXT DEFAULT 'scheduled',
                ai_suggested BOOLEAN DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_email) REFERENCES users(email)
            )
        ''')

        # User preferences for trends/calendar
        c.execute('''
            CREATE TABLE IF NOT EXISTS user_preferences (
                user_email TEXT PRIMARY KEY,
                preferred_niches TEXT,
                posting_frequency INTEGER DEFAULT 3,
                best_posting_days TEXT DEFAULT 'Monday,Wednesday,Friday',
                best_posting_time TEXT DEFAULT '10:00',
                FOREIGN KEY (user_email) REFERENCES users(email)
            )
        ''')

        conn.commit()
        conn.close()

    def get_trending_topics(self, user_email: str, niche: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get trending topics from YouTube Trending API"""
        try:
            # Try to fetch real trending videos from YouTube
            trends = self._fetch_youtube_trending(user_email, niche)

            if trends:
                print(f"[TRENDS] Fetched {len(trends)} real trending topics from YouTube")
                return trends
            else:
                print("[TRENDS] YouTube API returned no results, using fallback mock data")
        except Exception as e:
            print(f"[TRENDS] Error fetching from YouTube API: {e}, using fallback mock data")

        # Fallback to mock data if YouTube API fails
        trends = MOCK_TRENDING_TOPICS.copy()

        # Filter by niche if specified
        if niche:
            trends = [t for t in trends if t['niche'] == niche.lower()]

        # Get user preferences
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('SELECT preferred_niches FROM user_preferences WHERE user_email = ?', (user_email,))
        result = c.fetchone()
        conn.close()

        if result and result[0]:
            preferred_niches = [n.strip().lower() for n in result[0].split(',')]
            # Prioritize preferred niches
            preferred = [t for t in trends if t['niche'] in preferred_niches]
            others = [t for t in trends if t['niche'] not in preferred_niches]
            trends = preferred + others

        # Sort by growth rate
        def extract_growth_percentage(trend):
            growth_str = trend.get('growth', '+0%')
            import re
            match = re.search(r'([+-]?\d+)', growth_str)
            return int(match.group(1)) if match else 0

        trends.sort(key=extract_growth_percentage, reverse=True)

        return trends

    def _fetch_youtube_trending(self, user_email: str, niche: Optional[str] = None) -> List[Dict[str, Any]]:
        """Fetch trending videos from YouTube Data API v3"""
        try:
            # Import YouTube API
            from googleapiclient.discovery import build
            from google.oauth2.credentials import Credentials
            import os

            # Get API key or credentials
            api_key = os.getenv('YOUTUBE_API_KEY')

            if not api_key:
                # Try to get user's YouTube credentials
                conn = sqlite3.connect(self.db_path)
                c = conn.cursor()
                c.execute('''
                    SELECT credentials FROM platform_connections
                    WHERE user_email = ? AND platform = 'youtube' AND status = 'active'
                    LIMIT 1
                ''', (user_email,))
                result = c.fetchone()
                conn.close()

                if not result:
                    print("[TRENDS] No YouTube API key or credentials found")
                    return []

                # Use user's OAuth credentials
                creds_data = json.loads(result[0])
                credentials = Credentials(
                    token=creds_data.get('token'),
                    refresh_token=creds_data.get('refresh_token'),
                    token_uri=creds_data.get('token_uri'),
                    client_id=creds_data.get('client_id'),
                    client_secret=creds_data.get('client_secret')
                )
                youtube = build('youtube', 'v3', credentials=credentials)
            else:
                # Use API key
                youtube = build('youtube', 'v3', developerKey=api_key)

            # Target categories we WANT - AI, science, technology, world issues, health, government
            # YouTube category IDs: https://developers.google.com/youtube/v3/docs/videoCategories/list
            target_categories = [
                '28',  # Science & Technology (includes AI, tech innovation, research)
                '22',  # People & Blogs (often has world issues, political commentary, AI discussions)
                '26',  # Howto & Style (includes health, fitness, wellness)
            ]

            # Fetch trending videos from ALL categories (no filter), then filter by target
            all_trends = []

            # Fetch trending from each target category
            for category_id in target_categories:
                try:
                    request = youtube.videos().list(
                        part='snippet,statistics',
                        chart='mostPopular',
                        regionCode='US',
                        maxResults=20,
                        videoCategoryId=category_id
                    )
                    response = request.execute()

                    for video in response.get('items', []):
                        all_trends.append(video)

                except Exception as e:
                    print(f"[TRENDS] Error fetching category {category_id}: {e}")
                    continue

            response = {'items': all_trends}

            # Process videos into trends format
            trends = []
            for video in response.get('items', []):
                snippet = video['snippet']

                # Only include English videos
                default_language = snippet.get('defaultLanguage', '')
                default_audio_language = snippet.get('defaultAudioLanguage', '')
                title = snippet.get('title', '')

                # Skip non-English content
                if default_language and default_language.lower() not in ['en', 'en-us', 'en-gb']:
                    continue
                if default_audio_language and default_audio_language.lower() not in ['en', 'en-us', 'en-gb']:
                    continue

                # Simple heuristic: skip if title contains mostly non-ASCII characters
                if title:
                    ascii_chars = sum(1 for c in title if ord(c) < 128)
                    if len(title) > 0 and ascii_chars / len(title) < 0.7:
                        continue

                # Filter out late night talk shows
                channel_title = snippet.get('channelTitle', '').lower()
                title_lower = title.lower()

                late_night_shows = [
                    'tonight show', 'late show', 'late night', 'jimmy fallon', 'stephen colbert',
                    'jimmy kimmel', 'james corden', 'seth meyers', 'conan', 'daily show',
                    'last week tonight', 'john oliver', 'saturday night live', 'snl'
                ]

                # Skip if title or channel matches late night shows
                if any(show in title_lower or show in channel_title for show in late_night_shows):
                    continue

                stats = video['statistics']

                views = int(stats.get('viewCount', 0))
                likes = int(stats.get('likeCount', 0))
                comments = int(stats.get('commentCount', 0))

                # Calculate engagement rate
                engagement_rate = ((likes + comments) / views * 100) if views > 0 else 0

                # Estimate growth (simplified - in production, compare with historical data)
                growth_estimate = f"+{int(engagement_rate * 10)}%"

                # Map category ID to niche name
                category_id = snippet.get('categoryId', '0')
                category_to_niche = {
                    '25': 'news-politics',
                    '28': 'technology',
                    '27': 'education',
                    '22': 'world-issues',
                    '26': 'health',
                }
                niche_name = category_to_niche.get(category_id, 'general')

                # Determine difficulty based on competition
                if views > 1000000:
                    difficulty = 'high'
                elif views > 100000:
                    difficulty = 'medium'
                else:
                    difficulty = 'low'

                # Extract keywords from title and description
                title = snippet['title']
                description = snippet.get('description', '')
                keywords = self._extract_keywords(title, description)

                # Generate subtopics based on title
                subtopics = self._generate_subtopics(title, keywords)

                trend = {
                    'topic': title,
                    'views': f"{views // 1000}K" if views < 1000000 else f"{views // 1000000}.{(views % 1000000) // 100000}M",
                    'growth': growth_estimate,
                    'niche': niche_name,
                    'difficulty': difficulty,
                    'keywords': keywords[:10],
                    'subtopics': subtopics,
                    'video_id': video['id'],
                    'channel_title': snippet.get('channelTitle', ''),
                    'published_at': snippet.get('publishedAt', '')
                }

                trends.append(trend)

                # Stop if we have enough trends
                if len(trends) >= 15:
                    break

            # If we got some trends but not many, that's OK - return what we have
            if len(trends) > 0:
                print(f"[TRENDS] Successfully fetched {len(trends)} trending topics (after filtering)")
                return trends

            # If we got zero trends, return empty list (will trigger fallback)
            print(f"[TRENDS] No videos passed category filter")
            return []

        except Exception as e:
            print(f"[TRENDS] Error in _fetch_youtube_trending: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _extract_keywords(self, title: str, description: str) -> List[str]:
        """Extract keywords from title and description"""
        import re

        # Combine title and description
        text = f"{title} {description}".lower()

        # Remove common words
        stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
                     'of', 'with', 'by', 'from', 'is', 'are', 'was', 'were', 'be', 'been',
                     'this', 'that', 'these', 'those', 'how', 'what', 'when', 'where', 'why'}

        # Extract words (alphanumeric sequences)
        words = re.findall(r'\b[a-z0-9]+\b', text)

        # Filter and count
        from collections import Counter
        word_counts = Counter([w for w in words if w not in stop_words and len(w) > 3])

        # Return top keywords
        return [word for word, count in word_counts.most_common(15)]

    def _generate_subtopics(self, title: str, keywords: List[str]) -> List[str]:
        """Generate relevant subtopics based on title and keywords"""
        # Simple subtopic generation - in production, use AI
        subtopics = []

        # Common question patterns
        if keywords:
            subtopics.append(f"How to {keywords[0] if keywords else 'get started'}")
            if len(keywords) > 1:
                subtopics.append(f"{keywords[1].title()} vs {keywords[0].title()}")
            if len(keywords) > 2:
                subtopics.append(f"Best {keywords[2]} for beginners")

        # Add title-based subtopic
        if len(title) < 50:
            subtopics.insert(0, f"{title}: Complete Guide")

        return subtopics[:3]

    def save_trend_alert(self, user_email: str, trend: Dict[str, Any]) -> int:
        """Save a trend alert for a user"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        c.execute('''
            INSERT INTO trend_alerts (user_email, topic, views, growth, niche, difficulty)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            user_email,
            trend['topic'],
            trend.get('views', ''),
            trend.get('growth', ''),
            trend.get('niche', ''),
            trend.get('difficulty', '')
        ))

        alert_id = c.lastrowid
        conn.commit()
        conn.close()

        return alert_id

    def get_user_alerts(self, user_email: str, include_dismissed: bool = False) -> List[Dict[str, Any]]:
        """Get all trend alerts for a user"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()

        query = '''
            SELECT * FROM trend_alerts
            WHERE user_email = ?
        '''

        if not include_dismissed:
            query += ' AND dismissed = 0'

        query += ' ORDER BY detected_at DESC LIMIT 20'

        c.execute(query, (user_email,))
        rows = c.fetchall()
        conn.close()

        return [dict(row) for row in rows]

    def dismiss_alert(self, alert_id: int, user_email: str) -> bool:
        """Dismiss a trend alert"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        c.execute('''
            UPDATE trend_alerts
            SET dismissed = 1
            WHERE id = ? AND user_email = ?
        ''', (alert_id, user_email))

        success = c.rowcount > 0
        conn.commit()
        conn.close()

        return success

    def generate_content_calendar(self, user_email: str, days_ahead: int = 30) -> List[Dict[str, Any]]:
        """Generate AI-powered content calendar suggestions"""
        # Get user preferences
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('''
            SELECT posting_frequency, best_posting_days, best_posting_time
            FROM user_preferences
            WHERE user_email = ?
        ''', (user_email,))

        result = c.fetchone()
        conn.close()

        if result:
            frequency, days_str, time_str = result
        else:
            frequency, days_str, time_str = 3, 'Monday,Wednesday,Friday', '10:00'

        # Parse preferred posting days
        preferred_days = [d.strip() for d in days_str.split(',')]
        day_map = {
            'Monday': 0, 'Tuesday': 1, 'Wednesday': 2,
            'Thursday': 3, 'Friday': 4, 'Saturday': 5, 'Sunday': 6
        }
        preferred_day_nums = [day_map[d] for d in preferred_days if d in day_map]

        # Generate suggestions
        suggestions = []
        today = datetime.now()
        trending = self.get_trending_topics(user_email)

        # Generate posts for next N days based on frequency
        posts_per_week = frequency
        current_date = today
        topic_index = 0

        for week in range(days_ahead // 7 + 1):
            posts_this_week = 0

            for day_offset in range(7):
                check_date = current_date + timedelta(days=week * 7 + day_offset)

                if (check_date - today).days >= days_ahead:
                    break

                # Check if this day is a preferred posting day
                if check_date.weekday() in preferred_day_nums and posts_this_week < posts_per_week:
                    if topic_index < len(trending):
                        topic = trending[topic_index]
                        suggestions.append({
                            'date': check_date.strftime('%Y-%m-%d'),
                            'time': time_str,
                            'title': f"Video about {topic['topic']}",
                            'topic': topic['topic'],
                            'niche': topic['niche'],
                            'reason': f"Trending with {topic['views']} views ({topic['growth']} growth)",
                            'difficulty': topic['difficulty'],
                            'ai_suggested': True
                        })
                        topic_index += 1
                        posts_this_week += 1

        return suggestions

    def save_calendar_entry(self, user_email: str, entry: Dict[str, Any]) -> int:
        """Save a content calendar entry"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        c.execute('''
            INSERT INTO content_calendar
            (user_email, title, description, scheduled_date, scheduled_time,
             topic, niche, status, ai_suggested)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            user_email,
            entry.get('title', ''),
            entry.get('description', ''),
            entry.get('date', ''),
            entry.get('time', '10:00'),
            entry.get('topic', ''),
            entry.get('niche', ''),
            entry.get('status', 'scheduled'),
            entry.get('ai_suggested', False)
        ))

        entry_id = c.lastrowid
        conn.commit()
        conn.close()

        return entry_id

    def get_calendar_entries(self, user_email: str, start_date: Optional[str] = None,
                           end_date: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get calendar entries for a user"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()

        query = 'SELECT * FROM content_calendar WHERE user_email = ?'
        params = [user_email]

        if start_date:
            query += ' AND scheduled_date >= ?'
            params.append(start_date)

        if end_date:
            query += ' AND scheduled_date <= ?'
            params.append(end_date)

        query += ' ORDER BY scheduled_date, scheduled_time'

        c.execute(query, params)
        rows = c.fetchall()
        conn.close()

        return [dict(row) for row in rows]

    def update_calendar_entry(self, entry_id: int, user_email: str, updates: Dict[str, Any]) -> bool:
        """Update a calendar entry"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        # Build update query dynamically
        allowed_fields = ['title', 'description', 'scheduled_date', 'scheduled_time', 'status']
        update_fields = []
        values = []

        for field in allowed_fields:
            if field in updates:
                update_fields.append(f'{field} = ?')
                values.append(updates[field])

        if not update_fields:
            conn.close()
            return False

        values.extend([entry_id, user_email])
        query = f'''
            UPDATE content_calendar
            SET {', '.join(update_fields)}
            WHERE id = ? AND user_email = ?
        '''

        c.execute(query, values)
        success = c.rowcount > 0
        conn.commit()
        conn.close()

        return success

    def delete_calendar_entry(self, entry_id: int, user_email: str) -> bool:
        """Delete a calendar entry"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        c.execute('DELETE FROM content_calendar WHERE id = ? AND user_email = ?',
                 (entry_id, user_email))

        success = c.rowcount > 0
        conn.commit()
        conn.close()

        return success

    def save_user_preferences(self, user_email: str, preferences: Dict[str, Any]) -> bool:
        """Save user preferences for trends and calendar"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        # Check if preferences exist
        c.execute('SELECT user_email FROM user_preferences WHERE user_email = ?', (user_email,))
        exists = c.fetchone() is not None

        if exists:
            # Update
            c.execute('''
                UPDATE user_preferences
                SET preferred_niches = ?, posting_frequency = ?,
                    best_posting_days = ?, best_posting_time = ?
                WHERE user_email = ?
            ''', (
                preferences.get('preferred_niches', ''),
                preferences.get('posting_frequency', 3),
                preferences.get('best_posting_days', 'Monday,Wednesday,Friday'),
                preferences.get('best_posting_time', '10:00'),
                user_email
            ))
        else:
            # Insert
            c.execute('''
                INSERT INTO user_preferences
                (user_email, preferred_niches, posting_frequency, best_posting_days, best_posting_time)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                user_email,
                preferences.get('preferred_niches', ''),
                preferences.get('posting_frequency', 3),
                preferences.get('best_posting_days', 'Monday,Wednesday,Friday'),
                preferences.get('best_posting_time', '10:00')
            ))

        conn.commit()
        conn.close()
        return True

    def get_user_preferences(self, user_email: str) -> Dict[str, Any]:
        """Get user preferences"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()

        c.execute('SELECT * FROM user_preferences WHERE user_email = ?', (user_email,))
        row = c.fetchone()
        conn.close()

        if row:
            return dict(row)
        else:
            # Return defaults
            return {
                'user_email': user_email,
                'preferred_niches': '',
                'posting_frequency': 3,
                'best_posting_days': 'Monday,Wednesday,Friday',
                'best_posting_time': '10:00'
            }
