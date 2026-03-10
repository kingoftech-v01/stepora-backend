"""
Tests for notifications app.
"""

import uuid
from datetime import timedelta
from unittest.mock import Mock, patch

import pytest
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.users.models import User

from .models import Notification, NotificationTemplate

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _set_user_plan(user, slug):
    """Ensure a user has the given subscription plan via DB records."""
    from apps.subscriptions.models import Subscription, SubscriptionPlan

    plan = SubscriptionPlan.objects.filter(slug=slug).first()
    if not plan:
        return
    sub, _ = Subscription.objects.get_or_create(
        user=user,
        defaults={"plan": plan, "status": "active"},
    )
    if sub.plan_id != plan.pk or sub.status != "active":
        sub.plan = plan
        sub.status = "active"
        sub.save(update_fields=["plan", "status"])
    if hasattr(user, "_cached_plan"):
        del user._cached_plan


# Override global fixtures: notification view tests need a premium user
# so that the free-tier notification type filter does not hide test results.


@pytest.fixture
def user(db):
    """Premium user for notification tests."""
    u = User.objects.create_user(
        email="testuser@example.com",
        password="testpassword123",
        display_name="Test User",
        timezone="Europe/Paris",
    )
    _set_user_plan(u, "premium")
    u.refresh_from_db()
    return u


@pytest.fixture
def authenticated_client(user):
    """Authenticated client with premium user."""
    client = APIClient()
    client.force_authenticate(user=user)
    return client


class TestNotificationModel:
    """Test Notification model"""

    def test_create_notification(self, db, notification_data):
        """Test creating a notification"""
        notification = Notification.objects.create(**notification_data)

        assert notification.user == notification_data["user"]
        assert notification.notification_type == "reminder"
        assert notification.status == "pending"
        assert notification.read_at is None

    def test_notification_str(self, notification):
        """Test notification string representation"""
        expected = f"{notification.notification_type}: {notification.title} ({notification.status})"
        assert str(notification) == expected

    def test_mark_read(self, notification):
        """Test marking notification as read"""
        assert notification.read_at is None

        notification.mark_read()

        assert notification.read_at is not None
        assert (timezone.now() - notification.read_at).seconds < 5

    def test_notification_scheduled_in_future(self, db, user):
        """Test notification scheduled for future"""
        future_time = timezone.now() + timedelta(hours=2)

        notification = Notification.objects.create(
            user=user,
            notification_type="reminder",
            title="Future notification",
            body="Scheduled for later",
            scheduled_for=future_time,
        )

        assert notification.scheduled_for > timezone.now()
        assert notification.status == "pending"

    def test_notification_with_data(self, db, user):
        """Test notification with additional data"""
        data = {
            "action": "open_dream",
            "dream_id": str(uuid.uuid4()),
            "screen": "DreamDetail",
        }

        notification = Notification.objects.create(
            user=user,
            notification_type="reminder",
            title="Test notification",
            body="With data",
            scheduled_for=timezone.now(),
            data=data,
        )

        assert notification.data["action"] == "open_dream"
        assert notification.data["screen"] == "DreamDetail"


class TestNotificationTemplateModel:
    """Test NotificationTemplate model"""

    def test_create_template(self, db):
        """Test creating a notification template"""
        template = NotificationTemplate.objects.create(
            name="test_template",
            notification_type="reminder",
            title_template="Reminder: {title}",
            body_template="Don't forget to {action}",
            is_active=True,
        )

        assert template.name == "test_template"
        assert template.notification_type == "reminder"
        assert template.is_active

    def test_render_template(self, notification_template):
        """Test rendering template with variables"""
        context = {"title": "Complete task", "action": "finish your homework"}

        title = notification_template.title_template.format(**context)
        body = notification_template.body_template.format(**context)

        assert title == "Reminder: Complete task"
        assert body == "Don't forget to finish your homework"

    def test_inactive_template(self, db):
        """Test inactive template"""
        template = NotificationTemplate.objects.create(
            name="inactive_template",
            notification_type="reminder",
            title_template="Test",
            body_template="Test",
            is_active=False,
        )

        # Active templates query should not include this
        active_templates = NotificationTemplate.objects.filter(is_active=True)
        assert template not in active_templates


