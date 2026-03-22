# Notifications App

Django application for push notifications, reminders, and real-time delivery via WebSocket, email, and Web Push.

## Overview

The Notifications app manages all push communications:

- **Notification** - Individual notification with scheduling, DND, retry logic
- **NotificationTemplate** - Reusable templates with variable interpolation
- **NotificationBatch** - Grouped batch sends with progress tracking
- **WebPushSubscription** - Browser Web Push subscriptions (VAPID)

## Models

### Notification

Push notification with multi-channel delivery support.

| Field | Type | Description |
|-------|------|-------------|
| id | UUID | Primary key |
| user | FK(User) | Recipient (related_name: `notifications`) |
| notification_type | CharField(20) | Type (see choices below) |
| title | CharField(255) | Notification title |
| body | TextField | Message body |
| data | JSONField | Deep linking data: `{screen, dreamId, goalId, taskId}` (default: {}) |
| scheduled_for | DateTimeField | Scheduled send date |
| sent_at | DateTimeField | Actual send date (nullable) |
| read_at | DateTimeField | Read date (nullable) |
| opened_at | DateTimeField | When notification was opened/tapped for analytics (nullable) |
| image_url | URLField(500) | Optional image URL for rich notifications |
| action_url | CharField(500) | Deep link URL for the notification action |
| status | CharField(20) | `pending`, `sent`, `failed`, `cancelled` (default: `pending`) |
| retry_count | IntegerField | Number of delivery attempts (default: 0) |
| max_retries | IntegerField | Maximum retry attempts (default: 3) |
| error_message | TextField | Error message on failure |
| created_at | DateTimeField | Auto-set on creation |

**DB table:** `notifications`

**Notification types:**

| Type | Display Name |
|------|-------------|
| `reminder` | Reminder |
| `motivation` | Motivation |
| `progress` | Progress |
| `achievement` | Achievement |
| `check_in` | Check In |
| `rescue` | Rescue |
| `buddy` | Buddy |
| `system` | System |
| `missed_call` | Missed Call |
| `dream_completed` | Dream Completed |
| `weekly_report` | Weekly Report |
| `daily_summary` | Daily Summary |

**Methods:**

- `mark_sent()` - Set status to `sent`, record `sent_at`
- `mark_read()` - Record `read_at` timestamp
- `mark_opened()` - Record `opened_at` timestamp (also marks as read if not already)
- `mark_failed(error_message)` - Set status to `failed`, increment `retry_count`
- `should_send()` - Check if notification should be sent now (checks status, schedule, DND period)

### NotificationTemplate

Reusable template for notification messages with variable interpolation.

| Field | Type | Description |
|-------|------|-------------|
| id | UUID | Primary key |
| name | CharField(100) | Unique template name |
| notification_type | CharField(20) | Type of notification this template creates |
| title_template | CharField(255) | Title template with `{variable}` placeholders |
| body_template | TextField | Body template with `{variable}` placeholders |
| available_variables | JSONField | List of available variables (default: []) |
| is_active | BooleanField | Whether template is available (default: True) |
| created_at | DateTimeField | Auto-set on creation |
| updated_at | DateTimeField | Auto-set on update |

**DB table:** `notification_templates`

**Methods:**

- `render(**variables)` - Render template by replacing `{key}` placeholders with provided values. Returns `(title, body)` tuple.

### WebPushSubscription

Browser Web Push subscription using VAPID protocol.

| Field | Type | Description |
|-------|------|-------------|
| id | UUID | Primary key |
| user | FK(User) | Subscriber (related_name: `webpush_subscriptions`) |
| subscription_info | JSONField | Web Push subscription: `{endpoint, keys: {p256dh, auth}}` |
| browser | CharField(50) | Browser identifier |
| is_active | BooleanField | Whether subscription is active (default: True) |
| created_at | DateTimeField | Auto-set on creation |

**DB table:** `webpush_subscriptions`

### UserDevice

FCM device registration for push notifications.

| Field | Type | Description |
|-------|------|-------------|
| id | UUID | Primary key |
| user | FK(User) | Device owner (related_name: `devices`) |
| fcm_token | TextField | Firebase Cloud Messaging token (unique) |
| platform | CharField(10) | `android`, `ios`, or `web` |
| device_name | EncryptedCharField(255) | Human-readable device name (encrypted at rest) |
| app_version | CharField(50) | App version at registration |
| is_active | BooleanField | Active status (default: True) |
| created_at | DateTimeField | Auto-set on creation |
| updated_at | DateTimeField | Auto-set on update |

