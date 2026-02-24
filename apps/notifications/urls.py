"""
URLs for Notifications app.
"""

from django.urls import path, include
from rest_framework.routers import SimpleRouter
from .views import NotificationViewSet, NotificationTemplateViewSet, WebPushSubscriptionViewSet, UserDeviceViewSet

router = SimpleRouter()
router.register(r'', NotificationViewSet, basename='notification')
router.register(r'templates', NotificationTemplateViewSet, basename='notification-template')
router.register(r'push-subscriptions', WebPushSubscriptionViewSet, basename='push-subscription')
router.register(r'devices', UserDeviceViewSet, basename='user-device')

urlpatterns = [
    path('', include(router.urls)),
]
