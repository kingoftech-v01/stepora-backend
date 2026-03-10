# Multi-stage build for production-ready Django backend

# Stage 1: Builder
FROM python:3.11-slim as builder

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Create and set working directory
WORKDIR /app

# Install Python dependencies
COPY requirements/ requirements/
ARG REQUIREMENTS_FILE=requirements/production.txt
RUN pip install --upgrade pip && pip install -r ${REQUIREMENTS_FILE}


# Stage 2: Runtime
FROM python:3.11-slim

# Set environment variables
ARG DJANGO_SETTINGS=config.settings.production
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=${DJANGO_SETTINGS}

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    postgresql-client \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create app user for security
RUN useradd -m -u 1000 appuser && \
    mkdir -p /app /app/staticfiles /app/mediafiles /app/logs && \
    chown -R appuser:appuser /app

# Set working directory
WORKDIR /app

# Copy Python dependencies from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages/ /usr/local/lib/python3.11/site-packages/
COPY --from=builder /usr/local/bin/ /usr/local/bin/

# Copy application code
COPY --chown=appuser:appuser . .

# Collect static files (FIELD_ENCRYPTION_KEY needed at build time for settings import)
# A placeholder is used during build; the real key is injected at runtime via ECS task definition.
ARG FIELD_ENCRYPTION_KEY="build-time-placeholder-key-not-for-production"
ENV FIELD_ENCRYPTION_KEY=${FIELD_ENCRYPTION_KEY}
RUN python manage.py collectstatic --noinput --clear

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health/liveness/ || exit 1

# Run gunicorn
CMD ["gunicorn", \
     "--bind", "0.0.0.0:8000", \
     "--workers", "4", \
     "--worker-class", "gthread", \
     "--threads", "2", \
     "--timeout", "120", \
     "--access-logfile", "-", \
     "--error-logfile", "-", \
     "--log-level", "info", \
     "config.wsgi:application"]
