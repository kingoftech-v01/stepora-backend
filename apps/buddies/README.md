# Buddies App

Django application implementing Dream Buddy accountability pairings, where two users partner up for mutual motivation, progress tracking, and encouragement.

## Overview

The Buddies app provides a one-to-one accountability partnership system. Users can find a compatible match based on level, XP, and activity recency, create a pairing, track side-by-side progress, and send encouragement messages. Each user can have only one active buddy pairing at a time.

## Models

### BuddyPairing

Represents an accountability pairing between two users.

| Field | Type | Description |
|-------|------|-------------|
| id | UUID | Primary key |
| user1 | FK(User) | Initiator (related_name: `buddy_pairings_as_user1`) |
| user2 | FK(User) | Matched partner (related_name: `buddy_pairings_as_user2`) |
| status | CharField(20) | `pending`, `active`, `completed`, `cancelled` (default: `pending`) |
| compatibility_score | Float | Score between 0.0 and 1.0, calculated at match time |
| encouragement_streak | IntegerField | Current consecutive-day encouragement streak (default: 0) |
| best_encouragement_streak | IntegerField | Best-ever consecutive-day encouragement streak (default: 0) |
| last_encouragement_at | DateTimeField | Timestamp of the last encouragement sent (nullable) |
| created_at | DateTimeField | Auto-set on creation |
| updated_at | DateTimeField | Auto-set on update |
| ended_at | DateTimeField | When pairing ended (nullable) |

**DB table:** `buddy_pairings`

### BuddyEncouragement

An encouragement message sent between buddies.

| Field | Type | Description |
|-------|------|-------------|
| id | UUID | Primary key |
| pairing | FK(BuddyPairing) | Parent pairing (related_name: `encouragements`) |
| sender | FK(User) | Message sender (related_name: `sent_encouragements`) |
| message | TextField | Optional motivational message |
| created_at | DateTimeField | Auto-set on creation |

**DB table:** `buddy_encouragements`

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/current` | Get current active buddy pairing (returns `null` if none) |
| GET | `/{id}/progress` | Get progress comparison between user and buddy |
| GET | `/history` | Get pairing history (all past and current pairings) |
| POST | `/find-match` | Find a compatible buddy match |
| POST | `/pair` | Create a pairing with a specific user (body: `{"partnerId": "UUID"}`, status: `active`) |
| POST | `/{id}/accept` | Accept a pending buddy request |
| POST | `/{id}/reject` | Reject a pending buddy request |
| POST | `/{id}/encourage` | Send encouragement to buddy (body: `{"message": "text"}`) |
| DELETE | `/{id}/` | End an active buddy pairing (soft-delete: sets status to `cancelled`) |

**ViewSet:** `BuddyViewSet` (GenericViewSet)
- Permission: `IsAuthenticated`

### Endpoint Details

#### GET /current

Returns the active pairing with partner profile info and recent activity (tasks completed in last 7 days).

#### GET /{id}/progress

Returns side-by-side comparison:
```json
{
  "progress": {
    "user": {
      "currentStreak": 5,
      "tasksThisWeek": 12,
      "influenceScore": 3500
    },
    "partner": {
      "currentStreak": 3,
      "tasksThisWeek": 8,
      "influenceScore": 2800
    }
  }
}
```

#### POST /find-match

Searches for available users (no active pairing, active account) and scores them by compatibility. Returns the best match or `null`.

#### POST /pair

Creates a buddy pairing (status set to `active` immediately). Both users must not have an existing active pairing. A conversation is also created for the buddy pair.

#### POST /{id}/accept

Accepts a pending buddy request. Sets the pairing status to `active`. Only the invited user (user2) can accept.

#### POST /{id}/reject

Rejects a pending buddy request. Sets the pairing status to `cancelled`. Only the invited user (user2) can reject.

#### GET /history

Returns all past and current pairings for the authenticated user, ordered by creation date (newest first).

#### POST /{id}/encourage

Creates a BuddyEncouragement record. Also tracks encouragement streaks (consecutive days of encouragement exchange, awards bonus XP) and attempts to create a notification for the partner (best-effort, fails silently if the notifications app is unavailable).

#### DELETE /{id}/

Sets pairing status to `cancelled` and records `ended_at`. The record is not deleted from the database.

## Matching Algorithm

The `find_match` endpoint scores candidates based on three factors:

| Factor | Weight | Calculation |
|--------|--------|-------------|
| Level proximity | 30% | `max(0.0, 1.0 - (level_diff / 50.0))` |
| XP proximity | 30% | `max(0.0, 1.0 - (xp_diff / 10000.0))` |
| Activity recency | 40% | `max(0.0, 1.0 - (days_since_activity / 30.0))` |

**Candidate pool:** Active users without an existing active pairing, ordered by `last_activity`, limited to top 50. The candidate with the highest combined score is returned.

**Shared interests:** After finding the best match, the system checks both users' gamification profiles for overlapping category XP (health, career, relationships, personal_growth, finance, hobbies).

## Serializers

| Serializer | Purpose |
|------------|---------|
| `BuddyPartnerSerializer` | Partner profile: `id`, `username`, `avatar`, `title`, `currentLevel`, `influenceScore`, `currentStreak` |
| `BuddyPairingSerializer` | Pairing detail: `id`, nested `partner`, `compatibilityScore`, `status`, `recentActivity`, `createdAt` |
| `BuddyProgressSerializer` | Progress comparison: `user` dict and `partner` dict with streak, weekly tasks, influence score |
| `BuddyMatchSerializer` | Match result: `userId`, `username`, `avatar`, `compatibilityScore`, `sharedInterests` |
| `BuddyPairRequestSerializer` | Input: `partnerId` (UUID) |
| `BuddyEncourageSerializer` | Input: `message` (optional, max 1000 chars) |

## WebSocket Integration

### BuddyChatConsumer

Real-time messaging between paired buddies. Defined in `apps/buddies/consumers.py` with routing in `apps/buddies/routing.py`.

**URL:** `ws://host/ws/buddy-chat/{pairing_id}/?token=<auth_token>`

