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
| POST | `/find-match` | Find a compatible buddy match |
| POST | `/pair` | Create a pairing with a specific user (body: `{"partnerId": "UUID"}`) |
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

Creates a pairing directly (status set to `active` immediately). Both users must not have an existing active pairing.

#### POST /{id}/encourage

Creates a BuddyEncouragement record. Also attempts to create a notification for the partner (best-effort, fails silently if the notifications app is unavailable).

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

## Admin

Both models are registered with Django admin:

- **BuddyPairingAdmin** - Shows both users, status, compatibility score, and timestamps. Includes `BuddyEncouragementInline` for viewing encouragements within a pairing. Filter by status
- **BuddyEncouragementAdmin** - Shows `message_preview` (truncated to 80 chars). Filter by date. Search by sender email/display name or message content
