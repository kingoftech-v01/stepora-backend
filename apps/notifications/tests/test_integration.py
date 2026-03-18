"""
Integration tests for the Notifications app API endpoints.
"""

import pytest
from django.utils import timezone
from rest_framework import status

from apps.notifications.models import Notification
from apps.users.models import User


# ──────────────────────────────────────────────────────────────────────
#  List Notifications
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestListNotifications:
    """Integration tests for listing notifications."""

    def test_list_notifications_authenticated(self, notif_client, multiple_notifications):
        """Authenticated user can list their notifications."""
        response = notif_client.get("/api/notifications/")
        assert response.status_code == status.HTTP_200_OK
        # Should return paginated results or list
        data = response.data
        if isinstance(data, dict) and "results" in data:
            results = data["results"]
        else:
            results = data
        assert len(results) == 5

    def test_list_notifications_unauthenticated(self):
        """Unauthenticated request returns 401."""
        from rest_framework.test import APIClient

        client = APIClient()
        response = client.get("/api/notifications/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_list_notifications_only_own(self, notif_client, notif_user):
        """User only sees their own notifications."""
        other_user = User.objects.create_user(
            email="other_notif_user@example.com", password="testpassword123"
        )
        # Create notification for other user
        Notification.objects.create(
            user=other_user,
            notification_type="reminder",
            title="Other's notification",
            body="Not for me",
            scheduled_for=timezone.now(),
            status="sent",
        )
        # Create notification for notif_user
        Notification.objects.create(
            user=notif_user,
            notification_type="reminder",
            title="My notification",
            body="This is mine",
            scheduled_for=timezone.now(),
            status="sent",
        )
        response = notif_client.get("/api/notifications/")
        assert response.status_code == status.HTTP_200_OK
        data = response.data
        if isinstance(data, dict) and "results" in data:
            results = data["results"]
        else:
            results = data
        # Should only see own notification
        for n in results:
            assert str(n["user"]) == str(notif_user.id)

    def test_list_notifications_filter_by_type(self, notif_client, notif_user):
        """Notifications can be filtered by notification_type."""
        Notification.objects.create(
            user=notif_user,
            notification_type="reminder",
            title="Reminder",
            body="Body",
            scheduled_for=timezone.now(),
            status="sent",
        )
        Notification.objects.create(
            user=notif_user,
            notification_type="progress",
            title="Progress",
            body="Body",
            scheduled_for=timezone.now(),
            status="sent",
        )
        response = notif_client.get("/api/notifications/?notification_type=reminder")
        assert response.status_code == status.HTTP_200_OK
        data = response.data
        if isinstance(data, dict) and "results" in data:
            results = data["results"]
        else:
            results = data
        for n in results:
            assert n["notification_type"] == "reminder"


# ──────────────────────────────────────────────────────────────────────
#  Mark as Read
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestMarkRead:
    """Integration tests for marking notifications as read."""

    def test_mark_notification_read(self, notif_client, sample_notification):
        """User can mark a notification as read."""
        assert sample_notification.read_at is None
        response = notif_client.post(
            f"/api/notifications/{sample_notification.id}/mark_read/"
        )
        assert response.status_code == status.HTTP_200_OK
        sample_notification.refresh_from_db()
        assert sample_notification.read_at is not None

    def test_mark_read_nonexistent(self, notif_client):
        """Marking a nonexistent notification returns 404."""
        import uuid

        fake_id = uuid.uuid4()
        response = notif_client.post(f"/api/notifications/{fake_id}/mark_read/")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_mark_read_returns_notification_data(self, notif_client, sample_notification):
        """mark_read response contains notification data with is_read=True."""
        response = notif_client.post(
            f"/api/notifications/{sample_notification.id}/mark_read/"
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["is_read"] is True


# ──────────────────────────────────────────────────────────────────────
#  Mark All as Read
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestMarkAllRead:
    """Integration tests for marking all notifications as read."""

    def test_mark_all_read(self, notif_client, multiple_notifications):
        """mark_all_read deletes all notifications for the user."""
        response = notif_client.post("/api/notifications/mark_all_read/")
        assert response.status_code == status.HTTP_200_OK
        assert "marked_read" in response.data
        # All notifications should be deleted
        remaining = Notification.objects.filter(
            user=multiple_notifications[0].user
        ).count()
        assert remaining == 0

    def test_mark_all_read_returns_count(self, notif_client, multiple_notifications):
        """mark_all_read returns the count of deleted notifications."""
        response = notif_client.post("/api/notifications/mark_all_read/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["marked_read"] == 5

    def test_mark_all_read_empty(self, notif_client):
        """mark_all_read with no notifications returns 0."""
        response = notif_client.post("/api/notifications/mark_all_read/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["marked_read"] == 0

    def test_mark_all_read_does_not_affect_other_users(
        self, notif_client, notif_user, multiple_notifications
    ):
        """mark_all_read only deletes notifications for the current user."""
        other_user = User.objects.create_user(
            email="other_mark_all@example.com", password="testpassword123"
        )
        other_notif = Notification.objects.create(
            user=other_user,
            notification_type="reminder",
            title="Other",
            body="Body",
            scheduled_for=timezone.now(),
            status="sent",
        )
        notif_client.post("/api/notifications/mark_all_read/")
        # Other user's notification should still exist
        assert Notification.objects.filter(id=other_notif.id).exists()


# ──────────────────────────────────────────────────────────────────────
#  Unread Count
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestUnreadCount:
    """Integration tests for the unread count endpoint."""

    def test_unread_count(self, notif_client, multiple_notifications):
        """unread_count returns count of unread sent notifications."""
        response = notif_client.get("/api/notifications/unread_count/")
        assert response.status_code == status.HTTP_200_OK
        assert "unread_count" in response.data
        # 5 total, 2 are read (from fixture), so 3 unread
        assert response.data["unread_count"] == 3

    def test_unread_count_zero(self, notif_client, notif_user):
        """unread_count returns 0 when no unread notifications exist."""
        response = notif_client.get("/api/notifications/unread_count/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["unread_count"] == 0

    def test_unread_count_only_sent(self, notif_client, notif_user):
        """unread_count only counts sent (not pending) notifications."""
        # Create a pending notification (not yet sent)
        Notification.objects.create(
            user=notif_user,
            notification_type="reminder",
            title="Pending",
            body="Still pending",
            scheduled_for=timezone.now(),
            status="pending",
        )
        response = notif_client.get("/api/notifications/unread_count/")
        assert response.status_code == status.HTTP_200_OK
        # Pending notifications should not be counted
        assert response.data["unread_count"] == 0

    def test_unread_count_excludes_read(self, notif_client, notif_user):
        """unread_count excludes notifications that have been read."""
        n = Notification.objects.create(
            user=notif_user,
            notification_type="reminder",
            title="Read Me",
            body="Already read",
            scheduled_for=timezone.now(),
            status="sent",
        )
        n.mark_read()
        response = notif_client.get("/api/notifications/unread_count/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["unread_count"] == 0
