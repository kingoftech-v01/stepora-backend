# Friends App

Social relationship management for Stepora: friendships, follows, blocks, and reports.

## Architecture

The `friends` app defines the **data models** and core **business logic** (services), while the
`social` app exposes the **API endpoints** that the frontend consumes. Both share the same
underlying models.

| Layer           | Location                          | Purpose                                     |
|-----------------|-----------------------------------|---------------------------------------------|
| Models          | `apps/friends/models.py`          | Friendship, UserFollow, BlockedUser, ReportedUser |
| Services        | `apps/friends/services.py`        | `FriendshipService` (is_friend, mutual_friends, suggestions) |
| Admin           | `apps/friends/admin.py`           | Django admin for all 4 models               |
| Tasks           | `apps/friends/tasks.py`           | `cleanup_rejected_requests` (Celery)        |
| API Views       | `apps/social/views.py`            | `FriendshipViewSet` + `FriendSuggestionsView` |
| API URLs        | `apps/social/urls.py`             | Mounted at `/api/social/`                   |
| Legacy API      | `apps/friends/views.py` + `urls.py` | Mounted at `/api/v1/friends/`            |

## Models

### Friendship
Bidirectional relationship requiring acceptance. `user1` is always the sender.

- Status: `pending` -> `accepted` | `rejected`
- Unique constraint: one record per user pair (directional)
- Rejected requests can be re-sent (status reset to pending)

### UserFollow
Unidirectional relationship. No acceptance required.

- Unique constraint: one follow per direction
- Independent of friendships (a user can follow someone who is not a friend)

### BlockedUser
Blocks another user from all social interactions.

- `is_blocked(user_a, user_b)` checks both directions
- Blocking removes existing friendships and follows in both directions
- Blocked users are excluded from search, suggestions, feeds
- `reason` field is encrypted at rest (`EncryptedTextField`)

### ReportedUser
User moderation reports.

- Categories: `spam`, `harassment`, `inappropriate`, `other`
- Status: `pending` -> `reviewed` | `dismissed`
- `reason` field is encrypted at rest
- Multiple reports can be filed against the same user

## API Endpoints (via /api/social/)

### Friendships
| Method | Path                                  | Description               |
|--------|---------------------------------------|---------------------------|
| GET    | `/friends/`                           | List accepted friends     |
| POST   | `/friends/request/`                   | Send friend request       |
| GET    | `/friends/requests/pending/`          | Received pending requests |
| GET    | `/friends/requests/sent/`             | Sent pending requests     |
| POST   | `/friends/accept/<id>/`               | Accept request            |
| POST   | `/friends/reject/<id>/`               | Reject request            |
| DELETE | `/friends/cancel/<id>/`               | Cancel sent request       |
| DELETE | `/friends/remove/<user_id>/`          | Remove friend             |
| GET    | `/friends/mutual/<user_id>/`          | Mutual friends            |
| GET    | `/friends/online/`                    | Online friends            |

### Follows
| Method | Path                         | Description    |
|--------|------------------------------|----------------|
| POST   | `/follow/`                   | Follow user    |
| DELETE | `/unfollow/<user_id>/`       | Unfollow user  |

### Blocks
| Method | Path                         | Description       |
|--------|------------------------------|-------------------|
| POST   | `/block/`                    | Block user        |
| DELETE | `/unblock/<user_id>/`        | Unblock user      |
| GET    | `/blocked/`                  | List blocked users|

### Other
| Method | Path                         | Description         |
|--------|------------------------------|---------------------|
| POST   | `/report/`                   | Report user         |
| GET    | `/counts/<user_id>/`         | Social counts       |
| GET    | `/friend-suggestions/`       | Smart suggestions   |
| GET    | `/follow-suggestions/`       | Follow suggestions  |

## Request Body Formats

All POST endpoints expect `target_user_id` (UUID):

```json
{ "target_user_id": "uuid-here" }
```

Block and report accept additional fields:

```json
// Block
{ "target_user_id": "uuid", "reason": "optional" }

// Report
{ "target_user_id": "uuid", "reason": "required", "category": "spam|harassment|inappropriate|other" }
```

## FriendshipService

Business logic layer used by views and other apps.

```python
from apps.friends.services import FriendshipService

FriendshipService.is_friend(user_a_id, user_b_id)   # bool
FriendshipService.is_blocked(user_a_id, user_b_id)  # bool (both directions)
FriendshipService.mutual_friends(user_a_id, user_b_id)  # list[dict]
FriendshipService.suggestions(user, limit=10)        # list[dict]
```

## Friend Suggestions Algorithm

The `FriendSuggestionsView` (in `apps/social/views.py`) scores potential friends based on:

1. **Mutual friends** (40%) -- more shared connections = higher score
2. **Shared dream categories** (25%) -- similar goals and interests
3. **Activity level** (15%) -- recently active users rank higher
4. **Streak similarity** (10%) -- users with similar dedication levels
5. **Level proximity** (10%) -- users at similar experience levels

Excluded from suggestions: existing friends, pending requests, blocked users, self.

## Frontend Screens

| Screen               | Path                    | Hook                          |
|----------------------|-------------------------|-------------------------------|
| Friend Requests      | `/friend-requests`      | `useFriendRequestsScreen`     |
| Online Friends       | `/online-friends`       | `useOnlineFriendsScreen`      |
| User Search          | `/search`               | `useUserSearchScreen`         |
| User Profile         | `/user/:id`             | `useUserProfileScreen`        |
| Blocked Users        | `/settings/blocked`     | `useBlockedUsersScreen`       |
| Friend Suggestions   | (component)             | `FriendSuggestions.jsx`       |

Each screen has 3-device variants (Mobile, Tablet, Desktop) sharing a single business logic hook.

## Security

- All endpoints require `IsAuthenticated`
- IDOR protection: only the request recipient (user2) can accept/reject
- Block checks prevent friend requests and follows between blocked users
- Sensitive fields (reason) are encrypted at rest
- Social counts return 404 for blocked user pairs

## Celery Tasks

- `cleanup_rejected_requests`: Removes rejected friend requests older than 30 days.
  Scheduled via `celery-beat`.

## Tests

- **Backend**: `apps/friends/tests/test_friends_complete.py` (98 tests)
  - Models, services, views, IDOR, edge cases
- **Frontend**: 5 test files, 54 tests total
  - `useFriendRequestsScreen.test.jsx` (13 tests)
  - `useUserSearchScreen.test.jsx` (8 tests)
  - `useOnlineFriendsScreen.test.jsx` (6 tests)
  - `useUserProfileScreen.test.jsx` (18 tests)
  - `useBlockedUsersScreen.test.jsx` (9 tests)
