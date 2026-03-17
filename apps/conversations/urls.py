"""
Backward-compatibility shim. All URL patterns now live in apps.chat.urls.
"""

from apps.chat.urls import urlpatterns  # noqa: F401
