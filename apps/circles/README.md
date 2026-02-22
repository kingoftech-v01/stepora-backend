# Circles App

Django application implementing Dream Circles: small, focused accountability groups where users share goals, post progress updates, and participate in challenges.

## Overview

Dream Circles are groups of up to 20 members organized by category (career, health, fitness, etc.). Circles can be public (anyone can join) or private (invite only). Members can post updates to the circle's feed, and circle admins can create challenges with defined time periods for structured accountability.

## Models

### Circle

Represents a Dream Circle group.

| Field | Type | Description |
|-------|------|-------------|
| id | UUID | Primary key |
| name | CharField(200) | Circle display name |
| description | TextField | Circle description and goals |
| category | CharField(30) | Category for discovery (see choices below) |
| is_public | Boolean | Whether publicly visible and joinable (default: True) |
| creator | FK(User) | Circle creator (related_name: `created_circles`) |
| max_members | Integer | Max members allowed (default: 20, range: 2-100) |
| created_at | DateTimeField | Auto-set on creation |
| updated_at | DateTimeField | Auto-set on update |

**DB table:** `circles`

**Category Choices:** `career`, `health`, `fitness`, `education`, `finance`, `creativity`, `relationships`, `personal_growth`, `hobbies`, `other`

**Properties:**
- `member_count` - Current number of members
- `is_full` - True if member count >= max_members

### CircleMembership

Tracks a user's membership and role in a circle.

| Field | Type | Description |
|-------|------|-------------|
| id | UUID | Primary key |
| circle | FK(Circle) | Circle (related_name: `memberships`) |
| user | FK(User) | Member (related_name: `circle_memberships`) |
| role | CharField(20) | `member`, `moderator`, or `admin` (default: `member`) |
| joined_at | DateTimeField | Auto-set on creation |

**DB table:** `circle_memberships`
**Constraint:** `unique_together = [['circle', 'user']]`

### CirclePost

A post/update within a circle's feed.

| Field | Type | Description |
|-------|------|-------------|
| id | UUID | Primary key |
| circle | FK(Circle) | Circle (related_name: `posts`) |
| author | FK(User) | Post author (related_name: `circle_posts`) |
| content | TextField | Post text content |
| created_at | DateTimeField | Auto-set on creation |
| updated_at | DateTimeField | Auto-set on update |

**DB table:** `circle_posts`

### CircleChallenge

A time-bounded challenge within a circle.

| Field | Type | Description |
|-------|------|-------------|
| id | UUID | Primary key |
| circle | FK(Circle) | Circle (related_name: `challenges`) |
| title | CharField(200) | Challenge title |
| description | TextField | Challenge description |
| start_date | DateTimeField | Challenge start |
| end_date | DateTimeField | Challenge end |
| status | CharField(20) | `upcoming`, `active`, `completed`, `cancelled` (default: `upcoming`) |
| participants | M2M(User) | Users who joined (related_name: `circle_challenges`) |
| created_at | DateTimeField | Auto-set on creation |
| updated_at | DateTimeField | Auto-set on update |

**DB table:** `circle_challenges`

**Properties:**
- `is_active` - True if within date range and status is `active`
- `participant_count` - Number of participants

### PostReaction

Reactions on circle posts (emoji-style).

| Field | Type | Description |
|-------|------|-------------|
| id | UUID | Primary key |
| post | FK(CirclePost) | Reacted post (related_name: `reactions`) |
| user | FK(User) | Reacting user (related_name: `post_reactions`) |
| reaction_type | CharField(20) | `thumbs_up`, `fire`, `clap`, `heart` |
| created_at | DateTimeField | Auto-set on creation |

**DB table:** `post_reactions`
**Constraint:** `unique_together = [['post', 'user', 'reaction_type']]`

### CircleInvitation

Invitation system for private circles, supporting both direct and link-based invites.

| Field | Type | Description |
|-------|------|-------------|
| id | UUID | Primary key |
| circle | FK(Circle) | Target circle (related_name: `invitations`) |
| invited_by | FK(User) | Inviting user (related_name: `sent_circle_invitations`) |
| invited_user | FK(User) | Invited user (nullable, for direct invites) |
| invite_code | CharField(50) | Unique invite code (for link-based invites) |
| status | CharField(20) | `pending`, `accepted`, `declined`, `expired` (default: `pending`) |
| expires_at | DateTimeField | Invitation expiry (nullable) |
| created_at | DateTimeField | Auto-set on creation |

**DB table:** `circle_invitations`

### ChallengeProgress

Tracks individual user progress within a challenge.

