"""
Tests for apps/calendar/serializers.py

Covers: CalendarEventSerializer, CalendarEventCreateSerializer,
CalendarEventRescheduleSerializer, SuggestTimeSlotsSerializer,
TimeBlockSerializer, TimeBlockTemplateSerializer, HabitSerializer,
HabitCompletionSerializer, HabitCompleteSerializer, HabitUncompleteSerializer,
RecurrenceExceptionSerializer, SkipOccurrenceSerializer, ModifyOccurrenceSerializer,
CalendarShareCreateSerializer, CalendarShareSerializer, CalendarShareLinkSerializer,
TimeSuggestionSerializer, CalendarPreferencesSerializer, CheckConflictsSerializer,
BatchScheduleSerializer, SmartScheduleRequestSerializer, AcceptScheduleSerializer,
HeatmapDaySerializer, SaveCurrentTemplateSerializer.
"""

import uuid
from datetime import date, time, timedelta

import pytest
from django.test import RequestFactory
from django.utils import timezone
from rest_framework.request import Request

from apps.calendar.models import (
    CalendarEvent,
    CalendarShare,
    Habit,
    HabitCompletion,
    RecurrenceException,
    TimeBlock,
    TimeBlockTemplate,
)
from apps.calendar.serializers import (
    AcceptScheduleSerializer,
    BatchScheduleSerializer,
    CalendarEventCreateSerializer,
    CalendarEventRescheduleSerializer,
    CalendarEventSerializer,
    CalendarPreferencesSerializer,
    CalendarShareCreateSerializer,
    CalendarShareLinkSerializer,
    CalendarShareSerializer,
    CheckConflictsSerializer,
    HabitCompleteSerializer,
    HabitCompletionSerializer,
    HabitSerializer,
    HabitUncompleteSerializer,
    HeatmapDaySerializer,
    ModifyOccurrenceSerializer,
    RecurrenceExceptionSerializer,
    SaveCurrentTemplateSerializer,
    SkipOccurrenceSerializer,
    SmartScheduleRequestSerializer,
    SuggestTimeSlotsSerializer,
    TimeBlockSerializer,
    TimeBlockTemplateSerializer,
    TimeSuggestionSerializer,
)
from apps.users.models import User

# ── helpers ──────────────────────────────────────────────────────


def _drf_request(user=None):
    factory = RequestFactory()
    r = factory.get("/")
    if user:
        r.user = user
    return Request(r)


# ══════════════════════════════════════════════════════════════════
#  CalendarEventSerializer (read)
# ══════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestCalendarEventSerializer:

    def test_basic_serialization(self, cal_event):
        data = CalendarEventSerializer(cal_event).data
        assert data["title"] == "Test Meeting"
        assert data["category"] == "meeting"
        assert data["status"] == "scheduled"

    def test_is_multi_day_false(self, cal_event):
        data = CalendarEventSerializer(cal_event).data
        assert data["is_multi_day"] is False
        assert data["duration_days"] == 1

    def test_is_multi_day_true(self, cal_user):
        now = timezone.now()
        event = CalendarEvent.objects.create(
            user=cal_user,
            title="Multi Day",
            start_time=now,
            end_time=now + timedelta(days=2),
        )
        data = CalendarEventSerializer(event).data
        assert data["is_multi_day"] is True
        assert data["duration_days"] == 3

    def test_display_timezone_from_event(self, cal_user):
        event = CalendarEvent.objects.create(
            user=cal_user,
            title="TZ Event",
            start_time=timezone.now(),
            end_time=timezone.now() + timedelta(hours=1),
            event_timezone="America/New_York",
        )
        data = CalendarEventSerializer(event).data
        assert data["display_timezone"] == "America/New_York"

    def test_display_timezone_from_user(self, cal_event):
        """cal_user has timezone='Europe/Paris'."""
        data = CalendarEventSerializer(cal_event).data
        assert data["display_timezone"] == "Europe/Paris"

    def test_display_timezone_fallback_utc(self, db):
        user = User.objects.create_user(
            email="notz@example.com", password="pass", timezone=""
        )
        event = CalendarEvent.objects.create(
            user=user,
            title="No TZ",
            start_time=timezone.now(),
            end_time=timezone.now() + timedelta(hours=1),
        )
        data = CalendarEventSerializer(event).data
        assert data["display_timezone"] == "UTC"

    def test_recurrence_exceptions_empty_for_non_recurring(self, cal_event):
        data = CalendarEventSerializer(cal_event).data
        assert data["recurrence_exceptions"] == []

    def test_recurrence_exceptions_populated(self, cal_user):
        event = CalendarEvent.objects.create(
            user=cal_user,
            title="Recurring",
            start_time=timezone.now(),
            end_time=timezone.now() + timedelta(hours=1),
            is_recurring=True,
            recurrence_rule={"frequency": "daily", "interval": 1},
        )
        RecurrenceException.objects.create(
            parent_event=event,
            original_date=date.today(),
            skip_occurrence=True,
        )
        data = CalendarEventSerializer(event).data
        assert len(data["recurrence_exceptions"]) == 1
        assert data["recurrence_exceptions"][0]["skip_occurrence"] is True

    def test_task_title_null_when_no_task(self, cal_event):
        data = CalendarEventSerializer(cal_event).data
        assert data["task_title"] is None


