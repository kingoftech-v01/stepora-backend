# Buddies App - TODO

## Completed

- [x] **Buddy request acceptance flow** - Two-step pairing process: the initiator sends a buddy request (status: `pending`), and the partner must accept before the pairing becomes `active`. Accept/reject endpoints implemented.

- [x] **Buddy chat** - Real-time messaging channel between paired buddies (BuddyChatConsumer WebSocket). Integrated with existing WebSocket infrastructure.

- [x] **Pairing history** - Endpoint to retrieve a user's past buddy pairings (completed and cancelled), including partner info, duration, compatibility score, and encouragement count.

- [x] **Check-in reminders** - Automated reminder notifications to encourage buddies to check in with each other. Celery beat task schedules periodic reminders (e.g., every 3 days if no encouragement has been sent).

- [x] **Encouragement streak tracking** - Tracks consecutive days where at least one encouragement was exchanged between buddies. Displays the current and best encouragement streak in the pairing detail response.

- [x] **Own consumer and routing** - BuddyChatConsumer moved from conversations app to `apps/buddies/consumers.py` with dedicated routing in `apps/buddies/routing.py`. URL parameter changed from `conversation_id` to `pairing_id`.

- [x] **FCM push notifications** - Firebase Cloud Messaging push to offline buddy partner when a message is sent via WebSocket.

- [x] **Block enforcement** - Bidirectional block check on connect and re-check on every message send via `BlockingMixin`.

- [x] **Mark read** - `mark_read` message type updates `MessageReadStatus` for read receipts.

- [x] **Call broadcast** - `call_started` WebSocket event broadcast to `buddy_chat_{pairing_id}` group when a buddy call is initiated via REST.

## Planned Improvements

- [ ] **Improved matching algorithm** - Enhance compatibility scoring with additional signals: shared dream categories, similar goal timelines, timezone compatibility, and preferred check-in frequency.

- [ ] **Buddy suggestions list** - Instead of returning a single best match, return a ranked list of top 3-5 matches so users can choose their preferred buddy partner.

- [ ] **Mutual pairing completion** - Add a `completed` status transition that requires both users to agree the pairing was successful, rather than only allowing `cancelled` as the end state.

- [ ] **Buddy activity feed** - Create a dedicated feed showing only the paired buddy's recent activity (tasks completed, dreams progressed, milestones reached) for easy at-a-glance accountability.

- [ ] **Rate limiting on encouragements** - Add a cooldown period between encouragement messages to prevent spam (e.g., max 5 encouragements per day per pairing).
