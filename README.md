# DreamPlanner - AI-Powered Goal Achievement Platform

DreamPlanner is a comprehensive goal-tracking and achievement platform that combines AI-powered planning (GPT-4), real-time collaboration, gamification, and social features to help users turn their dreams into reality.

**Backend**: Django 5.0.1 with 12 apps, 170+ API endpoints, 28 Celery tasks, 4 WebSocket consumers

---

## Features

### AI-Powered Intelligence
- **GPT-4 Coaching**: Personalized AI coach that analyzes patterns and suggests adjustments
- **Smart Planning**: GPT-4 generates actionable plans from dreams, enriched by a 7-15 question calibration flow
- **2-Minute Start**: AI creates micro-tasks (under 2 minutes) to overcome procrastination
- **Obstacle Prediction**: AI predicts potential blockers and generates solutions
- **Vision Boards**: DALL-E 3 generates motivational images for goals
- **Rescue Mode**: Auto-detects user inactivity (3+ days) and re-engages with empathy
- **Whisper Voice Transcription**: Voice messages transcribed automatically via OpenAI Whisper
- **GPT-4V Image Analysis**: Image analysis capabilities for richer AI context
- **Conversation Summarization**: Automatic summaries generated after every 20 messages

### Dream Management
- **Dream Templates**: Browse and create dreams from pre-built templates with goals and tasks
- **Dream Sharing**: Share dreams with other users (view/edit permissions)
- **Dream Collaboration**: Add collaborators with viewer/editor roles
- **Dream Tags**: Organize dreams with custom tags
- **Dream Duplication**: Deep-copy dreams including all goals and tasks
- **PDF Export**: Export dreams with goals, tasks, and obstacles as formatted PDFs
- **Smart Archive**: Auto-pause inactive dreams at 30 days, archive at 90 days

### Task Management and Calendar
- **Smart Scheduling**: Intelligent task scheduling based on work hours and preferences
- **Calendar Views**: Day/Week/Month views with conflict detection
- **Auto-Scheduling**: AI schedules unscheduled tasks optimally based on user work schedule
- **Recurring Events**: Daily, weekly, monthly recurrence with automatic instance generation
- **Smart Suggestions**: AI-powered time slot recommendations
- **Google Calendar Sync**: Bidirectional sync (push and pull events)
- **iCal Feed**: Public iCal feed URL for subscribing in any calendar app
- **Conflict Detection**: Automatic detection of overlapping events
- **Overdue Detection**: Daily checks with gentle nudge notifications

### Real-Time Communication
- **AI Chat (WebSocket)**: Real-time streaming chat with GPT-4 via `AIChatConsumer`
- **Buddy Chat (WebSocket)**: Real-time peer-to-peer chat between accountability buddies via `BuddyChatConsumer` with FCM push
- **Circle Chat (WebSocket)**: Real-time group chat within circles via `CircleChatConsumer` with block filtering
- **Voice/Video Calls (Agora)**: Circle group calls powered by Agora.io RTC with token generation and participant tracking
- **Conversation Types**: Dream creation, planning, motivation, coaching, rescue, buddy chat
- **Conversation Templates**: Pre-built conversation starters for common scenarios
- **Conversation Export**: Export conversations as PDF or JSON
- **Typing Indicators**: Real-time typing status across all chat consumers

### Gamification System
- **XP and Leveling**: Earn XP for completing tasks and achieving milestones
- **8 Rank Tiers**: Dreamer, Aspirant, Planner, Achiever, Dream Warrior, Inspirer, Champion, Legend
- **Streak Tracking**: Daily streaks with automatic detection and milestone notifications (7, 14, 30, 60, 100, 365 days)
- **Badge System**: Unlock achievements for milestones
- **RPG Attributes**: Track Discipline, Learning, Wellbeing, Career, Creativity (0-100)
- **Time Multipliers**: Weekend Warrior (1.5x), Early Bird (1.3x), Night Owl (1.3x), Perfect Week (2.0x)
- **Influence Score**: Weighted composite of XP, completed dreams, active buddies, circle memberships, and streaks

### Subscriptions and Monetization
- **3 Tiers**: Free (3 dreams, no AI), Premium ($14.99/mo), Pro ($29.99/mo)
- **Stripe Integration**: Checkout sessions, webhooks, customer portal, invoices
- **Trial Periods**: Configurable free trial for premium tiers
- **Coupons**: Stripe coupon and promotion code support
- **Subscription Analytics**: Tracking of MRR, churn, and conversion metrics
- **Feature Gating**: 9 permission classes enforce tier limits across all endpoints
- **Payment Receipts**: Automatic email receipts on successful payment via Celery

### In-App Store
- **Cosmetic Items**: Avatar skins, badge frames, themes organized by categories
- **XP Purchasing**: Buy items using earned XP as alternative to real currency
- **Stripe Purchases**: Real-currency purchases via Stripe payment intents
- **Wishlists**: Save items for later
- **Gifting**: Send store items as gifts to other users, with claim flow
- **Refund Requests**: Request refunds on purchases
- **Featured Items**: Curated featured items section

### Leagues and Ranking
- **7 League Tiers**: Bronze, Silver, Gold, Platinum, Diamond, Master, Grandmaster
- **Seasonal Competitions**: 90-day seasons with automatic transitions and reward calculation
- **Leaderboards**: Global (top 100), league-specific, friends, nearby ranking
- **Dense Ranking**: Accurate rank calculation with tie handling
- **Daily Rank Snapshots**: Historical rank tracking for progress visualization
- **Automatic Promotion/Demotion**: Weekly league tier changes with notifications
- **Season Rewards**: Claim rewards at end of each season
- **Seed Command**: `seed_leagues` management command for initial setup

