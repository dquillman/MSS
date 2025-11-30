"""
Redis caching utilities for MSS application
"""
import redis
import json
import os
import hashlib
import logging
from functools import wraps
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Redis client (will be None if Redis unavailable)
redis_client: Optional[redis.Redis] = None

def init_redis():
    """Initialize Redis connection"""
    global redis_client
    try:
        redis_host = os.getenv('REDIS_HOST', 'localhost')
        redis_port = int(os.getenv('REDIS_PORT', 6379))
        redis_db = int(os.getenv('REDIS_DB', 0))
        
        redis_client = redis.Redis(
            host=redis_host,
            port=redis_port,
            db=redis_db,
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=2
        )
        
        # Test connection
        redis_client.ping()
        logger.info(f"[CACHE] Redis connected: {redis_host}:{redis_port}/{redis_db}")
        return True
    except Exception as e:
        logger.warning(f"[CACHE] Redis unavailable: {e}. Caching disabled.")
        redis_client = None
        return False

# Initialize on import
_init_success = init_redis()


def cache_key(prefix: str, *args, **kwargs) -> str:
    """Generate cache key from arguments"""
    key_data = f"{prefix}:{args}:{kwargs}"
    key_hash = hashlib.md5(key_data.encode()).hexdigest()[:16]
    return f"{prefix}:{key_hash}"


def get_cached(key: str, default: Any = None) -> Any:
    """Get value from cache"""
    if not redis_client:
        return default
    
    try:
        value = redis_client.get(key)
        if value:
            return json.loads(value)
    except Exception as e:
        logger.warning(f"[CACHE] Get failed for {key}: {e}")
    
    return default


def set_cached(key: str, value: Any, ttl: int = 300) -> bool:
    """Set value in cache with TTL (seconds)"""
    if not redis_client:
        return False
    
    try:
        redis_client.setex(
            key,
            ttl,
            json.dumps(value, default=str)
        )
        return True
    except Exception as e:
        logger.warning(f"[CACHE] Set failed for {key}: {e}")
        return False


def delete_cached(key: str) -> bool:
    """Delete key from cache"""
    if not redis_client:
        return False
    
    try:
        redis_client.delete(key)
        return True
    except Exception as e:
        logger.warning(f"[CACHE] Delete failed for {key}: {e}")
        return False


def delete_cached_pattern(pattern: str) -> int:
    """Delete all keys matching pattern"""
    if not redis_client:
        return 0
    
    try:
        keys = redis_client.keys(pattern)
        if keys:
            return redis_client.delete(*keys)
        return 0
    except Exception as e:
        logger.warning(f"[CACHE] Delete pattern failed for {pattern}: {e}")
        return 0


def cache_result(ttl: int = 300, prefix: str = "cache"):
    """Decorator to cache function results"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Generate cache key
            key = cache_key(f"{prefix}:{func.__name__}", *args, **kwargs)
            
            # Try to get from cache
            cached = get_cached(key)
            if cached is not None:
                logger.debug(f"[CACHE] Hit: {key}")
                return cached
            
            # Cache miss - call function
            logger.debug(f"[CACHE] Miss: {key}")
            result = func(*args, **kwargs)
            
            # Store in cache
            set_cached(key, result, ttl)
            
            return result
        return wrapper
    return decorator


def get_cache_stats() -> dict:
    """Get cache statistics"""
    if not redis_client:
        return {'enabled': False}
    
    try:
        info = redis_client.info('stats')
        hits = info.get('keyspace_hits', 0)
        misses = info.get('keyspace_misses', 0)
        total = hits + misses
        
        return {
            'enabled': True,
            'keys': redis_client.dbsize(),
            'hits': hits,
            'misses': misses,
            'hit_rate': hits / max(1, total) if total > 0 else 0.0
        }
    except Exception as e:
        logger.warning(f"[CACHE] Stats failed: {e}")
        return {'enabled': True, 'error': str(e)}


# Convenience functions for common caching patterns
def cache_user_session(session_id: str, user_data: dict, ttl: int = 604800) -> bool:
    """Cache user session data (default 7 days)"""
    return set_cached(f"session:{session_id}", user_data, ttl=ttl)


def get_cached_user_session(session_id: str) -> Optional[dict]:
    """Get cached user session data"""
    return get_cached(f"session:{session_id}")


def invalidate_user_session(session_id: str) -> bool:
    """Invalidate cached user session"""
    return delete_cached(f"session:{session_id}")


@cache_result(ttl=300, prefix="user_stats")
def get_user_stats_cached(user_id: int) -> dict:
    """Cached wrapper for user stats (5 min TTL)"""
    # This will be called by the actual function
    # Import here to avoid circular dependencies
    from web import firebase_db as database
    return database.get_user_stats(user_id)

