# Agent 4: Performance & Scalability Specialist - Detailed Tasks

**Priority:** 🔵 MEDIUM-HIGH - Essential for scale
**Estimated Time:** 50-66 hours
**Branch:** `agent4-performance`

---

## Phase 1: Redis Caching Implementation (8-10 hours)

### Task 1.1: Install and Configure Redis
**Time:** 1-2 hours

- [ ] Add to `requirements.txt`:
  ```
  redis>=5.0.0
  ```

- [ ] Create Redis configuration:
  ```python
  # web/cache.py
  import redis
  import json
  import os
  
  redis_client = redis.Redis(
      host=os.getenv('REDIS_HOST', 'localhost'),
      port=int(os.getenv('REDIS_PORT', 6379)),
      db=0,
      decode_responses=True
  )
  
  def test_redis_connection():
      try:
          redis_client.ping()
          return True
      except Exception:
          return False
  ```

- [ ] Update `.env.example`:
  ```
  REDIS_HOST=localhost
  REDIS_PORT=6379
  ```

- [ ] Create `docker-compose.yml` for local development:
  ```yaml
  version: '3.8'
  services:
    redis:
      image: redis:7-alpine
      ports:
        - "6379:6379"
      volumes:
        - redis-data:/data
  
  volumes:
    redis-data:
  ```

**Success Criteria:**
- Redis installed and configured
- Connection test passes

---

### Task 1.2: Create Caching Utilities
**File:** `web/cache.py`
**Time:** 2-3 hours

- [ ] Create caching functions:
  ```python
  from functools import wraps
  import json
  import hashlib
  
  def cache_key(prefix: str, *args, **kwargs):
      """Generate cache key from arguments"""
      key_data = f"{prefix}:{args}:{kwargs}"
      key_hash = hashlib.md5(key_data.encode()).hexdigest()
      return f"{prefix}:{key_hash}"
  
  def get_cached(key: str, default=None):
      """Get value from cache"""
      try:
          value = redis_client.get(key)
          if value:
              return json.loads(value)
      except Exception as e:
          logger.warning(f"Cache get failed: {e}")
      return default
  
  def set_cached(key: str, value: any, ttl: int = 300):
      """Set value in cache with TTL (seconds)"""
      try:
          redis_client.setex(
              key,
              ttl,
              json.dumps(value, default=str)
          )
          return True
      except Exception as e:
          logger.warning(f"Cache set failed: {e}")
          return False
  
  def delete_cached(key: str):
      """Delete key from cache"""
      try:
          redis_client.delete(key)
      except Exception as e:
          logger.warning(f"Cache delete failed: {e}")
  
  def cache_result(ttl: int = 300, prefix: str = "cache"):
      """Decorator to cache function results"""
      def decorator(func):
          @wraps(func)
          def wrapper(*args, **kwargs):
              key = cache_key(f"{prefix}:{func.__name__}", *args, **kwargs)
              cached = get_cached(key)
              if cached is not None:
                  return cached
              
              result = func(*args, **kwargs)
              set_cached(key, result, ttl)
              return result
          return wrapper
      return decorator
  ```

**Success Criteria:**
- Caching utilities created
- Decorator works correctly

---

### Task 1.3: Implement Caching for Topic Generation
**Time:** 1-2 hours

- [ ] Cache topic generation results:
  ```python
  # In scripts/make_video.py or web/services/video_service.py
  from web.cache import cache_result
  
  @cache_result(ttl=300, prefix="topics")  # 5 minutes
  def openai_generate_topics(niche: str, count: int = 10):
      # Existing implementation
      ...
  ```

- [ ] Cache by niche and count
- [ ] Invalidate cache when needed
- [ ] Test caching behavior

**Success Criteria:**
- Topic generation cached
- Cache hit/miss working

---

### Task 1.4: Cache User Sessions in Redis
**Time:** 2-3 hours

