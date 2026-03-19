"""
Tests for apps/notifications/tasks.py — all Celery tasks.

Covers:
- check_due_tasks
- send_weekly_digests / send_user_digest
- expire_ringing_calls
- process_pending_notifications
- generate_daily_motivation
- check_inactive_users
- send_reminder_notifications
- cleanup_old_notifications
- send_streak_milestone_notification
- send_level_up_notification
- cleanup_stale_fcm_tokens
"""

import uuid
from datetime import timedelta
from unittest.mock import MagicMock, Mock, patch

import pytest
from django.utils import timezone

from apps.dreams.models import Dream, Goal, Task
from apps.notifications.models import Notification, UserDevice
from apps.users.models import User


# ──────────────────────────────────────────────────────────────────────
#  check_due_tasks
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestCheckDueTasks:
    """Tests for the check_due_tasks task."""

    def _setup_due_task(self, user):
        """Helper: create a dream/goal/task due in the next 3 minutes."""
        dream = Dream.objects.create(
            user=user,
            title="Test Dream",
            description="Test",
            status="active",
        )
        goal = Goal.objects.create(dream=dream, title="Goal", order=1)
        now = timezone.now()
        task = Task.objects.create(
            goal=goal,
            title="Due Task",
            order=1,
            status="pending",
            scheduled_date=now + timedelta(minutes=1),
        )
        return task

    @patch("apps.notifications.fcm_service.FCMService")
    def test_sends_notification_for_due_task(self, mock_fcm_cls, user):
        """check_due_tasks sends push notifications for tasks due within 3 minutes."""
        mock_fcm = Mock()
        mock_fcm_cls.return_value = mock_fcm
        task = self._setup_due_task(user)

        # Create a device for the user
        UserDevice.objects.create(
            user=user,
            fcm_token="token-due-task-test",
            platform="android",
            is_active=True,
        )

        from apps.notifications.tasks import check_due_tasks

        result = check_due_tasks()

        assert result["sent"] >= 1
        mock_fcm.send_to_token.assert_called()
        # A Notification record should be created
        assert Notification.objects.filter(
            user=user,
            notification_type="task_due",
        ).exists()

    @patch("apps.notifications.fcm_service.FCMService")
    def test_skips_already_notified_task(self, mock_fcm_cls, user):
        """check_due_tasks skips tasks that already have a recent notification."""
        mock_fcm = Mock()
        mock_fcm_cls.return_value = mock_fcm
        task = self._setup_due_task(user)

        # Pre-create a task_due notification
        Notification.objects.create(
            user=user,
            notification_type="task_due",
            title="Due Task",
            body="Time to work",
            scheduled_for=timezone.now(),
            data={"task_id": str(task.id)},
        )

        from apps.notifications.tasks import check_due_tasks

        result = check_due_tasks()
        assert result["sent"] == 0

    @patch("apps.notifications.fcm_service.FCMService")
    def test_skips_inactive_user(self, mock_fcm_cls, db):
        """check_due_tasks skips tasks belonging to inactive users."""
        mock_fcm = Mock()
        mock_fcm_cls.return_value = mock_fcm

        inactive_user = User.objects.create_user(
            email="inactive_due@example.com",
            password="testpassword123",
            is_active=False,
        )
        dream = Dream.objects.create(
            user=inactive_user, title="Dream", description="d", status="active"
        )
        goal = Goal.objects.create(dream=dream, title="G", order=1)
        Task.objects.create(
            goal=goal,
            title="Task",
            order=1,
            status="pending",
            scheduled_date=timezone.now() + timedelta(minutes=1),
        )

        from apps.notifications.tasks import check_due_tasks

        result = check_due_tasks()
        assert result["sent"] == 0

    @patch("apps.notifications.fcm_service.FCMService")
    def test_no_due_tasks(self, mock_fcm_cls, user):
        """check_due_tasks returns 0 when no tasks are due."""
        mock_fcm_cls.return_value = Mock()
        from apps.notifications.tasks import check_due_tasks

        result = check_due_tasks()
        assert result["sent"] == 0


