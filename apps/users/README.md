# Users App

Django application for user management, authentication, gamification, achievements, and account operations.

## Overview

The Users app manages:

- **User** - Custom user model with email auth, gamification, subscriptions, encrypted PII
- **GamificationProfile** - RPG-style attribute XP system (6 life categories)
- **EmailChangeRequest** - Verified email change flow
- **DailyActivity** - Daily activity tracking for heatmap display
- **Achievement** - Achievement definitions with condition-based unlocking
- **UserAchievement** - Tracks which achievements a user has unlocked

## Models

### User

Custom user model using email for authentication (extends `AbstractBaseUser`, `PermissionsMixin`).

| Field | Type | Description |
|-------|------|-------------|
| id | UUID | Primary key |
| email | EmailField | Unique email (login identifier) |
| display_name | CharField(255) | Display name |
| avatar_url | URLField(500) | Profile picture URL |
| avatar_image | ImageField | Uploaded avatar file (upload_to: `avatars/`) |
| bio | EncryptedTextField | User biography (encrypted at rest) |
| location | EncryptedCharField(200) | User location (encrypted at rest) |
| social_links | JSONField | Social media links: `{twitter, instagram, ...}` (nullable) |
| profile_visibility | CharField(20) | `public`, `friends`, `private` (default: `public`) |
| timezone | CharField(50) | User timezone (default: `Europe/Paris`) |
| subscription | CharField(20) | `free`, `premium`, `pro` (default: `free`) |
| subscription_ends | DateTimeField | Subscription expiration (nullable) |
| work_schedule | JSONField | Work schedule: `{workDays, startTime, endTime}` (nullable) |
| notification_prefs | JSONField | Notification preferences (nullable) |
| app_prefs | JSONField | App preferences: `{theme, language}` (nullable) |
| xp | IntegerField | Experience points (default: 0) |
| level | IntegerField | User level (default: 1) |
| streak_days | IntegerField | Consecutive active days (default: 0) |
| last_activity | DateTimeField | Last activity timestamp |
| is_online | BooleanField | Online status (default: False) |
| last_seen | DateTimeField | Last seen timestamp (nullable) |
| is_staff | BooleanField | Django admin access (default: False) |
| is_active | BooleanField | Account active status (default: True) |
| created_at | DateTimeField | Auto-set on creation |
| updated_at | DateTimeField | Auto-set on update |

**DB table:** `users`

**Methods:**

- `get_active_plan()` - Returns the `SubscriptionPlan` from the user's active/trialing `Subscription` (cached per-request on `_cached_plan`)
- `is_premium()` - Returns True if active plan slug is `premium` or `pro` (reads from DB via `get_active_plan()`)
- `can_create_dream()` - Check dream creation limit from active plan's `dream_limit` field (reads from DB)
- `update_activity()` - Update `last_activity` to now
- `add_xp(amount)` - Add XP and auto-level (100 XP per level)

### GamificationProfile

RPG-style attribute XP system with 6 life categories.

| Field | Type | Description |
|-------|------|-------------|
| id | UUID | Primary key |
| user | OneToOneField(User) | Related user (related_name: `gamification`) |
| health_xp | IntegerField | Health & Fitness XP (default: 0) |
| career_xp | IntegerField | Career & Business XP (default: 0) |
| relationships_xp | IntegerField | Relationships XP (default: 0) |
| personal_growth_xp | IntegerField | Personal Growth XP (default: 0) |
| finance_xp | IntegerField | Finance XP (default: 0) |
| hobbies_xp | IntegerField | Hobbies XP (default: 0) |
| badges | JSONField | Earned badges (default: []) |
| achievements | JSONField | Earned achievements (default: []) |
| streak_jokers | IntegerField | Streak insurance tokens (default: 3) |
| created_at | DateTimeField | Auto-set on creation |
| updated_at | DateTimeField | Auto-set on update |

**DB table:** `gamification_profiles`

**Methods:**

- `get_attribute_level(attribute)` - Get level for a specific attribute (100 XP per level)
- `add_attribute_xp(attribute, amount)` - Add XP to a specific attribute

### EmailChangeRequest

Stores pending email change requests with token verification.

| Field | Type | Description |
|-------|------|-------------|
| id | UUID | Primary key |
| user | FK(User) | User requesting change (related_name: `email_change_requests`) |
| new_email | EmailField | New email address |
| token | CharField(128) | Unique verification token |
| is_verified | BooleanField | Whether verified (default: False) |
| expires_at | DateTimeField | Token expiration (24 hours) |
| created_at | DateTimeField | Auto-set on creation |

**DB table:** `email_change_requests`

**Properties:**

- `is_expired` - Check if token has expired