# ══════════════════════════════════════════════════════════════════
#  CalendarEventCreateSerializer
# ══════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestCalendarEventCreateSerializer:

    def _base_data(self):
        now = timezone.now() + timedelta(hours=1)
        return {
            "title": "New Event",
            "start_time": now.isoformat(),
            "end_time": (now + timedelta(hours=1)).isoformat(),
        }

    def test_valid_basic(self):
        ser = CalendarEventCreateSerializer(data=self._base_data())
        assert ser.is_valid(), ser.errors

    def test_end_before_start(self):
        data = self._base_data()
        data["end_time"] = (timezone.now() - timedelta(hours=1)).isoformat()
        data["start_time"] = timezone.now().isoformat()
        # Swap so end < start
        data["start_time"], data["end_time"] = data["end_time"], data["start_time"]
        ser = CalendarEventCreateSerializer(data=data)
        # Actually make end_time < start_time explicitly
        now = timezone.now()
        ser2 = CalendarEventCreateSerializer(
            data={
                "title": "Bad",
                "start_time": (now + timedelta(hours=2)).isoformat(),
                "end_time": now.isoformat(),
            }
        )
        assert not ser2.is_valid()

    def test_sanitizes_title(self):
        data = self._base_data()
        data["title"] = "<script>alert('xss')</script>Meeting"
        ser = CalendarEventCreateSerializer(data=data)
        assert ser.is_valid(), ser.errors
        assert "<script>" not in ser.validated_data["title"]

    def test_sanitizes_description(self):
        data = self._base_data()
        data["description"] = "<b>Bold</b>"
        ser = CalendarEventCreateSerializer(data=data)
        assert ser.is_valid(), ser.errors
        assert "<b>" not in ser.validated_data["description"]

    def test_sanitizes_location(self):
        data = self._base_data()
        data["location"] = "<img onerror=x>Room 5"
        ser = CalendarEventCreateSerializer(data=data)
        assert ser.is_valid(), ser.errors
        assert "<img" not in ser.validated_data["location"]

    # ── Reminders validation ─────────────────────────────────────

    def test_valid_reminders(self):
        data = self._base_data()
        data["reminders"] = [
            {"minutes_before": 15, "type": "push"},
            {"minutes_before": 60, "type": "email"},
        ]
        ser = CalendarEventCreateSerializer(data=data)
        assert ser.is_valid(), ser.errors

    def test_reminders_empty_list(self):
        data = self._base_data()
        data["reminders"] = []
        ser = CalendarEventCreateSerializer(data=data)
        assert ser.is_valid(), ser.errors
        assert ser.validated_data["reminders"] == []

    def test_reminders_not_array(self):
        data = self._base_data()
        data["reminders"] = "not_array"
        ser = CalendarEventCreateSerializer(data=data)
        assert not ser.is_valid()

    def test_reminders_max_count(self):
        data = self._base_data()
        data["reminders"] = [{"minutes_before": i, "type": "push"} for i in range(11)]
        ser = CalendarEventCreateSerializer(data=data)
        assert not ser.is_valid()

    def test_reminder_missing_minutes(self):
        data = self._base_data()
        data["reminders"] = [{"type": "push"}]
        ser = CalendarEventCreateSerializer(data=data)
        assert not ser.is_valid()

    def test_reminder_invalid_type(self):
        data = self._base_data()
        data["reminders"] = [{"minutes_before": 10, "type": "sms"}]
        ser = CalendarEventCreateSerializer(data=data)
        assert not ser.is_valid()

    def test_reminder_negative_minutes(self):
        data = self._base_data()
        data["reminders"] = [{"minutes_before": -5, "type": "push"}]
        ser = CalendarEventCreateSerializer(data=data)
        assert not ser.is_valid()

    def test_reminder_item_not_dict(self):
        data = self._base_data()
        data["reminders"] = ["not_a_dict"]
        ser = CalendarEventCreateSerializer(data=data)
        assert not ser.is_valid()

    # ── Recurrence rule validation ───────────────────────────────

    def test_valid_recurrence_daily(self):
        data = self._base_data()
        data["is_recurring"] = True
        data["recurrence_rule"] = {"frequency": "daily", "interval": 1}
        ser = CalendarEventCreateSerializer(data=data)
        assert ser.is_valid(), ser.errors

    def test_valid_recurrence_weekly_with_days(self):
        data = self._base_data()
        data["is_recurring"] = True
        data["recurrence_rule"] = {
            "frequency": "weekly",
            "interval": 1,
            "days_of_week": [0, 2, 4],
        }
        ser = CalendarEventCreateSerializer(data=data)
        assert ser.is_valid(), ser.errors

    def test_valid_recurrence_monthly_with_day(self):
        data = self._base_data()
        data["is_recurring"] = True
        data["recurrence_rule"] = {
            "frequency": "monthly",
            "interval": 1,
            "day_of_month": 15,
        }
        ser = CalendarEventCreateSerializer(data=data)
        assert ser.is_valid(), ser.errors

    def test_valid_recurrence_with_end_date(self):
        data = self._base_data()
        data["is_recurring"] = True
        data["recurrence_rule"] = {
            "frequency": "daily",
            "end_date": "2026-12-31",
        }
        ser = CalendarEventCreateSerializer(data=data)
        assert ser.is_valid(), ser.errors

    def test_valid_recurrence_with_end_after_count(self):
        data = self._base_data()
        data["is_recurring"] = True
        data["recurrence_rule"] = {
            "frequency": "daily",
            "end_after_count": 10,
        }
        ser = CalendarEventCreateSerializer(data=data)
        assert ser.is_valid(), ser.errors

    def test_recurrence_missing_frequency(self):
        data = self._base_data()
        data["is_recurring"] = True
        data["recurrence_rule"] = {"interval": 1}
        ser = CalendarEventCreateSerializer(data=data)
        assert not ser.is_valid()

    def test_recurrence_invalid_frequency(self):
        data = self._base_data()
        data["is_recurring"] = True
        data["recurrence_rule"] = {"frequency": "hourly"}
        ser = CalendarEventCreateSerializer(data=data)
        assert not ser.is_valid()

    def test_recurrence_invalid_interval(self):
        data = self._base_data()
        data["is_recurring"] = True
        data["recurrence_rule"] = {"frequency": "daily", "interval": 0}
        ser = CalendarEventCreateSerializer(data=data)
        assert not ser.is_valid()

    def test_recurrence_invalid_days_of_week(self):
        data = self._base_data()
        data["is_recurring"] = True
        data["recurrence_rule"] = {"frequency": "weekly", "days_of_week": [7]}
        ser = CalendarEventCreateSerializer(data=data)
        assert not ser.is_valid()

    def test_recurrence_days_of_week_not_list(self):
        data = self._base_data()
        data["is_recurring"] = True
        data["recurrence_rule"] = {"frequency": "weekly", "days_of_week": "MWF"}
        ser = CalendarEventCreateSerializer(data=data)
        assert not ser.is_valid()

    def test_recurrence_invalid_day_of_month(self):
        data = self._base_data()
        data["is_recurring"] = True
        data["recurrence_rule"] = {"frequency": "monthly", "day_of_month": 32}
        ser = CalendarEventCreateSerializer(data=data)
        assert not ser.is_valid()

    def test_recurrence_week_of_month_missing_day(self):
        data = self._base_data()
        data["is_recurring"] = True
        data["recurrence_rule"] = {"frequency": "monthly", "week_of_month": 2}
        ser = CalendarEventCreateSerializer(data=data)
        assert not ser.is_valid()

    def test_recurrence_week_of_month_invalid(self):
        data = self._base_data()
        data["is_recurring"] = True
        data["recurrence_rule"] = {
            "frequency": "monthly",
            "week_of_month": 6,
            "day_of_week": 0,
        }
        ser = CalendarEventCreateSerializer(data=data)
        assert not ser.is_valid()

    def test_recurrence_invalid_end_date(self):
        data = self._base_data()
        data["is_recurring"] = True
        data["recurrence_rule"] = {"frequency": "daily", "end_date": "not-a-date"}
        ser = CalendarEventCreateSerializer(data=data)
        assert not ser.is_valid()

    def test_recurrence_invalid_end_after_count(self):
        data = self._base_data()
        data["is_recurring"] = True
        data["recurrence_rule"] = {"frequency": "daily", "end_after_count": 0}
        ser = CalendarEventCreateSerializer(data=data)
        assert not ser.is_valid()

    def test_recurrence_weekdays_only_not_bool(self):
        data = self._base_data()
        data["is_recurring"] = True
        data["recurrence_rule"] = {"frequency": "daily", "weekdays_only": "yes"}
        ser = CalendarEventCreateSerializer(data=data)
        assert not ser.is_valid()

    def test_recurrence_rule_not_dict(self):
        data = self._base_data()
        data["is_recurring"] = True
        data["recurrence_rule"] = "daily"
        ser = CalendarEventCreateSerializer(data=data)
        assert not ser.is_valid()

    def test_recurring_without_rule(self):
        data = self._base_data()
        data["is_recurring"] = True
        ser = CalendarEventCreateSerializer(data=data)
        assert not ser.is_valid()

    def test_force_flag(self):
        data = self._base_data()
        data["force"] = True
        ser = CalendarEventCreateSerializer(data=data)
        assert ser.is_valid(), ser.errors
        assert ser.validated_data["force"] is True