### Dream Circles
- **Circle Management**: Create, join, and manage circles with privacy settings (public/private)
- **Circle Chat**: Real-time group messaging via WebSocket with content moderation and block filtering
- **Circle Calls**: Voice/video group calls powered by Agora.io with RTC token generation
- **Invite Codes**: Join circles via shareable invite codes
- **Invitations**: View and manage pending circle invitations
- **Circle Posts**: Create, edit, delete posts within circles
- **Reactions**: React and unreact to circle posts
- **Challenges**: Create and join circle-wide challenges with progress tracking
- **Moderator Management**: Promote/demote/remove members (moderator and owner roles)
- **Filtered Discovery**: Browse circles by my/public/recommended filters

### Social Features
- **Friends**: Send, accept, reject friend requests; remove friends
- **Mutual Friends**: View mutual friends between users
- **Follows**: Follow and unfollow users
- **Follow Suggestions**: AI-powered follow recommendations
- **Blocking**: Block and unblock users
- **Reporting**: Report users for violations
- **User Search**: Search users by name or email
- **Activity Feed**: Friends activity feed with filtering
- **Social Counts**: Follower, following, and friend counts per user
- **Dream Posts**: Share dream progress publicly with optional images, GoFundMe links, and visibility controls
- **Post Feed**: Aggregated feed from followed users and public posts with block filtering
- **Post Interactions**: Like, threaded comments, and share/repost
- **Encouragements**: 5 typed encouragement reactions (you_got_this, keep_going, inspired, proud, fire)

### Dream Buddies
- **Buddy Matching**: AI-powered compatibility matching for accountability partners
- **Acceptance Flow**: Send, accept, and reject buddy pairing requests
- **Auto-Expiration**: Pending buddy requests automatically expire after 7 days
- **Real-Time Chat**: WebSocket-based buddy-to-buddy messaging via `BuddyChatConsumer` with FCM push notifications
- **Buddy Calls**: Initiate calls with broadcast to WebSocket group
- **Encouragement**: Send encouragement messages to your buddy
- **Check-In Reminders**: Automatic daily reminders when no encouragement sent in 3+ days
- **Streak Tracking**: Track buddy engagement streaks
- **Progress Comparison**: Side-by-side progress comparison with your buddy
- **Pairing History**: View past buddy pairings

### Smart Notifications
- **3-Channel Delivery**: WebSocket (real-time), Email, and Web Push (VAPID) with per-user preference toggles
- **12+ Notification Types**: Reminders, motivation, progress milestones, achievement unlocks, rescue, buddy check-in, overdue tasks, weekly report, dream completed, dream paused, dream archived, dream sharing, coaching suggestions
- **DND Support**: Respects Do Not Disturb hours with automatic rescheduling (including midnight-crossing windows)
- **Granular Preferences**: Per-type and per-channel notification toggle for each user
- **Personalized Messages**: AI-generated notification content based on user context
- **Notification Grouping**: Group similar notifications for cleaner inbox
- **Notification Analytics**: Track delivery, open, and engagement rates
- **Notification Templates**: Reusable templates for common notification patterns
- **Web Push Subscriptions**: Register/manage browser push subscriptions via VAPID

### Authentication and Security
- **django-allauth + dj-rest-auth**: JWT authentication (short-lived access tokens, httpOnly refresh cookies)
- **Social Auth**: Google Sign-In and Apple Sign-In via allauth social providers
- **Two-Factor Authentication (TOTP)**: Setup, verify, disable, status check, backup code regeneration. Login with 2FA uses challenge token flow — no JWT tokens issued until OTP is verified.
- **Account lockout**: 5 failed login attempts locks IP + email for 15 minutes via Redis
- **Rate limiting**: `AuthRateThrottle` at 5/min on login, register, password reset, and password reset confirm
- **Email Change Verification**: Secure email change with verification link (24-hour expiry)
- **Password Management**: Change password, forgot password flow

### GDPR Compliance
- **Account Deletion**: Soft-delete with data anonymization, automatic GDPR hard-delete after 30-day grace period
- **Data Export**: Export all user data (profile, dreams, goals, tasks, notifications) as JSON
- **Email Data Export**: Async data export via Celery with download link emailed to user

---

## Architecture

```
dreamplanner/
+-- apps/                        # 12 Django applications
|   +-- users/                   # User management, gamification, 2FA, GDPR
|   +-- dreams/                  # Dreams, Goals, Tasks, Obstacles, Templates, Tags, PDF export
|   +-- conversations/           # AI chat (AIChatConsumer WebSocket), templates, voice transcription
|   +-- notifications/           # Push notifications, templates, preferences, Celery tasks
|   +-- calendar/                # Events, recurring, Google Calendar sync, iCal feed
|   +-- subscriptions/           # Stripe plans, checkout, webhooks, invoices
|   +-- store/                   # Items, categories, purchases, wishlists, gifting, refunds
|   +-- leagues/                 # Leagues, seasons, leaderboards, rank snapshots
|   +-- circles/                 # Circles, posts, reactions, challenges, invitations, group chat, Agora calls
|   +-- social/                  # Friends, follows, blocking, reporting, activity feed, dream posts
|   +-- buddies/                 # Buddy pairing, encouragement, check-in reminders, chat, calls
+-- core/                        # Auth, permissions, AI validators, moderation, audit, middleware, consumer mixins
+-- integrations/                # OpenAI (GPT-4, DALL-E, Whisper), Google Calendar
+-- config/                      # Django settings, Celery, ASGI/WSGI
+-- docker/                      # Docker configs
|   +-- nginx.conf               # Internal nginx (security headers, rate limiting, proxy)
+-- scripts/                     # Utility scripts
|   +-- backup.sh                # Automated PostgreSQL backup (cron daily)
+-- docs/                        # Documentation
+-- .github/workflows/           # CI/CD Pipelines
```

