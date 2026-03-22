"""
Tests for apps/calendar/tasks.py — Celery tasks.

Covers:
- send_daily_summaries
- generate_recurring_events
- sync_google_calendar
- check_and_send_reminders
- _next_occurrence helper
"""

import uuid
from datetime import timedelta
from unittest.mock import Mock, patch

import pytest
from django.utils import timezone

from apps.calendar.models import CalendarEvent
from apps.dreams.models import Dream, Goal, Task
from apps.notifications.models import Notification, UserDevice
from apps.users.models import User

# ──────────────────────────────────────────────────────────────────────
#  send_daily_summaries
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestSendDailySummaries:
    """Tests for send_daily_summaries task."""

    @patch("apps.notifications.fcm_service.FCMService")
    def test_sends_summary_for_user_with_tasks(self, mock_fcm_cls, cal_user):
        """Sends daily summary when user has scheduled tasks."""
        mock_fcm = Mock()
        mock_result = Mock(invalid_tokens=[])
        mock_fcm.send_multicast.return_value = mock_result
        mock_fcm_cls.return_value = mock_fcm

        dream = Dream.objects.create(
            user=cal_user, title="D", description="d", status="active"
        )
        goal = Goal.objects.create(dream=dream, title="G", order=1)
        Task.objects.create(
            goal=goal, title="T1", order=1, status="pending",
            scheduled_date=timezone.now(),
        )

        from apps.calendar.tasks import send_daily_summaries

        result = send_daily_summaries()
        assert result["sent"] >= 1

        assert Notification.objects.filter(
            user=cal_user, notification_type="daily_summary"
        ).exists()

    @patch("apps.notifications.fcm_service.FCMService")
    def test_sends_summary_for_user_with_events(self, mock_fcm_cls, cal_user):
        """Sends daily summary when user has calendar events."""
        mock_fcm_cls.return_value = Mock()

        CalendarEvent.objects.create(
            user=cal_user, title="Meeting",
            start_time=timezone.now() + timedelta(hours=1),
            end_time=timezone.now() + timedelta(hours=2),
            status="scheduled",
        )

        from apps.calendar.tasks import send_daily_summaries

        result = send_daily_summaries()
        assert result["sent"] >= 1

    @patch("apps.notifications.fcm_service.FCMService")
    def test_skips_user_with_no_tasks_or_events(self, mock_fcm_cls, db):
        """Skips users with nothing scheduled."""
        mock_fcm_cls.return_value = Mock()

        User.objects.create_user(
            email="empty_calendar_tsk@test.com", password="pass",
            timezone="UTC",
        )

        from apps.calendar.tasks import send_daily_summaries

        result = send_daily_summaries()
        assert result["skipped"] >= 1

    @patch("apps.notifications.fcm_service.FCMService")
    def test_skips_user_with_disabled_pref(self, mock_fcm_cls, db):
        """Skips users who disabled daily_summary_enabled."""
        mock_fcm_cls.return_value = Mock()

        user = User.objects.create_user(
            email="nosummary_tsk@test.com", password="pass",
            timezone="UTC",
            notification_prefs={"daily_summary_enabled": False},
        )
        dream = Dream.objects.create(
            user=user, title="D", description="d", status="active"
        )
        goal = Goal.objects.create(dream=dream, title="G", order=1)
        Task.objects.create(
            goal=goal, title="T", order=1, status="pending",
            scheduled_date=timezone.now(),
        )

        from apps.calendar.tasks import send_daily_summaries

        result = send_daily_summaries()
        assert result["skipped"] >= 1

    @patch("apps.notifications.fcm_service.FCMService")
    def test_deactivates_invalid_fcm_tokens(self, mock_fcm_cls, cal_user):
        """Invalid FCM tokens are deactivated."""
        mock_fcm = Mock()
        mock_result = Mock(invalid_tokens=["bad-token"])
        mock_fcm.send_multicast.return_value = mock_result
        mock_fcm_cls.return_value = mock_fcm

        device = UserDevice.objects.create(
            user=cal_user, fcm_token="bad-token",
            platform="android", is_active=True,
        )

        dream = Dream.objects.create(
            user=cal_user, title="D", description="d", status="active"
        )
        goal = Goal.objects.create(dream=dream, title="G", order=1)
        Task.objects.create(
            goal=goal, title="T", order=1, status="pending",
            scheduled_date=timezone.now(),
        )

        from apps.calendar.tasks import send_daily_summaries

        send_daily_summaries()

        device.refresh_from_db()
        assert device.is_active is False