# ══════════════════════════════════════════════════════════════════
#  CalendarEventRescheduleSerializer
# ══════════════════════════════════════════════════════════════════


class TestCalendarEventRescheduleSerializer:

    def test_valid(self):
        now = timezone.now()
        ser = CalendarEventRescheduleSerializer(
            data={
                "start_time": now.isoformat(),
                "end_time": (now + timedelta(hours=1)).isoformat(),
            }
        )
        assert ser.is_valid(), ser.errors

    def test_end_before_start(self):
        now = timezone.now()
        ser = CalendarEventRescheduleSerializer(
            data={
                "start_time": (now + timedelta(hours=2)).isoformat(),
                "end_time": now.isoformat(),
            }
        )
        assert not ser.is_valid()


# ══════════════════════════════════════════════════════════════════
#  SuggestTimeSlotsSerializer
# ══════════════════════════════════════════════════════════════════


class TestSuggestTimeSlotsSerializer:

    def test_valid(self):
        ser = SuggestTimeSlotsSerializer(
            data={
                "date": "2026-04-01",
                "duration_mins": 30,
            }
        )
        assert ser.is_valid(), ser.errors

    def test_duration_too_small(self):
        ser = SuggestTimeSlotsSerializer(
            data={
                "date": "2026-04-01",
                "duration_mins": 2,
            }
        )
        assert not ser.is_valid()

    def test_duration_too_large(self):
        ser = SuggestTimeSlotsSerializer(
            data={
                "date": "2026-04-01",
                "duration_mins": 999,
            }
        )
        assert not ser.is_valid()


