# DreamPlanner Backend - Django API

Complete Django REST API backend for the DreamPlanner mobile application. Features 12 Django apps, 150+ API endpoints, 2 WebSocket consumers, 50+ Celery tasks, social auth, two-factor authentication, Stripe subscriptions, Google Calendar sync, and full AI integration (GPT-4, DALL-E 3, Whisper).

## Tech Stack

| Component | Technology |
| --- | --- |
| **Framework** | Django 5.0.1 + Django REST Framework 3.14.0 |
| **API Documentation** | drf-spectacular (OpenAPI 3.0, Swagger UI, ReDoc) |
| **Database** | PostgreSQL 15 (production) / SQLite (development) |
| **Caching** | Redis 7 via django-redis |
| **Real-time** | Django Channels 4.0.0 (WebSocket) |
| **Background Jobs** | Celery 5.3.4 + django-celery-beat + Redis broker |
| **Authentication** | django-allauth 65.3.0 + dj-rest-auth 7.0.0 (Token auth) |
| **Social Auth** | Google Sign-In + Apple Sign-In (allauth social providers) |
| **Two-Factor Auth** | TOTP-based 2FA with backup codes |
| **AI** | OpenAI GPT-4, DALL-E 3, Whisper, GPT-4V |
| **Push Notifications** | Firebase Cloud Messaging (firebase-admin) |
| **Payments** | Stripe (subscriptions + one-time purchases) |
| **PDF Generation** | ReportLab |
| **Testing** | pytest + pytest-django + pytest-cov |
| **Deployment** | Docker + Docker Compose + Gunicorn + Daphne + Nginx |
| **Language** | Python 3.11 |

## Project Structure

```
backend/
+-- config/                      # Django configuration
|   +-- settings/
|   |   +-- base.py             # Base settings (all env vars defined here)
|   |   +-- development.py      # Local dev (SQLite, DEBUG=True)
|   |   +-- production.py       # Production (PostgreSQL, AWS)
|   |   +-- testing.py          # Test environment
|   +-- urls.py                 # Root URL routing
|   +-- asgi.py                 # ASGI config (HTTP + WebSocket)
|   +-- wsgi.py                 # WSGI config (HTTP only)
|   +-- celery.py               # Celery app + beat schedule (15 periodic tasks)
|
+-- apps/                        # 11 Django applications
|   +-- users/                  # User management, gamification, 2FA, GDPR, email change
|   +-- dreams/                 # Dreams, Goals, Tasks, Obstacles, Templates, Tags, Sharing, Collaboration, PDF export
|   +-- conversations/          # AI chat, buddy chat (WebSocket), templates, voice transcription, summarization
|   +-- notifications/          # Push notifications, templates, preferences, DND, grouping
|   +-- calendar/               # Events, time blocks, recurring events, Google Calendar sync, iCal feed
|   +-- subscriptions/          # Stripe plans, checkout, webhooks, invoices, customer portal
|   +-- store/                  # Categories, items, inventory, purchases (Stripe + XP), wishlists, gifting, refunds
|   +-- leagues/                # Leagues, seasons, leaderboards, rank snapshots, promotion/demotion
|   +-- circles/                # Circles, posts, reactions, challenges, invitations, moderator management
|   +-- social/                 # Friends, follows, blocking, reporting, activity feed, search, suggestions
|   +-- buddies/                # Buddy pairing, acceptance flow, encouragement, check-in reminders
|
+-- core/                        # Core utilities (12th app)
|   +-- authentication.py       # BearerTokenAuthentication, CsrfExemptAPIMiddleware
|   +-- social_auth.py          # GoogleLoginView, AppleLoginView
|   +-- websocket_auth.py       # TokenWebSocketMiddleware
|   +-- permissions.py          # DRF permissions (IsOwner, CanCreateDream, 9 subscription gates)
|   +-- exceptions.py           # Custom exception handler
|   +-- pagination.py           # Pagination classes
|   +-- urls.py                 # Health check endpoints
|   +-- views.py                # Health check views
|
+-- integrations/                # External service clients
|   +-- openai_service.py       # GPT-4 chat, planning, calibration, motivation, DALL-E, Whisper
|   +-- fcm_service.py          # Firebase Cloud Messaging (push only)
|   +-- google_calendar.py      # Google Calendar push/pull sync
|
+-- requirements/                # Python dependencies
|   +-- base.txt
|   +-- development.txt
|   +-- production.txt
|   +-- testing.txt
|
+-- docker/                      # Docker configuration
|   +-- nginx.conf              # Nginx reverse proxy config
|
+-- Dockerfile                   # Production Docker image
+-- docker-compose.yml           # Local development
+-- docker-compose.prod.yml      # Production compose
+-- Makefile                     # Convenience commands
+-- pytest.ini                   # Test configuration
+-- manage.py                    # Django management
```

