# DreamPlanner - AI-Powered Goal Achievement Platform

DreamPlanner is a comprehensive goal-tracking and achievement platform that combines AI-powered planning (GPT-4), real-time collaboration, gamification, and social features to help users turn their dreams into reality.

**Backend**: Django 5.0.1 with 12 apps, 150+ API endpoints, 50+ Celery tasks, 3 WebSocket consumers

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
- **AI Chat (WebSocket)**: Real-time streaming chat with GPT-4 via WebSocket
- **Buddy Chat (WebSocket)**: Real-time peer-to-peer chat between accountability buddies
- **Conversation Types**: Dream creation, planning, motivation, coaching, rescue, buddy chat
- **Conversation Templates**: Pre-built conversation starters for common scenarios
- **Conversation Export**: Export conversations as PDF or JSON
- **Typing Indicators**: Real-time typing status for both AI and buddy chats

### Gamification System
- **XP and Leveling**: Earn XP for completing tasks and achieving milestones
- **8 Rank Tiers**: Dreamer, Aspirant, Planner, Achiever, Dream Warrior, Inspirer, Champion, Legend
- **Streak Tracking**: Daily streaks with automatic detection and milestone notifications (7, 14, 30, 60, 100, 365 days)
- **Badge System**: Unlock achievements for milestones
- **RPG Attributes**: Track Discipline, Learning, Wellbeing, Career, Creativity (0-100)
- **Time Multipliers**: Weekend Warrior (1.5x), Early Bird (1.3x), Night Owl (1.3x), Perfect Week (2.0x)
- **Influence Score**: Weighted composite of XP, completed dreams, active buddies, circle memberships, and streaks

### Subscriptions and Monetization
- **3 Tiers**: Free (3 dreams, no AI), Premium ($9.99/mo or $99.99/yr), Pro ($19.99/mo or $199.99/yr)
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

### Dream Buddies
- **Buddy Matching**: AI-powered compatibility matching for accountability partners
- **Acceptance Flow**: Send, accept, and reject buddy pairing requests
- **Real-Time Chat**: WebSocket-based buddy-to-buddy messaging
- **Encouragement**: Send encouragement messages to your buddy
- **Check-In Reminders**: Automatic daily reminders when no encouragement sent in 3+ days
- **Streak Tracking**: Track buddy engagement streaks
- **Progress Comparison**: Side-by-side progress comparison with your buddy
- **Pairing History**: View past buddy pairings

### Smart Notifications
- **3-Channel Delivery**: WebSocket (real-time), Email, and Web Push (VAPID) with per-user preference toggles
- **12+ Notification Types**: Reminders, motivation, progress milestones, achievements, rescue, buddy check-in, overdue tasks, weekly report, dream completed, dream paused, dream archived, coaching suggestions
- **DND Support**: Respects Do Not Disturb hours with automatic rescheduling (including midnight-crossing windows)
- **Granular Preferences**: Per-type and per-channel notification toggle for each user
- **Personalized Messages**: AI-generated notification content based on user context
- **Notification Grouping**: Group similar notifications for cleaner inbox
- **Notification Analytics**: Track delivery, open, and engagement rates
- **Notification Templates**: Reusable templates for common notification patterns
- **Web Push Subscriptions**: Register/manage browser push subscriptions via VAPID

### Authentication and Security
- **django-allauth + dj-rest-auth**: Token-based authentication (Token and Bearer variants)
- **Social Auth**: Google Sign-In and Apple Sign-In via allauth social providers
- **Two-Factor Authentication (TOTP)**: Setup, verify, disable, status check, backup code regeneration
- **Email Change Verification**: Secure email change with verification link (24-hour expiry)
- **Password Management**: Change password, forgot password flow

### GDPR Compliance
- **Account Deletion**: Soft-delete with data anonymization, permanent deletion after 30 days
- **Data Export**: Export all user data (profile, dreams, goals, tasks, notifications) as JSON
- **Email Data Export**: Async data export via Celery with download link emailed to user

---

## Architecture

```
dreamplanner/
+-- apps/                        # 12 Django applications
|   +-- users/                   # User management, gamification, 2FA, GDPR
|   +-- dreams/                  # Dreams, Goals, Tasks, Obstacles, Templates, Tags, PDF export
|   +-- conversations/           # AI chat, buddy chat (WebSocket), templates, voice transcription
|   +-- notifications/           # Push notifications, templates, preferences, Celery tasks
|   +-- calendar/                # Events, recurring, Google Calendar sync, iCal feed
|   +-- subscriptions/           # Stripe plans, checkout, webhooks, invoices
|   +-- store/                   # Items, categories, purchases, wishlists, gifting, refunds
|   +-- leagues/                 # Leagues, seasons, leaderboards, rank snapshots
|   +-- circles/                 # Circles, posts, reactions, challenges, invitations
|   +-- social/                  # Friends, follows, blocking, reporting, activity feed
|   +-- buddies/                 # Buddy pairing, encouragement, check-in reminders
+-- core/                        # Auth, permissions, pagination, health checks
+-- integrations/                # OpenAI (GPT-4, DALL-E, Whisper), Google Calendar
+-- config/                      # Django settings, Celery, ASGI/WSGI
+-- docker/                      # Docker + Nginx configs
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
| **Authentication** | django-allauth + dj-rest-auth (Token auth) |
| **Social Auth** | Google Sign-In, Apple Sign-In |
| **AI** | OpenAI GPT-4, DALL-E 3, Whisper, GPT-4V |
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
# Build images
make build

# Start all services
make up

# Run migrations
make migrate

# Create admin user
make createsuperuser

# Seed data
python manage.py seed_leagues   # Create league tiers and initial season
python manage.py seed_store     # Create store categories and items

# Services available:
# API:       http://localhost:8000
# Admin:     http://localhost:8000/admin
# Swagger:   http://localhost:8000/api/docs/
# ReDoc:     http://localhost:8000/api/redoc/
# WebSocket: ws://localhost:9000
# Flower:    http://localhost:5555
```

