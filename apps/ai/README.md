# AI Coaching App (`apps/ai`)

The AI Coaching module provides GPT-powered conversational coaching for Stepora users. It supports real-time streaming via WebSocket, voice messages (Whisper), image analysis (GPT-4V), conversation branching, persistent cross-conversation memory, and automatic summarization.

## Architecture

```
apps/ai/
  models.py         6 models: AIConversation, AIMessage, ConversationBranch,
                     ConversationSummary, ConversationTemplate, ChatMemory
  views.py          4 ViewSets: AIConversationViewSet (full CRUD + 15 actions),
                     AIMessageViewSet (read-only), ConversationTemplateViewSet
                     (read-only), ChatMemoryViewSet (list/delete/clear)
  serializers.py    10 serializers covering all models + search + create
  consumers.py      AIChatConsumer: WebSocket consumer for real-time streaming
  tasks.py          3 Celery tasks: transcribe_voice_message,
                     summarize_conversation, extract_chat_memories
  urls.py           DRF router under /api/ai/
  routing.py        WebSocket routes: /ws/ai-chat/{id}/ and /ws/conversations/{id}/
  admin.py          Django admin with inlines for all models
  tests/            5 test files, 190+ tests
```

## Data Model

### AIConversation
Top-level conversation session. Linked to a user and optionally to a Dream.
- `conversation_type`: one of `dream_creation`, `planning`, `check_in`, `adjustment`, `general`, `motivation`, `rescue`
- `title`: encrypted at rest (EncryptedCharField)
- Tracks `total_messages` and `total_tokens_used`

### AIMessage
Individual messages within a conversation.
- `content`: encrypted at rest (EncryptedTextField)
- Voice support: `audio_url`, `audio_duration`, `transcription` (encrypted)
- Image support: `image_url`
- Interaction: `is_pinned`, `is_liked`, `reactions` (JSONField)
- Optional `branch` FK for conversation branching

### ConversationBranch
Allows "what if" exploration by branching from any message. Context messages are copied to the branch at creation time.

### ConversationSummary
AI-generated summaries of conversation segments (triggered every 20 messages). Prepended to API context window for long-running conversations.

### ConversationTemplate
Admin-managed templates with system prompts and starter messages for different coaching scenarios.

### ChatMemory
Persistent user memories extracted from conversations (e.g., preferences, facts, goals). Capped at 50 active memories per user. Injected into every AI conversation context.

## API Endpoints

### Conversations (`/api/ai/conversations/`)
| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | List user's conversations (filterable by type, is_active) |
| POST | `/` | Create conversation (requires CanUseAI for premium+) |
| GET | `/{id}/` | Retrieve with latest 50 messages |
| PATCH | `/{id}/` | Update title, pin status |
| DELETE | `/{id}/` | Delete conversation |
| POST | `/{id}/send_message/` | Send text, get AI response (moderated, quota-checked) |
| POST | `/{id}/send-voice/` | Upload audio, queue Whisper transcription |
| POST | `/{id}/send-image/` | Upload image, get GPT-4V analysis |
| POST | `/{id}/summarize-voice/{msg_id}/` | Summarize a voice message |
| GET | `/{id}/messages/` | Paginated messages |
| POST | `/{id}/pin/` | Toggle conversation pin |
| POST | `/{id}/pin-message/{msg_id}/` | Toggle message pin |
| POST | `/{id}/like-message/{msg_id}/` | Toggle message like |
| POST | `/{id}/react-message/{msg_id}/` | Add/remove emoji reaction |
| GET | `/{id}/search/?q=` | Search messages (min 2 chars) |
| GET | `/{id}/export/?format=json|pdf` | Export conversation |
| POST | `/{id}/archive/` | Archive (set is_active=False) |

### Branches
| Method | Path | Description |
|--------|------|-------------|
| POST | `/{id}/branch/` | Create branch from message |
| GET | `/{id}/branches/` | List branches |
| POST | `/{id}/branch/{branch_id}/send/` | Send message in branch |
| GET | `/{id}/branch/{branch_id}/messages/` | Get branch messages |

