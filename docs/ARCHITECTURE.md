# DreamPlanner — System Architecture & Navigation Guide

> **Purpose**: This document is your map to the entire codebase. If you need to find where something lives, how systems connect, or what infrastructure exists — start here.

---

## Table of Contents

1. [Request Flow](#request-flow)
2. [App Map](#app-map)
3. [Feature Location Guide](#feature-location-guide)
4. [Authentication & Authorization](#authentication--authorization)
5. [Subscription Tiers & Feature Gating](#subscription-tiers--feature-gating)
6. [AI Pipeline](#ai-pipeline)
7. [Real-Time Infrastructure (WebSocket)](#real-time-infrastructure-websocket)
8. [Background Tasks (Celery)](#background-tasks-celery)
9. [Django Signals](#django-signals)
10. [Management Commands (Seed Data)](#management-commands-seed-data)
11. [Cross-App Flows](#cross-app-flows)
12. [Per-App Documentation Index](#per-app-documentation-index)

---

## Request Flow

### HTTP API Request

```
Client (Mobile/Web)
  │
  ▼
Nginx (rate limit: 10 req/s API, 5 req/s WS)
  │
  ▼
Gunicorn / Daphne
  │
  ▼
SecurityHeadersMiddleware        (core/middleware.py)
  │  Adds CSP, X-Frame-Options, Referrer-Policy, etc.
  ▼
LastActivityMiddleware           (core/middleware.py)
  │  Updates user.last_seen, user.is_online (throttled: 1x/60s)
  ▼
CsrfExemptAPIMiddleware          (core/authentication.py)
  │  Skips CSRF for /api/ routes with token auth
  ▼
ExpiringTokenAuthentication      (core/authentication.py)
  │  Validates Bearer/Token header, checks 24h expiry
  ▼
DRF Throttling                   (core/throttles.py)
  │  Per-feature rate limits (ai_chat, ai_plan, subscription, store_purchase)
  ▼
DRF Permission Classes           (core/permissions.py)
  │  Subscription-based: IsOwner, IsPremiumUser, IsProUser, CanUseAI, etc.
  ▼
ViewSet / APIView                (apps/{app}/views.py)
  │
  ▼
Serializer (validate + sanitize) (apps/{app}/serializers.py)
  │  Uses core/sanitizers.py for XSS protection
  ▼
Model / QuerySet                 (apps/{app}/models.py)
  │
  ▼
JSON Response (with pagination)  (core/pagination.py)
```

### WebSocket Connection

```
Client
  │
  ▼
ws://host/ws/{path}/?token=<auth_token>
  │
  ▼
AllowedHostsOriginValidator      (config/asgi.py)
  │
  ▼
TokenAuthMiddlewareStack         (core/websocket_auth.py)
  │  Extracts token from query string, sets scope['user']
  ▼
URL Router                       (config/asgi.py → app routing.py)
  │
  ▼
Consumer                         (apps/{app}/consumers.py)
  │  AsyncWebsocketConsumer with channel group messaging
  ▼
Channel Layer (Redis)            Broadcasts to group members
```

### Async Task Flow

```
View / Signal / Celery Beat
  │
  ▼
task.delay() or task.apply_async()
  │
  ▼
Redis Broker
  │
  ▼
Celery Worker
  │
  ▼
External Service (OpenAI / Stripe / Google / Email)
```

---

## App Map

```
dreamplanner/
├── apps/
│   ├── users/           User model, auth, gamification, 2FA, achievements, GDPR
│   ├── dreams/          Dreams, Goals, Tasks, Obstacles, Templates, Tags, Vision Board, PDF
│   ├── conversations/   AI chat (AIChatConsumer WebSocket), templates, voice transcription
│   ├── notifications/   Push notifications, templates, preferences, delivery service
│   ├── calendar/        Events, recurring, time blocks, Google Calendar, iCal feed
│   ├── subscriptions/   Stripe plans, checkout, webhooks, invoices, analytics
│   ├── store/           Items, categories, purchases, wishlists, gifting, refunds
│   ├── leagues/         Leagues, seasons, leaderboards, rank snapshots, rewards
│   ├── circles/         Circles, posts, reactions, challenges, invitations, group chat (CircleChatConsumer), Agora voice/video calls
│   ├── social/          Friends, follows, blocking, reporting, activity feed, search, dream posts, encouragements
│   └── buddies/         Buddy pairing, encouragement, check-in reminders, real-time chat (BuddyChatConsumer), call broadcast
├── core/                Auth, permissions, throttling, sanitizers, middleware, moderation,
│                        AI validators, audit logging, AI usage tracking, pagination,
│                        WebSocket consumer mixins (RateLimitMixin, AuthenticatedConsumerMixin, BlockingMixin, ModerationMixin)
├── integrations/        OpenAI service (GPT-4, DALL-E 3, Whisper, GPT-4V)
├── config/              Django settings, Celery, ASGI/WSGI, URL routing
├── docs/                Documentation (this file, cross-app flows, specs)
└── docker/              Docker + Nginx configs
```

### App Dependencies

| App | Depends On |
| --- | --- |
| `dreams` | `users` (User, GamificationProfile), `notifications` (send notifications) |
| `conversations` | `users` (User), `buddies` (BuddyPairing), `dreams` (Dream) |
| `calendar` | `users` (User), `dreams` (Task) |
| `notifications` | `users` (User, UserSettings) |
| `subscriptions` | `users` (User) |
| `store` | `users` (User, GamificationProfile) |
| `leagues` | `users` (User, GamificationProfile) |
| `circles` | `users` (User), `social` (BlockedUser), `notifications` (push delivery) |
| `social` | `users` (User), `dreams` (Dream) |
| `buddies` | `users` (User), `conversations` (Conversation), `social` (BlockedUser) |
| `core` | No app dependencies (standalone utilities) |
| `integrations` | No app dependencies (standalone services) |

---

## Feature Location Guide

| If you need to... | Go to | Key files |
| --- | --- | --- |
| Add a new API endpoint | `apps/{app}/views.py` + `urls.py` | Pattern: ViewSet + SimpleRouter |
| Gate a feature by subscription | `core/permissions.py` | `HasPremium`, `HasPro`, `CanUseAI`, `CanUseCircles`, etc. |
| Add an AI-powered feature | `integrations/openai_service.py` | + `core/ai_validators.py` for output validation |
| Track daily AI usage quotas | `core/ai_usage.py` | Redis-backed per-user counters, 5 categories |
| Send a notification | `apps/notifications/services.py` | `NotificationDeliveryService.send()` |
| Moderate user content | `core/moderation.py` | 3-tier: patterns → OpenAI API → manual review |
| Validate AI outputs | `core/ai_validators.py` | Pydantic schemas for plans, chat, calibration, etc. |
| Sanitize user input (XSS) | `core/sanitizers.py` | `sanitize_text()`, `sanitize_html()`, `sanitize_url()` |
| Validate input fields | `core/validators.py` | `validate_uuid()`, `validate_display_name()`, etc. |
| Log security events | `core/audit.py` | `log_auth_failure()`, `log_jailbreak_attempt()`, etc. |
| Add a Celery background task | `apps/{app}/tasks.py` | Register periodic tasks in `config/celery.py` beat schedule |
| Add a WebSocket consumer | `apps/{app}/consumers.py` | Register route in `apps/{app}/routing.py` + `config/asgi.py` |
| Add a management command | `apps/{app}/management/commands/` | Follow `seed_*.py` pattern for seed data |
| Handle Stripe webhooks | `apps/subscriptions/services.py` | `StripeService.handle_webhook_event()` |
| Encrypt sensitive fields | Import `EncryptedTextField` | Used in: social (reports, blocks), users (bio, location) |
| Add custom pagination | `core/pagination.py` | `StandardResultsSetPagination` (20/page), `LargeResultsSetPagination` (50/page) |
| Add rate limiting | `core/throttles.py` | Create `UserRateThrottle` subclass with scope |
| Handle errors consistently | `core/exceptions.py` | `custom_exception_handler` wraps all errors |
| Use shared WebSocket mixins | `core/consumers.py` | `RateLimitMixin`, `AuthenticatedConsumerMixin`, `BlockingMixin`, `ModerationMixin` |
| Start a circle voice/video call | `apps/circles/views.py` | `CircleViewSet.start_call()` — Agora RTC token generation |
| Create a dream post | `apps/social/views.py` | `DreamPostViewSet` — feed, like, comment, encourage |

---

## Authentication & Authorization

### JWT Auth Flow

```
1. POST /api/auth/registration/     → Creates user, returns JWT (access + refresh)
   POST /api/auth/login/            → Validates credentials, returns JWT
                                      (or challenge token if 2FA enabled)
   POST /api/auth/2fa-challenge/    → Verifies OTP with challenge token, returns JWT

2. All subsequent requests:
   Authorization: Bearer <access_token>

3. Access token is short-lived; refresh token is set as httpOnly cookie on web.
   Native clients send X-Client-Platform: native to receive tokens in response body.
   Silent refresh on page load via POST /api/auth/token/refresh/.
```

**Implementation**: `core/auth/views.py` → `NativeAwareLoginView`, `TwoFactorChallengeView`

**Settings**: `DP_AUTH` dict in `config/settings/base.py` (NOT `REST_AUTH`)

### Social Auth

```
POST /api/auth/google/    → Google ID token verified directly → JWT tokens
POST /api/auth/apple/     → Apple ID token verified directly → JWT tokens
```

**Implementation**: `core/auth/views.py` → `GoogleLoginView`, `AppleLoginView`
**Token verification**: `core/auth/social.py` (verifies tokens directly, no allauth adapters)

### Auth Emails

All auth-related emails (verification, password reset, welcome, login notification, password changed) are sent asynchronously via Celery tasks defined in `core/auth/tasks.py`.

### Two-Factor Authentication (TOTP)

```
POST /api/users/2fa/setup/         → Generate secret + QR code
POST /api/users/2fa/verify/        → Verify code, enable 2FA
POST /api/users/2fa/disable/       → Disable 2FA
GET  /api/users/2fa/status/        → Check if 2FA is enabled
POST /api/users/2fa/backup-codes/  → Regenerate backup codes
```

### WebSocket Auth

```
ws://host/ws/{path}/?token=<auth_token>
```

Token extracted from query string by `TokenWebSocketMiddleware` (`core/websocket_auth.py`).

---

## Subscription Tiers & Feature Gating

### Tier Comparison

| Feature | Free | Premium ($19.99/mo) | Pro ($29.99/mo) |
| --- | --- | --- | --- |
| Active dreams | 3 max | 10 max | Unlimited |
| AI coaching & chat | No | Yes | Yes |
| AI plan generation | No | Yes | Yes |
| Dream Buddies | No | Yes | Yes |
| Leagues | No | Yes | Yes |
| Store purchasing | No | Yes | Yes |
| Circle joining | No | Yes | Yes |
| Circle creation | No | No | Yes |
| Vision Board (DALL-E) | No | No | Yes |
| Social feed | No | Yes | Yes |
| Ads shown | Yes | No | No |

### AI Daily Quotas

| Category | Actions Included | Free | Premium | Pro |
| --- | --- | --- | --- | --- |
| `ai_chat` | send_message, websocket_chat, send_image | 0 | 50 | 200 |
| `ai_plan` | analyze_dream, calibration, generate_plan, two_minute_start | 0 | 10 | 50 |
| `ai_image` | generate_vision (DALL-E) | 0 | 0 | 10 |
| `ai_voice` | send_voice, transcribe (Whisper) | 0 | 10 | 50 |
| `ai_background` | daily_motivation, weekly_report, rescue_message, conversation_summary | 3 | 20 | 100 |

**Quota tracking**: `core/ai_usage.py` → `AIUsageTracker` (Redis keys: `ai_usage:{user_id}:{category}:{YYYY-MM-DD}`)

### Permission Classes (`core/permissions.py`)

| Class | Check | Used By |
| --- | --- | --- |
| `IsOwner` | `obj.user == request.user` | All apps (object-level) |
| `IsPremiumUser` | `user.is_premium()` | General premium check |
| `IsProUser` | `user.get_active_plan().tier == 'pro'` | General pro check |
| `CanCreateDream` | `user.can_create_dream()` (limit check) | Dreams (POST only) |
| `CanUseAI` | Premium or Pro | Conversations, Dreams AI endpoints |
| `CanUseBuddy` | Premium or Pro | Buddies |
| `CanUseCircles` | Pro creates, Premium+ reads/joins | Circles |
| `CanUseVisionBoard` | Pro only | Dreams (vision board) |
| `CanUseLeague` | Premium or Pro | Leagues |
| `CanUseStore` | Premium or Pro | Store (purchasing) |
| `CanUseSocialFeed` | Premium or Pro | Social (full feed) |

---

## AI Pipeline

### Architecture

```
User Request
  │
  ▼
Permission Check (CanUseAI)          core/permissions.py
  │
  ▼
Quota Check (AIUsageTracker)         core/ai_usage.py
  │  Redis: ai_usage:{user_id}:{category}:{date}
  ▼
Content Moderation (input)           core/moderation.py
  │  Tier 1: Jailbreak pattern detection (regex)
  │  Tier 2: Roleplay pattern detection (regex)
  │  Tier 3: Harmful content patterns (regex)
  │  Tier 4: OpenAI Moderation API (omni-moderation-latest)
  ▼
OpenAI API Call                      integrations/openai_service.py
  │  Ethical preamble prepended to ALL prompts
  │  Models: GPT-4 (chat/plan), DALL-E 3 (images), Whisper (voice)
  │  Retry: 3 attempts with exponential backoff
  ▼
Output Validation (Pydantic)         core/ai_validators.py
  │  PlanResponseSchema, ChatResponseSchema, etc.
  ▼
Output Safety Check                  core/ai_validators.py
  │  validate_ai_output_safety() — harmful content detection
  │  check_ai_character_integrity() — jailbreak/persona detection
  ▼
Quota Increment                      core/ai_usage.py
  │
  ▼
Response to User
```

### OpenAI Service Methods (`integrations/openai_service.py`)

| Method | Model | Purpose |
| --- | --- | --- |
| `chat()` / `chat_async()` / `chat_stream_async()` | GPT-4 | Conversation with optional function calling |
| `generate_plan()` | GPT-4 | Structured plan from dream + calibration data |
| `analyze_dream()` | GPT-4 | Category, difficulty, challenges, approach |
| `generate_calibration_questions()` | GPT-4 | Initial (7) or follow-up questions |
| `generate_calibration_summary()` | GPT-4 | User profile synthesis from Q&A |
| `generate_motivational_message()` | GPT-4 | 1-2 sentence personalized encouragement |
| `generate_two_minute_start()` | GPT-4 | Micro-action (30s-2min) to start a dream |
| `generate_rescue_message()` | GPT-4 | Re-engagement for inactive users |
| `transcribe_audio()` | Whisper | Voice message transcription |
| `analyze_image()` | GPT-4V | Image analysis |
| `generate_vision_image()` | DALL-E 3 | Vision board image generation |

### AI Function Calling

The AI chat supports function calls that create/complete tasks and goals:

| Function | Parameters | Action |
| --- | --- | --- |
| `create_task` | title, description, goal_id | Creates a new task |
| `complete_task` | task_id | Marks task as completed |
| `create_goal` | title, description, dream_id | Creates a new goal |

---

## Real-Time Infrastructure (WebSocket)

### Consumers

| Consumer | File | WebSocket URL | Channel Group | Purpose |
| --- | --- | --- | --- | --- |
| `AIChatConsumer` | `apps/conversations/consumers.py` | `ws/ai-chat/{id}/` | `ai_chat_{id}` | AI chat with GPT-4 streaming, content moderation, quota tracking |
| `BuddyChatConsumer` | `apps/buddies/consumers.py` | `ws/buddy-chat/{pairing_id}/` | `buddy_chat_{pairing_id}` | Buddy-to-buddy messaging with FCM push, block enforcement |
| `CircleChatConsumer` | `apps/circles/consumers.py` | `ws/circle-chat/{circle_id}/` | `circle_chat_{circle_id}` | Circle group chat with block filtering, call notifications |
| `NotificationConsumer` | `apps/notifications/consumers.py` | `ws/notifications/` | `notifications_{user_id}` | Real-time notification push, unread count updates |

> **Note:** The deprecated alias `ws/conversations/{id}/` still routes to `AIChatConsumer` (formerly `ChatConsumer`) for backward compatibility.

All chat consumers use shared mixins from `core/consumers.py`: `RateLimitMixin`, `AuthenticatedConsumerMixin`, `BlockingMixin`, `ModerationMixin`.

### WebSocket Events

**AIChatConsumer** receives:
- `message` — User message → content moderation → AI response (streamed)
- `function_call` — Explicit function call (create_task, complete_task, create_goal)
- `typing` — Typing indicator broadcast

**BuddyChatConsumer** receives:
- `message` — Buddy message → content moderation → broadcast to pair → FCM push
- `typing` — Typing indicator broadcast
- `mark_read` — Mark messages as read

**BuddyChatConsumer** sends (via channel group):
- `chat_message` — New message from partner
- `typing_status` — Partner typing indicator
- `call_started` — Buddy call initiated (broadcast from REST endpoint)

**CircleChatConsumer** receives:
- `message` — Circle message → content moderation → save → broadcast (with block filtering)
- `typing` — Typing indicator broadcast

**CircleChatConsumer** sends (via channel group):
- `circle_message` — New message from member (filtered by blocks)
- `typing_status` — Member typing indicator
- `call_started` — Circle call initiated (broadcast from REST endpoint)

**NotificationConsumer** receives:
- `mark_read` — Mark single notification read
- `mark_all_read` — Mark all notifications read

**NotificationConsumer** sends (via channel group):
- `send_notification` — Push new notification to client
- `unread_count_update` — Updated unread count

### Routing Configuration

- `config/asgi.py` — Combines all WebSocket routes under `ProtocolTypeRouter`
- `apps/conversations/routing.py` — AI chat routes (`ws/ai-chat/` + deprecated `ws/conversations/`)
- `apps/buddies/routing.py` — Buddy chat route (`ws/buddy-chat/`)
- `apps/circles/routing.py` — Circle chat route (`ws/circle-chat/`)
- `apps/notifications/routing.py` — Notification route (`ws/notifications/`)

---

## Background Tasks (Celery)

### Periodic Tasks (Celery Beat Schedule)

| Task | App | Schedule | Description |
| --- | --- | --- | --- |
| `process_pending_notifications` | notifications | Every 60 seconds | Process and deliver scheduled notifications |
| `send_reminder_notifications` | notifications | Every 15 minutes | Send goal reminder notifications |
| `generate_daily_motivation` | notifications | Daily 8:00 AM | AI-generated personalized motivational messages |
| `check_inactive_users` | notifications | Daily 9:00 AM | Detect 3+ day inactive users, send rescue notifications |
| `send_weekly_report` | notifications | Sunday 10:00 AM | Weekly progress reports with AI insights |
| `cleanup_old_notifications` | notifications | Monday 2:00 AM | Delete read notifications older than 30 days |
| `update_dream_progress` | dreams | Daily 3:00 AM | Recalculate dream progress, check milestones |
| `smart_archive_dreams` | dreams | Daily 4:00 AM | Pause dreams inactive 30+ days |
| `check_overdue_tasks` | dreams | Daily 10:00 AM | Detect overdue tasks, send reminders |
| `cleanup_abandoned_dreams` | dreams | Sunday 3:00 AM | Archive dreams inactive 90+ days |
| `generate_recurring_events` | calendar | Daily 1:00 AM | Create recurring event instances (2-week horizon) |
| `send_buddy_checkin_reminders` | buddies | Daily 11:00 AM | Remind buddy pairs with 3+ days no encouragement |
| `check_season_end` | leagues | Daily 12:05 AM | Handle season transitions and rewards |
| `send_league_change_notifications` | leagues | Sunday 11:00 PM | Send promotion/demotion notifications |
| `create_daily_rank_snapshots` | leagues | Daily 11:55 PM | Snapshot all user rankings for history |

### On-Demand Tasks

| Task | App | Triggered By | Description |
| --- | --- | --- | --- |
| `generate_two_minute_start` | dreams | Dream creation / user request | AI micro-action to start a dream |
| `auto_schedule_tasks` | dreams | User request | AI schedules unscheduled tasks |
| `detect_obstacles` | dreams | Dream analysis | AI obstacle detection |
| `suggest_task_adjustments` | dreams | Proactive AI coach | Suggest adjustments for low completion rate |
| `generate_vision_board` | dreams | User request | DALL-E vision board image |
| `send_streak_milestone_notification` | notifications | Gamification logic | Milestone notifications (7, 14, 30, 60, 100, 365 days) |
| `send_level_up_notification` | notifications | User levels up | Congratulations notification |
| `sync_google_calendar` | calendar | User request / periodic | Bidirectional Google Calendar sync |
| `send_payment_receipt_email` | subscriptions | Successful payment webhook | Email receipt with plan details |
| `send_email_change_verification` | users | Email change request | Verification email with 24h link |
| `export_user_data` | users | GDPR data export request | Export all user data as JSON, email link |
| `transcribe_voice_message` | conversations | Voice message received | Whisper transcription |
| `summarize_conversation` | conversations | Every 20th message | AI conversation summary for context optimization |

**Total: 15 periodic + 13 on-demand = 28 tasks**

---

## Django Signals

| Signal | Sender | Handler | File | Description |
| --- | --- | --- | --- | --- |
| `post_save` | User | `create_stripe_customer_on_user_creation` | `apps/subscriptions/signals.py` | Creates Stripe customer record for new users |
| `pre_save` | User | `track_xp_change` | `apps/leagues/signals.py` | Captures previous XP value before save |
| `post_save` | User | `update_league_standing_on_xp_change` | `apps/leagues/signals.py` | Updates league membership when XP changes |

**Signal registration**: In each app's `apps.py` → `ready()` method imports `signals.py`.

---

## Management Commands (Seed Data)

| Command | App | Description |
| --- | --- | --- |
| `seed_achievements` | users | 17 achievements across 5 categories (streaks, dreams, tasks, social, special) |
| `seed_dream_templates` | dreams | 8 dream templates (health, career, education, finance, creative, personal, social, travel) |
| `seed_conversation_templates` | conversations | 6 AI conversation types (planning, check-in, motivation, obstacle, review, general) |
| `seed_notification_templates` | notifications | 6 notification templates (motivation, streak, reminder, report, achievement, buddy) |
| `seed_leagues` | leagues | 7 league tiers (Bronze→Legend) + initial season |
| `seed_store` | store | 5 categories + 15+ cosmetic items with pricing/rarity |
| `seed_subscription_plans` | subscriptions | 3 plans (Free, Premium $19.99, Pro $29.99) |

**Run all seed commands**:

```bash
python manage.py seed_subscription_plans
python manage.py seed_achievements
python manage.py seed_dream_templates
python manage.py seed_conversation_templates
python manage.py seed_notification_templates
python manage.py seed_leagues
python manage.py seed_store
```

---

## Cross-App Flows

For detailed step-by-step traces of cross-app flows, see **[docs/CROSS_APP_FLOWS.md](CROSS_APP_FLOWS.md)**.

Key flows documented:
1. **Task Completion Chain** — dreams → users (XP, streak, achievements) → leagues → buddies → calendar → notifications
2. **Dream Creation with AI** — calibration → AI plan → goals/tasks → snapshot → notifications
3. **User Registration** — user creation → Stripe customer (signal) → gamification profile → settings → notification
4. **Notification Delivery Pipeline** — event → service → DB → preferences check → WebSocket / push / email
5. **Subscription Change** — Stripe checkout → webhook → subscription record → user sync → permission gates

---

## Per-App Documentation Index

Each app has a detailed README documenting its models, endpoints, serializers, services, and more:

| App | README | Key Topics |
| --- | --- | --- |
| Users | [apps/users/README.md](../apps/users/README.md) | User model, GamificationProfile, DailyActivity, Achievements, 2FA, GDPR |
| Dreams | [apps/dreams/README.md](../apps/dreams/README.md) | Dreams, Goals, Tasks, Obstacles, Templates, Tags, Calibration, Vision Board |
| Conversations | [apps/conversations/README.md](../apps/conversations/README.md) | AI Chat (AIChatConsumer), WebSocket, Templates, Voice, Export |
| Notifications | [apps/notifications/README.md](../apps/notifications/README.md) | Multi-channel delivery, Templates, WebSocket, Push, Preferences |
| Calendar | [apps/calendar/README.md](../apps/calendar/README.md) | Events, Time Blocks, Google Calendar, iCal, Conflict Detection |
| Subscriptions | [apps/subscriptions/README.md](../apps/subscriptions/README.md) | Stripe, Plans, Webhooks, Invoices, Coupons, Analytics |
| Store | [apps/store/README.md](../apps/store/README.md) | Items, Categories, XP/Stripe Purchase, Wishlists, Gifts, Refunds |
| Leagues | [apps/leagues/README.md](../apps/leagues/README.md) | Leagues, Seasons, Leaderboards, Rank Snapshots, Rewards |
| Circles | [apps/circles/README.md](../apps/circles/README.md) | Circles, Posts, Reactions, Challenges, Invitations, Group Chat (CircleChatConsumer), Agora Calls |
| Social | [apps/social/README.md](../apps/social/README.md) | Friends, Follows, Blocking, Reporting, Feed, Search, Dream Posts, Encouragements |
| Buddies | [apps/buddies/README.md](../apps/buddies/README.md) | Pairing, Encouragement, Streaks, Check-in Reminders, Real-Time Chat (BuddyChatConsumer), Calls |
| Core | [core/README.md](../core/README.md) | Auth, Permissions, Throttling, Sanitizers, Moderation, AI Validators, Audit, Consumer Mixins |

### Other Documentation

| Document | Path | Topics |
| --- | --- | --- |
| Top-Level README | [README.md](../README.md) | Features overview, tech stack, quick start, full API reference |
| Cross-App Flows | [docs/CROSS_APP_FLOWS.md](CROSS_APP_FLOWS.md) | 5 detailed cross-app flow traces |
| Technical Architecture | [docs/TECHNICAL_ARCHITECTURE.md](TECHNICAL_ARCHITECTURE.md) | Infrastructure, deployment, scaling |
| Feature Specifications | [docs/FEATURES_SPECIFICATIONS.md](FEATURES_SPECIFICATIONS.md) | Detailed feature specs |
| Testing Strategy | [docs/TESTING_STRATEGY.md](TESTING_STRATEGY.md) | Testing approach and coverage |
