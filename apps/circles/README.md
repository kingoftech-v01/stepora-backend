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
| inviter | FK(User) | Inviting user (related_name: `circle_invites_sent`) |
| invitee | FK(User) | Invited user (nullable, for direct invites) |
| invite_code | CharField(20) | Unique invite code (for link-based invites) |
| status | CharField(20) | `pending`, `accepted`, `declined`, `expired` (default: `pending`) |
| expires_at | DateTimeField | Invitation expiry |
| created_at | DateTimeField | Auto-set on creation |

**DB table:** `circle_invitations`

### ChallengeProgress

Tracks individual user progress within a challenge.

| Field | Type | Description |
|-------|------|-------------|
| id | UUID | Primary key |
| challenge | FK(CircleChallenge) | Parent challenge (related_name: `progress_entries`) |
| user | FK(User) | Participant (related_name: `challenge_progress`) |
| progress_value | FloatField | Numeric progress value (default: 0) |
| notes | TextField | Optional notes (blank) |
| created_at | DateTimeField | Auto-set on creation |

**DB table:** `challenge_progress`

### CircleMessage

A chat message within a circle's real-time group chat.

| Field | Type | Description |
|-------|------|-------------|
| id | UUID | Primary key |
| circle | FK(Circle) | Circle (related_name: `chat_messages`) |
| sender | FK(User) | Message sender (related_name: `circle_messages`) |
| content | EncryptedTextField | Message text content (encrypted at rest) |
| metadata | JSONField | Additional message metadata (default: {}) |
| created_at | DateTimeField | Auto-set on creation |

**DB table:** `circle_messages`
**Indexes:** `(circle, created_at)`, `sender`

### CircleCall

A voice/video group call within a circle, powered by Agora.

| Field | Type | Description |
|-------|------|-------------|
| id | UUID | Primary key |
| circle | FK(Circle) | Circle (related_name: `calls`) |
| initiator | FK(User) | User who started the call (related_name: `initiated_circle_calls`) |
| call_type | CharField(10) | `voice` or `video` |
| status | CharField(20) | `active`, `completed`, `cancelled` |
| agora_channel | CharField(100) | Agora channel name for this call |
| started_at | DateTimeField | When the call started |
| ended_at | DateTimeField | When the call ended (nullable) |
| duration_seconds | IntegerField | Total call duration (nullable) |
| max_participants | IntegerField | Peak participant count (default: 0) |
| created_at | DateTimeField | Auto-set on creation |

**DB table:** `circle_calls`
**Indexes:** `(circle, status)`, `status`

### CircleCallParticipant

Tracks individual participation in a circle call.

| Field | Type | Description |
|-------|------|-------------|
| id | UUID | Primary key |
| call | FK(CircleCall) | Parent call (related_name: `participants`) |
| user | FK(User) | Participant (related_name: `circle_call_participations`) |
| joined_at | DateTimeField | When the user joined the call |
| left_at | DateTimeField | When the user left (nullable) |

**DB table:** `circle_call_participants`
**Constraint:** `unique_together = [['call', 'user']]`

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

### Circle Chat

| Method | Path | Description |
|--------|------|-------------|
| POST | `/circles/{id}/chat/send/` | Send a chat message (broadcasts to WebSocket group) |
| GET | `/circles/{id}/chat/history/` | Get paginated chat message history (members only) |

### Circle Calls