## Quick Start

### Prerequisites

- Python 3.11+ (for local development)
- Docker and Docker Compose (for containerized development)
- OpenAI API key
- Firebase project credentials (for push notifications)
- Stripe account (for subscriptions and store purchases)
- Google OAuth credentials (for social auth and calendar sync)
- Apple Developer credentials (for Apple Sign-In)

### Environment Setup

Create a `.env` file in `backend/`:

```env
# === Django ===
DJANGO_SECRET_KEY=your-secret-key-here
DJANGO_SETTINGS_MODULE=config.settings.development
ALLOWED_HOSTS=localhost,127.0.0.1
DEBUG=True
FRONTEND_URL=http://localhost:8100
DEFAULT_FROM_EMAIL=noreply@dreamplanner.app

# === Database (production only - dev uses SQLite) ===
DB_NAME=dreamplanner
DB_USER=dreamplanner
DB_PASSWORD=password
DB_HOST=localhost
DB_PORT=5432

# === Redis ===
REDIS_URL=redis://localhost:6379/0
REDIS_HOST=localhost
REDIS_PORT=6379

# === OpenAI ===
OPENAI_API_KEY=sk-...your-openai-api-key
OPENAI_ORGANIZATION_ID=org-...                 # optional

# === Social Authentication ===
GOOGLE_CLIENT_ID=your-google-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-google-client-secret
APPLE_CLIENT_ID=com.yourcompany.dreamplanner
APPLE_CLIENT_SECRET=your-apple-client-secret
APPLE_KEY_ID=your-apple-key-id

# === Stripe ===
STRIPE_SECRET_KEY=sk_test_...
STRIPE_PUBLISHABLE_KEY=pk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...
STRIPE_PREMIUM_MONTHLY_PRICE_ID=price_...
STRIPE_PREMIUM_YEARLY_PRICE_ID=price_...
STRIPE_PRO_MONTHLY_PRICE_ID=price_...
STRIPE_PRO_YEARLY_PRICE_ID=price_...

# === CORS ===
CORS_ORIGIN=http://localhost:3000,http://localhost:8081

# === AWS (production only) ===
AWS_ACCESS_KEY_ID=your-aws-key
AWS_SECRET_ACCESS_KEY=your-aws-secret
AWS_STORAGE_BUCKET_NAME=dreamplanner-media

# === Monitoring (production only) ===
SENTRY_DSN=your-sentry-dsn
```

### Start with Docker (Recommended)

```bash
make build          # Build images
make up             # Start all services (API, DB, Redis, Celery, Daphne)
make migrate        # Run migrations
make createsuperuser  # Create admin user

# Seed initial data
python manage.py seed_leagues   # Create league tiers + first season
python manage.py seed_store     # Create store categories + items

# View logs
make logs
```

Services available:

| Service | URL |
| --- | --- |
| API | http://localhost:8000 |
| Admin | http://localhost:8000/admin |
| Swagger UI | http://localhost:8000/api/docs/ |
| ReDoc | http://localhost:8000/api/redoc/ |
| OpenAPI Schema | http://localhost:8000/api/schema/ |
| WebSocket | ws://localhost:9000 |
| Flower (Celery) | http://localhost:5555 |

### Local Development (Without Docker)

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

# Seed data
python manage.py seed_leagues
python manage.py seed_store

# Start development server
python manage.py runserver

# In separate terminals:
celery -A config worker -l info           # Celery worker
celery -A config beat -l info             # Celery beat scheduler
daphne -b 0.0.0.0 -p 9000 config.asgi:application  # WebSocket server
```

## Management Commands

| Command | Description |
| --- | --- |
| `python manage.py seed_leagues` | Creates the 7 league tiers (Bronze through Grandmaster) and an initial 90-day season |
| `python manage.py seed_store` | Creates store categories and sample cosmetic items (avatar skins, badge frames, themes) |
| `python manage.py createsuperuser` | Creates a Django admin superuser |
| `python manage.py migrate` | Applies all database migrations |

## API Documentation

### Base URL

- **Development**: `http://localhost:8000/api`
- **Production**: `https://api.dreamplanner.app/api`