# ══════════════════════════════════════════════════════════════════
#  TimeBlockSerializer
# ══════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestTimeBlockSerializer:

    def test_serialization(self, time_block):
        data = TimeBlockSerializer(time_block).data
        assert data["block_type"] == "work"
        assert data["day_name"] == "Monday"
        assert data["day_of_week"] == 0

    def test_valid_creation_data(self):
        ser = TimeBlockSerializer(
            data={
                "block_type": "personal",
                "day_of_week": 3,
                "start_time": "09:00",
                "end_time": "12:00",
            }
        )
        assert ser.is_valid(), ser.errors

    def test_end_before_start(self):
        ser = TimeBlockSerializer(
            data={
                "block_type": "work",
                "day_of_week": 0,
                "start_time": "17:00",
                "end_time": "09:00",
            }
        )
        assert not ser.is_valid()

    def test_invalid_day_of_week(self):
        ser = TimeBlockSerializer(
            data={
                "block_type": "work",
                "day_of_week": 7,
                "start_time": "09:00",
                "end_time": "17:00",
            }
        )
        assert not ser.is_valid()

    def test_day_name_all_days(self, cal_user):
        expected = [
            "Monday",
            "Tuesday",
            "Wednesday",
            "Thursday",
            "Friday",
            "Saturday",
            "Sunday",
        ]
        for i, name in enumerate(expected):
            tb = TimeBlock.objects.create(
                user=cal_user,
                block_type="work",
                day_of_week=i,
                start_time=time(9, 0),
                end_time=time(17, 0),
            )
            data = TimeBlockSerializer(tb).data
            assert data["day_name"] == name