---

## Tech Stack

| Component | Technology |
|-----------|-----------|
| **Framework** | Django 5.0.1 |
| **API** | Django REST Framework 3.14.0 |
| **API Docs** | drf-spectacular (OpenAPI/Swagger + ReDoc) |
| **WebSocket** | Django Channels 4.0.0 |
| **Background Jobs** | Celery 5.3.4 + django-celery-beat |
| **Database** | PostgreSQL 15 (prod) / SQLite (dev) |
| **Cache/Broker** | Redis 7 |
| **Authentication** | django-allauth + dj-rest-auth (JWT auth) |
| **Social Auth** | Google Sign-In, Apple Sign-In |
| **AI** | OpenAI GPT-4, DALL-E 3, Whisper, GPT-4V |
| **Real-Time Calls** | Agora.io RTC (voice/video) |
| **Push Notifications** | Firebase Cloud Messaging (FCM) |
| **Payments** | Stripe (subscriptions + one-time) |
| **PDF Generation** | ReportLab |
| **Server** | Gunicorn + Daphne |
| **Reverse Proxy** | Nginx |
| **Container** | Docker + Docker Compose |
| **Testing** | pytest + pytest-django |
| **Language** | Python 3.11 |

---

## Quick Start

### With Docker (Recommended)

```bash
# 1. Copy and fill .env
cp .env.example .env   # Then edit with real values
chmod 600 .env

# 2. Build and start all services (production settings)
docker compose up -d --build

# 3. Create admin user
docker compose exec web python manage.py createsuperuser

# 4. Seed data
docker compose exec web python manage.py seed_subscription_plans
docker compose exec web python manage.py seed_achievements
docker compose exec web python manage.py seed_dream_templates
docker compose exec web python manage.py seed_conversation_templates
docker compose exec web python manage.py seed_notification_templates
docker compose exec web python manage.py seed_leagues
docker compose exec web python manage.py seed_store

# Services available (behind nginx on 127.0.0.1:8085):
# API:       http://127.0.0.1:8085/api/
# Admin:     http://127.0.0.1:8085/admin/
# Swagger:   http://127.0.0.1:8085/api/docs/
# WebSocket: ws://127.0.0.1:8085/ws/
# Health:    http://127.0.0.1:8085/health/
```

### Without Docker (Local development — uses SQLite + in-memory cache)

```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Use development settings (DEBUG=True, SQLite, in-memory cache)
export DJANGO_SETTINGS_MODULE=config.settings.development
export FIELD_ENCRYPTION_KEY=$(python -c "import base64,os;print(base64.urlsafe_b64encode(os.urandom(32)).decode())")

pip install -r requirements/development.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver

# In separate terminals:
celery -A config worker -l info
celery -A config beat -l info
daphne -b 0.0.0.0 -p 9000 config.asgi:application
```

### Environment Variables

Create `.env` in the project root (must be `chmod 600`):

```env
# ── Django Core ─────────────────────────────────────────
DJANGO_SECRET_KEY=your-secret-key          # REQUIRED in production
DJANGO_SETTINGS_MODULE=config.settings.production
ALLOWED_HOSTS=dpapi.yourdomain.com,localhost,127.0.0.1
FRONTEND_URL=https://dp.yourdomain.com
CORS_ORIGIN=https://dp.yourdomain.com,https://localhost,capacitor://localhost
CSRF_TRUSTED_ORIGINS=https://dp.yourdomain.com,https://localhost,capacitor://localhost

# ── Database (PostgreSQL) ───────────────────────────────
DB_NAME=dreamplanner
DB_USER=dreamplanner
DB_PASSWORD=your-db-password               # REQUIRED in production
DB_HOST=localhost
DB_PORT=5432

# ── Redis ───────────────────────────────────────────────
REDIS_URL=redis://localhost:6379/0
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=your-redis-password

# ── Elasticsearch ───────────────────────────────────────
ELASTICSEARCH_URL=http://localhost:9200
ELASTIC_PASSWORD=your-elastic-password

# ── Field Encryption ────────────────────────────────────
FIELD_ENCRYPTION_KEY=...                   # Generate: python -c "import base64,os;print(base64.urlsafe_b64encode(os.urandom(32)).decode())"

# ── OpenAI ──────────────────────────────────────────────
OPENAI_API_KEY=sk-...
OPENAI_ORGANIZATION_ID=                    # optional

# ── Agora.io ────────────────────────────────────────────
AGORA_APP_ID=your-agora-app-id
AGORA_APP_CERTIFICATE=your-agora-app-certificate

# ── Web Push (VAPID) ───────────────────────────────────
VAPID_PUBLIC_KEY=...
VAPID_PRIVATE_KEY=...
VAPID_ADMIN_EMAIL=admin@yourdomain.com

# ── Firebase (FCM push) ────────────────────────────────
FIREBASE_CREDENTIALS_PATH=/app/firebase-service-account.json

# ── Stripe ──────────────────────────────────────────────
STRIPE_SECRET_KEY=sk_...
STRIPE_PUBLISHABLE_KEY=pk_...
STRIPE_WEBHOOK_SECRET=whsec_...

# ── Social Auth ─────────────────────────────────────────
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
APPLE_CLIENT_ID=...
APPLE_CLIENT_SECRET=...
APPLE_KEY_ID=...

# ── Email (SMTP) ───────────────────────────────────────
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_HOST_USER=...
EMAIL_HOST_PASSWORD=...
DEFAULT_FROM_EMAIL=noreply@yourdomain.com

# ── Monitoring (optional) ──────────────────────────────
# SENTRY_DSN=...
```

---

## API Documentation