**URL parameter:** `pairing_id` — the UUID of the `BuddyPairing`

**Channel group:** `buddy_chat_{pairing_id}`

**Rate limit:** 30 messages per 60 seconds

**Mixins:** `RateLimitMixin`, `AuthenticatedConsumerMixin`, `BlockingMixin`, `ModerationMixin` (from `core.consumers`)

**Access control:** Only the two users in an active `BuddyPairing` can connect. Block status is re-checked on every message send.

**Flow:**
1. Connection: accept → authenticate → verify pairing → check blocks → get/create buddy_chat conversation → join group
2. Message: validate → rate limit → block re-check → moderate → sanitize → save → broadcast to group → FCM push to offline partner

**Message types (client → server):**
- `authenticate` — Post-connect token auth
- `message` — Send a chat message
- `typing` — Typing indicator
- `mark_read` — Mark messages as read (updates `MessageReadStatus`)
- `ping` — Keepalive

**Message format:**
```json
// Send a message
{"type": "message", "message": "Hey buddy!"}

// Typing indicator
{"type": "typing", "is_typing": true}

// Mark messages as read
{"type": "mark_read"}

// Receive message (includes sender info)
{"type": "message", "message": {"id": "uuid", "content": "Hey!", "sender_id": "uuid", "sender_name": "John", "created_at": "..."}}

// Call started notification (received from server)
{"type": "call_started", "call": {"id": "uuid", "initiator": "uuid", "call_type": "video"}}
```

**FCM Push:** When the partner is not connected to the WebSocket, a push notification is sent via Firebase Cloud Messaging.

## Buddy Calls

The `BuddyViewSet` supports initiating calls between paired buddies. When a call is initiated via REST, a `call_started` event is broadcast to the `buddy_chat_{pairing_id}` WebSocket group, notifying the partner in real time.

## Celery Tasks

| Task | Description |
|------|-------------|
| `send_checkin_reminders` | Periodic task (Celery beat) that sends check-in reminder notifications to active buddy pairs who haven't interacted recently |

**Note:** Encouragement streak tracking (consecutive days of exchange, bonus XP) is handled inline in the `encourage` endpoint, not as a separate Celery task.

## Admin

Both models are registered with Django admin:

- **BuddyPairingAdmin** - Shows both users, status, compatibility score, and timestamps. Includes `BuddyEncouragementInline` for viewing encouragements within a pairing. Filter by status
- **BuddyEncouragementAdmin** - Shows `message_preview` (truncated to 80 chars). Filter by date. Search by sender email/display name or message content
