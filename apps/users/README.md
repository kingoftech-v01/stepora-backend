# Users App - DreamPlanner Backend

## Overview

The **users** app manages user authentication, profiles, gamification, and social features including the Dream Buddy system.

## Features

### Core Features
- User management with django-allauth + Token authentication
- Profile management (display name, avatar, timezone, preferences)
- Enhanced profile fields (bio, location, social_links, avatar_image, profile_visibility)
- Avatar upload endpoint (POST /upload-avatar/ with file type/size validation)
- Subscription management (free, premium, pro)
- Work schedule and notification preferences

### Account Management
- Account deletion (soft-delete, GDPR compliant)
- Email change with verification (Celery task)
- Data export endpoint (GDPR compliant downloadable archive)
- Notification preferences endpoint (per-type push/email toggles)

### Two-Factor Authentication (2FA)
- 2FA setup (TOTP-based)
- 2FA verify
- 2FA disable
- 2FA status check
- Backup codes generation and management

### Gamification Features
- XP and leveling system
- Streak tracking (daily activity)
- RPG-style attributes (health, career, education, etc.)
- Badge/achievement system
- Rank tiers (Dreamer -> Legend)

### Social Features
- Dream Buddy matching system
- Accountability partnerships
- User statistics and progress tracking

## Models

### User
Main user model with django-allauth integration and gamification.

**Fields**:
- `id` (UUID) - Primary key
- `email` (Email, unique) - User email
- `display_name` (String) - Display name
- `avatar_url` (URL) - Profile picture
- `avatar_image` (ImageField) - Uploaded avatar image file
- `bio` (TextField) - User biography
- `location` (String) - User location
- `social_links` (JSONField) - Social media profile links
- `profile_visibility` (Choice) - Profile visibility setting (public/friends/private)
- `timezone` (String) - User timezone (default: Europe/Paris)
- `subscription` (Choice) - Subscription tier (free/premium/pro)
- `subscription_ends` (DateTime) - Subscription expiration
- `xp` (Integer) - Experience points
- `level` (Integer) - User level
- `streak_days` (Integer) - Consecutive active days
- `last_activity` (DateTime) - Last activity timestamp
- `work_schedule` (JSON) - Work hours configuration
- `notification_prefs` (JSON) - Notification preferences
- `app_prefs` (JSON) - App preferences

**Methods**:
- `is_premium` (property) - Check if user has active premium
- `update_streak()` - Update daily streak
- `award_xp(amount)` - Award XP and check for level up

### GamificationProfile
Extended gamification data for RPG-style attributes.

**Fields**:
- `user` (OneToOne) - Related user
- `xp` (Integer) - Experience points
- `level` (Integer) - Current level
- `attributes` (JSON) - RPG attributes (health, career, etc.)

### DreamBuddy
Accountability partner matching system.

**Fields**:
- `user` (ForeignKey) - User requesting buddy
- `buddy` (ForeignKey) - Matched buddy user
- `status` (String) - pending/active/ended
- `matched_at` (DateTime) - Matching date

### Badge
Achievement badges system.

**Fields**:
- `user` (ForeignKey) - Badge owner
- `badge_type` (String) - Type identifier
- `name` (String) - Badge name
- `description` (Text) - Badge description
- `icon_url` (URL) - Badge icon
- `is_claimed` (Boolean) - Whether badge is claimed
- `earned_at` (DateTime) - Earned date
- `claimed_at` (DateTime) - Claimed date

## API Endpoints

### Profile Management
```
GET    /api/users/me/                      # Get current user profile
PUT    /api/users/me/                      # Update full profile
PATCH  /api/users/me/                      # Partial update
POST   /api/users/me/upload-avatar/        # Upload avatar image (file type/size validation)
```

**Response Example**:
```json
{
  "id": "uuid",
  "email": "user@example.com",
  "display_name": "John Doe",
  "xp": 1250,
  "level": 5,
  "streak_days": 7,
  "subscription": "premium",
  "is_premium": true
}
```

### Preferences
```
POST   /api/users/me/update-preferences/  # Update user preferences
```

**Request Body**:
```json
{
  "notification_prefs": {
    "motivation": true,
    "weekly_report": true,
    "reminders": true,
    "dnd_start": "22:00",
    "dnd_end": "08:00"
  },
  "work_schedule": {
    "start_hour": 9,
    "end_hour": 17,
    "working_days": [1, 2, 3, 4, 5]
  },
  "app_prefs": {
    "theme": "dark",
    "language": "fr"
  }
}
```

### Account Management
```
POST   /api/users/me/delete-account/       # Soft-delete account (GDPR compliant)
POST   /api/users/me/change-email/         # Request email change (sends verification via Celery)
GET    /api/users/me/export-data/          # Export all user data (GDPR compliant)
POST   /api/users/me/notification-prefs/   # Update notification preferences
```

### Two-Factor Authentication (2FA)
```
POST   /api/users/me/2fa/setup/            # Initialize 2FA setup (returns TOTP secret + QR code)
POST   /api/users/me/2fa/verify/           # Verify 2FA with TOTP code
POST   /api/users/me/2fa/disable/          # Disable 2FA
GET    /api/users/me/2fa/status/           # Check 2FA status
POST   /api/users/me/2fa/backup-codes/     # Generate backup codes
```

### Statistics
```
GET    /api/users/me/stats/                # Get user statistics
```

**Response Example**:
```json
{
  "total_dreams": 5,
  "completed_dreams": 2,
  "active_dreams": 3,
  "total_tasks": 45,
  "completed_tasks": 32,
  "completion_rate": 71.1,
  "current_streak": 7,
  "longest_streak": 14,
  "total_xp": 1250,
  "level": 5
}
```

