# Agent 2: Architecture & Code Quality Specialist - Detailed Tasks

**Priority:** 🟡 HIGH - Wait for Agent 1 security fixes
**Estimated Time:** 38-52 hours
**Branch:** `agent2-architecture`

---

## ⚠️ IMPORTANT: Wait for Agent 1

**DO NOT START** until Agent 1 completes security fixes. Review `AGENT1_SECURITY_TASKS.md` to see what changes will be made.

---

## Phase 1: Blueprint Architecture Setup (6-8 hours)

### Task 1.1: Create Blueprint Directory Structure
**Time:** 1 hour

- [ ] Create directory structure:
  ```
  web/
  ├── api/
  │   ├── __init__.py
  │   ├── auth.py
  │   ├── videos.py
  │   ├── platforms.py
  │   ├── analytics.py
  │   ├── trends.py
  │   ├── assets.py
  │   ├── admin.py
  │   └── subscription.py
  ```

- [ ] Create `web/api/__init__.py`:
  ```python
  from flask import Blueprint
  
  def register_blueprints(app):
      from web.api import auth, videos, platforms, analytics, trends, assets, admin, subscription
    
      app.register_blueprint(auth.bp, url_prefix='/api')
      app.register_blueprint(videos.bp, url_prefix='/api')
      app.register_blueprint(platforms.bp, url_prefix='/api')
      app.register_blueprint(analytics.bp, url_prefix='/api')
      app.register_blueprint(trends.bp, url_prefix='/api')
      app.register_blueprint(assets.bp, url_prefix='/api')
      app.register_blueprint(admin.bp, url_prefix='/api/admin')
      app.register_blueprint(subscription.bp, url_prefix='/api')
  ```

**Success Criteria:**
- Directory structure created
- Blueprint registration function ready

---

### Task 1.2: Create Auth Blueprint
**File:** `web/api/auth.py`
**Time:** 2-3 hours

- [ ] Create blueprint:
  ```python
  from flask import Blueprint, request, jsonify
  from web import database
  from web.models.requests import LoginRequest, SignupRequest
  
  bp = Blueprint('auth', __name__)
  
  @bp.route('/login', methods=['POST'])
  def login():
      # Move login route here from api_server.py
      ...
  
  @bp.route('/signup', methods=['POST'])
  def signup():
      # Move signup route here
      ...
  
  @bp.route('/logout', methods=['POST'])
  def logout():
      # Move logout route here
      ...
  
  @bp.route('/me', methods=['GET'])
  def get_current_user():
      # Move /api/me route here
      ...
  ```

- [ ] Move routes from `api_server.py`:
  - `/api/login`
  - `/api/signup`
  - `/api/logout`
  - `/api/me`
  - `/api/password-reset`
  - `/api/password-reset-request`

- [ ] Ensure all imports work
- [ ] Test authentication flow

**Success Criteria:**
- Auth routes moved to blueprint
- Authentication still works
- No duplicate routes

---

### Task 1.3: Create Videos Blueprint
**File:** `web/api/videos.py`
**Time:** 3-4 hours

- [ ] Create blueprint with video routes:
  ```python
  from flask import Blueprint
  
  bp = Blueprint('videos', __name__)
  
  @bp.route('/create-video-enhanced', methods=['POST'])
  def create_video():
      # Move video creation route
      ...
  
  @bp.route('/post-process-video', methods=['POST'])
  def post_process():
      # Move post-processing route
      ...
  
  @bp.route('/generate-topics', methods=['POST'])
  def generate_topics():
      # Move topic generation route
      ...
  ```

- [ ] Move routes from `api_server.py`:
  - `/api/create-video-enhanced`
  - `/api/post-process-video`
  - `/api/generate-topics`
  - `/api/generate-script`
  - `/api/get-latest-output`
  - `/api/get-recent-videos`
  - `/api/delete-video`
  - `/api/get-video-metadata`

- [ ] Ensure video generation still works
- [ ] Test video creation flow

**Success Criteria:**
- Video routes in blueprint
- Video generation functional
- All endpoints working

---

## Phase 2: Service Layer Creation (8-10 hours)

### Task 2.1: Create Service Directory
**Time:** 1 hour

