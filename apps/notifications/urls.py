"""
URLs for Notifications app.
"""

from django.urls import include, path
from rest_framework.routers import SimpleRouter

from .views import (
    NotificationBatchViewSet,
    NotificationTemplateViewSet,
    NotificationViewSet,
    ReminderPreferenceViewSet,
    UserDeviceViewSet,
    WebPushSubscriptionViewSet,
)

router = SimpleRouter()
router.register(r"reminders", ReminderPreferenceViewSet, basename="reminder-preference")
router.register(r"", NotificationViewSet, basename="notification")
router.register(
    r"templates", NotificationTemplateViewSet, basename="notification-template"
)
router.register(
    r"push-subscriptions", WebPushSubscriptionViewSet, basename="push-subscription"
)
router.register(r"devices", UserDeviceViewSet, basename="user-device")
router.register(r"batches", NotificationBatchViewSet, basename="notification-batch")

urlpatterns = [
    path("", include(router.urls)),
]
