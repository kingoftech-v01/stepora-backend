"""
ASGI config for DreamPlanner backend.
Exposes the ASGI callable as a module-level variable named ``application``.
"""

import os
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import AllowedHostsOriginValidator
from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')

# Initialize Django ASGI application early
django_asgi_app = get_asgi_application()

# Import routing after Django setup
from apps.conversations.routing import websocket_urlpatterns
from core.websocket_auth import FirebaseAuthMiddlewareStack

application = ProtocolTypeRouter({
    # HTTP
    "http": django_asgi_app,

    # WebSocket - Using Firebase authentication
    "websocket": AllowedHostsOriginValidator(
        FirebaseAuthMiddlewareStack(
            URLRouter(websocket_urlpatterns)
        )
    ),
})
