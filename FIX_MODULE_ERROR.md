# 🔧 Fix: Module 'web' Not Found

## Solution: Set PYTHONPATH

The server needs to find the `web` module. Run this:

```powershell
# Set PYTHONPATH to current directory
$env:PYTHONPATH = "$PWD"

# Start server
python web/api_server.py
```

**OR** use this one-liner:

```powershell
$env:PYTHONPATH = "G:\Users\daveq\MSS"; python web/api_server.py
```

---

## ✅ Alternative: Use Python -m Flag

```powershell
# From project root
python -m web.api_server
```

---

## 🔍 Why This Happens

Python needs to know where to find the `web` module. Setting `PYTHONPATH` tells Python to look in the current directory.

---

## 📝 Quick Fix Script

Save this as `start_server.ps1`:

```powershell
# Start MSS Server
$env:PYTHONPATH = "$PWD"
python web/api_server.py
```

Then just run: `.\start_server.ps1`

---

**Try the PYTHONPATH solution now!** 🚀