### DailyActivity

Daily activity tracking for heatmap display.

| Field | Type | Description |
|-------|------|-------------|
| id | UUID | Primary key |
| user | FK(User) | User (related_name: `daily_activities`) |
| date | DateField | Activity date |
| tasks_completed | IntegerField | Tasks completed that day (default: 0) |
| xp_earned | IntegerField | XP earned that day (default: 0) |
| minutes_active | IntegerField | Active minutes (default: 0) |
| created_at | DateTimeField | Auto-set on creation |

**DB table:** `daily_activities`
**Constraint:** `unique_together = ('user', 'date')`

**Methods:**

- `record_task_completion(user, xp_earned, duration_mins)` (classmethod) - Record or update today's activity

### Achievement

Achievement definition for the gamification system.

| Field | Type | Description |
|-------|------|-------------|
| id | UUID | Primary key |
| name | CharField(200) | Achievement name (unique) |
| description | TextField | Achievement description |
| icon | CharField(50) | Emoji or icon identifier |
| category | CharField(20) | `streaks`, `dreams`, `social`, `tasks`, `special` |
| xp_reward | IntegerField | XP awarded on unlock (default: 0) |
| condition_type | CharField(30) | Unlock condition (see choices below) |
| condition_value | IntegerField | Threshold value to unlock (default: 1) |
| is_active | BooleanField | Whether achievement is available (default: True) |
| created_at | DateTimeField | Auto-set on creation |

**DB table:** `achievements`

**Condition types:** `streak_days`, `dreams_created`, `dreams_completed`, `tasks_completed`, `friends_count`, `circles_joined`, `level_reached`, `xp_earned`, `early_task`, `late_task`, `first_dream`, `first_buddy`, `vision_created`

### UserAchievement

Tracks which achievements a user has unlocked.

| Field | Type | Description |
|-------|------|-------------|
| id | UUID | Primary key |
| user | FK(User) | User (related_name: `user_achievements`) |
| achievement | FK(Achievement) | Achievement (related_name: `user_achievements`) |
| unlocked_at | DateTimeField | Auto-set on creation |

**DB table:** `user_achievements`
**Constraint:** `unique_together = ('user', 'achievement')`

## API Endpoints

### User Profile

| Method | Path | Description |
|--------|------|-------------|
| GET | `/me/` | Get current user profile (with achievements summary, equipped items, season rank) |
| PUT/PATCH | `/update-profile/` | Update profile fields |
| POST | `/upload-avatar/` | Upload avatar image (JPEG/PNG/GIF/WebP, max 5MB) |
| GET | `/stats/` | Get user statistics (dreams, tasks, streaks, XP) |
| GET | `/dashboard/` | Aggregated dashboard: heatmap (28 days), stats, upcoming tasks, top dreams with sparklines |
| GET | `/gamification/` | Get RPG-style gamification profile with skill radar data |
| GET | `/ai-usage/` | Get current AI usage quotas and remaining for today |
| GET | `/achievements/` | List all achievements with unlock status |
| PUT | `/notification-preferences/` | Update per-type notification preferences |

### Account Management

| Method | Path | Description |
|--------|------|-------------|
| DELETE | `/delete-account/` | Soft-delete account (GDPR), anonymize data, requires password confirmation |
| POST | `/change-email/` | Request email change (sends verification via Celery), requires password |
| GET | `/export-data/` | Export all user data as JSON (GDPR data portability), rate-limited |
| GET | `/verify-email/{token}/` | Verify email change via token link |

### Two-Factor Authentication (2FA)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/2fa/setup/` | Initialize 2FA setup (returns TOTP secret + QR code) |
| POST | `/2fa/verify/` | Verify 2FA with TOTP code |
| POST | `/2fa/disable/` | Disable 2FA |
| GET | `/2fa/status/` | Check 2FA status |
| POST | `/2fa/backup-codes/` | Regenerate backup codes |

**ViewSet:** `UserViewSet` (ModelViewSet)

- Permission: `IsAuthenticated`
- Users can only see/modify their own data

## Authentication

Uses the custom `core.auth` package with SimpleJWT for JWT-based authentication.

**Flow:**

1. Register or login via `core.auth` endpoints (email/password)
2. Server returns JWT tokens (short-lived access token + httpOnly refresh cookie on web, or body tokens on native via `X-Client-Platform: native`)
3. Client sends access token in header: `Authorization: Bearer <access_token>`
4. If 2FA is enabled, login returns a challenge token instead of JWT. Client verifies OTP via `POST /api/auth/2fa-challenge/` to receive JWT.

