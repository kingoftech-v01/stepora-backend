# Notifications App

Django application for push notifications and reminders.

> **Note:** FCM is used purely as a push notification delivery channel. Authentication is handled by django-allauth + Token auth.

## Overview

The Notifications app manages all push communications:
- **Notification** - Individual notification
- **NotificationTemplate** - Reusable templates
- **NotificationBatch** - Grouped sends

## Models

### Notification

| Field | Type | Description |
|-------|------|-------------|
| id | UUID | Unique identifier |
| user | FK(User) | Recipient |
| notification_type | CharField | Notification type |
| title | CharField(255) | Title |
| body | TextField | Message body |
| data | JSONField | Deep linking data |
| scheduled_for | DateTime | Scheduled send date |
| sent_at | DateTime | Actual send date |
| read_at | DateTime | Read date |
| opened_at | DateTime | When notification was opened/tapped (analytics tracking) |
| status | CharField | pending, sent, failed, cancelled |
| retry_count | Integer | Number of attempts |

**Notification types:**
- `reminder` - Task reminder
- `motivation` - Motivational message
- `progress` - Progress update
- `achievement` - Badge/achievement unlocked
- `check_in` - Progress check-in
- `rescue` - Rescue mode
- `buddy` - Buddy message
- `system` - System notification

### NotificationTemplate

| Field | Type | Description |
|-------|------|-------------|
| id | UUID | Unique identifier |
| name | CharField(100) | Unique name |
| notification_type | CharField | Type |
| title_template | CharField(255) | Title template |
| body_template | TextField | Body template |
| available_variables | JSONField | Available variables |
| is_active | Boolean | Active template |

### NotificationBatch

| Field | Type | Description |
|-------|------|-------------|
| id | UUID | Unique identifier |
| name | CharField(255) | Batch name |
| total_scheduled | Integer | Scheduled notifications |
| total_sent | Integer | Sent notifications |
| total_failed | Integer | Failed notifications |
| status | CharField | scheduled, processing, completed, failed |

## API Endpoints

- `GET /api/notifications/` - List notifications (supports grouping by type via `?group=true`)
- `GET /api/notifications/{id}/` - Detail
- `POST /api/notifications/{id}/read/` - Mark individual notification as read
- `POST /api/notifications/read-all/` - Mark all notifications as read
- `GET /api/notifications/unread-count/` - Get unread notification count
- `DELETE /api/notifications/{id}/` - Delete a notification

### Notification Preferences

- `GET /api/notifications/preferences/` - Get current notification preferences
- `PUT /api/notifications/preferences/` - Update notification preferences

Granular per-type push and email toggles allow users to control which notification types they receive and through which channel:

```json
{
  "reminder": {"push": true, "email": false},
  "motivation": {"push": true, "email": true},
  "progress": {"push": true, "email": false},
  "achievement": {"push": true, "email": true},
  "buddy": {"push": true, "email": false},
  "system": {"push": true, "email": true}
}
```

### Analytics

- `opened_at` field tracks when a notification was tapped/opened
- Notification grouping by type for aggregated views (e.g., "5 new achievements")

### Templates (Admin)
- `GET /api/notification-templates/` - List templates
- `POST /api/notification-templates/` - Create a template

## Serializers

- `NotificationSerializer` - Full notification
- `NotificationListSerializer` - List version
- `NotificationTemplateSerializer` - Full template

## Firebase Cloud Messaging

The FCM integration handles:
1. Sending individual notifications
2. Batch sending (up to 500)
3. Managing expired tokens
4. Automatic retry on failure

## Do Not Disturb (DND)

Notifications respect DND preferences:
- `dndEnabled` - DND enabled
- `dndStart` - Start time (0-23)
- `dndEnd` - End time (0-23)

Notifications are deferred if sent during DND.

## Celery Tasks

| Task | Frequency | Description |
|------|-----------|-------------|
| `process_pending_notifications` | 1 min | Sends pending notifications |
| `send_reminder_notifications` | 15 min | Task reminders |
| `generate_daily_motivation` | 8:00 AM | Motivational messages |
| `send_weekly_report` | Sun 10:00 AM | Weekly report |
| `check_overdue_tasks` | 10:00 AM | Overdue task detection |
| `cleanup_old_notifications` | Mon 2:00 AM | Old notification cleanup |

## Template Variables

Variables available in templates:
- `{user_name}` - User name
- `{dream_title}` - Dream title
- `{goal_title}` - Goal title
- `{task_title}` - Task title
- `{progress}` - Progress percentage
- `{streak_days}` - Streak days
- `{xp_gained}` - XP gained

## Testing

```bash
# Unit tests
python manage.py test apps.notifications

# With coverage
pytest apps/notifications/tests.py -v --cov=apps.notifications
```

## Configuration

Environment variables:
- `FIREBASE_PROJECT_ID` - Firebase project ID
- `FIREBASE_PRIVATE_KEY` - Private key
- `FIREBASE_CLIENT_EMAIL` - Client email