- [ ] Create `web/services/` directory:
  ```
  web/services/
  ├── __init__.py
  ├── video_service.py
  ├── auth_service.py
  ├── platform_service.py
  └── analytics_service.py
  ```

- [ ] Create base service class (optional):
  ```python
  class BaseService:
      def __init__(self):
          self.logger = logging.getLogger(self.__class__.__name__)
  ```

**Success Criteria:**
- Service directory structure ready

---

### Task 2.2: Create Video Service
**File:** `web/services/video_service.py`
**Time:** 3-4 hours

- [ ] Extract video business logic from routes:
  ```python
  class VideoService:
      def __init__(self):
          self.logger = logging.getLogger(__name__)
      
      def create_video(self, user_id: int, topic: str, **kwargs):
          """Business logic for video creation"""
          # Move logic from route handler
          ...
      
      def post_process_video(self, user_id: int, video_path: str):
          """Business logic for post-processing"""
          ...
      
      def generate_topics(self, user_id: int, niche: str, count: int):
          """Business logic for topic generation"""
          ...
  ```

- [ ] Move business logic from:
  - `/api/create-video-enhanced` route
  - `/api/post-process-video` route
  - `/api/generate-topics` route

- [ ] Keep routes thin (just validation and service calls)
- [ ] Add error handling
- [ ] Add logging

**Success Criteria:**
- Business logic separated from routes
- Video service methods tested
- Routes call service methods

---

### Task 2.3: Create Auth Service
**File:** `web/services/auth_service.py`
**Time:** 2-3 hours

- [ ] Extract auth business logic:
  ```python
  class AuthService:
      def login(self, email: str, password: str):
          """Handle login logic"""
          ...
      
      def signup(self, email: str, password: str, username: str = None):
          """Handle signup logic"""
          ...
      
      def create_session(self, user_id: int, remember_me: bool = False):
          """Create user session"""
          ...
      
      def verify_session(self, session_id: str):
          """Verify and return user from session"""
          ...
  ```

- [ ] Move logic from auth routes
- [ ] Add password validation
- [ ] Add session management

**Success Criteria:**
- Auth logic in service layer
- Routes call service methods

---

### Task 2.4: Create Platform Service
**File:** `web/services/platform_service.py`
**Time:** 2-3 hours

- [ ] Extract platform publishing logic:
  ```python
  class PlatformService:
      def publish_to_youtube(self, user_id: int, video_path: str, metadata: dict):
          """Publish video to YouTube"""
          ...
      
      def publish_to_tiktok(self, user_id: int, video_path: str, metadata: dict):
          """Publish video to TikTok"""
          ...
  ```

- [ ] Move logic from platform routes
- [ ] Add OAuth handling
- [ ] Add error handling

**Success Criteria:**
- Platform logic in service layer
- Publishing functional

---

## Phase 3: Refactor api_server.py (12-16 hours)

### Task 3.1: Move Routes to Blueprints
**Time:** 8-10 hours

- [ ] Systematically move routes:
  1. Auth routes → `web/api/auth.py`
  2. Video routes → `web/api/videos.py`
  3. Platform routes → `web/api/platforms.py`
  4. Analytics routes → `web/api/analytics.py`
  5. Trends routes → `web/api/trends.py`
  6. Asset routes → `web/api/assets.py`
  7. Admin routes → `web/api/admin.py`
  8. Subscription routes → `web/api/subscription.py`

- [ ] For each route:
  - Move route function to appropriate blueprint
  - Update imports
  - Update decorator from `@app.route` to `@bp.route`
  - Ensure dependencies available
  - Test route works

- [ ] Keep track of moved routes in checklist

**Success Criteria:**
- All routes moved to blueprints
- No routes remaining in `api_server.py` (except static serving)

---

### Task 3.2: Simplify api_server.py
**Time:** 2-3 hours

- [ ] Reduce `api_server.py` to:
  ```python
  from flask import Flask
  from flask_cors import CORS
  from web.api import register_blueprints
  from web.database import init_db
  
  app = Flask(__name__)
  
  # Configuration
  app.config['MAX_CONTENT_LENGTH'] = 1024 * 1024 * 1024
  
  # CORS (from Agent 1)
  CORS(app, ...)
  
  # Initialize database
  init_db()
  
  # Register blueprints
  register_blueprints(app)
  
  # Static file serving (keep these)
  @app.route('/')
  def serve_landing():
      ...
  
  if __name__ == '__main__':
      app.run(debug=True)
  ```

