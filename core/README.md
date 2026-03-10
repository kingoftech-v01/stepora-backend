# Core Module

Shared utilities, middleware, and base classes used across all Stepora backend apps.

## Overview

The `core` module provides cross-cutting infrastructure including authentication, permissions, pagination, rate limiting, input sanitization, WebSocket authentication, custom exception handling, and health check endpoints. It does not define any Django models.

## Files

| File | Description |
|------|-------------|
| `auth/` | Custom auth package: JWT via SimpleJWT, social login (Google/Apple ID token verification), email verification, password reset, 2FA challenge, async email tasks. Settings in `DP_AUTH` dict. |
| `authentication.py` | BearerTokenAuthentication (accepts Token/Bearer prefix) and CSRF exemption middleware |
| `permissions.py` | 11 subscription-based permission classes for feature gating |
| `pagination.py` | Custom DRF pagination classes |
| `sanitizers.py` | XSS sanitization utilities for user-generated content |
| `throttles.py` | Per-feature rate limiting throttle classes |
| `websocket_auth.py` | Token-based WebSocket authentication for Django Channels |
| `exceptions.py` | Custom DRF exception handler and domain exception classes |
| `ai_validators.py` | Pydantic schemas for validating AI-generated output |
| `ai_usage.py` | Redis-backed daily AI usage quota tracking per user |
| `moderation.py` | 3-tier content moderation (patterns + OpenAI API) |
| `validators.py` | Input validators (display names, UUIDs, pagination, search queries) |
| `middleware.py` | Security headers and last-activity tracking middleware |
| `audit.py` | Structured security audit logging |
| `consumers.py` | Shared WebSocket consumer mixins (rate limiting, auth, blocking, moderation) |
| `urls.py` | Health check endpoint routing |
| `views.py` | Health check view functions and social auth views |

## Authentication

### BearerTokenAuthentication

`authentication.py`

Extends DRF's `TokenAuthentication` to accept both `Token` and `Bearer` prefixes in the `Authorization` header. This allows mobile clients to use the standard `Bearer <token>` format while maintaining compatibility with DRF's default `Token <token>` format.

```
Authorization: Bearer <auth_token>
Authorization: Token <auth_token>
```

### CsrfExemptAPIMiddleware

`authentication.py`

Django middleware that skips CSRF checks for all `/api/` routes. The admin panel continues to use CSRF protection. This is necessary because API clients (mobile app, external services) use token authentication rather than cookies.

### Social Authentication Views

`core/auth/social.py` and `core/auth/views.py`

Social login endpoints verify ID tokens directly against Google/Apple servers. No allauth adapters are used.

| View | Provider | Description |
|------|----------|-------------|
| `GoogleLoginView` | Google | Verifies Google ID token directly, creates/links `SocialAccount`, returns JWT |
| `AppleLoginView` | Apple | Verifies Apple ID token directly, creates/links `SocialAccount`, returns JWT |

Both views return JWT tokens (access + refresh) on successful authentication, following the same token format as email/password login. The `core.auth.social` module handles token verification logic.

## Celery Tasks

| Task | Description |
|------|-------------|
| `send_email_change_verification` | Sends a verification email when a user requests an email address change. Generates a signed token and sends a confirmation link |
| `export_user_data` | Exports all user data (profile, dreams, conversations, calendar events, notifications) as a downloadable archive for GDPR compliance |

## Permissions

`permissions.py`

DB-driven subscription-based access control. Each permission class reads from the user's active `SubscriptionPlan` model fields via `user.get_active_plan()` (cached per-request on `_cached_plan`). Plans are configured via Django admin without code changes.

| Permission Class | Tier Required | Description |
|-----------------|--------------|-------------|
| `IsOwner` | Any authenticated | Checks `obj.user == request.user` (or `obj.user1`/`obj.user2` for pairings) |
| `IsPremiumUser` | Premium or Pro | Calls `user.is_premium()` |
| `IsProUser` | Pro only | Checks `user.get_active_plan().tier == 'pro'` |
| `CanCreateDream` | Any (limit-based) | Calls `user.can_create_dream()` on POST requests only |
| `CanUseAI` | Premium or Pro | Gates AI chat, plan generation, dream analysis, motivational AI |
| `CanUseBuddy` | Premium or Pro | Gates Dream Buddy matching |
| `CanUseCircles` | Pro (create), Premium+ (join/read) | Circle creation requires Pro; joining/reading requires Premium+ |
| `CanUseVisionBoard` | Pro only | Gates AI Vision Board generation |
| `CanUseLeague` | Premium or Pro | Gates league features |
| `CanUseStore` | Premium or Pro | Gates store purchasing |
| `CanUseSocialFeed` | Premium or Pro | Gates full social feed access |