**Auth endpoints** (provided by `core.auth`):

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/auth/registration/` | Register (email + password), returns JWT |
| POST | `/api/auth/login/` | Login (returns JWT or 2FA challenge token) |
| POST | `/api/auth/logout/` | Logout (clears refresh cookie) |
| POST | `/api/auth/token/refresh/` | Refresh access token using httpOnly cookie |
| POST | `/api/auth/password/reset/` | Password reset via email (async Celery task) |
| POST | `/api/auth/password/reset/confirm/` | Confirm password reset with token |
| POST | `/api/auth/2fa-challenge/` | Verify OTP for 2FA login |
| POST | `/api/auth/google/` | Google Sign-In (ID token verification) |
| POST | `/api/auth/apple/` | Apple Sign-In (ID token verification) |

## Serializers

| Serializer | Purpose |
|------------|---------|
| `UserSerializer` | Full user with computed `can_create_dream`, `is_premium` |
| `UserProfileSerializer` | Detailed profile with `active_dreams_count`, `completed_dreams_count`, `achievements_summary` (recent 5), `equipped_items` (from store), `rank` (current season league standing) |
| `UserUpdateSerializer` | Input: `display_name` (validated), `avatar_url` (sanitized), `bio` (sanitized), `location` (validated), `social_links` (sanitized), `profile_visibility`, `timezone`, `work_schedule`, `notification_prefs`, `app_prefs` (all JSON values sanitized) |
| `GamificationProfileSerializer` | RPG profile with per-attribute `{category}_level` computed fields and `skill_radar` data for radar chart |

## Services

### BuddyMatchingService

Finds compatible dream buddies using a weighted scoring algorithm.

**Scoring weights:**

| Factor | Weight | Description |
|--------|--------|-------------|
| Shared dream categories | 40% | Jaccard similarity of active dream categories |
| Activity level | 25% | Streak days similarity |
| Timezone proximity | 20% | Same timezone > same region > different regions |
| Level similarity | 15% | Level difference scoring |

**Minimum compatibility score:** 0.3

**Exclusions:** Self, existing active/pending pairings, inactive users (30+ days)

### UserStatsService

Calculates comprehensive user statistics including `xp_to_next_level`, weekly task completions, and subscription info.

### AchievementService

Checks all achievement conditions against user stats and unlocks any newly met ones. Pre-computes stats for `streak_days`, `dreams_created/completed`, `tasks_completed`, `friends_count`, `circles_joined`, `first_dream`, `first_buddy`, `vision_created`, `level_reached`, `xp_earned`.

## Management Commands

| Command | Description |
|---------|-------------|
| `seed_achievements` | Seeds 17 achievements across 5 categories (streaks: 4, dreams: 4, tasks: 4, social: 3, special: 2). Idempotent (update_or_create by name) |

## Admin

3 models registered with Django admin:

- **UserAdmin** (extends BaseUserAdmin) - Shows email, display_name, subscription, level, xp, streak_days, is_staff. Fieldsets: Basic Info, Subscription, Preferences, Gamification, Permissions, Important dates. Filter by subscription, is_staff, is_active, date. Search by email, display_name
- **GamificationProfileAdmin** - Shows user, health/career/relationships levels, streak_jokers. Filter by date. Search by user email
- **EmailChangeRequestAdmin** - Shows user, new_email, is_verified, expires_at. Filter by is_verified, date. Search by user email, new_email

## Subscription Tiers

| Feature | Free | Premium | Pro |
|---------|------|---------|-----|
| Active dreams | 3 | 10 | Unlimited |
| AI features | Limited | Full | Full |
| Vision board | No | Yes | Yes |
| Notification types | Basic (4) | All | All |

## Gamification

**XP System:** 100 XP per level, auto-levels on `add_xp()`

**RPG Attributes (6 categories):**

- Health & Fitness
- Career & Business
- Relationships
- Personal Growth
- Finance
- Hobbies

Each attribute has independent XP and level tracking. Skill radar data is computed for chart display.

## Celery Tasks

| Task | Description |
|------|-------------|
| `send_email_change_verification` | Sends verification email with token link for email change |

## Testing

```bash
pytest apps/users/tests.py -v
```

## Configuration

```python
# Custom auth settings (in DP_AUTH dict)
DP_AUTH = {
    'EMAIL_VERIFICATION': True,
    'LOGIN_METHODS': ['email'],
    # ... see config/settings/base.py for full config
}

# SimpleJWT authentication
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ],
}

# XP per level
XP_PER_LEVEL = 100
```

## Dependencies

- `djangorestframework-simplejwt` - JWT authentication (access + refresh tokens)
- `django-encrypted-model-fields` - PII encryption at rest (bio, location)
- `pyotp` - TOTP-based 2FA