### Base URL
- **Development**: `http://localhost:8000/api`
- **Production**: `https://api.dreamplanner.app/api`
- **Swagger UI**: `http://localhost:8000/api/docs/`
- **ReDoc**: `http://localhost:8000/api/redoc/`
- **OpenAPI Schema**: `http://localhost:8000/api/schema/`

### Authentication

JWT authentication via dj-rest-auth:
```
Authorization: Bearer <access_token>
```

Refresh tokens are set as httpOnly cookies on web, or stored via `@capacitor/preferences` on native.

WebSocket authentication via message body (sent after connection opens):
```json
{"type": "authenticate", "token": "<access_token>"}
```

### Authentication Endpoints
```
POST   /api/auth/login/                        # Login (email + password) — returns JWT or challenge token if 2FA enabled
POST   /api/auth/2fa-challenge/                # Verify 2FA code with challenge token — returns JWT
POST   /api/auth/logout/                       # Logout
POST   /api/auth/registration/                 # Register new account
POST   /api/auth/password/change/              # Change password
POST   /api/auth/password/reset/               # Request password reset (rate limited: 5/min)
POST   /api/auth/password/reset/confirm/       # Confirm password reset (rate limited: 5/min)
GET    /api/auth/user/                         # Get authenticated user
POST   /api/auth/google/                       # Google Sign-In
POST   /api/auth/apple/                        # Apple Sign-In
```

### Users
```
GET    /api/users/me/                          # Current user profile
PUT    /api/users/update_profile/              # Update profile
GET    /api/users/gamification/                # Gamification profile (XP, level, rank)
POST   /api/users/upload_avatar/               # Upload avatar image
GET    /api/users/stats/                       # User statistics
DELETE /api/users/delete-account/              # GDPR account deletion
GET    /api/users/export-data/                 # GDPR data export
POST   /api/users/change-email/               # Request email change
PUT    /api/users/notification-preferences/    # Update notification preferences
GET    /api/users/verify-email/<token>/        # Verify email change
```

### Two-Factor Authentication
```
POST   /api/users/2fa/setup/                   # Generate TOTP secret + QR code
POST   /api/users/2fa/verify/                  # Verify TOTP code to enable 2FA
POST   /api/users/2fa/disable/                 # Disable 2FA
GET    /api/users/2fa/status/                  # Check 2FA status
POST   /api/users/2fa/backup-codes/            # Regenerate backup codes
```

### Dreams, Goals, Tasks, Obstacles
```
GET    /api/dreams/dreams/                     # List dreams
POST   /api/dreams/dreams/                     # Create dream
GET    /api/dreams/dreams/{id}/                # Dream details
PUT    /api/dreams/dreams/{id}/                # Update dream
DELETE /api/dreams/dreams/{id}/                # Delete dream
POST   /api/dreams/dreams/{id}/analyze/        # AI analysis
POST   /api/dreams/dreams/{id}/start_calibration/   # Start calibration (7 questions)
POST   /api/dreams/dreams/{id}/answer_calibration/  # Answer calibration questions
POST   /api/dreams/dreams/{id}/skip_calibration/    # Skip calibration
POST   /api/dreams/dreams/{id}/generate_plan/       # Generate AI plan (uses calibration)
POST   /api/dreams/dreams/{id}/generate_two_minute_start/  # Generate micro-action
POST   /api/dreams/dreams/{id}/generate_vision/     # Generate DALL-E vision board
POST   /api/dreams/dreams/{id}/complete/            # Mark dream completed
POST   /api/dreams/dreams/{id}/duplicate/           # Deep-copy dream
POST   /api/dreams/dreams/{id}/share/               # Share dream with user
DELETE /api/dreams/dreams/{id}/unshare/{user_id}/   # Remove sharing
POST   /api/dreams/dreams/{id}/tags/                # Add tag to dream
DELETE /api/dreams/dreams/{id}/tags/{tag_name}/     # Remove tag from dream
POST   /api/dreams/dreams/{id}/collaborators/       # Add collaborator
GET    /api/dreams/dreams/{id}/collaborators/list/  # List collaborators
DELETE /api/dreams/dreams/{id}/collaborators/{user_id}/  # Remove collaborator
GET    /api/dreams/dreams/shared-with-me/           # Dreams shared with me
GET    /api/dreams/dreams/tags/                     # List all tags
GET    /api/dreams/dreams/{id}/export-pdf/          # Export dream as PDF

GET    /api/dreams/goals/                      # List goals
POST   /api/dreams/goals/                      # Create goal
GET    /api/dreams/goals/{id}/                 # Goal details
PUT    /api/dreams/goals/{id}/                 # Update goal
DELETE /api/dreams/goals/{id}/                 # Delete goal
POST   /api/dreams/goals/{id}/complete/        # Complete goal

GET    /api/dreams/tasks/                      # List tasks
POST   /api/dreams/tasks/                      # Create task
GET    /api/dreams/tasks/{id}/                 # Task details
PUT    /api/dreams/tasks/{id}/                 # Update task
DELETE /api/dreams/tasks/{id}/                 # Delete task
POST   /api/dreams/tasks/{id}/complete/        # Complete task (awards XP)
POST   /api/dreams/tasks/{id}/skip/            # Skip task

GET    /api/dreams/obstacles/                  # List obstacles
POST   /api/dreams/obstacles/                  # Create obstacle
GET    /api/dreams/obstacles/{id}/             # Obstacle details
PUT    /api/dreams/obstacles/{id}/             # Update obstacle
DELETE /api/dreams/obstacles/{id}/             # Delete obstacle
POST   /api/dreams/obstacles/{id}/resolve/     # Resolve obstacle
```

