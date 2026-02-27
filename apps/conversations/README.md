# Conversations App

Django application for AI-powered chat conversations with WebSocket streaming, voice transcription, and image analysis.

## Overview

The Conversations app manages interactions between the user and the AI coach:
- **Conversation** - Chat session linked to a dream or buddy pairing, with type-based AI behavior
- **Message** - Individual message (user/assistant/system) with voice, image, pin, like, and reaction support
- **ConversationSummary** - Automatic summaries for long-term context preservation
- **ConversationTemplate** - Pre-built templates for common coaching scenarios

## Models

### Conversation

AI conversation session, also used for buddy-to-buddy chat.

| Field | Type | Description |
|-------|------|-------------|
| id | UUID | Primary key |
| user | FK(User) | Conversation owner (related_name: `conversations`) |
| dream | FK(Dream) | Associated dream (nullable, related_name: `conversations`) |
| buddy_pairing | FK(BuddyPairing) | Associated buddy pairing for buddy chat (nullable, related_name: `conversations`) |
| conversation_type | CharField(20) | Conversation type (see choices below, default: `general`) |
| title | CharField(255) | Optional conversation title |
| is_pinned | BooleanField | Whether this conversation is pinned (default: False) |
| total_messages | IntegerField | Total number of messages (default: 0) |
| total_tokens_used | IntegerField | OpenAI tokens consumed (default: 0) |
| is_active | BooleanField | Whether conversation is active (default: True) |
| created_at | DateTimeField | Auto-set on creation |
| updated_at | DateTimeField | Auto-set on update |

**DB table:** `conversations`

**Conversation types:**

| Type | Display Name | Description |
|------|-------------|-------------|
| `dream_creation` | Dream Creation | Guided dream creation |
| `planning` | Planning | Goal planning |
| `check_in` | Check In | Progress check-in |
| `adjustment` | Adjustment | Plan adjustment |
| `general` | General | General discussion |
| `motivation` | Motivation | Motivation boost |
| `rescue` | Rescue | Rescue mode (user struggling) |
| `buddy_chat` | Buddy Chat | Real-time buddy-to-buddy chat (no AI) |

**Methods:**
- `add_message(role, content, metadata=None)` - Add a message, increment counters, save
- `get_messages_for_api(limit=20, max_tokens=None)` - Get recent messages formatted for OpenAI API, with dream context injection and token-based trimming

### Message

Individual message in a conversation.

| Field | Type | Description |
|-------|------|-------------|
| id | UUID | Primary key |
| conversation | FK(Conversation) | Parent conversation (related_name: `messages`) |
| role | CharField(10) | `user`, `assistant`, or `system` |
| content | TextField | Message text content |
| audio_url | URLField(500) | URL to uploaded audio file for voice messages |
| transcription | TextField | Whisper transcription of audio message |
| image_url | URLField(500) | URL to uploaded image for GPT-4 Vision analysis |
| is_pinned | BooleanField | Whether message is pinned (default: False) |
| is_liked | BooleanField | Whether message is liked (default: False) |
| reactions | JSONField | List of reaction emojis (default: []) |
| metadata | JSONField | Tokens used, model version, etc. (default: {}) |
| created_at | DateTimeField | Auto-set on creation |

**DB table:** `messages`

### ConversationSummary

Summarized conversation segment for long-term context.

| Field | Type | Description |
|-------|------|-------------|
| id | UUID | Primary key |
| conversation | FK(Conversation) | Parent conversation (related_name: `summaries`) |
| summary | TextField | Text summary |
| key_points | JSONField | Extracted key points (default: []) |
| start_message | FK(Message) | First message covered (related_name: `summary_starts`) |
| end_message | FK(Message) | Last message covered (related_name: `summary_ends`) |
| created_at | DateTimeField | Auto-set on creation |

**DB table:** `conversation_summaries`

### ConversationTemplate

Pre-built conversation templates for common AI coaching scenarios.

| Field | Type | Description |
|-------|------|-------------|
| id | UUID | Primary key |
| name | CharField(200) | Template name |
| conversation_type | CharField(20) | Type of conversation this template creates |
| system_prompt | TextField | Custom system prompt for this template |
| starter_messages | JSONField | List of starter message dicts: `[{"role": "assistant", "content": "..."}]` |
| description | TextField | Description shown to users when browsing templates |
| icon | CharField(50) | Emoji or icon identifier for the template |
| is_active | BooleanField | Whether template is available (default: True) |
| created_at | DateTimeField | Auto-set on creation |
| updated_at | DateTimeField | Auto-set on update |