- [ ] Remove all route definitions
- [ ] Remove business logic (moved to services)
- [ ] Keep only app initialization

**Success Criteria:**
- `api_server.py` <200 lines
- Only app setup code remains
- All functionality works

---

### Task 3.3: Update Imports Throughout Codebase
**Time:** 2-3 hours

- [ ] Update imports in:
  - Blueprint files
  - Service files
  - Test files
  - Scripts that import from `api_server`

- [ ] Fix circular imports if any
- [ ] Ensure all imports resolve correctly
- [ ] Test application starts without errors

**Success Criteria:**
- No import errors
- Application runs successfully

---

## Phase 4: Database Structure Improvements (4-6 hours)

### Task 4.1: Add Connection Context Managers
**File:** `web/database.py`
**Time:** 2-3 hours

**Current Code:**
```python
def get_db():
    conn = sqlite3.connect(str(DB_PATH), timeout=10.0)
    conn.row_factory = sqlite3.Row
    return conn

def create_user(email, password, username=None):
    conn = get_db()
    cursor = conn.cursor()
    # ... code ...
    conn.commit()
    conn.close()  # ⚠️ Manual close - can leak on error
```

**Improved Code:**
```python
from contextlib import contextmanager

@contextmanager
def get_db():
    """Context manager for database connections"""
    conn = sqlite3.connect(str(DB_PATH), timeout=10.0)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def create_user(email, password, username=None):
    with get_db() as conn:
        cursor = conn.cursor()
        # ... code ...
        # Auto-commits on success, rolls back on error, closes always
```

- [ ] Convert `get_db()` to context manager
- [ ] Update all database functions to use `with` statement
- [ ] Ensure transactions handled correctly
- [ ] Test error handling (rollback on exception)

**Success Criteria:**
- All DB operations use context managers
- No connection leaks
- Transactions properly managed

---

### Task 4.2: Add Connection Pooling (PostgreSQL Prep)
**File:** `web/database.py`
**Time:** 2-3 hours

- [ ] Create connection factory:
  ```python
  import os
  
  def get_db_connection():
      """Get database connection (supports SQLite and PostgreSQL)"""
      db_url = os.getenv('DATABASE_URL')
      
      if db_url and db_url.startswith('postgresql://'):
          # PostgreSQL connection
          import psycopg2
          return psycopg2.connect(db_url)
      else:
          # SQLite (development)
          return sqlite3.connect(str(DB_PATH), timeout=10.0)
  ```

- [ ] Add connection pooling support:
  ```python
  from sqlalchemy import create_engine
  from sqlalchemy.pool import QueuePool
  
  engine = create_engine(
      db_url,
      poolclass=QueuePool,
      pool_size=10,
      max_overflow=20
  )
  ```

- [ ] Make database layer support both SQLite and PostgreSQL
- [ ] Test with both database types

**Success Criteria:**
- Database abstraction layer ready
- PostgreSQL connection supported
- Connection pooling configured

---

## Phase 5: Exception Handling Enhancement (4-6 hours)

### Task 5.1: Replace Bare Exception Handlers
**File:** All blueprint files
**Time:** 3-4 hours

**Find all:**
```python
except Exception as e:
    pass  # ⚠️ Silent failure
```

**Replace with:**
```python
except DatabaseError as e:
    logger.error(f"Database error in {function_name}: {e}", exc_info=True)
    raise APIError("Database operation failed") from e
except ValidationError as e:
    logger.warning(f"Validation error: {e}")
    raise
except Exception as e:
    logger.error(f"Unexpected error in {function_name}: {e}", exc_info=True)
    raise APIError("An unexpected error occurred") from e
```

- [ ] Search for all `except Exception: pass` blocks
- [ ] Replace with specific exception types from `web.exceptions`
- [ ] Add proper logging
- [ ] Ensure exceptions propagate correctly

**Success Criteria:**
- No silent exception handlers
- All exceptions logged
- Specific exception types used

