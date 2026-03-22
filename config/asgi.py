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

# Import routing after Django setup
from apps.ai.routing import websocket_urlpatterns as ai_chat_ws  # noqa: E402
from apps.chat.routing import websocket_urlpatterns as buddy_chat_ws  # noqa: E402
from apps.circles.routing import websocket_urlpatterns as circle_chat_ws  # noqa: E402
from apps.leagues.routing import websocket_urlpatterns as league_ws  # noqa: E402
from apps.notifications.routing import websocket_urlpatterns as notification_ws  # noqa: E402
from apps.social.routing import websocket_urlpatterns as social_ws  # noqa: E402
from core.websocket_auth import TokenAuthMiddlewareStack  # noqa: E402

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
