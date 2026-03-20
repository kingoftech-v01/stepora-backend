# Standalone Chat App + NotificationService + BuddyMatchingService Refactor

## Scope

### 1. Chat App Enhancements
- Add `send-voice/` endpoint for voice message uploads (with audio_url, audio_duration)
- Add `search/` endpoint for message search within a conversation
- Add `summarize-voice/` endpoint placeholder (returns 501 without AI integration)
- Add `FriendChatConsumer` WebSocket for direct friend-to-friend messaging (not just buddy pairings)
- Celery tasks for: missed message notifications, stale conversation cleanup

### 2. NotificationService Centralization
- Replace all direct `Notification.objects.create(...)` calls with `NotificationService.create(...)` in:
  - `apps/buddies/views.py` (5 occurrences)
  - `apps/buddies/tasks.py` (1 occurrence)
- Add `ReminderPreference` model for user-specific notification scheduling
- Add new notification types: `buddy_request`, `chat_message`
- Add `notification_type` to `NotificationService.create` calls that were missing it

### 3. BuddyMatchingService Refactor
- Add `BuddySkip` model for tracking skipped suggestions
- Add `BuddySuggestionSerializer` for queue endpoint
- Add `suggestions/` endpoint (Tinder-style matching queue)
- Add `accept-suggestion/` and `skip-suggestion/` endpoints
- Enhanced `_compute_compatibility_score()` with language + activity metrics
- Exclude skipped and blocked users from suggestions

### 4. FriendChatScreen Bug Fixes
- Ensure FRIEND_CHAT endpoints include `SEND_VOICE`, `SEARCH`, `SUMMARIZE_VOICE`
- Voice message upload support in useFriendChatScreen hook (already present)

## API Endpoints

### Chat (new)
- `POST /api/chat/<id>/send-voice/` - Upload voice message
- `GET /api/chat/<id>/search/?q=<query>` - Search messages
- `POST /api/chat/<id>/summarize-voice/<msg_id>/` - Summarize voice (placeholder)

### Buddies (new)
- `GET /api/buddies/buddies/suggestions/` - Get suggestion queue
- `POST /api/buddies/buddies/<id>/accept-suggestion/` - Accept suggestion
- `POST /api/buddies/buddies/<id>/skip-suggestion/` - Skip suggestion

### Notifications (enhanced)
- Notification types expanded: `buddy_request`, `chat_message`

## Models

### New: BuddySkip
- `user` FK -> User
- `skipped_user` FK -> User
- `created_at` DateTimeField
- Unique constraint on (user, skipped_user)

### New: ReminderPreference
- `user` FK -> User (OneToOne)
- `preferred_time` TimeField
- `timezone` CharField
- `enabled` BooleanField

## Testing Strategy
- Unit tests for models, serializers, services
- Integration tests for API endpoints
- All tests use pytest + DRF APIClient
