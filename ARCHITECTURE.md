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
│   ├── users/              # User management, gamification, achievements, 2FA, GDPR
│   ├── dreams/             # Dreams, Goals, Tasks, Obstacles, Templates, Tags, Vision Board, PDF
│   ├── conversations/      # AI Chat (AIChatConsumer WebSocket), templates, voice transcription
│   ├── calendar/           # Events, recurring events, time blocks, Google Calendar sync, iCal feed
│   ├── notifications/      # Multi-channel delivery (WebSocket + Email + Web Push), templates, preferences
│   ├── subscriptions/      # Stripe plans (SubscriptionPlan + Subscription models), webhooks, invoices
│   ├── store/              # Items, categories, XP/Stripe purchases, wishlists, gifting, refunds
│   ├── leagues/            # Leagues, seasons, auto-grouping, leaderboards, promotion/relegation, rewards
│   ├── circles/            # Circles, posts, reactions, challenges, invitations, group chat, Agora calls
│   ├── social/             # Friends, follows, blocking, reporting, feed, dream posts, encouragements
│   ├── buddies/            # Buddy pairing, encouragement, streaks, chat (BuddyChatConsumer), calls
│   ├── search/             # Unified search across dreams, users, circles
│   └── updates/            # OTA live update management for Capacitor mobile apps
│
├── core/                   # Shared functionality
│   ├── auth/               # Custom auth package (JWT via SimpleJWT, social login, email verify,
│   │                       #   password reset, 2FA challenge — settings in DP_AUTH dict)
│   ├── permissions.py      # 10 DB-driven permission classes (read from SubscriptionPlan fields)
│   ├── authentication.py   # BearerTokenAuthentication, CsrfExemptAPIMiddleware
│   ├── ai_usage.py         # Redis-backed daily AI quota tracking
│   ├── ai_validators.py    # Pydantic schemas for AI output validation
│   ├── moderation.py       # 4-tier content moderation (patterns + OpenAI API)
│   ├── sanitizers.py       # XSS sanitization (nh3-based)
│   ├── consumers.py        # Shared WebSocket consumer mixins
│   ├── middleware.py        # Security headers, last-activity tracking
│   ├── audit.py            # Structured security audit logging
│   ├── pagination.py       # Standard + large result set pagination
│   └── exceptions.py       # Custom DRF exception handler
│
├── integrations/           # External services
│   ├── openai_service.py   # GPT-4 + DALL-E 3 + Whisper + GPT-4V
│   ├── checkin_tools.py    # AI check-in function calling tools
│   └── google_calendar.py  # Google Calendar sync
│
└── config/                 # Configuration
    ├── settings/
    │   ├── base.py         # Common settings (DP_AUTH config dict)
    │   ├── development.py  # Dev settings
    │   └── production.py   # Prod settings
    ├── celery.py           # Celery config + beat schedule
    ├── asgi.py             # ASGI config (HTTP + WebSocket routing)
    └── urls.py             # Root URLs (/api/v1/ canonical + /api/ backward-compat)
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
│   Mobile    │         │   Django    │         │  core.auth  │
│    App      │         │   Backend   │         │  (SimpleJWT)│
└──────┬──────┘         └──────┬──────┘         └──────┬──────┘
       │                       │                       │
       │  1. Login / Register  │                       │
       │──────────────────────▶│                       │
       │                       │                       │
       │                       │  2. Validate creds    │
       │                       │──────────────────────▶│
       │                       │                       │
       │  3. JWT (access +     │                       │
       │     refresh cookie)   │                       │
       │◀──────────────────────│                       │
       │                       │                       │
       │  4. API Request       │                       │
       │  (Bearer access_token)│                       │
       │──────────────────────▶│                       │
       │                       │                       │
       │                       │  5. Verify JWT        │
       │                       │──────────────────────▶│
       │                       │                       │
       │  6. API Response      │                       │
       │◀──────────────────────│                       │
       │                       │                       │
