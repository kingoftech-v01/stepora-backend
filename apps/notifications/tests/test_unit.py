"""
Unit tests for the Notifications app models and services.
"""

import pytest
from django.utils import timezone

from apps.notifications.models import (
    Notification,
    UserDevice,
    WebPushSubscription,
)
from apps.notifications.services import NotificationService
from apps.users.models import User


# ──────────────────────────────────────────────────────────────────────
#  Notification Model
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestNotificationModel:
    """Tests for the Notification model."""

    def test_create_notification(self, notif_user):
        """Notification can be created with required fields."""
        now = timezone.now()
        notification = Notification.objects.create(
            user=notif_user,
            notification_type="reminder",
            title="Test Notification",
            body="This is a test notification body.",
            scheduled_for=now,
        )
        assert notification.pk is not None
        assert notification.user == notif_user
        assert notification.notification_type == "reminder"
        assert notification.title == "Test Notification"
        assert notification.body == "This is a test notification body."
        assert notification.status == "pending"
        assert notification.sent_at is None
        assert notification.read_at is None
        assert notification.opened_at is None
        assert notification.retry_count == 0
        assert notification.max_retries == 3

    def test_notification_str(self, notif_user):
        """Notification __str__ returns type, title, and status."""
        notification = Notification.objects.create(
            user=notif_user,
            notification_type="motivation",
            title="Stay Motivated",
            body="Keep going!",
            scheduled_for=timezone.now(),
        )
        result = str(notification)
        assert "motivation" in result
        assert "Stay Motivated" in result
        assert "pending" in result

    def test_mark_sent(self, notif_user):
        """mark_sent() updates status and sent_at."""
        notification = Notification.objects.create(
            user=notif_user,
            notification_type="reminder",
            title="Test",
            body="Body",
            scheduled_for=timezone.now(),
        )
        notification.mark_sent()
        notification.refresh_from_db()
        assert notification.status == "sent"
        assert notification.sent_at is not None

    def test_mark_read(self, notif_user):
        """mark_read() sets read_at timestamp."""
        notification = Notification.objects.create(
            user=notif_user,
            notification_type="reminder",
            title="Test",
            body="Body",
            scheduled_for=timezone.now(),
            status="sent",
        )
        assert notification.read_at is None
        notification.mark_read()
        notification.refresh_from_db()
        assert notification.read_at is not None

    def test_mark_opened(self, notif_user):
        """mark_opened() sets opened_at and also sets read_at if not already read."""
        notification = Notification.objects.create(
            user=notif_user,
            notification_type="reminder",
            title="Test",
            body="Body",
            scheduled_for=timezone.now(),
            status="sent",
        )
        assert notification.read_at is None
        assert notification.opened_at is None
        notification.mark_opened()
        notification.refresh_from_db()
        assert notification.opened_at is not None
        assert notification.read_at is not None
        # read_at should equal opened_at
        assert notification.read_at == notification.opened_at

    def test_mark_opened_preserves_read_at(self, notif_user):
        """mark_opened() does not overwrite an existing read_at."""
        notification = Notification.objects.create(
            user=notif_user,
            notification_type="reminder",
            title="Test",
            body="Body",
            scheduled_for=timezone.now(),
            status="sent",
        )
        # Mark as read first
        notification.mark_read()
        original_read_at = notification.read_at
        # Then mark as opened
        notification.mark_opened()
        notification.refresh_from_db()
        assert notification.read_at == original_read_at
        assert notification.opened_at is not None

    def test_mark_failed(self, notif_user):
        """mark_failed() updates status, error_message, and retry_count."""
        notification = Notification.objects.create(
            user=notif_user,
            notification_type="reminder",
            title="Test",
            body="Body",
            scheduled_for=timezone.now(),
        )
        notification.mark_failed("Connection timeout")
        notification.refresh_from_db()
        assert notification.status == "failed"
        assert notification.error_message == "Connection timeout"
        assert notification.retry_count == 1

    def test_should_send_pending_scheduled_now(self, notif_user):
        """should_send() returns True for pending notification scheduled in the past."""
        notification = Notification.objects.create(
            user=notif_user,
            notification_type="reminder",
            title="Test",
            body="Body",
            scheduled_for=timezone.now(),
            status="pending",
        )
        assert notification.should_send() is True

    def test_should_send_false_for_sent(self, notif_user):
        """should_send() returns False for already-sent notifications."""
        notification = Notification.objects.create(
            user=notif_user,
            notification_type="reminder",
            title="Test",
            body="Body",
            scheduled_for=timezone.now(),
            status="sent",
        )
        assert notification.should_send() is False

    def test_should_send_false_for_future(self, notif_user):
        """should_send() returns False for notifications scheduled in the future."""
        from datetime import timedelta

        notification = Notification.objects.create(
            user=notif_user,
            notification_type="reminder",
            title="Test",
            body="Body",
            scheduled_for=timezone.now() + timedelta(hours=1),
            status="pending",
        )
        assert notification.should_send() is False

    def test_notification_types(self, notif_user):
        """All notification types can be created."""
        types = [
            "reminder", "motivation", "progress", "achievement",
            "check_in", "rescue", "buddy", "missed_call", "system",
            "dream_completed", "weekly_report", "daily_summary",
        ]
        for ntype in types:
            n = Notification.objects.create(
                user=notif_user,
                notification_type=ntype,
                title=f"Test {ntype}",
                body="Body",
                scheduled_for=timezone.now(),
            )
            assert n.notification_type == ntype

    def test_notification_data_json(self, notif_user):
        """Notification data field stores and retrieves JSON correctly."""
        data = {"screen": "dreams", "dreamId": "abc123"}
        notification = Notification.objects.create(
            user=notif_user,
            notification_type="reminder",
            title="Test",
            body="Body",
            scheduled_for=timezone.now(),
            data=data,
        )
        notification.refresh_from_db()
        assert notification.data == data
        assert notification.data["screen"] == "dreams"


