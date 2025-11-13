# 🚀 Quick Start Guide

## Start the Server

The route `/auth` exists, but you need to **start the server first**!

> **Cloud SQL users:** set a `DATABASE_URL` environment variable (e.g. `postgresql://USER:PASSWORD@/mss?host=/cloudsql/PROJECT:REGION:INSTANCE`) before starting the server so the app connects to your Google Cloud SQL database instead of the local SQLite file.

### Step 1: Start the Server

Open PowerShell in the project root and run:

```powershell
cd web
python api_server.py
```

**OR** if you're already in the `web` directory:

```powershell
python api_server.py
```

### Step 2: Wait for Server to Start

You should see output like:
```
 * Running on http://127.0.0.1:5000
 * Running on http://[::1]:5000
```

**Keep this terminal window open!** The server needs to keep running.

### Step 3: Open Browser

Once server is running, open:
- `http://localhost:5000/auth`
- OR `http://127.0.0.1:5000/auth`

Both should work!

---

## ✅ Available Pages

Once server is running, these URLs work:

- `http://localhost:5000/` - Landing page
- `http://localhost:5000/auth` - Login/Signup
- `http://localhost:5000/studio` - Studio
- `http://localhost:5000/dashboard` - Dashboard
- `http://localhost:5000/workflow` - Workflow
- `http://localhost:5000/trends-calendar` - Trends
- `http://localhost:5000/multi-platform` - Multi-platform publisher
- `http://localhost:5000/settings` - Settings

---

## 🔍 Troubleshooting

### "Connection Refused" or "This site can't be reached"
→ **Server is not running!** Start it with `python api_server.py`

### "Port already in use"
→ Another server is running on port 5000. Kill it or use a different port.

### File not found errors
→ Make sure you're running from the `web` directory!

---

## 🎯 Testing Checklist

Once server is running:

1. ✅ Server shows "Running on http://127.0.0.1:5000"
2. ✅ Browser opens `http://localhost:5000/auth`
3. ✅ Login/Signup form appears
4. ✅ Can test rate limiting (6 rapid login attempts)
5. ✅ Can test mobile responsiveness (F12 → Device Toolbar)

---

**The server needs to be running for the routes to work!** 🚀

