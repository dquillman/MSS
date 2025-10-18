"""
Performance Analytics Module for MSS
Tracks video performance metrics and provides insights
"""

import json
import sqlite3
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import os

class AnalyticsManager:
    def __init__(self, db_path: str = None):
        # Auto-detect correct database path
        if db_path is None:
            import os
            possible_paths = [
                "mss_users.db",
                "web/mss_users.db",
                os.path.join(os.path.dirname(__file__), "mss_users.db")
            ]
            for path in possible_paths:
                if os.path.exists(path):
                    db_path = path
                    break
            else:
                db_path = os.path.join(os.path.dirname(__file__), "mss_users.db")

        self.db_path = db_path
        print(f"[ANALYTICS] Using database: {self.db_path}")
        self._init_tables()

    def _init_tables(self):
        """Initialize database tables for analytics"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        # Videos table - stores all created videos
        c.execute('''
            CREATE TABLE IF NOT EXISTS videos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_email TEXT NOT NULL,
                title TEXT,
                description TEXT,
                filename TEXT,
                platform TEXT DEFAULT 'youtube',
                topic_data TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                published_at TIMESTAMP,
                status TEXT DEFAULT 'created',
                FOREIGN KEY (user_email) REFERENCES users(email)
            )
        ''')

        # Video metrics table - performance data
        c.execute('''
            CREATE TABLE IF NOT EXISTS video_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                video_id INTEGER NOT NULL,
                platform TEXT DEFAULT 'youtube',
                views INTEGER DEFAULT 0,
                likes INTEGER DEFAULT 0,
                comments INTEGER DEFAULT 0,
                shares INTEGER DEFAULT 0,
                watch_time_minutes REAL DEFAULT 0,
                ctr REAL DEFAULT 0,
                avg_view_duration REAL DEFAULT 0,
                engagement_rate REAL DEFAULT 0,
                recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (video_id) REFERENCES videos(id)
            )
        ''')

        # Channel stats table - overall channel performance
        c.execute('''
            CREATE TABLE IF NOT EXISTS channel_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_email TEXT NOT NULL,
                platform TEXT DEFAULT 'youtube',
                subscribers INTEGER DEFAULT 0,
                total_views INTEGER DEFAULT 0,
                total_videos INTEGER DEFAULT 0,
                total_watch_time REAL DEFAULT 0,
                estimated_revenue REAL DEFAULT 0,
                recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_email) REFERENCES users(email)
            )
        ''')

        # Channel accounts table - manage multiple YouTube channels per user
        c.execute('''
            CREATE TABLE IF NOT EXISTS channel_accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_email TEXT NOT NULL,
                platform TEXT DEFAULT 'youtube',
                channel_id TEXT,
                channel_name TEXT,
                channel_handle TEXT,
                channel_custom_url TEXT,
                channel_description TEXT,
                thumbnail_url TEXT,
                is_active BOOLEAN DEFAULT 1,
                is_default BOOLEAN DEFAULT 0,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_synced_at TIMESTAMP,
                FOREIGN KEY (user_email) REFERENCES users(email),
                UNIQUE(user_email, platform, channel_id)
            )
        ''')

        # Add channel_account_id to videos table if it doesn't exist
        try:
            c.execute('ALTER TABLE videos ADD COLUMN channel_account_id INTEGER')
        except sqlite3.OperationalError:
            # Column already exists
            pass

        # Add tags column to videos table if it doesn't exist
        try:
            c.execute('ALTER TABLE videos ADD COLUMN tags TEXT')
        except sqlite3.OperationalError:
            # Column already exists
            pass

        conn.commit()
        conn.close()

    def track_video_creation(self, user_email: str, video_data: Dict[str, Any]) -> int:
        """Track when a video is created"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        c.execute('''
            INSERT INTO videos (user_email, title, description, filename, tags, topic_data, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            user_email,
            video_data.get('title', ''),
            video_data.get('description', ''),
            video_data.get('filename', ''),
            video_data.get('tags', ''),
            json.dumps(video_data.get('topic_data', {})),
            'created'
        ))

        video_id = c.lastrowid
        conn.commit()
        conn.close()

        return video_id

    def update_video_published(self, video_id: int, platform: str = 'youtube') -> bool:
        """Mark video as published"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        c.execute('''
            UPDATE videos
            SET status = 'published', published_at = CURRENT_TIMESTAMP, platform = ?
            WHERE id = ?
        ''', (platform, video_id))

        success = c.rowcount > 0
        conn.commit()
        conn.close()

        return success

    def record_video_metrics(self, video_id: int, metrics: Dict[str, Any], platform: str = 'youtube') -> int:
        """Record performance metrics for a video"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        # Calculate engagement rate
        views = metrics.get('views', 0)
        likes = metrics.get('likes', 0)
        comments = metrics.get('comments', 0)
        shares = metrics.get('shares', 0)

        engagement_rate = 0
        if views > 0:
            engagement_rate = ((likes + comments + shares) / views) * 100

        c.execute('''
            INSERT INTO video_metrics
            (video_id, platform, views, likes, comments, shares,
             watch_time_minutes, ctr, avg_view_duration, engagement_rate)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            video_id,
            platform,
            metrics.get('views', 0),
            metrics.get('likes', 0),
            metrics.get('comments', 0),
            metrics.get('shares', 0),
            metrics.get('watch_time_minutes', 0),
            metrics.get('ctr', 0),
            metrics.get('avg_view_duration', 0),
            engagement_rate
        ))

        metric_id = c.lastrowid
        conn.commit()
        conn.close()

        return metric_id

    def get_user_videos(self, user_email: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Get all videos for a user with latest metrics"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()

        c.execute('''
            SELECT
                v.*,
                vm.views,
                vm.likes,
                vm.comments,
                vm.shares,
                vm.watch_time_minutes,
                vm.ctr,
                vm.avg_view_duration,
                vm.engagement_rate,
                vm.recorded_at as metrics_recorded_at
            FROM videos v
            LEFT JOIN video_metrics vm ON v.id = vm.video_id
                AND vm.id = (
                    SELECT id FROM video_metrics
                    WHERE video_id = v.id
                    ORDER BY recorded_at DESC
                    LIMIT 1
                )
            WHERE v.user_email = ?
            ORDER BY v.created_at DESC
            LIMIT ?
        ''', (user_email, limit))

        rows = c.fetchall()
        conn.close()

        return [dict(row) for row in rows]

    def get_dashboard_stats(self, user_email: str, days: int = 30) -> Dict[str, Any]:
        """Get comprehensive dashboard statistics"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        # Date range
        start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')

        # Total videos created
        c.execute('''
            SELECT COUNT(*) FROM videos
            WHERE user_email = ? AND created_at >= ?
        ''', (user_email, start_date))
        total_videos = c.fetchone()[0]

        # Published videos
        c.execute('''
            SELECT COUNT(*) FROM videos
            WHERE user_email = ? AND status = 'published' AND published_at >= ?
        ''', (user_email, start_date))
        published_videos = c.fetchone()[0]

        # Total views (latest metrics per video)
        c.execute('''
            SELECT COALESCE(SUM(vm.views), 0)
            FROM videos v
            LEFT JOIN (
                SELECT video_id, views,
                       ROW_NUMBER() OVER (PARTITION BY video_id ORDER BY recorded_at DESC) as rn
                FROM video_metrics
            ) vm ON v.id = vm.video_id AND vm.rn = 1
            WHERE v.user_email = ? AND v.created_at >= ?
        ''', (user_email, start_date))
        total_views = c.fetchone()[0]

        # Total engagement
        c.execute('''
            SELECT
                COALESCE(SUM(vm.likes), 0) as total_likes,
                COALESCE(SUM(vm.comments), 0) as total_comments,
                COALESCE(SUM(vm.shares), 0) as total_shares
            FROM videos v
            LEFT JOIN (
                SELECT video_id, likes, comments, shares,
                       ROW_NUMBER() OVER (PARTITION BY video_id ORDER BY recorded_at DESC) as rn
                FROM video_metrics
            ) vm ON v.id = vm.video_id AND vm.rn = 1
            WHERE v.user_email = ? AND v.created_at >= ?
        ''', (user_email, start_date))
        engagement = c.fetchone()
        total_likes = engagement[0] if engagement else 0
        total_comments = engagement[1] if engagement else 0
        total_shares = engagement[2] if engagement else 0

        # Average engagement rate
        c.execute('''
            SELECT COALESCE(AVG(vm.engagement_rate), 0)
            FROM videos v
            LEFT JOIN (
                SELECT video_id, engagement_rate,
                       ROW_NUMBER() OVER (PARTITION BY video_id ORDER BY recorded_at DESC) as rn
                FROM video_metrics
            ) vm ON v.id = vm.video_id AND vm.rn = 1
            WHERE v.user_email = ? AND v.created_at >= ?
        ''', (user_email, start_date))
        avg_engagement_rate = c.fetchone()[0]

        # Best performing video
        c.execute('''
            SELECT v.title, vm.views, vm.engagement_rate
            FROM videos v
            LEFT JOIN (
                SELECT video_id, views, engagement_rate,
                       ROW_NUMBER() OVER (PARTITION BY video_id ORDER BY recorded_at DESC) as rn
                FROM video_metrics
            ) vm ON v.id = vm.video_id AND vm.rn = 1
            WHERE v.user_email = ? AND v.created_at >= ?
            ORDER BY vm.views DESC
            LIMIT 1
        ''', (user_email, start_date))
        best_video = c.fetchone()

        # Views over time (last 7 days)
        c.execute('''
            SELECT DATE(vm.recorded_at) as date, SUM(vm.views) as views
            FROM videos v
            JOIN video_metrics vm ON v.id = vm.video_id
            WHERE v.user_email = ? AND vm.recorded_at >= DATE('now', '-7 days')
            GROUP BY DATE(vm.recorded_at)
            ORDER BY date
        ''', (user_email,))
        views_timeline = [{'date': row[0], 'views': row[1]} for row in c.fetchall()]

        conn.close()

        return {
            'total_videos': total_videos,
            'published_videos': published_videos,
            'total_views': total_views,
            'total_likes': total_likes,
            'total_comments': total_comments,
            'total_shares': total_shares,
            'avg_engagement_rate': round(avg_engagement_rate, 2),
            'best_video': {
                'title': best_video[0] if best_video else 'N/A',
                'views': best_video[1] if best_video else 0,
                'engagement_rate': round(best_video[2], 2) if best_video and best_video[2] else 0
            } if best_video else None,
            'views_timeline': views_timeline,
            'period_days': days
        }

    def get_video_by_filename(self, user_email: str, filename: str) -> Optional[Dict[str, Any]]:
        """Get video by filename"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()

        c.execute('''
            SELECT * FROM videos
            WHERE user_email = ? AND filename = ?
            LIMIT 1
        ''', (user_email, filename))

        row = c.fetchone()
        conn.close()

        return dict(row) if row else None

    # ==================== CHANNEL ACCOUNT MANAGEMENT ====================

    def add_channel_account(self, user_email: str, platform: str, channel_data: Dict[str, Any]) -> int:
        """Add a new channel account"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        # Check if this is the first channel for this user/platform
        c.execute('''
            SELECT COUNT(*) FROM channel_accounts
            WHERE user_email = ? AND platform = ?
        ''', (user_email, platform))
        is_first = c.fetchone()[0] == 0

        c.execute('''
            INSERT INTO channel_accounts
            (user_email, platform, channel_id, channel_name, channel_handle,
             channel_custom_url, channel_description, thumbnail_url, is_default)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            user_email,
            platform,
            channel_data.get('channel_id'),
            channel_data.get('channel_name'),
            channel_data.get('channel_handle'),
            channel_data.get('channel_custom_url'),
            channel_data.get('channel_description'),
            channel_data.get('thumbnail_url'),
            1 if is_first else 0  # First channel becomes default
        ))

        channel_account_id = c.lastrowid
        conn.commit()
        conn.close()

        return channel_account_id

    def get_user_channels(self, user_email: str, platform: str = 'youtube') -> List[Dict[str, Any]]:
        """Get all channel accounts for a user"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()

        c.execute('''
            SELECT * FROM channel_accounts
            WHERE user_email = ? AND platform = ? AND is_active = 1
            ORDER BY is_default DESC, channel_name
        ''', (user_email, platform))

        rows = c.fetchall()
        conn.close()

        return [dict(row) for row in rows]

    def get_default_channel(self, user_email: str, platform: str = 'youtube') -> Optional[Dict[str, Any]]:
        """Get the default channel account for a user"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()

        c.execute('''
            SELECT * FROM channel_accounts
            WHERE user_email = ? AND platform = ? AND is_default = 1 AND is_active = 1
            LIMIT 1
        ''', (user_email, platform))

        row = c.fetchone()
        conn.close()

        return dict(row) if row else None

    def set_default_channel(self, user_email: str, channel_account_id: int) -> bool:
        """Set a channel as the default"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        # First, unset all defaults for this user
        c.execute('''
            UPDATE channel_accounts
            SET is_default = 0
            WHERE user_email = ?
        ''', (user_email,))

        # Set the specified channel as default
        c.execute('''
            UPDATE channel_accounts
            SET is_default = 1
            WHERE id = ? AND user_email = ?
        ''', (channel_account_id, user_email))

        success = c.rowcount > 0
        conn.commit()
        conn.close()

        return success

    def update_channel_sync_time(self, channel_account_id: int) -> bool:
        """Update the last_synced_at timestamp for a channel"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        c.execute('''
            UPDATE channel_accounts
            SET last_synced_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (channel_account_id,))

        success = c.rowcount > 0
        conn.commit()
        conn.close()

        return success

    def remove_channel_account(self, user_email: str, channel_account_id: int) -> bool:
        """Soft delete a channel account"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        # Check if this is the default channel
        c.execute('''
            SELECT is_default FROM channel_accounts
            WHERE id = ? AND user_email = ?
        ''', (channel_account_id, user_email))
        row = c.fetchone()

        if not row:
            conn.close()
            return False

        was_default = row[0]

        # Soft delete the channel
        c.execute('''
            UPDATE channel_accounts
            SET is_active = 0, is_default = 0
            WHERE id = ? AND user_email = ?
        ''', (channel_account_id, user_email))

        # If this was the default, make another channel default
        if was_default:
            # Find the oldest active channel to make default
            c.execute('''
                SELECT id FROM channel_accounts
                WHERE user_email = ? AND is_active = 1
                ORDER BY added_at
                LIMIT 1
            ''', (user_email,))
            next_channel = c.fetchone()

            if next_channel:
                c.execute('''
                    UPDATE channel_accounts
                    SET is_default = 1
                    WHERE id = ?
                ''', (next_channel[0],))

        conn.commit()
        conn.close()

        return True

    def get_channel_by_id(self, channel_id: str, user_email: str, platform: str = 'youtube') -> Optional[Dict[str, Any]]:
        """Get channel account by YouTube channel ID"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()

        c.execute('''
            SELECT * FROM channel_accounts
            WHERE channel_id = ? AND user_email = ? AND platform = ?
            LIMIT 1
        ''', (channel_id, user_email, platform))

        row = c.fetchone()
        conn.close()

        return dict(row) if row else None