| Method | Path | Description |
|--------|------|-------------|
| POST | `/circles/{id}/call/start/` | Start a voice/video group call (creates CircleCall, generates Agora token) |
| POST | `/circles/{id}/call/join/` | Join the active call (creates CircleCallParticipant, returns Agora token) |
| POST | `/circles/{id}/call/leave/` | Leave the active call (sets left_at on participant) |
| POST | `/circles/{id}/call/end/` | End the active call (sets status to completed, calculates duration) |
| GET | `/circles/{id}/call/active/` | Get the currently active call with participant list |

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
| `CirclePostUpdateSerializer` | Input: `content` |
| `CircleUpdateSerializer` | Input: `name`, `description`, `category`, `isPublic`, `max_members` |
| `PostReactionSerializer` | Input: `reaction_type` (choice field) |
| `CircleInvitationSerializer` | Full invitation with inviter/invitee/circle names |
| `DirectInviteSerializer` | Input: `user_id` (UUID) |
| `ChallengeProgressSerializer` | Progress entry with `userName`, `userAvatar`, `progress_value`, `notes` |
| `ChallengeProgressCreateSerializer` | Input: `progress_value`, optional `notes` |
| `CircleMessageSerializer` | Chat message: `id`, `circle`, `sender`, `senderName`, `senderAvatar`, `content`, `metadata`, `createdAt` |
| `CircleCallSerializer` | Call detail: `id`, `initiatorName`, `callType`, `agoraChannel`, `status`, `startedAt`, `endedAt`, `participantCount` |

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

## WebSocket Consumer

### CircleChatConsumer

Real-time group chat within a circle. Defined in `apps/circles/consumers.py` with routing in `apps/circles/routing.py`.

**URL:** `ws://host/ws/circle-chat/{circle_id}/`

**Channel group:** `circle_chat_{circle_id}`

**Rate limit:** 20 messages per 60 seconds (lower than buddy chat due to group broadcast volume)

**Mixins:** `RateLimitMixin`, `AuthenticatedConsumerMixin`, `BlockingMixin`, `ModerationMixin` (from `core.consumers`)

**Access control:** User must be a member of the circle (`CircleMembership` required).

**Block filtering:** Messages from blocked users are silently dropped on the receiving end. Each consumer instance loads the user's blocked user IDs at connection time and filters incoming group broadcasts.

**Message types (client → server):**
- `authenticate` — Post-connect token auth
- `message` — Send a chat message
- `typing` — Typing indicator
- `ping` — Keepalive

**Channel layer handlers:**
- `circle_message` — Receive and forward chat messages (with block filtering)
- `typing_status` — Receive and forward typing indicators
- `call_started` — Receive call start notifications (broadcast when a call is started via REST)

**Message format:**
```json
// Send a message
{"type": "message", "message": "Great progress everyone!"}

// Typing indicator
{"type": "typing", "is_typing": true}

// Receive message (with sender info)
{"type": "message", "message": {"id": "uuid", "content": "Great progress!", "sender_id": "uuid", "sender_name": "Jane", "created_at": "..."}}

// Call started notification
{"type": "call_started", "call": {"id": "uuid", "initiator": "uuid", "call_type": "voice", "agora_channel": "circle_xxx"}}
```

## Agora Integration

Circle voice/video calls are powered by [Agora.io](https://www.agora.io/) RTC.

**Token generation:** When a user starts or joins a call, the server generates a short-lived Agora RTC token scoped to the call's channel name and the user's UID.

**Call lifecycle:**
1. **Start** (`POST /call/start/`) — Creates `CircleCall`, generates Agora channel name, returns RTC token, broadcasts `call_started` to WebSocket group, sends FCM push to circle members
2. **Join** (`POST /call/join/`) — Creates `CircleCallParticipant`, generates RTC token for the joiner
3. **Leave** (`POST /call/leave/`) — Sets `left_at` on participant record
4. **End** (`POST /call/end/`) — Sets call status to `completed`, calculates duration, updates `max_participants`

**Environment variables:**

| Variable | Description |
|----------|-------------|
| `AGORA_APP_ID` | Agora project App ID |
| `AGORA_APP_CERTIFICATE` | Agora project App Certificate (for token generation) |

**FCM push:** When a call starts, a push notification is sent to all circle members via Firebase Cloud Messaging, allowing them to join even if they are not connected to the WebSocket.

## Admin

All four models are registered with Django admin:

- **CircleAdmin** - Shows `member_count`. Includes `CircleMembershipInline`, `CircleChallengeInline`, and `CirclePostInline`. Filter by category, visibility, creation date
- **CircleMembershipAdmin** - Filter by role. Search by user email, circle name
- **CirclePostAdmin** - Shows `content_preview` (truncated to 80 chars). Search by content, author
- **CircleChallengeAdmin** - Shows `participant_count`. Filter by status. Uses `filter_horizontal` for participants
