#!/bin/bash
# Don't exit on error for dependency checks - allow fallback installs
set +e

echo "[ENTRYPOINT] Starting MSS Flask application..."
echo "[ENTRYPOINT] PORT=${PORT:-8080}"
echo "[ENTRYPOINT] PYTHONPATH=${PYTHONPATH}"
echo "[ENTRYPOINT] PATH=${PATH}"

# Wait for Cloud SQL proxy if DB_URL contains cloudsql
if [ -n "$DB_URL" ] && [[ "$DB_URL" == *"cloudsql"* ]]; then
    echo "[ENTRYPOINT] Waiting for Cloud SQL proxy..."
    sleep 2
fi

# Run migrations if needed (future: when using Cloud SQL)
# python -m web.database migrate

# Quick check if key packages are missing, install only if needed (faster)
echo "[ENTRYPOINT] Checking critical dependencies..."
python -c "from flask_limiter import Limiter; import stripe; import gunicorn; print('[ENTRYPOINT] All dependencies OK')" 2>/dev/null || {
    echo "[ENTRYPOINT] Missing dependencies, installing from requirements.txt..."
    if [ -f requirements.txt ]; then
        pip install --user --no-cache-dir -r requirements.txt
        echo "[ENTRYPOINT] Rechecking after install..."
        python -c "from flask_limiter import Limiter; import stripe; import gunicorn" || {
            echo "[ENTRYPOINT] ERROR: Critical packages still missing after install!"
            pip list | grep -E "(flask|stripe|gunicorn)"
            exit 1
        }
    else
        echo "[ENTRYPOINT] ERROR: requirements.txt not found!"
        exit 1
    fi
}

# Verify Python and gunicorn are available
echo "[ENTRYPOINT] Verifying dependencies..."
python --version
echo "[ENTRYPOINT] PATH=${PATH}"
echo "[ENTRYPOINT] Looking for gunicorn..."
which gunicorn || /root/.local/bin/gunicorn --version || { echo "[ENTRYPOINT] ERROR: gunicorn not found!"; exit 1; }

# Now enable strict error checking
set -e

# Verify app can be imported
echo "[ENTRYPOINT] Verifying app import..."
python -c "from web import api_server; print('[ENTRYPOINT] App imported successfully')" 2>&1 || { 
    echo "[ENTRYPOINT] ERROR: Failed to import app!"
    python -c "from web import api_server" 2>&1 | head -20
    exit 1
}

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