### Dream Templates
```
GET    /api/dreams/dreams/templates/           # List templates (filterable by category)
GET    /api/dreams/dreams/templates/{id}/      # Template details
POST   /api/dreams/dreams/templates/{id}/use/  # Create dream from template
GET    /api/dreams/dreams/templates/featured/  # Featured templates
```

### Conversations (AI Chat)
```
GET    /api/conversations/conversations/       # List conversations
POST   /api/conversations/conversations/       # Start conversation
GET    /api/conversations/conversations/{id}/  # Conversation detail
PUT    /api/conversations/conversations/{id}/  # Update conversation
DELETE /api/conversations/conversations/{id}/  # Delete conversation
POST   /api/conversations/conversations/{id}/send_message/  # Send message (get AI response)

GET    /api/conversations/messages/            # List messages
GET    /api/conversations/messages/{id}/       # Message detail

GET    /api/conversations/conversation-templates/      # List conversation templates
GET    /api/conversations/conversation-templates/{id}/ # Template detail
```

### Calendar
```
GET    /api/calendar/events/                   # List calendar events
POST   /api/calendar/events/                   # Create event
GET    /api/calendar/events/{id}/              # Event details
PUT    /api/calendar/events/{id}/              # Update event
DELETE /api/calendar/events/{id}/              # Delete event

GET    /api/calendar/timeblocks/               # List time blocks
POST   /api/calendar/timeblocks/               # Create time block
GET    /api/calendar/timeblocks/{id}/          # Time block details
PUT    /api/calendar/timeblocks/{id}/          # Update time block
DELETE /api/calendar/timeblocks/{id}/          # Delete time block

GET    /api/calendar/view/                     # Calendar view for date range (?start=&end=)
GET    /api/calendar/today/                    # Today's scheduled tasks
POST   /api/calendar/reschedule/               # Reschedule a task
GET    /api/calendar/suggest-time-slots/       # Find available time slots (?date=&duration_mins=)
PATCH  /api/calendar/events/{id}/reschedule/   # Reschedule event to new times

GET    /api/calendar/google/auth/              # Start Google Calendar OAuth
POST   /api/calendar/google/callback/          # Google Calendar OAuth callback
POST   /api/calendar/google/sync/              # Trigger bidirectional sync
POST   /api/calendar/google/disconnect/        # Disconnect Google Calendar
GET    /api/calendar/ical-feed/<token>/        # Public iCal feed
```

### Notifications
```
GET    /api/notifications/notifications/               # List notifications (filterable)
POST   /api/notifications/notifications/               # Create notification
GET    /api/notifications/notifications/{id}/           # Notification details
DELETE /api/notifications/notifications/{id}/           # Delete notification
POST   /api/notifications/notifications/{id}/mark_read/ # Mark as read
POST   /api/notifications/notifications/mark_all_read/ # Mark all read
GET    /api/notifications/notifications/unread_count/  # Unread count

GET    /api/notifications/templates/                   # List notification templates
GET    /api/notifications/templates/{id}/              # Template details

POST   /api/notifications/notifications/{id}/opened/   # Mark as opened (tracks engagement)
GET    /api/notifications/notifications/grouped/       # Notifications grouped by type

GET    /api/notifications/push-subscriptions/          # List push subscriptions
POST   /api/notifications/push-subscriptions/          # Register push subscription
DELETE /api/notifications/push-subscriptions/{id}/     # Remove push subscription
```

### Subscriptions
```
GET    /api/subscriptions/plans/                       # List subscription plans
GET    /api/subscriptions/plans/{id}/                  # Plan details
GET    /api/subscriptions/subscription/                # List subscriptions
GET    /api/subscriptions/subscription/current/        # Current subscription
POST   /api/subscriptions/subscription/checkout/       # Create Stripe checkout session
POST   /api/subscriptions/subscription/cancel/         # Cancel subscription
POST   /api/subscriptions/subscription/reactivate/     # Reactivate subscription
POST   /api/subscriptions/subscription/portal/         # Stripe customer portal
POST   /api/subscriptions/webhook/stripe/              # Stripe webhook handler
```

### Store
```
GET    /api/store/categories/                  # List store categories
GET    /api/store/categories/{id}/             # Category detail with items
GET    /api/store/items/                       # List store items (searchable, filterable)
GET    /api/store/items/{id}/                  # Item detail
GET    /api/store/items/featured/              # Featured items
GET    /api/store/inventory/                   # User inventory
GET    /api/store/inventory/{id}/              # Inventory item detail
POST   /api/store/inventory/{id}/equip/        # Equip/unequip item
GET    /api/store/inventory/history/           # Purchase history
GET    /api/store/wishlist/                    # User wishlist
POST   /api/store/wishlist/                    # Add to wishlist
DELETE /api/store/wishlist/{id}/               # Remove from wishlist
POST   /api/store/purchase/                    # Initiate Stripe purchase
POST   /api/store/purchase/confirm/            # Confirm Stripe purchase
POST   /api/store/purchase/xp/                 # Purchase with XP
POST   /api/store/gifts/send/                  # Send item as gift
POST   /api/store/gifts/{id}/claim/            # Claim received gift
GET    /api/store/gifts/                       # List gifts (sent/received)
POST   /api/store/refunds/                     # Request refund
```

### Leagues and Leaderboard
```
GET    /api/leagues/leagues/                   # List all leagues
GET    /api/leagues/leagues/{id}/              # League detail
GET    /api/leagues/seasons/                   # List all seasons
GET    /api/leagues/seasons/{id}/              # Season detail
GET    /api/leagues/seasons/current/           # Current active season
GET    /api/leagues/seasons/past/              # Past seasons
GET    /api/leagues/seasons/my-rewards/        # User season rewards
POST   /api/leagues/seasons/{id}/claim-reward/ # Claim season reward
GET    /api/leagues/leaderboard/global/        # Global top 100
GET    /api/leagues/leaderboard/league/        # League-specific board
GET    /api/leagues/leaderboard/friends/       # Friends leaderboard
GET    /api/leagues/leaderboard/me/            # Current user standing
GET    /api/leagues/leaderboard/nearby/        # Nearby ranked users
```