**DB table:** `user_devices`

### NotificationBatch

Batch of notifications sent together with progress tracking.

| Field | Type | Description |
|-------|------|-------------|
| id | UUID | Primary key |
| name | CharField(255) | Batch name |
| notification_type | CharField(20) | Type of notifications in the batch |
| total_scheduled | IntegerField | Total scheduled notifications (default: 0) |
| total_sent | IntegerField | Successfully sent (default: 0) |
| total_failed | IntegerField | Failed sends (default: 0) |
| status | CharField(20) | `scheduled`, `processing`, `completed`, `failed` (default: `scheduled`) |
| created_at | DateTimeField | Auto-set on creation |
| completed_at | DateTimeField | Completion timestamp (nullable) |

**DB table:** `notification_batches`

## API Endpoints

### Notifications

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | List notifications (filterable by `notification_type`, `status`) |
| POST | `/` | Create a notification |
| GET | `/{id}/` | Notification detail |
| PUT | `/{id}/` | Update a notification |
| DELETE | `/{id}/` | Delete a notification |
| POST | `/{id}/mark_read/` | Mark notification as read |
| POST | `/{id}/opened/` | Mark notification as opened (analytics) |
| POST | `/mark_all_read/` | Delete all notifications (clears inbox) |
| GET | `/unread_count/` | Get count of unread sent notifications |
| GET | `/grouped/` | Get notifications grouped by type with total and unread counts |

**ViewSet:** `NotificationViewSet` (ModelViewSet)

- Permission: `IsAuthenticated`
- Free-tier users only see: `reminder`, `progress`, `dream_completed`, `system`

### Notification Templates

| Method | Path | Description |
|--------|------|-------------|
| GET | `/templates/` | List active templates |
| GET | `/templates/{id}/` | Template detail |

**ViewSet:** `NotificationTemplateViewSet` (ReadOnlyModelViewSet)

- Permission: `IsAuthenticated`

### Web Push Subscriptions

| Method | Path | Description |
|--------|------|-------------|
| GET | `/push-subscriptions/` | List active push subscriptions for current user |
| POST | `/push-subscriptions/` | Register a new push subscription (deactivates existing with same endpoint) |
| DELETE | `/push-subscriptions/{id}/` | Remove a push subscription |

**ViewSet:** `WebPushSubscriptionViewSet` (ModelViewSet, GET/POST/DELETE only)

- Permission: `IsAuthenticated`

### User Devices (FCM)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/devices/` | List active devices for current user |
| POST | `/devices/` | Register FCM device token (re-register deletes old token first) |
| DELETE | `/devices/{id}/` | Soft-delete device (set `is_active=False`) |

**ViewSet:** `UserDeviceViewSet` (ModelViewSet, GET/POST/DELETE only)

- Permission: `IsAuthenticated`
- On create: subscribes device to FCM topics based on user prefs
- On delete: unsubscribes device from all FCM topics

### Notification Batches (Admin)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/batches/` | List batches (filterable by `notification_type`, `status`) |
| GET | `/batches/{id}/` | Batch detail |

**ViewSet:** `NotificationBatchViewSet` (ReadOnlyModelViewSet)

- Permission: `IsAuthenticated`, `IsAdminUser`

## Serializers

| Serializer | Purpose |
|------------|---------|
| `NotificationSerializer` | Full notification with computed `is_read` boolean |
| `NotificationCreateSerializer` | Input: `notification_type`, `title` (sanitized), `body` (sanitized), `data`, `scheduled_for` |
| `NotificationTemplateSerializer` | Full template with `available_variables` |
| `NotificationBatchSerializer` | Batch with computed `success_rate` percentage |
| `WebPushSubscriptionSerializer` | Push subscription with `subscription_info`, `browser` |
| `UserDeviceSerializer` | FCM device with `fcm_token` (validated: min 20, max 4096 chars), `platform`, `device_name`, `app_version` |

## WebSocket Consumer

### NotificationConsumer

Real-time notification delivery via WebSocket.

**URL:** `ws://host/ws/notifications/`

**Authentication:** JWT token via post-connect `authenticate` message (preferred) or middleware

**Rate limiting:** 20 messages per 60-second sliding window

**Flow:**

