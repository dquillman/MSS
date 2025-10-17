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
    {"topic": "AI Tools 2025", "views": "2.5M", "growth": "+125%", "niche": "technology", "difficulty": "medium"},
    {"topic": "Side Hustles", "views": "1.8M", "growth": "+98%", "niche": "business", "difficulty": "low"},
    {"topic": "Travel Tips Europe", "views": "1.2M", "growth": "+76%", "niche": "travel", "difficulty": "medium"},
    {"topic": "Fitness Transformation", "views": "950K", "growth": "+65%", "niche": "health", "difficulty": "high"},
    {"topic": "Cryptocurrency Updates", "views": "890K", "growth": "+54%", "niche": "finance", "difficulty": "high"},
    {"topic": "DIY Home Projects", "views": "780K", "growth": "+43%", "niche": "lifestyle", "difficulty": "low"},
    {"topic": "Gaming News", "views": "650K", "growth": "+38%", "niche": "gaming", "difficulty": "medium"},
    {"topic": "Productivity Hacks", "views": "580K", "growth": "+32%", "niche": "self-improvement", "difficulty": "low"},
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
        """Get trending topics, optionally filtered by niche"""
        # In production, this would call YouTube Data API
        # For now, return mock data filtered by user preferences

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

        # Sort by growth rate (extract percentage and sort descending)
        def extract_growth_percentage(trend):
            growth_str = trend.get('growth', '+0%')
            # Extract number from string like "+125%"
            import re
            match = re.search(r'([+-]?\d+)', growth_str)
            return int(match.group(1)) if match else 0

        trends.sort(key=extract_growth_percentage, reverse=True)

        return trends

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
