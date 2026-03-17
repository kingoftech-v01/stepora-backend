"""
Backward-compatibility shim. All routing now lives in apps.chat.routing.
"""

from apps.chat.routing import websocket_urlpatterns  # noqa: F401
