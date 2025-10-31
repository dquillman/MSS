# Agent 1: Security & Infrastructure Specialist - Detailed Tasks

**Priority:** 🔴 CRITICAL - Must complete first
**Estimated Time:** 24-33 hours
**Branch:** `agent1-security`

---

## Phase 1: Security Audit & SQL Injection Fixes (8-10 hours)

### Task 1.1: Complete SQL Query Audit
**File:** `web/database.py`
**Time:** 3-4 hours

- [ ] Review ALL `cursor.execute()` calls in `database.py`
- [ ] Verify ALL queries use parameterized placeholders (`?`)
- [ ] Check for any string formatting (`%s`, `.format()`, f-strings) in queries
- [ ] Document any vulnerable queries found
- [ ] Fix any identified vulnerabilities
- [ ] Test with SQL injection attempts:
  ```python
  # Test cases
  email = "test' OR '1'='1"
  email = "test'--"
  email = "test' UNION SELECT * FROM users--"
  ```

**Success Criteria:**
- All queries use parameterized placeholders
- No SQL injection vulnerabilities found
- Tests pass with injection attempts

---

### Task 1.2: File Upload Security Audit
**File:** `web/api_server.py` (all upload endpoints)
**Time:** 2-3 hours

- [ ] Find all file upload endpoints (`@app.route` with `request.files`)
- [ ] Review each endpoint for:
  - File size limits (max 100MB for videos, 10MB for images)
  - MIME type validation (check actual file content, not just extension)
  - File extension whitelist
  - Magic bytes validation (detect file type from header)
  - Virus/malware scanning (optional but recommended)
- [ ] Add validation to:
  - `/api/upload-avatar`
  - `/api/upload-logo`
  - `/api/upload-thumbnail`
  - Any other upload endpoints
- [ ] Test with malicious files (rename `.exe` to `.png`, oversized files)

**Success Criteria:**
- All upload endpoints validate file type and size
- Malicious file uploads rejected
- Clear error messages for invalid uploads

---

### Task 1.3: Token Storage Encryption
**File:** `web/platform_apis.py`, `web/database.py`
**Time:** 3-4 hours

- [ ] Identify where OAuth tokens are stored (database, files, environment)
- [ ] Implement AES-256 encryption for sensitive tokens:
  ```python
  from cryptography.fernet import Fernet
  # Generate key: Fernet.generate_key()
  # Store key in environment variable
  ```
- [ ] Encrypt tokens before database storage
- [ ] Decrypt tokens when needed (on-the-fly)
- [ ] Add token encryption for:
  - YouTube OAuth tokens
  - TikTok OAuth tokens
  - Instagram OAuth tokens
  - Facebook OAuth tokens
  - API keys stored in database
- [ ] Create migration script to encrypt existing tokens
- [ ] Test encryption/decryption flow

**Success Criteria:**
- All OAuth tokens encrypted at rest
- Encryption key stored securely (env var, not in code)
- Decryption works for existing tokens
- No plaintext tokens in database

---

## Phase 2: CORS & HTTPS Enforcement (2-3 hours)

### Task 2.1: Restrict CORS Configuration
**File:** `web/api_server.py`
**Time:** 1 hour

**Current Code:**
```python
CORS(app, supports_credentials=True)  # ⚠️ Allows ANY origin
```

**Fix Required:**
```python
# Get allowed origins from environment variable
ALLOWED_ORIGINS = os.getenv('ALLOWED_ORIGINS', '').split(',')
if not ALLOWED_ORIGINS or ALLOWED_ORIGINS == ['']:
    ALLOWED_ORIGINS = ['http://localhost:5000', 'http://localhost:3000']

CORS(app, 
     origins=ALLOWED_ORIGINS,
     supports_credentials=True,
     allow_headers=['Content-Type', 'Authorization'],
     methods=['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'])
```

