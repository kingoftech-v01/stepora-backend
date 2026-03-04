# Core Module — TODO

Feature ideas and improvements for the shared core module (auth, permissions, middleware, validators, consumers).

---

## Authentication

- [ ] **Passkey/WebAuthn support** — Add passwordless login via FIDO2/WebAuthn for modern browsers and native apps
- [ ] **Session management dashboard** — Endpoint to list active sessions (device, IP, last activity) with remote revocation
- [ ] **Login history** — Track login attempts (success/failure) with device fingerprint, IP, and geolocation for security audit
- [ ] **Magic link login** — Email-based passwordless login as alternative to password (especially useful for low-friction onboarding)
- [ ] **JWT key rotation** — Implement signing key rotation with grace period for old tokens

## Permissions

- [ ] **Feature flags** — Integrate django-waffle or custom feature flag system for gradual rollouts
- [ ] **Fine-grained permissions** — Per-resource permission grants (e.g., "user X can edit dream Y") beyond owner/subscription checks
- [ ] **Permission caching** — Cache subscription tier checks to avoid DB hit on every request
- [ ] **Rate limit by subscription tier** — Higher rate limits for premium/pro users (e.g., AI chat: free=5/min, premium=20/min, pro=unlimited)

## Middleware

- [ ] **Request ID tracing** — Add unique request ID header for distributed tracing across services
- [ ] **Performance monitoring** — Middleware to log request duration, DB query count, and cache hit ratio
- [ ] **IP geolocation** — Middleware to attach country/region info for analytics and content localization
- [ ] **Maintenance mode** — Middleware to return 503 with maintenance page during deployments

## Validators

- [ ] **Content moderation queue** — Instead of hard-blocking flagged content, add a moderation queue for human review
- [ ] **Custom profanity filter** — App-specific word blocklist beyond OpenAI moderation (support multiple languages)
- [ ] **AI-powered spam detection** — Classify user-generated content (posts, comments) as spam/ham using lightweight model
- [ ] **Image NSFW detection** — Add image content moderation for avatar uploads and vision board images

## Consumer Mixins

- [ ] **WebSocket analytics** — Track message volume, latency, and connection duration per consumer
- [ ] **Connection limits** — Per-user WebSocket connection limit (prevent tab spam)
- [ ] **Graceful shutdown** — Send "server shutting down" message before closing WebSocket connections during deploy
- [ ] **Binary message support** — Support binary WebSocket frames for voice data streaming (reduce base64 overhead)