### Feature Access Matrix

| Feature | Free | Premium | Pro |
|---------|------|---------|-----|
| Dream creation | 3 max | 10 max | Unlimited |
| AI features | No | Yes | Yes |
| Buddy matching | No | Yes | Yes |
| Circle joining | No | Yes | Yes |
| Circle creation | No | No | Yes |
| Vision boards | No | No | Yes |
| Leagues | No | Yes | Yes |

## Pagination

`pagination.py`

### StandardResultsSetPagination

Default pagination with 20 items per page. Supports `page_size` query parameter (max 100).

Response format:
```json
{
  "pagination": {
    "count": 150,
    "next": "http://example.com/api/items/?page=2",
    "previous": null,
    "page_size": 20,
    "current_page": 1,
    "total_pages": 8
  },
  "results": [...]
}
```

### LargeResultsSetPagination

Pagination for large datasets with 50 items per page (max 200).

## Sanitizers

`sanitizers.py`

XSS sanitization utilities built on the `bleach` library.

| Function | Purpose |
|----------|---------|
| `sanitize_text(text, strip=True)` | Remove all HTML tags from plain text fields (titles, names) |
| `sanitize_html(text, extra_tags=None)` | Keep only safe HTML tags (`p`, `br`, `strong`, `em`, `u`, `ul`, `ol`, `li`, `a`) |
| `sanitize_url(url)` | Validate URL scheme (http/https/mailto only) and block dangerous patterns (`javascript:`, `data:`, `vbscript:`, `<script`, event handlers) |
| `sanitize_json_values(data, keys_to_sanitize=None)` | Recursively sanitize string values in a dictionary |
| `create_sanitizing_serializer_mixin(fields)` | Factory for a serializer mixin that sanitizes specified fields in `to_internal_value` |

### Allowed HTML Tags

`p`, `br`, `strong`, `em`, `u`, `ul`, `ol`, `li`, `a`

### Allowed Attributes

`a`: `href`, `title`

### Allowed Protocols

`http`, `https`, `mailto`

## Throttling

`throttling.py`

Per-feature rate limiting using DRF's `UserRateThrottle`. Throttle scopes are configured in Django settings.

| Throttle Class | Scope | Purpose |
|---------------|-------|---------|
| `AIChatThrottle` | `ai_chat` | Rate limit AI chat messages |
| `AIPlanGenerationThrottle` | `ai_plan` | Rate limit AI plan generation requests |
| `SubscriptionThrottle` | `subscription` | Rate limit subscription management operations |
| `StorePurchaseThrottle` | `store_purchase` | Rate limit store purchase operations |

## WebSocket Authentication

`websocket_auth.py`

Token-based authentication for Django Channels WebSocket connections. Tokens are passed via query string.

### Connection Format

```
ws://host/ws/path/?token=<auth_token>
```

### Components

| Component | Description |
|-----------|-------------|
| `get_user_from_token(token_key)` | Async function that verifies a DRF token and returns the user (or `AnonymousUser`). Also calls `user.update_activity()` |
| `TokenWebSocketMiddleware` | Channels `BaseMiddleware` subclass that extracts the token from query string and sets `scope['user']` |
| `TokenWebSocketAuthMiddleware` | Alternative ASGI application wrapper with the same functionality |
| `TokenAuthMiddlewareStack(inner)` | Convenience function, drop-in replacement for `AuthMiddlewareStack` |

### Usage in asgi.py

```python
from core.websocket_auth import TokenAuthMiddlewareStack

application = ProtocolTypeRouter({
    "websocket": TokenAuthMiddlewareStack(
        URLRouter(websocket_urlpatterns)
    ),
})
```

