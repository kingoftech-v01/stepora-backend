"""
Fixtures for notifications app tests.
"""

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.notifications.models import Notification, WebPushSubscription, UserDevice
from apps.users.models import User


@pytest.fixture
def notif_user(db):
    """Create a user for notification tests."""
    return User.objects.create_user(
        email="notifuser@example.com",
        password="testpassword123",
        display_name="Notif User",
        timezone="Europe/Paris",
    )


@pytest.fixture
def notif_client(notif_user):
    """Authenticated API client for notif_user."""
    client = APIClient()
    client.force_authenticate(user=notif_user)
    return client


@pytest.fixture
def sample_notification(db, notif_user):
    """Create a sample notification."""
    return Notification.objects.create(
        user=notif_user,
        notification_type="reminder",
        title="Test Reminder",
        body="This is a test reminder body.",
        scheduled_for=timezone.now(),
        status="sent",
    )


@pytest.fixture
def multiple_notifications(db, notif_user):
    """Create multiple notifications for list/count tests."""
    now = timezone.now()
    notifications = []
    for i in range(5):
        n = Notification.objects.create(
            user=notif_user,
            notification_type="reminder",
            title=f"Notification {i}",
            body=f"Body for notification {i}",
            scheduled_for=now,
            status="sent",
        )
        notifications.append(n)
    # Mark some as read
    notifications[0].mark_read()
    notifications[1].mark_read()
    return notifications
