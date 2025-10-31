# Agent 3: Testing & Quality Assurance Specialist - Detailed Tasks

**Priority:** 🟢 HIGH - Essential for quality, can work in parallel
**Estimated Time:** 66-88 hours
**Branch:** `agent3-testing`

---

## Phase 1: Test Infrastructure Setup (4-6 hours)

### Task 1.1: Install Testing Dependencies
**Time:** 30 minutes

- [ ] Add to `requirements.txt`:
  ```
  pytest>=7.4.0
  pytest-cov>=4.1.0
  pytest-mock>=3.11.1
  pytest-flask>=1.3.0
  pytest-timeout>=2.1.0
  coverage>=7.3.0
  ```

- [ ] Create `requirements-dev.txt`:
  ```
  -r requirements.txt
  pytest>=7.4.0
  pytest-cov>=4.1.0
  pytest-mock>=3.11.1
  pytest-flask>=1.3.0
  faker>=19.0.0  # For test data generation
  responses>=0.23.0  # For mocking HTTP requests
  ```

- [ ] Install dependencies:
  ```bash
  pip install -r requirements-dev.txt
  ```

**Success Criteria:**
- Testing packages installed
- Requirements files updated

---

### Task 1.2: Create Pytest Configuration
**File:** `pytest.ini`
**Time:** 30 minutes

- [ ] Create `pytest.ini`:
  ```ini
  [pytest]
  testpaths = tests
  python_files = test_*.py
  python_classes = Test*
  python_functions = test_*
  addopts = 
      -v
      --strict-markers
      --cov=web
      --cov=scripts
      --cov-report=html
      --cov-report=term-missing
      --cov-fail-under=80
  markers =
      unit: Unit tests
      integration: Integration tests
      e2e: End-to-end tests
      slow: Slow running tests
  ```

- [ ] Create `.coveragerc`:
  ```ini
  [run]
  source = web,scripts
  omit = 
      */tests/*
      */venv/*
      */migrations/*
  
  [report]
  exclude_lines =
      pragma: no cover
      def __repr__
      raise AssertionError
      raise NotImplementedError
      if __name__ == .__main__.:
      if TYPE_CHECKING:
  ```

**Success Criteria:**
- Pytest configured
- Coverage reporting set up

---

### Task 1.3: Create Test Fixtures
**File:** `tests/conftest.py`
**Time:** 3-5 hours

- [ ] Create comprehensive fixtures:
  ```python
  import pytest
  import tempfile
  import os
  from pathlib import Path
  from flask import Flask
  from web.api_server import app as flask_app
  from web import database
  import sqlite3
  
  @pytest.fixture
  def app():
      """Flask application fixture"""
      flask_app.config['TESTING'] = True
      flask_app.config['WTF_CSRF_ENABLED'] = False
      yield flask_app
  
  @pytest.fixture
  def client(app):
      """Test client fixture"""
      return app.test_client()
  
  @pytest.fixture
  def test_db():
      """Create temporary test database"""
      db_fd, db_path = tempfile.mkstemp(suffix='.db')
      original_db_path = database.DB_PATH
      database.DB_PATH = Path(db_path)
      database.init_db()
      yield database
      database.DB_PATH = original_db_path
      os.close(db_fd)
      os.unlink(db_path)
  
  @pytest.fixture
  def test_user(test_db):
      """Create a test user"""
      result = database.create_user(
          email='test@example.com',
          password='testpass123',
          username='testuser'
      )
      assert result['success']
      user_id = result['user_id']
      yield user_id
      # Cleanup if needed
  
  @pytest.fixture
  def authenticated_client(client, test_user):
      """Client with authenticated session"""
      # Login and get session
      response = client.post('/api/login', json={
          'email': 'test@example.com',
          'password': 'testpass123'
      })
      session_id = response.json.get('session_id')
      client.set_cookie('localhost', 'session_id', session_id)
      return client
  
  @pytest.fixture
  def mock_openai(monkeypatch):
      """Mock OpenAI API"""
      def mock_complete(*args, **kwargs):
          return {'choices': [{'message': {'content': 'Mocked AI response'}}]}
      monkeypatch.setattr('scripts.make_video.openai_generate_topics', mock_complete)
  
  @pytest.fixture
  def mock_stripe(monkeypatch):
      """Mock Stripe API"""
      # Mock Stripe API calls
      ...
  
  @pytest.fixture
  def mock_google_tts(monkeypatch):
      """Mock Google TTS"""
      # Mock TTS calls
      ...
  ```