### Circles
```
GET    /api/circles/                           # List circles (filter: my/public/recommended)
POST   /api/circles/                           # Create circle
GET    /api/circles/{id}/                      # Circle detail
PUT    /api/circles/{id}/                      # Update circle
DELETE /api/circles/{id}/                      # Delete circle
POST   /api/circles/{id}/join/                 # Join circle
POST   /api/circles/{id}/leave/                # Leave circle
GET    /api/circles/{id}/feed/                 # Circle post feed
POST   /api/circles/{id}/posts/                # Create post
PUT    /api/circles/{id}/posts/{post_id}/edit/ # Edit post
DELETE /api/circles/{id}/posts/{post_id}/delete/   # Delete post
POST   /api/circles/{id}/posts/{post_id}/react/    # React to post
POST   /api/circles/{id}/posts/{post_id}/unreact/  # Remove reaction
GET    /api/circles/{id}/challenges/           # List circle challenges
POST   /api/circles/{id}/members/{id}/promote/ # Promote to moderator
POST   /api/circles/{id}/members/{id}/demote/  # Demote from moderator
POST   /api/circles/{id}/members/{id}/remove/  # Remove member
POST   /api/circles/join/{invite_code}/        # Join by invite code
GET    /api/circles/my-invitations/            # Pending invitations
GET    /api/circles/challenges/                # List all challenges
POST   /api/circles/challenges/                # Create challenge
GET    /api/circles/challenges/{id}/           # Challenge detail
POST   /api/circles/challenges/{id}/join/      # Join challenge
```

### Social
```
GET    /api/social/friends/                    # List friends
POST   /api/social/friends/request/            # Send friend request
GET    /api/social/friends/requests/pending/   # Pending friend requests (received)
GET    /api/social/friends/requests/sent/      # Sent friend requests
POST   /api/social/friends/accept/{id}/        # Accept friend request
POST   /api/social/friends/reject/{id}/        # Reject friend request
DELETE /api/social/friends/remove/{user_id}/   # Remove friend
GET    /api/social/friends/mutual/{user_id}/   # Mutual friends
POST   /api/social/follow/                     # Follow a user
DELETE /api/social/unfollow/{user_id}/         # Unfollow a user
POST   /api/social/block/                      # Block a user
DELETE /api/social/unblock/{user_id}/          # Unblock a user
GET    /api/social/blocked/                    # List blocked users
POST   /api/social/report/                     # Report a user
GET    /api/social/counts/{user_id}/           # Follower/following/friend counts
GET    /api/social/feed/friends                # Friends activity feed
GET    /api/social/users/search                # Search users
GET    /api/social/follow-suggestions/         # Follow suggestions
```

### Buddies
```
GET    /api/buddies/current/                   # Current buddy pairing
GET    /api/buddies/{id}/progress/             # Progress comparison
POST   /api/buddies/find-match/                # Find compatible buddy
POST   /api/buddies/pair/                      # Create pairing
POST   /api/buddies/{id}/accept/               # Accept pairing
POST   /api/buddies/{id}/reject/               # Reject pairing
POST   /api/buddies/{id}/encourage/            # Send encouragement
GET    /api/buddies/history/                   # Pairing history
DELETE /api/buddies/{id}/                      # End pairing
```

### Circle Chat & Calls
```
POST   /api/circles/{id}/chat/send/                # Send circle chat message
GET    /api/circles/{id}/chat/history/             # Circle chat history
POST   /api/circles/{id}/call/start/               # Start voice/video call (Agora)
POST   /api/circles/{id}/call/join/                # Join active call
POST   /api/circles/{id}/call/leave/               # Leave call
POST   /api/circles/{id}/call/end/                 # End call
GET    /api/circles/{id}/call/active/              # Get active call
```

### Dream Posts
```
GET    /api/social/posts/                          # List posts
POST   /api/social/posts/                          # Create dream post
GET    /api/social/posts/{id}/                     # Post detail
PUT    /api/social/posts/{id}/                     # Update post
DELETE /api/social/posts/{id}/                     # Delete post
GET    /api/social/posts/feed/                     # Social feed
POST   /api/social/posts/{id}/like/                # Toggle like
POST   /api/social/posts/{id}/comment/             # Add comment
GET    /api/social/posts/{id}/comments/            # List comments
POST   /api/social/posts/{id}/encourage/           # Send encouragement
POST   /api/social/posts/{id}/share/               # Share/repost
GET    /api/social/posts/user/{user_id}/           # User's posts
```

### WebSocket Routes
```
ws/ai-chat/{conversation_id}/                      # AIChatConsumer — AI chat (GPT-4 streaming)
ws/conversations/{conversation_id}/                # (deprecated alias for ai-chat)
ws/buddy-chat/{pairing_id}/                        # BuddyChatConsumer — buddy real-time chat + FCM
ws/circle-chat/{circle_id}/                        # CircleChatConsumer — circle group chat
ws/notifications/                                  # NotificationConsumer — real-time notifications
```

### Health Checks
```
GET    /health/                                # General health
GET    /health/liveness/                       # Liveness probe
GET    /health/readiness/                      # Readiness probe (DB check)
```

---

## Gamification System

### XP Rewards