- [ ] Store sessions in Redis instead of (or in addition to) database:
  ```python
  # In web/database.py or web/services/auth_service.py
  def create_session_redis(user_id: int, duration_days: int = 7):
      session_id = secrets.token_urlsafe(32)
      ttl = duration_days * 24 * 60 * 60  # Convert to seconds
      
      session_data = {
          'user_id': user_id,
          'created_at': datetime.utcnow().isoformat()
      }
      
      redis_client.setex(
          f"session:{session_id}",
          ttl,
          json.dumps(session_data)
      )
      
      return session_id
  
  def get_session_redis(session_id: str):
      session_data = redis_client.get(f"session:{session_id}")
      if session_data:
          return json.loads(session_data)
      return None
  ```

- [ ] Update session lookup to check Redis first
- [ ] Fallback to database if Redis unavailable
- [ ] Test session caching

**Success Criteria:**
- Sessions cached in Redis
- Fast session lookups
- Fallback works

---

### Task 1.5: Cache Platform API Responses
**Time:** 2-3 hours

- [ ] Cache platform API calls:
  ```python
  @cache_result(ttl=600, prefix="platform_api")  # 10 minutes
  def get_youtube_channels(user_id: int):
      # API call to YouTube
      ...
  
  @cache_result(ttl=900, prefix="platform_api")  # 15 minutes
  def get_tiktok_account_info(user_id: int):
      # API call to TikTok
      ...
  ```

- [ ] Cache analytics data (15 min TTL)
- [ ] Cache trends data (1 hour TTL)
- [ ] Implement cache invalidation for user-specific data

**Success Criteria:**
- Platform API calls cached
- Cache invalidation working

---

## Phase 2: Async Task Queue (Celery) (16-20 hours)

### Task 2.1: Install and Configure Celery
**Time:** 2-3 hours

- [ ] Add to `requirements.txt`:
  ```
  celery>=5.3.0
  redis>=5.0.0  # Celery broker
  ```

- [ ] Create `celery_app.py`:
  ```python
  from celery import Celery
  import os
  
  celery_app = Celery(
      'mss',
      broker=os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0'),
      backend=os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0')
  )
  
  celery_app.conf.update(
      task_serializer='json',
      accept_content=['json'],
      result_serializer='json',
      timezone='UTC',
      enable_utc=True,
      task_track_started=True,
      task_time_limit=30 * 60,  # 30 minutes
      worker_prefetch_multiplier=4,
      worker_max_tasks_per_child=1000
  )
  ```

- [ ] Create `web/tasks.py`:
  ```python
  from celery_app import celery_app
  from scripts.make_video import render_video
  
  @celery_app.task(bind=True, name='tasks.generate_video')
  def generate_video_async(self, user_id: int, topic: str, **kwargs):
      """Async task to generate video"""
      try:
          # Update task state
          self.update_state(state='PROGRESS', meta={'step': 'generating_topics'})
          
          # Generate video
          result = render_video(topic=topic, user_id=user_id, **kwargs)
          
          self.update_state(state='SUCCESS', meta={'result': result})
          return result
      except Exception as e:
          self.update_state(state='FAILURE', meta={'error': str(e)})
          raise
  
  @celery_app.task(name='tasks.post_process_video')
  def post_process_video_async(video_path: str, user_id: int):
      """Async task for video post-processing"""
      # Post-processing logic
      ...
  
  @celery_app.task(name='tasks.publish_to_platform')
  def publish_to_platform_async(platform: str, video_path: str, user_id: int, metadata: dict):
      """Async task for platform publishing"""
      # Publishing logic
      ...
  ```

**Success Criteria:**
- Celery configured
- Basic tasks created

---

### Task 2.2: Convert Video Generation to Async
**Time:** 4-5 hours