# ──────────────────────────────────────────────────────────────────────
#  NotificationService.create()
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestNotificationService:
    """Tests for the NotificationService.create() method."""

    def test_create_basic_notification(self, notif_user):
        """NotificationService.create() creates a notification with defaults."""
        notification = NotificationService.create(
            user=notif_user,
            notification_type="buddy",
            title="New Buddy Match",
            body="You have been matched with a buddy!",
        )
        assert notification.pk is not None
        assert notification.user == notif_user
        assert notification.notification_type == "buddy"
        assert notification.title == "New Buddy Match"
        assert notification.body == "You have been matched with a buddy!"
        assert notification.status == "pending"
        assert notification.scheduled_for is not None
        assert notification.data == {}
        assert notification.action_url == ""
        assert notification.image_url == ""

    def test_create_with_all_kwargs(self, notif_user):
        """NotificationService.create() accepts all optional arguments."""
        now = timezone.now()
        notification = NotificationService.create(
            user=notif_user,
            notification_type="achievement",
            title="Badge Earned",
            body="You earned a new badge!",
            data={"badge_id": "123"},
            action_url="/badges/123",
            image_url="https://example.com/badge.png",
            scheduled_for=now,
            status="sent",
            sent_at=now,
        )
        assert notification.notification_type == "achievement"
        assert notification.data == {"badge_id": "123"}
        assert notification.action_url == "/badges/123"
        assert notification.image_url == "https://example.com/badge.png"
        assert notification.status == "sent"
        assert notification.sent_at == now

    def test_create_defaults_scheduled_for_to_now(self, notif_user):
        """NotificationService.create() defaults scheduled_for to now."""
        before = timezone.now()
        notification = NotificationService.create(
            user=notif_user,
            notification_type="system",
            title="System Update",
            body="A system update is available.",
        )
        after = timezone.now()
        assert before <= notification.scheduled_for <= after

    def test_create_with_none_data(self, notif_user):
        """NotificationService.create() handles None data by defaulting to empty dict."""
        notification = NotificationService.create(
            user=notif_user,
            notification_type="reminder",
            title="Test",
            body="Body",
            data=None,
        )
        assert notification.data == {}


