# ✅ Server Start Instructions - FINAL

## The Fix: Python Path Issue

The server needs the parent directory in Python's path. This is now fixed!

---

## 🚀 Start the Server

**From project root (`G:\Users\daveq\MSS`):**

```powershell
python web/api_server.py
```

**OR** use PYTHONPATH:

```powershell
$env:PYTHONPATH = "$PWD"
python web/api_server.py
```

---

## ✅ What Should Happen

You should see:
```
[SERVER] Starting Flask server on http://127.0.0.1:5000
[SERVER] Debug mode: False
 * Running on http://127.0.0.1:5000
Press CTRL+C to quit
```

---

## 🌐 Then Test

Once server is running:
- `http://localhost:5000/auth` ✅
- `http://localhost:5000/studio` ✅
- `http://localhost:5000/dashboard` ✅

---

## 🎯 Quick Test Checklist

- [ ] Server starts without errors
- [ ] See "Running on http://127.0.0.1:5000"
- [ ] Browser opens `/auth` page
- [ ] Can see login/signup forms
- [ ] Can test rate limiting (6 rapid login attempts)
- [ ] Can test mobile responsiveness (F12 → Device Toolbar)

---

**The path issue is fixed! Try starting the server now.** 🚀

