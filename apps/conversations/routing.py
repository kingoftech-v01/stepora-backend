"""
WebSocket routing for Conversations app.

BuddyChatConsumer and CallSignalingConsumer removed — replaced by Agora RTM/RTC.
ChatConsumer (AI chat) remains on Django Channels.
"""

from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r'ws/conversations/(?P<conversation_id>[0-9a-f-]+)/$', consumers.ChatConsumer.as_asgi()),
]
