"""
WebSocket routing for Circle Chat.
"""

from django.urls import re_path

from . import consumers

websocket_urlpatterns = [
    re_path(
        r"ws/circle-chat/(?P<circle_id>[0-9a-f-]+)/$",
        consumers.CircleChatConsumer.as_asgi(),
    ),
]