### Interactive Documentation

- **Swagger UI**: `http://localhost:8000/api/docs/` -- interactive API explorer
- **ReDoc**: `http://localhost:8000/api/redoc/` -- readable API reference
- **OpenAPI Schema**: `http://localhost:8000/api/schema/` -- raw JSON schema

### Authentication

All API requests (except auth and health endpoints) require Token authentication:

```
Authorization: Token <auth_token>
```

The Bearer variant is also supported via `BearerTokenAuthentication`:

```
Authorization: Bearer <auth_token>
```

WebSocket authentication uses a query parameter:

```
ws://localhost:9000/ws/conversations/{id}/?token=<auth_token>
```

### Rate Limiting

| Scope | Limit |
| --- | --- |
| Anonymous | 30 requests/minute |
| Authenticated | 120 requests/minute |
| AI Chat | 20 requests/minute |
| AI Plan Generation | 10 requests/minute |
| Subscription Actions | 10 requests/minute |
| Store Purchases | 10 requests/minute |

---

## Complete API Endpoint Reference

### Authentication (dj-rest-auth)

```
POST   /api/auth/login/                        # Email + password login (returns Token)
POST   /api/auth/logout/                       # Logout (invalidates token)
POST   /api/auth/registration/                 # Register new account
POST   /api/auth/password/change/              # Change password (authenticated)
POST   /api/auth/password/reset/               # Request password reset email
POST   /api/auth/password/reset/confirm/       # Confirm password reset with token
GET    /api/auth/user/                         # Get authenticated user details
PUT    /api/auth/user/                         # Update authenticated user details
```

### Social Authentication

```
POST   /api/auth/google/                       # Google Sign-In (exchange OAuth token)
POST   /api/auth/apple/                        # Apple Sign-In (exchange OAuth token)
```

### Users (`/api/users/`)

```
GET    /api/users/me/                          # Current user profile
PUT    /api/users/update_profile/              # Update profile (PUT or PATCH)
POST   /api/users/register_fcm_token/          # Register FCM device token
GET    /api/users/gamification/                # Gamification profile (XP, level, rank, attributes)
POST   /api/users/upload_avatar/               # Upload avatar image (multipart, max 5MB)
GET    /api/users/stats/                       # User statistics (dreams, tasks, streaks)
DELETE /api/users/delete-account/              # GDPR: soft-delete account (requires password)
GET    /api/users/export-data/                 # GDPR: export all user data as JSON
POST   /api/users/change-email/               # Request email change (sends verification)
PUT    /api/users/notification-preferences/    # Update per-type notification preferences
GET    /api/users/verify-email/<token>/        # Verify email change token (from email link)
```

### Two-Factor Authentication (`/api/users/2fa/`)

```
POST   /api/users/2fa/setup/                   # Generate TOTP secret + provisioning URI (QR code)
POST   /api/users/2fa/verify/                  # Verify TOTP code to enable 2FA
POST   /api/users/2fa/disable/                 # Disable 2FA (requires current TOTP code)
GET    /api/users/2fa/status/                  # Check whether 2FA is enabled
POST   /api/users/2fa/backup-codes/            # Regenerate backup codes
```

### Dreams (`/api/dreams/`)