| Action | XP | Multiplier Eligible |
|--------|---:|:-------------------:|
| Task completed | 10 | Yes |
| Daily goal met | 25 | Yes |
| Dream milestone 25% | 100 | Yes |
| Dream milestone 50% | 200 | Yes |
| Dream milestone 75% | 300 | Yes |
| Dream completed | 500 | Yes |
| Streak day | 5 x streak | No |
| Buddy help | 15 | Yes |
| Circle challenge | 50 | Yes |
| Public commitment | 250 | No |

### Time Multipliers
- **Weekend Warrior** (Sat/Sun): 1.5x
- **Early Bird** (before 8am): 1.3x
- **Night Owl** (after 10pm): 1.3x
- **Perfect Week** (7/7 days): 2.0x

### Influence Score Formula
```
Influence = (Total XP * 0.6)
          + (Completed Dreams * 500)
          + (Active Buddies * 200)
          + (Circle Memberships * 100)
          + (Current Streak * 10)
```

### Rank Tiers

| Rank | Name | Influence Required |
|------|------|-------------------:|
| 1 | Dreamer | 0 - 99 |
| 2 | Aspirant | 100 - 499 |
| 3 | Planner | 500 - 1,499 |
| 4 | Achiever | 1,500 - 3,499 |
| 5 | Dream Warrior | 3,500 - 7,499 |
| 6 | Inspirer | 7,500 - 14,999 |
| 7 | Champion | 15,000 - 29,999 |
| 8 | Legend | 30,000+ |

---

## Testing

```bash
# All tests
make test

# With coverage report
make test-cov

# Specific test types
make test-unit          # Unit tests only
make test-integration   # Integration tests
pytest -m asyncio       # Async tests (WebSocket)

# Coverage report generated in htmlcov/index.html
```

---

## Deployment

### Docker Deployment (Current — VPS)

Architecture: **External nginx (SSL) → Docker nginx (security) → Django/Daphne**

```bash
cd /root/dreamplanner

# 1. Create/update .env with production secrets (chmod 600)
# 2. Build and start all services
docker compose up -d --build

# 3. Run migrations (happens automatically via web entrypoint)
# 4. Collect static files
docker compose exec web python manage.py collectstatic --noinput

# 5. Seed data (first deploy only)
docker compose exec web python manage.py seed_subscription_plans
docker compose exec web python manage.py seed_achievements
docker compose exec web python manage.py seed_dream_templates
docker compose exec web python manage.py seed_leagues
docker compose exec web python manage.py seed_store
```

**Services in docker-compose.yml:**

| Service | Image | Port | Purpose |
| --- | --- | --- | --- |
| `db` | postgres:15-alpine | internal | PostgreSQL (512M limit) |
| `redis` | redis:7-alpine | internal | Cache + Celery broker (256M, auth required) |
| `elasticsearch` | ES 8.12.0 | internal | Full-text search (512M, auth required) |
| `web` | Dockerfile | 8000 (expose) | Django + Gunicorn |
| `celery` | Dockerfile | — | Background tasks |
| `celery-beat` | Dockerfile | — | Scheduled tasks |
| `daphne` | Dockerfile | 9000 (expose) | WebSocket (Channels) |
| `nginx` | nginx:1.27-alpine | 127.0.0.1:8085 | Internal reverse proxy (128M, read-only) |

### Backup & Recovery

```bash
# Manual backup
/root/dreamplanner/scripts/backup.sh

# Automated: cron runs daily at 3 AM, 7-day retention
# Backups stored in /root/dreamplanner/backups/
```

### Infrastructure (AWS — future)
- **ECS Fargate**: Django containers (HTTP + WebSocket + Celery worker + Celery beat)
- **RDS PostgreSQL**: Multi-AZ for high availability
- **ElastiCache Redis**: Cluster mode for cache + message broker
- **S3**: Vision boards, avatars, and media files
- **ALB**: Load balancer with health checks
- **CloudFront**: CDN for static assets
- **CloudWatch**: Logging and monitoring
- **Secrets Manager**: Environment secrets

---

## Project Stats

- **Django Apps**: 12 (users, dreams, conversations, notifications, calendar, subscriptions, store, leagues, circles, social, buddies, core)
- **API Endpoints**: 170+
- **WebSocket Consumers**: 4 (AIChatConsumer, BuddyChatConsumer, CircleChatConsumer, NotificationConsumer)
- **WebSocket Routes**: 5 (ai-chat, conversations (deprecated alias), buddy-chat, circle-chat, notifications)
- **Celery Beat Tasks**: 15 periodic tasks
- **On-Demand Celery Tasks**: 13 async tasks
- **Management Commands**: 7 (seed_subscription_plans, seed_achievements, seed_dream_templates, seed_conversation_templates, seed_notification_templates, seed_leagues, seed_store)
- **Models**: 50+
- **Test Coverage**: 99%+ target

---

## Security

### Authentication & Authorization
- **JWT auth** — django-allauth + dj-rest-auth with short-lived access tokens and httpOnly refresh cookies
- **2FA enforcement at login** — Challenge token flow: credentials validated → signed challenge token issued (5min TTL) → OTP verified → JWT tokens issued. No tokens leak before 2FA verification.
- **Account lockout** — 5 failed login attempts locks IP + email for 15 minutes via Redis
- **Rate limiting** — `AuthRateThrottle` at 5/min on login, register, password reset, and password reset confirm
- **Social auth** — Google Sign-In and Apple Sign-In via allauth providers
- **Two-Factor (TOTP)** — Setup, verify, disable, status, backup code regeneration. Secrets stored in `EncryptedCharField` (not plaintext). Backup codes hashed with PBKDF2 (100k iterations).
- **9 permission classes** — Enforce subscription tier limits across all endpoints

