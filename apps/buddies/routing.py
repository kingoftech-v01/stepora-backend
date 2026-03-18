"""
Backward-compatibility shim. Buddy chat WS route is now in apps.chat.routing.
This list is empty to avoid duplicate route registration in ASGI.
"""

websocket_urlpatterns = []
