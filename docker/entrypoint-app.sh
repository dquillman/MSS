#!/bin/bash
set -e

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

# Verify Python and gunicorn are available
echo "[ENTRYPOINT] Verifying dependencies..."
python --version
gunicorn --version || { echo "[ENTRYPOINT] ERROR: gunicorn not found!"; exit 1; }

# Verify app can be imported
echo "[ENTRYPOINT] Verifying app import..."
python -c "from web import api_server; print('[ENTRYPOINT] App imported successfully')" || { echo "[ENTRYPOINT] ERROR: Failed to import app!"; exit 1; }

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

