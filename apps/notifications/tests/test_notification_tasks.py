"""
Tests for apps/notifications/tasks.py — all Celery tasks.

Covers:
- process_pending_notifications
- generate_daily_motivation
- send_weekly_digests / send_user_digest
- check_inactive_users
- send_reminder_notifications
- cleanup_old_notifications
- send_streak_milestone_notification
- send_level_up_notification
- expire_ringing_calls
- check_due_tasks
- cleanup_stale_fcm_tokens
- Helper: _pick_motivational_message
"""

import uuid
from datetime import timedelta
from unittest.mock import Mock, patch

import pytest
from django.utils import timezone

from apps.dreams.models import Dream, Goal, Task
from apps.notifications.models import Notification, UserDevice
from apps.users.models import User


# ──────────────────────────────────────────────────────────────────────
#  process_pending_notifications
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestProcessPendingNotifications:
    """Tests for process_pending_notifications task."""

    @patch("apps.notifications.services.NotificationDeliveryService")
    def test_processes_pending_notifications(self, mock_delivery_cls, user):
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

    @patch("apps.notifications.services.NotificationDeliveryService")
    def test_reschedules_dnd_notifications(self, mock_delivery_cls, user):
        """Notifications that fail should_send() get rescheduled."""
        mock_delivery_cls.return_value = Mock()

        notif = Notification.objects.create(
            user=user,
            notification_type="reminder",
            title="DND",
            body="Body",
            scheduled_for=timezone.now() - timedelta(minutes=1),
            status="pending",
        )

        with patch.object(
            Notification, "should_send", return_value=False
        ):
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

    @patch("apps.notifications.tasks.AIUsageTracker")
    @patch("apps.notifications.tasks.OpenAIService")
    def test_handles_openai_error_gracefully(
        self, mock_ai_cls, mock_tracker_cls, user
    ):
        """OpenAI errors for a user don't crash the whole task."""
        from core.exceptions import OpenAIError

        user.notification_prefs = {"motivation": True}
        user.save(update_fields=["notification_prefs"])

        Dream.objects.create(
            user=user, title="Dream", description="d", status="active"
        )

        mock_ai = Mock()
        mock_ai.generate_motivational_message.side_effect = OpenAIError("API fail")
        mock_ai_cls.return_value = mock_ai

        mock_tracker = Mock()
        mock_tracker.check_quota.return_value = (True, {})
        mock_tracker_cls.return_value = mock_tracker

        from apps.notifications.tasks import generate_daily_motivation

        result = generate_daily_motivation()
        assert result["created"] == 0


