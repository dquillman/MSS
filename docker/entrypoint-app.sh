#!/bin/bash
# Enable verbose logging
set -x
# Don't exit on error for dependency checks - allow fallback installs
set +e

echo "[ENTRYPOINT] ========================================"
echo "[ENTRYPOINT] Starting MSS Flask application..."
echo "[ENTRYPOINT] PORT=${PORT:-8080}"
echo "[ENTRYPOINT] PYTHONPATH=${PYTHONPATH}"
echo "[ENTRYPOINT] PATH=${PATH}"
echo "[ENTRYPOINT] Working directory: $(pwd)"
echo "[ENTRYPOINT] Python: $(which python)"
echo "[ENTRYPOINT] Python version: $(python --version 2>&1)"

# Wait for Cloud SQL proxy if DB_URL contains cloudsql
if [ -n "$DB_URL" ] && [[ "$DB_URL" == *"cloudsql"* ]]; then
    echo "[ENTRYPOINT] Waiting for Cloud SQL proxy..."
    sleep 2
fi

# Run migrations if needed (future: when using Cloud SQL)
# python -m web.database migrate

# Quick check if key packages are missing, install only if needed (faster)
echo "[ENTRYPOINT] Checking critical dependencies..."
# Use python -m site --user-site to get user site-packages path and add it explicitly
python -c "import site; import sys; sys.path.insert(0, site.USER_SITE); from flask_limiter import Limiter; import stripe; import gunicorn; print('[ENTRYPOINT] All dependencies OK')" 2>/dev/null || {
    echo "[ENTRYPOINT] Missing dependencies, checking what's installed..."
    pip list | grep -i flask || echo "[ENTRYPOINT] No flask packages found"
    echo "[ENTRYPOINT] Installing flask-limiter explicitly..."
    pip install --user --no-cache-dir flask-limiter>=3.0.0 stripe gunicorn || {
        echo "[ENTRYPOINT] Direct install failed, trying full requirements.txt..."
        if [ -f requirements.txt ]; then
            pip install --user --no-cache-dir -r requirements.txt --force-reinstall --no-deps flask-limiter || pip install --user --no-cache-dir flask-limiter
        fi
    }
    echo "[ENTRYPOINT] Rechecking after install..."
    # After install, explicitly add user site-packages to path
    python -c "import site; import sys; sys.path.insert(0, site.USER_SITE); from flask_limiter import Limiter; import stripe; import gunicorn; print('[ENTRYPOINT] All dependencies OK after install')" || {
        echo "[ENTRYPOINT] ERROR: Critical packages still missing after install!"
        echo "[ENTRYPOINT] Checking user site-packages location..."
        python -c "import site; print(f'USER_SITE: {site.USER_SITE}')"
        echo "[ENTRYPOINT] Installed packages:"
        pip list | grep -iE "(flask|stripe|gunicorn|limiter)" || echo "[ENTRYPOINT] No matching packages found"
        python -c "import sys; print('Python path:'); print('\\n'.join(sys.path))"
        echo "[ENTRYPOINT] Trying to import directly..."
        python -c "import sys; sys.path.insert(0, '/root/.local/lib/python3.11/site-packages'); from flask_limiter import Limiter; print('SUCCESS')" || echo "[ENTRYPOINT] Direct path import also failed"
        exit 1
    }
}

# Verify Python and gunicorn are available
echo "[ENTRYPOINT] Verifying dependencies..."
python --version
echo "[ENTRYPOINT] PATH=${PATH}"
echo "[ENTRYPOINT] Looking for gunicorn..."
which gunicorn || /root/.local/bin/gunicorn --version || { echo "[ENTRYPOINT] ERROR: gunicorn not found!"; exit 1; }

# Now enable strict error checking
set -e

# Verify app can be imported - with detailed error output
echo "[ENTRYPOINT] ========================================"
echo "[ENTRYPOINT] Verifying app import..."
IMPORT_OUTPUT=$(python -c "from web import api_server; print('[ENTRYPOINT] App imported successfully')" 2>&1)
IMPORT_EXIT=$?
if [ $IMPORT_EXIT -ne 0 ]; then
    echo "[ENTRYPOINT] ERROR: Failed to import app!"
    echo "[ENTRYPOINT] Import error output:"
    echo "$IMPORT_OUTPUT"
    echo "[ENTRYPOINT] Trying to get full traceback..."
    python -c "from web import api_server" 2>&1
    echo "[ENTRYPOINT] Checking installed packages..."
    pip list | head -30
    echo "[ENTRYPOINT] Checking Python path..."
    python -c "import sys; print('\\n'.join(sys.path))"
    exit 1
fi
echo "$IMPORT_OUTPUT"

echo "[ENTRYPOINT] Starting gunicorn on 0.0.0.0:${PORT:-8080}..."

# Start gunicorn
exec gunicorn \
    --bind 0.0.0.0:${PORT:-8080} \
    --workers ${GUNICORN_WORKERS:-2} \
    --threads ${GUNICORN_THREADS:-4} \
    --timeout ${GUNICORN_TIMEOUT:-120} \
    --access-logfile - \
    --error-logfile - \
    --log-level info \
    web.api_server:app

