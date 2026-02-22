"""
URLs for Notifications app.
"""

from django.urls import path, include
from rest_framework.routers import SimpleRouter
from .views import NotificationViewSet, NotificationTemplateViewSet, WebPushSubscriptionViewSet

router = SimpleRouter()
router.register(r'', NotificationViewSet, basename='notification')
router.register(r'templates', NotificationTemplateViewSet, basename='notification-template')
router.register(r'push-subscriptions', WebPushSubscriptionViewSet, basename='push-subscription')

urlpatterns = [
    path('', include(router.urls)),
]