- [ ] Update `/api/create-video-enhanced` endpoint:
  ```python
  @app.route('/api/create-video-enhanced', methods=['POST'])
  def create_video():
      # Validate request
      req = CreateVideoRequest(**request.json)
      
      # Start async task
      task = generate_video_async.delay(
          user_id=user_id,
          topic=req.topic,
          duration=req.duration
      )
      
      return jsonify({
          'success': True,
          'task_id': task.id,
          'status': 'pending'
      }), 202  # Accepted
  ```

- [ ] Add task status endpoint:
  ```python
  @app.route('/api/task-status/<task_id>', methods=['GET'])
  def get_task_status(task_id):
      task = generate_video_async.AsyncResult(task_id)
      
      if task.state == 'PENDING':
          response = {'state': task.state, 'status': 'Waiting...'}
      elif task.state == 'PROGRESS':
          response = {
              'state': task.state,
              'status': 'Processing...',
              'meta': task.info
          }
      elif task.state == 'SUCCESS':
          response = {
              'state': task.state,
              'status': 'Complete',
              'result': task.result
          }
      else:  # FAILURE
          response = {
              'state': task.state,
              'status': 'Failed',
              'error': str(task.info)
          }
      
      return jsonify(response)
  ```

- [ ] Update frontend to poll task status
- [ ] Test async video generation

**Success Criteria:**
- Video generation non-blocking
- Task status trackable
- Frontend handles async flow

---

### Task 2.3: Convert Post-Processing to Async
**Time:** 3-4 hours

- [ ] Move post-processing to Celery task
- [ ] Update endpoint to return task ID
- [ ] Test post-processing async flow

**Success Criteria:**
- Post-processing async
- Status trackable

---

### Task 2.4: Convert Platform Publishing to Async
**Time:** 3-4 hours

- [ ] Move publishing to Celery task
- [ ] Handle multiple platforms in parallel
- [ ] Update endpoints
- [ ] Test publishing async flow

**Success Criteria:**
- Publishing async
- Multiple platforms supported

---

### Task 2.5: Add Task Progress Updates
**Time:** 2-3 hours

- [ ] Use Celery events for real-time updates:
  ```python
  from celery.events import Events
  
  @app.route('/api/task-events/<task_id>', methods=['GET'])
  def get_task_events(task_id):
      # Stream task events via Server-Sent Events
      def event_stream():
          events = Events(celery_app, app=celery_app)
          with events.get_receiver() as receiver:
              for event in receiver:
                  if event['uuid'] == task_id:
                      yield f"data: {json.dumps(event)}\n\n"
      
      return Response(event_stream(), mimetype='text/event-stream')
  ```

- [ ] Or use polling (simpler):
  - Frontend polls `/api/task-status/<task_id>` every 2 seconds
  - Show progress updates in UI

**Success Criteria:**
- Progress updates visible
- Users see task status

---

### Task 2.6: Handle Task Failures and Retries
**Time:** 2-3 hours

- [ ] Add retry logic:
  ```python
  @celery_app.task(bind=True, autoretry_for=(Exception,), retry_backoff=True, max_retries=3)
  def generate_video_async(self, ...):
      # Task implementation
      ...
  ```

- [ ] Add error handling and notifications
- [ ] Log task failures
- [ ] Test retry behavior

**Success Criteria:**
- Tasks retry on failure
- Errors handled gracefully

---

### Task 2.7: Create Celery Worker Startup Scripts
**Time:** 1-2 hours

- [ ] Create `start_celery_worker.sh`:
  ```bash
  #!/bin/bash
  celery -A celery_app worker --loglevel=info --concurrency=4
  ```

- [ ] Create `start_celery_beat.sh` (for scheduled tasks):
  ```bash
  #!/bin/bash
  celery -A celery_app beat --loglevel=info
  ```

- [ ] Update Dockerfile to support Celery workers
- [ ] Document deployment

**Success Criteria:**
- Workers can be started easily
- Documentation complete

---

## Phase 3: Database Query Optimization (6-8 hours)