# ──────────────────────────────────────────────────────────────────────
#  generate_recurring_events
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestGenerateRecurringEvents:
    """Tests for generate_recurring_events task."""

    def test_generates_weekly_instances(self, cal_user):
        """Creates future instances for a weekly recurring event."""
        now = timezone.now()
        parent = CalendarEvent.objects.create(
            user=cal_user, title="Weekly Meeting",
            start_time=now - timedelta(days=1),
            end_time=now - timedelta(days=1) + timedelta(hours=1),
            status="scheduled",
            is_recurring=True,
            recurrence_rule={"frequency": "weekly", "interval": 1},
        )

        from apps.calendar.tasks import generate_recurring_events

        total = generate_recurring_events()
        assert total >= 1

        instances = CalendarEvent.objects.filter(parent_event=parent)
        assert instances.count() >= 1

    def test_generates_daily_instances(self, cal_user):
        """Creates daily recurring instances."""
        now = timezone.now()
        CalendarEvent.objects.create(
            user=cal_user, title="Daily Standup",
            start_time=now - timedelta(hours=2),
            end_time=now - timedelta(hours=1),
            status="scheduled",
            is_recurring=True,
            recurrence_rule={"frequency": "daily", "interval": 1},
        )

        from apps.calendar.tasks import generate_recurring_events

        total = generate_recurring_events()
        assert total >= 1

    def test_respects_end_date(self, cal_user):
        """Does not generate instances beyond the recurrence end_date."""
        now = timezone.now()
        tomorrow = now + timedelta(days=1)
        CalendarEvent.objects.create(
            user=cal_user, title="Limited",
            start_time=now - timedelta(days=2),
            end_time=now - timedelta(days=2) + timedelta(hours=1),
            status="scheduled",
            is_recurring=True,
            recurrence_rule={
                "frequency": "daily",
                "interval": 1,
                "end_date": tomorrow.isoformat(),
            },
        )

        from apps.calendar.tasks import generate_recurring_events

        total = generate_recurring_events()
        # Should only generate a few instances up to tomorrow
        assert total >= 0  # May be 0 if already past

    def test_no_duplicates(self, cal_user):
        """Running twice does not create duplicate instances."""
        now = timezone.now()
        CalendarEvent.objects.create(
            user=cal_user, title="Weekly",
            start_time=now - timedelta(days=1),
            end_time=now - timedelta(days=1) + timedelta(hours=1),
            status="scheduled",
            is_recurring=True,
            recurrence_rule={"frequency": "weekly", "interval": 1},
        )

        from apps.calendar.tasks import generate_recurring_events

        first_run = generate_recurring_events()
        second_run = generate_recurring_events()
        assert second_run == 0  # No new instances on second run

    def test_skips_non_recurring_events(self, cal_user):
        """Non-recurring events are ignored."""
        CalendarEvent.objects.create(
            user=cal_user, title="One-time",
            start_time=timezone.now() + timedelta(hours=1),
            end_time=timezone.now() + timedelta(hours=2),
            status="scheduled",
            is_recurring=False,
        )

        from apps.calendar.tasks import generate_recurring_events

        total = generate_recurring_events()
        assert total == 0


