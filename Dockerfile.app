# Simple single-stage build for MSS Flask application
FROM python:3.11-slim

WORKDIR /app

# Install all dependencies at once (simpler and more reliable)
RUN apt-get update && apt-get install -y \
    curl \
    ffmpeg \
    gcc \
    g++ \
    libfreetype6-dev \
    libjpeg-dev \
    fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

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
# Ensure platform_credentials directory exists
# Note: Credentials should be provided via Cloud Run secrets or environment variables in production
# The directory structure is created here, but credential files are not copied (they're in .gitignore)
RUN mkdir -p web/platform_credentials

# Copy entrypoint script
COPY docker/entrypoint-app.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Set Python path and ensure PATH is set correctly
ENV PATH=/root/.local/bin:$PATH
ENV PYTHONPATH=/app
# Ensure Python can find user-installed packages
ENV PYTHONUSERBASE=/root/.local

# Verify gunicorn is installed
RUN /root/.local/bin/gunicorn --version || pip install --user gunicorn

# Expose port (Cloud Run will set PORT env var)
EXPOSE 8080

# Use entrypoint script
ENTRYPOINT ["/entrypoint.sh"]


