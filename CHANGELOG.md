# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [1.4.0] - 2026-03-03

### Security
- **2FA enforcement at login** — New challenge token flow: credentials validated → signed challenge token issued (5min TTL) → OTP verified → JWT tokens issued. No tokens leak before 2FA verification. New `TwoFactorChallengeView` endpoint at `/api/auth/2fa-challenge/`
- **Account lockout** — 5 failed login attempts locks IP + email for 15 minutes via Redis
- **Rate limiting on auth** — `AuthRateThrottle` (5/min) wired to login, register, password reset, and password reset confirm views
- **SSRF DNS rebinding fix** — `validate_url_no_ssrf()` now returns `(url, resolved_ip)` for connection pinning, preventing TOCTOU/DNS rebinding attacks
- **Backup code hashing** — Fixed inconsistency: replaced `hashlib.sha256` with PBKDF2 (100k iterations) matching `two_factor.py`
- **CSP hardening** — Added `frame-ancestors 'none'` on both frontend meta tag and backend `SecurityHeadersMiddleware`
- **Clickjacking** — `X-Frame-Options: DENY` in production settings + middleware
- **DB SSL** — Changed default `sslmode` from `prefer` to `require` in production settings
- **Cookie security** — `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`, `JWT_AUTH_SECURE` all True in production
- **Upload limits** — `DATA_UPLOAD_MAX_MEMORY_SIZE=110MB`, `FILE_UPLOAD_MAX_MEMORY_SIZE=10MB` at Django level
- **Protected routes** — `/change-password` wrapped in `ProtectedRoute` on frontend
- **npm supply chain** — Added `overrides` for `serialize-javascript>=7.0.3`, 0 npm audit vulnerabilities
- **gunicorn CVE-2024-1135** — Upgraded to `>=22.0.0,<24.0`
- **WebSocket auth** — Token now sent in message body (not URL query string), JWT signature + expiry validated
- **Error redaction** — 5xx responses return generic message in production, full error logged server-side

### Added
- `PRODUCTION_CHECKLIST.md` — Comprehensive pre-GA checklist covering security, infrastructure, and environment variables
- `TwoFactorChallengeView` — Unauthenticated endpoint for 2FA verification using signed challenge tokens
- Frontend 2FA challenge screen with OTP input on `LoginScreen.jsx`
- `AUTH.TFA_CHALLENGE` endpoint constant in frontend `endpoints.js`

### Changed
- `NativeAwareLoginView` now intercepts 2FA-enabled users and returns challenge token instead of JWT
- Backend `validate_url_no_ssrf()` returns `(url, resolved_ip)` tuple instead of just URL
- SSRF callers in `conversations/tasks.py` and `conversations/views.py` updated for DNS pinning
- Frontend `AuthContext.jsx` login flow passes `challengeToken` for 2FA
- HSTS set to 1 year with `includeSubDomains` and `preload`

## [1.3.0] - 2026-02-27

### Added
- **3 WebSocket consumers**: `AIChatConsumer` (conversations), `BuddyChatConsumer` (buddies), `CircleChatConsumer` (circles) — each with dedicated routing module
- **Shared consumer mixins** in `core/consumers.py`: `RateLimitMixin` (sliding window), `AuthenticatedConsumerMixin` (post-connect token auth + heartbeat), `BlockingMixin` (bidirectional block check), `ModerationMixin` (content moderation)
- **CircleMessage** model for persistent circle group chat with encrypted content
- **Agora.io circle calls**: `CircleCall` and `CircleCallParticipant` models, RTC token generation, voice/video call lifecycle endpoints (`start`, `join`, `leave`, `end`, `active`)
- **FCM push notifications** for buddy chat messages (offline partner) and circle call start (all members)
- **Buddy call broadcast**: `call_started` WebSocket event broadcast to `buddy_chat` group
- **DreamPost** model: public dream sharing with images, GoFundMe links, visibility controls (public/followers/private), denormalized counters
- **DreamPostLike**: toggle like with denormalized count
- **DreamPostComment**: threaded comments via self-referential parent FK
- **DreamEncouragement**: 5 typed encouragement reactions (you_got_this, keep_going, inspired, proud, fire)
- **Dream post feed algorithm**: followed users + public posts, exclude blocked, annotate has_liked/has_encouraged
- **Dream post endpoints**: CRUD, feed, like, comment, comments, encourage, share, user_posts
- **Social notification types**: `dream_post_like`, `dream_post_comment`, `dream_post_encouragement`, `circle_call`, `buddy_message`
- **Circle chat REST endpoints**: `POST /chat/send/`, `GET /chat/history/`
- `CircleMessageSerializer`, `CircleCallSerializer`, `DreamPostSerializer`, `DreamPostCreateSerializer`, `DreamPostCommentSerializer`, `DreamEncouragementSerializer`

### Changed
- **ChatConsumer → AIChatConsumer**: renamed for clarity; AI chat URL changed from `ws/conversations/` to `ws/ai-chat/` (old URL preserved as deprecated alias)
- **BuddyChatConsumer moved** from `apps/conversations/consumers.py` to `apps/buddies/consumers.py` with its own routing module
- **ASGI routing** now combines 4 separate routing modules (`ai_chat_ws`, `buddy_chat_ws`, `circle_chat_ws`, `notification_ws`) in `config/asgi.py`
- Buddy chat URL parameter changed from `conversation_id` to `pairing_id`
- Updated project stats: 4 WebSocket consumers, 5 WebSocket routes, 170+ API endpoints, 50+ models

