# Work Division Plan for 3 Agents

## Overview
This document outlines how to divide MSS development work among 3 parallel agents to maximize efficiency and minimize conflicts.

## Strategy
- **Agent 1**: Security & Infrastructure (Critical fixes, database, infrastructure)
- **Agent 2**: Code Quality & Refactoring (Blueprint splitting, testing, code organization)
- **Agent 3**: Features & Enhancements (New features, UI improvements, integrations)

---

## 🔴 AGENT 1: Security & Infrastructure Specialist

### Priority: HIGH - Must complete before moving to production

**Files to Own:**
- `web/database.py` (primary)
- `web/api_server.py` (security-related sections only)
- `web/platform_apis.py` (security audit)
- `requirements.txt` (add security dependencies)

**Tasks (Week 1-2):**

1. **Complete Security Audit** (6-8 hours)
   - [ ] Audit all SQL queries for injection risks
   - [ ] Fix string formatting → parameterized queries
   - [ ] Review all file upload endpoints for security
   - [ ] Audit token storage (encrypt sensitive tokens)

2. **Session Management** (2-3 hours)
   - [ ] Reduce session duration from 30 days → 7 days
   - [ ] Add "Remember Me" option (30-day sessions only with explicit opt-in)
   - [ ] Add session refresh mechanism
   - [ ] Implement session invalidation on password change

3. **Rate Limiting** (3-4 hours)
   - [ ] Install Flask-Limiter
   - [ ] Add rate limits to auth endpoints (5 attempts/min)
   - [ ] Add rate limits to video generation (based on subscription tier)
   - [ ] Add rate limits to API endpoints (100 req/min per IP)

4. **Input Validation Expansion** (4-6 hours)
   - [ ] Create pydantic models for all POST endpoints
   - [ ] Validate file uploads (type, size, content)
   - [ ] Sanitize user inputs (XSS prevention)
   - [ ] Validate API keys format

5. **PostgreSQL Migration Prep** (6-8 hours)
   - [ ] Create migration script (SQLite → PostgreSQL)
   - [ ] Test database connection pooling
   - [ ] Update database.py to support both SQLite (dev) and PostgreSQL (prod)
   - [ ] Add Alembic for schema migrations

**Dependencies:**
- Must complete before Agent 2 can safely refactor
- Agent 2 should wait for security fixes before blueprint splitting

**Estimated Time:** 21-29 hours

---

## 🟡 AGENT 2: Code Quality & Refactoring Specialist

### Priority: MEDIUM - Can work in parallel after Agent 1 completes security fixes

**Files to Own:**
- `web/api_server.py` (refactoring into blueprints)
- `web/api/` (new directory - create blueprints)
- `tests/` (new directory - create test suite)
- `web/database.py` (only after Agent 1 completes security fixes)

**Tasks (Week 2-4):**

1. **Blueprint Architecture Setup** (4-6 hours)
   - [ ] Create `web/api/__init__.py`
   - [ ] Create `web/api/auth.py` blueprint
   - [ ] Create `web/api/videos.py` blueprint
   - [ ] Create `web/api/platforms.py` blueprint
   - [ ] Create `web/api/analytics.py` blueprint
   - [ ] Create `web/api/trends.py` blueprint
   - [ ] Create `web/api/assets.py` blueprint (avatars, logos, thumbnails)

2. **Refactor Auth Routes** (3-4 hours)
   - [ ] Move `/api/login`, `/api/signup` to `web/api/auth.py`
   - [ ] Move password reset endpoints
   - [ ] Move session management endpoints
   - [ ] Test authentication flow

3. **Refactor Video Routes** (4-6 hours)
   - [ ] Move `/create-video-enhanced` to `web/api/videos.py`
   - [ ] Move `/post-process-video` to `web/api/videos.py`
   - [ ] Move topic generation endpoints
   - [ ] Move script generation endpoints
   - [ ] Test video creation flow

4. **Refactor Platform Routes** (3-4 hours)
   - [ ] Move platform publishing endpoints to `web/api/platforms.py`
   - [ ] Move OAuth endpoints
   - [ ] Move channel management endpoints
   - [ ] Test publishing flow

5. **Exception Handling** (4-6 hours)
   - [ ] Replace bare `except Exception: pass` with specific exceptions
   - [ ] Add proper error logging
   - [ ] Create custom exception classes
   - [ ] Add error handling middleware

6. **Test Suite Setup** (16-20 hours)
   - [ ] Install pytest and fixtures
   - [ ] Create `tests/conftest.py` with fixtures
   - [ ] Write unit tests for `database.py` functions
   - [ ] Write unit tests for auth endpoints
   - [ ] Write integration tests for video creation
   - [ ] Write E2E tests for full workflow
   - [ ] Set up CI/CD test running

**Dependencies:**
- Should wait for Agent 1's security fixes before blueprint splitting
- Can start test suite setup immediately

**Estimated Time:** 34-46 hours

**Proposed Blueprint Structure:**
```
web/
├── api/
│   ├── __init__.py          # Register all blueprints
│   ├── auth.py              # Login, signup, sessions (~300 lines)
│   ├── videos.py            # Video creation, processing (~800 lines)
│   ├── platforms.py         # Publishing, OAuth (~600 lines)
│   ├── analytics.py         # Analytics endpoints (~200 lines)
│   ├── trends.py            # Trends calendar (~200 lines)
│   └── assets.py            # Avatars, logos, thumbnails (~400 lines)
├── api_server.py            # Main app (now ~200 lines, just imports)
└── ...
```