# ──────────────────────────────────────────────────────────────────────
#  send_weekly_digests / send_user_digest
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestSendWeeklyDigests:
    """Tests for send_weekly_digests and send_user_digest tasks."""

    @patch("apps.notifications.tasks.send_user_digest")
    def test_dispatches_for_active_users(self, mock_send_user_digest, user):
        """send_weekly_digests dispatches per-user tasks for active users."""
        from apps.notifications.tasks import send_weekly_digests

        result = send_weekly_digests()
        assert result["dispatched"] >= 1
        mock_send_user_digest.delay.assert_called()

    @patch("apps.notifications.tasks.send_user_digest")
    def test_skips_users_with_disabled_weekly_report(self, mock_send, db):
        """send_weekly_digests skips users who disabled weekly_report."""
        user = User.objects.create_user(
            email="nodigest@example.com",
            password="testpassword123",
            notification_prefs={"weekly_report": False},
        )

        from apps.notifications.tasks import send_weekly_digests

        # Only count dispatches for our user
        result = send_weekly_digests()
        # Verify the call wasn't made for this specific user
        calls = mock_send.delay.call_args_list
        user_ids_dispatched = [c[0][0] for c in calls]
        assert str(user.id) not in user_ids_dispatched

    @patch("apps.notifications.tasks._send_digest_email")
    @patch("apps.notifications.tasks._send_digest_push")
    def test_send_user_digest_creates_notification(
        self, mock_push, mock_email, user
    ):
        """send_user_digest creates a notification record and sends push + email."""
        from apps.notifications.tasks import send_user_digest

        result = send_user_digest(str(user.id))

        assert result["sent"] is True
        assert "notification_id" in result
        mock_push.assert_called_once()
        mock_email.assert_called_once()

        # Notification should exist
        notif = Notification.objects.get(id=result["notification_id"])
        assert notif.notification_type == "weekly_report"
        assert notif.status == "sent"

    def test_send_user_digest_user_not_found(self, db):
        """send_user_digest handles missing user gracefully."""
        from apps.notifications.tasks import send_user_digest

        result = send_user_digest(str(uuid.uuid4()))
        assert result["sent"] is False
        assert result["reason"] == "user_not_found"

    @patch("apps.notifications.tasks._send_digest_email")
    @patch("apps.notifications.tasks._send_digest_push")
    def test_send_user_digest_includes_task_stats(
        self, mock_push, mock_email, user
    ):
        """send_user_digest includes completed task count in result."""
        # Create a completed task
        dream = Dream.objects.create(
            user=user, title="D", description="d", status="active"
        )
        goal = Goal.objects.create(dream=dream, title="G", order=1)
        Task.objects.create(
            goal=goal,
            title="Done",
            order=1,
            status="completed",
            completed_at=timezone.now(),
        )

        from apps.notifications.tasks import send_user_digest

        result = send_user_digest(str(user.id))
        assert result["sent"] is True
        assert result["tasks_completed"] == 1


# ──────────────────────────────────────────────────────────────────────
#  expire_ringing_calls
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestExpireRingingCalls:
    """Tests for expire_ringing_calls task."""

    def _create_call(self, caller, callee, created_at=None, status="ringing"):
        from apps.chat.models import Call

        call = Call.objects.create(
            caller=caller,
            callee=callee,
            call_type="voice",
            status=status,
        )
        if created_at:
            Call.objects.filter(id=call.id).update(created_at=created_at)
        return call

    @patch("channels.layers.get_channel_layer")
    def test_expires_stale_ringing_call(self, mock_channel_layer, db):
        """expire_ringing_calls sets stale ringing calls to missed."""
        mock_channel_layer.return_value = None

        caller = User.objects.create_user(
            email="caller@test.com", password="testpass123", display_name="Caller"
        )
        callee = User.objects.create_user(
            email="callee@test.com", password="testpass123", display_name="Callee"
        )

        stale_time = timezone.now() - timedelta(seconds=60)
        call = self._create_call(caller, callee, created_at=stale_time)

        from apps.notifications.tasks import expire_ringing_calls

        result = expire_ringing_calls()
        assert result["expired"] >= 1

        # Both caller and callee should have missed_call notifications
        assert Notification.objects.filter(
            user=callee, notification_type="missed_call"
        ).exists()
        assert Notification.objects.filter(
            user=caller, notification_type="missed_call"
        ).exists()

    @patch("channels.layers.get_channel_layer")
    def test_does_not_expire_recent_call(self, mock_channel_layer, db):
        """expire_ringing_calls ignores calls created less than 30s ago."""
        mock_channel_layer.return_value = None

        caller = User.objects.create_user(
            email="caller2@test.com", password="testpass123"
        )
        callee = User.objects.create_user(
            email="callee2@test.com", password="testpass123"
        )

        # Just created = not stale
        self._create_call(caller, callee)

        from apps.notifications.tasks import expire_ringing_calls

        result = expire_ringing_calls()
        assert result["expired"] == 0

    @patch("channels.layers.get_channel_layer")
    def test_does_not_expire_non_ringing_call(self, mock_channel_layer, db):
        """expire_ringing_calls ignores calls not in ringing status."""
        mock_channel_layer.return_value = None

        caller = User.objects.create_user(
            email="caller3@test.com", password="testpass123"
        )
        callee = User.objects.create_user(
            email="callee3@test.com", password="testpass123"
        )

        stale_time = timezone.now() - timedelta(seconds=60)
        self._create_call(
            caller, callee, created_at=stale_time, status="completed"
        )

        from apps.notifications.tasks import expire_ringing_calls

        result = expire_ringing_calls()
        assert result["expired"] == 0