**Actions:**
- [ ] Replace open CORS with restricted origins
- [ ] Add `ALLOWED_ORIGINS` to `.env.example`
- [ ] Test CORS with actual frontend domains
- [ ] Verify preflight requests work
- [ ] Document CORS configuration

**Success Criteria:**
- CORS only allows specified domains
- Frontend can make authenticated requests
- Other domains cannot access API

---

### Task 2.2: HTTPS Enforcement & Security Headers
**File:** `web/api_server.py`
**Time:** 1-2 hours

- [ ] Add HTTPS redirect middleware (production only):
  ```python
  @app.before_request
  def force_https():
      if os.getenv('FLASK_ENV') == 'production':
          if not request.is_secure and request.headers.get('X-Forwarded-Proto') != 'https':
              return redirect(request.url.replace('http://', 'https://'), code=301)
  ```

- [ ] Add security headers:
  ```python
  @app.after_request
  def add_security_headers(response):
      response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
      response.headers['X-Content-Type-Options'] = 'nosniff'
      response.headers['X-Frame-Options'] = 'DENY'
      response.headers['X-XSS-Protection'] = '1; mode=block'
      response.headers['Content-Security-Policy'] = "default-src 'self'"
      return response
  ```

- [ ] Configure secure cookies:
  ```python
  app.config['SESSION_COOKIE_SECURE'] = True  # HTTPS only
  app.config['SESSION_COOKIE_HTTPONLY'] = True  # No JavaScript access
  app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'  # CSRF protection
  ```

**Actions:**
- [ ] Implement HTTPS redirect
- [ ] Add security headers
- [ ] Configure secure cookies
- [ ] Test in production environment
- [ ] Verify headers in browser DevTools

**Success Criteria:**
- HTTP redirects to HTTPS in production
- All security headers present
- Cookies secure and HttpOnly

---

## Phase 3: Enhanced Input Validation (6-8 hours)

### Task 3.1: Create Pydantic Models for All Endpoints
**File:** Create `web/models/` directory with request models
**Time:** 4-5 hours

- [ ] Create `web/models/requests.py` with pydantic models:
  ```python
  from pydantic import BaseModel, EmailStr, Field, validator
  
  class LoginRequest(BaseModel):
      email: EmailStr
      password: str = Field(..., min_length=8)
  
  class SignupRequest(BaseModel):
      email: EmailStr
      password: str = Field(..., min_length=8, max_length=128)
      username: str = Field(None, max_length=50)
  
  class CreateVideoRequest(BaseModel):
      topic: str = Field(..., min_length=5, max_length=200)
      duration: int = Field(..., ge=30, le=600)  # 30s to 10min
      # ... etc
  ```

- [ ] Create models for:
  - `/api/login` → `LoginRequest`
  - `/api/signup` → `SignupRequest`
  - `/api/create-video-enhanced` → `CreateVideoRequest`
  - `/api/post-process-video` → `PostProcessRequest`
  - `/api/publish-to-platform` → `PublishRequest`
  - All other POST/PUT endpoints

- [ ] Update endpoints to use models:
  ```python
  @app.route('/api/login', methods=['POST'])
  def api_login():
      try:
          req = LoginRequest(**request.json)
          # Now req.email and req.password are validated
      except PydanticValidationError as e:
          return jsonify({'success': False, 'error': e.errors()}), 400
  ```

**Actions:**
- [ ] Create `web/models/requests.py`
- [ ] Create models for all POST endpoints
- [ ] Update endpoints to validate requests
- [ ] Test with invalid inputs
- [ ] Return clear validation errors

**Success Criteria:**
- All POST endpoints use pydantic validation
- Invalid inputs rejected with clear errors
- No unvalidated user input reaches business logic

---

### Task 3.2: File Upload Validation Enhancement
**File:** `web/api_server.py`, create `web/utils/file_validation.py`
**Time:** 2-3 hours

