# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/).

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
- Input validation with Zod/Django validators
- CORS protection
- Security headers with Helmet

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
