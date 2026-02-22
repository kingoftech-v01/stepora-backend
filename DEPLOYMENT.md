# DreamPlanner Deployment Guide

This guide covers deploying DreamPlanner to production environments.

## Table of Contents

- [Architecture Overview](#architecture-overview)
- [Prerequisites](#prerequisites)
- [Backend Deployment (Django)](#backend-deployment-django)
- [Post-Deployment](#post-deployment)
- [Monitoring](#monitoring)
- [Troubleshooting](#troubleshooting)

## Architecture Overview

```text
                    ┌─────────────────┐
                    │   API Clients   │
                    │ (Mobile / Web)  │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │   Load Balancer │
                    │   (Nginx/ALB)   │
                    └────────┬────────┘
                             │
        ┌────────────────────┼────────────────────┐
        │                    │                    │
┌───────▼───────┐   ┌───────▼───────┐   ┌───────▼───────┐
│   Django API  │   │    Daphne     │   │    Celery     │
│   (Gunicorn)  │   │  (WebSocket)  │   │   (Workers)   │
└───────┬───────┘   └───────┬───────┘   └───────┬───────┘
        │                   │                   │
        └─────────┬─────────┴─────────┬─────────┘
                  │                   │
         ┌────────▼────────┐ ┌───────▼────────┐
         │   PostgreSQL    │ │     Redis      │
         │   (Database)    │ │  (Cache/Queue) │
         └─────────────────┘ └────────────────┘
```

## Prerequisites

### Required Services

| Service | Purpose | Recommended Provider |
|---------|---------|---------------------|
| PostgreSQL 15+ | Database | AWS RDS, Supabase, Railway |
| Redis 7+ | Cache & Celery broker | AWS ElastiCache, Upstash, Railway |
| OpenAI | AI features (GPT-4) | OpenAI |
| Sentry | Error tracking | Sentry.io |

### Required Tools

```bash
# Docker
docker --version  # >= 24.0

# Python
python --version  # >= 3.11

```

## Backend Deployment (Django)

### Option A: Docker Deployment (Recommended)

#### 1. Build Production Image

```bash

# Build the image
docker build -t dreamplanner-backend:latest .

# Or use docker-compose for full stack
docker-compose -f docker-compose.prod.yml build
```

#### 2. Configure Environment

Create `.env.production`:

```env
# Django
DJANGO_SECRET_KEY=<generate-with: python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())">
DJANGO_SETTINGS_MODULE=config.settings.production
DEBUG=False
ALLOWED_HOSTS=api.dreamplanner.app,localhost

# Database
DB_NAME=dreamplanner_prod
DB_USER=dreamplanner
DB_PASSWORD=<strong-password>
DB_HOST=your-postgres-host.com
DB_PORT=5432

# Redis
REDIS_URL=redis://your-redis-host.com:6379/0

# OpenAI
OPENAI_API_KEY=sk-...

# Security
CORS_ORIGIN=https://app.dreamplanner.app

# Monitoring
SENTRY_DSN=https://...@sentry.io/...
SENTRY_ENVIRONMENT=production

# Web Push (VAPID) - for browser push notifications
VAPID_PUBLIC_KEY=<your-vapid-public-key>
VAPID_PRIVATE_KEY=<your-vapid-private-key>
VAPID_ADMIN_EMAIL=admin@dreamplanner.app
```

#### 3. Run with Docker Compose

```bash
# Start all services
docker-compose -f docker-compose.prod.yml up -d

# Run migrations
docker-compose exec web python manage.py migrate

# Create superuser
docker-compose exec web python manage.py createsuperuser

# Collect static files
docker-compose exec web python manage.py collectstatic --noinput
```

#### 4. Nginx Configuration

```nginx
upstream django {
    server web:8000;
}

upstream websocket {
    server daphne:9000;
}

server {
    listen 80;
    server_name api.dreamplanner.app;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name api.dreamplanner.app;

    ssl_certificate /etc/ssl/certs/dreamplanner.crt;
    ssl_certificate_key /etc/ssl/private/dreamplanner.key;

    location / {
        proxy_pass http://django;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /ws/ {
        proxy_pass http://websocket;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
    }

    location /static/ {
        alias /app/staticfiles/;
    }

    location /media/ {
        alias /app/media/;
    }
}
```

### Option B: AWS ECS Deployment

#### 1. Push to ECR

```bash
# Login to ECR
aws ecr get-login-password --region eu-west-1 | docker login --username AWS --password-stdin $ECR_REGISTRY

# Tag and push
docker tag dreamplanner-backend:latest $ECR_REGISTRY/dreamplanner-backend:latest
docker push $ECR_REGISTRY/dreamplanner-backend:latest
```

#### 2. ECS Task Definition

```json
{
  "family": "dreamplanner-api",
  "networkMode": "awsvpc",
  "containerDefinitions": [
    {
      "name": "web",
      "image": "${ECR_REGISTRY}/dreamplanner-backend:latest",
      "portMappings": [{"containerPort": 8000}],
      "command": ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000"],
      "environment": [
        {"name": "DJANGO_SETTINGS_MODULE", "value": "config.settings.production"}
      ],
      "secrets": [
        {"name": "DJANGO_SECRET_KEY", "valueFrom": "arn:aws:secretsmanager:..."}
      ]
    }
  ]
}
```

#### 3. Deploy Service

```bash
aws ecs update-service \
  --cluster dreamplanner-prod \
  --service dreamplanner-api \
  --force-new-deployment
```

### Option C: Manual Deployment

```bash

# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements/production.txt

# Set environment variables
export DJANGO_SETTINGS_MODULE=config.settings.production
# ... other env vars

# Run migrations
python manage.py migrate

# Collect static files
python manage.py collectstatic --noinput

# Start Gunicorn (HTTP)
gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 4

# In another terminal: Start Daphne (WebSocket)
daphne -b 0.0.0.0 -p 9000 config.asgi:application

# In another terminal: Start Celery worker
celery -A config worker -l info

# In another terminal: Start Celery beat
celery -A config beat -l info
```

## Post-Deployment

### Health Checks

```bash
# General health
curl https://api.dreamplanner.app/health/

# Liveness probe
curl https://api.dreamplanner.app/health/liveness/

# Readiness probe (includes DB check)
curl https://api.dreamplanner.app/health/readiness/
```

### Run Database Migrations

```bash
# Docker
docker-compose exec web python manage.py migrate

# ECS
aws ecs run-task \
  --cluster dreamplanner-prod \
  --task-definition dreamplanner-migrate
```

### Verify Services

1. **API**: `curl https://api.dreamplanner.app/api/auth/`
2. **WebSocket**: Test with wscat: `wscat -c wss://api.dreamplanner.app/ws/conversations/test/`
3. **Admin**: Visit `https://api.dreamplanner.app/admin/`
4. **Celery**: Check Flower at `https://api.dreamplanner.app:5555/`

## Monitoring

### Celery Monitoring (Flower)

```bash
# Access Flower dashboard
open http://localhost:5555

# Check task status
celery -A config inspect active
celery -A config inspect scheduled
```

### Database Monitoring

```sql
-- Active connections
SELECT count(*) FROM pg_stat_activity WHERE state = 'active';

-- Slow queries
SELECT query, mean_exec_time, calls
FROM pg_stat_statements
ORDER BY mean_exec_time DESC
LIMIT 10;

-- Table sizes
SELECT tablename, pg_size_pretty(pg_total_relation_size(tablename::regclass))
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(tablename::regclass) DESC;
```

### Application Logs

```bash
# Docker logs
docker-compose logs -f web
docker-compose logs -f celery
docker-compose logs -f daphne

# Systemd logs
journalctl -u gunicorn -f
journalctl -u celery -f
```

## Troubleshooting

### Database Connection Issues

```bash
# Test connection
psql -h $DB_HOST -U $DB_USER -d $DB_NAME -c "SELECT 1"

# Check migrations
python manage.py showmigrations

# Force migration
python manage.py migrate --fake-initial
```

### Redis Connection Issues

```bash
# Test Redis
redis-cli -u $REDIS_URL ping

# Check Celery broker
celery -A config inspect ping
```

### Celery Not Processing Tasks

```bash
# Check worker status
celery -A config inspect active

# Purge stuck tasks
celery -A config purge

# Restart workers
docker-compose restart celery celery-beat
```

### WebSocket Connection Failed

```bash
# Test WebSocket
wscat -c wss://api.dreamplanner.app/ws/health/

# Check Daphne logs
docker-compose logs daphne

# Verify Nginx WebSocket config
nginx -t
```

### High Memory Usage

```bash
# Check Django memory
python -c "import tracemalloc; tracemalloc.start(); # your code"

# Optimize Gunicorn workers
gunicorn --workers 2 --threads 4 --max-requests 1000
```

## Security Checklist

- [ ] Django SECRET_KEY is unique and secure
- [ ] DEBUG=False in production
- [ ] ALLOWED_HOSTS configured properly
- [ ] HTTPS enforced
- [ ] CORS origins restricted
- [ ] Database credentials secured
- [ ] Rate limiting enabled
- [ ] Security headers configured
- [ ] Admin URL changed from `/admin/`

## Backup Strategy

### Database Backups

```bash
# Manual backup
pg_dump -h $DB_HOST -U $DB_USER $DB_NAME > backup_$(date +%Y%m%d).sql

# Restore
psql -h $DB_HOST -U $DB_USER $DB_NAME < backup_20240101.sql
```

### Automated Backups (Cron)

```bash
# Daily backup at 2 AM
0 2 * * * pg_dump -h $DB_HOST -U $DB_USER $DB_NAME | gzip > /backups/db_$(date +\%Y\%m\%d).sql.gz
```

## Support

- Documentation: `/docs` folder
- Issues: GitHub Issues
- Email: support@dreamplanner.app

---

**Last Updated:** January 2026
**Maintained by:** DreamPlanner Team
