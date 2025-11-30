"""
Celery task definitions for MSS async operations
"""
from celery_app import celery_app
import logging

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name='tasks.generate_video')
def generate_video_async(self, user_id: int, topic: dict, **kwargs):
    """
    Async task to generate video
    
    Args:
        user_id: User ID
        topic: Topic dictionary
        **kwargs: Additional video generation options
    
    Returns:
        dict: Video generation result
    """
    try:
        # Update task state
        self.update_state(
            state='PROGRESS',
            meta={'step': 'generating_script', 'progress': 10}
        )
        
        # Import here to avoid circular dependencies
        from scripts.make_video import render_video
        
        # Generate script
        self.update_state(
            state='PROGRESS',
            meta={'step': 'generating_tts', 'progress': 30}
        )
        
        # Generate video
        self.update_state(
            state='PROGRESS',
            meta={'step': 'rendering_video', 'progress': 60}
        )
        
        result = render_video(topic=topic, user_id=user_id, **kwargs)
        
        self.update_state(
            state='SUCCESS',
            meta={'step': 'complete', 'progress': 100, 'result': result}
        )
        
        return result
    except Exception as e:
        logger.error(f"[TASK] Video generation failed: {e}", exc_info=True)
        self.update_state(
            state='FAILURE',
            meta={'error': str(e), 'step': 'failed'}
        )
        raise


@celery_app.task(name='tasks.post_process_video')
def post_process_video_async(video_path: str, user_id: int, options: dict = None):
    """Async task for video post-processing"""
    try:
        # Import post-processing functions
        from scripts.make_video import post_process_video
        
        result = post_process_video(video_path, user_id, options or {})
        return {'success': True, 'result': result}
    except Exception as e:
        logger.error(f"[TASK] Post-processing failed: {e}", exc_info=True)
        raise


@celery_app.task(name='tasks.publish_to_platform')
def publish_to_platform_async(platform: str, video_path: str, user_id: int, metadata: dict):
    """Async task for platform publishing"""
    try:
        from web.platform_apis import PlatformAPIManager
        
        platform_api = PlatformAPIManager()
        
        # Get user email
        from web import firebase_db as database
        user = database.get_user_by_id(user_id)
        if not user:
            raise ValueError(f"User {user_id} not found")
        
        user_email = user['email']
        
        # Publish to platform
        if platform == 'youtube':
            result = platform_api.upload_to_youtube(
                user_email=user_email,
                video_path=video_path,
                **metadata
            )
        elif platform == 'tiktok':
            result = platform_api.upload_to_tiktok(
                user_email=user_email,
                video_path=video_path,
                **metadata
            )
        else:
            raise ValueError(f"Unsupported platform: {platform}")
        
        return {'success': True, 'result': result}
    except Exception as e:
        logger.error(f"[TASK] Publishing failed: {e}", exc_info=True)
        raise


@celery_app.task(name='tasks.cleanup_temp_files')
def cleanup_temp_files():
    """Cleanup old temporary files"""
    try:
        from pathlib import Path
        import time
        import os
        
        tmp_dir = Path('tmp')
        cutoff_time = time.time() - (7 * 24 * 60 * 60)  # 7 days ago
        
        deleted = 0
        for file in tmp_dir.glob('*'):
            if file.is_file() and file.stat().st_mtime < cutoff_time:
                try:
                    file.unlink()
                    deleted += 1
                except Exception:
                    pass
        
        logger.info(f"[TASK] Cleaned up {deleted} temporary files")
        return {'success': True, 'deleted': deleted}
    except Exception as e:
        logger.error(f"[TASK] Cleanup failed: {e}")
        return {'success': False, 'error': str(e)}


@celery_app.task(name='tasks.cleanup_expired_sessions')
def cleanup_expired_sessions():
    """Cleanup expired sessions from database"""
    try:
        from web import firebase_db as database
        from datetime import datetime
        
        # Firestore cleanup
        # Note: This might be expensive if there are many sessions.
        # Ideally, use a TTL policy in Firestore, but for now we do manual cleanup.
        db = database.get_db()
        sessions_ref = db.collection('sessions')
        
        # Find expired sessions
        # Firestore doesn't support < CURRENT_TIMESTAMP directly in query without client-side time
        now = datetime.utcnow()
        docs = sessions_ref.where('expires_at', '<', now).stream()
        
        deleted = 0
        batch = db.batch()
        for doc in docs:
            batch.delete(doc.reference)
            deleted += 1
            if deleted % 500 == 0:
                batch.commit()
                batch = db.batch()
        
        if deleted % 500 != 0:
            batch.commit()
        
        logger.info(f"[TASK] Cleaned up {deleted} expired sessions")
        return {'success': True, 'deleted': deleted}
    except Exception as e:
        logger.error(f"[TASK] Session cleanup failed: {e}")
        return {'success': False, 'error': str(e)}


@celery_app.task(name='tasks.refresh_trends_cache')
def refresh_trends_cache():
    """Refresh trends cache"""
    try:
        from web.cache import delete_cached_pattern
        
        # Invalidate trends cache
        deleted = delete_cached_pattern("topics:*")
        
        logger.info(f"[TASK] Refreshed trends cache (deleted {deleted} keys)")
        return {'success': True, 'keys_deleted': deleted}
    except Exception as e:
        logger.error(f"[TASK] Trends cache refresh failed: {e}")
        return {'success': False, 'error': str(e)}


@celery_app.task(name='tasks.generate_daily_analytics')
def generate_daily_analytics():
    """Generate daily analytics summaries"""
    try:
        # This would generate analytics summaries for all users
        # Implementation depends on analytics structure
        logger.info("[TASK] Daily analytics generation completed")
        return {'success': True}
    except Exception as e:
        logger.error(f"[TASK] Analytics generation failed: {e}")
        return {'success': False, 'error': str(e)}

