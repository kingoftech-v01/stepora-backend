# Users App - DreamPlanner Backend

## Overview

The **users** app manages user authentication, profiles, gamification, and social features including the Dream Buddy system.

## Features

### Core Features
- ✅ User management with Firebase authentication
- ✅ Profile management (display name, avatar, timezone, preferences)
- ✅ FCM token management for push notifications
- ✅ Subscription management (free, premium, pro)
- ✅ Work schedule and notification preferences

### Gamification Features
- ✅ XP and leveling system
- ✅ Streak tracking (daily activity)
- ✅ RPG-style attributes (health, career, education, etc.)
- ✅ Badge/achievement system
- ✅ Rank tiers (Rêveur → Légende)

### Social Features
- ✅ Dream Buddy matching system
- ✅ Accountability partnerships
- ✅ User statistics and progress tracking

## Models

### User
Main user model with Firebase integration and gamification.

**Fields**:
- `id` (UUID) - Primary key
- `firebase_uid` (String, unique) - Firebase authentication ID
- `email` (Email, unique) - User email
- `display_name` (String) - Display name
- `avatar_url` (URL) - Profile picture
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

### FcmToken
Firebase Cloud Messaging tokens for push notifications.

**Fields**:
- `user` (ForeignKey) - Related user
- `token` (String) - FCM device token
- `device_type` (String) - ios/android
- `created_at` (DateTime) - Token creation date

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

### Device Management
```
POST   /api/users/me/register-fcm-token/  # Register device for notifications
```

**Request Body**:
```json
{
  "token": "fcm_device_token",
  "device_type": "ios"
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

### FcmTokenSerializer
FCM token registration.

**Fields**: `token`, `device_type`

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

Uses Firebase authentication with custom Django backend.

**Authentication Flow**:
1. Client authenticates with Firebase
2. Client sends Firebase ID token in header: `Authorization: Bearer <token>`
3. Backend verifies token with Firebase Admin SDK
4. Backend retrieves or creates Django User with `firebase_uid`
5. Request proceeds with authenticated user

## Testing

### Test Files
- `tests.py` - Complete test suite (300+ lines)

### Test Coverage
- ✅ Model tests (User, FcmToken, GamificationProfile, Badge)
- ✅ Authentication tests (Firebase backend, DRF auth)
- ✅ ViewSet tests (all CRUD operations)
- ✅ Permission tests (IsOwner, IsPremiumUser)
- ✅ Gamification tests (XP, levels, streaks)

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
- ✅ Firebase token verification on every request
- ✅ IsOwner permission on all user endpoints
- ✅ Sensitive fields excluded from serializers (password, firebase_uid)
- ✅ Rate limiting via Nginx (10 req/s)
- ✅ CORS whitelist configured
- ✅ Input validation via DRF serializers

### Security Best Practices
- Never expose `firebase_uid` in API responses
- Always use IsOwner permission for user-specific endpoints
- Validate FCM tokens before storing
- Sanitize user-generated content (display_name, avatar_url)
- Rate limit authentication attempts

## Admin Interface

### Registered Models
- User (with search, filters, actions)
- FcmToken (inline with User)
- GamificationProfile (inline with User)
- DreamBuddy (with filters by status)
- Badge (with filters by type, claimed status)

### Admin URL
`http://localhost:8000/admin/users/`

## Dependencies

### Internal
- `core.authentication` - Firebase authentication backend
- `core.permissions` - Custom permissions
- `core.pagination` - Pagination classes

### External
- `firebase-admin` - Firebase Admin SDK
- `djangorestframework` - REST API
- `django-filter` - API filtering

## Configuration

### Settings
```python
# Firebase Admin SDK
FIREBASE_CREDENTIALS = env('FIREBASE_CREDENTIALS')

# Subscription tiers
SUBSCRIPTION_CHOICES = [
    ('free', 'Free'),
    ('premium', 'Premium'),
    ('pro', 'Pro'),
]

# XP Configuration
XP_PER_LEVEL = 100  # XP required per level
```

### Environment Variables
```bash
FIREBASE_CREDENTIALS=path/to/firebase-credentials.json
```

## Database Indexes

Optimized indexes for performance:
- `firebase_uid` - Unique index for authentication
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

**Firebase authentication fails**:
- Check `FIREBASE_CREDENTIALS` path
- Verify Firebase project configuration
- Ensure token is not expired

**Streak not updating**:
- Check `last_activity` field
- Verify timezone configuration
- Run `user.update_streak()` manually

**Premium check fails**:
- Verify `subscription_ends` is in future
- Check subscription value is 'premium' or 'pro'

## Future Enhancements

- [ ] Social graph (friends, followers)
- [ ] Activity feed
- [ ] User blocking/reporting
- [ ] Email verification
- [ ] Password reset (if adding email/password auth)
- [ ] Two-factor authentication
- [ ] Account deletion with data export

## License

Proprietary - DreamPlanner

---

**Last Updated**: 2026-01-28
**Maintained By**: Backend Team
**Status**: ✅ Production Ready
