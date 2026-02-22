# Social App

Django application implementing the social graph (friendships and follows) and the activity feed for the DreamPlanner community.

## Overview

The Social app provides three core features:
1. **Friendships** - Bidirectional relationships that require mutual acceptance (pending -> accepted/rejected)
2. **Follows** - Unidirectional relationships that do not require acceptance
3. **Activity Feed** - Aggregated feed of activities from friends and followed users

User search is also provided so users can discover and connect with others.

## Models

### BlockedUser

Tracks user blocking relationships. Blocked users cannot send friend requests, follow, or view content.

| Field | Type | Description |
|-------|------|-------------|
| id | UUID | Primary key |
| blocker | FK(User) | User performing the block (related_name: `blocked_users`) |
| blocked | FK(User) | User being blocked (related_name: `blocked_by`) |
| created_at | DateTimeField | Auto-set on creation |

**DB table:** `blocked_users`
**Constraint:** `unique_together = [['blocker', 'blocked']]`

### ReportedUser

User reporting system for moderation.

| Field | Type | Description |
|-------|------|-------------|
| id | UUID | Primary key |
| reporter | FK(User) | User filing the report (related_name: `reports_filed`) |
| reported_user | FK(User) | User being reported (related_name: `reports_received`) |
| reason | CharField(50) | Report reason (harassment, spam, inappropriate_content, other) |
| description | TextField | Detailed description (optional) |
| status | CharField(20) | `pending`, `reviewed`, `resolved`, `dismissed` (default: `pending`) |
| reviewed_by | FK(User) | Admin who reviewed (nullable) |
| created_at | DateTimeField | Auto-set on creation |
| resolved_at | DateTimeField | Resolution timestamp (nullable) |

**DB table:** `reported_users`

### Friendship

Bidirectional friendship between two users requiring acceptance.

| Field | Type | Description |
|-------|------|-------------|
| id | UUID | Primary key |
| user1 | FK(User) | Request sender (related_name: `friendships_sent`) |
| user2 | FK(User) | Request receiver (related_name: `friendships_received`) |
| status | CharField(20) | `pending`, `accepted`, `rejected` (default: `pending`) |
| created_at | DateTimeField | Auto-set on creation |
| updated_at | DateTimeField | Auto-set on update |

**DB table:** `friendships`
**Constraint:** `unique_together = [['user1', 'user2']]`

**Status transitions:** `pending` -> `accepted` or `rejected`. Rejected requests can be re-sent (status reset to `pending`).

### UserFollow

Unidirectional follow relationship.

| Field | Type | Description |
|-------|------|-------------|
| id | UUID | Primary key |
| follower | FK(User) | The user following (related_name: `following_set`) |
| following | FK(User) | The user being followed (related_name: `followers_set`) |
| created_at | DateTimeField | Auto-set on creation |

**DB table:** `user_follows`
**Constraint:** `unique_together = [['follower', 'following']]`

### ActivityFeedItem

An item in the social activity feed.

| Field | Type | Description |
|-------|------|-------------|
| id | UUID | Primary key |
| user | FK(User) | Activity performer (related_name: `activity_items`) |
| activity_type | CharField(30) | Activity type (see choices below) |
| content | JSONField | Structured content data (e.g., task title, dream name) |
| related_user | FK(User) | Related user, if applicable (related_name: `related_activity_items`, nullable) |
| data | JSONField | Additional metadata |
| created_at | DateTimeField | Auto-set on creation |

**DB table:** `activity_feed_items`

**Activity Types:**

| Type | Display Name |
|------|-------------|
| `task_completed` | Task Completed |
| `dream_completed` | Dream Completed |
| `milestone_reached` | Milestone Reached |
| `buddy_matched` | Buddy Matched |
| `circle_joined` | Circle Joined |
| `level_up` | Level Up |
| `streak_milestone` | Streak Milestone |
| `badge_earned` | Badge Earned |

## API Endpoints

### Friendships

