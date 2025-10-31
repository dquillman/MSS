# 🚀 Local Development Setup Guide

This guide will help you get MSS (Many Sources Say) running on your local machine.

## 📋 Prerequisites

- **Python 3.11+** (check with `python --version`)
- **pip** (Python package installer)
- **Git** (optional, if cloning the repo)
- **Redis** (optional, for caching - app works without it)

## 🔧 Step 1: Install Dependencies

### Option A: Using Virtual Environment (Recommended)

```powershell
# Create virtual environment
python -m venv venv

# Activate virtual environment (Windows)
.\venv\Scripts\activate

# Activate virtual environment (macOS/Linux)
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# For development (testing, linting, etc.)
pip install -r requirements-dev.txt
```

### Option B: Global Installation (Not Recommended)

```powershell
pip install -r requirements.txt
```

## ⚙️ Step 2: Environment Configuration

### Create `.env` File

Create a `.env` file in the project root (`G:\Users\daveq\MSS\.env`):

```bash
# Flask Configuration
FLASK_ENV=development
FLASK_DEBUG=true
PORT=5000

# Security
SECRET_KEY=your-secret-key-here-use-long-random-string
ENCRYPTION_KEY=your-encryption-key-here  # Generate with: python scripts/generate_encryption_key.py

# Database (SQLite - auto-created, no setup needed)
# DATABASE_URL=sqlite:///web/mss_users.db  # Optional - defaults to web/mss_users.db

# Redis (Optional - for caching and rate limiting)
# REDIS_HOST=localhost
# REDIS_PORT=6379
# REDIS_DB=0
# REDIS_URL=redis://localhost:6379/0

# CORS (for development)
ALLOWED_ORIGINS=http://localhost:5000,http://localhost:3000,http://127.0.0.1:5000

# OpenAI (Required for video generation)
OPENAI_API_KEY=your-openai-api-key-here

# Google Cloud (Required for TTS and YouTube)
GOOGLE_APPLICATION_CREDENTIALS=path/to/your/service-account-key.json

# Shotstack (Required for video rendering)
SHOTSTACK_API_KEY=your-shotstack-api-key
SHOTSTACK_ENV=stage  # or 'production'

# Stripe (Optional - for payments)
# STRIPE_SECRET_KEY=sk_test_xxxxx
# STRIPE_PUBLISHABLE_KEY=pk_test_xxxxx
# STRIPE_WEBHOOK_SECRET=whsec_xxxxx

# YouTube (Optional)
# YOUTUBE_API_KEY=your-youtube-api-key

# Other Optional Services
# PEXELS_API_KEY=your-pexels-api-key
# ENABLE_STOCK_FOOTAGE=true
```

### Generate Secret Keys

```powershell
# Generate SECRET_KEY
python -c "import secrets; print(secrets.token_urlsafe(32))"

# Generate ENCRYPTION_KEY
python scripts/generate_encryption_key.py
```

Copy the output values into your `.env` file.

## 🗄️ Step 3: Database Setup

**No setup required!** The app uses SQLite and will automatically:
- Create `web/mss_users.db` on first run
- Initialize all required tables
- Handle migrations automatically

## 🔴 Step 4: Redis Setup (Optional)

Redis is **optional** but recommended for:
- Caching (topics, analytics, user sessions)
- Rate limiting (falls back to memory if Redis unavailable)

### Install Redis (Windows)

1. **Using WSL (Recommended)**:
   ```bash
   # In WSL
   sudo apt update
   sudo apt install redis-server
   sudo service redis-server start
   ```

2. **Using Docker**:
   ```powershell
   docker run -d -p 6379:6379 redis:latest
   ```

3. **Using Memurai** (Windows Native):
   - Download from: https://www.memurai.com/
   - Install and start the service

### Verify Redis Connection

```powershell
# If Redis is installed, test connection
redis-cli ping  # Should return "PONG"
```

If Redis is not available, the app will still work but will:
- Use in-memory caching (lost on restart)
- Use memory-based rate limiting

## 🚀 Step 5: Start the Server

### From Project Root

```powershell
# Make sure you're in the project root
cd G:\Users\daveq\MSS

# Activate virtual environment (if using)
.\venv\Scripts\activate

# Start the server
python web/api_server.py
```

### Alternative: Using Flask CLI

```powershell
cd web
flask --app api_server run --host=127.0.0.1 --port=5000 --debug
```

### Expected Output

```
[BOOT] Using temp dir: G:\Users\daveq\MSS\tmp
[BOOT] OPENAI_API_KEY loaded from .env
[DATABASE] Database initialized successfully
[CACHE] Redis connected: localhost:6379/0  # or "Redis unavailable" if not running
[SERVER] Starting Flask server on http://127.0.0.1:5000
[SERVER] Debug mode: True
 * Running on http://127.0.0.1:5000
Press CTRL+C to quit
```