**DB table:** `conversation_templates`

## API Endpoints

### Conversations

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | List conversations for current user (filterable by `conversation_type`, `is_active`) |
| POST | `/` | Create a new conversation (body: `conversation_type`, optional `dream`) |
| GET | `/{id}/` | Get conversation detail with all messages |
| PUT | `/{id}/` | Update a conversation |
| PATCH | `/{id}/` | Partial update |
| DELETE | `/{id}/` | Delete a conversation |
| POST | `/{id}/send_message/` | Send a text message and get AI response |
| POST | `/{id}/send-voice/` | Upload audio file for Whisper transcription (max 25MB) |
| POST | `/{id}/send-image/` | Upload image for GPT-4 Vision analysis (max 20MB) |
| GET | `/{id}/messages/` | List messages with pagination |
| POST | `/{id}/pin/` | Toggle pin on conversation |
| POST | `/{id}/pin-message/{message_id}/` | Toggle pin on a message |
| POST | `/{id}/like-message/{message_id}/` | Toggle like on a message |
| POST | `/{id}/react-message/{message_id}/` | Add/remove reaction emoji (body: `{"emoji": "..."}`) |
| GET | `/{id}/search/?q={query}` | Search messages within conversation (min 2 chars, max 50 results) |
| GET | `/{id}/export/?format={json\|pdf}` | Export conversation as JSON or PDF |

**ViewSet:** `ConversationViewSet` (ModelViewSet)
- Permission: `IsAuthenticated`, `CanUseAI`

#### Endpoint Details

##### POST /{id}/send_message/

Sends a user message and returns the AI response. Flow:
1. Content moderation check (blocks flagged content)
2. Save user message
3. Build API context (dream context + summary + recent messages)
4. Get AI response via OpenAI
5. Validate response (`validate_chat_response`, `validate_ai_output_safety`)
6. Save assistant message
7. Trigger auto-summarization every 20 messages

##### POST /{id}/send-voice/

Upload an audio file (mp3, m4a, wav, webm, ogg). The message is saved immediately with `[Voice message]` content, and transcription is queued via Celery (`transcribe_voice_message`).

##### POST /{id}/send-image/

Upload an image with an optional text prompt. The image is analyzed via GPT-4 Vision, and both the user message and AI analysis are returned.

### Messages

| Method | Path | Description |
|--------|------|-------------|
| GET | `/messages/` | List all messages for current user's conversations |
| GET | `/messages/{id}/` | Get a specific message |

**ViewSet:** `MessageViewSet` (ReadOnlyModelViewSet)
- Permission: `IsAuthenticated`

### Conversation Templates

| Method | Path | Description |
|--------|------|-------------|
| GET | `/conversation-templates/` | List all active templates |
| GET | `/conversation-templates/{id}/` | Get template detail |

**ViewSet:** `ConversationTemplateViewSet` (ReadOnlyModelViewSet)
- Permission: `IsAuthenticated`

## Serializers

| Serializer | Purpose |
|------------|---------|
| `ConversationSerializer` | Conversation with `dream_title` and `last_message` (truncated to 100 chars) |
| `ConversationDetailSerializer` | Full conversation with nested `messages` list |
| `ConversationCreateSerializer` | Input: `conversation_type`, optional `dream`. Validates dream-related types require a dream |
| `MessageSerializer` | Full message with `audio_url`, `transcription`, `image_url`, `is_pinned`, `is_liked`, `reactions` |
| `MessageCreateSerializer` | Input: `content` (max 5000 chars, sanitized) |
| `ConversationSummarySerializer` | Summary with `key_points`, `start_message`, `end_message` |
| `ConversationTemplateSerializer` | Template with `icon`, `starter_messages`, `description` |

## WebSocket Consumer

### AIChatConsumer (formerly ChatConsumer)

Real-time AI-powered chat via WebSocket with streaming responses. Defined in `apps/conversations/consumers.py`.

**URL:** `ws://host/ws/ai-chat/{conversation_id}/`
**Deprecated alias:** `ws://host/ws/conversations/{conversation_id}/` (still functional, will be removed in a future version)

**Routing:** `apps/conversations/routing.py`

**Channel group:** `ai_chat_{conversation_id}`