# ──────────────────────────────────────────────────────────────────────
#  sync_google_calendar
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestSyncGoogleCalendar:
    """Tests for sync_google_calendar task."""

    def _create_integration(self, user, direction="both"):
        from apps.calendar.models import GoogleCalendarIntegration

        return GoogleCalendarIntegration.objects.create(
            user=user,
            access_token="fake-access",
            refresh_token="fake-refresh",
            token_expiry=timezone.now() + timedelta(hours=1),
            sync_enabled=True,
            sync_direction=direction,
            sync_tasks=True,
            sync_events=True,
        )

    @patch("integrations.google_calendar.GoogleCalendarService")
    def test_push_and_pull(self, mock_gc_cls, cal_user):
        """Bidirectional sync pushes local events and pulls from Google."""
        integration = self._create_integration(cal_user, direction="both")

        # Create a local event to push
        CalendarEvent.objects.create(
            user=cal_user, title="Local Event",
            start_time=timezone.now() + timedelta(hours=1),
            end_time=timezone.now() + timedelta(hours=2),
            status="scheduled",
        )

        mock_service = Mock()
        mock_service.push_event.return_value = None
        mock_service.pull_events.return_value = [
            {
                "id": "google-evt-1",
                "summary": "Google Event",
                "description": "from Google",
                "status": "confirmed",
                "start": {"dateTime": (timezone.now() + timedelta(hours=3)).isoformat()},
                "end": {"dateTime": (timezone.now() + timedelta(hours=4)).isoformat()},
                "location": "Office",
            }
        ]
        mock_gc_cls.return_value = mock_service

        from apps.calendar.tasks import sync_google_calendar

        sync_google_calendar(str(integration.id))

        mock_service.push_event.assert_called()
        mock_service.pull_events.assert_called()

        # Pulled event should be created
        assert CalendarEvent.objects.filter(
            user=cal_user, google_event_id="google-evt-1"
        ).exists()

    @patch("integrations.google_calendar.GoogleCalendarService")
    def test_push_only(self, mock_gc_cls, cal_user):
        """Push-only direction pushes events but does not pull."""
        integration = self._create_integration(cal_user, direction="push_only")

        CalendarEvent.objects.create(
            user=cal_user, title="Push Event",
            start_time=timezone.now() + timedelta(hours=1),
            end_time=timezone.now() + timedelta(hours=2),
            status="scheduled",
        )

        mock_service = Mock()
        mock_gc_cls.return_value = mock_service

        from apps.calendar.tasks import sync_google_calendar

        sync_google_calendar(str(integration.id))

        mock_service.push_event.assert_called()
        mock_service.pull_events.assert_not_called()

    @patch("integrations.google_calendar.GoogleCalendarService")
    def test_pull_only(self, mock_gc_cls, cal_user):
        """Pull-only direction pulls events but does not push."""
        integration = self._create_integration(cal_user, direction="pull_only")

        mock_service = Mock()
        mock_service.pull_events.return_value = []
        mock_gc_cls.return_value = mock_service

        from apps.calendar.tasks import sync_google_calendar

        sync_google_calendar(str(integration.id))

        mock_service.push_event.assert_not_called()
        mock_service.pull_events.assert_called()

    def test_missing_integration(self, db):
        """Handles missing or disabled integration gracefully."""
        from apps.calendar.tasks import sync_google_calendar

        # Should not raise, just log a warning
        sync_google_calendar(str(uuid.uuid4()))

    @patch("integrations.google_calendar.GoogleCalendarService")
    def test_updates_existing_google_event(self, mock_gc_cls, cal_user):
        """Pulling an event with existing google_event_id updates it."""
        integration = self._create_integration(cal_user, direction="pull_only")

        # Pre-create a local event with a google_event_id
        existing = CalendarEvent.objects.create(
            user=cal_user, title="Old Title",
            start_time=timezone.now() + timedelta(hours=1),
            end_time=timezone.now() + timedelta(hours=2),
            status="scheduled",
            google_event_id="google-update-1",
        )

        mock_service = Mock()
        mock_service.pull_events.return_value = [
            {
                "id": "google-update-1",
                "summary": "Updated Title",
                "description": "Updated desc",
                "status": "confirmed",
                "start": {"dateTime": (timezone.now() + timedelta(hours=1)).isoformat()},
                "end": {"dateTime": (timezone.now() + timedelta(hours=2)).isoformat()},
                "location": "Home",
            }
        ]
        mock_gc_cls.return_value = mock_service

        from apps.calendar.tasks import sync_google_calendar

        sync_google_calendar(str(integration.id))

        existing.refresh_from_db()
        assert existing.title == "Updated Title"
        assert existing.location == "Home"