# ══════════════════════════════════════════════════════════════════
#  TimeBlockTemplateSerializer
# ══════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestTimeBlockTemplateSerializer:

    def test_valid(self):
        ser = TimeBlockTemplateSerializer(
            data={
                "name": "Work Week",
                "description": "Standard work week",
                "blocks": [
                    {
                        "block_type": "work",
                        "day_of_week": 0,
                        "start_time": "09:00",
                        "end_time": "17:00",
                    }
                ],
            }
        )
        assert ser.is_valid(), ser.errors

    def test_empty_blocks(self):
        ser = TimeBlockTemplateSerializer(
            data={
                "name": "Empty",
                "blocks": [],
            }
        )
        assert not ser.is_valid()

    def test_blocks_not_array(self):
        ser = TimeBlockTemplateSerializer(
            data={
                "name": "Bad",
                "blocks": "not_array",
            }
        )
        assert not ser.is_valid()

    def test_block_missing_field(self):
        ser = TimeBlockTemplateSerializer(
            data={
                "name": "Missing",
                "blocks": [{"block_type": "work"}],  # missing day_of_week etc.
            }
        )
        assert not ser.is_valid()

    def test_block_invalid_type(self):
        ser = TimeBlockTemplateSerializer(
            data={
                "name": "Bad Type",
                "blocks": [
                    {
                        "block_type": "gaming",
                        "day_of_week": 0,
                        "start_time": "09:00",
                        "end_time": "17:00",
                    }
                ],
            }
        )
        assert not ser.is_valid()

    def test_block_invalid_day(self):
        ser = TimeBlockTemplateSerializer(
            data={
                "name": "Bad Day",
                "blocks": [
                    {
                        "block_type": "work",
                        "day_of_week": 8,
                        "start_time": "09:00",
                        "end_time": "17:00",
                    }
                ],
            }
        )
        assert not ser.is_valid()

    def test_block_count(self, cal_user):
        tmpl = TimeBlockTemplate.objects.create(
            user=cal_user,
            name="Test",
            blocks=[
                {
                    "block_type": "work",
                    "day_of_week": 0,
                    "start_time": "09:00",
                    "end_time": "17:00",
                },
                {
                    "block_type": "personal",
                    "day_of_week": 1,
                    "start_time": "18:00",
                    "end_time": "20:00",
                },
            ],
        )
        data = TimeBlockTemplateSerializer(tmpl).data
        assert data["block_count"] == 2

    def test_block_count_non_list(self, cal_user):
        tmpl = TimeBlockTemplate.objects.create(
            user=cal_user,
            name="Non-list",
            blocks={},
        )
        data = TimeBlockTemplateSerializer(tmpl).data
        assert data["block_count"] == 0

    def test_sanitizes_name(self):
        ser = TimeBlockTemplateSerializer(
            data={
                "name": "<script>x</script>My Template",
                "blocks": [
                    {
                        "block_type": "work",
                        "day_of_week": 0,
                        "start_time": "09:00",
                        "end_time": "17:00",
                    },
                ],
            }
        )
        assert ser.is_valid(), ser.errors
        assert "<script>" not in ser.validated_data["name"]

    def test_block_item_not_dict(self):
        ser = TimeBlockTemplateSerializer(
            data={
                "name": "Bad",
                "blocks": ["not_a_dict"],
            }
        )
        assert not ser.is_valid()