## WebSocket Consumer Mixins

`consumers.py`

Shared mixins used by all WebSocket consumers (`AIChatConsumer`, `BuddyChatConsumer`, `CircleChatConsumer`). These provide reusable functionality for rate limiting, authentication, blocking, and content moderation.

### Constants

| Constant | Value | Description |
|----------|-------|-------------|
| `MAX_MSG_SIZE` | 8192 | Maximum raw WebSocket message size in bytes |
| `MAX_MSG_CONTENT_LEN` | 5000 | Maximum message content length |
| `DEFAULT_RATE_LIMIT_MSGS` | 30 | Default messages allowed per window |
| `DEFAULT_RATE_LIMIT_WINDOW` | 60 | Default rate limit window in seconds |
| `HEARTBEAT_INTERVAL` | 45 | Heartbeat ping interval in seconds |

### RateLimitMixin

Sliding-window rate limiter per WebSocket connection.

| Method | Description |
|--------|-------------|
| `_init_rate_limit()` | Initialize rate limit tracking state |
| `_is_rate_limited()` | Check if connection has exceeded the message rate limit |

Default: 30 messages per 60-second window. Override `rate_limit_msgs` and `rate_limit_window` on the consumer class to customize.

### AuthenticatedConsumerMixin

Post-connect token authentication with heartbeat keep-alive.

| Method | Description |
|--------|-------------|
| `_init_auth()` | Initialize authentication state |
| `_handle_auth_connect()` | Handle initial connection (accept and wait for auth message) |
| `_setup_authenticated()` | Set up the consumer after successful authentication |
| `_handle_authenticate_message(data)` | Process an incoming authentication message with token |
| `send_error(message, code)` | Send an error message to the client |

Supports deferred post-connect token authentication. After successful auth, starts a heartbeat loop every 45 seconds.

### BlockingMixin

Check `BlockedUser` relationships before allowing interactions.

| Method | Description |
|--------|-------------|
| `_is_blocked(user_a, user_b)` | Check bidirectional block status between two users |

### ModerationMixin

Content moderation via `ContentModerationService`.

| Method | Description |
|--------|-------------|
| `_moderate_content(content, context='chat')` | Run content through the moderation pipeline |

## Exception Handling

`exceptions.py`

### custom_exception_handler

Custom DRF exception handler that wraps all error responses in a consistent format:

```json
{
  "error": true,
  "message": "Error description",
  "status_code": 400,
  "detail": "..."
}
```

If the original response contains a `detail` key, it is preserved. Otherwise, all response data is placed under `details`.

### Domain Exceptions

| Exception | Purpose |
|-----------|---------|
| `OpenAIError` | OpenAI API errors |
| `ValidationError` | Custom validation errors |
| `NotificationError` | Notification delivery errors |

## Health Check Endpoints

`urls.py` and `views.py`

| Path | View | Description |
|------|------|-------------|
| `/` | `health_check` | Full health check including database and cache connectivity with latency measurements. Returns 503 if any service is down |
| `/liveness/` | `liveness_check` | Simple liveness probe (`{"status": "alive"}`). Confirms the Django process is running |
| `/readiness/` | `readiness_check` | Readiness probe that verifies database connectivity. Returns 503 if the database is unavailable |

### Health Check Response Format

```json
{
  "status": "healthy",
  "timestamp": 1707350400.0,
  "services": {
    "database": {
      "status": "up",
      "latency_ms": 1.23
    },
    "cache": {
      "status": "up",
      "latency_ms": 0.45
    }
  }
}
```

## AI Output Validators

`ai_validators.py`

Pydantic-based validation schemas for all AI-generated responses. Every AI output is validated before being saved or returned to the user.

### Pydantic Schemas