### Without Docker (Local development - uses SQLite)

```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

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

Create `.env` in the project root:

```env
# Django
DJANGO_SECRET_KEY=your-secret-key
DJANGO_SETTINGS_MODULE=config.settings.development
ALLOWED_HOSTS=localhost,127.0.0.1
DEBUG=True
FRONTEND_URL=http://localhost:8100

# Database (production only - dev uses SQLite)
DB_NAME=dreamplanner
DB_USER=dreamplanner
DB_PASSWORD=password
DB_HOST=localhost
DB_PORT=5432

# Redis
REDIS_URL=redis://localhost:6379/0
REDIS_HOST=localhost
REDIS_PORT=6379

# OpenAI
OPENAI_API_KEY=your-openai-api-key
OPENAI_ORGANIZATION_ID=your-org-id    # optional

# Social Auth
GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret
APPLE_CLIENT_ID=your-apple-client-id
APPLE_CLIENT_SECRET=your-apple-client-secret
APPLE_KEY_ID=your-apple-key-id

# Stripe
STRIPE_SECRET_KEY=sk_test_...
STRIPE_PUBLISHABLE_KEY=pk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...
STRIPE_PREMIUM_MONTHLY_PRICE_ID=price_...
STRIPE_PREMIUM_YEARLY_PRICE_ID=price_...
STRIPE_PRO_MONTHLY_PRICE_ID=price_...
STRIPE_PRO_YEARLY_PRICE_ID=price_...

# CORS
CORS_ORIGIN=http://localhost:3000,http://localhost:8081

# Email
DEFAULT_FROM_EMAIL=noreply@dreamplanner.app

# AWS (production)
AWS_ACCESS_KEY_ID=your-aws-key
AWS_SECRET_ACCESS_KEY=your-aws-secret
AWS_STORAGE_BUCKET_NAME=dreamplanner-media

# Monitoring (production)
SENTRY_DSN=your-sentry-dsn
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

Token authentication via dj-rest-auth:
```
Authorization: Token <auth_token>
Authorization: Bearer <auth_token>
```

WebSocket authentication via query parameter:
```
ws://localhost:9000/ws/conversations/{id}/?token=<auth_token>
```

### Authentication Endpoints
```
POST   /api/auth/login/                        # Login (email + password)
POST   /api/auth/logout/                       # Logout
POST   /api/auth/registration/                 # Register new account
POST   /api/auth/password/change/              # Change password
POST   /api/auth/password/reset/               # Request password reset
POST   /api/auth/password/reset/confirm/       # Confirm password reset
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

GET    /api/calendar/{view}/                   # Calendar views (today, week, month, overdue)
POST   /api/calendar/reschedule/               # Reschedule tasks
POST   /api/calendar/auto-schedule/            # AI auto-scheduling

POST   /api/calendar/google/auth/              # Start Google Calendar OAuth
GET    /api/calendar/google/callback/          # Google Calendar OAuth callback
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

### WebSocket Routes
```
ws://localhost:9000/ws/conversations/{conversation_id}/    # AI chat (GPT-4 streaming)
ws://localhost:9000/ws/buddy-chat/{conversation_id}/       # Buddy real-time chat
ws://localhost:9000/ws/notifications/                       # Real-time notification delivery
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

### Docker Deployment

```bash
# Build production image
make build-prod

# Tag and push to ECR
docker tag dreamplanner:latest ${ECR_REGISTRY}/dreamplanner:latest
docker push ${ECR_REGISTRY}/dreamplanner:latest

# Deploy to ECS
aws ecs update-service \
  --cluster dreamplanner-prod \
  --service dreamplanner-api \
  --force-new-deployment
```

### Infrastructure (AWS)
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
- **API Endpoints**: 150+
- **WebSocket Consumers**: 3 (AI Chat, Buddy Chat, Notifications)
- **Celery Beat Tasks**: 15 periodic tasks
- **On-Demand Celery Tasks**: 35+ async tasks
- **Management Commands**: seed_leagues, seed_store
- **Models**: 40+
- **Test Coverage**: 99%+ target

---

## Security

- Token Authentication with django-allauth + DRF
- Social Auth (Google, Apple) via allauth providers
- Two-Factor Authentication (TOTP) with backup codes
- HTTPS enforcement in production (TLS 1.2+)
- CORS configuration with whitelist
- SQL injection protection via Django ORM
- XSS protection via Django middleware
- CSRF protection via DRF
- Rate limiting: Nginx (10 req/s API, 5 req/s WebSocket) + DRF throttles (30/min anon, 120/min user, 20/min AI chat, 10/min AI plan)
- Input validation via DRF Serializers
- Secrets management via AWS Secrets Manager
- Container security with non-root user
- Security headers: HSTS, X-Frame-Options, CSP

---

## Documentation

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
