# Chat App

Friend/buddy chat and voice/video call functionality for Stepora. AI coaching conversations are handled separately by `apps.ai`.

## Models

| Model | Table | Description |
|-------|-------|-------------|
| `ChatConversation` | `chat_conversations` | Friend/buddy chat conversation (encrypted title, links to BuddyPairing) |
| `ChatMessage` | `chat_messages` | Individual message (encrypted content, supports text/voice/image, pinning, likes) |
| `Call` | `calls` | Voice/video call record (Agora.io integration, status tracking) |

## API Endpoints

All endpoints require authentication.

### Chat Conversations

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/chat/` | List conversations |
| POST | `/api/chat/start/` | Start new conversation with a user |
| GET | `/api/chat/{id}/` | Get conversation details |
| DELETE | `/api/chat/{id}/` | Delete conversation |
| POST | `/api/chat/{id}/send-message/` | Send a message |
| GET | `/api/chat/{id}/messages/` | List messages (paginated) |
| POST | `/api/chat/{id}/pin-message/{msg_id}/` | Pin/unpin a message |
| POST | `/api/chat/{id}/like-message/{msg_id}/` | Like/unlike a message |
| POST | `/api/chat/{id}/mark-read/` | Mark conversation as read |

### Calls (Agora.io)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/chat/calls/initiate/` | Initiate a call |
| POST | `/api/chat/calls/{id}/accept/` | Accept incoming call |
| POST | `/api/chat/calls/{id}/reject/` | Reject incoming call |
| POST | `/api/chat/calls/{id}/end/` | End active call |
| POST | `/api/chat/calls/{id}/cancel/` | Cancel outgoing call |
| GET | `/api/chat/calls/{id}/status/` | Get call status |
| GET | `/api/chat/calls/incoming/` | List incoming calls |
| GET | `/api/chat/calls/history/` | Call history |

### Agora.io Tokens

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/chat/agora/config/` | Agora configuration |
| POST | `/api/chat/agora/rtc-token/` | Generate RTC token for video/voice |
| POST | `/api/chat/agora/rtm-token/` | Generate RTM token for messaging |

## WebSocket

- `ws/chat/{conversation_id}/` -- Real-time chat messaging via Django Channels

## Security

- IDOR protection: users can only access their own conversations
- Encrypted at rest: message content, conversation titles (EncryptedTextField/EncryptedCharField)
- Call participants validated against friendship/buddy pairing
- Rate limiting on message sending

## Tests

469 tests (shared with AI app) across 6 test files:
- `test_unit.py` -- Model and serializer unit tests
- `test_integration.py` -- Full API endpoint tests
- `test_chat_views_extra.py` -- Extended view coverage
- `test_chat_complete.py` -- Comprehensive coverage supplement
- `test_consumers.py` -- WebSocket consumer tests
- `test_chat_consumers.py` -- Extended consumer tests

Run: `TEST_DB_NAME=test_chat pytest apps/chat/tests/ -o "addopts=" -q`
