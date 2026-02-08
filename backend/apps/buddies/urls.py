"""
URL configuration for the Buddies system.

Routes:
    /current                - Get current buddy pairing
    /<id>/progress          - Get progress comparison
    /find-match             - Find a compatible buddy
    /pair                   - Create a pairing
    /<id>/accept            - Accept a pending pairing
    /<id>/reject            - Reject a pending pairing
    /<id>/encourage         - Send encouragement
    /history                - Get pairing history
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