# ──────────────────────────────────────────────────────────────────────
#  send_weekly_digests / send_user_digest
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestSendWeeklyDigests:
    """Tests for send_weekly_digests and send_user_digest tasks."""

    @patch("apps.notifications.tasks.send_user_digest")
    def test_dispatches_for_active_users(self, mock_send_user_digest, user):
        from apps.notifications.tasks import send_weekly_digests

        result = send_weekly_digests()
        assert result["dispatched"] >= 1
        mock_send_user_digest.delay.assert_called()

    @patch("apps.notifications.tasks.send_user_digest")
    def test_skips_users_with_disabled_weekly_report(self, mock_send, db):
        user = User.objects.create_user(
            email="nodigest_ntask@example.com",
            password="testpassword123",
            notification_prefs={"weekly_report": False},
        )

        from apps.notifications.tasks import send_weekly_digests

        result = send_weekly_digests()
        calls = mock_send.delay.call_args_list
        user_ids_dispatched = [c[0][0] for c in calls]
        assert str(user.id) not in user_ids_dispatched

    @patch("apps.notifications.tasks._send_digest_email")
    @patch("apps.notifications.tasks._send_digest_push")
    def test_send_user_digest_creates_notification(
        self, mock_push, mock_email, user
    ):
        from apps.notifications.tasks import send_user_digest

        result = send_user_digest(str(user.id))

        assert result["sent"] is True
        assert "notification_id" in result
        mock_push.assert_called_once()
        mock_email.assert_called_once()

        notif = Notification.objects.get(id=result["notification_id"])
        assert notif.notification_type == "weekly_report"
        assert notif.status == "sent"

    def test_send_user_digest_user_not_found(self, db):
        from apps.notifications.tasks import send_user_digest

        result = send_user_digest(str(uuid.uuid4()))
        assert result["sent"] is False
        assert result["reason"] == "user_not_found"

    @patch("apps.notifications.tasks._send_digest_email")
    @patch("apps.notifications.tasks._send_digest_push")
    def test_send_user_digest_includes_task_stats(
        self, mock_push, mock_email, user
    ):
        dream = Dream.objects.create(
            user=user, title="D", description="d", status="active"
        )
        goal = Goal.objects.create(dream=dream, title="G", order=1)
        Task.objects.create(
            goal=goal, title="Done", order=1, status="completed",
            completed_at=timezone.now(),
        )

        from apps.notifications.tasks import send_user_digest

        result = send_user_digest(str(user.id))
        assert result["sent"] is True
        assert result["tasks_completed"] == 1

    @patch("apps.notifications.tasks.send_weekly_digests")
    def test_send_weekly_report_delegates(self, mock_digests):
        """send_weekly_report is a legacy alias that delegates to send_weekly_digests."""
        mock_digests.return_value = {"dispatched": 5}

        from apps.notifications.tasks import send_weekly_report

        send_weekly_report()
        mock_digests.assert_called_once()


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
        inactive_user = User.objects.create_user(
            email="rescue_ntask@test.com",
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

    @patch("apps.notifications.tasks.AIUsageTracker")
    @patch("apps.notifications.tasks.OpenAIService")
    def test_skips_recently_active_users(
        self, mock_ai_cls, mock_tracker_cls, user
    ):
        """Users active within last 3 days should not get rescue notifications."""
        user.last_activity = timezone.now()
        user.save(update_fields=["last_activity"])

        Dream.objects.create(
            user=user, title="Dream", description="d", status="active"
        )

        from apps.notifications.tasks import check_inactive_users

        result = check_inactive_users()
        assert result["created"] == 0


# ──────────────────────────────────────────────────────────────────────
#  send_reminder_notifications
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestSendReminderNotifications:
    """Tests for send_reminder_notifications task."""

    def test_creates_reminder_for_goals_with_reminders(self, user):
        dream = Dream.objects.create(
            user=user, title="D", description="d", status="active"
        )
        now = timezone.now()
        Goal.objects.create(
            dream=dream, title="Goal", order=1, status="pending",
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
        dream = Dream.objects.create(
            user=user, title="D", description="d", status="active"
        )
        Goal.objects.create(
            dream=dream, title="No Rem", order=1, status="pending",
            reminder_enabled=False,
            reminder_time=timezone.now() + timedelta(minutes=5),
        )

        from apps.notifications.tasks import send_reminder_notifications

        result = send_reminder_notifications()
        assert result["created"] == 0

    def test_skips_already_sent_reminders(self, user):
        """Does not duplicate reminders sent within the last hour."""
        dream = Dream.objects.create(
            user=user, title="D", description="d", status="active"
        )
        goal = Goal.objects.create(
            dream=dream, title="G", order=1, status="pending",
            reminder_enabled=True,
            reminder_time=timezone.now() + timedelta(minutes=5),
        )
        # Pre-create a reminder notification
        Notification.objects.create(
            user=user,
            notification_type="reminder",
            title="Reminder",
            body="Body",
            scheduled_for=timezone.now(),
            data={"goal_id": str(goal.id)},
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
        old_time = timezone.now() - timedelta(days=35)
        notif = Notification.objects.create(
            user=user,
            notification_type="reminder",
            title="Old",
            body="Old body",
            scheduled_for=old_time,
            status="sent",
        )
        Notification.objects.filter(id=notif.id).update(read_at=old_time)

        from apps.notifications.tasks import cleanup_old_notifications

        result = cleanup_old_notifications()
        assert result["deleted"] == 1
        assert not Notification.objects.filter(id=notif.id).exists()

    def test_keeps_recent_notifications(self, user):
        notif = Notification.objects.create(
            user=user,
            notification_type="reminder",
            title="Recent",
            body="Body",
            scheduled_for=timezone.now(),
            status="sent",
        )
        notif.mark_read()

        from apps.notifications.tasks import cleanup_old_notifications

        result = cleanup_old_notifications()
        assert result["deleted"] == 0
        assert Notification.objects.filter(id=notif.id).exists()

    def test_keeps_unread_old_notifications(self, user):
        """Old notifications that haven't been read should NOT be deleted."""
        old_time = timezone.now() - timedelta(days=35)
        notif = Notification.objects.create(
            user=user,
            notification_type="reminder",
            title="Old Unread",
            body="Body",
            scheduled_for=old_time,
            status="sent",
        )

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
        from apps.notifications.tasks import send_streak_milestone_notification

        result = send_streak_milestone_notification(str(user.id), 7)
        assert result["sent"] is True
        assert result["days"] == 7
        assert Notification.objects.filter(
            user=user, notification_type="achievement"
        ).exists()

    def test_sends_at_all_milestones(self, user):
        from apps.notifications.tasks import send_streak_milestone_notification

        for days in [7, 14, 30, 60, 100, 365]:
            result = send_streak_milestone_notification(str(user.id), days)
            assert result["sent"] is True

    def test_does_not_send_at_non_milestone(self, user):
        from apps.notifications.tasks import send_streak_milestone_notification

        result = send_streak_milestone_notification(str(user.id), 5)
        assert result["sent"] is False

    def test_handles_missing_user(self, db):
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
        from apps.notifications.tasks import send_level_up_notification

        result = send_level_up_notification(str(user.id), 5)
        assert result["sent"] is True
        assert result["level"] == 5
        assert Notification.objects.filter(
            user=user, notification_type="achievement"
        ).exists()

    def test_handles_missing_user(self, db):
        from apps.notifications.tasks import send_level_up_notification

        result = send_level_up_notification(str(uuid.uuid4()), 5)
        assert result["sent"] is False
        assert result["error"] == "user_not_found"


# ──────────────────────────────────────────────────────────────────────
#  check_due_tasks
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestCheckDueTasks:
    """Tests for check_due_tasks task."""

    def _setup_due_task(self, user):
        dream = Dream.objects.create(
            user=user, title="Dream", description="d", status="active",
        )
        goal = Goal.objects.create(dream=dream, title="G", order=1)
        return Task.objects.create(
            goal=goal, title="Due", order=1, status="pending",
            scheduled_date=timezone.now() + timedelta(minutes=1),
        )

    @patch("apps.notifications.fcm_service.FCMService")
    def test_sends_notification_for_due_task(self, mock_fcm_cls, user):
        mock_fcm = Mock()
        mock_fcm_cls.return_value = mock_fcm
        self._setup_due_task(user)

        UserDevice.objects.create(
            user=user, fcm_token="tok-due-ntask",
            platform="android", is_active=True,
        )

        from apps.notifications.tasks import check_due_tasks

        result = check_due_tasks()
        assert result["sent"] >= 1
        mock_fcm.send_to_token.assert_called()
        assert Notification.objects.filter(
            user=user, notification_type="task_due"
        ).exists()

    @patch("apps.notifications.fcm_service.FCMService")
    def test_skips_already_notified_task(self, mock_fcm_cls, user):
        mock_fcm = Mock()
        mock_fcm_cls.return_value = mock_fcm
        task = self._setup_due_task(user)

        Notification.objects.create(
            user=user,
            notification_type="task_due",
            title="Due",
            body="Work",
            scheduled_for=timezone.now(),
            data={"task_id": str(task.id)},
        )

        from apps.notifications.tasks import check_due_tasks

        result = check_due_tasks()
        assert result["sent"] == 0

    @patch("apps.notifications.fcm_service.FCMService")
    def test_no_due_tasks(self, mock_fcm_cls, user):
        mock_fcm_cls.return_value = Mock()
        from apps.notifications.tasks import check_due_tasks

        result = check_due_tasks()
        assert result["sent"] == 0


# ──────────────────────────────────────────────────────────────────────
#  expire_ringing_calls
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestExpireRingingCalls:
    """Tests for expire_ringing_calls task."""

    def _create_call(self, caller, callee, created_at=None, status="ringing"):
        from apps.chat.models import Call

        call = Call.objects.create(
            caller=caller, callee=callee,
            call_type="voice", status=status,
        )
        if created_at:
            Call.objects.filter(id=call.id).update(created_at=created_at)
        return call

    @patch("channels.layers.get_channel_layer")
    def test_expires_stale_ringing_call(self, mock_channel_layer, db):
        mock_channel_layer.return_value = None

        caller = User.objects.create_user(
            email="caller_ntask@test.com", password="pass", display_name="Caller"
        )
        callee = User.objects.create_user(
            email="callee_ntask@test.com", password="pass", display_name="Callee"
        )

        stale_time = timezone.now() - timedelta(seconds=60)
        self._create_call(caller, callee, created_at=stale_time)

        from apps.notifications.tasks import expire_ringing_calls

        result = expire_ringing_calls()
        assert result["expired"] >= 1
        assert Notification.objects.filter(
            user=callee, notification_type="missed_call"
        ).exists()
        assert Notification.objects.filter(
            user=caller, notification_type="missed_call"
        ).exists()


# ──────────────────────────────────────────────────────────────────────
#  cleanup_stale_fcm_tokens
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestCleanupStaleFcmTokens:
    """Tests for cleanup_stale_fcm_tokens task."""

    def test_deactivates_stale_tokens(self, user):
        device = UserDevice.objects.create(
            user=user,
            fcm_token="stale-ntask-" + uuid.uuid4().hex,
            platform="android",
            is_active=True,
        )
        stale_time = timezone.now() - timedelta(days=90)
        UserDevice.objects.filter(id=device.id).update(updated_at=stale_time)

        from apps.notifications.tasks import cleanup_stale_fcm_tokens

        result = cleanup_stale_fcm_tokens()
        assert result["deactivated"] >= 1

        device.refresh_from_db()
        assert device.is_active is False

    def test_keeps_recent_tokens(self, user):
        device = UserDevice.objects.create(
            user=user,
            fcm_token="recent-ntask-" + uuid.uuid4().hex,
            platform="android",
            is_active=True,
        )

        from apps.notifications.tasks import cleanup_stale_fcm_tokens

        result = cleanup_stale_fcm_tokens()
        device.refresh_from_db()
        assert device.is_active is True


# ──────────────────────────────────────────────────────────────────────
#  Helpers
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestPickMotivationalMessage:
    """Tests for _pick_motivational_message helper."""

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
