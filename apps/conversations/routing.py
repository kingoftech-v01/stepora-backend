"""
WebSocket routing for AI Chat (Conversations app).

BuddyChatConsumer lives in apps.buddies.routing.
"""

from django.urls import re_path

from . import consumers

websocket_urlpatterns = [
    # Primary path
    re_path(
        r"ws/ai-chat/(?P<conversation_id>[0-9a-f-]+)/$",
        consumers.AIChatConsumer.as_asgi(),
    ),
    # Deprecated alias (backward compat)
    re_path(
        r"ws/conversations/(?P<conversation_id>[0-9a-f-]+)/$",
        consumers.AIChatConsumer.as_asgi(),
    ),
]
