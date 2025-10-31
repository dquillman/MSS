# Simple single-stage build for MSS Flask application
FROM python:3.11-slim

WORKDIR /app

# Install all dependencies at once (simpler and more reliable)
RUN apt-get update && apt-get install -y \
    curl \
    ffmpeg \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies - VERIFY ALL ARE INSTALLED
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt
# Verify imports work (flask-limiter package imports as flask_limiter)
RUN python -c "import flask; print('flask OK')" && \
    python -c "import flask_cors; print('flask_cors OK')" && \
    python -c "from flask_limiter import Limiter; print('flask_limiter OK')" && \
    python -c "import stripe; print('stripe OK')" && \
    python -c "import gunicorn; print('gunicorn OK')" && \
    python -c "import bcrypt; print('bcrypt OK')" && \
    echo "All critical packages verified"

# Copy application code (copy requirements again so entrypoint can use it)
COPY web/ ./web/
COPY scripts/ ./scripts/
COPY requirements.txt ./requirements.txt
# Copy library files
COPY avatar_library.json ./
COPY intro_outro_library.json ./
COPY logo_library.json ./
COPY thumbnail_settings.json ./

# Create necessary directories
RUN mkdir -p tmp out public_audio thumbnails avatars logos

# Copy entrypoint script
COPY docker/entrypoint-app.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Set Python path and ensure PATH is set correctly
ENV PATH=/root/.local/bin:$PATH
ENV PYTHONPATH=/app

# Verify gunicorn is installed
RUN /root/.local/bin/gunicorn --version || pip install --user gunicorn

# Expose port (Cloud Run will set PORT env var)
EXPOSE 8080

# Use entrypoint script
ENTRYPOINT ["/entrypoint.sh"]