**Authentication:** Post-connect token authentication via `AuthenticatedConsumerMixin`

**Mixins:** `RateLimitMixin`, `AuthenticatedConsumerMixin`, `ModerationMixin` (from `core.consumers`)

**Access control:** User must own the conversation. Conversations of type `buddy_chat` are rejected with close code **4004** (buddy chat conversations should use `BuddyChatConsumer` in the buddies app).

**Flow:**
1. Connection: accept → authenticate → verify conversation ownership → reject buddy_chat type → join group
2. User sends message: content moderation → save → check AI quota → stream AI response
3. AI response chunks sent in real-time with length limit (10,000 chars max)
4. AI output is sanitized and validated for safety before saving

**Message types (client → server):**
- `authenticate` — Post-connect token auth
- `message` — Send a chat message
- `function_call` — Execute an explicit function call (create_task, complete_task, create_goal)
- `typing` — Typing indicator
- `ping` — Keepalive

**Message format:**
```json
// Send a message
{"type": "message", "message": "Hello!"}

// Typing indicator
{"type": "typing", "is_typing": true}

// Receive streaming response
{"type": "stream_start"}
{"type": "stream_chunk", "chunk": "Hel"}
{"type": "stream_chunk", "chunk": "lo!"}
{"type": "stream_end"}

// Receive complete message
{"type": "message", "message": {"id": "uuid", "role": "assistant", "content": "Hello!", "created_at": "..."}}

// Moderation rejection
{"type": "moderation", "message": "Your message was flagged..."}

// Error
{"type": "error", "error": "Error message"}
```

> **Note:** Buddy-to-buddy messaging has been moved to `BuddyChatConsumer` in the `apps/buddies` app. See the [Buddies README](../buddies/README.md).

## Content Moderation & AI Safety

- **User messages** are moderated via `ContentModerationService` before saving (both REST and WebSocket)
- **AI responses** are validated via `validate_chat_response` (structure) and `validate_ai_output_safety` (content safety)
- **Function calls** from AI are validated via `validate_function_call` before execution
- Unsafe AI responses are replaced with a safe fallback message

## Celery Tasks

| Task | Retries | Description |
|------|---------|-------------|
| `transcribe_voice_message` | 3 | Downloads audio from `audio_url`, transcribes via OpenAI Whisper, saves transcription to message |
| `summarize_conversation` | 2 | Auto-triggered every 20 messages. Generates a summary of unsummarized messages using GPT-4 for long-term context |

## Management Commands

| Command | Description |
|---------|-------------|
| `seed_conversation_templates` | Seeds 6 conversation templates: Dream Planning, Daily Check-in, Motivation Boost, Obstacle Solving, Progress Review, General Chat. Idempotent (update_or_create) |

## Admin

All three models are registered with Django admin:

- **ConversationAdmin** - Shows user, type, dream, message count, token usage. Includes `MessageInline` (read-only content preview). Filter by type, active status, date. Search by user email, dream title
- **MessageAdmin** - Shows `content_preview` (truncated to 100 chars). Filter by role, date. Search by content, user email
- **ConversationSummaryAdmin** - Shows `summary_preview` (truncated to 100 chars). Filter by date. Search by summary text, user email

## OpenAI Integration

**Model used:** GPT-4 Turbo (configurable via `OPENAI_MODEL`)

**Dynamic system prompt by type:**
- `dream_creation` - Guides dream creation
- `planning` - Helps plan steps
- `motivation` - Encourages and motivates
- `rescue` - Empathetic mode for struggling users

**Dream context injection:** When a conversation is linked to a dream, the AI always receives the dream's title, description, category, status, progress, calibration profile, and top 5 goals as system context.

## Rate Limiting

Conversations are subject to rate limiting:
- **Free**: 10 messages/hour
- **Premium**: 100 messages/hour
- **Pro**: 1000 messages/hour

## Configuration

Environment variables:
- `OPENAI_API_KEY` - OpenAI API key
- `OPENAI_MODEL` - Model (default: gpt-4o-mini)
- `OPENAI_TIMEOUT` - Timeout in seconds (default: 30)

## Testing

```bash
pytest apps/conversations/tests.py -v
```

## Dependencies

- `channels` - WebSocket support
- `channels-redis` - Redis channel layer
- `openai` - OpenAI API (GPT-4, GPT-4V, Whisper)
- `reportlab` - PDF export (optional)
