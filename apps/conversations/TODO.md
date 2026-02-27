# TODO - Conversations App

## Completed

- [x] Models: Conversation, Message, ConversationSummary
- [x] REST API endpoints
- [x] WebSocket consumer with streaming
- [x] GPT-4 integration
- [x] Dynamic system prompts by type
- [x] Rate limiting by tier
- [x] Unit and WebSocket tests
- [x] Conversation context management

## Recently Completed

- [x] Add @extend_schema decorators for Swagger
- [x] Implement WebSocket Token authentication
- [x] XSS sanitization of message content
- [x] **Automatic summarization** - Summarize long conversations (Celery task)
- [x] **Export conversations** - Export as PDF/JSON
- [x] **Conversation templates** - Pre-defined coaching templates (model + viewset)
- [x] **Voice messages** - Audio support with Whisper (send-voice endpoint)
- [x] **Image analysis** - Analyze images with GPT-4V (send-image endpoint)
- [x] **Consumer refactor to AIChatConsumer** - Renamed ChatConsumer to AIChatConsumer for clarity; AI chat URL changed to `ws/ai-chat/` (old URL preserved as deprecated alias)
- [x] **Shared mixins extraction** - Extracted `RateLimitMixin`, `AuthenticatedConsumerMixin`, `BlockingMixin`, `ModerationMixin` into `core/consumers.py` for reuse across all chat consumers
- [x] **Buddy chat moved out** - BuddyChatConsumer moved to `apps/buddies/consumers.py` with its own routing module

## Planned - High Priority

- [ ] **Function calling** - Allow AI to create tasks directly
- [ ] **Context window management** - Intelligent context management
- [ ] **Retry logic** - OpenAI error handling with retry

## Planned - Low Priority

- [ ] **Multi-language** - Dynamic multilingual support
- [ ] **Sentiment analysis** - Detect user mood
- [ ] **Proactive messaging** - AI initiates conversations

## Known Bugs

- [ ] WebSocket can lose connection without automatic reconnection
- [ ] Streaming can stall on very long responses
- [ ] Tokens are not counted precisely for rate limiting

## Technical Debt

- [ ] Refactor the consumer into smaller classes
- [ ] Add type hints
- [ ] Implement circuit breaker for OpenAI
- [ ] Centralize prompt management
- [ ] Add load tests for WebSocket

## Performance Optimizations

- [ ] Redis cache for system prompts
- [ ] Message pagination (currently limited to 20)
- [ ] Archive message compression
- [ ] Connection pooling for WebSocket