```
GET    /api/dreams/dreams/                     # List dreams (filterable: status, category; searchable)
POST   /api/dreams/dreams/                     # Create dream
GET    /api/dreams/dreams/{id}/                # Dream detail (with goals, tasks, obstacles)
PUT    /api/dreams/dreams/{id}/                # Update dream
PATCH  /api/dreams/dreams/{id}/                # Partial update dream
DELETE /api/dreams/dreams/{id}/                # Delete dream

# AI Features
POST   /api/dreams/dreams/{id}/analyze/                   # GPT-4 dream analysis
POST   /api/dreams/dreams/{id}/start_calibration/         # Start calibration (generates 7 questions)
POST   /api/dreams/dreams/{id}/answer_calibration/        # Answer calibration questions (up to 15 total)
POST   /api/dreams/dreams/{id}/skip_calibration/          # Skip calibration step
POST   /api/dreams/dreams/{id}/generate_plan/             # Generate AI plan (uses calibration if available)
POST   /api/dreams/dreams/{id}/generate_two_minute_start/ # Generate 2-minute micro-action
POST   /api/dreams/dreams/{id}/generate_vision/           # Generate DALL-E vision board image
POST   /api/dreams/dreams/{id}/complete/                  # Mark dream as completed

# Sharing and Collaboration
POST   /api/dreams/dreams/{id}/share/                         # Share dream with a user
DELETE /api/dreams/dreams/{id}/unshare/{user_id}/             # Remove sharing
POST   /api/dreams/dreams/{id}/collaborators/                 # Add collaborator (viewer/editor)
GET    /api/dreams/dreams/{id}/collaborators/list/            # List collaborators
DELETE /api/dreams/dreams/{id}/collaborators/{user_id}/       # Remove collaborator

# Duplication, Tags, Export
POST   /api/dreams/dreams/{id}/duplicate/                     # Deep-copy dream with goals and tasks
POST   /api/dreams/dreams/{id}/tags/                          # Add tag to dream
DELETE /api/dreams/dreams/{id}/tags/{tag_name}/               # Remove tag from dream
GET    /api/dreams/dreams/{id}/export-pdf/                    # Download dream as PDF

# Shared and Tags
GET    /api/dreams/dreams/shared-with-me/                     # Dreams shared with current user
GET    /api/dreams/dreams/tags/                               # List all available tags
```

### Dream Templates (`/api/dreams/dreams/templates/`)

```
GET    /api/dreams/dreams/templates/                   # List active templates (filterable by category)
GET    /api/dreams/dreams/templates/{id}/              # Template detail
POST   /api/dreams/dreams/templates/{id}/use/          # Create dream from template
GET    /api/dreams/dreams/templates/featured/          # Featured templates
```

### Goals (`/api/dreams/goals/`)

```
GET    /api/dreams/goals/                      # List goals (filterable: status; query: ?dream=<id>)
POST   /api/dreams/goals/                      # Create goal
GET    /api/dreams/goals/{id}/                 # Goal detail
PUT    /api/dreams/goals/{id}/                 # Update goal
PATCH  /api/dreams/goals/{id}/                 # Partial update goal
DELETE /api/dreams/goals/{id}/                 # Delete goal
POST   /api/dreams/goals/{id}/complete/        # Mark goal as completed
```

### Tasks (`/api/dreams/tasks/`)

```
GET    /api/dreams/tasks/                      # List tasks (filterable: status; query: ?goal=<id>)
POST   /api/dreams/tasks/                      # Create task
GET    /api/dreams/tasks/{id}/                 # Task detail
PUT    /api/dreams/tasks/{id}/                 # Update task
PATCH  /api/dreams/tasks/{id}/                 # Partial update task
DELETE /api/dreams/tasks/{id}/                 # Delete task
POST   /api/dreams/tasks/{id}/complete/        # Complete task (awards XP + streak update)
POST   /api/dreams/tasks/{id}/skip/            # Skip task
```

### Obstacles (`/api/dreams/obstacles/`)

```
GET    /api/dreams/obstacles/                  # List obstacles (query: ?dream=<id>)
POST   /api/dreams/obstacles/                  # Create obstacle
GET    /api/dreams/obstacles/{id}/             # Obstacle detail
PUT    /api/dreams/obstacles/{id}/             # Update obstacle
PATCH  /api/dreams/obstacles/{id}/             # Partial update obstacle
DELETE /api/dreams/obstacles/{id}/             # Delete obstacle
POST   /api/dreams/obstacles/{id}/resolve/     # Mark obstacle as resolved
```

### Conversations (`/api/conversations/`)

```
GET    /api/conversations/conversations/                   # List conversations (filterable: type, is_active)
POST   /api/conversations/conversations/                   # Start new conversation
GET    /api/conversations/conversations/{id}/              # Conversation detail with messages
PUT    /api/conversations/conversations/{id}/              # Update conversation
DELETE /api/conversations/conversations/{id}/              # Delete conversation
POST   /api/conversations/conversations/{id}/send_message/ # Send message and get AI response

GET    /api/conversations/messages/                        # List messages
GET    /api/conversations/messages/{id}/                   # Message detail

GET    /api/conversations/conversation-templates/          # List conversation templates
GET    /api/conversations/conversation-templates/{id}/     # Template detail
```

### Calendar (`/api/calendar/`)