- [ ] Create fixtures for:
  - Flask app
  - Test client
  - Test database
  - Test users
  - Authenticated sessions
  - Mocked external APIs (OpenAI, Stripe, Google)
  - Test files (images, videos)

**Success Criteria:**
- Comprehensive fixtures created
- Tests can use fixtures easily

---

## Phase 2: Unit Tests - Database Layer (8-10 hours)

### Task 2.1: Test User Management Functions
**File:** `tests/test_database_users.py`
**Time:** 3-4 hours

- [ ] Test `create_user()`:
  ```python
  def test_create_user_success(test_db):
      result = database.create_user(
          email='new@example.com',
          password='password123',
          username='newuser'
      )
      assert result['success'] is True
      assert 'user_id' in result
  
  def test_create_user_duplicate_email(test_db, test_user):
      result = database.create_user(
          email='test@example.com',  # Duplicate
          password='password123'
      )
      assert result['success'] is False
      assert 'error' in result
  
  def test_create_user_invalid_email(test_db):
      result = database.create_user(
          email='invalid-email',  # Invalid format
          password='password123'
      )
      assert result['success'] is False
  ```

- [ ] Test `verify_user()`:
  ```python
  def test_verify_user_correct_password(test_db, test_user):
      result = database.verify_user(
          email='test@example.com',
          password='testpass123'
      )
      assert result['success'] is True
      assert 'user' in result
  
  def test_verify_user_wrong_password(test_db, test_user):
      result = database.verify_user(
          email='test@example.com',
          password='wrongpassword'
      )
      assert result['success'] is False
  
  def test_verify_user_nonexistent(test_db):
      result = database.verify_user(
          email='nonexistent@example.com',
          password='anypassword'
      )
      assert result['success'] is False
  ```

- [ ] Test password hashing:
  ```python
  def test_password_hashing_bcrypt(test_db):
      """Verify passwords are hashed with bcrypt"""
      password = 'testpass123'
      hash1 = database.hash_password(password)
      hash2 = database.hash_password(password)
      # Same password, different hashes (salt)
      assert hash1 != hash2
      # But both verify correctly
      assert database.verify_password(hash1, password)
      assert database.verify_password(hash2, password)
  ```

**Success Criteria:**
- All user management functions tested
- Edge cases covered
- 100% coverage on user functions

---

### Task 2.2: Test Session Management Functions
**File:** `tests/test_database_sessions.py`
**Time:** 2-3 hours

- [ ] Test `create_session()`:
  ```python
  def test_create_session_success(test_db, test_user):
      session_id = database.create_session(
          user_id=test_user,
          duration_days=7
      )
      assert session_id is not None
      assert len(session_id) > 0
  
  def test_create_session_remember_me(test_db, test_user):
      session_id = database.create_session(
          user_id=test_user,
          duration_days=7,
          remember_me=True
      )
      # Verify session has longer expiry
      ...
  ```

- [ ] Test `get_session()`:
  ```python
  def test_get_session_valid(test_db, test_user):
      session_id = database.create_session(test_user)
      result = database.get_session(session_id)
      assert result['success'] is True
      assert result['user_id'] == test_user
  
  def test_get_session_expired(test_db, test_user):
      # Create expired session
      ...
      result = database.get_session(expired_session_id)
      assert result['success'] is False
  
  def test_get_session_invalid(test_db):
      result = database.get_session('invalid_session_id')
      assert result['success'] is False
  ```

**Success Criteria:**
- Session functions fully tested
- Expiry logic verified

