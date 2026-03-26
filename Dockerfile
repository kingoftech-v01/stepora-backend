# Multi-stage build for production-ready Django backend
#
# SECURITY TODO [V-268]: Enable automated Docker image vulnerability scanning.
# Options (implement at least one):
# 1. AWS ECR: Enable "Scan on push" in ECR repository settings
#    aws ecr put-image-scanning-configuration \
#      --repository-name stepora/backend \
#      --image-scanning-configuration scanOnPush=true
# 2. CI/CD: Add Trivy scan step before pushing to ECR:
#    docker run --rm aquasec/trivy image --exit-code 1 \
#      --severity CRITICAL ${IMAGE}
# 3. GitHub: Enable Dependabot container scanning
#
# SECURITY TODO [V-283]: Pin GitHub Actions by SHA instead of tag
# for supply chain security. Pin base Docker images by digest.

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
# A throwaway key is used ONLY during the build step. The real key is injected at
# runtime via ECS task definition. No secret is baked into the image layer.
ARG FIELD_ENCRYPTION_KEY="build-time-placeholder-do-not-use"
RUN FIELD_ENCRYPTION_KEY="${FIELD_ENCRYPTION_KEY}" python manage.py collectstatic --noinput --clear

# Make scripts executable
RUN chmod +x /app/healthcheck.sh /app/entrypoint.sh

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 8000

# Health check (role-aware: web checks gunicorn, worker/beat checks process)
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD /app/healthcheck.sh

# Entrypoint
COPY --chown=appuser:appuser entrypoint.sh /app/entrypoint.sh
CMD ["/app/entrypoint.sh"]
