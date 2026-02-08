# Conversations App

Django application for real-time AI chat with WebSocket.

## Overview

The Conversations app manages interactions between the user and the AI coach:
- **Conversation** - Chat session with context
- **Message** - Individual message (user/assistant/system)
- **ConversationSummary** - Summary for long-term context

## Models

### Conversation

| Field | Type | Description |
|-------|------|-------------|
| id | UUID | Unique identifier |
| user | FK(User) | Owner |
| dream | FK(Dream) | Associated dream (optional) |
| conversation_type | CharField | Conversation type |
| total_messages | Integer | Total number of messages |
| total_tokens_used | Integer | OpenAI tokens used |
| is_active | Boolean | Active conversation |

**Conversation types:**
- `dream_creation` - Guided dream creation
- `planning` - Goal planning
- `check_in` - Progress check-in
- `adjustment` - Plan adjustment
- `general` - General discussion
- `motivation` - Motivation boost
- `rescue` - Rescue mode (user struggling)

### Message

| Field | Type | Description |
|-------|------|-------------|
| id | UUID | Unique identifier |
| conversation | FK(Conversation) | Parent conversation |
| role | CharField | user, assistant, system |
| content | TextField | Message content |
| metadata | JSONField | Tokens used, model, etc. |

### ConversationSummary

| Field | Type | Description |
|-------|------|-------------|
| id | UUID | Unique identifier |
| conversation | FK(Conversation) | Conversation |
| summary | TextField | Text summary |
| key_points | JSONField | Extracted key points |
| start_message | FK(Message) | First message covered |
| end_message | FK(Message) | Last message covered |

## API Endpoints

### REST API
- `GET /api/conversations/` - List conversations
- `POST /api/conversations/` - Create a conversation
- `GET /api/conversations/{id}/` - Detail with messages
- `DELETE /api/conversations/{id}/` - Delete
- `GET /api/conversations/{id}/messages/` - List messages
- `POST /api/conversations/{id}/messages/` - Send a message (non-streaming)

### WebSocket
- `ws://host/ws/conversations/{id}/` - Real-time chat

**WebSocket actions:**
```json
// Send a message
{"type": "message", "content": "Hello!"}

// Receive a response (streaming)
{"type": "assistant_start"}
{"type": "assistant_chunk", "content": "Hel"}
{"type": "assistant_chunk", "content": "lo"}
{"type": "assistant_end", "message_id": "uuid"}

// Typing indicator
{"type": "typing", "is_typing": true}
```

## Serializers

- `ConversationSerializer` - With recent messages
- `ConversationListSerializer` - Lightweight version
- `MessageSerializer` - Full message

## WebSocket Consumer

The `ChatConsumer` handles:
1. Authentication via DRF Token (query param for WebSocket, header for REST)
2. Receiving user messages
3. Streaming GPT-4 responses
4. Typing indicators
5. Error handling

## OpenAI Integration

**Model used:** GPT-4 Turbo (configurable)

**Dynamic system prompt by type:**
- `dream_creation`: Guides dream creation
- `planning`: Helps plan steps
- `motivation`: Encourages and motivates
- `rescue`: Empathetic mode for struggling users

## Rate Limiting

Conversations are subject to rate limiting:
- **Free**: 10 messages/hour
- **Premium**: 100 messages/hour
- **Pro**: 1000 messages/hour

## Testing

```bash
# Unit tests
python manage.py test apps.conversations

# WebSocket tests
pytest apps/conversations/tests.py -v -k websocket
```

## Configuration

Environment variables:
- `OPENAI_API_KEY` - OpenAI API key
- `OPENAI_MODEL` - Model (default: gpt-4-turbo-preview)
- `OPENAI_TIMEOUT` - Timeout in seconds (default: 30)

## WebSocket Routing

```python
# routing.py
websocket_urlpatterns = [
    re_path(r'ws/conversations/(?P<conversation_id>[^/]+)/$', ChatConsumer.as_asgi()),
]
```

## Dependencies

- `channels` - WebSocket support
- `channels-redis` - Redis channel layer
- `openai` - OpenAI API
