"""
Idempotency middleware for offline queue replay protection.

Clients send an ``X-Idempotency-Key`` header on mutation requests
(POST / PUT / PATCH / DELETE).  The server caches the response and
returns the cached version on replay, preventing duplicate side-effects
such as double XP awards.

Cache backend: Django default cache (Redis in production).
TTL: 24 hours — long enough to cover any realistic offline window.
"""

import json
import logging

from django.core.cache import cache
from django.http import JsonResponse

logger = logging.getLogger(__name__)


class IdempotencyMiddleware:
    """Return cached responses for replayed mutation requests."""

    CACHE_TTL = 86400  # 24 hours

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Only apply to mutation methods
        if request.method not in ("POST", "PUT", "PATCH", "DELETE"):
            return self.get_response(request)

        key = request.headers.get("X-Idempotency-Key")
        if not key:
            return self.get_response(request)

        # Scope by authenticated user to prevent cross-user cache collisions
        user_id = getattr(request.user, "id", "anon") if hasattr(request, "user") else "anon"
        cache_key = f"idempotency:{user_id}:{key}"

        cached = cache.get(cache_key)
        if cached is not None:
            logger.debug("Idempotency cache hit for key=%s user=%s", key, user_id)
            response = JsonResponse(
                cached["body"], status=cached["status"], safe=False
            )
            response["X-Idempotency-Replayed"] = "true"
            return response

        response = self.get_response(request)

        # Cache successful responses (2xx)
        if 200 <= response.status_code < 300:
            try:
                body = json.loads(response.content)
            except (json.JSONDecodeError, ValueError):
                body = {}
            cache.set(
                cache_key,
                {"status": response.status_code, "body": body},
                self.CACHE_TTL,
            )

        return response