---

### Task 2.3: Test Video History Functions
**File:** `tests/test_database_videos.py`
**Time:** 2-3 hours

- [ ] Test `add_video_to_history()`:
  ```python
  def test_add_video_to_history(test_db, test_user):
      result = database.add_video_to_history(
          user_id=test_user,
          video_filename='test_video.mp4',
          title='Test Video'
      )
      assert result['success'] is True
  ```

- [ ] Test `get_video_history()`:
  ```python
  def test_get_video_history(test_db, test_user):
      # Add some videos
      database.add_video_to_history(test_user, 'video1.mp4', 'Video 1')
      database.add_video_to_history(test_user, 'video2.mp4', 'Video 2')
      
      history = database.get_video_history(test_user)
      assert len(history) == 2
      assert history[0]['title'] == 'Video 2'  # Most recent first
  ```

**Success Criteria:**
- Video history functions tested
- Queries work correctly

---

### Task 2.4: Test Database Connection Management
**File:** `tests/test_database_connections.py`
**Time:** 1-2 hours

- [ ] Test context manager:
  ```python
  def test_db_context_manager(test_db):
      """Test that connections are properly closed"""
      with database.get_db() as conn:
          cursor = conn.cursor()
          cursor.execute('SELECT 1')
          result = cursor.fetchone()
          assert result[0] == 1
      # Connection should be closed now
      # Verify no connection leaks
  ```

- [ ] Test transaction rollback:
  ```python
  def test_transaction_rollback_on_error(test_db):
      """Test that errors cause rollback"""
      # Attempt invalid operation that should fail
      # Verify data not committed
      ...
  ```

**Success Criteria:**
- Connection management tested
- No leaks detected

---

## Phase 3: Unit Tests - Service Layer (12-16 hours)

### Task 3.1: Test Video Service
**File:** `tests/test_services_video.py`
**Time:** 4-5 hours

- [ ] Test video creation:
  ```python
  def test_video_service_create_video(test_user, mock_openai, mock_google_tts):
      from web.services.video_service import VideoService
      service = VideoService()
      
      result = service.create_video(
          user_id=test_user,
          topic='Test Topic',
          duration=60
      )
      assert result['success'] is True
  ```

- [ ] Test topic generation:
- [ ] Test script generation:
- [ ] Test post-processing:

**Success Criteria:**
- Video service methods tested
- External APIs mocked

---

### Task 3.2: Test Auth Service
**File:** `tests/test_services_auth.py`
**Time:** 3-4 hours

- [ ] Test login:
- [ ] Test signup:
- [ ] Test session creation:

**Success Criteria:**
- Auth service tested

---

### Task 3.3: Test Platform Service
**File:** `tests/test_services_platform.py`
**Time:** 3-4 hours

- [ ] Test YouTube publishing:
- [ ] Test TikTok publishing:
- [ ] Test OAuth handling:

**Success Criteria:**
- Platform service tested

---

## Phase 4: Integration Tests - API Endpoints (16-20 hours)

### Task 4.1: Test Authentication Endpoints
**File:** `tests/test_api_auth.py`
**Time:** 4-5 hours

- [ ] Test `/api/login`:
  ```python
  def test_login_success(client, test_db, test_user):
      response = client.post('/api/login', json={
          'email': 'test@example.com',
          'password': 'testpass123'
      })
      assert response.status_code == 200
      assert response.json['success'] is True
      assert 'session_id' in response.json
  
  def test_login_wrong_password(client, test_db, test_user):
      response = client.post('/api/login', json={
          'email': 'test@example.com',
          'password': 'wrongpassword'
      })
      assert response.status_code == 401
      assert response.json['success'] is False
  
  def test_login_rate_limit(client, test_db, test_user):
      """Test that rate limiting works"""
      # Make 6 login attempts rapidly
      for i in range(6):
          client.post('/api/login', json={
              'email': 'test@example.com',
              'password': 'wrongpassword'
          })
      # 6th attempt should be rate limited
      response = client.post('/api/login', json={
          'email': 'test@example.com',
          'password': 'wrongpassword'
      })
      assert response.status_code == 429  # Too Many Requests
  ```