# ──────────────────────────────────────────────────────────────────────
#  WebPushSubscription Model
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestWebPushSubscriptionModel:
    """Tests for the WebPushSubscription model."""

    def test_create_subscription(self, notif_user):
        """WebPushSubscription can be created."""
        sub = WebPushSubscription.objects.create(
            user=notif_user,
            subscription_info={
                "endpoint": "https://fcm.googleapis.com/fcm/send/abc123",
                "keys": {"p256dh": "key1", "auth": "key2"},
            },
            browser="Chrome",
            is_active=True,
        )
        assert sub.pk is not None
        assert sub.user == notif_user
        assert sub.browser == "Chrome"
        assert sub.is_active is True
        assert sub.subscription_info["endpoint"].startswith("https://")

    def test_subscription_str(self, notif_user):
        """WebPushSubscription __str__ returns readable representation."""
        sub = WebPushSubscription.objects.create(
            user=notif_user,
            subscription_info={"endpoint": "https://example.com"},
            browser="Firefox",
        )
        result = str(sub)
        assert notif_user.email in result
        assert "Firefox" in result

    def test_subscription_defaults_active(self, notif_user):
        """WebPushSubscription defaults to is_active=True."""
        sub = WebPushSubscription.objects.create(
            user=notif_user,
            subscription_info={"endpoint": "https://example.com"},
        )
        assert sub.is_active is True


# ──────────────────────────────────────────────────────────────────────
#  UserDevice Model
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestUserDeviceModel:
    """Tests for the UserDevice model."""

    def test_create_device(self, notif_user):
        """UserDevice can be created with required fields."""
        device = UserDevice.objects.create(
            user=notif_user,
            fcm_token="fake-fcm-token-0123456789abcdef",
            platform="android",
            device_name="Pixel 7",
            app_version="2.0.0",
        )
        assert device.pk is not None
        assert device.user == notif_user
        assert device.platform == "android"
        assert device.device_name == "Pixel 7"
        assert device.app_version == "2.0.0"
        assert device.is_active is True

    def test_device_str(self, notif_user):
        """UserDevice __str__ returns readable representation."""
        device = UserDevice.objects.create(
            user=notif_user,
            fcm_token="fake-fcm-token-device-str-test",
            platform="ios",
        )
        result = str(device)
        assert notif_user.email in result
        assert "ios" in result
        assert "active" in result

    def test_device_platforms(self, notif_user):
        """UserDevice supports android, ios, and web platforms."""
        for i, platform in enumerate(("android", "ios", "web")):
            device = UserDevice.objects.create(
                user=notif_user,
                fcm_token=f"fake-token-platform-{i}-{platform}",
                platform=platform,
            )
            assert device.platform == platform

    def test_device_unique_token(self, notif_user):
        """UserDevice fcm_token must be unique."""
        from django.db import IntegrityError

        token = "shared-token-unique-test-123456"
        UserDevice.objects.create(
            user=notif_user, fcm_token=token, platform="android"
        )
        user2 = User.objects.create_user(
            email="device_unique@example.com", password="testpassword123"
        )
        with pytest.raises(IntegrityError):
            UserDevice.objects.create(
                user=user2, fcm_token=token, platform="ios"
            )

    def test_device_soft_delete(self, notif_user):
        """UserDevice can be soft-deleted by setting is_active=False."""
        device = UserDevice.objects.create(
            user=notif_user,
            fcm_token="fake-token-soft-delete-test-99",
            platform="android",
        )
        assert device.is_active is True
        device.is_active = False
        device.save(update_fields=["is_active"])
        device.refresh_from_db()
        assert device.is_active is False
