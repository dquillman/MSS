# Testing Guide - MSS Agent Improvements

**Date:** 2025-01-XX  
**Status:** Complete Testing Guide for All Improvements

---

## 🧪 Quick Test Checklist

### ✅ Security Features (Agent 1)

#### 1. Session Management
- [ ] **Test Default Session (7 days)**
  1. Log in WITHOUT checking "Remember Me"
  2. Check cookie expiration (should be ~7 days from now)
  3. Verify session expires after 7 days

- [ ] **Test Remember Me (30 days)**
  1. Log in WITH "Remember Me" checked
  2. Check cookie expiration (should be ~30 days from now)
  3. Verify session lasts 30 days

#### 2. Rate Limiting
- [ ] **Test Auth Rate Limits**
  1. Try logging in 6 times rapidly (should fail on 6th attempt)
  2. Wait 1 minute, try again (should work)
  3. Try signup 6 times rapidly (should fail on 6th attempt)

- [ ] **Test Rate Limit Error Message**
  1. Hit rate limit
  2. Verify friendly error message shown (not technical error)

#### 3. File Upload Security
- [ ] **Test File Type Validation**
  1. Try uploading `.exe` file → Should reject
  2. Try uploading `.php` file → Should reject
  3. Try uploading `.png` file → Should accept
  4. Try uploading `.mp4` file → Should accept

- [ ] **Test File Size Limits**
  1. Try uploading 101MB video → Should reject (max 100MB)
  2. Try uploading 11MB image → Should reject (max 10MB for logos)
  3. Try uploading 5MB file → Should accept

#### 4. HTTPS Enforcement
- [ ] **Test HTTPS Redirect (Production)**
  - Set `ENFORCE_HTTPS=true` in environment
  - Try accessing via HTTP → Should redirect to HTTPS

---

### ✅ Exception Handling (Agent 2)

#### 1. File Serving Endpoints
- [ ] **Test `/out/<filename>`**
  1. Request non-existent file → Should return 404 with friendly message
  2. Check logs for proper error level

- [ ] **Test `/avatars/<filename>`**
  1. Request non-existent avatar → Should return 404
  2. Verify proper error handling

- [ ] **Test `/thumbnails/<filename>`**
  1. Request non-existent thumbnail → Should return 404
  2. Verify proper error handling

#### 2. Video Management
- [ ] **Test `/delete-video`**
  1. Delete non-existent video → Should return 404 with friendly message
  2. Delete valid video → Should succeed
  3. Try path traversal attack (`../../../etc/passwd`) → Should reject

- [ ] **Test `/get-recent-videos`**
  1. When `out/` directory doesn't exist → Should return empty array (not error)
  2. Check logs for proper handling

#### 3. API Endpoints
- [ ] **Test `/api/video/metadata`**
  1. Request metadata for non-existent video → Should return 404
  2. Send invalid JSON → Should return 400 with friendly message
  3. Check error logs

- [ ] **Test `/generate-topics`**
  1. Send invalid input → Should return 400
  2. Check error messages are user-friendly

- [ ] **Test `/generate-ai-thumbnail`**
  1. Missing title → Should return 400
  2. Invalid input → Should return proper error

---

### ✅ Frontend Improvements (Agent 3)

#### 1. Authentication Forms
- [ ] **Test Loading States**
  1. Click "Sign In" → Button should disable, show "Signing in..."
  2. Button should have opacity 0.7 and cursor not-allowed
  3. After response, button should re-enable