| Schema | Purpose |
|--------|---------|
| `PlanTaskSchema` | Single task: title, description, order, duration_mins, reasoning |
| `PlanGoalSchema` | Goal with nested tasks list, estimated_minutes, reasoning |
| `PlanObstacleSchema` | Obstacle: title, description, solution, evidence |
| `PlanResponseSchema` | Complete plan: goals, tips, obstacles, calibration_references |
| `AnalysisResponseSchema` | Dream analysis: category, difficulty, key_challenges, approach |
| `CalibrationQuestionSchema` | Single calibration question with category |
| `CalibrationQuestionsResponseSchema` | Question batch with sufficient flag, confidence_score |
| `UserProfileSchema` | Structured user profile: experience_level, budget, tools, motivations, constraints |
| `PlanRecommendationsSchema` | AI recommendations: pace, focus areas, pitfalls |
| `CalibrationSummaryResponseSchema` | Full calibration summary with user profile and recommendations |
| `ChatResponseSchema` | Chat response: content, tokens_used, model |
| `FunctionCallSchema` | Function calls (create_task, complete_task, create_goal) |

### Validation Functions

| Function | Purpose |
|----------|---------|
| `validate_plan_response(data)` | Validates plan against `PlanResponseSchema` |
| `validate_analysis_response(data)` | Validates analysis against `AnalysisResponseSchema` |
| `validate_calibration_questions(data)` | Validates questions against `CalibrationQuestionsResponseSchema` |
| `validate_calibration_summary(data)` | Validates summary against `CalibrationSummaryResponseSchema` |
| `validate_chat_response(data)` | Validates chat response against `ChatResponseSchema` |
| `validate_function_call(data)` | Validates function call against `FunctionCallSchema` |

### Safety Checks

| Function | Purpose |
|----------|---------|
| `validate_ai_output_safety(text)` | Scans AI output for harmful content (violence, sexual, illegal, self-harm) |
| `check_ai_character_integrity(text)` | Detects jailbreak or role-play patterns in AI responses |
| `check_plan_calibration_coherence(plan, calibration)` | Validates that the generated plan matches the user's calibration data |

### Constants

- Max lengths: `MAX_TITLE_LEN=255`, `MAX_DESCRIPTION_LEN=5000`, `MAX_TEXT_LEN=10000`
- Valid enums: categories, difficulties, experience_levels, paces, risk_levels, calibration_categories

## AI Usage Tracking

`ai_usage.py`

Redis-backed daily AI usage quota tracking per user per feature. Prevents users from exceeding their subscription plan's daily limits.

### Quota Categories

| Category | Actions Included |
|----------|-----------------|
| `ai_chat` | send_message, websocket_chat, send_image |
| `ai_plan` | analyze_dream, calibration, generate_plan, two_minute_start |
| `ai_image` | generate_vision (DALL-E) |
| `ai_voice` | send_voice, transcribe (Whisper) |
| `ai_background` | daily_motivation, weekly_report, rescue_message, conversation_summary |

### AIUsageTracker Class

| Method | Description |
|--------|-------------|
| `get_limits(user)` | Returns daily limits from user's subscription plan (or defaults) |
| `check_quota(user, category)` | Returns `(allowed: bool, info: dict)` — whether user has remaining quota |
| `increment(user, category)` | Atomically increments usage counter. Sets 24h TTL on first use |
| `get_usage(user)` | Returns all category usage counts for today |
| `get_reset_time()` | Returns next midnight UTC when quotas reset |

### Redis Key Format

```
ai_usage:{user_id}:{category}:{YYYY-MM-DD}
```

Keys auto-expire at end of day via Redis TTL.

## Content Moderation

`moderation.py`

Three-tier content moderation system for all user-generated text and AI inputs/outputs.

### Moderation Pipeline

```
Input text
  │
  ├─ Tier 1: Jailbreak detection (regex)
  │    Instruction overrides, DAN/persona injection, system prompt extraction,
  │    encoding bypass, hypothetical framing
  │
  ├─ Tier 2: Roleplay detection (regex)
  │    Pretend/imagine attempts, character adoption
  │
  ├─ Tier 3: Harmful content patterns (regex)
  │    Four categories:
  │    - Violence (kill, harm, revenge)
  │    - Sexual content (explicit language)
  │    - Coercion (force love, stalking, manipulation)
  │    - Illegal activity (steal, hack, fraud, drugs)
  │
  └─ Tier 4: OpenAI Moderation API
       Model: omni-moderation-latest
       Catches anything patterns missed
```

### ModerationResult

Dataclass returned from all moderation checks:

| Field | Type | Description |
|-------|------|-------------|
| `is_flagged` | bool | Whether content was flagged |
| `categories` | list[str] | Flagged categories (e.g., `['jailbreak_attempt']`) |
| `severity` | str | `none`, `low`, `medium`, `high` |
| `user_message` | str | User-facing rejection message |
| `raw_scores` | dict | Raw scores from OpenAI API |
| `detection_source` | str | Which tier caught it |

### ContentModerationService

| Method | Description |
|--------|-------------|
| `moderate_text(text)` | Full moderation pipeline with caching |
| `moderate_dream(title, description)` | Specialized for dream content |

### Rejection Messages

Pre-written friendly rejection messages for: `harmful_content`, `sexual_content`, `relationship_coercion`, `self_harm`, `jailbreak_attempt`, `roleplay_attempt`, `illegal_content`, `generic_violation`.

## Input Validators

`validators.py`

Field-specific input validators with regex patterns.

### Regex Patterns

| Pattern | Rules | Max Length |
|---------|-------|-----------|
| `DISPLAY_NAME_PATTERN` | Alphanumeric + accents, spaces, hyphens, apostrophes, periods | 100 chars |
| `LOCATION_PATTERN` | Alphanumeric + accents, commas, hyphens, apostrophes, parentheses | 200 chars |
| `COUPON_CODE_PATTERN` | Letters, numbers, hyphens, underscores | 50 chars |
| `TAG_NAME_PATTERN` | Letters, numbers, spaces, hyphens | 50 chars |
| `UUID_PATTERN` | Standard UUID format | 36 chars |

### Validation Functions

| Function | Purpose |
|----------|---------|
| `validate_uuid(value)` | Validates UUID strings or UUID objects |
| `validate_pagination_params(page, page_size)` | Ensures page >= 1, page_size 1-100 |
| `validate_search_query(query)` | Sanitizes and limits search input to 200 chars |
| `validate_display_name(name)` | Validates against DISPLAY_NAME_PATTERN |
| `validate_location(location)` | Validates against LOCATION_PATTERN |
| `validate_coupon_code(code)` | Validates against COUPON_CODE_PATTERN |
| `validate_tag_name(name)` | Validates against TAG_NAME_PATTERN |
| `validate_text_length(text, max_length)` | Ensures text doesn't exceed max_length |

## Middleware

`middleware.py`

### SecurityHeadersMiddleware

Adds security headers to every HTTP response:

| Header | Value |
|--------|-------|
| `Content-Security-Policy` | Configurable via `settings.CSP_POLICY` |
| `Referrer-Policy` | `strict-origin-when-cross-origin` |
| `Permissions-Policy` | Disables geolocation, microphone, camera, payment |
| `X-Content-Type-Options` | `nosniff` |
| `X-Frame-Options` | `DENY` |
| `Cross-Origin-Opener-Policy` | Set |
| `Cross-Origin-Resource-Policy` | Set |

### LastActivityMiddleware

Tracks `user.last_seen` and `user.is_online` on every authenticated request. Throttled to max once per 60 seconds per user to minimize database writes. Uses in-memory cache for throttle tracking.

## Audit Logging

`audit.py`

Structured security event logging via Python's `logging` module (logger name: `security`). All functions accept the Django `request` object and extract client IP from `X-Forwarded-For` header.

### Logging Functions

| Function | Severity | Triggered By |
|----------|----------|--------------|
| `log_auth_failure(request, email)` | WARNING | Failed login attempt |
| `log_auth_success(request, user)` | INFO | Successful login |
| `log_permission_denied(request, permission)` | WARNING | Permission check failure |
| `log_data_export(request, user)` | INFO | GDPR data export request |
| `log_account_change(request, change_type)` | INFO | Password/email change, account deletion |
| `log_webhook_event(request, event_type)` | INFO | Incoming Stripe/external webhook |
| `log_suspicious_input(request, field, original)` | WARNING | Input sanitization stripped content |
| `log_content_moderation(request, text, result)` | WARNING | Content moderation flagged input |
| `log_ai_output_flagged(request, output, reason)` | WARNING | AI output failed safety check |
| `log_jailbreak_attempt(request, text)` | CRITICAL | Jailbreak attempt detected |