```

**Note:** If 2FA is enabled, step 3 returns a challenge token instead of JWT.
The client must verify the OTP via `POST /api/auth/2fa-challenge/` to receive the JWT.

Native clients (Android/iOS) send `X-Client-Platform: native` to receive refresh
tokens in the response body instead of httpOnly cookies.

Social login (Google/Apple) verifies ID tokens directly via `core.auth.social`
(no allauth adapters).

### Security Layers

1. **Transport**: HTTPS/TLS 1.3
2. **Authentication**: Custom `core.auth` package with SimpleJWT (JWT access + httpOnly refresh cookies)
3. **Authorization**: 10 DB-driven permission classes reading from `SubscriptionPlan` model
4. **Input Validation**: DRF serializers + `core/sanitizers.py` (XSS) + `core/validators.py`
5. **SQL Injection**: Django ORM (parameterized queries)
6. **XSS**: `nh3` sanitizer on backend, DOMPurify on frontend
7. **CSRF**: Django CSRF middleware (exempt for `/api/` routes using token auth)
8. **Rate Limiting**: DRF throttling + Nginx rate limits + Redis-backed daily AI quotas
9. **Security Headers**: `SecurityHeadersMiddleware` (CSP, COOP, CORP, X-Frame-Options: DENY)
10. **Content Moderation**: 4-tier pipeline (jailbreak + roleplay + harmful patterns + OpenAI API)

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
| `AGORA_APP_ID` | Agora project App ID (RTM messaging + RTC calls) |
| `AGORA_APP_CERTIFICATE` | Agora project App Certificate (token generation) |

> **Agora setup:** Signaling must be enabled in the [Agora Console](https://console.agora.io) (Projects → All features → Signaling → select data center + subscribe). Without this, RTM login fails with error `2010026`. See `DEPLOYMENT.md`.

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

## League & Auto-Grouping System

The `leagues` app implements a competitive ranking system with automatic group management.

### Architecture

```text
User earns XP
      |
      v
LeagueService.update_standing()
      |
      +--> Determine league tier (Bronze-Legend) from total XP
      +--> Create/update LeagueStanding for active Season
      +--> Recalculate ranks (dense ranking)
      +--> assign_user_to_group() on new standing or tier change
```

### Key Models

- **SeasonConfig** (singleton) -- Admin-configurable parameters: season duration, group sizes (target/max/min), promotion/relegation XP thresholds, auto-create toggle.
- **League** -- 7 static tiers (Bronze through Legend) with XP ranges.
- **Season** -- Time-bounded competitive period. Status lifecycle: `pending` -> `active` -> `processing` -> `ended`.
- **LeagueStanding** -- User's rank, XP, and stats within a season. One per user per season.
- **LeagueGroup** -- Competitive pod within a league tier for a season (target 20 users).
- **LeagueGroupMembership** -- Links standings to groups (OneToOne on standing).

### Automated Processes (Celery Beat)

| Schedule | Task | Purpose |
|----------|------|---------|
| Hourly | `auto_activate_pending_seasons` | Activate scheduled seasons |
| Daily 12:05 AM | `check_season_end` | Detect ended seasons, trigger processing |
| Daily 11:55 PM | `create_daily_rank_snapshots` | Historical rank tracking |
| Sunday 11 PM | `send_league_change_notifications` | Weekly promotion/demotion cycle |
| Monday 3 AM | `rebalance_groups_task` | Rebalance groups across all leagues |

Season-end processing chains: rewards calculation, promotion/relegation flags, notifications, then auto-creates the next season with carried-over standings and fresh group assignments.

### Admin Configuration

All settings are managed via Django admin at `/admin/leagues/`. The `SeasonConfig` singleton controls group sizing and season behavior. See `apps/leagues/README.md` for a detailed admin configuration guide.

---

**Last Updated:** March 2026