1. Connection: accept and wait for `authenticate` message
2. Client sends `{"type": "authenticate", "token": "<jwt_access_token>"}`
3. Join user-specific group `notifications_{user_id}`
4. Send connection confirmation with current `unread_count`
5. Start heartbeat loop (ping every 45s to keep connection alive)
6. Receive real-time notifications as they are sent

**Message format:**

```json
// Connection confirmation
{"type": "connection", "status": "connected", "unread_count": 5}

// Incoming notification
{"type": "notification", "notification": {"id": "uuid", "notification_type": "...", "title": "...", "body": "...", "data": {}, "image_url": "", "action_url": "", "created_at": "..."}}

// Mark single notification as read
{"type": "mark_read", "notification_id": "uuid"}
// Response: {"type": "marked_read", "notification_id": "uuid"}

// Mark all as read
{"type": "mark_all_read"}
// Response: {"type": "all_marked_read", "count": 5}

// Unread count update (pushed by server)
{"type": "unread_count", "count": 3}
```

## Services

### NotificationDeliveryService

Orchestrates multi-channel notification delivery based on user preferences.

**Channels:**

| Channel | Default | Description |
|---------|---------|-------------|
| WebSocket | Enabled | Real-time via channel layer `group_send` |
| FCM Push | Enabled | Firebase Cloud Messaging to mobile/web devices |
| Web Push | Fallback | VAPID-based browser push via `pywebpush` (only if FCM fails) |
| Email | Disabled (opt-in) | HTML/text email via `send_templated_email` |

**Delivery logic:**

1. Skip if `retry_count >= max_retries`
2. Send via WebSocket (if `websocket_enabled`, default True)
3. Send via email (if `email_enabled`, default False)
4. Send via FCM (if `push_enabled`, default True)
5. If FCM fails, fall back to Web Push VAPID
6. If all channels fail and email was not already tried, send email as last resort
7. Returns `True` if at least one channel succeeds
8. Invalid/expired FCM tokens and Web Push subscriptions are auto-deactivated

### FCMService

Firebase Cloud Messaging service (`fcm_service.py`).

- **Singleton Firebase app**: initialized once per process via `get_firebase_app()`
- **Credentials**: `FIREBASE_CREDENTIALS_JSON` env var (for ECS) or `FIREBASE_CREDENTIALS_PATH` setting
- **send_to_token()**: Send to single device, raises `InvalidTokenError` on bad token
- **send_multicast()**: Send to multiple tokens, auto-chunks lists > 500
- **send_to_topic()**: Send to all devices subscribed to a topic
- **subscribe_to_topic() / unsubscribe_from_topic()**: Manage topic subscriptions
- **Platform configs**: Android (high priority, custom channel), APNS (sound, mutable content), WebPush (icon)

## Do Not Disturb (DND)

Notifications respect DND preferences stored in `user.notification_prefs`:

- `dndEnabled` - Whether DND is active
- `dndStart` - Start hour (0-23, default: 22)
- `dndEnd` - End hour (0-23, default: 7)

DND supports crossing midnight (e.g., 22:00 to 07:00). Notifications during DND are rescheduled to 1 hour later.

## Celery Tasks

| Task | Retries | Description |
|------|---------|-------------|
| `process_pending_notifications` | 3 | Send pending notifications via `NotificationDeliveryService` (checks DND, reschedules if needed) |
| `send_reminder_notifications` | 3 | Send reminders for goals with `reminder_enabled` due in the next 15 minutes |
| `generate_daily_motivation` | 3 | Generate AI motivational messages for active users (respects `ai_background` quota) |
| `send_weekly_report` | 3 | Generate AI weekly progress reports with task completion stats |
| `check_inactive_users` | 3 | Send AI rescue messages to users inactive for 3+ days (max once per 7 days) |
| `cleanup_old_notifications` | 3 | Delete read notifications older than 30 days |
| `send_streak_milestone_notification` | 3 | Send notification at streak milestones (7, 14, 30, 60, 100, 365 days) |
| `send_level_up_notification` | 3 | Send notification when user reaches a new level |
| `expire_ringing_calls` | 3 | Expire calls stuck in 'ringing' > 30s, notify both caller and callee |
| `check_due_tasks` | 3 | Send FCM push for tasks due in next 3 minutes |
| `cleanup_stale_fcm_tokens` | 3 | Deactivate FCM tokens not updated in 60+ days |
| `send_weekly_digests` | 0 | Dispatcher: fans out per-user `send_user_digest` tasks |
| `send_user_digest` | 3 | Generate weekly digest: stats, push, email for a single user |

