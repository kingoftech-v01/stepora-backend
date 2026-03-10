# Stepora Deployment Guide

This guide covers deploying Stepora to production environments.

## Table of Contents

- [Architecture Overview](#architecture-overview)
- [Prerequisites](#prerequisites)
- [Backend Deployment (Django)](#backend-deployment-django)
- [Post-Deployment](#post-deployment)
- [Monitoring](#monitoring)
- [Troubleshooting](#troubleshooting)
- [Frontend Deployment (React + Capacitor)](#frontend-deployment-react--capacitor)

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
| Agora.io | Real-time messaging (RTM) + Circle voice/video calls (RTC) | Agora.io |
| Firebase | Push notifications (FCM) | Google Firebase |
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
docker build -t stepora-backend:latest .

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
ALLOWED_HOSTS=api.stepora.app,localhost

# Database
DB_NAME=stepora_prod
DB_USER=stepora
DB_PASSWORD=<strong-password>
DB_HOST=your-postgres-host.com
DB_PORT=5432

# Redis
REDIS_URL=redis://your-redis-host.com:6379/0

# OpenAI
OPENAI_API_KEY=sk-...

# Agora (real-time messaging + circle voice/video calls)
# IMPORTANT: You must also enable Signaling in the Agora Console (see below)
AGORA_APP_ID=<your-agora-app-id>
AGORA_APP_CERTIFICATE=<your-agora-app-certificate>

# Firebase (push notifications)
FIREBASE_CREDENTIALS_PATH=/path/to/firebase-service-account.json

# Security
CORS_ORIGIN=https://app.stepora.app

# Monitoring
SENTRY_DSN=https://...@sentry.io/...
SENTRY_ENVIRONMENT=production

# Web Push (VAPID) - for browser push notifications
VAPID_PUBLIC_KEY=<your-vapid-public-key>
VAPID_PRIVATE_KEY=<your-vapid-private-key>
VAPID_ADMIN_EMAIL=admin@stepora.app
```

#### Agora Console Setup (Required for RTM + RTC)

Setting `AGORA_APP_ID` and `AGORA_APP_CERTIFICATE` in `.env` is **not enough**. You must also enable the **Signaling** service in the Agora Console, otherwise RTM login will fail with error code **2010026** (`LOGIN_REJECTED_BY_SERVER`).

1. Go to [console.agora.io](https://console.agora.io) and sign in
2. Navigate to **Projects** → click the **pencil icon** on your project
3. Go to **All features** → **Signaling** → **Basic information**
4. Select a **data center** from the dropdown (cannot be changed later)
5. Go to **Subscriptions** → **Signaling** → subscribe to the **Free Package** (or a paid plan)

> **Troubleshooting:** If buddy/circle chat messages don't appear in real-time and the browser console shows `Error Code 2010026`, it means Signaling is not enabled or the subscription has expired.

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
    server_name api.stepora.app;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name api.stepora.app;

    ssl_certificate /etc/ssl/certs/stepora.crt;
    ssl_certificate_key /etc/ssl/private/stepora.key;

    client_max_body_size 110m;  # Match Django DATA_UPLOAD_MAX_MEMORY_SIZE

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
docker tag stepora-backend:latest $ECR_REGISTRY/stepora-backend:latest
docker push $ECR_REGISTRY/stepora-backend:latest
```

#### 2. ECS Task Definition

```json
{
  "family": "stepora-api",
  "networkMode": "awsvpc",
  "containerDefinitions": [
    {
      "name": "web",
      "image": "${ECR_REGISTRY}/stepora-backend:latest",
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
  --cluster stepora-prod \
  --service stepora-api \
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
curl https://api.stepora.app/health/

# Liveness probe
curl https://api.stepora.app/health/liveness/

# Readiness probe (includes DB check)
curl https://api.stepora.app/health/readiness/
```

### Run Database Migrations

```bash
# Docker
docker-compose exec web python manage.py migrate

# ECS
aws ecs run-task \
  --cluster stepora-prod \
  --task-definition stepora-migrate
```

### Verify Services

1. **API**: `curl https://api.stepora.app/api/auth/`
2. **WebSocket**: Test with wscat:
   - AI Chat: `wscat -c wss://api.stepora.app/ws/ai-chat/test/`
   - Circle Chat: `wscat -c wss://api.stepora.app/ws/circle-chat/test/`
   - Buddy Chat: `wscat -c wss://api.stepora.app/ws/buddy-chat/test/`
   - Notifications: `wscat -c wss://api.stepora.app/ws/notifications/`
3. **Admin**: Visit `https://api.stepora.app/admin/`
4. **Celery**: Check Flower at `https://api.stepora.app:5555/`

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
wscat -c wss://api.stepora.app/ws/health/

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

See **[PRODUCTION_CHECKLIST.md](PRODUCTION_CHECKLIST.md)** for the full pre-GA checklist including all security, infrastructure, and environment variable requirements.

Quick summary:

- [ ] Django SECRET_KEY is unique and secure
- [ ] DEBUG=False in production
- [ ] ALLOWED_HOSTS configured properly
- [ ] HTTPS enforced with HSTS (1 year, includeSubDomains, preload)
- [ ] CORS origins restricted (`CORS_ORIGIN` env var set)
- [ ] Database credentials secured, `sslmode=require`
- [ ] Rate limiting enabled (auth endpoints: 5/min)
- [ ] Security headers configured (CSP, X-Frame-Options: DENY, COOP, CORP)
- [ ] `FIELD_ENCRYPTION_KEY` moved to secret manager (not hardcoded)
- [ ] All secrets rotated after beta
- [ ] `client_max_body_size 110m` set in nginx (matches Django `DATA_UPLOAD_MAX_MEMORY_SIZE`)
- [ ] Sentry DSN configured
- [ ] SMTP configured for email verification

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

## Frontend Deployment (React + Capacitor)

The frontend is a separate project at `/root/stepora-frontend` (React + Vite + Capacitor for Android).

### Web Build

```bash
cd /root/stepora-frontend

# Build production bundle
npm run build

# Output in dist/ — serve via nginx or upload to CDN
```

### Environment Variables (Frontend)

| Variable | Purpose |
|----------|---------|
| `VITE_API_BASE` | API base URL (empty for same-origin proxy, or `https://dpapi.jhpetitfrere.com` for direct) |

### Same-Origin Proxy Setup

External nginx on `dp.jhpetitfrere.com` proxies `/api/` and `/ws/` to the backend at `127.0.0.1:8085`. The frontend uses relative URLs (`VITE_API_BASE=`), so cookies are host-only on `dp.jhpetitfrere.com`.

### Android (Capacitor)

```bash
# Sync web assets to native project
npx cap sync android

# Build APK (Android Studio or CLI)
cd android && ./gradlew assembleRelease
```

### OTA Live Updates

Push web bundle updates to mobile apps without app store review:

```bash
# Build, sign, and deploy OTA update
./scripts/deploy-ota.sh notify   # or "silent" for background updates
```

- **RSA Code Signing**: Bundles signed with RSA-2048, verified server-side and client-side
- **Rollback Safety**: Auto-reverts to previous bundle if new one crashes within 10s
- **Admin Panel**: Manage bundles, deactivate bad releases via Django Admin

## Support

- Documentation: `/docs` folder
- Issues: GitHub Issues
- Email: support@stepora.app

---

**Last Updated:** March 2026
**Maintained by:** Stepora Team
