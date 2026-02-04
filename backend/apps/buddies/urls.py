"""
URL configuration for the Buddies system.

Routes:
    /current                - Get current buddy pairing
    /<id>/progress          - Get progress comparison
    /find-match             - Find a compatible buddy
    /pair                   - Create a pairing
    /<id>/encourage         - Send encouragement
    /<id>/                  - End (DELETE) a pairing
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import BuddyViewSet

router = DefaultRouter()
router.register(r'', BuddyViewSet, basename='buddy')

urlpatterns = [
    path('', include(router.urls)),
]
