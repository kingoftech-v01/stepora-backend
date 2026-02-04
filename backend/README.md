# DreamPlanner Backend - Django API

Complete Django REST API backend for DreamPlanner mobile application.

## 🎯 Features

### Core Features
- **User Management**: Firebase authentication with custom Django backend
- **Dreams System**: Create, manage, and track life goals
- **AI Integration**: GPT-4 powered planning, motivation, and coaching
- **Real-time Chat**: WebSocket support for AI conversations
- **Smart Notifications**: FCM push notifications with DND support
- **Gamification**: XP, levels, streaks, and achievements
- **Calendar Integration**: Task scheduling and time management

### Advanced Features
- **2-Minute Start**: Micro-actions to overcome procrastination
- **Rescue Mode**: AI detects and re-engages inactive users
- **Proactive AI Coach**: Personalized suggestions based on patterns
- **Vision Boards**: DALL-E generated motivational images
- **Dream Buddy**: Accountability partner matching
- **Obstacle Prediction**: AI predicts and suggests solutions

## 🏗️ Tech Stack

- **Framework**: Django 5.0.1 + Django REST Framework 3.14.0
- **Database**: PostgreSQL 15
- **Caching**: Redis 7
- **Real-time**: Django Channels 4.0.0 (WebSocket)
- **Background Jobs**: Celery 5.3.4 + Redis
- **Authentication**: Firebase Admin SDK
- **AI**: OpenAI GPT-4 + DALL-E 3
- **Push Notifications**: Firebase Cloud Messaging
- **Testing**: pytest + pytest-django + pytest-cov
- **Deployment**: Docker + Docker Compose + Gunicorn + Nginx

## 📁 Project Structure

```
backend/
├── config/                      # Django configuration
│   ├── settings/
│   │   ├── base.py             # Base settings
│   │   ├── development.py      # Development settings
│   │   ├── production.py       # Production settings
│   │   └── testing.py          # Test settings
│   ├── urls.py                 # URL routing
│   ├── asgi.py                 # ASGI config (WebSocket)
│   ├── wsgi.py                 # WSGI config (HTTP)
│   └── celery.py               # Celery configuration
│
├── apps/                        # Django applications
│   ├── users/                  # User management
│   ├── dreams/                 # Dreams, Goals, Tasks
│   ├── conversations/          # AI chat (WebSocket)
│   ├── notifications/          # Push notifications
│   └── calendar/               # Calendar views & scheduling
│
├── core/                        # Core utilities
│   ├── authentication.py       # Firebase auth backend
│   ├── permissions.py          # DRF permissions
│   ├── exceptions.py           # Custom exceptions
│   └── pagination.py           # Pagination classes
│
├── integrations/                # External services
│   ├── openai_service.py       # OpenAI GPT-4 integration
│   ├── fcm_service.py          # Firebase Cloud Messaging
│   └── firebase_admin_service.py
│
├── requirements/                # Python dependencies
│   ├── base.txt
│   ├── development.txt
│   ├── production.txt
│   └── testing.txt
│
├── docker/                      # Docker configuration
│   └── nginx.conf              # Nginx config
│
├── Dockerfile                   # Production Docker image
├── docker-compose.yml           # Local development
├── docker-compose.prod.yml      # Production compose
├── Makefile                     # Convenience commands
├── pytest.ini                   # Test configuration
└── manage.py                    # Django management
```

## 🚀 Quick Start

### Prerequisites

- Docker & Docker Compose
- Python 3.11+ (for local development)
- Firebase project (for authentication)
- OpenAI API key
- PostgreSQL 15 (if not using Docker)
- Redis 7 (if not using Docker)

### 1. Environment Setup

Create `.env` file based on `.env.example`:

```bash
cp .env.example .env
```

Required environment variables:

```env
# Django
SECRET_KEY=your-secret-key-here
DJANGO_SETTINGS_MODULE=config.settings.development
ALLOWED_HOSTS=localhost,127.0.0.1
DEBUG=True

# Database
DATABASE_URL=postgresql://dreamplanner:password@localhost:5432/dreamplanner

# Redis
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0

# Firebase
FIREBASE_CREDENTIALS=path/to/firebase-credentials.json

# OpenAI
OPENAI_API_KEY=your-openai-api-key

# CORS
CORS_ALLOWED_ORIGINS=http://localhost:3000,http://localhost:8081
```

### 2. Start with Docker (Recommended)

```bash
# Build images
make build

# Start all services
make up

# Run migrations
make migrate

# Create superuser
make createsuperuser

# View logs
make logs
```

Services will be available at:
- **API**: http://localhost:8000
- **Admin**: http://localhost:8000/admin
- **WebSocket**: ws://localhost:9000
- **Flower** (Celery monitoring): http://localhost:5555

### 3. Local Development (Without Docker)

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements/development.txt

# Run migrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Start development server
python manage.py runserver

# In separate terminals:
# Start Celery worker
celery -A config worker -l info

