# 🚀 How to Start the Server - CORRECT WAY

## ✅ Flask-Limiter is Installed!

The module is installed and working. The issue was how to start the server.

---

## 📍 Start from the CORRECT Directory

### Option 1: From Project Root (RECOMMENDED)

```powershell
# You should be in: G:\Users\daveq\MSS
python web/api_server.py
```

**OR** if you're already in the `web` directory:

```powershell
# Navigate back to root first
cd ..
python web/api_server.py
```

### Option 2: Using Flask CLI

```powershell
# From project root (G:\Users\daveq\MSS)
flask --app web.api_server run
```

---

## ✅ Try This Now

**In PowerShell, run:**

```powershell
# Make sure you're in the project root
cd G:\Users\daveq\MSS

# Start the server
python web/api_server.py
```

**OR** if you're in the `web` directory:

```powershell
# Go back to root
cd ..

# Start server
python web/api_server.py
```

---

## 🔍 Why This Works

The server imports `web.exceptions` and `web.database`, which means Python needs to see the `web` directory as a package. Running from the project root allows this.

---

## ✅ Expected Output

When it works, you'll see:
```
 * Running on http://127.0.0.1:5000
Press CTRL+C to quit
```

Then open: `http://localhost:5000/auth`

---

**Try starting from the project root now!** 🚀

