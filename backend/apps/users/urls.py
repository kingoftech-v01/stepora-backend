"""
URLs for Users app.
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import UserViewSet, DreamBuddyViewSet

router = DefaultRouter()
router.register(r'', UserViewSet, basename='user')
router.register(r'buddies', DreamBuddyViewSet, basename='dream-buddy')

urlpatterns = [
    path('', include(router.urls)),
]