# Start Celery beat
celery -A config beat -l info

# Start Channels (WebSocket)
daphne -b 0.0.0.0 -p 9000 config.asgi:application
```

## 🧪 Testing

### Run Tests

```bash
# All tests
make test

# With coverage
make test-cov

# Unit tests only
make test-unit

# Integration tests only
make test-integration

# Generate coverage report
make coverage
```

### Test Coverage

Current target: **80%+ coverage** across all modules.

Coverage reports are generated in `htmlcov/index.html`.

## 📚 API Documentation

### Base URL
- Development: `http://localhost:8000/api`
- Production: `https://api.dreamplanner.app/api`

### Authentication

All API requests (except authentication endpoints) require Firebase ID token:

```
Authorization: Bearer <firebase_id_token>
```

### Main Endpoints

#### Users
- `GET /api/users/me/` - Get current user
- `PUT /api/users/me/` - Update user profile
- `POST /api/users/me/register-fcm-token/` - Register device for push notifications
- `GET /api/users/me/stats/` - Get user statistics

#### Dreams
- `GET /api/dreams/` - List user's dreams
- `POST /api/dreams/` - Create new dream
- `GET /api/dreams/{id}/` - Get dream details
- `PUT /api/dreams/{id}/` - Update dream
- `DELETE /api/dreams/{id}/` - Delete dream
- `POST /api/dreams/{id}/analyze/` - AI analysis
- `POST /api/dreams/{id}/generate-plan/` - Generate complete plan with AI
- `POST /api/dreams/{id}/generate-two-minute-start/` - Generate micro-action
- `POST /api/dreams/{id}/generate-vision/` - Generate vision board image

#### Goals
- `GET /api/dreams/{dream_id}/goals/` - List goals for dream
- `POST /api/dreams/{dream_id}/goals/` - Create goal
- `PUT /api/goals/{id}/` - Update goal
- `POST /api/goals/{id}/complete/` - Mark goal as completed

#### Tasks
- `GET /api/goals/{goal_id}/tasks/` - List tasks for goal
- `POST /api/goals/{goal_id}/tasks/` - Create task
- `PUT /api/tasks/{id}/` - Update task
- `POST /api/tasks/{id}/complete/` - Complete task (awards XP)
- `POST /api/tasks/{id}/reschedule/` - Reschedule task

#### Conversations (Chat)
- `GET /api/conversations/` - List conversations
- `POST /api/conversations/` - Start new conversation
- `GET /api/conversations/{id}/messages/` - Get messages
- `POST /api/conversations/{id}/messages/` - Send message

#### WebSocket (Real-time Chat)
```
ws://localhost:9000/ws/conversations/{conversation_id}/
```

Send message:
```json
{
  "type": "message",
  "message": "Hello AI!"
}
```

Receive streaming response:
```json
{"type": "stream_start"}
{"type": "stream_chunk", "chunk": "Hello"}
{"type": "stream_chunk", "chunk": " there!"}
{"type": "stream_end"}
{"type": "message", "message": {...}}
```

#### Notifications
- `GET /api/notifications/` - List notifications
- `POST /api/notifications/{id}/mark_read/` - Mark as read
- `POST /api/notifications/mark_all_read/` - Mark all as read
- `GET /api/notifications/unread_count/` - Get unread count

#### Calendar
- `GET /api/calendar/` - Get calendar events (date range)
- `GET /api/calendar/today/` - Get today's tasks
- `GET /api/calendar/week/` - Get weekly view
- `GET /api/calendar/overdue/` - Get overdue tasks
- `POST /api/calendar/reschedule/` - Reschedule multiple tasks
- `POST /api/calendar/auto-schedule/` - Auto-schedule unscheduled tasks

#### Health Checks
- `GET /health/` - General health check
- `GET /health/liveness/` - Liveness probe
- `GET /health/readiness/` - Readiness probe (checks DB)

## 🔧 Configuration

### Django Settings

Settings are split into multiple files:
- `base.py` - Common settings
- `development.py` - Local development
- `production.py` - Production (AWS)
- `testing.py` - Test environment

Activate specific settings:
```bash
export DJANGO_SETTINGS_MODULE=config.settings.production
```

### Celery Tasks

Scheduled tasks (Celery Beat):

| Task | Schedule | Description |
|------|----------|-------------|
| `process_pending_notifications` | Every 1 minute | Send pending notifications |
| `send_reminder_notifications` | Every 15 minutes | Send goal reminders |
| `generate_daily_motivation` | Daily at 8 AM | Motivational messages |
| `check_inactive_users` | Daily at 9 AM | Rescue mode |
| `send_weekly_report` | Sunday at 10 AM | Weekly progress report |
| `update_dream_progress` | Daily at 3 AM | Recalculate dream progress |
| `check_overdue_tasks` | Daily at 10 AM | Notify overdue tasks |
| `cleanup_old_notifications` | Weekly (Monday 2 AM) | Delete old notifications |
| `cleanup_abandoned_dreams` | Weekly (Sunday 3 AM) | Archive inactive dreams |

