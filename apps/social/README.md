# Social App

Django application implementing the social graph (friendships, follows, blocking, reporting), activity feed, user search, follow suggestions, dream post social platform, stories, social events, and friend suggestions for the Stepora community.

## Overview

The Social app provides:

1. **Friendships** - Bidirectional relationships requiring mutual acceptance (pending -> accepted/rejected)
2. **Follows** - Unidirectional relationships (no acceptance needed)
3. **Blocking** - Prevents all interaction between two users
4. **Reporting** - User moderation system with category-based reports
5. **Activity Feed** - Aggregated feed from friends and followed users (premium+ for full feed)
6. **User Search** - Discovery by display name with friendship/follow status
7. **Follow Suggestions** - Algorithm-based user recommendations (premium+)
8. **Friend Suggestions** - Smart recommendation engine scored by mutual friends (40%), similar dream categories (30%), activity level (15%), and shared circles (15%), cached 1 hour
9. **Recent Searches** - Saved search history per user (max 20, deduplication)
10. **Dream Posts** - Public dream sharing with images/video/audio, GoFundMe links, visibility controls, and linked achievements/milestones
11. **Dream Post Interactions** - Likes, emoji reactions (6 types), threaded comments, typed encouragements (5 types), sharing/reposting, and bookmarking/saving
12. **Social Events** - Virtual, physical, and challenge events with registration, capacity limits, atomic participant counting, and event feeds
13. **Stories** - Ephemeral 24-hour media posts (image/video) with view tracking, grouped feeds (unviewed first), and viewer lists
14. **Post Reactions** - Emoji reactions (like, love, fire, clap, wow, celebrate) with toggle and change support
15. **3-Tier Social Feed Algorithm** - T1 friends (highest priority, all visibility except private), T2 friends-of-friends (public only, capped at 500 IDs), T3 follows + trending (public posts from last 7 days), interleaved ~8/4/3 per page of 15

## Models

### BlockedUser

Tracks user blocking relationships. Blocked users cannot send friend requests, follow, or view content.

| Field | Type | Description |
|-------|------|-------------|
| id | UUID | Primary key |
| blocker | FK(User) | User performing the block (related_name: `blocked_users`) |
| blocked | FK(User) | User being blocked (related_name: `blocked_by`) |
| reason | EncryptedTextField | Optional reason for blocking (encrypted at rest, default: `''`) |
| created_at | DateTimeField | Auto-set on creation |

**DB table:** `blocked_users`
**Constraint:** `unique_together = [['blocker', 'blocked']]`
**Indexes:** `blocker`, `blocked`

**Side effects of blocking:** Removes existing friendships and follows in both directions.

### ReportedUser

User reporting system for moderation.

| Field | Type | Description |
|-------|------|-------------|
| id | UUID | Primary key |
| reporter | FK(User) | User filing the report (related_name: `reports_made`) |
| reported | FK(User) | User being reported (related_name: `reports_received`) |
| reason | EncryptedTextField | Description of why the user is being reported (encrypted at rest) |
| category | CharField(20) | `spam`, `harassment`, `inappropriate`, `other` (default: `other`) |
| status | CharField(20) | `pending`, `reviewed`, `dismissed` (default: `pending`) |
| admin_notes | TextField | Internal notes from admin review (default: `''`) |
| created_at | DateTimeField | Auto-set on creation |
| updated_at | DateTimeField | Auto-set on update |

**DB table:** `reported_users`
**Indexes:** `status`, `-created_at`

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
**Indexes:** `(user1, status)`, `(user2, status)`, `status`, `-created_at`

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
**Indexes:** `follower`, `following`

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
**Indexes:** `(user, -created_at)`, `activity_type`, `-created_at`

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

### RecentSearch

Stores recent search queries for a user (max 20 per user).

| Field | Type | Description |
|-------|------|-------------|
| id | UUID | Primary key |
| user | FK(User) | User (related_name: `recent_searches`) |
| query | CharField(200) | Search query text |
| search_type | CharField(10) | `users`, `dreams`, `all` (default: `all`) |
| created_at | DateTimeField | Auto-set on creation |

**DB table:** `recent_searches`
**Indexes:** `(user, -created_at)`

### DreamPost

