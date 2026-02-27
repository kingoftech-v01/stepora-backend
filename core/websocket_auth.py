"""
Token-based WebSocket authentication middleware for Django Channels.
Uses DRF Token authentication.

Supports two authentication modes:
1. Post-connect message: client sends {"type": "authenticate", "token": "..."} (preferred, secure)
2. Query string: ws://host/ws/path/?token=<token> (deprecated — tokens leak into logs)

Mode 1 is preferred because tokens in URLs can appear in server access logs,
browser history, proxy logs, and Referrer headers.
"""

import json
import logging
from urllib.parse import parse_qs
from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware
from django.contrib.auth.models import AnonymousUser
from rest_framework.authtoken.models import Token

logger = logging.getLogger(__name__)


@database_sync_to_async
def get_user_from_token(token_key):
    """
    Verify DRF token, check expiration, and return corresponding user.
    Returns AnonymousUser if token is invalid or expired.
    """
    if not token_key:
        return AnonymousUser()

    try:
        token = Token.objects.select_related('user').get(key=token_key)

        # Check token expiration (same logic as ExpiringTokenAuthentication)
        from django.conf import settings
        from django.utils import timezone
        from datetime import timedelta
        token_age = timezone.now() - token.created
        expiry_hours = getattr(settings, 'TOKEN_EXPIRY_HOURS', 24)
        if token_age > timedelta(hours=expiry_hours):
            return AnonymousUser()

        if not token.user.is_active:
            return AnonymousUser()

        return token.user
    except Token.DoesNotExist:
        return AnonymousUser()
    except Exception:
        return AnonymousUser()


class TokenWebSocketMiddleware(BaseMiddleware):
    """
    Custom middleware to authenticate WebSocket connections using DRF tokens.

    Preferred: client sends {"type": "authenticate", "token": "..."} after connect.
    Fallback: query string ?token=<auth_token> (deprecated).

    Usage in asgi.py:
        application = ProtocolTypeRouter({
            "websocket": TokenWebSocketMiddleware(
                URLRouter(websocket_urlpatterns)
            ),
        })
    """

    async def __call__(self, scope, receive, send):
        # Fallback: try query string token (deprecated, for backward compatibility)
        query_string = scope.get('query_string', b'').decode()
        query_params = parse_qs(query_string)
        token = query_params.get('token', [None])[0]

        if token:
            logger.warning(
                "WebSocket auth via query string is deprecated. "
                "Use post-connect authenticate message instead."
            )

        scope['user'] = await get_user_from_token(token)
        # Store a flag so consumers know they can accept a post-connect authenticate message
        scope['_allow_post_auth'] = not token

        return await super().__call__(scope, receive, send)


class TokenWebSocketAuthMiddleware:
    """
    Alternative middleware that wraps the ASGI application.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'websocket':
            return await self.app(scope, receive, send)

        query_string = scope.get('query_string', b'').decode()
        query_params = parse_qs(query_string)
        token = query_params.get('token', [None])[0]

        if token:
            logger.warning(
                "WebSocket auth via query string is deprecated. "
                "Use post-connect authenticate message instead."
            )

        scope['user'] = await get_user_from_token(token)
        scope['_allow_post_auth'] = not token

        return await self.app(scope, receive, send)


def TokenAuthMiddlewareStack(inner):
    """
    Convenience function to wrap an ASGI application with token auth.
    Drop-in replacement for AuthMiddlewareStack.
    """
    return TokenWebSocketAuthMiddleware(inner)
