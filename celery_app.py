"""
Celery configuration for MSS async task queue
"""
from celery import Celery
import os

# Get Redis URL from environment
redis_url = os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0')
result_backend = os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0')

# Create Celery app
celery_app = Celery(
    'mss',
    broker=redis_url,
    backend=result_backend
)

# Celery configuration
celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 minutes max per task
    task_soft_time_limit=25 * 60,  # Soft limit: 25 minutes
    worker_prefetch_multiplier=4,
    worker_max_tasks_per_child=1000,  # Restart worker after 1000 tasks
    task_acks_late=True,  # Acknowledge after task completes
    task_reject_on_worker_lost=True,
    worker_disable_rate_limits=False,
)

# Scheduled tasks (Celery Beat)
celery_app.conf.beat_schedule = {
    'cleanup-temp-files': {
        'task': 'tasks.cleanup_temp_files',
        'schedule': 86400.0,  # Daily (24 hours)
    },
    'cleanup-expired-sessions': {
        'task': 'tasks.cleanup_expired_sessions',
        'schedule': 43200.0,  # Every 12 hours
    },
    'refresh-trends-cache': {
        'task': 'tasks.refresh_trends_cache',
        'schedule': 21600.0,  # Every 6 hours
    },
    'generate-daily-analytics': {
        'task': 'tasks.generate_daily_analytics',
        'schedule': 86400.0,  # Daily
    },
}

print(f"[CELERY] Celery app configured. Broker: {redis_url}")