- [ ] Test `/api/signup`:
- [ ] Test `/api/logout`:
- [ ] Test `/api/me`:

**Success Criteria:**
- All auth endpoints tested
- Rate limiting verified

---

### Task 4.2: Test Video Endpoints
**File:** `tests/test_api_videos.py`
**Time:** 6-8 hours

- [ ] Test `/api/create-video-enhanced`:
  ```python
  def test_create_video_success(authenticated_client, mock_openai, mock_google_tts):
      response = authenticated_client.post('/api/create-video-enhanced', json={
          'topic': 'Test Topic',
          'duration': 60
      })
      assert response.status_code == 200
      assert response.json['success'] is True
  
  def test_create_video_quota_exceeded(authenticated_client):
      # Create videos up to quota limit
      # Next video should fail
      ...
  
  def test_create_video_validation_error(authenticated_client):
      response = authenticated_client.post('/api/create-video-enhanced', json={
          'topic': '',  # Invalid - too short
          'duration': 10  # Invalid - too short
      })
      assert response.status_code == 400
  ```

- [ ] Test `/api/post-process-video`:
- [ ] Test `/api/generate-topics`:
- [ ] Test `/api/get-recent-videos`:

**Success Criteria:**
- Video endpoints fully tested
- Validation tested
- Quota limits tested

---

### Task 4.3: Test Platform Endpoints
**File:** `tests/test_api_platforms.py`
**Time:** 4-5 hours

- [ ] Test `/api/publish-to-platform`:
- [ ] Test OAuth endpoints:
- [ ] Test channel management:

**Success Criteria:**
- Platform endpoints tested

---

### Task 4.4: Test File Upload Endpoints
**File:** `tests/test_api_uploads.py`
**Time:** 2-3 hours

- [ ] Test `/api/upload-avatar`:
  ```python
  def test_upload_avatar_success(authenticated_client, test_image_file):
      response = authenticated_client.post('/api/upload-avatar',
          data={'file': test_image_file},
          content_type='multipart/form-data'
      )
      assert response.status_code == 200
  
  def test_upload_avatar_invalid_type(authenticated_client, test_exe_file):
      """Test that .exe files are rejected even if renamed"""
      response = authenticated_client.post('/api/upload-avatar',
          data={'file': test_exe_file},
          content_type='multipart/form-data'
      )
      assert response.status_code == 400
  
  def test_upload_avatar_too_large(authenticated_client, test_large_file):
      """Test file size limits"""
      response = authenticated_client.post('/api/upload-avatar',
          data={'file': test_large_file}
      )
      assert response.status_code == 400
  ```

**Success Criteria:**
- Upload security tested
- Validation verified

---

## Phase 5: End-to-End Tests (12-16 hours)

### Task 5.1: Full User Registration Flow
**File:** `tests/test_e2e_registration.py`
**Time:** 2-3 hours

- [ ] Test complete flow:
  1. Sign up new user
  2. Verify email (if implemented)
  3. Login
  4. Check session
  5. Logout

**Success Criteria:**
- Full registration flow works

---

### Task 5.2: Complete Video Creation Pipeline
**File:** `tests/test_e2e_video_creation.py`
**Time:** 4-5 hours

- [ ] Test complete flow:
  1. Login
  2. Generate topics
  3. Select topic
  4. Generate script
  5. Create video
  6. Post-process
  7. Verify video exists
  8. Download video

**Success Criteria:**
- Full video pipeline works

---

### Task 5.3: Multi-Platform Publishing Workflow
**File:** `tests/test_e2e_publishing.py`
**Time:** 4-5 hours

- [ ] Test workflow:
  1. Create video
  2. Connect YouTube (OAuth)
  3. Publish to YouTube
  4. Verify published
  5. Connect TikTok
  6. Publish to TikTok

