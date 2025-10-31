# Multi-stage build for MSS Flask application
FROM python:3.11-slim as builder

WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Production stage
FROM python:3.11-slim

WORKDIR /app

# Install runtime and build dependencies (needed for some Python packages)
RUN apt-get update && apt-get install -y \
    curl \
    ffmpeg \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first
COPY requirements.txt .

# Install all Python dependencies directly (with build tools available)
RUN pip install --user --no-cache-dir -r requirements.txt

# Copy application code
COPY web/ ./web/
COPY scripts/ ./scripts/
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


