# How to Test MSS - Fixed Routes

## 🚀 Starting the Server

### Option 1: Direct Python Run
```bash
cd web
python api_server.py
```

### Option 2: Flask CLI
```bash
cd web
flask --app api_server run
```

### Option 3: With Port Specified
```bash
cd web
python api_server.py
# Server will start on http://127.0.0.1:5000
```

---

## ✅ Available Routes

### Authentication Pages
- `http://localhost:5000/auth` ✅
- `http://localhost:5000/auth.html` ✅
- `http://localhost:5000/login` ✅
- `http://localhost:5000/signup` ✅

### Main Pages
- `http://localhost:5000/` - Landing page
- `http://localhost:5000/studio` - Studio page
- `http://localhost:5000/dashboard` - Dashboard
- `http://localhost:5000/workflow` - Workflow
- `http://localhost:5000/trends-calendar` - Trends & Calendar

### Alternative URLs
If `localhost` doesn't work, try:
- `http://127.0.0.1:5000/auth`
- `http://127.0.0.1:5000/studio`

---

## 🔍 Troubleshooting

### Issue: "This page isn't working" or Connection Refused

**Check 1: Is the server running?**
```bash
# Check if Python is running
Get-Process python

# Check if port 5000 is in use
netstat -ano | findstr :5000
```

**Check 2: Start the server**
```bash
cd web
python api_server.py
```

Look for output like:
```
 * Running on http://127.0.0.1:5000
```

**Check 3: Try different URL**
- If `localhost` doesn't work → Try `127.0.0.1`
- If port 5000 doesn't work → Check what port is shown in server output

### Issue: 404 Not Found

**Check if file exists:**
```bash
Test-Path web\topic-picker-standalone\auth.html
```

Should return: `True`

**Check server output:**
- Look for error messages in terminal
- Check if it says "File not found"

### Issue: Permission Denied

**Run as Administrator:**
- Right-click PowerShell → Run as Administrator
- Then start server

---

## ✅ Quick Test Steps

1. **Start Server:**
   ```bash
   cd web
   python api_server.py
   ```

2. **Wait for:**
   ```
   * Running on http://127.0.0.1:5000
   ```

3. **Open Browser:**
   - `http://127.0.0.1:5000/auth`
   - OR `http://localhost:5000/auth`

4. **If still doesn't work:**
   - Check server terminal for errors
   - Try `http://127.0.0.1:5000/` first (landing page)
   - Check firewall settings

---

## 🔧 Common Issues

### Port Already in Use
If you see "Address already in use":
```bash
# Find what's using port 5000
netstat -ano | findstr :5000

# Kill the process (replace PID with actual process ID)
taskkill /PID <PID> /F
```

### File Not Found Error
Make sure you're running from the correct directory:
```bash
# Should be in: G:\Users\daveq\MSS\web
cd web
python api_server.py
```

---

## 📝 Quick Test Checklist

- [ ] Server is running (see output in terminal)
- [ ] No errors in server terminal
- [ ] Browser opens `http://127.0.0.1:5000/auth`
- [ ] Page loads (should see login form)
- [ ] Can click "Sign In" or "Sign Up" tabs
- [ ] Forms are visible

---

**Need help?** Share the error message you're seeing!