## 🎨 Code Quality

### Linting

```bash
# Run linters
make lint

# Format code
make format
```

Tools used:
- **black** - Code formatting
- **isort** - Import sorting
- **flake8** - Linting

### Pre-commit Hooks

```bash
# Install hooks
make install-hooks

# Run manually
make pre-commit
```

## 🐳 Docker Commands

```bash
# Development
make build          # Build images
make up             # Start services
make down           # Stop services
make restart        # Restart services
make logs           # View all logs
make logs-web       # View web logs
make logs-celery    # View Celery logs
make shell          # Django shell
make bash           # Bash shell
make migrate        # Run migrations
make test           # Run tests
make clean          # Clean up containers

# Production
make build-prod     # Build production image
make up-prod        # Start production services
make down-prod      # Stop production services
make logs-prod      # View production logs

# Database
make reset-db       # Reset database (WARNING: deletes data)
make backup-db      # Backup database
make restore-db     # Restore from backup
```

## 📊 Monitoring

### Health Checks

```bash
# Check service health
make health

# Or manually
curl http://localhost:8000/health/
curl http://localhost:8000/health/readiness/
```

### Celery Monitoring (Flower)

Access at http://localhost:5555 when services are running.

### Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f web
docker-compose logs -f celery
docker-compose logs -f celery-beat
```

## 🚢 Deployment

### AWS Deployment (ECS + RDS + ElastiCache)

1. **Build and push Docker image**:
```bash
# Build
docker build -t dreamplanner-api:latest .

# Tag
docker tag dreamplanner-api:latest ${ECR_REGISTRY}/dreamplanner-api:latest

# Push
docker push ${ECR_REGISTRY}/dreamplanner-api:latest
```

2. **Set environment variables** in AWS Secrets Manager or ECS task definition

3. **Deploy to ECS**:
```bash
aws ecs update-service \
  --cluster dreamplanner-prod \
  --service dreamplanner-api \
  --force-new-deployment
```

4. **Run migrations**:
```bash
aws ecs run-task \
  --cluster dreamplanner-prod \
  --task-definition dreamplanner-migrate \
  --launch-type FARGATE
```

### Environment Variables (Production)

Required for production:
- `SECRET_KEY` - Django secret key
- `DATABASE_URL` - PostgreSQL connection string
- `REDIS_URL` - Redis connection string
- `FIREBASE_CREDENTIALS` - Firebase service account JSON
- `OPENAI_API_KEY` - OpenAI API key
- `ALLOWED_HOSTS` - Comma-separated hostnames
- `CORS_ALLOWED_ORIGINS` - Allowed origins for CORS
- `AWS_ACCESS_KEY_ID` - AWS credentials
- `AWS_SECRET_ACCESS_KEY` - AWS credentials
- `AWS_STORAGE_BUCKET_NAME` - S3 bucket for media
- `SENTRY_DSN` - Sentry error tracking

## 🔐 Security

### Best Practices Implemented

- ✅ Firebase authentication with token verification
- ✅ HTTPS enforced (production)
- ✅ CORS configured
- ✅ SQL injection protection (ORM)
- ✅ XSS protection (Django middleware)
- ✅ CSRF protection (DRF)
- ✅ Rate limiting (Nginx)
- ✅ Non-root Docker user
- ✅ Secrets in environment variables
- ✅ Security headers (Nginx)

### Secrets Management

**Never commit secrets!**

- Use `.env` for local development (git-ignored)
- Use AWS Secrets Manager for production
- Rotate keys regularly

## 🤝 Contributing

### Development Workflow

1. Create feature branch
2. Make changes
3. Write/update tests
4. Run tests: `make test-cov`
5. Format code: `make format`
6. Commit changes
7. Push and create PR

### Coding Standards

- Follow PEP 8
- Write docstrings for all functions/classes
- Maintain 80%+ test coverage
- Use type hints where appropriate

## 📝 License

Proprietary - DreamPlanner

## 🆘 Troubleshooting

### Common Issues

**Database connection error**:
```bash
# Ensure PostgreSQL is running
docker-compose ps
docker-compose up -d db
```

**Celery not processing tasks**:
```bash
# Check Celery worker logs
make logs-celery

# Restart Celery
docker-compose restart celery
```

**WebSocket connection failed**:
```bash
# Check Daphne logs
docker-compose logs -f daphne

# Ensure Redis is running
docker-compose ps redis
```

**Tests failing**:
```bash
# Use test database
export DJANGO_SETTINGS_MODULE=config.settings.testing

# Run specific test
pytest apps/users/tests.py::TestUserModel::test_create_user -v
```

## 📞 Support

For issues or questions:
- Check logs: `make logs`
- Review documentation
- Run health checks: `make health`

---

**Built with ❤️ for DreamPlanner**