| Method | Path | Description |
|--------|------|-------------|
| GET | `/friends` | List accepted friends |
| GET | `/friends/requests/pending` | List pending received requests |
| GET | `/friends/requests/sent` | List sent friend requests |
| GET | `/friends/mutual/{user_id}` | List mutual friends with a specific user |
| POST | `/friends/request` | Send a friend request (body: `{"targetUserId": "UUID"}`) |
| POST | `/friends/accept/{request_id}` | Accept a pending request |
| POST | `/friends/reject/{request_id}` | Reject a pending request |
| DELETE | `/friends/{friendship_id}` | Unfriend a user |

**ViewSet:** `FriendshipViewSet` (GenericViewSet)
- Permission: `IsAuthenticated`

### Follows

| Method | Path | Description |
|--------|------|-------------|
| POST | `/follow` | Follow a user (body: `{"targetUserId": "UUID"}`) |
| DELETE | `/follow/{user_id}` | Unfollow a user |
| GET | `/follow/suggestions` | Get follow suggestions based on mutual connections and activity |
| GET | `/follow/counts/{user_id}` | Get follower and following counts for a user |

**ViewSet:** `FriendshipViewSet` (same viewset, different action)
- Permission: `IsAuthenticated`

### Blocking and Reporting

| Method | Path | Description |
|--------|------|-------------|
| POST | `/block` | Block a user (body: `{"targetUserId": "UUID"}`) |
| DELETE | `/block/{user_id}` | Unblock a user |
| GET | `/blocked` | List blocked users |
| POST | `/report` | Report a user (body: `{"targetUserId": "UUID", "reason": "harassment", "description": "..."}`) |

### Activity Feed

| Method | Path | Description |
|--------|------|-------------|
| GET | `/feed/friends` | Activity feed from friends + followed users + self |
| GET | `/feed/friends?type={activity_type}` | Filter feed by activity type |
| GET | `/feed/friends?from={date}&to={date}` | Filter feed by date range |

**View:** `ActivityFeedView` (ListAPIView)
- Permission: `IsAuthenticated`
- Paginated. Response uses key `activities` instead of `results`

### User Search

| Method | Path | Description |
|--------|------|-------------|
| GET | `/users/search?q={query}` | Search users by display name or email (min 2 chars, max 20 results) |

**View:** `UserSearchView` (ListAPIView)
- Permission: `IsAuthenticated`
- Returns users with `isFriend` and `isFollowing` flags
- Excludes the requesting user from results

## Serializers

| Serializer | Purpose |
|------------|---------|
| `UserPublicSerializer` | Public user profile: `username`, `avatar`, `currentLevel`, `influenceScore`, `currentStreak`, `title` |
| `FriendSerializer` | Friend entry: `id`, `username`, `avatar`, `title`, `currentLevel`, `influenceScore`, `currentStreak` |
| `FriendRequestSerializer` | Pending request with nested `sender` info (id, username, avatar, level, XP) |
| `UserSearchResultSerializer` | Search result: user info plus `isFriend` and `isFollowing` booleans |
| `ActivityFeedItemSerializer` | Feed item with nested `user` (id, username, avatar), `type`, `content`, `createdAt` |
| `SendFriendRequestSerializer` | Input: `targetUserId` (UUID) |
| `FollowUserSerializer` | Input: `targetUserId` (UUID) |

### User Titles (Level-Based)

| Level Range | Title |
|------------|-------|
| 0-4 | Dreamer |
| 5-9 | Explorer |
| 10-19 | Achiever |
| 20-29 | Expert |
| 30-49 | Master |
| 50+ | Legend |

## Admin

All three models are registered with Django admin:

- **FriendshipAdmin** - Filter by status. Search by user email/display name. Shows both users, status, and timestamps
- **UserFollowAdmin** - Filter by date. Search by follower/following email/display name
- **ActivityFeedItemAdmin** - Filter by activity type. Shows `content_preview` (truncated). Search by user email/display name
- **BlockedUserAdmin** - Filter by date. Search by blocker/blocked email/display name
- **ReportedUserAdmin** - Filter by status, reason. Search by reporter/reported email/display name