# ──────────────────────────────────────────────────────────────────────
#  process_pending_notifications
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestProcessPendingNotifications:
    """Tests for process_pending_notifications task."""

    @patch("apps.notifications.services.NotificationDeliveryService")
    def test_processes_pending_notifications(self, mock_delivery_cls, user):
        """process_pending_notifications delivers pending notifications."""
        mock_delivery = Mock()
        mock_delivery.deliver.return_value = True
        mock_delivery_cls.return_value = mock_delivery

        Notification.objects.create(
            user=user,
            notification_type="reminder",
            title="Test",
            body="Body",
            scheduled_for=timezone.now() - timedelta(minutes=1),
            status="pending",
        )

        from apps.notifications.tasks import process_pending_notifications

        result = process_pending_notifications()
        assert result["sent"] == 1
        assert result["failed"] == 0

    @patch("apps.notifications.services.NotificationDeliveryService")
    def test_marks_failed_when_delivery_fails(self, mock_delivery_cls, user):
        """process_pending_notifications marks notification as failed on delivery failure."""
        mock_delivery = Mock()
        mock_delivery.deliver.return_value = False
        mock_delivery_cls.return_value = mock_delivery

        Notification.objects.create(
            user=user,
            notification_type="reminder",
            title="Test",
            body="Body",
            scheduled_for=timezone.now() - timedelta(minutes=1),
            status="pending",
        )

        from apps.notifications.tasks import process_pending_notifications

        result = process_pending_notifications()
        assert result["failed"] == 1
        assert result["sent"] == 0

    @patch("apps.notifications.services.NotificationDeliveryService")
    def test_skips_future_notifications(self, mock_delivery_cls, user):
        """process_pending_notifications ignores notifications scheduled in the future."""
        mock_delivery_cls.return_value = Mock()

        Notification.objects.create(
            user=user,
            notification_type="reminder",
            title="Future",
            body="Body",
            scheduled_for=timezone.now() + timedelta(hours=1),
            status="pending",
        )

        from apps.notifications.tasks import process_pending_notifications

        result = process_pending_notifications()
        assert result["sent"] == 0
        assert result["failed"] == 0


# ──────────────────────────────────────────────────────────────────────
#  generate_daily_motivation
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestGenerateDailyMotivation:
    """Tests for generate_daily_motivation task."""

    @patch("apps.notifications.tasks.AIUsageTracker")
    @patch("apps.notifications.tasks.OpenAIService")
    def test_generates_motivation_for_active_dream_users(
        self, mock_ai_cls, mock_tracker_cls, user
    ):
        """generate_daily_motivation creates notifications for users with active dreams."""
        # Setup: user needs active dream and motivation prefs enabled
        user.notification_prefs = {"motivation": True}
        user.save(update_fields=["notification_prefs"])

        Dream.objects.create(
            user=user, title="Dream", description="d", status="active"
        )

        mock_ai = Mock()
        mock_ai.generate_motivational_message.return_value = "Keep going!"
        mock_ai_cls.return_value = mock_ai

        mock_tracker = Mock()
        mock_tracker.check_quota.return_value = (True, {})
        mock_tracker_cls.return_value = mock_tracker

        from apps.notifications.tasks import generate_daily_motivation

        result = generate_daily_motivation()
        assert result["created"] >= 1

        assert Notification.objects.filter(
            user=user, notification_type="motivation"
        ).exists()

    @patch("apps.notifications.tasks.AIUsageTracker")
    @patch("apps.notifications.tasks.OpenAIService")
    def test_skips_users_at_quota(self, mock_ai_cls, mock_tracker_cls, user):
        """generate_daily_motivation skips users who have reached AI quota."""
        user.notification_prefs = {"motivation": True}
        user.save(update_fields=["notification_prefs"])

        Dream.objects.create(
            user=user, title="Dream", description="d", status="active"
        )

        mock_ai_cls.return_value = Mock()
        mock_tracker = Mock()
        mock_tracker.check_quota.return_value = (False, {})
        mock_tracker_cls.return_value = mock_tracker

        from apps.notifications.tasks import generate_daily_motivation

        result = generate_daily_motivation()
        assert result["created"] == 0


