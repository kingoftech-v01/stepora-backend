"""
WebSocket routing for Chat app (Buddy Chat only).
AI chat routing is in apps.ai.routing.
"""

from django.urls import re_path

from . import consumers

websocket_urlpatterns = [
    # Buddy Chat
    re_path(
        r"ws/buddy-chat/(?P<pairing_id>[0-9a-f-]+)/$",
        consumers.BuddyChatConsumer.as_asgi(),
    ),
]
