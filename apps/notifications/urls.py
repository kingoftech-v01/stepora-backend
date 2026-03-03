"""
URLs for Notifications app.
"""

from django.urls import path, include
from rest_framework.routers import SimpleRouter
from .views import (
    NotificationViewSet,
    NotificationTemplateViewSet,
    WebPushSubscriptionViewSet,
    UserDeviceViewSet,
    NotificationBatchViewSet,
)

router = SimpleRouter()
router.register(r'', NotificationViewSet, basename='notification')
router.register(r'templates', NotificationTemplateViewSet, basename='notification-template')
router.register(r'push-subscriptions', WebPushSubscriptionViewSet, basename='push-subscription')
router.register(r'devices', UserDeviceViewSet, basename='user-device')
router.register(r'batches', NotificationBatchViewSet, basename='notification-batch')

urlpatterns = [
    path('', include(router.urls)),
]
