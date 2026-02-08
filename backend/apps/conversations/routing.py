"""
WebSocket routing for Conversations app.
"""

from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r'ws/conversations/(?P<conversation_id>[0-9a-f-]+)/$', consumers.ChatConsumer.as_asgi()),
    re_path(r'ws/buddy-chat/(?P<conversation_id>[0-9a-f-]+)/$', consumers.BuddyChatConsumer.as_asgi()),
]
