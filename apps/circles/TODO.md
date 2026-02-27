# Circles App - TODO

## Completed

- [x] **Circle edit and delete** - PUT/PATCH and DELETE endpoints for circles. Only admins can edit circle details (name, description, category, visibility) or delete the entire circle. Deleting a circle cascade-deletes memberships, posts, and challenges.

- [x] **Invitation system** - Invite mechanism for private circles. Admins/moderators can generate invite codes or send direct invitations to users (CircleInvitation model). Tracks pending invitations with accept/reject flow.

- [x] **Moderator management** - Endpoints to promote members to moderator, demote moderators to member. Moderators can delete posts and remove members.

- [x] **Post editing and deletion** - Post authors can edit or delete their own posts. Moderators and admins can delete any post.

- [x] **Post reactions** - Reaction system for circle posts (PostReaction model). Tracks reactions per post per user to prevent duplicates. Returns reaction counts in the post serializer.

- [x] **Challenge progress tracking** - Individual participant progress within challenges (ChallengeProgress model). Progress update endpoint where participants can log their daily/weekly progress. Progress leaderboards within challenges.

- [x] **Group chat** - CircleMessage model with encrypted content. CircleChatConsumer WebSocket consumer at `ws/circle-chat/{circle_id}/` with rate limiting (20/60s), content moderation, and block filtering. REST endpoints: `POST /chat/send/`, `GET /chat/history/`.

- [x] **Agora voice/video calls** - CircleCall and CircleCallParticipant models. REST endpoints for call lifecycle: `start`, `join`, `leave`, `end`, `active`. Agora RTC token generation per user/channel.

- [x] **RTC token generation** - Short-lived Agora tokens scoped to call channel and user UID via `AGORA_APP_ID` and `AGORA_APP_CERTIFICATE` environment variables.

- [x] **Block filtering** - CircleChatConsumer loads blocked user IDs at connection time and silently drops incoming messages from blocked senders.

- [x] **FCM call notifications** - Firebase Cloud Messaging push sent to all circle members when a call starts, enabling join even when not connected to WebSocket.

- [x] **REST chat endpoints** - `POST /circles/{id}/chat/send/` (broadcasts to WebSocket group) and `GET /circles/{id}/chat/history/` (paginated message history).

## Planned Improvements

- [ ] **Circle search** - Add a search endpoint for discovering circles by name or description text, with category and membership size filters.

- [ ] **Circle activity stats** - Track and expose circle activity metrics: posts per day, active members, challenge participation rate. Use these for the "recommended" filter algorithm.

- [ ] **Pin posts** - Allow admins/moderators to pin important posts to the top of the feed.

- [ ] **Challenge creation endpoint** - Add a POST endpoint for admins/moderators to create challenges via the API rather than only through the admin panel.

- [ ] **Member activity indicators** - Show when members were last active in the circle (last post date, last visit) to help identify inactive members.