**Success Criteria:**
- Publishing workflow complete

---

## Phase 6: Performance Tests (6-8 hours)

### Task 6.1: Load Testing
**File:** `tests/test_performance_load.py`
**Time:** 3-4 hours

- [ ] Install locust:
  ```bash
  pip install locust
  ```

- [ ] Create `tests/load_test.py`:
  ```python
  from locust import HttpUser, task, between
  
  class MSSUser(HttpUser):
      wait_time = between(1, 3)
      
      @task(3)
      def login(self):
          self.client.post('/api/login', json={
              'email': 'test@example.com',
              'password': 'testpass123'
          })
      
      @task(1)
      def create_video(self):
          self.client.post('/api/create-video-enhanced', json={
              'topic': 'Test Topic',
              'duration': 60
          })
  ```

- [ ] Run load test:
  ```bash
  locust -f tests/load_test.py --host=http://localhost:5000
  ```

- [ ] Test with:
  - 50 concurrent users
  - 100 concurrent users
  - Measure response times
  - Identify bottlenecks

**Success Criteria:**
- Load testing set up
- Performance baseline established

---

### Task 6.2: Stress Testing
**File:** `tests/test_performance_stress.py`
**Time:** 2-3 hours

- [ ] Test system limits:
  - Maximum concurrent video generations
  - Database connection limits
  - Memory usage under load
  - CPU usage

**Success Criteria:**
- System limits identified

---

### Task 6.3: Profile Slow Endpoints
**Time:** 1-2 hours

- [ ] Use cProfile to profile endpoints:
  ```python
  import cProfile
  import pstats
  
  profiler = cProfile.Profile()
  profiler.enable()
  # Run endpoint
  profiler.disable()
  stats = pstats.Stats(profiler)
  stats.sort_stats('cumulative')
  stats.print_stats(20)  # Top 20 slowest functions
  ```

- [ ] Identify slow queries
- [ ] Optimize bottlenecks

**Success Criteria:**
- Slow endpoints identified
- Optimization opportunities documented

---

## Phase 7: CI/CD Integration (4-6 hours)

### Task 7.1: Create GitHub Actions Workflow
**File:** `.github/workflows/tests.yml`
**Time:** 2-3 hours

- [ ] Create workflow:
  ```yaml
  name: Tests
  
  on:
    push:
      branches: [ main, develop ]
    pull_request:
      branches: [ main, develop ]
  
  jobs:
    test:
      runs-on: ubuntu-latest
      steps:
        - uses: actions/checkout@v3
        - uses: actions/setup-python@v4
          with:
            python-version: '3.11'
        - name: Install dependencies
          run: |
            pip install -r requirements-dev.txt
        - name: Run tests
          run: |
            pytest --cov=web --cov-report=xml
        - name: Upload coverage
          uses: codecov/codecov-action@v3
          with:
            file: ./coverage.xml
  ```

**Success Criteria:**
- Tests run on every PR
- Coverage reports generated

---

### Task 7.2: Add Test Badges
**File:** `README.md`
**Time:** 30 minutes

- [ ] Add badges:
  ```markdown
  [![Tests](https://github.com/your-repo/MSS/actions/workflows/tests.yml/badge.svg)](https://github.com/your-repo/MSS/actions)
  [![Coverage](https://codecov.io/gh/your-repo/MSS/branch/main/graph/badge.svg)](https://codecov.io/gh/your-repo/MSS)
  ```

**Success Criteria:**
- Badges visible in README

---

## Checklist Summary

- [ ] Phase 1: Test Infrastructure Complete
- [ ] Phase 2: Database Unit Tests Complete (>90% coverage)
- [ ] Phase 3: Service Layer Tests Complete (>80% coverage)
- [ ] Phase 4: API Integration Tests Complete
- [ ] Phase 5: E2E Tests Complete
- [ ] Phase 6: Performance Tests Complete
- [ ] Phase 7: CI/CD Integration Complete

---

**Status:** Ready to start
**Start Date:** ___________
**Target Completion:** ___________