- [ ] Create `web/utils/file_validation.py`:
  ```python
  import magic
  from PIL import Image
  
  ALLOWED_IMAGE_TYPES = ['image/png', 'image/jpeg', 'image/gif', 'image/webp']
  ALLOWED_VIDEO_TYPES = ['video/mp4', 'video/webm']
  
  def validate_image(file):
      # Check MIME type using magic bytes
      mime = magic.Magic(mime=True)
      file_type = mime.from_buffer(file.read(1024))
      file.seek(0)
      
      if file_type not in ALLOWED_IMAGE_TYPES:
          raise FileUploadError(f"Invalid image type: {file_type}")
      
      # Verify it's actually an image
      try:
          img = Image.open(file)
          img.verify()
          file.seek(0)
          return True
      except Exception:
          raise FileUploadError("File is not a valid image")
  
  def validate_file_size(file, max_size_mb=10):
      file.seek(0, 2)  # Seek to end
      size = file.tell()
      file.seek(0)
      if size > max_size_mb * 1024 * 1024:
          raise FileUploadError(f"File too large: {size} bytes")
      return True
  ```

- [ ] Update all upload endpoints to use validation
- [ ] Add virus scanning (optional - ClamAV integration)
- [ ] Sanitize filenames (remove special characters)

**Success Criteria:**
- Files validated by content, not just extension
- File size limits enforced
- Malicious files rejected

---

### Task 3.3: Input Sanitization (XSS Prevention)
**File:** `web/utils/sanitizers.py` (create new)
**Time:** 2-3 hours

- [ ] Install `bleach` for HTML sanitization:
  ```bash
  pip install bleach
  ```

- [ ] Create `web/utils/sanitizers.py`:
  ```python
  import bleach
  import html
  
  def sanitize_html(text: str) -> str:
      """Remove potentially dangerous HTML"""
      return bleach.clean(text, tags=[], strip=True)
  
  def sanitize_filename(filename: str) -> str:
      """Remove special characters from filename"""
      import re
      # Remove everything except alphanumeric, dots, dashes, underscores
      return re.sub(r'[^a-zA-Z0-9._-]', '', filename)
  
  def sanitize_url(url: str) -> str:
      """Validate and sanitize URLs"""
      from urllib.parse import urlparse
      parsed = urlparse(url)
      if parsed.scheme not in ['http', 'https']:
          raise ValidationError("Invalid URL scheme")
      return url
  ```

- [ ] Sanitize all user inputs before:
  - Database storage
  - Display in HTML
  - API responses

**Success Criteria:**
- No XSS vulnerabilities
- HTML properly escaped
- URLs validated

---

## Phase 4: Token & Credential Security (4-6 hours)

### Task 4.1: Implement Token Encryption
**File:** `web/utils/encryption.py` (create new)
**Time:** 3-4 hours

- [ ] Create encryption utility:
  ```python
  from cryptography.fernet import Fernet
  import os
  
  def get_encryption_key():
      key = os.getenv('ENCRYPTION_KEY')
      if not key:
          raise ValueError("ENCRYPTION_KEY environment variable not set")
      return key.encode()
  
  def encrypt_token(token: str) -> str:
      f = Fernet(get_encryption_key())
      return f.encrypt(token.encode()).decode()
  
  def decrypt_token(encrypted_token: str) -> str:
      f = Fernet(get_encryption_key())
      return f.decrypt(encrypted_token.encode()).decode()
  ```

- [ ] Update `database.py` to encrypt tokens before storing
- [ ] Update `platform_apis.py` to decrypt tokens when using
- [ ] Create migration script for existing tokens
- [ ] Add `ENCRYPTION_KEY` to `.env.example`

**Success Criteria:**
- All tokens encrypted in database
- Decryption works correctly
- Existing tokens migrated

---

### Task 4.2: Token Rotation & Expiration
**File:** `web/platform_apis.py`
**Time:** 1-2 hours

- [ ] Add token expiration checks
- [ ] Implement automatic token refresh (before expiration)
- [ ] Add token rotation mechanism
- [ ] Store token expiration dates
- [ ] Handle expired tokens gracefully

