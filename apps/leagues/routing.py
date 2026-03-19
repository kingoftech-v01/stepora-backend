"""
League routing — removed.

League standings are updated via Celery Beat (4x/day).
No WebSocket consumer needed.
"""

websocket_urlpatterns = []