### Templates (`/api/ai/templates/`)
Read-only. Lists active templates with system prompts and starter messages.

### Memories (`/api/ai/memories/`)
| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | List active memories |
| DELETE | `/{id}/` | Deactivate a memory |
| POST | `/clear/` | Deactivate all memories |

### Messages (`/api/ai/messages/`)
Read-only viewset. Lists all messages across the user's conversations.

## WebSocket (`/ws/ai-chat/{conversation_id}/`)

Protocol:
1. Connect (JWT in scope or post-connect authenticate)
2. Send: `{"type": "message", "message": "..."}`
3. Receive: `stream_start` -> `stream_chunk` (multiple) -> `stream_end` -> `message` (final)
4. Other types: `ping`/`pong`, `typing`, `function_call`
5. Error types: `error`, `quota_exceeded`, `moderation`

## Celery Tasks

| Task | Trigger | Description |
|------|---------|-------------|
| `transcribe_voice_message` | After voice upload | Downloads audio, transcribes via Whisper, auto-summarizes |
| `summarize_conversation` | Every 20th message | Summarizes message range, stores as ConversationSummary |
| `extract_chat_memories` | Every 5th user message | Extracts facts/preferences, caps at 50 active per user |

## Security

- **IDOR Protection**: All querysets filtered by `request.user`. `perform_update` and `perform_destroy` verify ownership.
- **Content Moderation**: User messages checked via `ContentModerationService` before saving or calling AI.
- **AI Output Safety**: Assistant responses validated via `validate_ai_output_safety`; unsafe responses replaced with fallback.
- **Rate Limiting**: `AIRateThrottle`, `AIChatDailyThrottle`, `AIVoiceDailyThrottle` on write endpoints.
- **Quota Enforcement**: `AIUsageTracker` (Redis counters) enforces per-plan daily limits for ai_chat, ai_voice, ai_background.
- **Encryption at Rest**: All message content, transcriptions, and memories use `EncryptedTextField`/`EncryptedCharField`.
- **SSRF Prevention**: Audio/image URLs validated via `validate_url_no_ssrf` with DNS-pinned connections.
- **Input Sanitization**: Message content sanitized via `core.sanitizers.sanitize_text`.
- **File Validation**: Audio magic bytes checked; filenames sanitized to prevent path traversal.
- **Permission**: `CanUseAI` permission class blocks free-tier users from AI write actions.

## AI Context Building (`get_messages_for_api`)

The context sent to OpenAI is built in layers:
1. **Memory context** (cross-conversation recall from ChatMemory)
2. **Dream context** (if conversation linked to a dream: title, description, goals, calibration profile)
3. **Conversation summary** (latest ConversationSummary, if available)
4. **Recent messages** (last N, with optional token-based trimming via tiktoken)

## Test Coverage

```
tests/
  conftest.py              Shared fixtures (premium user, conversations, messages)
  test_unit.py             40 tests: model CRUD, defaults, ordering, serializer validation
  test_integration.py      57 tests: API endpoints (CRUD, send, voice, image, branches, search, export)
  test_comprehensive.py    69 tests: IDOR, quota, memory CRUD, tasks, model methods, serializer edges
  test_ai_consumers.py     24 tests: WebSocket lifecycle, streaming, auth, errors, moderation
  test_consumers.py         4 tests: Consumer class existence checks
```

Run tests: `python3 -m pytest apps/ai/tests/ -o "addopts=" --reuse-db`

## Frontend Integration

The frontend (`/root/stepora-frontend`) has full AI chat support:
- `src/pages/chat/AIChatScreen/` — Chat UI (Mobile/Tablet/Desktop variants)
- `src/pages/chat/AIChatListScreen/` — Conversation list with type filters
- `src/services/endpoints.js` — `AI_CHAT` object with all endpoint URLs
- WebSocket streaming via `createWebSocket(WS.AI_CHAT(id))`
- Branch management, voice summarization, pin/like/react interactions