**Success Criteria:**
- Tokens refreshed automatically
- Expired tokens detected and handled

---

## Phase 5: Security Monitoring & Logging (4-6 hours)

### Task 5.1: Security Event Logging
**File:** `web/utils/security_logging.py` (create new)
**Time:** 2-3 hours

- [ ] Create security logging utility:
  ```python
  import logging
  from datetime import datetime
  
  security_logger = logging.getLogger('security')
  
  def log_failed_login(email: str, ip_address: str):
      security_logger.warning(f"Failed login attempt: {email} from {ip_address}")
  
  def log_suspicious_activity(event: str, user_id: int, details: dict):
      security_logger.warning(f"Suspicious activity: {event}", extra={
          'user_id': user_id,
          'details': details,
          'timestamp': datetime.utcnow().isoformat()
      })
  ```

- [ ] Log:
  - Failed login attempts
  - Multiple failed logins from same IP
  - Unusual API usage patterns
  - File upload violations
  - SQL injection attempts (if detected)

**Success Criteria:**
- Security events logged
- Logs searchable and actionable

---

### Task 5.2: IP-Based Rate Limiting & Blocking
**File:** `web/api_server.py`
**Time:** 2-3 hours

- [ ] Enhance Flask-Limiter configuration:
  ```python
  from flask_limiter import Limiter
  from flask_limiter.util import get_remote_address
  
  limiter = Limiter(
      app=app,
      key_func=get_remote_address,
      default_limits=["200 per day", "50 per hour"],
      storage_uri="redis://localhost:6379"  # Use Redis for distributed rate limiting
  )
  ```

- [ ] Add per-endpoint limits:
  ```python
  @limiter.limit("5 per minute")
  @app.route('/api/login', methods=['POST'])
  def api_login():
      ...
  ```

- [ ] Implement IP blocking for brute force:
  - Track failed login attempts per IP
  - Block IP after 5 failed attempts in 15 minutes
  - Store blocked IPs (Redis or database)
  - Unblock after timeout

**Success Criteria:**
- Rate limiting active on all endpoints
- Brute force protection working
- IP blocking functional

---

## Testing & Verification

### Security Test Suite
**File:** `tests/test_security.py` (create new)
**Time:** 2-3 hours

- [ ] Create tests for:
  - SQL injection attempts
  - XSS attempts
  - File upload security
  - CORS restrictions
  - Rate limiting
  - Token encryption
  - Input validation

- [ ] Run security scanning tools:
  - `bandit` (Python security linter)
  - `safety` (dependency vulnerability checker)
  - OWASP ZAP (web security scanner)

**Commands:**
```bash
pip install bandit safety
bandit -r web/
safety check
```

---

## Checklist Summary

- [ ] Phase 1: Security Audit Complete
  - [ ] All SQL queries parameterized
  - [ ] File uploads secured
  - [ ] Tokens encrypted
- [ ] Phase 2: CORS & HTTPS Complete
  - [ ] CORS restricted
  - [ ] HTTPS enforced
  - [ ] Security headers added
- [ ] Phase 3: Input Validation Complete
  - [ ] Pydantic models for all endpoints
  - [ ] File validation enhanced
  - [ ] Input sanitization active
- [ ] Phase 4: Token Security Complete
  - [ ] Token encryption working
  - [ ] Token rotation implemented
- [ ] Phase 5: Security Monitoring Complete
  - [ ] Security logging active
  - [ ] Rate limiting enhanced
  - [ ] IP blocking functional
- [ ] Testing Complete
  - [ ] Security tests passing
  - [ ] Vulnerability scans clean

---

## Next Steps After Completion

1. Merge `agent1-security` branch to `main`
2. Notify Agent 2 that security fixes are complete
3. Document security improvements in `SECURITY_IMPROVEMENTS.md`
4. Prepare for penetration testing

---

**Status:** Ready to start
**Start Date:** ___________
**Target Completion:** ___________

