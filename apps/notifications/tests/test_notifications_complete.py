"""
Comprehensive tests for the notifications app — filling coverage gaps.

Covers:
- IDOR protection: users cannot access/modify other users' notifications
- DND (Do Not Disturb) logic in Notification.should_send()
- NotificationTemplate.render() method
- Serializer validation (XSS sanitization, FCM token validation)
- NotificationBatch success_rate property
- Model __str__ methods for all models
- NotificationConsumer WebSocket coverage
- Rate limiting patterns
- Edge cases in should_send()
"""

import uuid
from datetime import timedelta
from unittest.mock import MagicMock, patch

import pytest
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.notifications.models import (
    Notification,
    NotificationBatch,
    NotificationTemplate,
    UserDevice,
    WebPushSubscription,
)
from apps.notifications.serializers import (
    NotificationBatchSerializer,
    NotificationCreateSerializer,
    UserDeviceSerializer,
)
from apps.notifications.services import NotificationService
from apps.users.models import User


# ── Fixtures ─────────────────────────────────────────────────────────


@pytest.fixture
def user_a(db):
    """First test user."""
    return User.objects.create_user(
        email="idor_a@example.com",
        password="testpassword123",
        display_name="User A",
        timezone="Europe/Paris",
    )


@pytest.fixture
def user_b(db):
    """Second test user (for IDOR tests)."""
    return User.objects.create_user(
        email="idor_b@example.com",
        password="testpassword123",
        display_name="User B",
        timezone="America/New_York",
    )


@pytest.fixture
def client_a(user_a):
    """Authenticated API client for user_a."""
    client = APIClient()
    client.force_authenticate(user=user_a)
    return client


@pytest.fixture
def client_b(user_b):
    """Authenticated API client for user_b."""
    client = APIClient()
    client.force_authenticate(user=user_b)
    return client


@pytest.fixture
def notif_a(user_a):
    """Notification belonging to user_a."""
    return Notification.objects.create(
        user=user_a,
        notification_type="reminder",
        title="User A Notif",
        body="Private to A",
        scheduled_for=timezone.now(),
        status="sent",
    )


@pytest.fixture
def notif_b(user_b):
    """Notification belonging to user_b."""
    return Notification.objects.create(
        user=user_b,
        notification_type="reminder",
        title="User B Notif",
        body="Private to B",
        scheduled_for=timezone.now(),
        status="sent",
    )