## [1.2.0] - 2026-02-27

### Added
- Two-Factor Authentication (TOTP) with backup codes via `/api/users/2fa/*` endpoints
- Onboarding completion tracking (`POST /api/users/complete-onboarding/`)
- GDPR hard-delete: automatic permanent deletion of soft-deleted accounts after 30-day grace period
- Buddy request auto-expiration after 7 days for pending requests
- Dream sharing notifications sent to recipients
- Achievement unlock notifications
- Progress recalculation signal on task deletion
- `IsOwnerOrSharedWith` permission class for shared dreams
- Subscription downgrade feature revocation
- Circle ownership auto-transfer on creator departure
- Notification email fallback when FCM fails
- Search app test suite (17 tests)
- New features test suite (40 tests covering 2FA, GDPR, buddies, idempotency, sharing, signals)

### Fixed
- Double-completion bug: tasks/goals/dreams now return 400 if already completed (idempotent)
- Dream progress corruption when tasks are deleted (post_delete signal)
- Account deletion now cancels Stripe subscription and cleans up buddy pairings/circle memberships
- 25 bare `except: pass` blocks replaced with proper logging
- N+1 query fix in dream serializers (use prefetch cache)
- Standardized error response format in custom exception handler

### Changed
- Added caching (5 min) to leaderboard, store items, and dream templates endpoints
- All documentation translated from French to English
- Unified pricing to USD ($14.99 Premium / $29.99 Pro)
- Unified coverage target to 84%
- Updated OpenAI SDK syntax in docs
- Replaced all "DreamBuddy" references with "BuddyPairing"

---

## [1.1.0] - 2026-02-22

### Added
- **3-Channel Notification Delivery**: WebSocket (real-time), Email, and Web Push (VAPID) notification channels with per-user preference toggles
- **NotificationConsumer**: WebSocket consumer for real-time notification delivery, mark-read, and unread count updates
- **NotificationDeliveryService**: Unified service dispatching notifications across all 3 channels with DND support
- **WebPushSubscription model**: Browser push subscription management with VAPID key support
- **NotificationBatch model**: Batch notification tracking with success rate analytics
- **Notification engagement tracking**: `opened_at` field and `/opened/` action for delivery analytics
- **Notification grouping**: `/grouped/` endpoint to view notifications by type
- **AI Validators**: Pydantic validation schemas for all AI-generated responses (`core/ai_validators.py`)
- **XSS Sanitization**: `core/sanitizers.py` with bleach-based HTML sanitization for all user-facing content

### Tests
- **Circles test suite**: 165 tests covering models, views, serializers, admin, invitation flows, challenge actions
- **Social test suite**: 159 tests covering friendship lifecycle, follows, blocking, reporting, activity feed, user search, follow suggestions
- **Buddies test suite**: 72 tests covering pairing, encouragement, streaks, progress comparison, history
- **Notification test suite expanded**: 45+ new tests for WebSocket consumer, delivery service, Web Push, batch serializer
- **AI validators test suite**: 80+ tests covering all Pydantic schemas, validation functions, coherence checker
- **Coverage target raised**: 80% → 84%

### Fixed
- Fixed broken `conftest.py` imports (`DreamBuddy` model removed, replaced with `BuddyPairing`)
- Fixed `core/tests.py` import names (`liveness` → `liveness_check`, `readiness` → `readiness_check`)
- Fixed notification test assertions using French strings instead of English
- Removed root `__init__.py` that caused Django app discovery errors

---

## [1.0.0] - 2025-01-28

### Added

#### Django Backend
- **Users App** - Profile management, preferences
- **Dreams App** - Full CRUD for dreams, goals, tasks, obstacles
- **Conversations App** - Real-time chat with WebSocket and GPT-4
- **Notifications App** - Push notifications and templates
- **Calendar App** - Calendar views and smart scheduling
- **Gamification** - XP system, levels, badges, streaks
- **Dream Buddy** - Accountability partnership system

#### Integrations
- OpenAI GPT-4 for plan generation and coaching
- DALL-E 3 for vision board generation
- Redis for cache and Celery broker
- PostgreSQL as the primary database

#### Documentation
- Complete README with setup instructions
- Technical architecture documentation
- Feature specifications
- Contributing guide
- Deployment guide

#### Security
- Multi-tier rate limiting
- Input validation with Django validators and DRF serializers
- CORS protection
- Security headers via SecurityHeadersMiddleware

#### Tests
- Unit tests for all models
- Integration tests for API endpoints
- WebSocket tests for real-time chat
- Pytest configuration with reusable fixtures
- Code coverage > 80%

### Infrastructure
- Docker and Docker Compose for local development
- Production configuration for Railway/AWS
- CI/CD with GitHub Actions
- Monitoring with Sentry

## [0.1.0] - 2024-12-01

### Added
- Initial project structure
- Initial Django project structure
- Initial database schema

---

## Types of Changes

- `Added` for new features
- `Changed` for changes to existing features
- `Deprecated` for features that will be removed soon
- `Removed` for removed features
- `Fixed` for bug fixes
- `Security` for fixed vulnerabilities