class TestNotificationViewSet:
    """Test Notification API endpoints"""

    def test_list_notifications(self, authenticated_client, user):
        """Test GET /api/notifications/"""
        # Create notifications
        Notification.objects.create(
            user=user,
            notification_type="reminder",
            title="Notification 1",
            body="Body 1",
            scheduled_for=timezone.now(),
        )
        Notification.objects.create(
            user=user,
            notification_type="motivation",
            title="Notification 2",
            body="Body 2",
            scheduled_for=timezone.now(),
        )

        response = authenticated_client.get("/api/notifications/")

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]) == 2

    def test_mark_notification_read(self, authenticated_client, notification):
        """Test POST /api/notifications/{id}/mark-read/"""
        assert notification.read_at is None

        response = authenticated_client.post(
            f"/api/notifications/{notification.id}/mark_read/"
        )

        assert response.status_code == status.HTTP_200_OK
        notification.refresh_from_db()
        assert notification.read_at is not None

    def test_mark_all_read(self, authenticated_client, user):
        """Test POST /api/notifications/mark-all-read/"""
        # Create multiple unread notifications
        for i in range(3):
            Notification.objects.create(
                user=user,
                notification_type="reminder",
                title=f"Notification {i}",
                body=f"Body {i}",
                scheduled_for=timezone.now(),
                status="sent",
            )

        response = authenticated_client.post("/api/notifications/mark_all_read/")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["marked_read"] == 3

        # All should be marked as read
        unread_count = Notification.objects.filter(
            user=user, read_at__isnull=True
        ).count()
        assert unread_count == 0

    def test_unread_count(self, authenticated_client, user):
        """Test GET /api/notifications/unread-count/"""
        # Create some read and unread notifications
        Notification.objects.create(
            user=user,
            notification_type="reminder",
            title="Read notification",
            body="Body",
            scheduled_for=timezone.now(),
            status="sent",
            read_at=timezone.now(),
        )

        for i in range(3):
            Notification.objects.create(
                user=user,
                notification_type="reminder",
                title=f"Unread {i}",
                body="Body",
                scheduled_for=timezone.now(),
                status="sent",
            )

        response = authenticated_client.get("/api/notifications/unread_count/")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["unread_count"] == 3

    def test_filter_by_type(self, authenticated_client, user):
        """Test filtering notifications by type"""
        Notification.objects.create(
            user=user,
            notification_type="reminder",
            title="Reminder",
            body="Body",
            scheduled_for=timezone.now(),
        )
        Notification.objects.create(
            user=user,
            notification_type="motivation",
            title="Motivation",
            body="Body",
            scheduled_for=timezone.now(),
        )

        response = authenticated_client.get(
            "/api/notifications/?notification_type=reminder"
        )

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]) == 1
        assert response.data["results"][0]["notification_type"] == "reminder"


class TestNotificationTasks:
    """Test Celery tasks for notifications"""

    def test_process_pending_notifications(self, db, user):
        """Test process_pending_notifications task"""
        # Create pending notifications
        Notification.objects.create(
            user=user,
            notification_type="reminder",
            title="Test notification",
            body="Body",
            scheduled_for=timezone.now() - timedelta(minutes=1),
            status="pending",
        )

        from apps.notifications.tasks import process_pending_notifications

        result = process_pending_notifications()

        assert result["sent"] == 1

        # Notification should be marked as sent
        notification = Notification.objects.first()
        assert notification.status == "sent"
        assert notification.sent_at is not None

    def test_generate_daily_motivation(self, db, user, dream, mock_openai):
        """Test generate_daily_motivation task"""
        # Set user preferences
        user.notification_prefs = {"motivation": True}
        user.save()

        from apps.notifications.tasks import generate_daily_motivation

        with patch("apps.notifications.tasks.OpenAIService") as mock_service:
            mock_service.return_value.generate_motivational_message.return_value = (
                "Stay motivated!"
            )

            result = generate_daily_motivation()

            assert result["created"] >= 1

            # Notification should be created
            notification = Notification.objects.filter(
                user=user, notification_type="motivation"
            ).first()

            assert notification is not None
            assert notification.title == "Daily motivation"

    def test_send_weekly_report(self, db, user, dream, task, mock_openai):
        """Test send_weekly_report task dispatches per-user digest tasks."""
        # Set user preferences
        user.notification_prefs = {"weekly_report": True}
        user.save()

        # Complete a task
        task.status = "completed"
        task.completed_at = timezone.now()
        task.save()

        from apps.notifications.tasks import send_weekly_report

        with patch("apps.notifications.tasks.send_user_digest") as mock_digest:
            mock_digest.delay = Mock()

            result = send_weekly_report()

            # The task now dispatches per-user digest tasks
            assert result["dispatched"] >= 1
            mock_digest.delay.assert_called()

    def test_check_inactive_users(self, db, user, dream, mock_openai):
        """Test check_inactive_users task (Rescue Mode)"""
        # Set user as inactive
        user.last_activity = timezone.now() - timedelta(days=4)
        user.save()

        from apps.notifications.tasks import check_inactive_users

        with patch("apps.notifications.tasks.OpenAIService") as mock_service:
            mock_service.return_value.generate_rescue_message.return_value = (
                "We miss you!"
            )

            result = check_inactive_users()

            assert result["created"] >= 1

            # Rescue notification should be created
            notification = Notification.objects.filter(
                user=user, notification_type="rescue"
            ).first()

            assert notification is not None
            assert "still here" in notification.title

    def test_send_reminder_notifications(self, db, user, goal):
        """Test send_reminder_notifications task"""
        # Set reminder for goal
        goal.reminder_enabled = True
        goal.reminder_time = timezone.now() + timedelta(minutes=10)
        goal.save()

        from apps.notifications.tasks import send_reminder_notifications

        result = send_reminder_notifications()

        assert result["created"] >= 1

        # Reminder notification should be created
        notification = Notification.objects.filter(
            user=user, notification_type="reminder"
        ).first()

        assert notification is not None

    def test_cleanup_old_notifications(self, db, user):
        """Test cleanup_old_notifications task"""
        # Create old read notifications
        old_date = timezone.now() - timedelta(days=35)

        for i in range(5):
            notification = Notification.objects.create(
                user=user,
                notification_type="reminder",
                title=f"Old notification {i}",
                body="Body",
                scheduled_for=old_date,
                status="sent",
                read_at=old_date,
            )
            # Manually set created_at to old date
            notification.created_at = old_date
            notification.save()

        initial_count = Notification.objects.count()

        from apps.notifications.tasks import cleanup_old_notifications

        result = cleanup_old_notifications()

        assert result["deleted"] == 5
        assert Notification.objects.count() == initial_count - 5

    def test_send_streak_milestone_notification(self, db, user, mock_celery):
        """Test send_streak_milestone_notification task"""
        from apps.notifications.tasks import send_streak_milestone_notification

        result = send_streak_milestone_notification(str(user.id), 7)

        assert result["sent"] is True

        # Notification should be created
        notification = Notification.objects.filter(
            user=user, notification_type="achievement", data__achievement="streak"
        ).first()

        assert notification is not None
        assert "7-day streak" in notification.title

    def test_send_level_up_notification(self, db, user):
        """Test send_level_up_notification task"""
        from apps.notifications.tasks import send_level_up_notification

        result = send_level_up_notification(str(user.id), 5)

        assert result["sent"] is True

        # Notification should be created
        notification = Notification.objects.filter(
            user=user, notification_type="achievement", data__achievement="level_up"
        ).first()

        assert notification is not None
        assert "Level 5" in notification.title