## 🌐 Step 6: Access the Application

Once the server is running, open your browser and visit:

### Main Pages
- **Landing Page**: http://localhost:5000/
- **Authentication**: http://localhost:5000/auth
- **Studio**: http://localhost:5000/studio
- **Dashboard**: http://localhost:5000/dashboard
- **Workflow**: http://localhost:5000/workflow
- **Trends Calendar**: http://localhost:5000/trends-calendar
- **Settings**: http://localhost:5000/settings

### API Endpoints
- **API Documentation (Swagger)**: http://localhost:5000/api/docs
- **Health Check**: http://localhost:5000/healthz
- **API Base**: http://localhost:5000/api/

## ✅ Step 7: Verify Setup

### Quick Health Check

1. **Server Status**: Visit http://localhost:5000/healthz
   - Should return: `{"status": "ok"}`

2. **API Docs**: Visit http://localhost:5000/api/docs
   - Should show Swagger UI with API documentation

3. **Database**: Check if `web/mss_users.db` was created
   ```powershell
   Test-Path web\mss_users.db  # Should return True
   ```

4. **Test Authentication**:
   - Visit http://localhost:5000/auth
   - Try signing up with a new account
   - Login with the credentials

## 🧪 Step 8: Run Tests (Optional)

```powershell
# Run all tests
pytest

# Run with coverage
pytest --cov=web --cov-report=html

# Run specific test file
pytest tests/test_api_auth.py

# Run with verbose output
pytest -v
```

## 🔍 Troubleshooting

### Issue: "Module not found" or Import Errors

**Solution**: Make sure you're running from the project root and virtual environment is activated:
```powershell
cd G:\Users\daveq\MSS
.\venv\Scripts\activate
python web/api_server.py
```

### Issue: "Port 5000 already in use"

**Solution**: Use a different port:
```powershell
$env:PORT=5001
python web/api_server.py
```

Or kill the process using port 5000:
```powershell
# Find process
netstat -ano | findstr :5000

# Kill process (replace PID with actual process ID)
taskkill /PID <PID> /F
```

### Issue: "Database locked" or SQLite Errors

**Solution**: 
- Make sure no other process is using `web/mss_users.db`
- Delete the database file and restart (data will be lost):
  ```powershell
  Remove-Item web\mss_users.db
  python web/api_server.py  # Will recreate database
  ```

### Issue: Redis Connection Failed

**Solution**: This is **normal** if Redis is not installed. The app will:
- Use in-memory caching (temporary)
- Use memory-based rate limiting
- Still function perfectly for development

To enable Redis caching, install Redis (see Step 4).

### Issue: "OPENAI_API_KEY not found"

**Solution**: Make sure your `.env` file:
1. Exists in the project root
2. Contains `OPENAI_API_KEY=your-key-here`
3. Has no spaces around the `=` sign

### Issue: CORS Errors in Browser

**Solution**: Make sure `ALLOWED_ORIGINS` in `.env` includes your frontend URL:
```bash
ALLOWED_ORIGINS=http://localhost:5000,http://localhost:3000,http://127.0.0.1:5000
```

### Issue: SSL/Certificate Errors (HTTPS Redirect)

**Solution**: For local development, disable HTTPS enforcement:
```bash
# In .env
FLASK_ENV=development
```

The app will only enforce HTTPS in production mode.

## 🎯 Quick Start Checklist

- [ ] Python 3.11+ installed
- [ ] Virtual environment created and activated
- [ ] Dependencies installed (`pip install -r requirements.txt`)
- [ ] `.env` file created with required keys
- [ ] SECRET_KEY and ENCRYPTION_KEY generated
- [ ] Server starts without errors
- [ ] Can access http://localhost:5000/auth
- [ ] Database file created (`web/mss_users.db`)
- [ ] (Optional) Redis running for caching

## 📚 Additional Resources

- **API Documentation**: http://localhost:5000/api/docs (when server is running)
- **README**: See `README.md` for full feature documentation
- **Testing Guide**: See `TESTING_GUIDE.md`
- **Deployment**: See `DEPLOYMENT.md` for production setup

## 🚨 Important Notes

1. **Never commit `.env` file** - it contains secrets!
2. **Development mode** (`FLASK_ENV=development`) disables many security features
3. **SQLite database** is for development - use PostgreSQL for production
4. **Redis is optional** - app works fine without it for local development
5. **Keep server running** - press `CTRL+C` to stop

## 🎉 You're Ready!

Your local development environment is now set up. Start the server and begin developing!

```powershell
python web/api_server.py
```

Happy coding! 🚀


