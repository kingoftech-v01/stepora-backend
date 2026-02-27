# DreamPlanner Architecture

## System Overview

```text
┌─────────────────────────────────────────────────────────────────┐
│                        CLIENTS                                   │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐    ┌─────────────┐                            │
│  │   iOS App   │    │ Android App │                            │
│  │  (Mobile    │    │  (Mobile    │                            │
│  │   Client)   │    │   Client)   │                            │
│  └──────┬──────┘    └──────┬──────┘                            │
└─────────┼──────────────────┼───────────────────────────────────┘
          │                  │
          └────────┬─────────┘
                   │
                    ┌────────▼────────┐
                    │  Load Balancer  │
                    │  (Nginx / ALB)  │
                    └────────┬────────┘
                             │
┌────────────────────────────┼────────────────────────────────────┐
│                    BACKEND SERVICES                              │
├────────────────────────────┼────────────────────────────────────┤
│            ┌───────────────┴───────────────┐                    │
│            │                               │                    │
│   ┌────────▼────────┐           ┌─────────▼─────────┐          │
│   │   Gunicorn      │           │     Daphne        │          │
│   │   (HTTP API)    │           │   (WebSocket)     │          │
│   │   Port 8000     │           │   Port 9000       │          │
│   └────────┬────────┘           └─────────┬─────────┘          │
│            │                               │                    │
│            └───────────────┬───────────────┘                    │
│                            │                                    │
│                   ┌────────▼────────┐                          │
│                   │     Django      │                          │
│                   │   Application   │                          │
│                   └────────┬────────┘                          │
│                            │                                    │
│   ┌────────────────────────┼────────────────────────┐          │
│   │                        │                        │          │
│   │  ┌─────────────┐  ┌────▼────┐  ┌─────────────┐ │          │
│   │  │   Celery    │  │  Django │  │   Celery    │ │          │
│   │  │   Worker    │  │  Channels│  │   Beat     │ │          │
│   │  │             │  │         │  │  (Scheduler)│ │          │
│   │  └──────┬──────┘  └────┬────┘  └──────┬──────┘ │          │
│   │         │              │              │        │          │
│   └─────────┼──────────────┼──────────────┼────────┘          │
│             │              │              │                    │
└─────────────┼──────────────┼──────────────┼────────────────────┘
              │              │              │
┌─────────────┼──────────────┼──────────────┼────────────────────┐
│             │      DATA LAYER             │                    │
├─────────────┼──────────────┼──────────────┼────────────────────┤
│   ┌─────────▼──────────┐   │   ┌─────────▼──────────┐         │
│   │    PostgreSQL      │   │   │      Redis         │         │
│   │    (Database)      │   │   │  (Cache + Broker)  │         │
│   └────────────────────┘   │   └────────────────────┘         │
│                            │                                   │
└────────────────────────────┼───────────────────────────────────┘
                             │
┌────────────────────────────┼───────────────────────────────────┐
│              EXTERNAL SERVICES                                  │
├────────────────────────────┼───────────────────────────────────┤
│   ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐ │
│   │   OpenAI    │  │  Agora.io   │  │  Firebase   │  │   Sentry    │ │
│   │  (GPT-4)    │  │  (RTC Calls)│  │  (FCM Push) │  │  (Errors)   │ │
│   └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘ │
└────────────────────────────────────────────────────────────────┘
```

## Technology Decisions

### Backend: Django (Python)

**Why Django over Node.js:**

1. **Mature ORM**: Django ORM handles complex queries, migrations, and relationships elegantly
2. **Admin Interface**: Built-in admin panel for data management
3. **Batteries Included**: Authentication, forms, security all built-in
4. **Celery Integration**: Native Python async task processing
5. **Django Channels**: Production-ready WebSocket support
6. **Type Safety**: Type hints with mypy for static analysis

### Database: PostgreSQL

**Why PostgreSQL:**

1. **ACID Compliance**: Full transaction support
2. **JSON Support**: JSONB for flexible schema fields
3. **Full-Text Search**: Built-in FTS capabilities
4. **Scalability**: Read replicas, partitioning support
5. **Extensions**: PostGIS for geo-features, pg_trgm for fuzzy search

### Cache/Queue: Redis

**Why Redis:**

1. **Speed**: In-memory data store
2. **Versatility**: Cache, message broker, session store
3. **Celery Support**: Native broker support
4. **Pub/Sub**: Real-time features
5. **Data Structures**: Lists, sets, sorted sets for leaderboards

## Django App Structure

