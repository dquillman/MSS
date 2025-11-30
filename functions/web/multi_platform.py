"""
Multi-Platform Publisher Module for MSS
Handles publishing videos to YouTube, TikTok, Instagram Reels, and other platforms
Refactored to use Firestore (No SQLite)
"""

import json
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
import os
import subprocess
from pathlib import Path
from google.cloud import firestore
from web import firebase_db

logger = logging.getLogger(__name__)

class MultiPlatformPublisher:
    # Static presets (previously in DB)
    PLATFORM_PRESETS = [
        {'platform': 'youtube', 'max_duration_seconds': 43200, 'aspect_ratio': '16:9', 'max_file_size_mb': 256000, 'recommended_resolution': '1920x1080', 'description': 'Standard YouTube videos'},
        {'platform': 'youtube_shorts', 'max_duration_seconds': 60, 'aspect_ratio': '9:16', 'max_file_size_mb': 1000, 'recommended_resolution': '1080x1920', 'description': 'YouTube Shorts (vertical, max 60s)'},
        {'platform': 'tiktok', 'max_duration_seconds': 600, 'aspect_ratio': '9:16', 'max_file_size_mb': 500, 'recommended_resolution': '1080x1920', 'description': 'TikTok videos (vertical, max 10min)'},
        {'platform': 'instagram_reels', 'max_duration_seconds': 90, 'aspect_ratio': '9:16', 'max_file_size_mb': 1000, 'recommended_resolution': '1080x1920', 'description': 'Instagram Reels (vertical, max 90s)'},
        {'platform': 'instagram_feed', 'max_duration_seconds': 600, 'aspect_ratio': '1:1', 'max_file_size_mb': 1000, 'recommended_resolution': '1080x1080', 'description': 'Instagram Feed videos (square, max 10min)'},
        {'platform': 'facebook', 'max_duration_seconds': 14400, 'aspect_ratio': '16:9', 'max_file_size_mb': 10000, 'recommended_resolution': '1920x1080', 'description': 'Facebook videos (max 4 hours)'}
    ]

    def __init__(self, db_path: str = None):
        # db_path is ignored for Firestore
        self.db = firebase_db.get_db()
        logger.info("[MULTIPLATFORM] Initialized with Firestore")

    def _init_tables(self):
        # No-op for Firestore
        pass

    def get_platform_presets(self) -> List[Dict[str, Any]]:
        """Get all platform optimization presets"""
        return self.PLATFORM_PRESETS

    def get_preset_for_platform(self, platform: str) -> Optional[Dict[str, Any]]:
        """Get preset for a specific platform"""
        for preset in self.PLATFORM_PRESETS:
            if preset['platform'] == platform:
                return preset
        return None

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
                         scheduled_time: Optional[str] = None, thumbnail_path: Optional[str] = None) -> str:
        """Add video to publishing queue"""
        try:
            data = {
                'user_email': user_email,
                'video_filename': video_filename,
                'platforms': platforms, # Store as list directly
                'title': title,
                'description': description,
                'tags': tags or [],
                'scheduled_time': scheduled_time,
                'thumbnail_path': thumbnail_path,
                'status': 'pending',
                'created_at': firestore.SERVER_TIMESTAMP,
                'processed_at': None,
                'error_message': None
            }
            _, doc_ref = self.db.collection('publishing_queue').add(data)
            return doc_ref.id
        except Exception as e:
            logger.error(f"Error queuing publication: {e}")
            return ""

    def get_publishing_queue(self, user_email: str, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get publishing queue items for user"""
        try:
            query = (self.db.collection('publishing_queue')
                     .where('user_email', '==', user_email))
            
            if status:
                query = query.where('status', '==', status)
                
            query = query.order_by('created_at', direction=firestore.Query.DESCENDING).limit(50)
            
            docs = query.stream()
            items = []
            for doc in docs:
                d = doc.to_dict()
                d['id'] = doc.id
                # Convert timestamps
                for field in ['created_at', 'processed_at']:
                    if d.get(field):
                        d[field] = d[field].isoformat() if hasattr(d[field], 'isoformat') else str(d[field])
                items.append(d)
            return items
        except Exception as e:
            logger.error(f"Error getting publishing queue: {e}")
            return []

    def update_queue_status(self, queue_id: str, status: str, error_message: str = None) -> bool:
        """Update status of a queue item"""
        try:
            data = {
                'status': status,
                'processed_at': firestore.SERVER_TIMESTAMP
            }
            if error_message:
                data['error_message'] = error_message
                
            self.db.collection('publishing_queue').document(queue_id).update(data)
            return True
        except Exception as e:
            logger.error(f"Error updating queue status: {e}")
            return False

    def delete_queue_item(self, user_email: str, queue_id: str) -> bool:
        """Delete a queue item"""
        try:
            ref = self.db.collection('publishing_queue').document(queue_id)
            doc = ref.get()
            if not doc.exists:
                return False
            
            # Verify ownership
            if doc.to_dict().get('user_email') != user_email:
                return False
                
            ref.delete()
            return True
        except Exception as e:
            logger.error(f"Error deleting queue item: {e}")
            return False

    def clear_completed_queue(self, user_email: str) -> int:
        """Clear all completed, failed, and old pending queue items"""
        try:
            batch = self.db.batch()
            count = 0
            
            # 1. Completed or Failed
            docs = (self.db.collection('publishing_queue')
                    .where('user_email', '==', user_email)
                    .where('status', 'in', ['completed', 'failed'])
                    .stream())
            
            for doc in docs:
                batch.delete(doc.reference)
                count += 1
                
            # 2. Old pending (older than 24h)
            # Firestore doesn't support complex OR queries easily or date math in query
            # We'll fetch pending and check date in python
            pending_docs = (self.db.collection('publishing_queue')
                            .where('user_email', '==', user_email)
                            .where('status', '==', 'pending')
                            .stream())
                            
            cutoff = datetime.utcnow() - timedelta(days=1)
            # Make cutoff timezone-aware if needed, but Firestore timestamps are aware.
            # Assuming UTC for simplicity.
            
            for doc in pending_docs:
                created_at = doc.to_dict().get('created_at')
                if created_at:
                    # created_at is a datetime with timezone
                    if created_at.replace(tzinfo=None) < cutoff:
                         batch.delete(doc.reference)
                         count += 1
            
            batch.commit()
            return count
        except Exception as e:
            logger.error(f"Error clearing queue: {e}")
            return 0

    def record_publication(self, user_email: str, video_id: Optional[str], platform: str,
                          platform_video_id: str, platform_url: str,
                          title: str, description: str = '') -> str:
        """Record a successful publication"""
        try:
            data = {
                'user_email': user_email,
                'video_id': video_id,
                'platform': platform,
                'platform_video_id': platform_video_id,
                'platform_url': platform_url,
                'title': title,
                'description': description,
                'published_at': firestore.SERVER_TIMESTAMP,
                'status': 'published'
            }
            _, doc_ref = self.db.collection('published_videos').add(data)
            return doc_ref.id
        except Exception as e:
            logger.error(f"Error recording publication: {e}")
            return ""

    def get_published_videos(self, user_email: str, platform: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get published videos for user"""
        try:
            query = (self.db.collection('published_videos')
                     .where('user_email', '==', user_email))
            
            if platform:
                query = query.where('platform', '==', platform)
                
            query = query.order_by('published_at', direction=firestore.Query.DESCENDING).limit(100)
            
            docs = query.stream()
            items = []
            for doc in docs:
                d = doc.to_dict()
                d['id'] = doc.id
                if d.get('published_at'):
                    d['published_at'] = d['published_at'].isoformat() if hasattr(d['published_at'], 'isoformat') else str(d['published_at'])
                items.append(d)
            return items
        except Exception as e:
            logger.error(f"Error getting published videos: {e}")
            return []

    def connect_platform(self, user_email: str, platform: str, credentials: Dict[str, Any]) -> bool:
        """Store platform connection credentials"""
        try:
            # Check if exists
            docs = (self.db.collection('platform_connections')
                    .where('user_email', '==', user_email)
                    .where('platform', '==', platform)
                    .limit(1)
                    .stream())
            
            existing_ref = None
            for doc in docs:
                existing_ref = doc.reference
                break
            
            data = {
                'user_email': user_email,
                'platform': platform,
                'credentials': credentials, # Firestore can store dicts directly
                'access_token': credentials.get('access_token', ''),
                'refresh_token': credentials.get('refresh_token', ''),
                'connected_at': firestore.SERVER_TIMESTAMP,
                'status': 'active'
            }
            
            if existing_ref:
                existing_ref.update(data)
            else:
                self.db.collection('platform_connections').add(data)
                
            return True
        except Exception as e:
            logger.error(f"Error connecting platform: {e}")
            return False

    def get_connected_platforms(self, user_email: str) -> List[Dict[str, Any]]:
        """Get all connected platforms for user"""
        try:
            docs = (self.db.collection('platform_connections')
                    .where('user_email', '==', user_email)
                    .where('status', '==', 'active')
                    .stream())
            
            platforms = []
            for doc in docs:
                d = doc.to_dict()
                platforms.append({
                    'platform': d.get('platform'),
                    'status': d.get('status'),
                    'connected_at': d.get('connected_at').isoformat() if d.get('connected_at') else None
                })
            return platforms
        except Exception as e:
            logger.error(f"Error getting connected platforms: {e}")
            return []

