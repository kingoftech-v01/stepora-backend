"""
Firebase WebSocket authentication middleware for Django Channels.
"""

from urllib.parse import parse_qs
from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware
from django.contrib.auth.models import AnonymousUser
from firebase_admin import auth as firebase_auth
from apps.users.models import User


@database_sync_to_async
def get_user_from_firebase_token(token):
    """
    Verify Firebase token and return corresponding user.
    Returns AnonymousUser if token is invalid.
    """
    if not token:
        return AnonymousUser()

    try:
        # Verify token with Firebase
        decoded_token = firebase_auth.verify_id_token(token)
        firebase_uid = decoded_token['uid']

        # Get user from database
        try:
            user = User.objects.get(firebase_uid=firebase_uid)
            user.update_activity()
            return user
        except User.DoesNotExist:
            # Auto-create user if doesn't exist
            email = decoded_token.get('email')
            if not email:
                return AnonymousUser()

            user = User.objects.create(
                firebase_uid=firebase_uid,
                email=email,
                display_name=decoded_token.get('name', '')
            )
            return user

    except firebase_auth.InvalidIdTokenError:
        return AnonymousUser()
    except firebase_auth.ExpiredIdTokenError:
        return AnonymousUser()
    except Exception as e:
        print(f"WebSocket Firebase auth error: {e}")
        return AnonymousUser()


class FirebaseWebSocketMiddleware(BaseMiddleware):
    """
    Custom middleware to authenticate WebSocket connections using Firebase JWT.

    Token can be provided via:
    1. Query string: ws://host/ws/path/?token=<firebase_jwt>
    2. First message (for clients that can't set query params)

    Usage in asgi.py:
        application = ProtocolTypeRouter({
            "websocket": FirebaseWebSocketMiddleware(
                URLRouter(websocket_urlpatterns)
            ),
        })
    """

    async def __call__(self, scope, receive, send):
        # Extract token from query string
        query_string = scope.get('query_string', b'').decode()
        query_params = parse_qs(query_string)
        token = query_params.get('token', [None])[0]

        # Authenticate user
        scope['user'] = await get_user_from_firebase_token(token)

        return await super().__call__(scope, receive, send)


class FirebaseWebSocketAuthMiddleware:
    """
    Alternative middleware that wraps the ASGI application.
    Provides the same functionality as FirebaseWebSocketMiddleware.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        # Only process websocket connections
        if scope['type'] != 'websocket':
            return await self.app(scope, receive, send)

        # Extract token from query string
        query_string = scope.get('query_string', b'').decode()
        query_params = parse_qs(query_string)
        token = query_params.get('token', [None])[0]

        # Authenticate user
        scope['user'] = await get_user_from_firebase_token(token)

        return await self.app(scope, receive, send)


def FirebaseAuthMiddlewareStack(inner):
    """
    Convenience function to wrap an ASGI application with Firebase auth.
    Drop-in replacement for AuthMiddlewareStack.

    Usage:
        from core.websocket_auth import FirebaseAuthMiddlewareStack

        application = ProtocolTypeRouter({
            "websocket": AllowedHostsOriginValidator(
                FirebaseAuthMiddlewareStack(
                    URLRouter(websocket_urlpatterns)
                )
            ),
        })
    """
    return FirebaseWebSocketAuthMiddleware(inner)
