"""
WebSocket routing for Buddy Chat.
"""

from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(
        r'ws/buddy-chat/(?P<pairing_id>[0-9a-f-]+)/$',
        consumers.BuddyChatConsumer.as_asgi(),
    ),
]