---

## 🟢 AGENT 3: Features & Enhancements Specialist

### Priority: LOW-MEDIUM - Can work independently, mostly parallel

**Files to Own:**
- `web/topic-picker-standalone/*.html` (frontend)
- `scripts/` (new features)
- `web/analytics.py` (enhancements)
- `web/trend_calendar.py` (enhancements)

**Tasks (Week 1-4):**

1. **Frontend Improvements** (8-12 hours)
   - [ ] Fix UI/UX inconsistencies
   - [ ] Add loading states to all async operations
   - [ ] Improve error messages (user-friendly)
   - [ ] Add form validation on frontend
   - [ ] Mobile responsiveness improvements

2. **Redis Caching** (6-8 hours)
   - [ ] Install redis-py
   - [ ] Add caching for topic generation (5 min TTL)
   - [ ] Cache user sessions
   - [ ] Cache platform API responses
   - [ ] Add cache invalidation strategies

3. **Analytics Enhancements** (6-8 hours)
   - [ ] Add more metrics (retention curves, demographics)
   - [ ] Create performance score algorithm
   - [ ] Add export functionality (CSV, PDF)
   - [ ] Create analytics dashboard improvements
   - [ ] Add trend analysis

4. **Trends Calendar Improvements** (4-6 hours)
   - [ ] Integrate real YouTube Trending API
   - [ ] Add Google Calendar export
   - [ ] Add email notifications for hot trends
   - [ ] Improve topic filtering by niche

5. **Documentation** (4-6 hours)
   - [ ] Create OpenAPI/Swagger spec
   - [ ] Add API documentation endpoint (`/api/docs`)
   - [ ] Update README with new features
   - [ ] Create developer onboarding guide

6. **Admin Dashboard** (12-16 hours)
   - [ ] Create admin routes in API
   - [ ] User management interface
   - [ ] Subscription management
   - [ ] System health monitoring
   - [ ] Usage analytics per user

**Dependencies:**
- Mostly independent
- Redis caching can be done anytime
- Admin dashboard should wait for Agent 2's blueprint refactoring

**Estimated Time:** 40-56 hours

---

## 🚦 Coordination & Conflict Prevention

### File Ownership Rules:
- **Agent 1**: `web/database.py`, security sections of `web/api_server.py`
- **Agent 2**: `web/api_server.py` (refactoring), `web/api/` (new), `tests/`
- **Agent 3**: Frontend files, `scripts/`, feature modules

### Communication Protocol:
1. **Daily Standup**: Share what you're working on
2. **Conflict Resolution**: 
   - If two agents need same file → Agent 1 (security) has priority
   - Agent 2 should wait for Agent 1's security fixes
   - Agent 3 can work independently on frontend/features

### Merge Strategy:
1. **Agent 1 merges first** (security fixes)
2. **Agent 2 merges second** (refactoring on top of secure code)
3. **Agent 3 merges last** (features on top of refactored code)

### Git Branch Strategy:
```
main
├── agent1-security (merge first)
├── agent2-refactoring (merge second)
└── agent3-features (merge last)
```

---

## 📊 Timeline Estimate

**Week 1:**
- Agent 1: Security fixes (21-29h)
- Agent 2: Test setup, exception handling (8-12h)
- Agent 3: Frontend improvements, Redis caching (14-20h)

**Week 2:**
- Agent 1: PostgreSQL migration prep (6-8h)
- Agent 2: Blueprint splitting (14-24h)
- Agent 3: Analytics enhancements, documentation (10-14h)

**Week 3-4:**
- Agent 1: Monitoring, final security audit (4-6h)
- Agent 2: Complete test suite (16-20h)
- Agent 3: Admin dashboard, trends improvements (20-28h)

**Total Estimated Time:** ~95-135 hours across 3 agents (~4-6 weeks)

---

## ✅ Success Criteria

**Agent 1 Complete When:**
- ✅ All SQL injection risks fixed
- ✅ Rate limiting implemented
- ✅ Session management secure
- ✅ PostgreSQL migration ready

**Agent 2 Complete When:**
- ✅ API split into 6+ blueprints
- ✅ All routes tested
- ✅ Exception handling improved
- ✅ >80% test coverage

**Agent 3 Complete When:**
- ✅ Redis caching implemented
- ✅ Admin dashboard functional
- ✅ API documentation complete
- ✅ Frontend improvements deployed

---

## 🎯 Quick Start Commands for Each Agent

### Agent 1 (Security):
```bash
git checkout -b agent1-security
# Work on database.py, security fixes
```

### Agent 2 (Refactoring):
```bash
git checkout -b agent2-refactoring
# Wait for agent1-security merge, then refactor
```

### Agent 3 (Features):
```bash
git checkout -b agent3-features
# Work independently on frontend/features
```

---

## 📝 Notes

- **Agent 1 should prioritize security** - these are blockers for production
- **Agent 2 should coordinate with Agent 1** - don't refactor insecure code
- **Agent 3 can work freely** - features are independent
- **All agents should write tests** for their changes
- **Use pydantic models** for all new endpoints (Agent 1's pattern)

---

**Last Updated:** 2025-01-XX
**Status:** Ready for execution