## Management Commands

| Command | Description |
|---------|-------------|
| `seed_notification_templates` | Seeds 6 notification templates: daily_motivation, streak_milestone, task_reminder, weekly_report, achievement_unlocked, buddy_checkin. Idempotent (update_or_create by name) |

## Admin

All 3 models are registered with Django admin:

- **NotificationAdmin** - Shows title, user, type, status, scheduled_for, sent_at. Fieldsets: Basic Info, Data & Deep Linking (collapsed), Scheduling, Retry Logic (collapsed), Timestamps. Filter by type, status, scheduled_for, date. Search by title, body, user email. Custom actions: `mark_as_sent`, `mark_as_cancelled`
- **NotificationTemplateAdmin** - Shows name, type, is_active. Fieldsets: Basic Info, Template, Timestamps. Filter by type, is_active, date. Search by name, title_template, body_template
- **NotificationBatchAdmin** - Shows name, type, status, computed `progress` (percentage). Filter by type, status, date. Search by name

## Template Variables

Variables available in notification templates:

- `{display_name}` - User display name
- `{streak_days}` - Current streak days
- `{task_title}` - Task title
- `{tasks_completed}` - Tasks completed count
- `{xp_earned}` - XP earned
- `{message}` - Dynamic message
- `{icon}` - Achievement icon
- `{achievement_name}` - Achievement name
- `{xp_reward}` - XP reward amount
- `{buddy_name}` - Buddy display name

## Testing

```bash
pytest apps/notifications/tests/ -v
```

**Test files:**

| File | Coverage |
|------|----------|
| `test_unit.py` | Model CRUD, __str__, mark_sent/read/opened/failed, should_send, DND, data JSON |
| `test_integration.py` | API endpoints: list, create, delete, mark_read, mark_all_read, unread_count, grouped, templates, devices, batches |
| `test_notification_views.py` | ViewSet: CRUD, free-tier filtering, premium access, IDOR, templates, WebPush CRUD, device CRUD with FCM topic mocking, batch admin-only |
| `test_notification_services.py` | NotificationService.create, NotificationDeliveryService: multi-channel delivery, max retries, email fallback, FCM/WebPush/WebSocket channels |
| `test_notification_tasks.py` | All 12 Celery tasks: process_pending, daily_motivation, weekly_digests, check_inactive, reminders, cleanup, streak, level_up, expire_calls, check_due_tasks, cleanup_stale_tokens, _pick_motivational_message |
| `test_fcm_service.py` | FCMService: build_message, send_to_token, send_multicast (chunking, invalid tokens), send_to_topic, subscribe/unsubscribe, InvalidTokenError, MulticastResult |
| `test_notifications_complete.py` | IDOR protection (10 tests), DND logic (8 tests), template render, serializer validation (XSS, FCM token), batch success_rate, model __str__, edge cases |

## Admin Bulk Send

Custom admin view at `/admin/notifications/bulk-send/` for sending notifications to user segments:

- **Audience segments**: all, free, premium, pro, premium+pro, has_device
- **Platform filter**: android, ios, web (optional)
- **Delivery modes**: send now or schedule for later
- Creates `NotificationBatch` record with progress tracking

## Configuration

Environment variables:

- `FIREBASE_CREDENTIALS_JSON` - Firebase Admin SDK credentials (JSON string, preferred for ECS)
- `FIREBASE_CREDENTIALS_PATH` - Path to Firebase credentials file (alternative)
- `WEBPUSH_SETTINGS.VAPID_PRIVATE_KEY` - VAPID private key for Web Push
- `WEBPUSH_SETTINGS.VAPID_ADMIN_EMAIL` - Admin email for VAPID claims
- `DEFAULT_FROM_EMAIL` - Sender email for notification emails
- `FRONTEND_URL` - Frontend URL for email action links

## Dependencies

- `channels` - WebSocket support (ASGI)
- `channels-redis` - Redis channel layer backend
- `firebase-admin` - FCM push notification delivery
- `pywebpush` - Web Push VAPID delivery (fallback)
- `django-encrypted-model-fields` - Encrypted title, body, device_name at rest
- `openai` - AI-generated messages (motivation, rescue, weekly reports)
