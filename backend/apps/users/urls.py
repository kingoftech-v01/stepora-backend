"""
URLs for Users app.
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import AuthViewSet, UserViewSet, DreamBuddyViewSet

router = DefaultRouter()
router.register(r'auth', AuthViewSet, basename='auth')
router.register(r'users', UserViewSet, basename='user')
router.register(r'buddies', DreamBuddyViewSet, basename='dream-buddy')

urlpatterns = [
    path('', include(router.urls)),
]