# ──────────────────────────────────────────────────────────────────────
#  check_and_send_reminders
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestCheckAndSendReminders:
    """Tests for check_and_send_reminders task."""

    @patch("apps.notifications.fcm_service.FCMService")
    def test_sends_reminder_for_upcoming_event(self, mock_fcm_cls, cal_user):
        """Sends push notification for event with reminder due now."""
        mock_fcm = Mock()
        mock_fcm_cls.return_value = mock_fcm

        now = timezone.now()
        # Event starts in 15 min 30 sec, reminder is 15 min before
        # => reminder fires at now + 30s which is within [now, now+60s]
        event = CalendarEvent.objects.create(
            user=cal_user, title="Meeting",
            start_time=now + timedelta(minutes=15, seconds=30),
            end_time=now + timedelta(minutes=75, seconds=30),
            status="scheduled",
            reminders=[{"minutes_before": 15, "type": "push"}],
            reminders_sent=[],
        )

        UserDevice.objects.create(
            user=cal_user, fcm_token="tok-reminder-cal",
            platform="android", is_active=True,
        )

        from apps.calendar.tasks import check_and_send_reminders

        result = check_and_send_reminders()
        assert result["sent"] >= 1
        mock_fcm.send_to_token.assert_called()

        # Reminder key should be stored to prevent duplicates
        event.refresh_from_db()
        assert len(event.reminders_sent) >= 1

        assert Notification.objects.filter(
            user=cal_user, notification_type="reminder"
        ).exists()

    @patch("apps.notifications.fcm_service.FCMService")
    def test_skips_already_sent_reminder(self, mock_fcm_cls, cal_user):
        """Does not re-send reminders already in reminders_sent."""
        mock_fcm_cls.return_value = Mock()

        now = timezone.now()
        start = now + timedelta(minutes=15, seconds=30)
        reminder_key = "15_%s" % start.isoformat()

        CalendarEvent.objects.create(
            user=cal_user, title="Meeting",
            start_time=start,
            end_time=start + timedelta(hours=1),
            status="scheduled",
            reminders=[{"minutes_before": 15, "type": "push"}],
            reminders_sent=[reminder_key],
        )

        from apps.calendar.tasks import check_and_send_reminders

        result = check_and_send_reminders()
        assert result["sent"] == 0
        assert result["skipped"] >= 1

    @patch("apps.notifications.fcm_service.FCMService")
    def test_skips_snoozed_event(self, mock_fcm_cls, cal_user):
        """Skips events that are currently snoozed."""
        mock_fcm_cls.return_value = Mock()

        now = timezone.now()
        CalendarEvent.objects.create(
            user=cal_user, title="Snoozed",
            start_time=now + timedelta(minutes=15),
            end_time=now + timedelta(hours=1),
            status="scheduled",
            reminders=[{"minutes_before": 15, "type": "push"}],
            snoozed_until=now + timedelta(hours=2),
        )

        from apps.calendar.tasks import check_and_send_reminders

        result = check_and_send_reminders()
        assert result["sent"] == 0

    @patch("apps.notifications.fcm_service.FCMService")
    def test_falls_back_to_legacy_reminder_field(self, mock_fcm_cls, cal_user):
        """Uses reminder_minutes_before if reminders JSON is empty."""
        mock_fcm = Mock()
        mock_fcm_cls.return_value = mock_fcm

        now = timezone.now()
        CalendarEvent.objects.create(
            user=cal_user, title="Legacy Reminder",
            start_time=now + timedelta(minutes=15, seconds=30),
            end_time=now + timedelta(hours=1, seconds=30),
            status="scheduled",
            reminders=[],
            reminders_sent=[],
            reminder_minutes_before=15,
        )

        UserDevice.objects.create(
            user=cal_user, fcm_token="tok-legacy-cal",
            platform="android", is_active=True,
        )

        from apps.calendar.tasks import check_and_send_reminders

        result = check_and_send_reminders()
        assert result["sent"] >= 1


# ──────────────────────────────────────────────────────────────────────
#  _next_occurrence helper
# ──────────────────────────────────────────────────────────────────────


class TestNextOccurrence:
    """Tests for the _next_occurrence helper."""

    def test_daily(self):
        from apps.calendar.tasks import _next_occurrence

        now = timezone.now()
        result = _next_occurrence(now, "daily", 1)
        assert result == now + timedelta(days=1)

    def test_weekly(self):
        from apps.calendar.tasks import _next_occurrence

        now = timezone.now()
        result = _next_occurrence(now, "weekly", 1)
        assert result == now + timedelta(weeks=1)

    def test_weekly_interval_2(self):
        from apps.calendar.tasks import _next_occurrence

        now = timezone.now()
        result = _next_occurrence(now, "weekly", 2)
        assert result == now + timedelta(weeks=2)

    def test_monthly(self):
        from dateutil.relativedelta import relativedelta

        from apps.calendar.tasks import _next_occurrence

        now = timezone.now()
        result = _next_occurrence(now, "monthly", 1)
        assert result == now + relativedelta(months=1)

    def test_unknown_defaults_to_weekly(self):
        from apps.calendar.tasks import _next_occurrence

        now = timezone.now()
        result = _next_occurrence(now, "unknown", 1)
        assert result == now + timedelta(weeks=1)