# ══════════════════════════════════════════════════════════════════
#  HabitSerializer
# ══════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestHabitSerializer:

    def test_valid(self):
        ser = HabitSerializer(
            data={
                "name": "Meditate",
                "frequency": "daily",
                "target_per_day": 1,
                "color": "#8B5CF6",
                "icon": "brain",
                "custom_days": [],
            }
        )
        assert ser.is_valid(), ser.errors

    def test_completions_today(self, cal_user):
        habit = Habit.objects.create(
            user=cal_user,
            name="Read",
            frequency="daily",
            target_per_day=1,
        )
        HabitCompletion.objects.create(
            habit=habit,
            date=timezone.now().date(),
            count=2,
        )
        data = HabitSerializer(habit).data
        assert data["completions_today"] == 2

    def test_completions_today_zero(self, cal_user):
        habit = Habit.objects.create(
            user=cal_user,
            name="Run",
            frequency="daily",
        )
        data = HabitSerializer(habit).data
        assert data["completions_today"] == 0

    def test_invalid_color(self):
        ser = HabitSerializer(
            data={
                "name": "Bad Color",
                "frequency": "daily",
                "color": "red",
                "custom_days": [],
                "target_per_day": 1,
            }
        )
        assert not ser.is_valid()
        assert "color" in ser.errors

    def test_valid_color(self):
        ser = HabitSerializer(
            data={
                "name": "Good Color",
                "frequency": "daily",
                "color": "#FF00AA",
                "custom_days": [],
                "target_per_day": 1,
            }
        )
        assert ser.is_valid(), ser.errors

    def test_invalid_custom_days(self):
        ser = HabitSerializer(
            data={
                "name": "Bad Days",
                "frequency": "custom",
                "custom_days": [7],
                "target_per_day": 1,
            }
        )
        assert not ser.is_valid()

    def test_custom_days_not_list(self):
        ser = HabitSerializer(
            data={
                "name": "Bad Days",
                "frequency": "custom",
                "custom_days": "MWF",
                "target_per_day": 1,
            }
        )
        assert not ser.is_valid()

    def test_target_per_day_too_low(self):
        ser = HabitSerializer(
            data={
                "name": "Low",
                "frequency": "daily",
                "custom_days": [],
                "target_per_day": 0,
            }
        )
        assert not ser.is_valid()

    def test_target_per_day_too_high(self):
        ser = HabitSerializer(
            data={
                "name": "High",
                "frequency": "daily",
                "custom_days": [],
                "target_per_day": 101,
            }
        )
        assert not ser.is_valid()

    def test_sanitizes_name(self):
        ser = HabitSerializer(
            data={
                "name": "<b>Bold Habit</b>",
                "frequency": "daily",
                "custom_days": [],
                "target_per_day": 1,
            }
        )
        assert ser.is_valid(), ser.errors
        assert "<b>" not in ser.validated_data["name"]


# ══════════════════════════════════════════════════════════════════
#  HabitCompletionSerializer
# ══════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestHabitCompletionSerializer:

    def test_serialization(self, cal_user):
        habit = Habit.objects.create(
            user=cal_user,
            name="Walk",
            frequency="daily",
            color="#00FF00",
            icon="footprints",
        )
        completion = HabitCompletion.objects.create(
            habit=habit,
            date=timezone.now().date(),
            count=1,
            note="Nice walk",
        )
        data = HabitCompletionSerializer(completion).data
        assert data["habit_name"] == "Walk"
        assert data["habit_color"] == "#00FF00"
        assert data["habit_icon"] == "footprints"
        assert data["count"] == 1


# ══════════════════════════════════════════════════════════════════
#  HabitCompleteSerializer / HabitUncompleteSerializer
# ══════════════════════════════════════════════════════════════════


class TestHabitCompleteSerializer:

    def test_valid(self):
        ser = HabitCompleteSerializer(data={"date": "2026-04-01", "note": "Done!"})
        assert ser.is_valid(), ser.errors

    def test_without_note(self):
        ser = HabitCompleteSerializer(data={"date": "2026-04-01"})
        assert ser.is_valid(), ser.errors

    def test_sanitizes_note(self):
        ser = HabitCompleteSerializer(
            data={
                "date": "2026-04-01",
                "note": "<script>bad</script>Good",
            }
        )
        assert ser.is_valid()
        assert "<script>" not in ser.validated_data["note"]

    def test_missing_date(self):
        ser = HabitCompleteSerializer(data={})
        assert not ser.is_valid()


class TestHabitUncompleteSerializer:

    def test_valid(self):
        ser = HabitUncompleteSerializer(data={"date": "2026-04-01"})
        assert ser.is_valid(), ser.errors


# ══════════════════════════════════════════════════════════════════
#  RecurrenceExceptionSerializer
# ══════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestRecurrenceExceptionSerializer:

    def test_serialization(self, cal_user):
        event = CalendarEvent.objects.create(
            user=cal_user,
            title="Weekly",
            start_time=timezone.now(),
            end_time=timezone.now() + timedelta(hours=1),
            is_recurring=True,
            recurrence_rule={"frequency": "weekly"},
        )
        exc = RecurrenceException.objects.create(
            parent_event=event,
            original_date=date.today(),
            skip_occurrence=True,
        )
        data = RecurrenceExceptionSerializer(exc).data
        assert data["skip_occurrence"] is True
        assert data["original_date"] == str(date.today())


# ══════════════════════════════════════════════════════════════════
#  SkipOccurrenceSerializer / ModifyOccurrenceSerializer
# ══════════════════════════════════════════════════════════════════


class TestSkipOccurrenceSerializer:

    def test_valid(self):
        ser = SkipOccurrenceSerializer(data={"original_date": "2026-04-01"})
        assert ser.is_valid(), ser.errors


