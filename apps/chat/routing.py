"""
WebSocket routing for Chat app (AI Chat + Buddy Chat).
"""

from django.urls import re_path

from . import consumers

websocket_urlpatterns = [
    # AI Chat - Primary path
    re_path(
        r"ws/ai-chat/(?P<conversation_id>[0-9a-f-]+)/$",
        consumers.AIChatConsumer.as_asgi(),
    ),
    # AI Chat - Deprecated alias (backward compat)
    re_path(
        r"ws/conversations/(?P<conversation_id>[0-9a-f-]+)/$",
        consumers.AIChatConsumer.as_asgi(),
    ),
    # Buddy Chat
    re_path(
        r"ws/buddy-chat/(?P<pairing_id>[0-9a-f-]+)/$",
        consumers.BuddyChatConsumer.as_asgi(),
    ),
]