```
# Calendar Events
GET    /api/calendar/events/                   # List calendar events
POST   /api/calendar/events/                   # Create event
GET    /api/calendar/events/{id}/              # Event detail
PUT    /api/calendar/events/{id}/              # Update event
DELETE /api/calendar/events/{id}/              # Delete event

# Time Blocks
GET    /api/calendar/timeblocks/               # List time blocks
POST   /api/calendar/timeblocks/               # Create time block
GET    /api/calendar/timeblocks/{id}/          # Time block detail
PUT    /api/calendar/timeblocks/{id}/          # Update time block
DELETE /api/calendar/timeblocks/{id}/          # Delete time block

# Calendar Views
GET    /api/calendar/today/                    # Today's tasks and events
GET    /api/calendar/week/                     # Weekly view
GET    /api/calendar/month/                    # Monthly view
GET    /api/calendar/overdue/                  # Overdue tasks
POST   /api/calendar/reschedule/               # Reschedule multiple tasks
POST   /api/calendar/auto-schedule/            # AI auto-scheduling

# Google Calendar Integration
POST   /api/calendar/google/auth/              # Start Google Calendar OAuth flow
GET    /api/calendar/google/callback/          # Google Calendar OAuth callback
POST   /api/calendar/google/sync/              # Trigger bidirectional sync
POST   /api/calendar/google/disconnect/        # Disconnect Google Calendar

# iCal Feed
GET    /api/calendar/ical-feed/<feed_token>/   # Public iCal feed URL (subscribe in any app)
```

### Notifications (`/api/notifications/`)

```
GET    /api/notifications/notifications/                   # List notifications (filterable: type, status)
POST   /api/notifications/notifications/                   # Create notification
GET    /api/notifications/notifications/{id}/              # Notification detail
PUT    /api/notifications/notifications/{id}/              # Update notification
DELETE /api/notifications/notifications/{id}/              # Delete notification
POST   /api/notifications/notifications/{id}/mark_read/   # Mark as read
POST   /api/notifications/notifications/mark_all_read/    # Mark all as read
GET    /api/notifications/notifications/unread_count/     # Get unread count
GET    /api/notifications/notifications/grouped/          # Grouped notifications
GET    /api/notifications/notifications/analytics/        # Notification analytics

GET    /api/notifications/templates/                       # List notification templates
GET    /api/notifications/templates/{id}/                  # Template detail
```

### Subscriptions (`/api/subscriptions/`)

```
GET    /api/subscriptions/plans/                           # List subscription plans
GET    /api/subscriptions/plans/{id}/                      # Plan detail

GET    /api/subscriptions/subscription/                    # List subscriptions
GET    /api/subscriptions/subscription/{id}/               # Subscription detail
GET    /api/subscriptions/subscription/current/            # Current active subscription
POST   /api/subscriptions/subscription/checkout/           # Create Stripe checkout session
POST   /api/subscriptions/subscription/cancel/             # Cancel subscription
POST   /api/subscriptions/subscription/reactivate/         # Reactivate canceled subscription
POST   /api/subscriptions/subscription/portal/             # Open Stripe customer portal

POST   /api/subscriptions/webhook/stripe/                  # Stripe webhook endpoint
```

### Store (`/api/store/`)

```
# Catalog
GET    /api/store/categories/                  # List store categories
GET    /api/store/categories/{id}/             # Category detail with items
GET    /api/store/items/                       # List items (searchable, filterable, orderable)
GET    /api/store/items/{id}/                  # Item detail
GET    /api/store/items/featured/              # Featured items

# Inventory
GET    /api/store/inventory/                   # User's inventory
GET    /api/store/inventory/{id}/              # Inventory item detail
POST   /api/store/inventory/{id}/equip/        # Equip or unequip an item
GET    /api/store/inventory/history/           # Purchase history

# Wishlist
GET    /api/store/wishlist/                    # User's wishlist
POST   /api/store/wishlist/                    # Add item to wishlist
DELETE /api/store/wishlist/{id}/               # Remove from wishlist

# Purchases
POST   /api/store/purchase/                    # Initiate Stripe payment intent
POST   /api/store/purchase/confirm/            # Confirm Stripe payment
POST   /api/store/purchase/xp/                 # Purchase item with XP

# Gifting
POST   /api/store/gifts/send/                  # Send an item as a gift
POST   /api/store/gifts/{id}/claim/            # Claim a received gift
GET    /api/store/gifts/                       # List gifts (sent and received)

# Refunds
POST   /api/store/refunds/                     # Request a refund
```

