"""
Multi-Platform Publisher Module for MSS
Handles publishing videos to YouTube, TikTok, Instagram Reels, and other platforms
"""

import json
import sqlite3
from datetime import datetime
from typing import List, Dict, Any, Optional
import os
import subprocess
from pathlib import Path

class MultiPlatformPublisher:
    def __init__(self, db_path: str = None):
        # Auto-detect correct database path
        if db_path is None:
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
        print(f"[MULTIPLATFORM] Using database: {self.db_path}")
        self._init_tables()

    def _init_tables(self):
        """Initialize database tables for multi-platform publishing"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        # Platform connections table
        c.execute('''
            CREATE TABLE IF NOT EXISTS platform_connections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_email TEXT NOT NULL,
                platform TEXT NOT NULL,
                credentials TEXT,
                access_token TEXT,
                refresh_token TEXT,
                connected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP,
                status TEXT DEFAULT 'active',
                FOREIGN KEY (user_email) REFERENCES users(email),
                UNIQUE(user_email, platform)
            )
        ''')

        # Published videos table - tracks cross-platform publications
        c.execute('''
            CREATE TABLE IF NOT EXISTS published_videos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_email TEXT NOT NULL,
                video_id INTEGER,
                platform TEXT NOT NULL,
                platform_video_id TEXT,
                platform_url TEXT,
                title TEXT,
                description TEXT,
                published_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status TEXT DEFAULT 'published',
                FOREIGN KEY (user_email) REFERENCES users(email),
                FOREIGN KEY (video_id) REFERENCES videos(id)
            )
        ''')

        # Publishing queue table
        c.execute('''
            CREATE TABLE IF NOT EXISTS publishing_queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_email TEXT NOT NULL,
                video_filename TEXT NOT NULL,
                platforms TEXT NOT NULL,
                title TEXT,
                description TEXT,
                tags TEXT,
                scheduled_time TIMESTAMP,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                processed_at TIMESTAMP,
                error_message TEXT,
                FOREIGN KEY (user_email) REFERENCES users(email)
            )
        ''')

        # Platform optimization presets
        c.execute('''
            CREATE TABLE IF NOT EXISTS platform_presets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                platform TEXT NOT NULL UNIQUE,
                max_duration_seconds INTEGER,
                aspect_ratio TEXT,
                max_file_size_mb INTEGER,
                recommended_resolution TEXT,
                description TEXT
            )
        ''')

        # Insert default platform presets
        presets = [
            ('youtube', 43200, '16:9', 256000, '1920x1080', 'Standard YouTube videos'),
            ('youtube_shorts', 60, '9:16', 1000, '1080x1920', 'YouTube Shorts (vertical, max 60s)'),
            ('tiktok', 600, '9:16', 500, '1080x1920', 'TikTok videos (vertical, max 10min)'),
            ('instagram_reels', 90, '9:16', 1000, '1080x1920', 'Instagram Reels (vertical, max 90s)'),
            ('instagram_feed', 600, '1:1', 1000, '1080x1080', 'Instagram Feed videos (square, max 10min)'),
            ('facebook', 14400, '16:9', 10000, '1920x1080', 'Facebook videos (max 4 hours)')
        ]

        for platform, duration, aspect, size, resolution, desc in presets:
            c.execute('''
                INSERT OR IGNORE INTO platform_presets
                (platform, max_duration_seconds, aspect_ratio, max_file_size_mb, recommended_resolution, description)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (platform, duration, aspect, size, resolution, desc))

        conn.commit()
        conn.close()

    def get_platform_presets(self) -> List[Dict[str, Any]]:
        """Get all platform optimization presets"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()

        c.execute('SELECT * FROM platform_presets ORDER BY platform')
        rows = c.fetchall()
        conn.close()

        return [dict(row) for row in rows]

    def get_preset_for_platform(self, platform: str) -> Optional[Dict[str, Any]]:
        """Get preset for a specific platform"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()

        c.execute('SELECT * FROM platform_presets WHERE platform = ?', (platform,))
        row = c.fetchone()
        conn.close()

        return dict(row) if row else None

    def optimize_video_for_platform(self, input_path: str, platform: str, output_path: str = None) -> Dict[str, Any]:
        """
        Optimize video for specific platform requirements
        Returns dict with success status and output path
        """
        preset = self.get_preset_for_platform(platform)
        if not preset:
            return {'success': False, 'error': f'No preset found for platform: {platform}'}

        if not os.path.exists(input_path):
            return {'success': False, 'error': f'Input file not found: {input_path}'}

        # Generate output path if not provided
        if not output_path:
            base_dir = os.path.dirname(input_path)
            base_name = os.path.splitext(os.path.basename(input_path))[0]
            output_path = os.path.join(base_dir, f"{base_name}_{platform}.mp4")

        # Build FFmpeg command based on preset
        aspect_ratio = preset['aspect_ratio']
        resolution = preset['recommended_resolution']

        try:
            # Parse resolution
            width, height = map(int, resolution.split('x'))

            # Build FFmpeg command
            cmd = [
                'ffmpeg',
                '-i', input_path,
                '-vf', f'scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1',
                '-c:v', 'libx264',
                '-preset', 'medium',
                '-crf', '23',
                '-c:a', 'aac',
                '-b:a', '128k',
                '-movflags', '+faststart',
                '-y',  # Overwrite output
                output_path
            ]

            # Run FFmpeg
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

            if result.returncode != 0:
                return {
                    'success': False,
                    'error': f'FFmpeg error: {result.stderr[:500]}'
                }

            return {
                'success': True,
                'output_path': output_path,
                'platform': platform,
                'preset': preset
            }

        except Exception as e:
            return {
                'success': False,
                'error': f'Optimization failed: {str(e)}'
            }

    def queue_publication(self, user_email: str, video_filename: str, platforms: List[str],
                         title: str, description: str = '', tags: List[str] = None,
                         scheduled_time: Optional[str] = None) -> int:
        """Add video to publishing queue"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        c.execute('''
            INSERT INTO publishing_queue
            (user_email, video_filename, platforms, title, description, tags, scheduled_time)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            user_email,
            video_filename,
            json.dumps(platforms),
            title,
            description,
            json.dumps(tags or []),
            scheduled_time
        ))

        queue_id = c.lastrowid
        conn.commit()
        conn.close()

        return queue_id

    def get_publishing_queue(self, user_email: str, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get publishing queue items for user"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()

        query = 'SELECT * FROM publishing_queue WHERE user_email = ?'
        params = [user_email]

        if status:
            query += ' AND status = ?'
            params.append(status)

        query += ' ORDER BY created_at DESC LIMIT 50'

        c.execute(query, params)
        rows = c.fetchall()
        conn.close()

        return [dict(row) for row in rows]

    def update_queue_status(self, queue_id: int, status: str, error_message: str = None) -> bool:
        """Update status of a queue item"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        if error_message:
            c.execute('''
                UPDATE publishing_queue
                SET status = ?, processed_at = CURRENT_TIMESTAMP, error_message = ?
                WHERE id = ?
            ''', (status, error_message, queue_id))
        else:
            c.execute('''
                UPDATE publishing_queue
                SET status = ?, processed_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (status, queue_id))

        success = c.rowcount > 0
        conn.commit()
        conn.close()

        return success

    def delete_queue_item(self, user_email: str, queue_id: int) -> bool:
        """Delete a queue item"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        c.execute('''
            DELETE FROM publishing_queue
            WHERE id = ? AND user_email = ?
        ''', (queue_id, user_email))

        success = c.rowcount > 0
        conn.commit()
        conn.close()

        return success

    def clear_completed_queue(self, user_email: str) -> int:
        """Clear all completed, failed, and old pending queue items"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        # Delete completed and failed items, and pending items older than 24 hours
        c.execute('''
            DELETE FROM publishing_queue
            WHERE user_email = ? AND (
                status IN ('completed', 'failed') OR
                (status = 'pending' AND datetime(created_at) < datetime('now', '-1 day'))
            )
        ''', (user_email,))

        deleted = c.rowcount
        conn.commit()
        conn.close()

        return deleted

    def record_publication(self, user_email: str, video_id: Optional[int], platform: str,
                          platform_video_id: str, platform_url: str,
                          title: str, description: str = '') -> int:
        """Record a successful publication"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        c.execute('''
            INSERT INTO published_videos
            (user_email, video_id, platform, platform_video_id, platform_url, title, description)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            user_email,
            video_id,
            platform,
            platform_video_id,
            platform_url,
            title,
            description
        ))

        pub_id = c.lastrowid
        conn.commit()
        conn.close()

        return pub_id

    def get_published_videos(self, user_email: str, platform: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get published videos for user"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()

        query = 'SELECT * FROM published_videos WHERE user_email = ?'
        params = [user_email]

        if platform:
            query += ' AND platform = ?'
            params.append(platform)

        query += ' ORDER BY published_at DESC LIMIT 100'

        c.execute(query, params)
        rows = c.fetchall()
        conn.close()

        return [dict(row) for row in rows]

    def connect_platform(self, user_email: str, platform: str, credentials: Dict[str, Any]) -> bool:
        """Store platform connection credentials"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        # Check if connection exists
        c.execute('''
            SELECT id FROM platform_connections
            WHERE user_email = ? AND platform = ?
        ''', (user_email, platform))

        exists = c.fetchone()

        if exists:
            # Update existing connection
            c.execute('''
                UPDATE platform_connections
                SET credentials = ?, access_token = ?, refresh_token = ?,
                    connected_at = CURRENT_TIMESTAMP, status = 'active'
                WHERE user_email = ? AND platform = ?
            ''', (
                json.dumps(credentials),
                credentials.get('access_token', ''),
                credentials.get('refresh_token', ''),
                user_email,
                platform
            ))
        else:
            # Insert new connection
            c.execute('''
                INSERT INTO platform_connections
                (user_email, platform, credentials, access_token, refresh_token)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                user_email,
                platform,
                json.dumps(credentials),
                credentials.get('access_token', ''),
                credentials.get('refresh_token', '')
            ))

        conn.commit()
        conn.close()
        return True

    def get_connected_platforms(self, user_email: str) -> List[Dict[str, Any]]:
        """Get all connected platforms for user"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()

        c.execute('''
            SELECT platform, status, connected_at
            FROM platform_connections
            WHERE user_email = ? AND status = 'active'
        ''', (user_email,))

        rows = c.fetchall()
        conn.close()

        return [dict(row) for row in rows]