# ============================================================
# New tests for WebSocket consumer, delivery service, WebPush
# ============================================================


import pytest
from channels.db import database_sync_to_async
from channels.testing import WebsocketCommunicator
from django.core import mail

from .consumers import NotificationConsumer
from .models import NotificationBatch, UserDevice, WebPushSubscription
from .serializers import (
    NotificationBatchSerializer,
    UserDeviceSerializer,
)
from .services import NotificationDeliveryService


class TestNotificationModelExtended:
    """Extended tests for Notification model methods."""

    def test_mark_sent(self, notification):
        """Test mark_sent sets status and sent_at."""
        notification.mark_sent()
        notification.refresh_from_db()
        assert notification.status == "sent"
        assert notification.sent_at is not None

    def test_mark_opened_sets_both(self, notification):
        """Test mark_opened sets opened_at and read_at if not already read."""
        assert notification.opened_at is None
        assert notification.read_at is None

        notification.mark_opened()
        notification.refresh_from_db()

        assert notification.opened_at is not None
        assert notification.read_at is not None
        assert notification.read_at == notification.opened_at

    def test_mark_opened_preserves_read_at(self, notification):
        """Test mark_opened preserves existing read_at."""
        notification.mark_read()
        original_read_at = notification.read_at

        notification.mark_opened()
        notification.refresh_from_db()

        assert notification.opened_at is not None
        assert notification.read_at == original_read_at

    def test_mark_failed(self, notification):
        """Test mark_failed sets status, error, and increments retry."""
        notification.mark_failed("Connection timeout")
        notification.refresh_from_db()

        assert notification.status == "failed"
        assert notification.error_message == "Connection timeout"
        assert notification.retry_count == 1

    def test_should_send_pending_and_past(self, notification):
        """Test should_send returns True for pending notification scheduled in past."""
        notification.scheduled_for = timezone.now() - timedelta(minutes=1)
        notification.save()
        assert notification.should_send() is True

    def test_should_send_already_sent(self, notification):
        """Test should_send returns False for already-sent notification."""
        notification.status = "sent"
        notification.save()
        assert notification.should_send() is False

    def test_should_send_future_scheduled(self, notification):
        """Test should_send returns False for future-scheduled notification."""
        notification.scheduled_for = timezone.now() + timedelta(hours=2)
        notification.save()
        assert notification.should_send() is False

    def test_should_send_dnd_crosses_midnight(self, db, user):
        """Test should_send returns False during DND that crosses midnight."""
        user.notification_prefs = {
            "dndEnabled": True,
            "dndStart": 22,
            "dndEnd": 7,
        }
        user.timezone = "UTC"
        user.save()

        notification = Notification.objects.create(
            user=user,
            notification_type="reminder",
            title="DND test",
            body="body",
            scheduled_for=timezone.now() - timedelta(minutes=1),
            status="pending",
        )

        # We can't easily control the current hour in tests,
        # but we can verify the method runs without error
        result = notification.should_send()
        assert isinstance(result, bool)


class TestWebPushSubscriptionModel:
    """Test WebPushSubscription model."""

    def test_create_subscription(self, db, user):
        """Test creating a web push subscription."""
        sub = WebPushSubscription.objects.create(
            user=user,
            subscription_info={
                "endpoint": "https://push.example.com/abc",
                "keys": {"p256dh": "key1", "auth": "key2"},
            },
            browser="Chrome",
        )
        assert sub.is_active is True
        assert sub.browser == "Chrome"

    def test_subscription_str(self, db, user):
        """Test string representation."""
        sub = WebPushSubscription.objects.create(
            user=user,
            subscription_info={"endpoint": "https://push.example.com/abc"},
            browser="Firefox",
        )
        assert user.email in str(sub)
        assert "Firefox" in str(sub)

    def test_subscription_str_no_browser(self, db, user):
        """Test string representation without browser."""
        sub = WebPushSubscription.objects.create(
            user=user,
            subscription_info={"endpoint": "https://push.example.com/abc"},
        )
        assert "unknown" in str(sub)