### Task 3.1: Add Database Indexes
**File:** `web/database.py`
**Time:** 2-3 hours

- [ ] Add indexes:
  ```python
  def init_db():
      conn = get_db()
      cursor = conn.cursor()
      
      # Existing table creation...
      
      # Add indexes
      cursor.execute('CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)')
      cursor.execute('CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id)')
      cursor.execute('CREATE INDEX IF NOT EXISTS idx_sessions_expires ON sessions(expires_at)')
      cursor.execute('CREATE INDEX IF NOT EXISTS idx_video_history_user_id ON video_history(user_id)')
      cursor.execute('CREATE INDEX IF NOT EXISTS idx_video_history_created ON video_history(created_at)')
      
      conn.commit()
      conn.close()
  ```

- [ ] Test query performance before/after
- [ ] Document indexes added

**Success Criteria:**
- Indexes created
- Query performance improved

---

### Task 3.2: Optimize Slow Queries
**Time:** 2-3 hours

- [ ] Profile database queries:
  ```python
  import time
  
  def profile_query(query_func):
      start = time.time()
      result = query_func()
      duration = time.time() - start
      if duration > 0.1:  # Log slow queries
          logger.warning(f"Slow query: {duration:.3f}s - {query_func.__name__}")
      return result
  ```

- [ ] Use `EXPLAIN QUERY PLAN` for SQLite
- [ ] Optimize:
  - Video history queries (add pagination)
  - Session lookups (use indexes)
  - User queries (add caching)

**Success Criteria:**
- Slow queries identified
- Optimizations applied

---

### Task 3.3: Implement Query Result Caching
**Time:** 2-3 hours

- [ ] Cache frequent queries:
  ```python
  @cache_result(ttl=300, prefix="db")
  def get_user_subscription_tier(user_id: int):
      # Database query
      ...
  ```

- [ ] Cache:
  - User subscription info
  - Video counts
  - Analytics data
  - Trends data

**Success Criteria:**
- Queries cached appropriately
- Cache invalidation working

---

## Phase 4: API Response Optimization (4-6 hours)

### Task 4.1: Add Response Compression
**File:** `web/api_server.py`
**Time:** 1-2 hours

- [ ] Install Flask-Compress:
  ```bash
  pip install flask-compress
  ```

- [ ] Enable compression:
  ```python
  from flask_compress import Compress
  
  Compress(app)
  ```

- [ ] Test response sizes
- [ ] Verify compression working

**Success Criteria:**
- Responses compressed
- Smaller payload sizes

---

### Task 4.2: Implement Pagination
**Time:** 2-3 hours

- [ ] Add pagination to list endpoints:
  ```python
  def paginate_query(query, page: int = 1, per_page: int = 20):
      offset = (page - 1) * per_page
      total = len(query)
      items = query[offset:offset + per_page]
      
      return {
          'items': items,
          'page': page,
          'per_page': per_page,
          'total': total,
          'pages': (total + per_page - 1) // per_page
      }
  ```

- [ ] Add pagination to:
  - `/api/get-recent-videos`
  - `/api/analytics` (if large datasets)
  - Video history endpoints

**Success Criteria:**
- Pagination working
- Large datasets handled efficiently

---

### Task 4.3: Add ETags for Cacheable Responses
**Time:** 1-2 hours

- [ ] Implement ETag generation:
  ```python
  import hashlib
  
  def generate_etag(data):
      return hashlib.md5(json.dumps(data, sort_keys=True).encode()).hexdigest()
  
  @app.after_request
  def add_etag(response):
      if response.status_code == 200 and response.content_type == 'application/json':
          etag = generate_etag(response.get_json())
          response.headers['ETag'] = f'"{etag}"'
          if request.headers.get('If-None-Match') == f'"{etag}"':
              return Response(status=304)
      return response
  ```

**Success Criteria:**
- ETags added
- 304 responses working

---

## Phase 5: Background Job Processing (6-8 hours)

