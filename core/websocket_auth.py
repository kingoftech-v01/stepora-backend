"""
Token-based WebSocket authentication middleware for Django Channels.
Uses DRF Token authentication.
"""

from urllib.parse import parse_qs
from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware
from django.contrib.auth.models import AnonymousUser
from rest_framework.authtoken.models import Token


@database_sync_to_async
def get_user_from_token(token_key):
    """
    Verify DRF token and return corresponding user.
    Returns AnonymousUser if token is invalid.
    """
    if not token_key:
        return AnonymousUser()

    try:
        token = Token.objects.select_related('user').get(key=token_key)
        user = token.user
        user.update_activity()
        return user
    except Token.DoesNotExist:
        return AnonymousUser()
    except Exception:
        return AnonymousUser()


class TokenWebSocketMiddleware(BaseMiddleware):
    """
    Custom middleware to authenticate WebSocket connections using DRF tokens.

    Token can be provided via query string: ws://host/ws/path/?token=<auth_token>

    Usage in asgi.py:
        application = ProtocolTypeRouter({
            "websocket": TokenWebSocketMiddleware(
                URLRouter(websocket_urlpatterns)
            ),
        })
    """

    async def __call__(self, scope, receive, send):
        query_string = scope.get('query_string', b'').decode()
        query_params = parse_qs(query_string)
        token = query_params.get('token', [None])[0]

        scope['user'] = await get_user_from_token(token)

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

        scope['user'] = await get_user_from_token(token)

        return await self.app(scope, receive, send)


def TokenAuthMiddlewareStack(inner):
    """
    Convenience function to wrap an ASGI application with token auth.
    Drop-in replacement for AuthMiddlewareStack.
    """
    return TokenWebSocketAuthMiddleware(inner)