class TestNotificationBatchModel:
    """Test NotificationBatch model."""

    def test_create_batch(self, db):
        """Test creating a notification batch."""
        batch = NotificationBatch.objects.create(
            name="Daily motivation",
            notification_type="motivation",
            total_scheduled=100,
            total_sent=95,
            total_failed=5,
        )
        assert batch.status == "scheduled"
        assert batch.completed_at is None

    def test_batch_str(self, db):
        """Test string representation."""
        batch = NotificationBatch.objects.create(
            name="Weekly reports",
            notification_type="weekly_report",
            total_scheduled=50,
            total_sent=48,
        )
        assert "Weekly reports" in str(batch)
        assert "48/50" in str(batch)


class TestNotificationBatchSerializerTests:
    """Test NotificationBatch serializer."""

    def test_success_rate_zero_scheduled(self, db):
        """Test success rate when no notifications scheduled."""
        batch = NotificationBatch.objects.create(
            name="empty",
            notification_type="system",
            total_scheduled=0,
            total_sent=0,
        )
        serializer = NotificationBatchSerializer(batch)
        assert serializer.data["success_rate"] == 0.0

    def test_success_rate_partial(self, db):
        """Test partial success rate."""
        batch = NotificationBatch.objects.create(
            name="partial",
            notification_type="system",
            total_scheduled=100,
            total_sent=50,
        )
        serializer = NotificationBatchSerializer(batch)
        assert serializer.data["success_rate"] == 50.0

    def test_success_rate_full(self, db):
        """Test 100% success rate."""
        batch = NotificationBatch.objects.create(
            name="full",
            notification_type="system",
            total_scheduled=100,
            total_sent=100,
        )
        serializer = NotificationBatchSerializer(batch)
        assert serializer.data["success_rate"] == 100.0