```text
dreamplanner/
├── apps/
│   ├── users/              # User management
│   │   ├── models.py       # User, Profile
│   │   ├── views.py        # ViewSets
│   │   ├── serializers.py  # DRF serializers
│   │   └── urls.py         # URL routing
│   │
│   ├── dreams/             # Core domain
│   │   ├── models.py       # Dream, Goal, Task, Obstacle
│   │   ├── views.py        # CRUD + AI features
│   │   ├── services.py     # Business logic
│   │   └── signals.py      # Post-save hooks
│   │
│   ├── conversations/      # AI Chat
│   │   ├── models.py       # Conversation, Message
│   │   ├── consumers.py    # WebSocket consumers
│   │   └── routing.py      # WebSocket routing
│   │
│   ├── calendar/           # Calendar features
│   │   ├── views.py        # Date range views
│   │   └── utils.py        # Date calculations
│   │
│   └── notifications/      # Multi-channel notifications
│       ├── models.py       # Notification, WebPushSubscription, NotificationBatch
│       ├── consumers.py    # WebSocket consumer (real-time delivery)
│       ├── services.py     # NotificationDeliveryService (WebSocket + Email + Web Push)
│       └── tasks.py        # Celery tasks (scheduling, cleanup)
│
├── core/                   # Shared functionality
│   ├── authentication.py   # Token auth
│   ├── permissions.py      # DRF permissions
│   ├── pagination.py       # Cursor pagination
│   └── exceptions.py       # Custom exceptions
│
├── integrations/           # External services
│   ├── openai_service.py   # GPT-4 + DALL-E + Whisper
│   └── google_calendar.py  # Google Calendar sync
│
└── config/                 # Configuration
    ├── settings/
    │   ├── base.py         # Common settings
    │   ├── development.py  # Dev settings
    │   └── production.py   # Prod settings
    ├── celery.py           # Celery config
    ├── asgi.py             # ASGI config
    └── urls.py             # Root URLs
```

## Data Flow

### HTTP Request Flow

```text
Client Request
      │
      ▼
┌─────────────┐
│    Nginx    │ ─── Static files
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  Gunicorn   │
└──────┬──────┘
       │
       ▼
┌─────────────────────────────────────┐
│          Django Middleware          │
├─────────────────────────────────────┤
│  SecurityMiddleware                 │
│  SessionMiddleware                  │
│  AuthenticationMiddleware           │
│  TokenAuthMiddleware (custom)       │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│          URL Router                  │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│          DRF ViewSet                 │
├─────────────────────────────────────┤
│  1. Permission check                │
│  2. Serializer validation           │
│  3. Business logic (services)       │
│  4. Database operations             │
│  5. Response serialization          │
└──────────────┬──────────────────────┘
               │
               ▼
         JSON Response
```

### WebSocket Flow

```text
Client WebSocket Connect
         │
         ▼
┌─────────────┐
│   Daphne    │
└──────┬──────┘
         │
         ▼
┌─────────────────────────────────────┐
│      Django Channels                 │
├─────────────────────────────────────┤
│  AuthMiddlewareStack                │
│  URLRouter                          │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│      WebSocket Consumer              │
├─────────────────────────────────────┤
│  connect()   - Auth + join group    │
│  receive()   - Handle message       │
│  disconnect() - Cleanup             │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│      Channel Layer (Redis)           │
├─────────────────────────────────────┤
│  group_send() - Broadcast           │
│  send()       - Direct message      │
└─────────────────────────────────────┘
```

### Background Task Flow

```text
Trigger Event (API call, schedule)
              │
              ▼
┌─────────────────────────────────────┐
│         Celery Client                │
│    task.delay() / task.apply_async() │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│         Redis (Broker)               │
│         Task Queue                   │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│         Celery Worker                │
├─────────────────────────────────────┤
│  1. Fetch task from queue           │
│  2. Execute task function           │
│  3. Handle retries on failure       │
│  4. Store result (optional)         │
└─────────────────────────────────────┘
```

## Security Architecture

### Authentication Flow

```text
┌─────────────┐         ┌─────────────┐         ┌─────────────┐
│   Mobile    │         │   Django    │         │  dj-rest-   │
│    App      │         │   Backend   │         │    auth     │
└──────┬──────┘         └──────┬──────┘         └──────┬──────┘
       │                       │                       │
       │  1. Sign in           │                       │
       │──────────────────────────────────────────────▶│
       │                       │                       │
       │  2. ID Token          │                       │
       │◀──────────────────────────────────────────────│
       │                       │                       │
       │  3. API Request       │                       │
       │  (Bearer Token)       │                       │
       │──────────────────────▶│                       │
       │                       │                       │
       │                       │  4. Verify Token      │
       │                       │──────────────────────▶│
       │                       │                       │
       │                       │  5. Token Valid       │
       │                       │◀──────────────────────│
       │                       │                       │
       │  6. API Response      │                       │
       │◀──────────────────────│                       │
       │                       │                       │
```

### Security Layers

1. **Transport**: HTTPS/TLS 1.3
2. **Authentication**: Token auth (django-allauth + dj-rest-auth)
3. **Authorization**: Django permissions
4. **Input Validation**: DRF serializers
5. **SQL Injection**: Django ORM (parameterized queries)
6. **XSS**: Django template escaping
7. **CSRF**: Django CSRF middleware
8. **Rate Limiting**: Django Ratelimit
9. **Security Headers**: Django SecurityMiddleware

