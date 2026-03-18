"""
WebSocket routing for AI Coaching app.
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
]