class TestModifyOccurrenceSerializer:

    def test_valid_basic(self):
        ser = ModifyOccurrenceSerializer(data={"original_date": "2026-04-01"})
        assert ser.is_valid(), ser.errors

    def test_with_modified_times(self):
        now = timezone.now()
        ser = ModifyOccurrenceSerializer(
            data={
                "original_date": "2026-04-01",
                "title": "Modified",
                "start_time": now.isoformat(),
                "end_time": (now + timedelta(hours=1)).isoformat(),
            }
        )
        assert ser.is_valid(), ser.errors

    def test_end_before_start(self):
        now = timezone.now()
        ser = ModifyOccurrenceSerializer(
            data={
                "original_date": "2026-04-01",
                "start_time": (now + timedelta(hours=2)).isoformat(),
                "end_time": now.isoformat(),
            }
        )
        assert not ser.is_valid()

    def test_sanitizes_title(self):
        ser = ModifyOccurrenceSerializer(
            data={
                "original_date": "2026-04-01",
                "title": "<img src=x>Title",
            }
        )
        assert ser.is_valid()
        assert "<img" not in ser.validated_data["title"]


# ══════════════════════════════════════════════════════════════════
#  CalendarShareCreateSerializer / CalendarShareSerializer
# ══════════════════════════════════════════════════════════════════


class TestCalendarShareCreateSerializer:

    def test_valid_view(self):
        ser = CalendarShareCreateSerializer(
            data={
                "user_id": str(uuid.uuid4()),
                "permission": "view",
            }
        )
        assert ser.is_valid(), ser.errors

    def test_valid_suggest(self):
        ser = CalendarShareCreateSerializer(
            data={
                "user_id": str(uuid.uuid4()),
                "permission": "suggest",
            }
        )
        assert ser.is_valid()

    def test_invalid_permission(self):
        ser = CalendarShareCreateSerializer(
            data={
                "user_id": str(uuid.uuid4()),
                "permission": "admin",
            }
        )
        assert not ser.is_valid()


@pytest.mark.django_db
class TestCalendarShareSerializer:

    def test_serialization(self, cal_user):
        user2 = User.objects.create_user(
            email="buddy@example.com", password="pass", display_name="Buddy"
        )
        share = CalendarShare.objects.create(
            owner=cal_user,
            shared_with=user2,
            permission="view",
        )
        data = CalendarShareSerializer(share).data
        assert data["owner_name"] == "Calendar User"
        assert data["shared_with_name"] == "Buddy"
        assert data["permission"] == "view"


class TestCalendarShareLinkSerializer:

    def test_valid(self):
        ser = CalendarShareLinkSerializer(data={"permission": "view"})
        assert ser.is_valid(), ser.errors

    def test_invalid_permission(self):
        ser = CalendarShareLinkSerializer(data={"permission": "edit"})
        assert not ser.is_valid()


# ══════════════════════════════════════════════════════════════════
#  TimeSuggestionSerializer
# ══════════════════════════════════════════════════════════════════


class TestTimeSuggestionSerializer:

    def test_valid(self):
        now = timezone.now()
        ser = TimeSuggestionSerializer(
            data={
                "suggested_start": now.isoformat(),
                "suggested_end": (now + timedelta(hours=1)).isoformat(),
            }
        )
        assert ser.is_valid(), ser.errors

    def test_end_before_start(self):
        now = timezone.now()
        ser = TimeSuggestionSerializer(
            data={
                "suggested_start": (now + timedelta(hours=2)).isoformat(),
                "suggested_end": now.isoformat(),
            }
        )
        assert not ser.is_valid()

    def test_sanitizes_note(self):
        now = timezone.now()
        ser = TimeSuggestionSerializer(
            data={
                "suggested_start": now.isoformat(),
                "suggested_end": (now + timedelta(hours=1)).isoformat(),
                "note": "<b>Check this</b>",
            }
        )
        assert ser.is_valid()
        assert "<b>" not in ser.validated_data["note"]


# ══════════════════════════════════════════════════════════════════
#  CalendarPreferencesSerializer
# ══════════════════════════════════════════════════════════════════


class TestCalendarPreferencesSerializer:

    def test_valid(self):
        ser = CalendarPreferencesSerializer(
            data={
                "buffer_minutes": 15,
                "min_event_duration": 30,
            }
        )
        assert ser.is_valid(), ser.errors

    def test_defaults(self):
        ser = CalendarPreferencesSerializer(data={})
        assert ser.is_valid()
        assert ser.validated_data["buffer_minutes"] == 15
        assert ser.validated_data["min_event_duration"] == 30

    def test_buffer_too_high(self):
        ser = CalendarPreferencesSerializer(data={"buffer_minutes": 61})
        assert not ser.is_valid()