## Scalability Considerations

### Horizontal Scaling

```text
                    ┌─────────────┐
                    │    ALB      │
                    └──────┬──────┘
                           │
        ┌──────────────────┼──────────────────┐
        │                  │                  │
┌───────▼───────┐  ┌───────▼───────┐  ┌───────▼───────┐
│   Django 1    │  │   Django 2    │  │   Django 3    │
│   (Gunicorn)  │  │   (Gunicorn)  │  │   (Gunicorn)  │
└───────────────┘  └───────────────┘  └───────────────┘
        │                  │                  │
        └──────────────────┼──────────────────┘
                           │
              ┌────────────┼────────────┐
              │            │            │
      ┌───────▼───────┐   │   ┌───────▼───────┐
      │   PostgreSQL  │   │   │    Redis      │
      │   (Primary)   │   │   │   (Cluster)   │
      └───────┬───────┘   │   └───────────────┘
              │           │
      ┌───────▼───────┐   │
      │   PostgreSQL  │   │
      │   (Replica)   │   │
      └───────────────┘   │
                          │
        ┌─────────────────┼─────────────────┐
        │                 │                 │
┌───────▼───────┐ ┌───────▼───────┐ ┌───────▼───────┐
│  Celery W1    │ │  Celery W2    │ │  Celery W3    │
└───────────────┘ └───────────────┘ └───────────────┘
```

### Caching Strategy

| Data Type | TTL | Cache Key Pattern |
|-----------|-----|-------------------|
| User profile | 30 min | `user:{id}:profile` |
| Leaderboard | 5 min | `leaderboard:{type}:{page}` |
| Dream list | 10 min | `user:{id}:dreams` |
| AI responses | 24 hours | `ai:response:{hash}` |

## Monitoring

### Health Checks

| Endpoint | Purpose | Checks |
|----------|---------|--------|
| `/health/` | Full status | All services |
| `/health/liveness/` | K8s liveness | App running |
| `/health/readiness/` | K8s readiness | DB connected |

### Metrics

- Request latency (p50, p95, p99)
- Error rates by endpoint
- Database query times
- Redis hit/miss ratio
- Celery queue depth
- WebSocket connections

### Logging

```python
# Structured logging format
{
    "timestamp": "2024-01-28T12:00:00Z",
    "level": "INFO",
    "logger": "django.request",
    "message": "GET /api/dreams/",
    "user_id": "abc123",
    "request_id": "req-xyz",
    "duration_ms": 45,
    "status_code": 200
}
```

## Deployment Architecture

### Docker Services

```yaml
services:
  web:        # Django + Gunicorn
  daphne:     # WebSocket server
  celery:     # Background worker
  beat:       # Task scheduler
  postgres:   # Database
  redis:      # Cache + broker
  nginx:      # Reverse proxy
```

### Environment Configuration

| Variable | Purpose |
|----------|---------|
| `DJANGO_SECRET_KEY` | Session encryption |
| `DATABASE_URL` | PostgreSQL connection |
| `REDIS_URL` | Redis connection |
| `OPENAI_API_KEY` | GPT-4 access |
| `SENTRY_DSN` | Error tracking |
| `VAPID_PUBLIC_KEY` | Web Push public key |
| `VAPID_PRIVATE_KEY` | Web Push private key |
| `AGORA_APP_ID` | Agora project App ID (circle voice/video calls) |
| `AGORA_APP_CERTIFICATE` | Agora project App Certificate (RTC token generation) |

### Notification Delivery Flow

```text
Notification Created (API / Celery task)
              │
              ▼
┌─────────────────────────────────────┐
│   NotificationDeliveryService       │
├─────────────────────────────────────┤
│  1. Check user notification prefs   │
│  2. Check DND hours                │
│  3. Dispatch to enabled channels:  │
│     ├── WebSocket (channel layer)  │
│     ├── Email (django.core.mail)   │
│     └── Web Push (VAPID/pywebpush) │
│  4. Mark notification as sent      │
└─────────────────────────────────────┘
```

### WebSocket Routes

| Route | Consumer | Purpose |
|-------|----------|---------|
| `ws/ai-chat/{id}/` | AIChatConsumer | AI chat with GPT-4 streaming |
| `ws/conversations/{id}/` | AIChatConsumer | (deprecated alias for ai-chat) |
| `ws/buddy-chat/{pairing_id}/` | BuddyChatConsumer | Buddy-to-buddy chat with FCM push |
| `ws/circle-chat/{circle_id}/` | CircleChatConsumer | Circle group chat with block filtering |
| `ws/notifications/` | NotificationConsumer | Real-time notification delivery |

---

**Last Updated:** February 2026