Public dream sharing post with optional image, GoFundMe link, and visibility controls.

| Field | Type | Description |
|-------|------|-------------|
| id | UUID | Primary key |
| user | FK(User) | Post author (related_name: `dream_posts`) |
| dream | FK(Dream) | Associated dream (nullable, related_name: `posts`) |
| content | EncryptedTextField | Post text content (encrypted at rest) |
| image_url | URLField | External image URL (nullable) |
| image_file | ImageField | Uploaded image file (nullable) |
| gofundme_url | URLField | GoFundMe fundraising link (nullable) |
| visibility | CharField(20) | `public`, `followers`, `private` (default: `public`) |
| likes_count | IntegerField | Denormalized like count (default: 0) |
| comments_count | IntegerField | Denormalized comment count (default: 0) |
| shares_count | IntegerField | Denormalized share/repost count (default: 0) |
| is_pinned | BooleanField | Whether post is pinned to user profile (default: False) |
| created_at | DateTimeField | Auto-set on creation |
| updated_at | DateTimeField | Auto-set on update |

**DB table:** `dream_posts`

### DreamPostLike

Like on a dream post (one per user per post).

| Field | Type | Description |
|-------|------|-------------|
| id | UUID | Primary key |
| post | FK(DreamPost) | Liked post (related_name: `likes`) |
| user | FK(User) | Liking user (related_name: `dream_post_likes`) |
| created_at | DateTimeField | Auto-set on creation |

**DB table:** `dream_post_likes`
**Constraint:** `unique_together = [['post', 'user']]`

### DreamPostComment

Comment on a dream post with threading support via self-referential parent FK.

| Field | Type | Description |
|-------|------|-------------|
| id | UUID | Primary key |
| post | FK(DreamPost) | Parent post (related_name: `comments`) |
| user | FK(User) | Comment author (related_name: `dream_post_comments`) |
| content | EncryptedTextField | Comment text (encrypted at rest) |
| parent | FK(self) | Parent comment for threading (nullable, related_name: `replies`) |
| created_at | DateTimeField | Auto-set on creation |

**DB table:** `dream_post_comments`

### DreamEncouragement

Typed encouragement on a dream post (distinct from likes, one per user per post).

| Field | Type | Description |
|-------|------|-------------|
| id | UUID | Primary key |
| post | FK(DreamPost) | Encouraged post (related_name: `encouragements`) |
| user | FK(User) | Encouraging user (related_name: `dream_encouragements`) |
| encouragement_type | CharField(20) | Type of encouragement (see choices below) |
| message | EncryptedTextField | Optional personal message (encrypted at rest) |
| created_at | DateTimeField | Auto-set on creation |

**DB table:** `dream_encouragements`
**Constraint:** `unique_together = [['post', 'user']]`

**Encouragement types:**

| Type | Display Name |
|------|-------------|
| `you_got_this` | You Got This |
| `keep_going` | Keep Going |
| `inspired` | Inspired |
| `proud` | Proud |
| `fire` | Fire |

## API Endpoints

### Friendships

| Method | Path | Description |
|--------|------|-------------|
| GET | `/friends/` | List accepted friends |
| GET | `/friends/requests/pending/` | List pending received requests |
| GET | `/friends/requests/sent/` | List sent friend requests |
| GET | `/friends/mutual/{user_id}/` | List mutual friends with a specific user |
| GET | `/friends/online/` | List friends currently online or active in last 5 minutes |
| POST | `/friends/request/` | Send a friend request (body: `{"targetUserId": "UUID"}`) |
| POST | `/friends/accept/{request_id}/` | Accept a pending request |
| POST | `/friends/reject/{request_id}/` | Reject a pending request |
| DELETE | `/friends/remove/{user_id}/` | Remove a friend |
| DELETE | `/friends/cancel/{request_id}/` | Cancel a pending sent request |

### Follows

| Method | Path | Description |
|--------|------|-------------|
| POST | `/follow/` | Follow a user (body: `{"targetUserId": "UUID"}`) |
| DELETE | `/unfollow/{user_id}/` | Unfollow a user |
| GET | `/follow-suggestions/` | Get follow suggestions (premium+, see algorithm below) |
| GET | `/counts/{user_id}/` | Get follower, following, and friend counts for a user |

