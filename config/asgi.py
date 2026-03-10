"""
ASGI config for Stepora backend.
Exposes the ASGI callable as a module-level variable named ``application``.
"""

import os

from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import AllowedHostsOriginValidator
from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")

# Initialize Django ASGI application early
django_asgi_app = get_asgi_application()

from apps.buddies.routing import websocket_urlpatterns as buddy_chat_ws
from apps.circles.routing import websocket_urlpatterns as circle_chat_ws

# Import routing after Django setup
from apps.conversations.routing import websocket_urlpatterns as ai_chat_ws
from apps.leagues.routing import websocket_urlpatterns as league_ws
from apps.notifications.routing import websocket_urlpatterns as notification_ws
from apps.social.routing import websocket_urlpatterns as social_ws
from core.websocket_auth import TokenAuthMiddlewareStack

application = ProtocolTypeRouter(
    {
        # HTTP
        "http": django_asgi_app,
        # WebSocket - Using Token authentication
        "websocket": AllowedHostsOriginValidator(
            TokenAuthMiddlewareStack(
                URLRouter(
                    ai_chat_ws
                    + buddy_chat_ws
                    + circle_chat_ws
                    + notification_ws
                    + social_ws
                    + league_ws
                )
            )
        ),
    }
)
