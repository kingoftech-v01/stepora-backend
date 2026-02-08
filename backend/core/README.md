# Core Module

Shared utilities, middleware, and base classes used across all DreamPlanner backend apps.

## Overview

The `core` module provides cross-cutting infrastructure including authentication, permissions, pagination, rate limiting, input sanitization, WebSocket authentication, custom exception handling, and health check endpoints. It does not define any Django models.

## Files

| File | Description |
|------|-------------|
| `authentication.py` | Token authentication backend and CSRF exemption middleware |
| `permissions.py` | Subscription-based permission classes for feature gating |
| `pagination.py` | Custom DRF pagination classes |
| `sanitizers.py` | XSS sanitization utilities for user-generated content |
| `throttling.py` | Per-feature rate limiting throttle classes |
| `websocket_auth.py` | Token-based WebSocket authentication for Django Channels |
| `exceptions.py` | Custom DRF exception handler and domain exception classes |
| `urls.py` | Health check endpoint routing |
| `views.py` | Health check view functions |

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

## Permissions

`permissions.py`

Subscription-based access control. Each permission class checks the user's `subscription` field on the User model.

| Permission Class | Tier Required | Description |
|-----------------|--------------|-------------|
| `IsOwner` | Any authenticated | Checks `obj.user == request.user` (or `obj.user1`/`obj.user2` for pairings) |
| `IsPremiumUser` | Premium or Pro | Calls `user.is_premium()` |
| `IsProUser` | Pro only | Checks `user.subscription == 'pro'` |
| `CanCreateDream` | Any (limit-based) | Calls `user.can_create_dream()` on POST requests only |
| `CanUseAI` | Premium or Pro | Gates AI chat, plan generation, dream analysis, motivational AI |
| `CanUseBuddy` | Premium or Pro | Gates Dream Buddy matching |
| `CanUseCircles` | Pro (create), Premium+ (join/read) | Circle creation requires Pro; joining/reading requires Premium+ |
| `CanUseVisionBoard` | Pro only | Gates AI Vision Board generation |
| `CanUseLeague` | Premium or Pro | Gates league features |

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
| `FCMError` | Firebase Cloud Messaging errors |
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