# ──────────────────────────────────────────────────────────────────────
#  send_reminder_notifications
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestSendReminderNotifications:
    """Tests for send_reminder_notifications task."""

    def test_creates_reminder_for_goals_with_reminders(self, user):
        """send_reminder_notifications creates reminders for goals within the window."""
        dream = Dream.objects.create(
            user=user, title="D", description="d", status="active"
        )
        now = timezone.now()
        Goal.objects.create(
            dream=dream,
            title="Goal with Reminder",
            order=1,
            status="pending",
            reminder_enabled=True,
            reminder_time=now + timedelta(minutes=5),
        )

        from apps.notifications.tasks import send_reminder_notifications

        result = send_reminder_notifications()
        assert result["created"] == 1
        assert Notification.objects.filter(
            user=user, notification_type="reminder"
        ).exists()

    def test_skips_goals_without_reminders(self, user):
        """send_reminder_notifications skips goals with reminder_enabled=False."""
        dream = Dream.objects.create(
            user=user, title="D", description="d", status="active"
        )
        Goal.objects.create(
            dream=dream,
            title="No Reminder",
            order=1,
            status="pending",
            reminder_enabled=False,
            reminder_time=timezone.now() + timedelta(minutes=5),
        )

        from apps.notifications.tasks import send_reminder_notifications

        result = send_reminder_notifications()
        assert result["created"] == 0


# ──────────────────────────────────────────────────────────────────────
#  cleanup_old_notifications
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestCleanupOldNotifications:
    """Tests for cleanup_old_notifications task."""

    def test_deletes_old_read_notifications(self, user):
        """cleanup_old_notifications deletes read notifications older than 30 days."""
        old_time = timezone.now() - timedelta(days=35)

        notif = Notification.objects.create(
            user=user,
            notification_type="reminder",
            title="Old",
            body="Old body",
            scheduled_for=old_time,
            status="sent",
        )
        # Manually set read_at to a past date
        Notification.objects.filter(id=notif.id).update(read_at=old_time)

        from apps.notifications.tasks import cleanup_old_notifications

        result = cleanup_old_notifications()
        assert result["deleted"] == 1
        assert not Notification.objects.filter(id=notif.id).exists()

    def test_keeps_recent_notifications(self, user):
        """cleanup_old_notifications keeps notifications read less than 30 days ago."""
        notif = Notification.objects.create(
            user=user,
            notification_type="reminder",
            title="Recent",
            body="Recent body",
            scheduled_for=timezone.now(),
            status="sent",
        )
        notif.mark_read()

        from apps.notifications.tasks import cleanup_old_notifications

        result = cleanup_old_notifications()
        assert result["deleted"] == 0
        assert Notification.objects.filter(id=notif.id).exists()


# ──────────────────────────────────────────────────────────────────────
#  send_streak_milestone_notification
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestSendStreakMilestoneNotification:
    """Tests for send_streak_milestone_notification task."""

    def test_sends_at_milestone(self, user):
        """Sends notification at milestone streak days (7, 14, 30, etc.)."""
        from apps.notifications.tasks import send_streak_milestone_notification

        result = send_streak_milestone_notification(str(user.id), 7)
        assert result["sent"] is True
        assert result["days"] == 7

        assert Notification.objects.filter(
            user=user, notification_type="achievement"
        ).exists()

    def test_does_not_send_at_non_milestone(self, user):
        """Does not send notification at non-milestone streak days."""
        from apps.notifications.tasks import send_streak_milestone_notification

        result = send_streak_milestone_notification(str(user.id), 5)
        assert result["sent"] is False

    def test_handles_missing_user(self, db):
        """Handles missing user gracefully."""
        from apps.notifications.tasks import send_streak_milestone_notification

        result = send_streak_milestone_notification(str(uuid.uuid4()), 7)
        assert result["sent"] is False
        assert result["error"] == "user_not_found"


