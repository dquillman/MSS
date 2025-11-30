"""
Performance Analytics Module for MSS
Tracks video performance metrics and provides insights
Refactored to use Firestore (No SQLite)
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from google.cloud import firestore
from web import firebase_db

logger = logging.getLogger(__name__)

class AnalyticsManager:
    def __init__(self, db_path: str = None):
        # db_path is ignored for Firestore, kept for compatibility
        self.db = firebase_db.get_db()
        logger.info("[ANALYTICS] Initialized with Firestore")

    def _init_tables(self):
        # No-op for Firestore
        pass

    def track_video_creation(self, user_email: str, video_data: Dict[str, Any]) -> str:
        """Track when a video is created"""
        try:
            # Firestore add() returns (update_time, doc_ref)
            _, doc_ref = self.db.collection('videos').add({
                'user_email': user_email,
                'title': video_data.get('title', ''),
                'description': video_data.get('description', ''),
                'filename': video_data.get('filename', ''),
                'tags': video_data.get('tags', ''),
                'topic_data': video_data.get('topic_data', {}),
                'status': 'created',
                'created_at': firestore.SERVER_TIMESTAMP,
                'platform': 'youtube', # Default
                # Initialize metrics fields for easier querying
                'views': 0,
                'likes': 0,
                'comments': 0,
                'shares': 0,
                'engagement_rate': 0.0
            })
            return doc_ref.id
        except Exception as e:
            logger.error(f"Error tracking video creation: {e}")
            return ""

    def update_video_published(self, video_id: str, platform: str = 'youtube') -> bool:
        """Mark video as published"""
        try:
            self.db.collection('videos').document(video_id).update({
                'status': 'published',
                'published_at': firestore.SERVER_TIMESTAMP,
                'platform': platform
            })
            return True
        except Exception as e:
            logger.error(f"Error updating video published status: {e}")
            return False

    def record_video_metrics(self, video_id: str, metrics: Dict[str, Any], platform: str = 'youtube') -> str:
        """Record performance metrics for a video"""
        try:
            # Calculate engagement rate
            views = metrics.get('views', 0)
            likes = metrics.get('likes', 0)
            comments = metrics.get('comments', 0)
            shares = metrics.get('shares', 0)

            engagement_rate = 0
            if views > 0:
                engagement_rate = ((likes + comments + shares) / views) * 100

            metrics_data = {
                'video_id': video_id,
                'platform': platform,
                'views': views,
                'likes': likes,
                'comments': comments,
                'shares': shares,
                'watch_time_minutes': metrics.get('watch_time_minutes', 0),
                'ctr': metrics.get('ctr', 0),
                'avg_view_duration': metrics.get('avg_view_duration', 0),
                'engagement_rate': engagement_rate,
                'recorded_at': firestore.SERVER_TIMESTAMP
            }

            # 1. Add to history collection
            _, doc_ref = self.db.collection('videos').document(video_id).collection('metrics_history').add(metrics_data)

            # 2. Update latest metrics on the video document itself (Denormalization for Dashboard)
            self.db.collection('videos').document(video_id).update({
                'views': views,
                'likes': likes,
                'comments': comments,
                'shares': shares,
                'engagement_rate': engagement_rate,
                'latest_metrics_at': firestore.SERVER_TIMESTAMP
            })

            return doc_ref.id
        except Exception as e:
            logger.error(f"Error recording video metrics: {e}")
            return ""

    def get_user_videos(self, user_email: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Get all videos for a user with latest metrics"""
        try:
            docs = (self.db.collection('videos')
                    .where('user_email', '==', user_email)
                    .order_by('created_at', direction=firestore.Query.DESCENDING)
                    .limit(limit)
                    .stream())
            
            videos = []
            for doc in docs:
                d = doc.to_dict()
                d['id'] = doc.id
                # Handle timestamps
                for field in ['created_at', 'published_at', 'latest_metrics_at']:
                    if d.get(field):
                        d[field] = d[field].isoformat() if hasattr(d[field], 'isoformat') else str(d[field])
                videos.append(d)
            return videos
        except Exception as e:
            logger.error(f"Error getting user videos: {e}")
            return []

    def get_dashboard_stats(self, user_email: str, days: int = 30) -> Dict[str, Any]:
        """Get comprehensive dashboard statistics"""
        try:
            # Calculate start date
            start_date = datetime.utcnow() - timedelta(days=days)

            # Query videos created in the last X days
            # Note: Composite index might be needed for user_email + created_at
            docs = (self.db.collection('videos')
                    .where('user_email', '==', user_email)
                    .where('created_at', '>=', start_date)
                    .stream())

            total_videos = 0
            published_videos = 0
            total_views = 0
            total_likes = 0
            total_comments = 0
            total_shares = 0
            engagement_rates = []
            
            best_video = None
            max_views = -1
            
            # For timeline, we'll aggregate by day
            timeline_data = {} # "YYYY-MM-DD" -> views

            for doc in docs:
                d = doc.to_dict()
                total_videos += 1
                if d.get('status') == 'published':
                    published_videos += 1
                
                # Sum up metrics (stored on doc)
                v_views = d.get('views', 0)
                total_views += v_views
                total_likes += d.get('likes', 0)
                total_comments += d.get('comments', 0)
                total_shares += d.get('shares', 0)
                
                er = d.get('engagement_rate', 0)
                engagement_rates.append(er)

                # Best video check
                if v_views > max_views:
                    max_views = v_views
                    best_video = {
                        'title': d.get('title', 'Untitled'),
                        'views': v_views,
                        'engagement_rate': round(er, 2)
                    }

                # Timeline (approximate based on creation date or latest metrics?)
                # SQL version used `video_metrics` recorded_at.
                # Here we are iterating videos. 
                # To get true "views over time" we'd need to query the `metrics_history` subcollection for ALL videos, which is expensive.
                # Simplified approach: Just show current views distributed by creation date? No that's wrong.
                # Better approach: For the dashboard "Views over time" chart, we usually want daily aggregate views.
                # In Firestore, this is hard without a dedicated "daily_stats" collection.
                # For now, let's return an empty timeline or simplified one.
                # Let's just map the TOTAL views of the video to its creation date (not accurate but something).
                # OR: We can skip the timeline for now or implement a `daily_stats` collection later.
                # Let's return empty timeline to avoid errors, or maybe just the current snapshot.
                pass

            avg_er = sum(engagement_rates) / len(engagement_rates) if engagement_rates else 0

            return {
                'total_videos': total_videos,
                'published_videos': published_videos,
                'total_views': total_views,
                'total_likes': total_likes,
                'total_comments': total_comments,
                'total_shares': total_shares,
                'avg_engagement_rate': round(avg_er, 2),
                'best_video': best_video,
                'views_timeline': [], # TODO: Implement proper analytics aggregation
                'period_days': days
            }

        except Exception as e:
            logger.error(f"Error getting dashboard stats: {e}")
            return {
                'total_videos': 0, 'published_videos': 0, 'total_views': 0,
                'total_likes': 0, 'total_comments': 0, 'total_shares': 0,
                'avg_engagement_rate': 0, 'best_video': None, 'views_timeline': [],
                'period_days': days
            }

    def get_video_by_filename(self, user_email: str, filename: str) -> Optional[Dict[str, Any]]:
        """Get video by filename"""
        try:
            docs = (self.db.collection('videos')
                    .where('user_email', '==', user_email)
                    .where('filename', '==', filename)
                    .limit(1)
                    .stream())
            for doc in docs:
                d = doc.to_dict()
                d['id'] = doc.id
                return d
            return None
        except Exception as e:
            logger.error(f"Error getting video by filename: {e}")
            return None

    # ==================== CHANNEL ACCOUNT MANAGEMENT ====================

    def add_channel_account(self, user_email: str, platform: str, channel_data: Dict[str, Any]) -> str:
        """Add a new channel account"""
        try:
            # Check if exists
            existing = (self.db.collection('channel_accounts')
                        .where('user_email', '==', user_email)
                        .where('platform', '==', platform)
                        .where('channel_id', '==', channel_data.get('channel_id'))
                        .limit(1)
                        .stream())
            for doc in existing:
                return doc.id # Already exists

            # Check if first (to make default)
            count_query = (self.db.collection('channel_accounts')
                           .where('user_email', '==', user_email)
                           .where('platform', '==', platform)
                           .limit(1)
                           .stream())
            is_first = not any(count_query)

            data = {
                'user_email': user_email,
                'platform': platform,
                'channel_id': channel_data.get('channel_id'),
                'channel_name': channel_data.get('channel_name'),
                'channel_handle': channel_data.get('channel_handle'),
                'channel_custom_url': channel_data.get('channel_custom_url'),
                'channel_description': channel_data.get('channel_description'),
                'thumbnail_url': channel_data.get('thumbnail_url'),
                'is_active': True,
                'is_default': is_first,
                'added_at': firestore.SERVER_TIMESTAMP,
                'last_synced_at': None
            }
            _, doc_ref = self.db.collection('channel_accounts').add(data)
            return doc_ref.id
        except Exception as e:
            logger.error(f"Error adding channel account: {e}")
            return ""

    def get_user_channels(self, user_email: str, platform: str = 'youtube') -> List[Dict[str, Any]]:
        """Get all channel accounts for a user"""
        try:
            docs = (self.db.collection('channel_accounts')
                    .where('user_email', '==', user_email)
                    .where('platform', '==', platform)
                    .where('is_active', '==', True)
                    .stream())
            
            channels = []
            for doc in docs:
                d = doc.to_dict()
                d['id'] = doc.id
                channels.append(d)
            
            # Sort in python (default first)
            channels.sort(key=lambda x: (not x.get('is_default', False), x.get('channel_name', '')))
            return channels
        except Exception as e:
            logger.error(f"Error getting user channels: {e}")
            return []

    def get_default_channel(self, user_email: str, platform: str = 'youtube') -> Optional[Dict[str, Any]]:
        """Get the default channel account for a user"""
        try:
            docs = (self.db.collection('channel_accounts')
                    .where('user_email', '==', user_email)
                    .where('platform', '==', platform)
                    .where('is_default', '==', True)
                    .where('is_active', '==', True)
                    .limit(1)
                    .stream())
            for doc in docs:
                d = doc.to_dict()
                d['id'] = doc.id
                return d
            return None
        except Exception as e:
            logger.error(f"Error getting default channel: {e}")
            return None

    def set_default_channel(self, user_email: str, channel_account_id: str) -> bool:
        """Set a channel as the default"""
        try:
            batch = self.db.batch()
            
            # 1. Unset all defaults
            docs = (self.db.collection('channel_accounts')
                    .where('user_email', '==', user_email)
                    .where('is_default', '==', True)
                    .stream())
            for doc in docs:
                batch.update(doc.reference, {'is_default': False})
            
            # 2. Set new default
            ref = self.db.collection('channel_accounts').document(channel_account_id)
            batch.update(ref, {'is_default': True})
            
            batch.commit()
            return True
        except Exception as e:
            logger.error(f"Error setting default channel: {e}")
            return False

    def update_channel_sync_time(self, channel_account_id: str) -> bool:
        """Update the last_synced_at timestamp for a channel"""
        try:
            self.db.collection('channel_accounts').document(channel_account_id).update({
                'last_synced_at': firestore.SERVER_TIMESTAMP
            })
            return True
        except Exception as e:
            logger.error(f"Error updating channel sync time: {e}")
            return False

    def remove_channel_account(self, user_email: str, channel_account_id: str) -> bool:
        """Soft delete a channel account"""
        try:
            ref = self.db.collection('channel_accounts').document(channel_account_id)
            doc = ref.get()
            if not doc.exists:
                return False
            
            data = doc.to_dict()
            was_default = data.get('is_default')
            
            # Soft delete
            ref.update({'is_active': False, 'is_default': False})
            
            if was_default:
                # Make another channel default
                others = (self.db.collection('channel_accounts')
                          .where('user_email', '==', user_email)
                          .where('is_active', '==', True)
                          .limit(1)
                          .stream())
                for other in others:
                    other.reference.update({'is_default': True})
                    break
            return True
        except Exception as e:
            logger.error(f"Error removing channel account: {e}")
            return False

    def get_channel_by_id(self, channel_id: str, user_email: str, platform: str = 'youtube') -> Optional[Dict[str, Any]]:
        """Get channel account by YouTube channel ID"""
        try:
            docs = (self.db.collection('channel_accounts')
                    .where('channel_id', '==', channel_id)
                    .where('user_email', '==', user_email)
                    .where('platform', '==', platform)
                    .limit(1)
                    .stream())
            for doc in docs:
                d = doc.to_dict()
                d['id'] = doc.id
                return d
            return None
        except Exception as e:
            logger.error(f"Error getting channel by id: {e}")
            return None