- [ ] **Test Form Validation**
  1. Try submitting empty form → Should show error
  2. Enter invalid email (`test@` → Should show error
  3. Enter password < 8 chars → Should show error
  4. Verify errors appear BEFORE API call

- [ ] **Test Error Messages**
  1. Enter wrong password → Should show friendly message (not "401 Unauthorized")
  2. Hit rate limit → Should show friendly message
  3. Network error → Should show friendly message

- [ ] **Test Remember Me**
  1. Check "Remember Me" → Should extend session to 30 days
  2. Uncheck → Should use 7-day session

#### 2. Mobile Responsiveness
- [ ] **Test Auth Page (`auth.html`)**
  - Tablet (768px): Forms should stack vertically, buttons full-width
  - Phone (480px): Compact layout, tabs stack vertically
  - iOS: No zoom on input focus (font-size: 16px)

- [ ] **Test Studio Page (`studio.html`)**
  - Tablet: Cards stack, buttons full-width
  - Phone: Compact layout

- [ ] **Test Dashboard (`dashboard.html`)**
  - Tablet: Stats grid becomes single column
  - Phone: All cards stack vertically

- [ ] **Test Workflow (`workflow.html`)**
  - Tablet: Steps stack, buttons full-width
  - Phone: Compact step cards

- [ ] **Test Multi-Platform (`multi-platform.html`)**
  - Tablet: Platform grid becomes single column
  - Phone: Cards stack, forms adjust

- [ ] **Test Trends Calendar (`trends-calendar.html`)**
  - Tablet: Calendar grid becomes single column
  - Phone: Trend cards compact, tabs wrap

- [ ] **Test Settings (`settings.html`)**
  - Tablet: Grid becomes single column
  - Phone: Forms stack vertically

**How to Test Mobile:**
1. **Browser DevTools**: F12 → Toggle Device Toolbar (Ctrl+Shift+M)
2. **Resize Browser**: Drag window to different sizes
3. **Test Actual Devices**: Use real phone/tablet

---

## 🚀 Quick Start Testing

### Start the Server
```bash
# From project root
cd web
python api_server.py
# OR
flask --app api_server run
```

### Test Authentication
1. Open `http://localhost:5000/auth`
2. Try invalid login → See friendly error
3. Try valid login → Should redirect
4. Check browser DevTools → Network tab → See loading states

### Test Rate Limiting
```bash
# In PowerShell/Terminal
# Try rapid login attempts
for ($i=1; $i -le 10; $i++) {
    Invoke-WebRequest -Uri "http://localhost:5000/api/login" -Method POST -Body '{"email":"test@test.com","password":"test12345"}' -ContentType "application/json"
}
# Should see rate limit error after 5 attempts
```

### Test Mobile Responsiveness
1. Open any page (e.g., `http://localhost:5000/studio`)
2. Press F12 → Toggle Device Toolbar (Ctrl+Shift+M)
3. Select different devices (iPhone, iPad, etc.)
4. Verify layout adjusts properly

---

## 🔍 Detailed Testing Scenarios

### Scenario 1: Complete Login Flow
1. **Open** `http://localhost:5000/auth`
2. **Enter invalid credentials** → See friendly error message
3. **Enter valid credentials** → Button shows "Signing in..."
4. **Check Remember Me** → Session extends to 30 days
5. **Verify redirect** → Goes to `/studio` or `/dashboard`

### Scenario 2: File Upload Security
1. **Try uploading .exe file** → Should reject with error
2. **Try uploading 150MB video** → Should reject (max 100MB)
3. **Try uploading valid .mp4** → Should accept
4. **Check filename** → Should be sanitized (no special chars)

### Scenario 3: Exception Handling
1. **Request non-existent file** → `/out/nonexistent.mp4`
   - Should return 404 (not 500)
   - Should log error properly
   - Should show friendly message

2. **Delete non-existent video**
   - Should return 404 with friendly message
   - Should NOT crash server

### Scenario 4: Mobile Experience
1. **Open dashboard on phone**
   - Stats cards should stack vertically
   - Buttons should be full-width
   - Text should be readable without zoom

2. **Test forms**
   - Inputs should be large enough (16px font)
   - No iOS zoom on focus
   - Buttons easily tappable

---

## 🐛 Testing Tools

### Browser DevTools
- **Network Tab**: Check API responses, error codes
- **Console Tab**: Check for JavaScript errors
- **Application Tab**: Check cookies, localStorage
- **Device Toolbar**: Test mobile responsiveness

### API Testing
```bash
# Test login endpoint
curl -X POST http://localhost:5000/api/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@test.com","password":"test12345","remember_me":true}'

# Test rate limiting
for i in {1..10}; do 
  curl -X POST http://localhost:5000/api/login \
    -H "Content-Type: application/json" \
    -d '{"email":"test@test.com","password":"wrong"}'
done
```

### Python Testing Script
```python
# test_improvements.py
import requests

BASE_URL = "http://localhost:5000"

# Test 1: Rate limiting
print("Testing rate limiting...")
for i in range(6):
    resp = requests.post(f"{BASE_URL}/api/login", json={
        "email": "test@test.com",
        "password": "wrong"
    })
    print(f"Attempt {i+1}: {resp.status_code} - {resp.json().get('error', 'OK')}")

# Test 2: Exception handling
print("\nTesting exception handling...")
resp = requests.get(f"{BASE_URL}/out/nonexistent.mp4")
print(f"Non-existent file: {resp.status_code}")

# Test 3: File upload security
print("\nTesting file upload security...")
files = {'file': ('test.exe', b'fake content', 'application/x-msdownload')}
resp = requests.post(f"{BASE_URL}/upload-intro-outro-file", files=files)
print(f"Invalid file type: {resp.status_code} - {resp.json().get('error')}")
```

---

## ✅ Expected Results

### Security Tests
- ✅ Rate limiting: 5 attempts/minute max
- ✅ Session: 7 days default, 30 days with Remember Me
- ✅ File uploads: Only allowed types, size limits enforced
- ✅ HTTPS: Redirects in production

### Exception Handling Tests
- ✅ All errors return proper HTTP status codes
- ✅ Error messages are user-friendly (not technical)
- ✅ Errors are logged properly
- ✅ Server doesn't crash on errors

### Frontend Tests
- ✅ Loading states visible on all async operations
- ✅ Form validation prevents invalid submissions
- ✅ Error messages are friendly and helpful
- ✅ Mobile layouts work on all screen sizes

---

## 📋 Manual Testing Checklist

Print this and check off as you test:

**Security:**
- [ ] Login with Remember Me → 30-day session
- [ ] Login without Remember Me → 7-day session
- [ ] Hit rate limit → Friendly error message
- [ ] Upload invalid file type → Rejected
- [ ] Upload file too large → Rejected

**Exception Handling:**
- [ ] Access non-existent file → 404, not crash
- [ ] Invalid API input → 400 with friendly message
- [ ] Permission error → 403 with friendly message
- [ ] Check logs → Proper error logging

**Frontend:**
- [ ] Login form → Loading state, validation, errors
- [ ] Mobile view → Responsive layout
- [ ] Error messages → User-friendly
- [ ] All pages → Mobile-responsive

---

## 🎯 Performance Testing

### Load Testing (Optional)
```bash
# Install Apache Bench (or use similar)
ab -n 100 -c 10 http://localhost:5000/api/login

# Test rate limiting holds up under load
```

---

## 📝 Reporting Issues

If you find issues, note:
1. **Page/Endpoint**: Which page or API endpoint
2. **Action**: What you did
3. **Expected**: What should happen
4. **Actual**: What actually happened
5. **Browser/Device**: Which browser and device
6. **Console Errors**: Any JavaScript errors

---

**Happy Testing!** 🎉

