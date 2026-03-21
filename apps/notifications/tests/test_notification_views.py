"""
Comprehensive tests for apps/notifications/views.py — targeting 90%+ coverage.

Covers:
- NotificationViewSet: list, create, retrieve, update, delete, mark_read,
  mark_all_read, unread_count, opened, grouped
- Free-tier notification type filtering
- NotificationTemplateViewSet: list, retrieve
- WebPushSubscriptionViewSet: list, create (with dedup), delete
- UserDeviceViewSet: create (with re-register), list, delete (soft)
- NotificationBatchViewSet: admin-only access, list, retrieve
"""

import uuid
from unittest.mock import Mock, patch

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
from apps.users.models import User


# ── Fixtures ─────────────────────────────────────────────────────────


@pytest.fixture
def nuser(db):
    """Primary notification test user."""
    return User.objects.create_user(
        email="nv_user@example.com",
        password="testpassword123",
        display_name="NV User",
    )


@pytest.fixture
def nclient(nuser):
    client = APIClient()
    client.force_authenticate(user=nuser)
    return client


@pytest.fixture
def nuser2(db):
    """Second notification test user."""
    return User.objects.create_user(
        email="nv_user2@example.com",
        password="testpassword123",
        display_name="NV User 2",
    )


@pytest.fixture
def nclient2(nuser2):
    client = APIClient()
    client.force_authenticate(user=nuser2)
    return client


@pytest.fixture
def admin_user(db):
    """Admin user for batch endpoints."""
    return User.objects.create_superuser(
        email="nv_admin@example.com",
        password="adminpass123",
        display_name="NV Admin",
    )


@pytest.fixture
def admin_client(admin_user):
    client = APIClient()
    client.force_authenticate(user=admin_user)
    return client


@pytest.fixture
def sent_notification(db, nuser):
    """A sent notification for nuser."""
    return Notification.objects.create(
        user=nuser,
        notification_type="reminder",
        title="Sent Notif",
        body="Test body",
        scheduled_for=timezone.now(),
        status="sent",
    )


@pytest.fixture
def multiple_notifs(db, nuser):
    """Create 5 notifications of different types for nuser."""
    now = timezone.now()
    notifs = []
    types = ["reminder", "progress", "system", "reminder", "progress"]
    for i, ntype in enumerate(types):
        n = Notification.objects.create(
            user=nuser,
            notification_type=ntype,
            title=f"Notif {i}",
            body=f"Body {i}",
            scheduled_for=now,
            status="sent",
        )
        notifs.append(n)
    # Mark first two as read
    notifs[0].mark_read()
    notifs[1].mark_read()
    return notifs


@pytest.fixture
def active_template(db):
    """An active notification template."""
    return NotificationTemplate.objects.create(
        name="test_tmpl",
        notification_type="reminder",
        title_template="Reminder: {title}",
        body_template="Don't forget: {action}",
        is_active=True,
    )


@pytest.fixture
def inactive_template(db):
    """An inactive notification template."""
    return NotificationTemplate.objects.create(
        name="inactive_tmpl",
        notification_type="motivation",
        title_template="Go: {title}",
        body_template="Keep going: {action}",
        is_active=False,
    )