### Blocking and Reporting

| Method | Path | Description |
|--------|------|-------------|
| POST | `/block/` | Block a user (body: `{"targetUserId": "UUID", "reason": "..."}`) |
| DELETE | `/unblock/{user_id}/` | Unblock a user |
| GET | `/blocked/` | List blocked users |
| POST | `/report/` | Report a user (body: `{"targetUserId": "UUID", "reason": "...", "category": "harassment"}`) |

### Activity Feed

| Method | Path | Description |
|--------|------|-------------|
| GET | `/feed/friends` | Activity feed from friends + followed users + self |
| GET | `/feed/friends?activity_type={type}` | Filter feed by activity type |
| GET | `/feed/friends?created_after={datetime}` | Filter feed by start date (ISO 8601) |
| GET | `/feed/friends?created_before={datetime}` | Filter feed by end date (ISO 8601) |

**View:** `ActivityFeedView` (ListAPIView)
- Permission: `IsAuthenticated`
- Paginated. Response uses key `activities` instead of `results`
- **Free users** only see encouragement-type activities directed at themselves
- **Premium+ users** see the full feed from friends, followed users, and self
- Blocked users are excluded from the feed in both directions

### User Search

| Method | Path | Description |
|--------|------|-------------|
| GET | `/users/search?q={query}` | Search users by display name (min 2 chars, max 20 results) |

**View:** `UserSearchView` (ListAPIView)
- Permission: `IsAuthenticated`
- Returns users with `isFriend` and `isFollowing` flags
- Searches by `display_name` only (email never exposed)
- Excludes the requesting user and blocked users from results

### Recent Searches

| Method | Path | Description |
|--------|------|-------------|
| GET | `/recent-searches/list/` | List up to 20 recent searches |
| POST | `/recent-searches/add/` | Record a search (body: `{"query": "...", "search_type": "users"}`) |
| DELETE | `/recent-searches/clear/` | Clear all recent searches |

**ViewSet:** `RecentSearchViewSet` (GenericViewSet)
- Permission: `IsAuthenticated`
- Deduplicates queries (re-recording same query moves it to top)
- Auto-prunes to keep only 20 most recent

### Dream Posts

| Method | Path | Description |
|--------|------|-------------|
| GET | `/posts/` | List all posts (paginated) |
| POST | `/posts/` | Create a new dream post |
| GET | `/posts/{id}/` | Get post detail |
| PUT | `/posts/{id}/` | Update own post |
| PATCH | `/posts/{id}/` | Partial update own post |
| DELETE | `/posts/{id}/` | Delete own post |
| GET | `/posts/feed/` | Social feed (followed users + public posts) |
| POST | `/posts/{id}/like/` | Toggle like on a post (increments/decrements `likes_count`) |
| POST | `/posts/{id}/comment/` | Add a comment to a post (supports threading via `parent` field) |
| GET | `/posts/{id}/comments/` | List comments on a post (with nested replies) |
| POST | `/posts/{id}/encourage/` | Send a typed encouragement (body: `{"encouragement_type": "fire", "message": "..."}`) |
| POST | `/posts/{id}/share/` | Share/repost a dream post (increments `shares_count`) |
| GET | `/posts/user/{user_id}/` | Get all posts by a specific user |

**ViewSet:** `DreamPostViewSet` (ModelViewSet)
- Permission: `IsAuthenticated`

### Feed Algorithm

The `feed` endpoint returns posts from followed users and public posts, with the following behavior:

1. **Sources:** Posts from users the requester follows, plus public posts
2. **Exclusions:** Posts by blocked users are excluded (bidirectional)
3. **Annotations:** Each post is annotated with `has_liked` and `has_encouraged` flags for the requesting user
4. **Ordering:** Newest first (`-created_at`)
5. **Pagination:** Standard pagination (20 per page)

## ViewSets and Views

| View | Type | Permission |
|------|------|------------|
| `FriendshipViewSet` | GenericViewSet | `IsAuthenticated` |
| `ActivityFeedView` | ListAPIView | `IsAuthenticated` |
| `UserSearchView` | ListAPIView | `IsAuthenticated` |
| `FollowSuggestionsView` | ListAPIView | `IsAuthenticated`, `CanUseSocialFeed` |
| `RecentSearchViewSet` | GenericViewSet | `IsAuthenticated` |
| `DreamPostViewSet` | ModelViewSet | `IsAuthenticated` |