---

### Task 5.2: Create Global Error Handler
**File:** `web/api_server.py`
**Time:** 1-2 hours

- [ ] Add global error handlers:
  ```python
  from web.exceptions import MSSException, APIError, AuthenticationError
  
  @app.errorhandler(MSSException)
  def handle_mss_exception(e):
      return jsonify({
          'success': False,
          'error': e.message,
          'error_code': e.error_code,
          'details': e.details
      }), 400
  
  @app.errorhandler(404)
  def handle_not_found(e):
      return jsonify({'success': False, 'error': 'Not found'}), 404
  
  @app.errorhandler(500)
  def handle_internal_error(e):
      logger.error(f"Internal server error: {e}", exc_info=True)
      return jsonify({'success': False, 'error': 'Internal server error'}), 500
  ```

- [ ] Register handlers in `api_server.py`
- [ ] Test error responses

**Success Criteria:**
- Consistent error response format
- All exceptions handled gracefully

---

## Phase 6: Code Organization & Utilities (4-6 hours)

### Task 6.1: Create Utility Modules
**Time:** 2-3 hours

- [ ] Create `web/utils/validators.py`:
  ```python
  def validate_email(email: str) -> bool:
      import re
      pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
      return re.match(pattern, email) is not None
  
  def validate_password_strength(password: str) -> tuple[bool, str]:
      """Returns (is_valid, error_message)"""
      if len(password) < 8:
          return False, "Password must be at least 8 characters"
      # Add more checks
      return True, ""
  ```

- [ ] Create `web/utils/helpers.py`:
  ```python
  def format_file_size(bytes: int) -> str:
      """Format bytes to human-readable size"""
      ...
  
  def sanitize_filename(filename: str) -> str:
      """Remove dangerous characters from filename"""
      ...
  ```

- [ ] Create `web/utils/constants.py`:
  ```python
  # Video settings
  MAX_VIDEO_DURATION = 600  # 10 minutes
  MIN_VIDEO_DURATION = 30   # 30 seconds
  
  # Subscription limits
  FREE_VIDEOS_PER_MONTH = 5
  STARTER_VIDEOS_PER_MONTH = 20
  # ... etc
  ```

**Success Criteria:**
- Utility modules created
- Code organized logically

---

### Task 6.2: Remove Hardcoded Values
**Time:** 2-3 hours

- [ ] Find hardcoded paths like `G:/Users/daveq/...`
- [ ] Replace with environment variables or config
- [ ] Remove debug statements (`print()`, `debug=True`)
- [ ] Move magic numbers to `constants.py`
- [ ] Use configuration file for settings

**Success Criteria:**
- No hardcoded paths
- All config from environment
- No debug code in production

---

## Testing After Refactoring

### Task 7.1: Verify All Routes Work
**Time:** 2-3 hours

- [ ] Test all endpoints:
  - [ ] Auth endpoints (login, signup, logout)
  - [ ] Video endpoints (create, process, list)
  - [ ] Platform endpoints (publish, OAuth)
  - [ ] Analytics endpoints
  - [ ] Trends endpoints
  - [ ] Asset endpoints

- [ ] Verify no routes broken
- [ ] Check error handling
- [ ] Verify logging works

**Success Criteria:**
- All routes functional
- No regressions
- Code cleaner and organized

---

## Checklist Summary

- [ ] Phase 1: Blueprint Setup Complete
  - [ ] All blueprints created
  - [ ] Routes moved to blueprints
- [ ] Phase 2: Service Layer Complete
  - [ ] Service classes created
  - [ ] Business logic extracted
- [ ] Phase 3: api_server.py Refactored
  - [ ] All routes moved
  - [ ] api_server.py <200 lines
- [ ] Phase 4: Database Improvements Complete
  - [ ] Context managers implemented
  - [ ] Connection pooling ready
- [ ] Phase 5: Exception Handling Complete
  - [ ] No bare exception handlers
  - [ ] Global error handler added
- [ ] Phase 6: Code Organization Complete
  - [ ] Utilities created
  - [ ] Hardcoded values removed

---

**Status:** Waiting for Agent 1 completion
**Start Date:** ___________
**Target Completion:** ___________