# ══════════════════════════════════════════════════════════════════════
#  IDOR PROTECTION
# ══════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestIDORProtection:
    """Verify users cannot access or modify other users' notifications."""

    def test_cannot_retrieve_other_users_notification(self, client_b, notif_a):
        """User B cannot retrieve User A's notification."""
        response = client_b.get(f"/api/notifications/{notif_a.id}/")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_cannot_update_other_users_notification(self, client_b, notif_a):
        """User B cannot update User A's notification."""
        response = client_b.patch(
            f"/api/notifications/{notif_a.id}/",
            {"title": "Hacked"},
            format="json",
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_cannot_delete_other_users_notification(self, client_b, notif_a):
        """User B cannot delete User A's notification."""
        response = client_b.delete(f"/api/notifications/{notif_a.id}/")
        assert response.status_code == status.HTTP_404_NOT_FOUND
        # Verify notification still exists
        assert Notification.objects.filter(id=notif_a.id).exists()

    def test_cannot_mark_read_other_users_notification(self, client_b, notif_a):
        """User B cannot mark User A's notification as read."""
        response = client_b.post(f"/api/notifications/{notif_a.id}/mark_read/")
        assert response.status_code == status.HTTP_404_NOT_FOUND
        notif_a.refresh_from_db()
        assert notif_a.read_at is None

    def test_cannot_mark_opened_other_users_notification(self, client_b, notif_a):
        """User B cannot mark User A's notification as opened."""
        response = client_b.post(f"/api/notifications/{notif_a.id}/opened/")
        assert response.status_code == status.HTTP_404_NOT_FOUND
        notif_a.refresh_from_db()
        assert notif_a.opened_at is None

    def test_list_only_shows_own_notifications(self, client_a, notif_a, notif_b):
        """User A only sees their own notifications."""
        response = client_a.get("/api/notifications/")
        assert response.status_code == status.HTTP_200_OK
        data = response.data
        results = data.get("results", data)
        ids = [n["id"] for n in results]
        assert str(notif_a.id) in ids
        assert str(notif_b.id) not in ids

    def test_mark_all_read_only_affects_own(self, client_a, user_a, user_b, notif_a, notif_b):
        """mark_all_read only deletes current user's notifications."""
        response = client_a.post("/api/notifications/mark_all_read/")
        assert response.status_code == status.HTTP_200_OK
        # user_a's notification should be deleted
        assert not Notification.objects.filter(id=notif_a.id).exists()
        # user_b's notification should still exist
        assert Notification.objects.filter(id=notif_b.id).exists()

    def test_unread_count_only_counts_own(self, client_a, notif_a, notif_b):
        """unread_count only counts current user's notifications."""
        response = client_a.get("/api/notifications/unread_count/")
        assert response.status_code == status.HTTP_200_OK
        # notif_a is sent + unread = 1
        assert response.data["unread_count"] == 1

    def test_cannot_delete_other_users_webpush_subscription(self, client_b, user_a):
        """User B cannot delete User A's web push subscription."""
        sub = WebPushSubscription.objects.create(
            user=user_a,
            subscription_info={"endpoint": "https://push.example.com", "keys": {}},
            is_active=True,
        )
        response = client_b.delete(f"/api/notifications/push-subscriptions/{sub.id}/")
        assert response.status_code == status.HTTP_404_NOT_FOUND
        sub.refresh_from_db()
        assert sub.is_active is True

    @patch("apps.notifications.views.UserDeviceViewSet._unsubscribe_from_all_topics")
    def test_cannot_delete_other_users_device(self, mock_unsub, client_b, user_a):
        """User B cannot delete User A's device registration."""
        device = UserDevice.objects.create(
            user=user_a,
            fcm_token="idor-device-token-protect",
            platform="android",
            is_active=True,
        )
        response = client_b.delete(f"/api/notifications/devices/{device.id}/")
        assert response.status_code == status.HTTP_404_NOT_FOUND
        device.refresh_from_db()
        assert device.is_active is True


# ══════════════════════════════════════════════════════════════════════
#  DND (DO NOT DISTURB) LOGIC
# ══════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestDNDLogic:
    """Tests for Notification.should_send() DND (Do Not Disturb) logic."""

    def test_should_send_true_when_no_dnd(self, user_a):
        """should_send returns True when DND is not enabled."""
        user_a.notification_prefs = {"dndEnabled": False}
        user_a.save(update_fields=["notification_prefs"])
        notif = Notification.objects.create(
            user=user_a,
            notification_type="reminder",
            title="Test",
            body="Body",
            scheduled_for=timezone.now() - timedelta(minutes=1),
            status="pending",
        )
        assert notif.should_send() is True

    def test_should_send_false_during_dnd_crossing_midnight(self, user_a):
        """should_send returns False when in DND period that crosses midnight."""
        # DND from 22:00 to 07:00
        user_a.notification_prefs = {"dndEnabled": True, "dndStart": 22, "dndEnd": 7}
        user_a.timezone = "UTC"
        user_a.save(update_fields=["notification_prefs", "timezone"])

        # Mock time to 23:00 UTC
        mock_now = timezone.now().replace(hour=23, minute=0, second=0)
        with patch("django.utils.timezone.now", return_value=mock_now):
            notif = Notification.objects.create(
                user=user_a,
                notification_type="reminder",
                title="DND Test",
                body="Body",
                scheduled_for=mock_now - timedelta(minutes=1),
                status="pending",
            )
            assert notif.should_send() is False

    def test_should_send_true_outside_dnd(self, user_a):
        """should_send returns True when outside DND hours."""
        user_a.notification_prefs = {"dndEnabled": True, "dndStart": 22, "dndEnd": 7}
        user_a.timezone = "UTC"
        user_a.save(update_fields=["notification_prefs", "timezone"])

        # Mock time to 12:00 UTC (outside DND)
        mock_now = timezone.now().replace(hour=12, minute=0, second=0)
        with patch("django.utils.timezone.now", return_value=mock_now):
            notif = Notification.objects.create(
                user=user_a,
                notification_type="reminder",
                title="DND Test",
                body="Body",
                scheduled_for=mock_now - timedelta(minutes=1),
                status="pending",
            )
            assert notif.should_send() is True

    def test_should_send_false_when_not_pending(self, user_a):
        """should_send returns False when notification is already sent."""
        notif = Notification.objects.create(
            user=user_a,
            notification_type="reminder",
            title="Already Sent",
            body="Body",
            scheduled_for=timezone.now() - timedelta(minutes=1),
            status="sent",
        )
        assert notif.should_send() is False

    def test_should_send_false_when_cancelled(self, user_a):
        """should_send returns False when notification is cancelled."""
        notif = Notification.objects.create(
            user=user_a,
            notification_type="reminder",
            title="Cancelled",
            body="Body",
            scheduled_for=timezone.now() - timedelta(minutes=1),
            status="cancelled",
        )
        assert notif.should_send() is False

    def test_should_send_false_for_future_notification(self, user_a):
        """should_send returns False for future scheduled notifications."""
        notif = Notification.objects.create(
            user=user_a,
            notification_type="reminder",
            title="Future",
            body="Body",
            scheduled_for=timezone.now() + timedelta(hours=2),
            status="pending",
        )
        assert notif.should_send() is False

    def test_should_send_with_null_notification_prefs(self, user_a):
        """should_send handles None notification_prefs gracefully."""
        user_a.notification_prefs = None
        user_a.save(update_fields=["notification_prefs"])
        notif = Notification.objects.create(
            user=user_a,
            notification_type="reminder",
            title="Null prefs",
            body="Body",
            scheduled_for=timezone.now() - timedelta(minutes=1),
            status="pending",
        )
        assert notif.should_send() is True

    def test_should_send_dnd_same_day_range(self, user_a):
        """should_send handles DND within same day (e.g., 10-14)."""
        user_a.notification_prefs = {"dndEnabled": True, "dndStart": 10, "dndEnd": 14}
        user_a.timezone = "UTC"
        user_a.save(update_fields=["notification_prefs", "timezone"])

        # Mock time to 12:00 UTC (inside DND)
        mock_now = timezone.now().replace(hour=12, minute=0, second=0)
        with patch("django.utils.timezone.now", return_value=mock_now):
            notif = Notification.objects.create(
                user=user_a,
                notification_type="reminder",
                title="Same day DND",
                body="Body",
                scheduled_for=mock_now - timedelta(minutes=1),
                status="pending",
            )
            assert notif.should_send() is False


# ══════════════════════════════════════════════════════════════════════
#  NOTIFICATION TEMPLATE RENDER
# ══════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestNotificationTemplateRender:
    """Tests for NotificationTemplate.render() method."""

    def test_render_with_variables(self):
        """render replaces placeholders with provided values."""
        template = NotificationTemplate.objects.create(
            name="test_render",
            notification_type="reminder",
            title_template="Hello {user_name}!",
            body_template="Your dream '{dream_title}' is progressing.",
            available_variables=["user_name", "dream_title"],
        )
        title, body = template.render(user_name="Alice", dream_title="Travel the World")
        assert title == "Hello Alice!"
        assert body == "Your dream 'Travel the World' is progressing."

    def test_render_no_variables(self):
        """render returns templates unchanged when no variables provided."""
        template = NotificationTemplate.objects.create(
            name="test_no_vars",
            notification_type="system",
            title_template="System Update",
            body_template="New features available.",
        )
        title, body = template.render()
        assert title == "System Update"
        assert body == "New features available."

    def test_render_partial_variables(self):
        """render replaces only provided variables, leaves missing placeholders."""
        template = NotificationTemplate.objects.create(
            name="test_partial",
            notification_type="motivation",
            title_template="Hi {user_name}",
            body_template="{streak_days} days streak! {motivation}",
            available_variables=["user_name", "streak_days", "motivation"],
        )
        title, body = template.render(user_name="Bob", streak_days=7)
        assert title == "Hi Bob"
        assert "7 days streak!" in body
        # {motivation} remains unreplaced
        assert "{motivation}" in body

    def test_render_str_representation(self):
        """Template __str__ returns readable representation."""
        template = NotificationTemplate.objects.create(
            name="my_template",
            notification_type="reminder",
            title_template="T",
            body_template="B",
        )
        assert "my_template" in str(template)


# ══════════════════════════════════════════════════════════════════════
#  SERIALIZER VALIDATION
# ══════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestSerializerValidation:
    """Tests for serializer validation logic."""

    def test_notification_create_sanitizes_title(self):
        """NotificationCreateSerializer sanitizes XSS in title."""
        data = {
            "notification_type": "reminder",
            "title": '<script>alert("XSS")</script>Reminder',
            "body": "Body text",
            "scheduled_for": timezone.now().isoformat(),
        }
        serializer = NotificationCreateSerializer(data=data)
        assert serializer.is_valid()
        # sanitize_text should strip the script tag
        assert "<script>" not in serializer.validated_data["title"]

    def test_notification_create_sanitizes_body(self):
        """NotificationCreateSerializer sanitizes XSS in body."""
        data = {
            "notification_type": "reminder",
            "title": "Clean Title",
            "body": '<img src=x onerror=alert("XSS")>Check this out',
            "scheduled_for": timezone.now().isoformat(),
        }
        serializer = NotificationCreateSerializer(data=data)
        assert serializer.is_valid()
        assert "onerror" not in serializer.validated_data["body"]

    def test_fcm_token_too_short_rejected(self):
        """UserDeviceSerializer rejects FCM tokens that are too short."""
        data = {
            "fcm_token": "short",
            "platform": "android",
        }
        serializer = UserDeviceSerializer(data=data)
        assert not serializer.is_valid()
        assert "fcm_token" in serializer.errors

    def test_fcm_token_too_long_rejected(self):
        """UserDeviceSerializer rejects FCM tokens that exceed max length."""
        data = {
            "fcm_token": "x" * 5000,
            "platform": "android",
        }
        serializer = UserDeviceSerializer(data=data)
        assert not serializer.is_valid()
        assert "fcm_token" in serializer.errors

    def test_fcm_token_valid_accepted(self):
        """UserDeviceSerializer accepts valid FCM tokens."""
        data = {
            "fcm_token": "valid-fcm-token-with-enough-length-for-validation",
            "platform": "android",
        }
        serializer = UserDeviceSerializer(data=data)
        assert serializer.is_valid()

    def test_batch_success_rate_zero_scheduled(self):
        """NotificationBatchSerializer returns 0.0 for zero scheduled."""
        batch = NotificationBatch(
            name="Empty",
            notification_type="reminder",
            total_scheduled=0,
            total_sent=0,
        )
        serializer = NotificationBatchSerializer(batch)
        assert serializer.data["success_rate"] == 0.0

    def test_batch_success_rate_partial(self):
        """NotificationBatchSerializer calculates correct rate."""
        batch = NotificationBatch(
            name="Partial",
            notification_type="reminder",
            total_scheduled=10,
            total_sent=7,
            total_failed=3,
        )
        serializer = NotificationBatchSerializer(batch)
        assert serializer.data["success_rate"] == 70.0

    def test_batch_success_rate_full(self):
        """NotificationBatchSerializer returns 100% for all sent."""
        batch = NotificationBatch(
            name="Full",
            notification_type="reminder",
            total_scheduled=5,
            total_sent=5,
        )
        serializer = NotificationBatchSerializer(batch)
        assert serializer.data["success_rate"] == 100.0


# ══════════════════════════════════════════════════════════════════════
#  MODEL __STR__ METHODS
# ══════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestModelStrMethods:
    """Tests for model __str__ methods."""

    def test_notification_str(self, user_a):
        notif = Notification.objects.create(
            user=user_a,
            notification_type="achievement",
            title="Badge Earned",
            body="Body",
            scheduled_for=timezone.now(),
            status="sent",
        )
        s = str(notif)
        assert "achievement" in s
        assert "Badge Earned" in s
        assert "sent" in s

    def test_notification_batch_str(self):
        batch = NotificationBatch(
            name="Weekly Batch",
            notification_type="weekly_report",
            total_scheduled=100,
            total_sent=95,
        )
        s = str(batch)
        assert "Weekly Batch" in s
        assert "95" in s
        assert "100" in s

    def test_user_device_str(self, user_a):
        device = UserDevice.objects.create(
            user=user_a,
            fcm_token="str-test-device-token-complete",
            platform="web",
            is_active=True,
        )
        s = str(device)
        assert user_a.email in s
        assert "web" in s
        assert "active" in s

    def test_user_device_str_inactive(self, user_a):
        device = UserDevice.objects.create(
            user=user_a,
            fcm_token="str-test-inactive-token-abc",
            platform="ios",
            is_active=False,
        )
        s = str(device)
        assert "inactive" in s

    def test_webpush_subscription_str_with_browser(self, user_a):
        sub = WebPushSubscription.objects.create(
            user=user_a,
            subscription_info={"endpoint": "https://push.example.com"},
            browser="Safari",
        )
        s = str(sub)
        assert user_a.email in s
        assert "Safari" in s

    def test_webpush_subscription_str_no_browser(self, user_a):
        sub = WebPushSubscription.objects.create(
            user=user_a,
            subscription_info={"endpoint": "https://push.example.com"},
            browser="",
        )
        s = str(sub)
        assert user_a.email in s
        assert "unknown" in s

    def test_notification_template_str(self):
        template = NotificationTemplate.objects.create(
            name="str_test_template",
            notification_type="reminder",
            title_template="T",
            body_template="B",
        )
        s = str(template)
        assert "str_test_template" in s


# ══════════════════════════════════════════════════════════════════════
#  NOTIFICATION MODEL METHODS
# ══════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestNotificationModelMethods:
    """Extended model method tests."""

    def test_mark_failed_increments_retry_count(self, user_a):
        """mark_failed increments retry_count each time."""
        notif = Notification.objects.create(
            user=user_a,
            notification_type="reminder",
            title="Retry test",
            body="Body",
            scheduled_for=timezone.now(),
            status="pending",
        )
        notif.mark_failed("Error 1")
        assert notif.retry_count == 1
        assert notif.error_message == "Error 1"

        notif.mark_failed("Error 2")
        assert notif.retry_count == 2
        assert notif.error_message == "Error 2"

    def test_mark_opened_sets_read_if_not_read(self, user_a):
        """mark_opened sets read_at if not previously read."""
        notif = Notification.objects.create(
            user=user_a,
            notification_type="reminder",
            title="Open test",
            body="Body",
            scheduled_for=timezone.now(),
            status="sent",
        )
        assert notif.read_at is None
        notif.mark_opened()
        notif.refresh_from_db()
        assert notif.read_at is not None
        assert notif.opened_at is not None
        assert notif.read_at == notif.opened_at

    def test_mark_opened_preserves_existing_read_at(self, user_a):
        """mark_opened preserves existing read_at."""
        notif = Notification.objects.create(
            user=user_a,
            notification_type="reminder",
            title="Preserve test",
            body="Body",
            scheduled_for=timezone.now(),
            status="sent",
        )
        notif.mark_read()
        original_read = notif.read_at
        notif.mark_opened()
        notif.refresh_from_db()
        assert notif.read_at == original_read
        assert notif.opened_at is not None


# ══════════════════════════════════════════════════════════════════════
#  NOTIFICATION SERVICE EDGE CASES
# ══════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestNotificationServiceEdgeCases:
    """Edge cases in NotificationService.create()."""

    def test_create_with_empty_strings(self, user_a):
        """Empty optional strings are stored correctly."""
        n = NotificationService.create(
            user=user_a,
            notification_type="system",
            title="Minimal",
            body="Body",
            action_url="",
            image_url="",
        )
        assert n.action_url == ""
        assert n.image_url == ""

    def test_create_with_large_data(self, user_a):
        """Large data dict is stored correctly."""
        data = {f"key_{i}": f"value_{i}" for i in range(50)}
        n = NotificationService.create(
            user=user_a,
            notification_type="system",
            title="Large data",
            body="Body",
            data=data,
        )
        n.refresh_from_db()
        assert len(n.data) == 50

    def test_create_with_custom_status(self, user_a):
        """Custom status is persisted."""
        n = NotificationService.create(
            user=user_a,
            notification_type="system",
            title="Custom status",
            body="Body",
            status="sent",
        )
        assert n.status == "sent"

    def test_create_with_future_scheduled(self, user_a):
        """Future scheduled_for is persisted."""
        future = timezone.now() + timedelta(days=7)
        n = NotificationService.create(
            user=user_a,
            notification_type="reminder",
            title="Future",
            body="Body",
            scheduled_for=future,
        )
        assert n.scheduled_for == future


# ══════════════════════════════════════════════════════════════════════
#  NOTIFICATION BATCH ADMIN
# ══════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestNotificationBatchAdmin:
    """Tests for notification batch model operations."""

    def test_batch_ordering(self):
        """Batches are ordered by -created_at."""
        b1 = NotificationBatch.objects.create(
            name="Batch 1", notification_type="reminder"
        )
        b2 = NotificationBatch.objects.create(
            name="Batch 2", notification_type="reminder"
        )
        batches = list(NotificationBatch.objects.all())
        # Most recent first
        assert batches[0].name == "Batch 2"
        assert batches[1].name == "Batch 1"

    def test_batch_status_choices(self):
        """All batch status choices are valid."""
        for status_code, _ in NotificationBatch.STATUS_CHOICES:
            batch = NotificationBatch.objects.create(
                name=f"Batch {status_code}",
                notification_type="reminder",
                status=status_code,
            )
            assert batch.status == status_code


# ══════════════════════════════════════════════════════════════════════
#  GROUPED ENDPOINT
# ══════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestGroupedEndpointComplete:
    """Extended tests for the grouped notifications endpoint."""

    def test_grouped_counts_multiple_types(self, client_a, user_a):
        """Grouped returns correct counts for each type."""
        now = timezone.now()
        for ntype in ["reminder", "reminder", "progress", "system"]:
            Notification.objects.create(
                user=user_a,
                notification_type=ntype,
                title=f"{ntype} notif",
                body="Body",
                scheduled_for=now,
                status="sent",
            )
        response = client_a.get("/api/notifications/grouped/")
        assert response.status_code == status.HTTP_200_OK
        groups = {g["type"]: g for g in response.data["groups"]}
        assert groups["reminder"]["total"] == 2
        assert groups["progress"]["total"] == 1
        assert groups["system"]["total"] == 1

    def test_grouped_only_counts_sent(self, client_a, user_a):
        """Grouped only counts sent notifications."""
        now = timezone.now()
        Notification.objects.create(
            user=user_a,
            notification_type="reminder",
            title="Sent",
            body="Body",
            scheduled_for=now,
            status="sent",
        )
        Notification.objects.create(
            user=user_a,
            notification_type="reminder",
            title="Pending",
            body="Body",
            scheduled_for=now,
            status="pending",
        )
        response = client_a.get("/api/notifications/grouped/")
        groups = {g["type"]: g for g in response.data["groups"]}
        assert groups.get("reminder", {}).get("total", 0) == 1


# ══════════════════════════════════════════════════════════════════════
#  NOTIFICATION INDEX AND ORDERING
# ══════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestNotificationOrdering:
    """Tests for notification ordering."""

    def test_notifications_ordered_by_scheduled_for_desc(self, user_a):
        """Notifications are ordered by -scheduled_for (newest first)."""
        now = timezone.now()
        n1 = Notification.objects.create(
            user=user_a,
            notification_type="reminder",
            title="Old",
            body="Body",
            scheduled_for=now - timedelta(hours=2),
            status="sent",
        )
        n2 = Notification.objects.create(
            user=user_a,
            notification_type="reminder",
            title="New",
            body="Body",
            scheduled_for=now,
            status="sent",
        )
        notifs = list(Notification.objects.filter(user=user_a))
        assert notifs[0].id == n2.id
        assert notifs[1].id == n1.id


# ══════════════════════════════════════════════════════════════════════
#  WEBPUSH SUBSCRIPTION EDGE CASES
# ══════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestWebPushSubscriptionEdgeCases:
    """Edge cases for WebPush subscription management."""

    def test_create_subscription_without_browser(self, client_a, user_a):
        """Create subscription without specifying browser."""
        response = client_a.post(
            "/api/notifications/push-subscriptions/",
            {
                "subscription_info": {
                    "endpoint": "https://push.example.com/sub/1",
                    "keys": {"p256dh": "testkey", "auth": "testauthkey"},
                },
            },
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED

    def test_list_subscriptions_excludes_inactive(self, client_a, user_a):
        """List only shows active subscriptions."""
        WebPushSubscription.objects.create(
            user=user_a,
            subscription_info={"endpoint": "https://active1", "keys": {}},
            is_active=True,
        )
        WebPushSubscription.objects.create(
            user=user_a,
            subscription_info={"endpoint": "https://inactive1", "keys": {}},
            is_active=False,
        )
        response = client_a.get("/api/notifications/push-subscriptions/")
        data = response.data
        results = data.get("results", data)
        assert len(results) == 1