### Leagues and Leaderboard (`/api/leagues/`)

```
GET    /api/leagues/leagues/                   # List all 7 league tiers
GET    /api/leagues/leagues/{id}/              # League detail

GET    /api/leagues/seasons/                   # List all seasons
GET    /api/leagues/seasons/{id}/              # Season detail
GET    /api/leagues/seasons/current/           # Current active season
GET    /api/leagues/seasons/past/              # Past completed seasons
GET    /api/leagues/seasons/my-rewards/        # User's earned season rewards
POST   /api/leagues/seasons/{id}/claim-reward/ # Claim a season reward

GET    /api/leagues/leaderboard/global/        # Global leaderboard (top 100)
GET    /api/leagues/leaderboard/league/        # League-specific leaderboard
GET    /api/leagues/leaderboard/friends/       # Friends leaderboard
GET    /api/leagues/leaderboard/me/            # Current user's standing and rank
GET    /api/leagues/leaderboard/nearby/        # Users ranked near the current user
```

### Circles (`/api/circles/`)

```
GET    /api/circles/                                       # List circles (filter: my/public/recommended)
POST   /api/circles/                                       # Create circle
GET    /api/circles/{id}/                                  # Circle detail
PUT    /api/circles/{id}/                                  # Update circle
DELETE /api/circles/{id}/                                  # Delete circle
POST   /api/circles/{id}/join/                             # Join circle
POST   /api/circles/{id}/leave/                            # Leave circle
GET    /api/circles/{id}/feed/                             # Circle post feed
POST   /api/circles/{id}/posts/                            # Create post in circle
PUT    /api/circles/{id}/posts/{post_id}/edit/             # Edit a post
DELETE /api/circles/{id}/posts/{post_id}/delete/           # Delete a post
POST   /api/circles/{id}/posts/{post_id}/react/            # React to a post
POST   /api/circles/{id}/posts/{post_id}/unreact/          # Remove reaction
GET    /api/circles/{id}/challenges/                       # List circle challenges
POST   /api/circles/{id}/members/{member_id}/promote/      # Promote member to moderator
POST   /api/circles/{id}/members/{member_id}/demote/       # Demote moderator
POST   /api/circles/{id}/members/{member_id}/remove/       # Remove member from circle

POST   /api/circles/join/{invite_code}/                    # Join circle by invite code
GET    /api/circles/my-invitations/                        # View pending invitations

GET    /api/circles/challenges/                            # List all challenges
POST   /api/circles/challenges/                            # Create challenge
GET    /api/circles/challenges/{id}/                       # Challenge detail
POST   /api/circles/challenges/{id}/join/                  # Join a challenge
```

### Social (`/api/social/`)

```
# Friends
GET    /api/social/friends/                    # List friends
POST   /api/social/friends/request/            # Send friend request
GET    /api/social/friends/requests/pending/   # Pending received requests
GET    /api/social/friends/requests/sent/      # Sent requests
POST   /api/social/friends/accept/{id}/        # Accept friend request
POST   /api/social/friends/reject/{id}/        # Reject friend request
DELETE /api/social/friends/remove/{user_id}/   # Remove friend
GET    /api/social/friends/mutual/{user_id}/   # Mutual friends with another user

# Follows
POST   /api/social/follow/                     # Follow a user
DELETE /api/social/unfollow/{user_id}/         # Unfollow a user
GET    /api/social/follow-suggestions/         # AI-powered follow suggestions

# Blocking and Reporting
POST   /api/social/block/                      # Block a user
DELETE /api/social/unblock/{user_id}/          # Unblock a user
GET    /api/social/blocked/                    # List blocked users
POST   /api/social/report/                     # Report a user

# Activity and Search
GET    /api/social/counts/{user_id}/           # Follower/following/friend counts
GET    /api/social/feed/friends                # Friends activity feed (filterable)
GET    /api/social/users/search                # Search users by name/email
```

### Buddies (`/api/buddies/`)