## Serializers

| Serializer | Purpose |
|------------|---------|
| `UserPublicSerializer` | Public user profile: `id`, `username`, `avatar`, `currentLevel`, `influenceScore`, `currentStreak`, `title` |
| `FriendSerializer` | Friend entry: `id`, `username`, `avatar`, `title`, `currentLevel`, `influenceScore`, `currentStreak` |
| `FriendRequestSerializer` | Pending request with nested `sender` info (id, username, avatar, level, XP) |
| `UserSearchResultSerializer` | Search result: user info + `isFriend` and `isFollowing` booleans |
| `ActivityFeedItemSerializer` | Feed item with nested `user` (id, username, avatar), `type`, `content`, `createdAt` |
| `SendFriendRequestSerializer` | Input: `targetUserId` (UUID) |
| `FollowUserSerializer` | Input: `targetUserId` (UUID) |
| `BlockUserSerializer` | Input: `targetUserId` (UUID), optional `reason` (sanitized) |
| `ReportUserSerializer` | Input: `targetUserId` (UUID), `reason` (sanitized), `category` (choice) |
| `BlockedUserSerializer` | Blocked user list item: `id`, nested `user` (id, username, avatar), `reason`, `created_at` |
| `DreamPostSerializer` | Full post with `user` info, `likesCount`, `commentsCount`, `sharesCount`, `hasLiked`, `hasEncouraged`, `encouragementSummary`, `imageUrl`, `dreamTitle` |
| `DreamPostCreateSerializer` | Input: `content`, optional `dream_id`, `gofundme_url`, `visibility`, `image_url` |
| `DreamPostCommentSerializer` | Comment with nested `user`, `content`, `parent`, `replies` (nested), `createdAt` |
| `DreamEncouragementSerializer` | Encouragement with `user`, `encouragementType`, `message`, `createdAt` |

## Follow Suggestions Algorithm

`FollowSuggestionsView` recommends users to follow using a weighted scoring system across three strategies:

| Strategy | Score | Description |
|----------|-------|-------------|
| Shared circles | 3 | Users who are members of the same Circles (via `CircleMembership`) |
| Friends of friends | 2 | Users who are friends with your friends (limited to first 20 friends for performance) |
| Similar dream categories | 1 | Users with active dreams in the same categories (limited to 50 candidates) |

- Returns top 20 suggestions sorted by score
- Excludes: self, existing friends, existing follows, blocked users, inactive users
- Requires `CanUseSocialFeed` permission (premium+ subscription)

## Permissions

| Permission | Description |
|------------|-------------|
| `CanUseSocialFeed` | Restricts full activity feed and follow suggestions to premium+ users. Free users only see encouragement activities. |

## User Titles (Level-Based)

| Level Range | Title |
|------------|-------|
| 0-4 | Dreamer |
| 5-9 | Explorer |
| 10-19 | Achiever |
| 20-29 | Expert |
| 30-49 | Master |
| 50+ | Legend |

## Admin

5 models registered with Django admin:

- **FriendshipAdmin** - Filter by status, date. Search by user email/display name. Shows both users, status, timestamps. Raw ID fields for users
- **UserFollowAdmin** - Filter by date. Search by follower/following email/display name. Raw ID fields
- **ActivityFeedItemAdmin** - Filter by activity type, date. Shows `content_preview` (truncated to 80 chars). Search by user email/display name. Raw ID fields for user, related_user
- **BlockedUserAdmin** - Filter by date. Shows `reason_preview` (truncated to 60 chars). Search by blocker/blocked email/display name. Raw ID fields
- **ReportedUserAdmin** - Filter by status, category, date. Search by reporter/reported email/display name and reason. Fieldsets: Report, Review (status + admin_notes), Timestamps. Raw ID fields

## Testing

```bash
pytest apps/social/tests.py -v
```

## Dependencies

- `django-encrypted-model-fields` - Encryption at rest for `BlockedUser.reason` and `ReportedUser.reason`
- `drf-spectacular` - OpenAPI schema generation for all endpoints