# ══════════════════════════════════════════════════════════════════
#  CheckConflictsSerializer
# ══════════════════════════════════════════════════════════════════


class TestCheckConflictsSerializer:

    def test_valid(self):
        now = timezone.now()
        ser = CheckConflictsSerializer(
            data={
                "start_time": now.isoformat(),
                "end_time": (now + timedelta(hours=1)).isoformat(),
            }
        )
        assert ser.is_valid(), ser.errors

    def test_end_before_start(self):
        now = timezone.now()
        ser = CheckConflictsSerializer(
            data={
                "start_time": (now + timedelta(hours=2)).isoformat(),
                "end_time": now.isoformat(),
            }
        )
        assert not ser.is_valid()

    def test_with_exclude_event(self):
        now = timezone.now()
        ser = CheckConflictsSerializer(
            data={
                "start_time": now.isoformat(),
                "end_time": (now + timedelta(hours=1)).isoformat(),
                "exclude_event_id": str(uuid.uuid4()),
            }
        )
        assert ser.is_valid()


# ══════════════════════════════════════════════════════════════════
#  SmartScheduleRequestSerializer / AcceptScheduleSerializer
# ══════════════════════════════════════════════════════════════════


class TestSmartScheduleRequestSerializer:

    def test_valid(self):
        ser = SmartScheduleRequestSerializer(
            data={
                "task_ids": [str(uuid.uuid4())],
            }
        )
        assert ser.is_valid(), ser.errors

    def test_empty_list(self):
        ser = SmartScheduleRequestSerializer(data={"task_ids": []})
        assert not ser.is_valid()

    def test_too_many(self):
        ser = SmartScheduleRequestSerializer(
            data={
                "task_ids": [str(uuid.uuid4()) for _ in range(21)],
            }
        )
        assert not ser.is_valid()


class TestAcceptScheduleSerializer:

    def test_valid(self):
        ser = AcceptScheduleSerializer(
            data={
                "suggestions": [
                    {
                        "task_id": str(uuid.uuid4()),
                        "suggested_date": "2026-04-01",
                        "suggested_time": "10:00",
                    }
                ],
            }
        )
        assert ser.is_valid(), ser.errors

    def test_empty(self):
        ser = AcceptScheduleSerializer(data={"suggestions": []})
        assert not ser.is_valid()


# ══════════════════════════════════════════════════════════════════
#  BatchScheduleSerializer
# ══════════════════════════════════════════════════════════════════


class TestBatchScheduleSerializer:

    def test_valid(self):
        ser = BatchScheduleSerializer(
            data={
                "tasks": [
                    {
                        "task_id": str(uuid.uuid4()),
                        "date": "2026-04-01",
                        "time": "09:00",
                    },
                ],
                "create_events": True,
            }
        )
        assert ser.is_valid(), ser.errors

    def test_empty_tasks(self):
        ser = BatchScheduleSerializer(data={"tasks": []})
        assert not ser.is_valid()


# ══════════════════════════════════════════════════════════════════
#  SaveCurrentTemplateSerializer
# ══════════════════════════════════════════════════════════════════


class TestSaveCurrentTemplateSerializer:

    def test_valid(self):
        ser = SaveCurrentTemplateSerializer(
            data={
                "name": "My Template",
                "description": "A nice template",
            }
        )
        assert ser.is_valid(), ser.errors

    def test_sanitizes_name(self):
        ser = SaveCurrentTemplateSerializer(
            data={
                "name": "<script>x</script>Template",
            }
        )
        assert ser.is_valid()
        assert "<script>" not in ser.validated_data["name"]

    def test_missing_name(self):
        ser = SaveCurrentTemplateSerializer(data={})
        assert not ser.is_valid()


# ══════════════════════════════════════════════════════════════════
#  HeatmapDaySerializer (read-only, just check it accepts data)
# ══════════════════════════════════════════════════════════════════


class TestHeatmapDaySerializer:

    def test_valid(self):
        ser = HeatmapDaySerializer(
            data={
                "date": "2026-04-01",
                "tasks_completed": 5,
                "tasks_total": 8,
                "events_count": 3,
                "focus_minutes": 120,
                "productivity_score": 0.75,
            }
        )
        assert ser.is_valid(), ser.errors
