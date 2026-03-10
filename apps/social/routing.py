"""
WebSocket URL routing for Social app.
"""

from django.urls import re_path

from . import consumers

websocket_urlpatterns = [
    re_path(r"ws/social-feed/$", consumers.SocialFeedConsumer.as_asgi()),
]