| Field | Type | Description |
|-------|------|-------------|
| id | UUID | Primary key |
| challenge | FK(CircleChallenge) | Parent challenge (related_name: `progress_entries`) |
| user | FK(User) | Participant (related_name: `challenge_progress`) |
| progress_data | JSONField | Structured progress data |
| updated_at | DateTimeField | Auto-set on update |

**DB table:** `challenge_progress`
**Constraint:** `unique_together = [['challenge', 'user']]`

## API Endpoints

### Circles

| Method | Path | Description |
|--------|------|-------------|
| GET | `/circles/?filter={my\|public\|recommended}` | List circles with filtering |
| POST | `/circles/` | Create a circle (creator auto-added as admin) |
| GET | `/circles/{id}/` | Circle detail with members and challenges |
| PUT | `/circles/{id}/` | Edit circle details (admin only) |
| DELETE | `/circles/{id}/` | Delete a circle (admin only) |
| POST | `/circles/{id}/join/` | Join a public circle |
| POST | `/circles/{id}/leave/` | Leave a circle |
| GET | `/circles/{id}/feed/` | Get circle post feed (members only) |
| POST | `/circles/{id}/posts/` | Create a post in the circle (members only) |
| PUT | `/circles/{id}/posts/{post_id}/` | Edit a post (author only) |
| DELETE | `/circles/{id}/posts/{post_id}/` | Delete a post (author or moderator+) |
| POST | `/circles/{id}/posts/{post_id}/react/` | React to a post (body: `{"reaction_type": "fire"}`) |
| GET | `/circles/{id}/challenges/` | List active/upcoming challenges |
| POST | `/circles/{id}/members/{user_id}/promote/` | Promote member to moderator (admin only) |
| POST | `/circles/{id}/members/{user_id}/demote/` | Demote moderator to member (admin only) |
| DELETE | `/circles/{id}/members/{user_id}/` | Remove a member from the circle (moderator+ only) |

### Invitations

| Method | Path | Description |
|--------|------|-------------|
| POST | `/circles/{id}/invite/` | Send a direct invitation to a user |
| POST | `/circles/{id}/invite-link/` | Generate an invite code/link for the circle |
| POST | `/circles/join-by-code/` | Join a circle using an invite code |
| GET | `/circles/invitations/` | List pending invitations for the current user |
| POST | `/circles/invitations/{id}/accept/` | Accept an invitation |
| POST | `/circles/invitations/{id}/decline/` | Decline an invitation |

**ViewSet:** `CircleViewSet` (ModelViewSet)
- Permission: `IsAuthenticated`

#### List Filters

| Filter | Description |
|--------|-------------|
| `my` | Circles the user is a member of |
| `public` | All public circles |
| `recommended` | Public circles the user has not joined, sorted by member count (default) |

### Challenges

| Method | Path | Description |
|--------|------|-------------|
| POST | `/circles/challenges/{id}/join/` | Join a challenge (must be a circle member) |

**ViewSet:** `ChallengeViewSet` (GenericViewSet)
- Permission: `IsAuthenticated`

## Serializers

| Serializer | Purpose |
|------------|---------|
| `CircleMemberSerializer` | Member display: `username`, `avatar`, `role`, `joined_at` |
| `CircleChallengeSerializer` | Challenge with `participantCount`, `startDate`, `endDate` (camelCase) |
| `CircleListSerializer` | Lightweight: `memberCount`, `maxMembers`, `memberAvatars` (first 5), `creatorName`, `isMember` |
| `CircleDetailSerializer` | Full: nested `members` list, `challenges` list, `isMember` flag |
| `CircleCreateSerializer` | Input: `name`, `description`, `category`, `isPublic`. Auto-sets `creator` and creates admin membership |
| `CirclePostSerializer` | Post with nested `user` object (`id`, `username`, `avatar`) and `createdAt` |
| `CirclePostCreateSerializer` | Input: `content` (max 5000 chars) |

## Permissions

- All endpoints require `IsAuthenticated`
- Feed viewing and posting require circle membership (checked in view logic)
- Leaving as the last admin is blocked if other members exist
- Joining private circles requires an invitation (direct or via invite code)
- Challenge joining requires circle membership
- Post editing restricted to the original author
- Post deletion allowed for the author, moderators, and admins
- Member removal requires moderator or admin role
- Moderator promotion/demotion requires admin role

## Admin

All four models are registered with Django admin:

- **CircleAdmin** - Shows `member_count`. Includes `CircleMembershipInline`, `CircleChallengeInline`, and `CirclePostInline`. Filter by category, visibility, creation date
- **CircleMembershipAdmin** - Filter by role. Search by user email, circle name
- **CirclePostAdmin** - Shows `content_preview` (truncated to 80 chars). Search by content, author
- **CircleChallengeAdmin** - Shows `participant_count`. Filter by status. Uses `filter_horizontal` for participants
