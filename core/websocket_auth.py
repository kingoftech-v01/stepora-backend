"""
Token-based WebSocket authentication middleware for Django Channels.
Supports JWT (primary) and legacy DRF Token (fallback during migration).

Supports two authentication modes:
1. Post-connect message: client sends {"type": "authenticate", "token": "..."} (preferred, secure)
2. Query string: ws://host/ws/path/?token=<token> (deprecated -- tokens leak into logs)

Mode 1 is preferred because tokens in URLs can appear in server access logs,
browser history, proxy logs, and Referrer headers.

V-319: Includes per-IP WebSocket connection rate limiting to prevent flooding.
"""

import logging
import time
import threading
from collections import defaultdict
from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware
from django.contrib.auth.models import AnonymousUser

logger = logging.getLogger(__name__)

# ── WebSocket connection rate limiting (V-319) ──────────────────────
# Per-IP connection tracking to prevent WS flooding attacks.
_WS_MAX_CONNECTIONS_PER_IP = 20      # Max concurrent connections per IP
_WS_CONNECT_RATE_WINDOW = 60         # Rate window in seconds
_WS_MAX_CONNECTS_PER_WINDOW = 30     # Max new connections per window per IP

_ws_connections = defaultdict(int)     # IP -> active connection count
_ws_connect_times = defaultdict(list)  # IP -> list of connect timestamps
_ws_lock = threading.Lock()


def _get_client_ip_from_scope(scope):
    """Extract client IP from WebSocket scope headers."""
    headers = dict(scope.get("headers", []))
    # X-Forwarded-For from ALB (last entry is real client IP)
    xff = headers.get(b"x-forwarded-for", b"").decode()
    if xff:
        return xff.split(",")[-1].strip()
    # Direct connection
    client = scope.get("client")
    if client:
        return client[0]
    return "unknown"


def _check_ws_rate_limit(ip):
    """
    Check if a WebSocket connection from this IP should be allowed.
    Returns (allowed: bool, reason: str).
    """
    with _ws_lock:
        # Check concurrent connection limit
        if _ws_connections[ip] >= _WS_MAX_CONNECTIONS_PER_IP:
            return False, f"Too many concurrent WebSocket connections from {ip}"

        # Check connection rate
        now = time.monotonic()
        # Clean old timestamps
        _ws_connect_times[ip] = [
            t for t in _ws_connect_times[ip]
            if now - t < _WS_CONNECT_RATE_WINDOW
        ]
        if len(_ws_connect_times[ip]) >= _WS_MAX_CONNECTS_PER_WINDOW:
            return False, f"WebSocket connection rate limit exceeded for {ip}"

        # Record this connection
        _ws_connections[ip] += 1
        _ws_connect_times[ip].append(now)
        return True, ""


def _release_ws_connection(ip):
    """Release a tracked WebSocket connection for this IP."""
    with _ws_lock:
        if _ws_connections[ip] > 0:
            _ws_connections[ip] -= 1
        if _ws_connections[ip] == 0:
            del _ws_connections[ip]


@database_sync_to_async
def get_user_from_token(token_key):
    """
    Verify token and return corresponding user.
    Tries JWT first, falls back to legacy DRF Token.
    Returns AnonymousUser if token is invalid or expired.
    """
    if not token_key:
        return AnonymousUser()

    # Try JWT access token first
    try:
        from django.contrib.auth import get_user_model
        from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
        from rest_framework_simplejwt.tokens import AccessToken

        User = get_user_model()

        validated = AccessToken(token_key)
        user_id = validated["user_id"]
        user = User.objects.get(id=user_id, is_active=True)
        return user
    except (TokenError, InvalidToken, KeyError, User.DoesNotExist):
        pass

    # Fallback: legacy DRF Token (transition period)
    try:
        from datetime import timedelta

        from django.conf import settings
        from django.utils import timezone
        from rest_framework.authtoken.models import Token

        token = Token.objects.select_related("user").get(key=token_key)

        token_age = timezone.now() - token.created
        expiry_hours = getattr(settings, "TOKEN_EXPIRY_HOURS", 24)
        if token_age > timedelta(hours=expiry_hours):
            return AnonymousUser()

        if not token.user.is_active:
            return AnonymousUser()

        return token.user
    except (Token.DoesNotExist, TypeError, ValueError):
        return AnonymousUser()


class TokenWebSocketMiddleware(BaseMiddleware):
    """
    Custom middleware to authenticate WebSocket connections using DRF tokens.

    Preferred: client sends {"type": "authenticate", "token": "..."} after connect.
    Fallback: query string ?token=<auth_token> (deprecated).

    Includes per-IP connection rate limiting (V-319).

    Usage in asgi.py:
        application = ProtocolTypeRouter({
            "websocket": TokenWebSocketMiddleware(
                URLRouter(websocket_urlpatterns)
            ),
        })
    """

    async def __call__(self, scope, receive, send):
        # V-319: Per-IP WebSocket connection rate limiting
        client_ip = _get_client_ip_from_scope(scope)
        allowed, reason = _check_ws_rate_limit(client_ip)
        if not allowed:
            logger.warning("WebSocket connection rejected: %s", reason)
            # Send WebSocket close frame with 1008 (Policy Violation)
            await send({"type": "websocket.close", "code": 1008})
            _release_ws_connection(client_ip)
            return

        # Store IP in scope for cleanup on disconnect
        scope["_ws_client_ip"] = client_ip

        # Fallback: try query string token (deprecated, for backward compatibility)
        query_string = scope.get("query_string", b"").decode()
        query_params = parse_qs(query_string)
        token = query_params.get("token", [None])[0]

        if token:
            logger.warning(
                "WebSocket auth via query string is deprecated. "
                "Use post-connect authenticate message instead."
            )

        scope["user"] = await get_user_from_token(token)
        # Store a flag so consumers know they can accept a post-connect authenticate message
        scope["_allow_post_auth"] = not token

        try:
            return await super().__call__(scope, receive, send)
        finally:
            # Release the connection tracking when the WS disconnects
            _release_ws_connection(client_ip)


class TokenWebSocketAuthMiddleware:
    """
    Alternative middleware that wraps the ASGI application.
    Includes per-IP connection rate limiting (V-319).
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "websocket":
            return await self.app(scope, receive, send)

        # V-319: Per-IP WebSocket connection rate limiting
        client_ip = _get_client_ip_from_scope(scope)
        allowed, reason = _check_ws_rate_limit(client_ip)
        if not allowed:
            logger.warning("WebSocket connection rejected: %s", reason)
            await send({"type": "websocket.close", "code": 1008})
            _release_ws_connection(client_ip)
            return

        scope["_ws_client_ip"] = client_ip

        query_string = scope.get("query_string", b"").decode()
        query_params = parse_qs(query_string)
        token = query_params.get("token", [None])[0]

        if token:
            logger.warning(
                "WebSocket auth via query string is deprecated. "
                "Use post-connect authenticate message instead."
            )

        scope["user"] = await get_user_from_token(token)
        scope["_allow_post_auth"] = not token

        try:
            return await self.app(scope, receive, send)
        finally:
            _release_ws_connection(client_ip)


def TokenAuthMiddlewareStack(inner):
    """
    Convenience function to wrap an ASGI application with token auth.
    Drop-in replacement for AuthMiddlewareStack.
    """
    return TokenWebSocketAuthMiddleware(inner)
