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

## Planned - High Priority

- [ ] **Function calling** - Allow AI to create tasks directly
- [ ] **Automatic summarization** - Summarize long conversations
- [ ] **Context window management** - Intelligent context management
- [ ] **Retry logic** - OpenAI error handling with retry

## Planned - Medium Priority

- [ ] **Voice messages** - Audio support with Whisper
- [ ] **Image analysis** - Analyze images with GPT-4V
- [ ] **Export conversations** - Export as PDF/JSON
- [ ] **Conversation templates** - Pre-defined coaching templates

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