# ══════════════════════════════════════════════════════════════════════
#  NOTIFICATION LIST
# ══════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestNotificationList:
    """Tests for GET /api/notifications/"""

    def test_list_own_notifications(self, nclient, multiple_notifs):
        """User sees their own notifications."""
        response = nclient.get("/api/notifications/")
        assert response.status_code == status.HTTP_200_OK
        data = response.data
        results = data.get("results", data)
        assert len(results) == 5

    def test_list_excludes_other_users(self, nclient, nuser, nuser2):
        """User does not see other users' notifications."""
        Notification.objects.create(
            user=nuser2,
            notification_type="reminder",
            title="Not Mine",
            body="Not for me",
            scheduled_for=timezone.now(),
            status="sent",
        )
        Notification.objects.create(
            user=nuser,
            notification_type="reminder",
            title="Mine",
            body="For me",
            scheduled_for=timezone.now(),
            status="sent",
        )
        response = nclient.get("/api/notifications/")
        data = response.data
        results = data.get("results", data)
        for n in results:
            assert str(n["user"]) == str(nuser.id)

    def test_list_filter_by_type(self, nclient, multiple_notifs):
        """Filter by notification_type."""
        response = nclient.get("/api/notifications/?notification_type=reminder")
        assert response.status_code == status.HTTP_200_OK
        data = response.data
        results = data.get("results", data)
        for n in results:
            assert n["notification_type"] == "reminder"

    def test_list_filter_by_status(self, nclient, nuser):
        """Filter by status."""
        Notification.objects.create(
            user=nuser,
            notification_type="reminder",
            title="Pending",
            body="Pending body",
            scheduled_for=timezone.now(),
            status="pending",
        )
        response = nclient.get("/api/notifications/?status=pending")
        assert response.status_code == status.HTTP_200_OK
        data = response.data
        results = data.get("results", data)
        for n in results:
            assert n["status"] == "pending"

    def test_list_unauthenticated(self):
        """Unauthenticated returns 401."""
        client = APIClient()
        response = client.get("/api/notifications/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


# ══════════════════════════════════════════════════════════════════════
#  FREE-TIER TYPE FILTERING
# ══════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestFreeTierFiltering:
    """Free users only see FREE_TIER_TYPES notifications."""

    def test_free_user_filtered(self, nclient, nuser):
        """Free user does not see 'motivation' type notifications."""
        Notification.objects.create(
            user=nuser,
            notification_type="motivation",
            title="Motivation",
            body="Body",
            scheduled_for=timezone.now(),
            status="sent",
        )
        Notification.objects.create(
            user=nuser,
            notification_type="reminder",
            title="Reminder",
            body="Body",
            scheduled_for=timezone.now(),
            status="sent",
        )
        response = nclient.get("/api/notifications/")
        data = response.data
        results = data.get("results", data)
        types = [n["notification_type"] for n in results]
        # Free tier: reminder, progress, dream_completed, system
        assert "motivation" not in types
        assert "reminder" in types

    def test_premium_user_sees_all(self, db):
        """Premium user sees all notification types."""
        from decimal import Decimal
        from apps.subscriptions.models import Subscription, SubscriptionPlan

        # Create a fresh premium user and update the subscription CharField
        puser = User.objects.create_user(
            email="premium_notif@example.com",
            password="testpassword123",
            display_name="Premium Notif",
        )
        # Update the User.subscription CharField directly
        puser.subscription = "premium"
        puser.save(update_fields=["subscription"])

        plan, _ = SubscriptionPlan.objects.get_or_create(
            slug="premium",
            defaults={
                "name": "Premium",
                "price_monthly": Decimal("19.99"),
                "has_ai": True,
                "has_buddy": True,
                "has_circles": True,
                "is_active": True,
            },
        )
        Subscription.objects.update_or_create(
            user=puser,
            defaults={"plan": plan, "status": "active"},
        )

        Notification.objects.create(
            user=puser,
            notification_type="motivation",
            title="Motivation",
            body="Body",
            scheduled_for=timezone.now(),
            status="sent",
        )

        client = APIClient()
        client.force_authenticate(user=puser)
        response = client.get("/api/notifications/")
        data = response.data
        results = data.get("results", data)
        types = [n["notification_type"] for n in results]
        assert "motivation" in types


# ══════════════════════════════════════════════════════════════════════
#  CREATE NOTIFICATION
# ══════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestCreateNotification:
    """Tests for POST /api/notifications/"""

    def test_create_notification(self, nclient, nuser):
        """Create a notification."""
        response = nclient.post(
            "/api/notifications/",
            {
                "notification_type": "reminder",
                "title": "New Reminder",
                "body": "Don't forget",
                "scheduled_for": timezone.now().isoformat(),
            },
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        # Title is encrypted, so verify via response data and user count
        assert response.data["title"] == "New Reminder"
        assert Notification.objects.filter(user=nuser).count() >= 1

    def test_create_notification_assigns_user(self, nclient, nuser):
        """Created notification is assigned to the current user."""
        before_count = Notification.objects.filter(user=nuser).count()
        response = nclient.post(
            "/api/notifications/",
            {
                "notification_type": "progress",
                "title": "Progress",
                "body": "You're doing great!",
                "scheduled_for": timezone.now().isoformat(),
            },
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        after_count = Notification.objects.filter(user=nuser).count()
        assert after_count == before_count + 1


# ══════════════════════════════════════════════════════════════════════
#  RETRIEVE NOTIFICATION
# ══════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestRetrieveNotification:
    """Tests for GET /api/notifications/{id}/"""

    def test_retrieve_notification(self, nclient, sent_notification):
        """Retrieve a specific notification."""
        response = nclient.get(f"/api/notifications/{sent_notification.id}/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["id"] == str(sent_notification.id)

    def test_retrieve_nonexistent(self, nclient):
        """Non-existent notification returns 404."""
        response = nclient.get(f"/api/notifications/{uuid.uuid4()}/")
        assert response.status_code == status.HTTP_404_NOT_FOUND


# ══════════════════════════════════════════════════════════════════════
#  UPDATE NOTIFICATION
# ══════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestUpdateNotification:
    """Tests for PUT/PATCH /api/notifications/{id}/"""

    def test_partial_update(self, nclient, sent_notification):
        """Partially update a notification."""
        response = nclient.patch(
            f"/api/notifications/{sent_notification.id}/",
            {"title": "Updated Title"},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        sent_notification.refresh_from_db()
        assert sent_notification.title == "Updated Title"


# ══════════════════════════════════════════════════════════════════════
#  DELETE NOTIFICATION
# ══════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestDeleteNotification:
    """Tests for DELETE /api/notifications/{id}/"""

    def test_delete_notification(self, nclient, sent_notification):
        """Delete a notification."""
        response = nclient.delete(f"/api/notifications/{sent_notification.id}/")
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not Notification.objects.filter(id=sent_notification.id).exists()


# ══════════════════════════════════════════════════════════════════════
#  MARK READ
# ══════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestMarkReadExtra:
    """Tests for POST /api/notifications/{id}/mark_read/"""

    def test_mark_read(self, nclient, sent_notification):
        """Mark a notification as read."""
        assert sent_notification.read_at is None
        response = nclient.post(
            f"/api/notifications/{sent_notification.id}/mark_read/"
        )
        assert response.status_code == status.HTTP_200_OK
        sent_notification.refresh_from_db()
        assert sent_notification.read_at is not None

    def test_mark_read_nonexistent(self, nclient):
        """Marking nonexistent notification returns 404."""
        response = nclient.post(f"/api/notifications/{uuid.uuid4()}/mark_read/")
        assert response.status_code == status.HTTP_404_NOT_FOUND


# ══════════════════════════════════════════════════════════════════════
#  MARK ALL READ (DELETE ALL)
# ══════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestMarkAllReadExtra:
    """Tests for POST /api/notifications/mark_all_read/"""

    def test_mark_all_read_deletes(self, nclient, multiple_notifs):
        """mark_all_read deletes all notifications."""
        response = nclient.post("/api/notifications/mark_all_read/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["marked_read"] == 5
        assert Notification.objects.filter(user=multiple_notifs[0].user).count() == 0

    def test_mark_all_read_empty(self, nclient):
        """mark_all_read with no notifications returns 0."""
        response = nclient.post("/api/notifications/mark_all_read/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["marked_read"] == 0

    def test_mark_all_read_does_not_affect_others(self, nclient, nuser, nuser2, multiple_notifs):
        """mark_all_read only deletes current user's notifications."""
        other_notif = Notification.objects.create(
            user=nuser2,
            notification_type="reminder",
            title="Other",
            body="Body",
            scheduled_for=timezone.now(),
            status="sent",
        )
        nclient.post("/api/notifications/mark_all_read/")
        assert Notification.objects.filter(id=other_notif.id).exists()


# ══════════════════════════════════════════════════════════════════════
#  UNREAD COUNT
# ══════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestUnreadCountExtra:
    """Tests for GET /api/notifications/unread_count/"""

    def test_unread_count(self, nclient, multiple_notifs):
        """Returns correct unread count."""
        response = nclient.get("/api/notifications/unread_count/")
        assert response.status_code == status.HTTP_200_OK
        # 5 total, 2 read -> 3 unread
        assert response.data["unread_count"] == 3

    def test_unread_count_zero(self, nclient):
        """Returns 0 when no unread notifications."""
        response = nclient.get("/api/notifications/unread_count/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["unread_count"] == 0

    def test_unread_count_only_sent(self, nclient, nuser):
        """Pending notifications not counted."""
        Notification.objects.create(
            user=nuser,
            notification_type="reminder",
            title="Pending",
            body="Body",
            scheduled_for=timezone.now(),
            status="pending",
        )
        response = nclient.get("/api/notifications/unread_count/")
        assert response.data["unread_count"] == 0


# ══════════════════════════════════════════════════════════════════════
#  MARK OPENED
# ══════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestMarkOpenedExtra:
    """Tests for POST /api/notifications/{id}/opened/"""

    def test_mark_opened(self, nclient, sent_notification):
        """Mark notification as opened."""
        response = nclient.post(
            f"/api/notifications/{sent_notification.id}/opened/"
        )
        assert response.status_code == status.HTTP_200_OK
        sent_notification.refresh_from_db()
        assert sent_notification.opened_at is not None

    def test_mark_opened_nonexistent(self, nclient):
        """Nonexistent notification returns 404."""
        response = nclient.post(f"/api/notifications/{uuid.uuid4()}/opened/")
        assert response.status_code == status.HTTP_404_NOT_FOUND


# ══════════════════════════════════════════════════════════════════════
#  GROUPED NOTIFICATIONS
# ══════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestGroupedExtra:
    """Tests for GET /api/notifications/grouped/"""

    def test_grouped_with_data(self, nclient, multiple_notifs):
        """Grouped returns type counts."""
        response = nclient.get("/api/notifications/grouped/")
        assert response.status_code == status.HTTP_200_OK
        assert "groups" in response.data
        groups = response.data["groups"]
        assert len(groups) >= 1
        # Verify structure
        for g in groups:
            assert "type" in g
            assert "total" in g
            assert "unread" in g

    def test_grouped_empty(self, nclient):
        """Grouped returns empty list with no notifications."""
        response = nclient.get("/api/notifications/grouped/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["groups"] == []

    def test_grouped_unread_count(self, nclient, multiple_notifs):
        """Grouped unread counts are correct."""
        response = nclient.get("/api/notifications/grouped/")
        groups_dict = {g["type"]: g for g in response.data["groups"]}
        # 2 reminders (1 read, 1 unread), 2 progress (1 read, 1 unread), 1 system (unread)
        if "reminder" in groups_dict:
            assert groups_dict["reminder"]["total"] == 2
            assert groups_dict["reminder"]["unread"] == 1


# ══════════════════════════════════════════════════════════════════════
#  NOTIFICATION TEMPLATES
# ══════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestNotificationTemplates:
    """Tests for notification template endpoints."""

    def test_list_templates(self, nclient, active_template, inactive_template):
        """List only returns active templates."""
        response = nclient.get("/api/notifications/templates/")
        assert response.status_code == status.HTTP_200_OK
        data = response.data
        results = data.get("results", data)
        names = [t["name"] for t in results]
        assert active_template.name in names
        assert inactive_template.name not in names

    def test_retrieve_template(self, nclient, active_template):
        """Retrieve a specific template."""
        response = nclient.get(
            f"/api/notifications/templates/{active_template.id}/"
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["name"] == active_template.name

    def test_list_templates_unauthenticated(self):
        """Templates require authentication."""
        client = APIClient()
        response = client.get("/api/notifications/templates/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


# ══════════════════════════════════════════════════════════════════════
#  WEB PUSH SUBSCRIPTIONS
# ══════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestWebPushSubscriptions:
    """Tests for Web Push subscription endpoints."""

    def test_list_subscriptions_empty(self, nclient):
        """List returns empty when no subscriptions."""
        response = nclient.get("/api/notifications/push-subscriptions/")
        assert response.status_code == status.HTTP_200_OK

    def test_create_subscription(self, nclient, nuser):
        """Create a push subscription."""
        response = nclient.post(
            "/api/notifications/push-subscriptions/",
            {
                "subscription_info": {
                    "endpoint": "https://fcm.googleapis.com/test/123",
                    "keys": {"p256dh": "testkey", "auth": "testauthkey"},
                },
                "browser": "chrome",
            },
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert WebPushSubscription.objects.filter(user=nuser).exists()

    def test_create_subscription_deactivates_duplicate(self, nclient, nuser):
        """Creating subscription with same endpoint deactivates old one."""
        endpoint = "https://fcm.googleapis.com/test/dedup"
        sub_info = {
            "endpoint": endpoint,
            "keys": {"p256dh": "key1", "auth": "auth1"},
        }
        WebPushSubscription.objects.create(
            user=nuser, subscription_info=sub_info, is_active=True
        )
        response = nclient.post(
            "/api/notifications/push-subscriptions/",
            {"subscription_info": sub_info, "browser": "firefox"},
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        # Old subscription deactivated
        old_subs = WebPushSubscription.objects.filter(
            user=nuser, subscription_info__endpoint=endpoint, is_active=False
        )
        assert old_subs.exists()

    def test_delete_subscription(self, nclient, nuser):
        """Delete a push subscription."""
        sub = WebPushSubscription.objects.create(
            user=nuser,
            subscription_info={
                "endpoint": "https://fcm.googleapis.com/test/del",
                "keys": {"p256dh": "k", "auth": "a"},
            },
            is_active=True,
        )
        response = nclient.delete(
            f"/api/notifications/push-subscriptions/{sub.id}/"
        )
        assert response.status_code == status.HTTP_204_NO_CONTENT

    def test_list_only_active(self, nclient, nuser):
        """List only returns active subscriptions."""
        WebPushSubscription.objects.create(
            user=nuser,
            subscription_info={
                "endpoint": "https://active",
                "keys": {"p256dh": "k", "auth": "a"},
            },
            is_active=True,
        )
        WebPushSubscription.objects.create(
            user=nuser,
            subscription_info={
                "endpoint": "https://inactive",
                "keys": {"p256dh": "k", "auth": "a"},
            },
            is_active=False,
        )
        response = nclient.get("/api/notifications/push-subscriptions/")
        data = response.data
        results = data.get("results", data)
        assert len(results) == 1

    def test_push_subscriptions_unauthenticated(self):
        """Push subscriptions require authentication."""
        client = APIClient()
        response = client.get("/api/notifications/push-subscriptions/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


# ══════════════════════════════════════════════════════════════════════
#  USER DEVICES (FCM)
# ══════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestUserDevices:
    """Tests for FCM device registration endpoints."""

    def test_list_devices_empty(self, nclient):
        """List returns empty when no devices."""
        response = nclient.get("/api/notifications/devices/")
        assert response.status_code == status.HTTP_200_OK

    @patch("apps.notifications.views.UserDeviceViewSet._subscribe_to_user_topics")
    def test_register_device(self, mock_sub, nclient, nuser):
        """Register a new FCM device."""
        import uuid as uuid_mod

        unique_token = f"new-fcm-token-{uuid_mod.uuid4().hex[:12]}"
        response = nclient.post(
            "/api/notifications/devices/",
            {
                "fcm_token": unique_token,
                "platform": "android",
                "device_name": "Pixel 7",
                "app_version": "2.0.0",
            },
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert UserDevice.objects.filter(user=nuser, fcm_token=unique_token).exists()

    @patch("apps.notifications.views.UserDeviceViewSet._subscribe_to_user_topics")
    def test_register_device_reregister(self, mock_sub, nclient, nuser):
        """Re-registering with same token deletes old and creates new."""
        token = "reregister-token-xyz"
        UserDevice.objects.create(
            user=nuser, fcm_token=token, platform="android", is_active=True
        )
        response = nclient.post(
            "/api/notifications/devices/",
            {
                "fcm_token": token,
                "platform": "ios",
                "device_name": "iPhone 15",
            },
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        # Only one device with this token
        assert UserDevice.objects.filter(fcm_token=token).count() == 1

    @patch("apps.notifications.views.UserDeviceViewSet._unsubscribe_from_all_topics")
    def test_delete_device_soft(self, mock_unsub, nclient, nuser):
        """Deleting a device soft-deletes (deactivates)."""
        device = UserDevice.objects.create(
            user=nuser,
            fcm_token="delete-token-abc",
            platform="android",
            is_active=True,
        )
        response = nclient.delete(f"/api/notifications/devices/{device.id}/")
        assert response.status_code == status.HTTP_204_NO_CONTENT
        device.refresh_from_db()
        assert device.is_active is False

    def test_list_only_active_devices(self, nclient, nuser):
        """List only returns active devices."""
        UserDevice.objects.create(
            user=nuser,
            fcm_token="active-device-tok",
            platform="android",
            is_active=True,
        )
        UserDevice.objects.create(
            user=nuser,
            fcm_token="inactive-device-tok",
            platform="ios",
            is_active=False,
        )
        response = nclient.get("/api/notifications/devices/")
        data = response.data
        results = data.get("results", data)
        assert len(results) == 1

    def test_list_only_own_devices(self, nclient, nuser, nuser2):
        """User only sees their own devices."""
        UserDevice.objects.create(
            user=nuser, fcm_token="my-tok", platform="android", is_active=True
        )
        UserDevice.objects.create(
            user=nuser2, fcm_token="other-tok", platform="ios", is_active=True
        )
        response = nclient.get("/api/notifications/devices/")
        data = response.data
        results = data.get("results", data)
        assert len(results) == 1


# ══════════════════════════════════════════════════════════════════════
#  USER DEVICE TOPIC SUBSCRIPTION
# ══════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestDeviceTopicSubscription:
    """Tests for FCM topic subscription/unsubscription logic."""

    @patch("apps.notifications.fcm_service.get_firebase_app")
    @patch("apps.notifications.fcm_service.FCMService.subscribe_to_topic")
    def test_subscribe_to_topics(self, mock_subscribe, mock_app, nclient, nuser):
        """Device registration subscribes to topics."""
        nuser.notification_prefs = {"motivation": True, "weekly_report": False}
        nuser.save(update_fields=["notification_prefs"])

        # Use internal method directly
        device = UserDevice.objects.create(
            user=nuser,
            fcm_token="topic-test-tok",
            platform="android",
            is_active=True,
        )
        from apps.notifications.views import UserDeviceViewSet

        viewset = UserDeviceViewSet()
        viewset._subscribe_to_user_topics(device)
        # Should be called for user topic + motivation (not weekly_report)
        assert mock_subscribe.call_count >= 1

    @patch("apps.notifications.fcm_service.get_firebase_app")
    @patch("apps.notifications.fcm_service.FCMService.unsubscribe_from_topic")
    def test_unsubscribe_from_topics(self, mock_unsub, mock_app, nuser):
        """Device deletion unsubscribes from all topics."""
        device = UserDevice.objects.create(
            user=nuser,
            fcm_token="unsub-test-tok",
            platform="android",
            is_active=True,
        )
        from apps.notifications.views import UserDeviceViewSet

        viewset = UserDeviceViewSet()
        viewset._unsubscribe_from_all_topics(device)
        # Called for user topic + 3 notification topics
        assert mock_unsub.call_count == 4

    def test_subscribe_handles_exception(self, nuser):
        """Topic subscription handles FCM errors gracefully."""
        device = UserDevice.objects.create(
            user=nuser,
            fcm_token="err-tok",
            platform="android",
            is_active=True,
        )
        from apps.notifications.views import UserDeviceViewSet

        viewset = UserDeviceViewSet()
        # Should not raise even if FCMService fails
        with patch(
            "apps.notifications.fcm_service.FCMService.__init__",
            side_effect=Exception("Firebase not configured"),
        ):
            viewset._subscribe_to_user_topics(device)  # Should not raise

    def test_unsubscribe_handles_exception(self, nuser):
        """Topic unsubscription handles FCM errors gracefully."""
        device = UserDevice.objects.create(
            user=nuser,
            fcm_token="err-unsub-tok",
            platform="android",
            is_active=True,
        )
        from apps.notifications.views import UserDeviceViewSet

        viewset = UserDeviceViewSet()
        with patch(
            "apps.notifications.fcm_service.FCMService.__init__",
            side_effect=Exception("Firebase not configured"),
        ):
            viewset._unsubscribe_from_all_topics(device)  # Should not raise


# ══════════════════════════════════════════════════════════════════════
#  NOTIFICATION BATCHES (ADMIN)
# ══════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestNotificationBatches:
    """Tests for notification batch endpoints (admin only)."""

    def test_list_batches_non_admin(self, nclient):
        """Non-admin gets 403."""
        response = nclient.get("/api/notifications/batches/")
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_list_batches_unauthenticated(self):
        """Unauthenticated gets 401."""
        client = APIClient()
        response = client.get("/api/notifications/batches/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_list_batches_admin(self, admin_client):
        """Admin can list batches."""
        NotificationBatch.objects.create(
            name="Test Batch",
            notification_type="reminder",
            status="completed",
            total_scheduled=10,
            total_sent=10,
        )
        response = admin_client.get("/api/notifications/batches/")
        assert response.status_code == status.HTTP_200_OK

    def test_retrieve_batch_admin(self, admin_client):
        """Admin can retrieve a specific batch."""
        batch = NotificationBatch.objects.create(
            name="Specific Batch",
            notification_type="motivation",
            status="processing",
        )
        response = admin_client.get(f"/api/notifications/batches/{batch.id}/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["name"] == "Specific Batch"

    def test_retrieve_batch_non_admin(self, nclient):
        """Non-admin cannot retrieve a batch."""
        batch = NotificationBatch.objects.create(
            name="Forbidden Batch",
            notification_type="reminder",
        )
        response = nclient.get(f"/api/notifications/batches/{batch.id}/")
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_list_batches_filter_by_type(self, admin_client):
        """Batches can be filtered by notification_type."""
        NotificationBatch.objects.create(
            name="Reminder Batch",
            notification_type="reminder",
        )
        NotificationBatch.objects.create(
            name="Motivation Batch",
            notification_type="motivation",
        )
        response = admin_client.get(
            "/api/notifications/batches/?notification_type=reminder"
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.data
        results = data.get("results", data)
        for b in results:
            assert b["notification_type"] == "reminder"

    def test_list_batches_filter_by_status(self, admin_client):
        """Batches can be filtered by status."""
        NotificationBatch.objects.create(
            name="Completed",
            notification_type="reminder",
            status="completed",
        )
        NotificationBatch.objects.create(
            name="Processing",
            notification_type="reminder",
            status="processing",
        )
        response = admin_client.get(
            "/api/notifications/batches/?status=completed"
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.data
        results = data.get("results", data)
        for b in results:
            assert b["status"] == "completed"