### Infrastructure Security
- **UFW firewall** — Only ports 22 (SSH), 80 (HTTP/certbot), 443 (HTTPS) open
- **Docker port binding** — All services bind to `127.0.0.1` (not internet-accessible)
- **Separate-server ready** — CORS, CSRF, and cookies configured for frontend/backend on different servers
- **Fail2ban** — SSH (3 retries/2h ban), nginx-http-auth (5 retries), nginx-botsearch (3 retries/24h ban)
- **Daily backups** — Automated PostgreSQL backups with 7-day retention (`scripts/backup.sh`, cron at 3 AM)

### Nginx Security (Docker internal)
All security headers are set by the Docker-internal nginx (`docker/nginx.conf`). External nginx only handles SSL termination.

| Feature | Configuration |
| --- | --- |
| `server_tokens` | off (version hidden) |
| Rate limiting | API: 10r/s, WebSocket: 5r/s, Auth: 3r/s, Admin: 2r/s |
| Security headers | HSTS, X-XSS-Protection (transport-level; Django handles the rest) |
| Static/media | Own security headers (bypass Django middleware) |
| Exploit paths | `.env`, `.git`, `.htaccess`, `wp-admin`, `xmlrpc` blocked |
| Dotfiles | Denied with no logging |

### Application Security
- **Production mode** — `DEBUG=False`, `SECURE_PROXY_SSL_HEADER` set, `SECURE_SSL_REDIRECT=False` (external nginx handles TLS)
- **CORS** — Whitelist only (`CORS_ALLOW_ALL_ORIGINS=False`), origins from env var, credentials allowed
- **CSRF** — `CSRF_TRUSTED_ORIGINS` configured for cross-origin frontend
- **Cookies** — `SESSION_COOKIE_SECURE=True`, `CSRF_COOKIE_SECURE=True`, `JWT_AUTH_SECURE=True`, `SameSite=Lax`
- **HSTS** — 1 year, `includeSubDomains`, `preload`
- **SQL injection** — Protected via Django ORM
- **XSS** — DOMPurify with restricted `ALLOWED_TAGS` on frontend, `nh3` sanitizer on backend. SecurityHeadersMiddleware sets CSP (`frame-ancestors 'none'`), `X-Frame-Options: DENY`, Referrer-Policy, Permissions-Policy, COOP, CORP
- **SSRF prevention** — `validate_url_no_ssrf()` resolves DNS once and returns IP for connection pinning (prevents TOCTOU/DNS rebinding)
- **Upload validation** — Type + size + magic byte checks on all file uploads, UUID filenames. Django-level ceilings: `DATA_UPLOAD_MAX_MEMORY_SIZE=110MB`, `FILE_UPLOAD_MAX_MEMORY_SIZE=10MB`
- **DB SSL** — `sslmode=require` default in production
- **WebSocket auth** — Token in message body (not URL), JWT signature + expiry validated
- **Error redaction** — 5xx responses return generic message in production, full error logged server-side
- **DRF throttling** — Anon: 20/min, User: 100/min, AI chat: 10/min, AI plan: 5/min, Export: 1/day, Auth: 5/min
- **Input validation** — DRF Serializers + custom validation (avatar magic bytes, notification schema whitelist, channel name regex, message length limits)

### Secrets Management
- **`.env` file** — `chmod 600`, not committed to git. Contains all secrets (Django key, DB password, API keys)
- **Docker Compose** — References `${VAR}` from `.env`, no hardcoded secrets
- **Field encryption** — `django-encrypted-model-fields` for PII (TOTP secrets, sensitive user data)
- **Redis auth** — `requirepass` with dedicated password
- **Elasticsearch auth** — `xpack.security.enabled=true` with dedicated password

### Docker Hardening
- **Read-only filesystem** — Nginx container runs with `read_only: true`
- **Resource limits** — PostgreSQL: 512M/1CPU, Redis: 256M/0.5CPU, ES: 512M/1CPU, Nginx: 128M/0.5CPU
- **Health checks** — All services have health checks (pg_isready, redis-cli ping, curl, wget)
- **Port isolation** — Internal services use `expose` (not `ports`); only nginx is port-mapped to localhost

---

## Documentation

### Architecture & Navigation

- **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)**: System architecture, feature location guide, subscription tiers, infrastructure catalog — **start here to find anything**
- **[docs/CROSS_APP_FLOWS.md](docs/CROSS_APP_FLOWS.md)**: Step-by-step traces of cross-app flows (task completion, dream creation, registration, notifications, subscriptions)
- **[core/README.md](core/README.md)**: Core module docs (auth, permissions, AI validators, moderation, throttling, middleware, audit)

### Per-App Documentation

Each app has a detailed README: [users](apps/users/README.md) | [dreams](apps/dreams/README.md) | [conversations](apps/conversations/README.md) | [notifications](apps/notifications/README.md) | [calendar](apps/calendar/README.md) | [subscriptions](apps/subscriptions/README.md) | [store](apps/store/README.md) | [leagues](apps/leagues/README.md) | [circles](apps/circles/README.md) | [social](apps/social/README.md) | [buddies](apps/buddies/README.md)

### Other Docs

- **[docs/TECHNICAL_ARCHITECTURE.md](docs/TECHNICAL_ARCHITECTURE.md)**: Technical architecture
- **[docs/FEATURES_SPECIFICATIONS.md](docs/FEATURES_SPECIFICATIONS.md)**: Feature specifications
- **[docs/IMPROVEMENTS_STRATEGY.md](docs/IMPROVEMENTS_STRATEGY.md)**: Improvement roadmap

---

## Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Write/update tests
4. Run tests: `make test-cov`
5. Format code: `make format`
6. Commit changes
7. Push and create PR

---

## License

MIT License - see [LICENSE](LICENSE) file for details

---

**Built with Django, GPT-4, DALL-E, Whisper, and Stripe**
