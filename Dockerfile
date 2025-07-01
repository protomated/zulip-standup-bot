# Multi-stage Dockerfile for Zulip Standup Bot
# Production-ready with security and performance optimizations

# Build stage
FROM python:3.11-slim AS builder

# Install build dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Create build directory
WORKDIR /build

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Production stage
FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH="/app:/app/zulip_bots"

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    libpq5 \
    netcat-openbsd \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Set working directory
WORKDIR /app

# Copy Python packages from builder
COPY --from=builder /root/.local /usr/local

# Copy application code
COPY . /app/

# Create non-root user
RUN groupadd -r zulipbot && useradd -r -g zulipbot zulipbot

# Create necessary directories and set permissions
RUN mkdir -p /app/data /app/logs \
    && chown -R zulipbot:zulipbot /app \
    && chmod +x /app/scripts/start.sh \
    && chmod +x /app/setup.sh \
    && chmod +x /app/run_standup_bot.py \
    && chmod +x /app/test_imports.py \
    && chmod +x /app/init_database.py

# Note: We rely on PYTHONPATH for module discovery instead of package installation
# The local zulip_bots directory will be accessible via PYTHONPATH
RUN echo "Skipping package installation - using PYTHONPATH approach"

# Switch to non-root user
USER zulipbot

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:5002/health || exit 1

# Expose health check port
EXPOSE 5002

# Set the entrypoint
ENTRYPOINT ["/app/scripts/start.sh"]

# Labels for metadata
LABEL maintainer="Protomated <ask@protomated.com>" \
      description="Zulip Standup Bot - Automated team standups for Zulip" \
      version="1.0.0" \
      org.opencontainers.image.title="Zulip Standup Bot" \
      org.opencontainers.image.description="Production-ready bot for automating daily team standups in Zulip" \
      org.opencontainers.image.version="1.0.0" \
      org.opencontainers.image.vendor="Protomated" \
      org.opencontainers.image.licenses="MIT" \
      org.opencontainers.image.source="https://github.com/protomated/zulip-standup-bot"