### Task 5.1: Create Scheduled Tasks (Celery Beat)
**Time:** 3-4 hours

- [ ] Configure Celery Beat:
  ```python
  # celery_app.py
  from celery.schedules import crontab
  
  celery_app.conf.beat_schedule = {
      'cleanup-temp-files': {
          'task': 'tasks.cleanup_temp_files',
          'schedule': crontab(hour=2, minute=0),  # 2 AM daily
      },
      'generate-daily-analytics': {
          'task': 'tasks.generate_daily_analytics',
          'schedule': crontab(hour=0, minute=0),  # Midnight
      },
      'refresh-trends-cache': {
          'task': 'tasks.refresh_trends_cache',
          'schedule': crontab(hour='*/6'),  # Every 6 hours
      },
      'cleanup-expired-sessions': {
          'task': 'tasks.cleanup_expired_sessions',
          'schedule': crontab(hour='*/12'),  # Every 12 hours
      }
  }
  ```

- [ ] Create scheduled tasks:
  ```python
  @celery_app.task(name='tasks.cleanup_temp_files')
  def cleanup_temp_files():
      # Delete files older than 7 days from tmp/
      ...
  
  @celery_app.task(name='tasks.generate_daily_analytics')
  def generate_daily_analytics():
      # Generate daily analytics summaries
      ...
  ```

**Success Criteria:**
- Scheduled tasks configured
- Jobs run automatically

---

### Task 5.2: Add Job Monitoring
**Time:** 2-3 hours

- [ ] Create job monitoring endpoint:
  ```python
  @app.route('/api/admin/jobs', methods=['GET'])
  def get_job_status():
      # Get Celery task stats
      inspect = celery_app.control.inspect()
      
      active = inspect.active()
      scheduled = inspect.scheduled()
      reserved = inspect.reserved()
      
      return jsonify({
          'active': active,
          'scheduled': scheduled,
          'reserved': reserved
      })
  ```

- [ ] Add job queue length monitoring
- [ ] Alert on queue backlog

**Success Criteria:**
- Job monitoring available
- Queue health visible

---

## Phase 6: Performance Monitoring (4-6 hours)

### Task 6.1: Add Request Timing Middleware
**Time:** 2-3 hours

- [ ] Add timing middleware:
  ```python
  @app.before_request
  def before_request():
      g.start_time = time.time()
  
  @app.after_request
  def after_request(response):
      if hasattr(g, 'start_time'):
          duration = time.time() - g.start_time
          logger.info(f"{request.method} {request.path} - {duration:.3f}s")
          
          if duration > 1.0:  # Log slow requests
              logger.warning(f"Slow request: {request.path} took {duration:.3f}s")
      
      return response
  ```

**Success Criteria:**
- Request timing logged
- Slow requests identified

---

### Task 6.2: Add Performance Metrics Endpoint
**Time:** 2-3 hours

- [ ] Create metrics endpoint:
  ```python
  @app.route('/api/admin/metrics', methods=['GET'])
  def get_metrics():
      import psutil
      import os
      
      process = psutil.Process(os.getpid())
      
      return jsonify({
          'cpu_percent': process.cpu_percent(),
          'memory_mb': process.memory_info().rss / 1024 / 1024,
          'cache_hit_rate': get_cache_hit_rate(),  # From Redis
          'active_tasks': get_active_task_count(),
          'db_connections': get_db_connection_count()
      })
  ```

**Success Criteria:**
- Metrics available
- System health monitorable

---

## Checklist Summary

- [ ] Phase 1: Redis Caching Complete
- [ ] Phase 2: Celery Async Tasks Complete
- [ ] Phase 3: Database Optimization Complete
- [ ] Phase 4: API Response Optimization Complete
- [ ] Phase 5: Background Jobs Complete
- [ ] Phase 6: Performance Monitoring Complete

---

**Status:** Ready to start
**Start Date:** ___________
**Target Completion:** ___________

