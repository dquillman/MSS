# Manual Testing Steps

## 🚀 Quick Start

1. **Start the server:**
   ```bash
   cd web
   python api_server.py
   ```

2. **Open browser:** `http://localhost:5000`

---

## ✅ Testing Checklist

### Security (Agent 1)

#### Session Management
- [ ] **Login without Remember Me**
  1. Go to `/auth`
  2. Enter credentials
  3. DON'T check "Remember Me"
  4. Open DevTools → Application → Cookies
  5. Check `session_id` cookie expiration (should be ~7 days)

- [ ] **Login with Remember Me**
  1. Go to `/auth`
  2. Enter credentials
  3. CHECK "Remember Me"
  4. Check cookie expiration (should be ~30 days)

#### Rate Limiting
- [ ] **Test Login Rate Limit**
  1. Go to `/auth`
  2. Enter wrong password
  3. Click "Sign In" 6 times rapidly
  4. Should see "Too many login attempts" error after 5th attempt
  5. Wait 1 minute, try again → Should work

#### File Upload Security
- [ ] **Test Invalid File Type**
  1. Go to logo manager or intro/outro upload
  2. Try uploading `.exe` file → Should reject
  3. Try uploading `.php` file → Should reject
  4. Verify friendly error message

- [ ] **Test File Size Limits**
  1. Try uploading large file (>100MB for videos, >10MB for logos)
  2. Should reject with friendly error message

---

### Exception Handling (Agent 2)

#### File Serving
- [ ] **Test Non-Existent Files**
  1. Try accessing `/out/nonexistent.mp4`
  2. Should return 404 (not crash)
  3. Check browser console → No errors

- [ ] **Test Invalid Metadata Request**
  1. Try `/api/video/metadata/nonexistent.mp4`
  2. Should return 404 with friendly message
  3. Check server logs → Should log properly

#### Video Management
- [ ] **Test Delete Non-Existent Video**
  1. Try deleting video that doesn't exist
  2. Should return 404 with friendly message
  3. Server should NOT crash

---

### Frontend (Agent 3)

#### Authentication Forms
- [ ] **Test Loading States**
  1. Click "Sign In" button
  2. Button should:
     - Disable immediately
     - Show "Signing in..." text
     - Have opacity 0.7
     - Cursor should be "not-allowed"
  3. After response, button should re-enable

- [ ] **Test Form Validation**
  1. Try submitting empty form → Should show error BEFORE API call
  2. Enter invalid email (`test@`) → Should show error
  3. Enter password < 8 chars → Should show error
  4. All errors should be friendly

- [ ] **Test Error Messages**
  1. Enter wrong password → Should see "Invalid email or password" (not "401")
  2. Hit rate limit → Should see "Too many attempts" (not "Rate limit exceeded")
  3. Network error → Should see "Connection problem" (not "NetworkError")

#### Mobile Responsiveness
- [ ] **Test All Pages on Mobile**
  1. Press F12 → Toggle Device Toolbar (Ctrl+Shift+M)
  2. Select iPhone or Android device
  3. Test each page:
     - `/auth` - Forms should stack, buttons full-width
     - `/studio` - Cards should stack
     - `/dashboard` - Stats should stack vertically
     - `/workflow` - Steps should stack
     - `/multi-platform` - Platform cards should stack
     - `/trends-calendar` - Calendar grid should stack
     - `/settings` - Forms should stack

- [ ] **Test on Actual Device**
  1. Connect phone to same network
  2. Find your computer's IP: `ipconfig` (Windows) or `ifconfig` (Mac/Linux)
  3. Open `http://YOUR_IP:5000/auth` on phone
  4. Verify everything works and looks good

---

## 🎯 Key Things to Verify

### ✅ Security
- Rate limiting works (5 attempts/minute)
- Sessions are correct duration (7 vs 30 days)
- File uploads are validated (type + size)
- HTTPS redirects in production

### ✅ Error Handling
- Errors return proper status codes (404, 400, 403, 500)
- Error messages are user-friendly
- Server doesn't crash on errors
- Errors are logged properly

### ✅ Frontend
- Loading states visible
- Form validation works
- Error messages are friendly
- Mobile layouts work
- No console errors

---

## 🐛 If Something Doesn't Work

1. **Check Browser Console** (F12 → Console tab)
   - Look for JavaScript errors
   
2. **Check Network Tab** (F12 → Network tab)
   - See actual API responses
   - Check status codes
   
3. **Check Server Logs**
   - Look for error messages
   - Check if exceptions are logged properly

4. **Check Cookie Settings**
   - DevTools → Application → Cookies
   - Verify session cookie expiration

---

## 📱 Mobile Testing Shortcuts

**Browser DevTools:**
- Windows/Linux: `Ctrl+Shift+M`
- Mac: `Cmd+Shift+M`

**Common Devices to Test:**
- iPhone 12/13/14 (390px width)
- iPhone 14 Pro Max (430px width)
- iPad (768px width)
- Samsung Galaxy (360px width)

---

**Ready to test!** Start with the security tests, then move to frontend. 🚀