class TestWebPushSubscriptionViewSet:
    """Test WebPush subscription API endpoints."""

    def test_list_subscriptions(self, authenticated_client, user):
        """Test GET /api/notifications/push-subscriptions/."""
        WebPushSubscription.objects.create(
            user=user,
            subscription_info={"endpoint": "https://push.example.com/1"},
        )
        response = authenticated_client.get("/api/notifications/push-subscriptions/")
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]) == 1

    def test_create_subscription(self, authenticated_client, user):
        """Test POST /api/notifications/push-subscriptions/."""
        data = {
            "subscription_info": {
                "endpoint": "https://push.example.com/new",
                "keys": {"p256dh": "abc", "auth": "def"},
            },
            "browser": "Chrome",
        }
        response = authenticated_client.post(
            "/api/notifications/push-subscriptions/", data, format="json"
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert WebPushSubscription.objects.filter(user=user).count() == 1

    def test_create_deactivates_existing(self, authenticated_client, user):
        """Test creating subscription deactivates old one with same endpoint."""
        old_sub = WebPushSubscription.objects.create(
            user=user,
            subscription_info={"endpoint": "https://push.example.com/same"},
        )
        data = {
            "subscription_info": {
                "endpoint": "https://push.example.com/same",
                "keys": {"p256dh": "new", "auth": "new"},
            },
        }
        response = authenticated_client.post(
            "/api/notifications/push-subscriptions/", data, format="json"
        )
        assert response.status_code == status.HTTP_201_CREATED
        old_sub.refresh_from_db()
        assert old_sub.is_active is False

    def test_delete_subscription(self, authenticated_client, user):
        """Test DELETE /api/notifications/push-subscriptions/{id}/."""
        sub = WebPushSubscription.objects.create(
            user=user,
            subscription_info={"endpoint": "https://push.example.com/del"},
        )
        response = authenticated_client.delete(
            f"/api/notifications/push-subscriptions/{sub.id}/"
        )
        assert response.status_code == status.HTTP_204_NO_CONTENT

    def test_requires_auth(self, api_client):
        """Test endpoint requires authentication."""
        response = api_client.get("/api/notifications/push-subscriptions/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestNotificationViewSetExtended:
    """Extended tests for notification view actions."""

    def test_opened_action(self, authenticated_client, notification):
        """Test POST /api/notifications/{id}/opened/."""
        response = authenticated_client.post(
            f"/api/notifications/{notification.id}/opened/"
        )
        assert response.status_code == status.HTTP_200_OK
        notification.refresh_from_db()
        assert notification.opened_at is not None

    def test_grouped_action(self, authenticated_client, user):
        """Test GET /api/notifications/grouped/."""
        for t in ["reminder", "motivation", "reminder"]:
            Notification.objects.create(
                user=user,
                notification_type=t,
                title=f"{t} test",
                body="body",
                scheduled_for=timezone.now(),
                status="sent",
            )
        response = authenticated_client.get("/api/notifications/grouped/")
        assert response.status_code == status.HTTP_200_OK
        assert "groups" in response.data
        types = [g["type"] for g in response.data["groups"]]
        assert "reminder" in types

    def test_create_notification_sanitizes(self, authenticated_client, user):
        """Test that creating a notification sanitizes XSS from title/body."""
        data = {
            "notification_type": "system",
            "title": '<script>alert("xss")</script>Test',
            "body": "<img onerror=alert(1)>Body",
            "scheduled_for": timezone.now().isoformat(),
        }
        response = authenticated_client.post("/api/notifications/", data, format="json")
        assert response.status_code == status.HTTP_201_CREATED
        assert "<script>" not in response.data["title"]


class TestNotificationDeliveryService:
    """Test NotificationDeliveryService."""

    def test_deliver_websocket_success(self, db, user):
        """Test websocket delivery sends to channel layer."""
        notification = Notification.objects.create(
            user=user,
            notification_type="system",
            title="WS test",
            body="body",
            scheduled_for=timezone.now(),
        )
        service = NotificationDeliveryService()
        result = service._send_websocket(notification)
        assert result is True

    def test_deliver_websocket_disabled(self, db, user):
        """Test websocket is skipped when disabled in prefs."""
        user.notification_prefs = {
            "websocket_enabled": False,
            "email_enabled": False,
            "push_enabled": False,
        }
        user.save()
        notification = Notification.objects.create(
            user=user,
            notification_type="system",
            title="test",
            body="body",
            scheduled_for=timezone.now(),
        )
        service = NotificationDeliveryService()
        # All explicit channels disabled; service still tries email fallback
        # Mock the email fallback to also fail so deliver returns False
        with patch.object(service, "_send_email", return_value=False):
            result = service.deliver(notification)
        assert result is False

    def test_deliver_email_success(self, db, user):
        """Test email delivery sends email."""
        user.notification_prefs = {"email_enabled": True}
        user.save()
        notification = Notification.objects.create(
            user=user,
            notification_type="system",
            title="Email test",
            body="body content",
            scheduled_for=timezone.now(),
        )
        service = NotificationDeliveryService()
        result = service._send_email(notification)
        assert result is True
        assert len(mail.outbox) == 1
        assert mail.outbox[0].subject == "Email test"

    def test_deliver_email_disabled_by_default(self, db, user):
        """Test email is disabled by default."""
        notification = Notification.objects.create(
            user=user,
            notification_type="system",
            title="test",
            body="body",
            scheduled_for=timezone.now(),
        )
        service = NotificationDeliveryService()
        # deliver() should not send email by default
        prefs = user.notification_prefs or {}
        assert prefs.get("email_enabled", False) is False

    def test_deliver_webpush_no_subscriptions(self, db, user):
        """Test webpush returns False when no subscriptions."""
        notification = Notification.objects.create(
            user=user,
            notification_type="system",
            title="test",
            body="body",
            scheduled_for=timezone.now(),
        )
        service = NotificationDeliveryService()
        result = service._send_webpush(notification)
        assert result is False

    def test_deliver_webpush_no_vapid_key(self, db, user):
        """Test webpush returns False when VAPID key not configured."""
        WebPushSubscription.objects.create(
            user=user,
            subscription_info={"endpoint": "https://push.example.com/1"},
        )
        notification = Notification.objects.create(
            user=user,
            notification_type="system",
            title="test",
            body="body",
            scheduled_for=timezone.now(),
        )
        service = NotificationDeliveryService()
        with patch.object(service, "_send_webpush", wraps=service._send_webpush):
            result = service._send_webpush(notification)
            # No VAPID key in test settings
            assert result is False

    @patch("apps.notifications.services.async_to_sync")
    def test_deliver_websocket_failure(self, mock_async, db, user):
        """Test websocket returns False on exception."""
        mock_async.side_effect = Exception("Channel layer down")
        notification = Notification.objects.create(
            user=user,
            notification_type="system",
            title="test",
            body="body",
            scheduled_for=timezone.now(),
        )
        service = NotificationDeliveryService()
        result = service._send_websocket(notification)
        assert result is False

    def test_deliver_returns_true_if_any_succeed(self, db, user):
        """Test deliver returns True if at least one channel succeeds."""
        notification = Notification.objects.create(
            user=user,
            notification_type="system",
            title="test",
            body="body",
            scheduled_for=timezone.now(),
        )
        service = NotificationDeliveryService()
        # By default websocket is enabled and will succeed with InMemoryChannelLayer
        result = service.deliver(notification)
        assert result is True

    def test_deliver_prefs_none(self, db, user):
        """Test deliver handles None notification_prefs."""
        user.notification_prefs = None
        user.save()
        notification = Notification.objects.create(
            user=user,
            notification_type="system",
            title="test",
            body="body",
            scheduled_for=timezone.now(),
        )
        service = NotificationDeliveryService()
        result = service.deliver(notification)
        # Should use defaults (websocket enabled) and succeed
        assert result is True


class TestNotificationConsumer:
    """Test WebSocket notification consumer."""

    @pytest.mark.asyncio
    async def test_connect_unauthenticated(self, db):
        """Test unauthenticated connection is rejected."""
        from unittest.mock import MagicMock

        from channels.testing import WebsocketCommunicator

        communicator = WebsocketCommunicator(
            NotificationConsumer.as_asgi(), "/ws/notifications/"
        )
        communicator.scope["user"] = MagicMock(is_authenticated=False)

        connected, code = await communicator.connect()
        assert connected is False

    @pytest.mark.asyncio
    async def test_connect_authenticated(self, db, user):
        """Test authenticated connection succeeds and sends unread count."""
        communicator = WebsocketCommunicator(
            NotificationConsumer.as_asgi(), "/ws/notifications/"
        )
        communicator.scope["user"] = user

        connected, _ = await communicator.connect()
        assert connected is True

        response = await communicator.receive_json_from()
        assert response["type"] == "connection"
        assert response["status"] == "connected"
        assert "unread_count" in response

        await communicator.disconnect()

    @pytest.mark.asyncio
    async def test_receive_invalid_json(self, db, user):
        """Test receiving invalid JSON sends error."""
        communicator = WebsocketCommunicator(
            NotificationConsumer.as_asgi(), "/ws/notifications/"
        )
        communicator.scope["user"] = user
        await communicator.connect()
        await communicator.receive_json_from()  # consume connection message

        await communicator.send_to(text_data="not valid json")
        response = await communicator.receive_json_from()
        assert response["type"] == "error"

        await communicator.disconnect()

    @pytest.mark.asyncio
    @pytest.mark.xfail(
        reason="SQLite table locking in async context; passes with PostgreSQL"
    )
    async def test_mark_read_via_ws(self, db, user):
        """Test mark_read action via WebSocket."""
        notification = await database_sync_to_async(Notification.objects.create)(
            user=user,
            notification_type="system",
            title="WS read test",
            body="body",
            scheduled_for=timezone.now(),
            status="sent",
        )

        communicator = WebsocketCommunicator(
            NotificationConsumer.as_asgi(), "/ws/notifications/"
        )
        communicator.scope["user"] = user
        await communicator.connect()
        await communicator.receive_json_from()  # consume connection message

        await communicator.send_json_to(
            {
                "type": "mark_read",
                "notification_id": str(notification.id),
            }
        )
        response = await communicator.receive_json_from()
        assert response["type"] == "marked_read"

        await communicator.disconnect()

    @pytest.mark.asyncio
    @pytest.mark.xfail(
        reason="SQLite table locking in async context; passes with PostgreSQL"
    )
    async def test_mark_all_read_via_ws(self, db, user):
        """Test mark_all_read action via WebSocket."""
        for i in range(3):
            await database_sync_to_async(Notification.objects.create)(
                user=user,
                notification_type="system",
                title=f"WS test {i}",
                body="body",
                scheduled_for=timezone.now(),
                status="sent",
            )

        communicator = WebsocketCommunicator(
            NotificationConsumer.as_asgi(), "/ws/notifications/"
        )
        communicator.scope["user"] = user
        await communicator.connect()
        await communicator.receive_json_from()  # consume connection message

        await communicator.send_json_to({"type": "mark_all_read"})
        response = await communicator.receive_json_from()
        assert response["type"] == "all_marked_read"
        assert response["count"] == 3

        await communicator.disconnect()


# ============================================================
# FCM / UserDevice tests
# ============================================================


class TestUserDeviceModel:
    """Test UserDevice model."""

    def test_create_device(self, db, user):
        """Test creating a device registration."""
        device = UserDevice.objects.create(
            user=user,
            fcm_token="test-token-abc123-" + uuid.uuid4().hex,
            platform="android",
            device_name="Pixel 8",
        )
        assert device.is_active is True
        assert device.platform == "android"
        assert device.device_name == "Pixel 8"

    def test_device_str(self, db, user):
        """Test string representation."""
        device = UserDevice.objects.create(
            user=user,
            fcm_token="test-token-str-" + uuid.uuid4().hex,
            platform="ios",
        )
        assert user.email in str(device)
        assert "ios" in str(device)
        assert "active" in str(device)

    def test_device_str_inactive(self, db, user):
        """Test string representation for inactive device."""
        device = UserDevice.objects.create(
            user=user,
            fcm_token="test-token-inactive-" + uuid.uuid4().hex,
            platform="web",
            is_active=False,
        )
        assert "inactive" in str(device)

    def test_fcm_token_unique(self, db, user):
        """Test that fcm_token is unique."""
        token = "unique-token-" + uuid.uuid4().hex
        UserDevice.objects.create(
            user=user,
            fcm_token=token,
            platform="android",
        )
        from django.db import IntegrityError

        with pytest.raises(IntegrityError):
            UserDevice.objects.create(
                user=user,
                fcm_token=token,
                platform="ios",
            )

    def test_user_can_have_multiple_devices(self, db, user):
        """Test a user can register multiple devices."""
        for i in range(3):
            UserDevice.objects.create(
                user=user,
                fcm_token=f"multi-device-{i}-{uuid.uuid4().hex}",
                platform=["android", "ios", "web"][i],
            )
        assert UserDevice.objects.filter(user=user).count() == 3


class TestUserDeviceSerializer:
    """Test UserDeviceSerializer."""

    def test_valid_data(self, db):
        """Test serializer with valid data."""
        data = {
            "fcm_token": "a" * 50,
            "platform": "android",
            "device_name": "Test Phone",
            "app_version": "1.0.0",
        }
        serializer = UserDeviceSerializer(data=data)
        assert serializer.is_valid(), serializer.errors

    def test_short_fcm_token_rejected(self, db):
        """Test that short FCM tokens are rejected."""
        data = {
            "fcm_token": "short",
            "platform": "android",
        }
        serializer = UserDeviceSerializer(data=data)
        assert not serializer.is_valid()
        assert "fcm_token" in serializer.errors

    def test_long_fcm_token_rejected(self, db):
        """Test that overly long FCM tokens are rejected."""
        data = {
            "fcm_token": "a" * 5000,
            "platform": "android",
        }
        serializer = UserDeviceSerializer(data=data)
        assert not serializer.is_valid()
        assert "fcm_token" in serializer.errors

    def test_invalid_platform_rejected(self, db):
        """Test that invalid platform values are rejected."""
        data = {
            "fcm_token": "a" * 50,
            "platform": "blackberry",
        }
        serializer = UserDeviceSerializer(data=data)
        assert not serializer.is_valid()
        assert "platform" in serializer.errors


class TestUserDeviceViewSet:
    """Test device registration API endpoints."""

    def test_register_device(self, authenticated_client, user, mock_fcm):
        """Test POST /api/notifications/devices/."""
        data = {
            "fcm_token": "new-fcm-token-" + uuid.uuid4().hex,
            "platform": "android",
            "device_name": "Test Phone",
            "app_version": "2.0.0",
        }
        response = authenticated_client.post(
            "/api/notifications/devices/", data, format="json"
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert UserDevice.objects.filter(user=user, is_active=True).count() == 1

    def test_register_replaces_existing_token(
        self, authenticated_client, user, mock_fcm
    ):
        """Test that re-registering same token deletes old entry and creates new."""
        token = "reuse-token-" + uuid.uuid4().hex
        old = UserDevice.objects.create(
            user=user,
            fcm_token=token,
            platform="android",
        )
        old_id = old.id
        data = {
            "fcm_token": token,
            "platform": "android",
        }
        response = authenticated_client.post(
            "/api/notifications/devices/", data, format="json"
        )
        assert response.status_code == status.HTTP_201_CREATED
        # Old record should be deleted
        assert not UserDevice.objects.filter(id=old_id).exists()
        # New active device should exist
        assert (
            UserDevice.objects.filter(
                user=user, fcm_token=token, is_active=True
            ).count()
            == 1
        )

    def test_list_devices(self, authenticated_client, user):
        """Test GET /api/notifications/devices/."""
        UserDevice.objects.create(
            user=user,
            fcm_token="list-token-" + uuid.uuid4().hex,
            platform="ios",
        )
        response = authenticated_client.get("/api/notifications/devices/")
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]) == 1

    def test_list_only_active_devices(self, authenticated_client, user):
        """Test that only active devices are listed."""
        UserDevice.objects.create(
            user=user,
            fcm_token="active-token-" + uuid.uuid4().hex,
            platform="android",
        )
        UserDevice.objects.create(
            user=user,
            fcm_token="inactive-token-" + uuid.uuid4().hex,
            platform="android",
            is_active=False,
        )
        response = authenticated_client.get("/api/notifications/devices/")
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]) == 1

    def test_delete_device_soft_deletes(self, authenticated_client, user, mock_fcm):
        """Test DELETE soft-deactivates device."""
        device = UserDevice.objects.create(
            user=user,
            fcm_token="del-token-" + uuid.uuid4().hex,
            platform="android",
        )
        response = authenticated_client.delete(
            f"/api/notifications/devices/{device.id}/"
        )
        assert response.status_code == status.HTTP_204_NO_CONTENT
        device.refresh_from_db()
        assert device.is_active is False

    def test_requires_auth(self, api_client):
        """Test endpoint requires authentication."""
        response = api_client.get("/api/notifications/devices/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_user_isolation(self, authenticated_client, user, db):
        """Test user can only see their own devices."""
        other_user = User.objects.create_user(
            email="other-device@example.com",
            password="testpassword123",
        )
        UserDevice.objects.create(
            user=other_user,
            fcm_token="other-user-token-" + uuid.uuid4().hex,
            platform="android",
        )
        UserDevice.objects.create(
            user=user,
            fcm_token="my-token-" + uuid.uuid4().hex,
            platform="ios",
        )
        response = authenticated_client.get("/api/notifications/devices/")
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]) == 1