```
GET    /api/buddies/current/                   # Current active buddy pairing
GET    /api/buddies/{id}/progress/             # Progress comparison with buddy
POST   /api/buddies/find-match/                # Find a compatible buddy (AI-powered)
POST   /api/buddies/pair/                      # Create a buddy pairing request
POST   /api/buddies/{id}/accept/               # Accept a pending pairing
POST   /api/buddies/{id}/reject/               # Reject a pending pairing
POST   /api/buddies/{id}/encourage/            # Send encouragement to buddy
GET    /api/buddies/history/                   # View past pairings
DELETE /api/buddies/{id}/                      # End a buddy pairing
```

### Health Checks (`/health/`)

```
GET    /health/                                # General health check
GET    /health/liveness/                       # Liveness probe (for Kubernetes/ECS)
GET    /health/readiness/                      # Readiness probe (checks DB connectivity)
```

---

## WebSocket Endpoints

Two WebSocket consumers are available via Django Channels:

### AI Chat Consumer

```
ws://localhost:9000/ws/conversations/{conversation_id}/?token=<auth_token>
```

**Send message:**
```json
{"type": "message", "message": "Hello AI!"}
```

**Receive streaming response:**
```json
{"type": "stream_start"}
{"type": "stream_chunk", "chunk": "Hello"}
{"type": "stream_chunk", "chunk": " there!"}
{"type": "stream_end"}
{"type": "message", "message": {"id": "...", "role": "assistant", "content": "Hello there!", "created_at": "..."}}
```

**Typing indicator:**
```json
{"type": "typing", "is_typing": true}
```

### Buddy Chat Consumer

```
ws://localhost:9000/ws/buddy-chat/{conversation_id}/?token=<auth_token>
```

Peer-to-peer messaging between buddy pairs. Same message protocol as AI chat but without AI streaming responses. Messages include `sender_id` and `sender_name` fields.

---

## Celery Beat Schedule (15 Periodic Tasks)

| Task | Schedule | Queue | Description |
| --- | --- | --- | --- |
| `process_pending_notifications` | Every 60 seconds | notifications | Send pending notifications via FCM |
| `send_reminder_notifications` | Every 15 minutes | notifications | Send goal reminder notifications |
| `generate_daily_motivation` | Daily at 8:00 AM | notifications | AI-generated motivational messages |
| `check_inactive_users` | Daily at 9:00 AM | notifications | Rescue mode for 3+ day inactive users |
| `check_overdue_tasks` | Daily at 10:00 AM | dreams | Notify users about overdue tasks |
| `send_weekly_report` | Sunday at 10:00 AM | notifications | AI-generated weekly progress report |
| `update_dream_progress` | Daily at 3:00 AM | dreams | Recalculate dream progress percentages |
| `smart_archive_dreams` | Daily at 4:00 AM | dreams | Pause dreams inactive for 30+ days |
| `cleanup_abandoned_dreams` | Sunday at 3:00 AM | dreams | Archive dreams inactive for 90+ days |
| `cleanup_old_notifications` | Monday at 2:00 AM | notifications | Delete read notifications older than 30 days |
| `generate_recurring_events` | Daily at 1:00 AM | dreams | Generate recurring event instances (2-week horizon) |
| `send_buddy_checkin_reminders` | Daily at 11:00 AM | social | Remind buddies with no encouragement in 3+ days |
| `check_season_end` | Daily at 12:05 AM | social | Check if active season has ended and transition |
| `create_daily_rank_snapshots` | Daily at 11:55 PM | social | Snapshot user ranks for historical tracking |
| `weekly_league_promotions` | Sunday at 11:00 PM | social | Run promotion/demotion cycle with notifications |

### On-Demand Celery Tasks (Not Scheduled)

These tasks are triggered by API actions:

| Task | Queue | Triggered By |
| --- | --- | --- |
| `generate_two_minute_start` | dreams | Dream creation or user request |
| `auto_schedule_tasks` | dreams | User requests auto-scheduling |
| `detect_obstacles` | dreams | Dream analysis |
| `generate_vision_board` | dreams | User requests vision board |
| `suggest_task_adjustments` | dreams | Proactive AI Coach |
| `transcribe_voice_message` | integrations | Voice message received |
| `summarize_conversation` | integrations | Every 20th message in a conversation |
| `sync_google_calendar` | dreams | User triggers Google Calendar sync |
| `send_payment_receipt_email` | notifications | Successful Stripe payment |
| `send_email_change_verification` | notifications | User requests email change |
| `export_user_data` | notifications | User requests GDPR data export |
| `send_streak_milestone_notification` | notifications | User reaches streak milestone (7, 14, 30, 60, 100, 365 days) |
| `send_level_up_notification` | notifications | User levels up |