## Serializers

### UserSerializer
Complete user serialization with all fields.

**Fields**: All User model fields + `is_premium` property

### UserUpdateSerializer
For profile updates (excludes sensitive fields).

**Fields**: `display_name`, `avatar_url`, `timezone`

### UserStatsSerializer
User statistics aggregation.

**Fields**: Computed statistics fields

## Permissions

### IsOwner
Ensures user can only access/modify their own data.

**Usage**: Applied to all user endpoints

### IsPremiumUser
Checks if user has active premium subscription.

**Usage**: Applied to premium-only features

## Authentication

Uses django-allauth + Token authentication via dj-rest-auth.

**Authentication Flow**:
1. Client registers or logs in via dj-rest-auth endpoints (email/password)
2. Server returns a DRF Token on successful authentication
3. Client sends Token in header: `Authorization: Token <key>` or `Authorization: Bearer <key>`
4. Backend validates the Token and retrieves the associated Django User
5. Request proceeds with authenticated user

**Registration/Login Endpoints** (provided by dj-rest-auth):
```
POST /api/auth/registration/    # Register new user (email + password)
POST /api/auth/login/           # Login (returns Token)
POST /api/auth/logout/          # Logout (invalidates Token)
POST /api/auth/password/reset/  # Password reset via email
```

## Testing

### Test Files
- `tests.py` - Complete test suite (300+ lines)

### Test Coverage
- Model tests (User, GamificationProfile, Badge)
- Authentication tests (django-allauth backend, DRF Token auth)
- ViewSet tests (all CRUD operations)
- Permission tests (IsOwner, IsPremiumUser)
- Gamification tests (XP, levels, streaks)

### Run Tests
```bash
# All users app tests
pytest apps/users/tests.py -v

# With coverage
pytest apps/users/tests.py --cov=apps/users --cov-report=html

# Specific test class
pytest apps/users/tests.py::TestUserModel -v
```

## Security

### Implemented Security
- Token verification on every request via DRF TokenAuthentication
- IsOwner permission on all user endpoints
- Sensitive fields excluded from serializers (password)
- Rate limiting via Nginx (10 req/s)
- CORS whitelist configured
- Input validation via DRF serializers

### Security Best Practices
- Always use IsOwner permission for user-specific endpoints
- Sanitize user-generated content (display_name, avatar_url)
- Rate limit authentication attempts

## Admin Interface

### Registered Models
- User (with search, filters, actions)
- GamificationProfile (inline with User)
- DreamBuddy (with filters by status)
- Badge (with filters by type, claimed status)

### Admin URL
`http://localhost:8000/admin/users/`

## Dependencies

### Internal
- `core.authentication` - Token authentication backend
- `core.permissions` - Custom permissions
- `core.pagination` - Pagination classes

### External
- `django-allauth==65.3.0` - Authentication and account management
- `dj-rest-auth[with-social]==7.0.2` - REST API auth endpoints
- `djangorestframework` - REST API
- `django-filter` - API filtering

## Configuration

### Settings
```python
# django-allauth settings
ACCOUNT_LOGIN_METHODS = {'email'}
ACCOUNT_SIGNUP_FIELDS = ['email*', 'password1*', 'password2*']
ACCOUNT_EMAIL_VERIFICATION = 'optional'

# DRF Token Authentication
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.TokenAuthentication',
    ],
}

# Subscription tiers
SUBSCRIPTION_CHOICES = [
    ('free', 'Free'),
    ('premium', 'Premium'),
    ('pro', 'Pro'),
]

# XP Configuration
XP_PER_LEVEL = 100  # XP required per level
```

## Database Indexes

Optimized indexes for performance:
- `email` - Unique index
- `last_activity` - Index for streak calculations
- `subscription` + `subscription_ends` - Compound index for premium checks

## Related Apps

- **dreams** - User's dreams, goals, tasks
- **conversations** - User's AI conversations
- **notifications** - User notifications
- **calendar** - User's calendar events

## Maintenance

### Common Tasks

**Update user subscription**:
```python
from apps.users.models import User
from django.utils import timezone
from datetime import timedelta

user = User.objects.get(email='user@example.com')
user.subscription = 'premium'
user.subscription_ends = timezone.now() + timedelta(days=30)
user.save()
```

**Award XP and check level up**:
```python
user.award_xp(100)
```

**Update streak**:
```python
user.update_streak()
```

### Database Migrations
```bash
# Create migrations
python manage.py makemigrations users

# Apply migrations
python manage.py migrate users

# Show migrations
python manage.py showmigrations users
```

## Troubleshooting

### Common Issues

**Token authentication fails**:
- Verify the Token exists in the database (`authtoken_token` table)
- Ensure the header format is correct: `Authorization: Token <key>`
- Check that `rest_framework.authentication.TokenAuthentication` is in `DEFAULT_AUTHENTICATION_CLASSES`
- Confirm dj-rest-auth endpoints are included in URL config

**Streak not updating**:
- Check `last_activity` field
- Verify timezone configuration
- Run `user.update_streak()` manually

**Premium check fails**:
- Verify `subscription_ends` is in future
- Check subscription value is 'premium' or 'pro'

## Celery Tasks

| Task | Description |
|------|-------------|
| `send_email_change_verification` | Sends a verification email when a user requests an email change. Generates a signed token and sends a confirmation link |
| `export_user_data` | Collects all user data (profile, dreams, conversations, calendar events, notifications) and packages it as a downloadable archive for GDPR compliance |

## Future Enhancements

- [ ] Social graph (friends, followers)
- [ ] Activity feed

## License

Proprietary - DreamPlanner

---

**Last Updated**: 2026-02-08
**Maintained By**: Backend Team
**Status**: Production Ready
