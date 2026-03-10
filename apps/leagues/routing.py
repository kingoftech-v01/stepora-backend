"""
WebSocket URL routing for Leagues app.
"""

from django.urls import re_path

from . import consumers

websocket_urlpatterns = [
    re_path(r"ws/league/$", consumers.LeagueLeaderboardConsumer.as_asgi()),
]