### Task Queue Routing

| Queue | Apps |
| --- | --- |
| `notifications` | notifications, subscriptions, users |
| `dreams` | dreams, calendar |
| `social` | social, buddies, leagues, circles |
| `integrations` | conversations, openai |

---

## Configuration

### Django Settings

Settings are split across four files in `config/settings/`:

| File | Usage |
| --- | --- |
| `base.py` | Common settings shared across all environments |
| `development.py` | Local development (SQLite, DEBUG=True) |
| `production.py` | Production (PostgreSQL, AWS S3, Sentry) |
| `testing.py` | Test environment |

Activate specific settings:
```bash
export DJANGO_SETTINGS_MODULE=config.settings.production
```

### Subscription Tiers

| Tier | Monthly | Yearly | Features |
| --- | --- | --- | --- |
| **Free** | $0 | $0 | 3 dreams, no AI, no buddies, no circles, no leagues, ads |
| **Premium** | $9.99 | $99.99 | Unlimited dreams, AI access, buddies, circles |
| **Pro** | $19.99 | $199.99 | Everything in Premium + leagues, vision boards, priority support |

---

## Testing

```bash
# All tests
make test

# With coverage
make test-cov

# Unit tests only
make test-unit

# Integration tests only
make test-integration

# Async tests (WebSocket)
pytest -m asyncio

# Run a specific test
pytest apps/users/tests.py::TestUserModel::test_create_user -v
```

Coverage reports are generated in `htmlcov/index.html`. Target: 80%+ coverage.

## Code Quality

```bash
make lint           # Run flake8
make format         # Run black + isort
make install-hooks  # Install pre-commit hooks
make pre-commit     # Run all pre-commit checks
```

## Docker Commands

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
make reset-db       # Reset database (WARNING: deletes all data)
make backup-db      # Backup database
make restore-db     # Restore from backup
```

## Deployment (AWS ECS)

```bash
# Build and push Docker image
docker build -t dreamplanner-api:latest .
docker tag dreamplanner-api:latest ${ECR_REGISTRY}/dreamplanner-api:latest
docker push ${ECR_REGISTRY}/dreamplanner-api:latest

# Deploy to ECS
aws ecs update-service \
  --cluster dreamplanner-prod \
  --service dreamplanner-api \
  --force-new-deployment

# Run migrations in ECS
aws ecs run-task \
  --cluster dreamplanner-prod \
  --task-definition dreamplanner-migrate \
  --launch-type FARGATE
```

### Production Infrastructure

| Service | Purpose |
| --- | --- |
| ECS Fargate | Django HTTP + Daphne WebSocket + Celery worker + Celery beat |
| RDS PostgreSQL | Multi-AZ database |
| ElastiCache Redis | Cache + Celery broker + Channels layer |
| S3 | Media files (vision boards, avatars, exports) |
| ALB | Load balancer with health checks |
| CloudFront | CDN for static assets |
| CloudWatch | Logging, metrics, and alerts |
| Secrets Manager | Environment variable management |
| Sentry | Error tracking and performance monitoring |

## Security

- django-allauth + DRF Token authentication (Token and Bearer)
- Social auth (Google, Apple) via allauth social providers
- Two-Factor Authentication (TOTP) with backup codes
- HTTPS enforced in production
- CORS configured with explicit origin whitelist
- SQL injection protection via Django ORM
- XSS protection via Django middleware
- CSRF protection via DRF (with CsrfExemptAPIMiddleware for API routes)
- Rate limiting at Nginx and DRF levels
- Non-root Docker user
- Secrets stored in environment variables (never committed)
- Security headers via Nginx (HSTS, X-Frame-Options, CSP)

## Troubleshooting

**Database connection error:**
```bash
docker-compose ps           # Check if DB is running
docker-compose up -d db     # Start DB container
```

**Celery not processing tasks:**
```bash
make logs-celery            # Check worker logs
docker-compose restart celery
```

**WebSocket connection failed:**
```bash
docker-compose logs -f daphne   # Check Daphne logs
docker-compose ps redis         # Ensure Redis is running
```

**Tests failing:**
```bash
export DJANGO_SETTINGS_MODULE=config.settings.testing
pytest apps/users/tests.py -v --tb=short
```

---

**Built for DreamPlanner**
