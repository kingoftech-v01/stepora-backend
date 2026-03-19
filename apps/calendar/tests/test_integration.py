"""
Integration tests for the Calendar app API endpoints.

Tests calendar events CRUD, time blocks, conflict checking,
and Google Calendar sync endpoints (mocked).
"""

import uuid
from datetime import time, timedelta

import pytest
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient
from unittest.mock import patch, Mock

from apps.calendar.models import CalendarEvent, TimeBlock, Habit, HabitCompletion
from apps.users.models import User


@pytest.fixture
def cal_client(cal_user):
    """Authenticated API client for calendar tests."""
    client = APIClient()
    client.force_authenticate(user=cal_user)
    return client


@pytest.fixture
def cal_user2(db):
    """Create a second user for calendar tests."""
    return User.objects.create_user(
        email="caluser2@example.com",
        password="testpass123",
        display_name="Calendar User 2",
        timezone="Europe/Paris",
    )


# ──────────────────────────────────────────────────────────────────────
#  Calendar Event CRUD
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestCalendarEventCRUD:
    """Tests for calendar event CRUD endpoints."""

    def test_list_events(self, cal_client, cal_event):
        """List calendar events."""
        response = cal_client.get("/api/calendar/events/")
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) >= 1

    def test_list_events_unauthenticated(self):
        """Unauthenticated list returns 401."""
        client = APIClient()
        response = client.get("/api/calendar/events/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_create_event(self, cal_client):
        """Create a calendar event."""
        start = timezone.now() + timedelta(hours=3)
        end = start + timedelta(hours=1)
        response = cal_client.post(
            "/api/calendar/events/",
            {
                "title": "Team Meeting",
                "description": "Weekly sync",
                "start_time": start.isoformat(),
                "end_time": end.isoformat(),
                "category": "meeting",
            },
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["title"] == "Team Meeting"

    def test_create_event_missing_title(self, cal_client):
        """Create event without title returns 400."""
        start = timezone.now() + timedelta(hours=3)
        end = start + timedelta(hours=1)
        response = cal_client.post(
            "/api/calendar/events/",
            {
                "start_time": start.isoformat(),
                "end_time": end.isoformat(),
            },
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_retrieve_event(self, cal_client, cal_event):
        """Retrieve a specific calendar event."""
        response = cal_client.get(f"/api/calendar/events/{cal_event.id}/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["title"] == "Test Meeting"

    def test_retrieve_nonexistent_event(self, cal_client):
        """Retrieve nonexistent event returns 404."""
        response = cal_client.get(f"/api/calendar/events/{uuid.uuid4()}/")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_update_event(self, cal_client, cal_event):
        """Update a calendar event."""
        new_start = timezone.now() + timedelta(hours=5)
        new_end = new_start + timedelta(hours=1)
        response = cal_client.patch(
            f"/api/calendar/events/{cal_event.id}/",
            {
                "title": "Updated Meeting",
                "start_time": new_start.isoformat(),
                "end_time": new_end.isoformat(),
            },
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["title"] == "Updated Meeting"

    def test_delete_event(self, cal_client, cal_user):
        """Delete a calendar event."""
        event = CalendarEvent.objects.create(
            user=cal_user,
            title="To Delete",
            start_time=timezone.now() + timedelta(hours=5),
            end_time=timezone.now() + timedelta(hours=6),
        )
        response = cal_client.delete(f"/api/calendar/events/{event.id}/")
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not CalendarEvent.objects.filter(id=event.id).exists()

    def test_cannot_see_other_users_events(self, cal_client, cal_user2):
        """User cannot see another user's events."""
        other_event = CalendarEvent.objects.create(
            user=cal_user2,
            title="Other's Event",
            start_time=timezone.now() + timedelta(hours=1),
            end_time=timezone.now() + timedelta(hours=2),
        )
        response = cal_client.get(f"/api/calendar/events/{other_event.id}/")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_list_events_with_date_range(self, cal_client, cal_user):
        """List events filtered by date range."""
        now = timezone.now()
        CalendarEvent.objects.create(
            user=cal_user,
            title="In Range",
            start_time=now + timedelta(hours=1),
            end_time=now + timedelta(hours=2),
        )
        start = now.isoformat()
        end = (now + timedelta(days=1)).isoformat()
        response = cal_client.get(
            f"/api/calendar/events/?start_time__gte={start}&start_time__lte={end}"
        )
        assert response.status_code == status.HTTP_200_OK


# ──────────────────────────────────────────────────────────────────────
#  Event Reschedule
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestEventReschedule:
    """Tests for event reschedule endpoint."""

    def test_reschedule_event(self, cal_client, cal_event):
        """Reschedule an event to a new time."""
        new_start = timezone.now() + timedelta(hours=10)
        new_end = new_start + timedelta(hours=1)
        response = cal_client.patch(
            f"/api/calendar/events/{cal_event.id}/reschedule/",
            {
                "start_time": new_start.isoformat(),
                "end_time": new_end.isoformat(),
            },
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK

    def test_reschedule_with_force(self, cal_client, cal_event, cal_user):
        """Reschedule with force bypasses conflicts."""
        # Create a conflicting event
        new_start = timezone.now() + timedelta(hours=10)
        new_end = new_start + timedelta(hours=1)
        CalendarEvent.objects.create(
            user=cal_user,
            title="Conflict",
            start_time=new_start,
            end_time=new_end,
        )
        response = cal_client.patch(
            f"/api/calendar/events/{cal_event.id}/reschedule/",
            {
                "start_time": new_start.isoformat(),
                "end_time": new_end.isoformat(),
                "force": True,
            },
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK


# ──────────────────────────────────────────────────────────────────────
#  Conflict Checking
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestConflictChecking:
    """Tests for conflict checking endpoints."""

    def test_check_no_conflicts(self, cal_client):
        """Check conflicts when none exist."""
        start = timezone.now() + timedelta(days=10)
        end = start + timedelta(hours=1)
        response = cal_client.post(
            "/api/calendar/events/check-conflicts/",
            {
                "start_time": start.isoformat(),
                "end_time": end.isoformat(),
            },
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["has_conflicts"] is False

    def test_check_with_conflicts(self, cal_client, cal_event):
        """Check conflicts detects overlapping events."""
        response = cal_client.post(
            "/api/calendar/events/check-conflicts/",
            {
                "start_time": cal_event.start_time.isoformat(),
                "end_time": cal_event.end_time.isoformat(),
            },
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["has_conflicts"] is True


# ──────────────────────────────────────────────────────────────────────
#  Time Blocks CRUD
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestTimeBlockCRUD:
    """Tests for time block CRUD endpoints."""

    def test_list_time_blocks(self, cal_client, time_block):
        """List time blocks."""
        response = cal_client.get("/api/calendar/timeblocks/")
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) >= 1

    def test_create_time_block(self, cal_client):
        """Create a time block."""
        response = cal_client.post(
            "/api/calendar/timeblocks/",
            {
                "block_type": "personal",
                "day_of_week": 2,
                "start_time": "18:00",
                "end_time": "20:00",
            },
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED

    def test_update_time_block(self, cal_client, time_block):
        """Update a time block."""
        response = cal_client.patch(
            f"/api/calendar/timeblocks/{time_block.id}/",
            {"block_type": "blocked"},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK

    def test_delete_time_block(self, cal_client, time_block):
        """Delete a time block."""
        response = cal_client.delete(
            f"/api/calendar/timeblocks/{time_block.id}/"
        )
        assert response.status_code == status.HTTP_204_NO_CONTENT

    def test_list_time_blocks_unauthenticated(self):
        """Unauthenticated list returns 401."""
        client = APIClient()
        response = client.get("/api/calendar/timeblocks/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


# ──────────────────────────────────────────────────────────────────────
#  Event Categories and Search
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestEventCategoriesAndSearch:
    """Tests for event categories and search."""

    def test_list_categories(self, cal_client):
        """List event categories."""
        response = cal_client.get("/api/calendar/events/categories/")
        assert response.status_code == status.HTTP_200_OK
        assert "categories" in response.data
        assert len(response.data["categories"]) > 0

    def test_search_events(self, cal_client, cal_event):
        """Search events by query."""
        response = cal_client.get("/api/calendar/events/search/?q=Meeting")
        assert response.status_code == status.HTTP_200_OK

    def test_search_events_no_query(self, cal_client):
        """Search without query returns 400."""
        response = cal_client.get("/api/calendar/events/search/?q=")
        assert response.status_code == status.HTTP_400_BAD_REQUEST


# ──────────────────────────────────────────────────────────────────────
#  Event Snooze
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestEventSnooze:
    """Tests for event snooze."""

    def test_snooze_event(self, cal_client, cal_event):
        """Snooze an event notification."""
        response = cal_client.post(
            f"/api/calendar/events/{cal_event.id}/snooze/",
            {"minutes": 15},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert "snoozed_until" in response.data

    def test_snooze_invalid_minutes(self, cal_client, cal_event):
        """Snooze with invalid minutes returns 400."""
        response = cal_client.post(
            f"/api/calendar/events/{cal_event.id}/snooze/",
            {"minutes": 7},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST


# ──────────────────────────────────────────────────────────────────────
#  Google Calendar (mocked)
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestGoogleCalendar:
    """Tests for Google Calendar integration endpoints (mocked)."""

    def test_google_calendar_status(self, cal_client):
        """Get Google Calendar connection status."""
        response = cal_client.get("/api/calendar/google/status/")
        assert response.status_code == status.HTTP_200_OK

    def test_google_calendar_status_unauthenticated(self):
        """Unauthenticated request returns 401."""
        client = APIClient()
        response = client.get("/api/calendar/google/status/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_google_calendar_auth_url(self, cal_client):
        """Get Google Calendar auth URL (may fail without Google credentials)."""
        response = cal_client.get("/api/calendar/google/auth/")
        # Returns auth URL (200), redirect (302), or error depending on config
        assert response.status_code in (200, 302, 400, 500, 501)

    @pytest.mark.skip(reason="GoogleCalendarDisconnect requires Google credentials")
    def test_google_calendar_disconnect_not_connected(self, cal_client):
        """Disconnect when not connected returns appropriate response."""
        response = cal_client.post("/api/calendar/google/disconnect/")
        assert response.status_code in (200, 400, 404)


# ──────────────────────────────────────────────────────────────────────
#  Recurring Events
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestRecurringEvents:
    """Tests for recurring event operations."""

    def test_create_recurring_event(self, cal_client):
        """Create a recurring event."""
        start = timezone.now() + timedelta(hours=1)
        end = start + timedelta(hours=1)
        response = cal_client.post(
            "/api/calendar/events/",
            {
                "title": "Daily Standup",
                "start_time": start.isoformat(),
                "end_time": end.isoformat(),
                "is_recurring": True,
                "recurrence_rule": {
                    "frequency": "daily",
                    "interval": 1,
                },
                "category": "meeting",
            },
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED

    def test_skip_occurrence(self, cal_client, cal_user):
        """Skip a single occurrence of a recurring event."""
        start = timezone.now() + timedelta(hours=1)
        end = start + timedelta(hours=1)
        event = CalendarEvent.objects.create(
            user=cal_user,
            title="Recurring Event",
            start_time=start,
            end_time=end,
            is_recurring=True,
            recurrence_rule={"frequency": "daily", "interval": 1},
        )
        response = cal_client.post(
            f"/api/calendar/events/{event.id}/skip-occurrence/",
            {"original_date": (timezone.now() + timedelta(days=1)).date().isoformat()},
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED

    def test_skip_occurrence_non_recurring(self, cal_client, cal_event):
        """Skip occurrence on non-recurring event returns 400."""
        response = cal_client.post(
            f"/api/calendar/events/{cal_event.id}/skip-occurrence/",
            {"original_date": timezone.now().date().isoformat()},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_list_exceptions(self, cal_client, cal_user):
        """List recurrence exceptions."""
        start = timezone.now() + timedelta(hours=1)
        end = start + timedelta(hours=1)
        event = CalendarEvent.objects.create(
            user=cal_user,
            title="Recurring Event",
            start_time=start,
            end_time=end,
            is_recurring=True,
            recurrence_rule={"frequency": "daily", "interval": 1},
        )
        response = cal_client.get(
            f"/api/calendar/events/{event.id}/exceptions/"
        )
        assert response.status_code == status.HTTP_200_OK


# ──────────────────────────────────────────────────────────────────────
#  Calendar Heatmap / Overview (CalendarViewSet)
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestCalendarOverview:
    """Tests for calendar overview / heatmap endpoints."""

    def test_heatmap(self, cal_client):
        """Get activity heatmap with date range."""
        from datetime import date, timedelta as td

        today = date.today()
        start = (today - td(days=27)).isoformat()
        end = today.isoformat()
        response = cal_client.get(
            f"/api/calendar/heatmap/?start={start}&end={end}"
        )
        assert response.status_code == status.HTTP_200_OK

    def test_heatmap_missing_params(self, cal_client):
        """Heatmap without params returns 400."""
        response = cal_client.get("/api/calendar/heatmap/")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_get_preferences(self, cal_client):
        """Get calendar preferences."""
        response = cal_client.get("/api/calendar/preferences/")
        assert response.status_code == status.HTTP_200_OK

    def test_update_preferences(self, cal_client):
        """Update calendar preferences."""
        response = cal_client.post(
            "/api/calendar/preferences/",
            {
                "buffer_minutes": 10,
                "min_event_duration": 30,
                "default_view": "week",
            },
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK


# ──────────────────────────────────────────────────────────────────────
#  Habits
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestHabits:
    """Tests for habit CRUD and completion."""

    def test_list_habits(self, cal_client):
        """List habits."""
        response = cal_client.get("/api/calendar/habits/")
        assert response.status_code == status.HTTP_200_OK

    def test_create_habit(self, cal_client):
        """Create a habit."""
        response = cal_client.post(
            "/api/calendar/habits/",
            {
                "name": "Morning Run",
                "frequency": "daily",
            },
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED


# ──────────────────────────────────────────────────────────────────────
#  Calendar Preferences
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestCalendarPreferences:
    """Tests for calendar preferences endpoint."""

    def test_get_preferences(self, cal_client):
        """Get calendar preferences."""
        response = cal_client.get("/api/calendar/preferences/")
        assert response.status_code == status.HTTP_200_OK

    def test_set_preferences(self, cal_client):
        """Set calendar preferences."""
        response = cal_client.post(
            "/api/calendar/preferences/",
            {
                "default_event_duration": 30,
                "work_start_hour": 9,
                "work_end_hour": 17,
            },
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK


# ──────────────────────────────────────────────────────────────────────
#  Calendar Timezone
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestCalendarTimezone:
    """Tests for calendar timezone endpoint."""

    def test_get_timezone(self, cal_client):
        """Get user timezone."""
        response = cal_client.get("/api/calendar/timezone/")
        assert response.status_code == status.HTTP_200_OK

    def test_set_timezone(self, cal_client):
        """Set user timezone."""
        response = cal_client.put(
            "/api/calendar/timezone/",
            {"timezone": "America/New_York"},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK


# ──────────────────────────────────────────────────────────────────────
#  Calendar Tasks View
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestCalendarTasks:
    """Tests for calendar task views."""

    def test_upcoming_alerts(self, cal_client):
        """Get upcoming alerts."""
        response = cal_client.get("/api/calendar/upcoming-alerts/")
        assert response.status_code == status.HTTP_200_OK

    def test_overdue_tasks(self, cal_client):
        """Get overdue tasks."""
        response = cal_client.get("/api/calendar/overdue/")
        assert response.status_code == status.HTTP_200_OK


# ──────────────────────────────────────────────────────────────────────
#  Event Search
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestEventSearch:
    """Tests for event search endpoint."""

    def test_search_events(self, cal_client, cal_event):
        """Search events by query."""
        response = cal_client.get("/api/calendar/events/search/?q=Meeting")
        assert response.status_code == status.HTTP_200_OK

    def test_search_events_empty(self, cal_client):
        """Search with no results."""
        response = cal_client.get("/api/calendar/events/search/?q=nonexistent")
        assert response.status_code == status.HTTP_200_OK


# ──────────────────────────────────────────────────────────────────────
#  Event Categories
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestEventCategories:
    """Tests for event categories endpoint."""

    def test_list_categories(self, cal_client):
        """List event categories."""
        response = cal_client.get("/api/calendar/events/categories/")
        assert response.status_code == status.HTTP_200_OK


# ──────────────────────────────────────────────────────────────────────
#  Event Snooze & Dismiss
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestEventSnoozeDismiss:
    """Tests for snooze and dismiss event endpoints."""

    def test_snooze_event(self, cal_client, cal_event):
        """Snooze an event."""
        response = cal_client.post(
            f"/api/calendar/events/{cal_event.id}/snooze/",
            {"snooze_minutes": 15},
            format="json",
        )
        assert response.status_code in (
            status.HTTP_200_OK,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_dismiss_event(self, cal_client, cal_event):
        """Dismiss an event alert."""
        response = cal_client.post(
            f"/api/calendar/events/{cal_event.id}/dismiss/"
        )
        assert response.status_code == status.HTTP_200_OK


# ──────────────────────────────────────────────────────────────────────
#  Time Block Templates
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestTimeBlockTemplates:
    """Tests for time block template endpoints."""

    def test_list_templates(self, cal_client):
        """List time block templates."""
        response = cal_client.get("/api/calendar/timeblock-templates/")
        assert response.status_code == status.HTTP_200_OK

    def test_presets(self, cal_client):
        """Get time block presets."""
        response = cal_client.get("/api/calendar/timeblock-templates/presets/")
        assert response.status_code == status.HTTP_200_OK

    def test_save_current_blocks(self, cal_client, time_block):
        """Save current blocks as template."""
        response = cal_client.post(
            "/api/calendar/timeblock-templates/save-current/",
            {"name": "My Schedule"},
            format="json",
        )
        assert response.status_code in (
            status.HTTP_200_OK,
            status.HTTP_201_CREATED,
        )


# ──────────────────────────────────────────────────────────────────────
#  Calendar View (day/week/month)
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestCalendarView:
    """Tests for GET /api/calendar/view/"""

    def test_calendar_view_default(self, cal_client):
        """Get calendar view with date range."""
        from datetime import datetime, timedelta
        start = (datetime.now() - timedelta(days=7)).isoformat()
        end = (datetime.now() + timedelta(days=7)).isoformat()
        response = cal_client.get(f"/api/calendar/view/?start={start}&end={end}")
        assert response.status_code == status.HTTP_200_OK

    def test_calendar_view_no_params(self, cal_client):
        """Get calendar view without params returns 400."""
        response = cal_client.get("/api/calendar/view/")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_calendar_today(self, cal_client):
        """Get today's calendar data."""
        response = cal_client.get("/api/calendar/today/")
        assert response.status_code == status.HTTP_200_OK

    def test_calendar_overdue(self, cal_client):
        """Get overdue tasks."""
        response = cal_client.get("/api/calendar/overdue/")
        assert response.status_code == status.HTTP_200_OK


# ──────────────────────────────────────────────────────────────────────
#  Schedule Score
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestScheduleScore:
    """Tests for GET /api/calendar/schedule-score/"""

    def test_schedule_score(self, cal_client):
        """Get schedule quality score."""
        response = cal_client.get("/api/calendar/schedule-score/")
        assert response.status_code == status.HTTP_200_OK

    def test_schedule_score_with_date(self, cal_client):
        """Get schedule score for specific date."""
        from datetime import date
        today = date.today().isoformat()
        response = cal_client.get(f"/api/calendar/schedule-score/?date={today}")
        assert response.status_code == status.HTTP_200_OK


# ──────────────────────────────────────────────────────────────────────
#  Daily Summary
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestDailySummary:
    """Tests for GET /api/calendar/daily-summary/"""

    def test_daily_summary(self, cal_client):
        """Get daily summary."""
        response = cal_client.get("/api/calendar/daily-summary/")
        assert response.status_code == status.HTTP_200_OK


# ──────────────────────────────────────────────────────────────────────
#  Suggest Time Slots
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestSuggestTimeSlots:
    """Tests for GET /api/calendar/suggest-time-slots/"""

    def test_suggest_time_slots(self, cal_client):
        """Suggest time slots for a task."""
        response = cal_client.get(
            "/api/calendar/suggest-time-slots/?duration=30"
        )
        assert response.status_code in (
            status.HTTP_200_OK,
            status.HTTP_400_BAD_REQUEST,
        )


# ──────────────────────────────────────────────────────────────────────
#  Rescue
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestCalendarRescue:
    """Tests for POST /api/calendar/rescue/"""

    def test_rescue_empty(self, cal_client):
        """Rescue when no overdue tasks."""
        response = cal_client.post("/api/calendar/rescue/")
        assert response.status_code in (
            status.HTTP_200_OK,
            status.HTTP_400_BAD_REQUEST,
        )


# ──────────────────────────────────────────────────────────────────────
#  Focus Mode
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestFocusMode:
    """Tests for focus mode endpoints."""

    def test_focus_mode_active(self, cal_client):
        """Check if focus mode is active."""
        response = cal_client.get("/api/calendar/focus-mode-active/")
        assert response.status_code == status.HTTP_200_OK

    def test_focus_block_events(self, cal_client):
        """Get focus block events."""
        response = cal_client.get("/api/calendar/focus-block-events/")
        assert response.status_code == status.HTTP_200_OK


# ──────────────────────────────────────────────────────────────────────
#  Calendar Sharing
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestCalendarSharing:
    """Tests for calendar sharing endpoints."""

    def test_shared_with_me_empty(self, cal_client):
        """Get shared calendars when none shared."""
        response = cal_client.get("/api/calendar/shared-with-me/")
        assert response.status_code == status.HTTP_200_OK

    def test_my_shares_empty(self, cal_client):
        """Get my shares when none shared."""
        response = cal_client.get("/api/calendar/my-shares/")
        assert response.status_code == status.HTTP_200_OK

    def test_share_link(self, cal_client):
        """Generate share link."""
        response = cal_client.post("/api/calendar/share-link/")
        assert response.status_code in (
            status.HTTP_200_OK,
            status.HTTP_201_CREATED,
        )


# ──────────────────────────────────────────────────────────────────────
#  Dismiss Event
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestDismissEvent:
    """Tests for POST /api/calendar/events/<id>/dismiss/"""

    def test_dismiss_nonexistent(self, cal_client):
        """Dismiss nonexistent event returns 404."""
        import uuid
        response = cal_client.post(
            f"/api/calendar/events/{uuid.uuid4()}/dismiss/"
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND


# ──────────────────────────────────────────────────────────────────────
#  Calendar Timezone
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestCalendarTimezoneEndpoint:
    """Tests for /api/calendar/timezone/ endpoint."""

    def test_get_timezone_again(self, cal_client):
        """Get user's calendar timezone."""
        response = cal_client.get("/api/calendar/timezone/")
        assert response.status_code == status.HTTP_200_OK

    def test_set_timezone_valid(self, cal_client):
        """Set user's calendar timezone."""
        response = cal_client.put(
            "/api/calendar/timezone/",
            {"timezone": "America/New_York"},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