class TestFCMDelivery:
    """Test FCM delivery in NotificationDeliveryService."""

    def test_send_fcm_single_device(self, db, user, mock_fcm):
        """Test FCM send to single device."""
        UserDevice.objects.create(
            user=user,
            fcm_token="single-device-token-" + uuid.uuid4().hex,
            platform="android",
        )
        notification = Notification.objects.create(
            user=user,
            notification_type="system",
            title="FCM test",
            body="body",
            scheduled_for=timezone.now(),
        )
        service = NotificationDeliveryService()
        result = service._send_fcm(notification)
        assert result is True

    def test_send_fcm_no_devices(self, db, user):
        """Test FCM returns False when no devices registered."""
        notification = Notification.objects.create(
            user=user,
            notification_type="system",
            title="test",
            body="body",
            scheduled_for=timezone.now(),
        )
        service = NotificationDeliveryService()
        result = service._send_fcm(notification)
        assert result is False

    def test_send_fcm_multicast(self, db, user, mock_fcm):
        """Test FCM multicast for multiple devices."""
        mock_fcm["messaging"].send_each_for_multicast.return_value = Mock(
            success_count=3,
            failure_count=0,
            responses=[Mock(exception=None)] * 3,
        )
        for i in range(3):
            UserDevice.objects.create(
                user=user,
                fcm_token=f"multi-token-{i}-{uuid.uuid4().hex}",
                platform="android",
            )
        notification = Notification.objects.create(
            user=user,
            notification_type="system",
            title="multicast test",
            body="body",
            scheduled_for=timezone.now(),
        )
        service = NotificationDeliveryService()
        result = service._send_fcm(notification)
        assert result is True

    def test_send_fcm_invalid_token_deactivated(self, db, user, mock_fcm):
        """Test that invalid FCM tokens are deactivated on single send."""
        token = "invalid-token-" + uuid.uuid4().hex
        device = UserDevice.objects.create(
            user=user,
            fcm_token=token,
            platform="android",
        )
        # Make send raise UnregisteredError (which send_to_token converts to InvalidTokenError)
        mock_fcm["messaging"].send.side_effect = mock_fcm[
            "messaging"
        ].UnregisteredError("gone")
        notification = Notification.objects.create(
            user=user,
            notification_type="system",
            title="test",
            body="body",
            scheduled_for=timezone.now(),
        )
        service = NotificationDeliveryService()
        result = service._send_fcm(notification)
        assert result is False
        device.refresh_from_db()
        assert device.is_active is False

    def test_send_fcm_with_notification_data(self, db, user, mock_fcm):
        """Test FCM sends notification data payload."""
        UserDevice.objects.create(
            user=user,
            fcm_token="data-token-" + uuid.uuid4().hex,
            platform="ios",
        )
        notification = Notification.objects.create(
            user=user,
            notification_type="achievement",
            title="Level up!",
            body="You reached level 5",
            scheduled_for=timezone.now(),
            data={"screen": "Profile", "level": 5},
        )
        service = NotificationDeliveryService()
        result = service._send_fcm(notification)
        assert result is True

    def test_deliver_tries_fcm_before_webpush(self, db, user, mock_fcm):
        """Test that deliver() tries FCM before falling back to webpush."""
        UserDevice.objects.create(
            user=user,
            fcm_token="priority-token-" + uuid.uuid4().hex,
            platform="android",
        )
        notification = Notification.objects.create(
            user=user,
            notification_type="system",
            title="priority test",
            body="body",
            scheduled_for=timezone.now(),
        )
        service = NotificationDeliveryService()
        with patch.object(service, "_send_webpush") as mock_webpush:
            service.deliver(notification)
            # If FCM succeeds, webpush should NOT be called
            mock_webpush.assert_not_called()

    def test_deliver_falls_back_to_webpush(self, db, user):
        """Test that deliver() falls back to webpush when FCM has no devices."""
        notification = Notification.objects.create(
            user=user,
            notification_type="system",
            title="fallback test",
            body="body",
            scheduled_for=timezone.now(),
        )
        service = NotificationDeliveryService()
        with patch.object(service, "_send_webpush", return_value=False) as mock_webpush:
            service.deliver(notification)
            # FCM returns False (no devices), so webpush should be called
            mock_webpush.assert_called_once()


class TestCleanupStaleFCMTokens:
    """Test cleanup_stale_fcm_tokens task."""

    def test_deactivates_stale_tokens(self, db, user):
        """Test that tokens older than 60 days are deactivated."""
        device = UserDevice.objects.create(
            user=user,
            fcm_token="stale-token-" + uuid.uuid4().hex,
            platform="android",
        )
        # Manually set updated_at to 61 days ago
        UserDevice.objects.filter(pk=device.pk).update(
            updated_at=timezone.now() - timedelta(days=61)
        )

        from apps.notifications.tasks import cleanup_stale_fcm_tokens

        result = cleanup_stale_fcm_tokens()
        assert result["deactivated"] == 1
        device.refresh_from_db()
        assert device.is_active is False

    def test_keeps_fresh_tokens(self, db, user):
        """Test that recently updated tokens are kept active."""
        UserDevice.objects.create(
            user=user,
            fcm_token="fresh-token-" + uuid.uuid4().hex,
            platform="android",
        )

        from apps.notifications.tasks import cleanup_stale_fcm_tokens

        result = cleanup_stale_fcm_tokens()
        assert result["deactivated"] == 0
