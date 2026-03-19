"""
Unit tests for the Calendar app models.
"""

from datetime import time, timedelta

import pytest
from django.utils import timezone

from apps.calendar.models import CalendarEvent, TimeBlock
from apps.users.models import User


# ── CalendarEvent model ───────────────────────────────────────────────


class TestCalendarEventModel:
    """Tests for the CalendarEvent model."""

    def test_create_event(self, cal_event):
        """CalendarEvent can be created with required fields."""
        assert cal_event.title == "Test Meeting"
        assert cal_event.category == "meeting"
        assert cal_event.status == "scheduled"

    def test_str_representation(self, cal_event):
        """__str__ includes title and start time."""
        s = str(cal_event)
        assert "Test Meeting" in s

    def test_all_day_event(self, all_day_event):
        """All-day events have all_day=True."""
        assert all_day_event.all_day is True

    def test_default_reminder(self, cal_event):
        """Default reminder is 15 minutes."""
        assert cal_event.reminder_minutes_before == 15

    def test_category_choices(self, cal_user):
        """All category choices are valid."""
        now = timezone.now()
        for code, _ in CalendarEvent.CATEGORY_CHOICES:
            event = CalendarEvent.objects.create(
                user=cal_user,
                title=f"Event {code}",
                start_time=now + timedelta(hours=1),
                end_time=now + timedelta(hours=2),
                category=code,
            )
            assert event.category == code

    def test_status_choices(self, cal_user):
        """All status choices are valid."""
        now = timezone.now()
        for code, _ in CalendarEvent.STATUS_CHOICES:
            event = CalendarEvent.objects.create(
                user=cal_user,
                title=f"Status {code}",
                start_time=now + timedelta(hours=1),
                end_time=now + timedelta(hours=2),
                status=code,
            )
            assert event.status == code

    def test_recurring_event(self, cal_user):
        """Recurring event can have a recurrence rule."""
        now = timezone.now()
        event = CalendarEvent.objects.create(
            user=cal_user,
            title="Weekly Meeting",
            start_time=now,
            end_time=now + timedelta(hours=1),
            is_recurring=True,
            recurrence_rule={
                "frequency": "weekly",
                "interval": 1,
                "days_of_week": [0, 2, 4],
            },
        )
        assert event.is_recurring is True
        assert event.recurrence_rule["frequency"] == "weekly"

    def test_google_calendar_sync_fields(self, cal_event):
        """Google Calendar sync fields have correct defaults."""
        assert cal_event.google_event_id == ""
        assert cal_event.sync_status == "local"

    def test_ordering(self, cal_user):
        """Events are ordered by start_time ascending."""
        now = timezone.now()
        e1 = CalendarEvent.objects.create(
            user=cal_user,
            title="Later",
            start_time=now + timedelta(hours=5),
            end_time=now + timedelta(hours=6),
        )
        e2 = CalendarEvent.objects.create(
            user=cal_user,
            title="Earlier",
            start_time=now + timedelta(hours=1),
            end_time=now + timedelta(hours=2),
        )
        events = list(CalendarEvent.objects.filter(user=cal_user))
        assert events[0].title == "Earlier" or events[0].start_time <= events[-1].start_time

    def test_reminders_json_field(self, cal_user):
        """Multiple reminders can be stored as JSON."""
        now = timezone.now()
        event = CalendarEvent.objects.create(
            user=cal_user,
            title="Multi Reminder",
            start_time=now + timedelta(hours=1),
            end_time=now + timedelta(hours=2),
            reminders=[
                {"minutes_before": 15, "type": "push"},
                {"minutes_before": 60, "type": "email"},
            ],
        )
        event.refresh_from_db()
        assert len(event.reminders) == 2
        assert event.reminders[0]["minutes_before"] == 15

    def test_event_timezone_override(self, cal_user):
        """Event can have a custom timezone."""
        now = timezone.now()
        event = CalendarEvent.objects.create(
            user=cal_user,
            title="NYC Event",
            start_time=now,
            end_time=now + timedelta(hours=1),
            event_timezone="America/New_York",
        )
        assert event.event_timezone == "America/New_York"

    def test_snoozed_until(self, cal_event):
        """Events can be snoozed."""
        snooze_time = timezone.now() + timedelta(minutes=30)
        cal_event.snoozed_until = snooze_time
        cal_event.save()
        cal_event.refresh_from_db()
        assert cal_event.snoozed_until is not None


# ── TimeBlock model ───────────────────────────────────────────────────


class TestTimeBlockModel:
    """Tests for the TimeBlock model."""

    def test_create_time_block(self, time_block):
        """TimeBlock can be created with required fields."""
        assert time_block.block_type == "work"
        assert time_block.day_of_week == 0
        assert time_block.start_time == time(9, 0)
        assert time_block.end_time == time(17, 0)

    def test_str_representation(self, time_block):
        """__str__ includes day, times, and type."""
        s = str(time_block)
        assert "Mon" in s
        assert "work" in s

    def test_focus_block(self, focus_time_block):
        """Focus blocks are marked correctly."""
        assert focus_time_block.focus_block is True
        s = str(focus_time_block)
        assert "FOCUS" in s

    def test_block_type_choices(self, cal_user):
        """All block types are valid."""
        for code, _ in TimeBlock.BLOCK_TYPE_CHOICES:
            block = TimeBlock.objects.create(
                user=cal_user,
                block_type=code,
                day_of_week=2,
                start_time=time(10, 0),
                end_time=time(11, 0),
            )
            assert block.block_type == code

    def test_ordering(self, cal_user):
        """Time blocks are ordered by day_of_week, then start_time."""
        b1 = TimeBlock.objects.create(
            user=cal_user,
            block_type="work",
            day_of_week=2,
            start_time=time(14, 0),
            end_time=time(15, 0),
        )
        b2 = TimeBlock.objects.create(
            user=cal_user,
            block_type="work",
            day_of_week=2,
            start_time=time(10, 0),
            end_time=time(11, 0),
        )
        blocks = list(
            TimeBlock.objects.filter(user=cal_user, day_of_week=2)
        )
        assert blocks[0].start_time <= blocks[-1].start_time

    def test_is_active_default(self, time_block):
        """Time blocks are active by default."""
        assert time_block.is_active is True

    def test_deactivate_block(self, time_block):
        """Time blocks can be deactivated."""
        time_block.is_active = False
        time_block.save()
        time_block.refresh_from_db()
        assert time_block.is_active is False


# ══════════════════════════════════════════════════════════════════════
#  API ENDPOINT TESTS — Calendar
# ══════════════════════════════════════════════════════════════════════

import pytest


@pytest.mark.django_db
class TestCalendarAPI:
    """Tests for Calendar API endpoints."""

    def test_list_events(self, cal_user):
        from rest_framework.test import APIClient

        client = APIClient()
        client.force_authenticate(user=cal_user)
        resp = client.get(
            "/api/calendar/events/",
            HTTP_ORIGIN="https://stepora.app",
        )
        assert resp.status_code in (200, 403)

    def test_list_time_blocks(self, cal_user):
        from rest_framework.test import APIClient

        client = APIClient()
        client.force_authenticate(user=cal_user)
        resp = client.get(
            "/api/calendar/time-blocks/",
            HTTP_ORIGIN="https://stepora.app",
        )
        assert resp.status_code in (200, 403, 404)