# ──────────────────────────────────────────────────────────────────────
#  send_level_up_notification
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestSendLevelUpNotification:
    """Tests for send_level_up_notification task."""

    def test_sends_level_up(self, user):
        """Sends notification when user levels up."""
        from apps.notifications.tasks import send_level_up_notification

        result = send_level_up_notification(str(user.id), 5)
        assert result["sent"] is True
        assert result["level"] == 5
        assert Notification.objects.filter(
            user=user, notification_type="achievement"
        ).exists()

    def test_handles_missing_user(self, db):
        """Handles missing user gracefully."""
        from apps.notifications.tasks import send_level_up_notification

        result = send_level_up_notification(str(uuid.uuid4()), 5)
        assert result["sent"] is False
        assert result["error"] == "user_not_found"


# ──────────────────────────────────────────────────────────────────────
#  cleanup_stale_fcm_tokens
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestCleanupStaleFcmTokens:
    """Tests for cleanup_stale_fcm_tokens task."""

    def test_deactivates_stale_tokens(self, user):
        """Deactivates device registrations not updated in 60+ days."""
        device = UserDevice.objects.create(
            user=user,
            fcm_token="stale-token-cleanup-test-" + uuid.uuid4().hex,
            platform="android",
            is_active=True,
        )
        # Manually set updated_at to 90 days ago
        stale_time = timezone.now() - timedelta(days=90)
        UserDevice.objects.filter(id=device.id).update(updated_at=stale_time)

        from apps.notifications.tasks import cleanup_stale_fcm_tokens

        result = cleanup_stale_fcm_tokens()
        assert result["deactivated"] >= 1

        device.refresh_from_db()
        assert device.is_active is False

    def test_keeps_recent_tokens(self, user):
        """Keeps device registrations updated recently."""
        device = UserDevice.objects.create(
            user=user,
            fcm_token="recent-token-cleanup-test-" + uuid.uuid4().hex,
            platform="android",
            is_active=True,
        )

        from apps.notifications.tasks import cleanup_stale_fcm_tokens

        result = cleanup_stale_fcm_tokens()
        device.refresh_from_db()
        assert device.is_active is True


# ──────────────────────────────────────────────────────────────────────
#  check_inactive_users
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestCheckInactiveUsers:
    """Tests for check_inactive_users task."""

    @patch("apps.notifications.tasks.AIUsageTracker")
    @patch("apps.notifications.tasks.OpenAIService")
    def test_sends_rescue_for_inactive_user(
        self, mock_ai_cls, mock_tracker_cls, db
    ):
        """Creates rescue notification for users inactive 3+ days."""
        inactive_user = User.objects.create_user(
            email="rescue@test.com",
            password="testpass123",
            last_activity=timezone.now() - timedelta(days=5),
        )
        Dream.objects.create(
            user=inactive_user, title="Dream", description="d", status="active"
        )

        mock_ai = Mock()
        mock_ai.generate_rescue_message.return_value = "Come back!"
        mock_ai_cls.return_value = mock_ai

        mock_tracker = Mock()
        mock_tracker.check_quota.return_value = (True, {})
        mock_tracker_cls.return_value = mock_tracker

        from apps.notifications.tasks import check_inactive_users

        result = check_inactive_users()
        assert result["created"] >= 1
        assert Notification.objects.filter(
            user=inactive_user, notification_type="rescue"
        ).exists()


# ──────────────────────────────────────────────────────────────────────
#  Helpers
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestPickMotivationalMessage:
    """Tests for the _pick_motivational_message helper."""

    def test_zero_stats_returns_fresh_start(self):
        from apps.notifications.tasks import _pick_motivational_message

        msg = _pick_motivational_message(0, 0)
        assert "fresh start" in msg.lower()

    def test_high_tasks_returns_fire_message(self):
        from apps.notifications.tasks import _pick_motivational_message

        msg = _pick_motivational_message(20, 0)
        assert "fire" in msg.lower() or "incredible" in msg.lower()

    def test_high_streak_returns_streak_message(self):
        from apps.notifications.tasks import _pick_motivational_message

        msg = _pick_motivational_message(0, 7)
        assert "streak" in msg.lower()

    def test_moderate_stats_returns_from_list(self):
        from apps.notifications.tasks import (
            MOTIVATIONAL_MESSAGES,
            _pick_motivational_message,
        )

        msg = _pick_motivational_message(3, 2)
        assert msg in MOTIVATIONAL_MESSAGES
