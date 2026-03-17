"""
Tests for calendar app.
"""

from datetime import datetime
from datetime import time as dt_time
from datetime import timedelta
from datetime import timezone as dt_timezone

from django.utils import timezone
from rest_framework import status

from apps.calendar.models import CalendarEvent, TimeBlock
from apps.dreams.models import Dream, Goal, Task


class TestCalendarViews:
    """Test Calendar API endpoints"""

    def test_get_calendar_view(self, authenticated_client, user):
        """Test GET /api/calendar/view/?start=...&end=..."""
        # Create some scheduled tasks
        dream = Dream.objects.create(user=user, title="Test Dream", status="active")
        goal = Goal.objects.create(dream=dream, title="Test Goal", order=0)

        today = timezone.now().date()
        for i in range(5):
            task_date = today + timedelta(days=i)
            Task.objects.create(
                goal=goal,
                title=f"Task {i}",
                order=i,
                scheduled_date=timezone.make_aware(
                    datetime.combine(task_date, dt_time(10, 0))
                ),
                scheduled_time="10:00",
                duration_mins=60,
            )

        # Request calendar for date range using the view action
        start_dt = datetime.combine(today, dt_time(0, 0)).strftime("%Y-%m-%dT%H:%M:%S")
        end_dt = datetime.combine(today + timedelta(days=7), dt_time(0, 0)).strftime(
            "%Y-%m-%dT%H:%M:%S"
        )

        response = authenticated_client.get(
            "/api/calendar/view/", {"start": start_dt, "end": end_dt}
        )

        assert response.status_code == status.HTTP_200_OK
        # The view action returns a plain list of calendar task dicts
        assert len(response.data) == 5

    def test_get_calendar_view_missing_params(self, authenticated_client):
        """Test GET /api/calendar/view/ without required params returns 400"""
        response = authenticated_client.get("/api/calendar/view/")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_get_today_tasks(self, authenticated_client, user):
        """Test GET /api/calendar/today/"""
        # Create tasks for today
        dream = Dream.objects.create(user=user, title="Test Dream", status="active")
        goal = Goal.objects.create(dream=dream, title="Test Goal", order=0)

        today = timezone.now()
        yesterday = today - timedelta(days=1)
        tomorrow = today + timedelta(days=1)

        # Task for today
        Task.objects.create(
            goal=goal,
            title="Today Task",
            order=0,
            scheduled_date=today,
            status="pending",
        )

        # Task for yesterday (should not appear)
        Task.objects.create(
            goal=goal,
            title="Yesterday Task",
            order=1,
            scheduled_date=yesterday,
            status="pending",
        )

        # Task for tomorrow (should not appear)
        Task.objects.create(
            goal=goal,
            title="Tomorrow Task",
            order=2,
            scheduled_date=tomorrow,
            status="pending",
        )

        response = authenticated_client.get("/api/calendar/today/")

        assert response.status_code == status.HTTP_200_OK
        # The today action returns a plain list
        assert len(response.data) == 1
        assert response.data[0]["task_title"] == "Today Task"

    def test_reschedule_task(
        self, authenticated_client, user, complete_dream_structure
    ):
        """Test POST /api/calendar/reschedule/"""
        task = complete_dream_structure["tasks"].first()

        new_date = (timezone.now() + timedelta(days=5)).isoformat()

        data = {
            "task_id": str(task.id),
            "new_date": new_date,
        }

        response = authenticated_client.post(
            "/api/calendar/reschedule/", data, format="json"
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["message"] == "Task rescheduled successfully"
        assert str(response.data["task_id"]) == str(task.id)

    def test_reschedule_task_missing_params(self, authenticated_client):
        """Test POST /api/calendar/reschedule/ without required params returns 400"""
        response = authenticated_client.post(
            "/api/calendar/reschedule/", {}, format="json"
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_reschedule_task_not_found(self, authenticated_client, user):
        """Test POST /api/calendar/reschedule/ with nonexistent task returns 404"""
        import uuid

        data = {
            "task_id": str(uuid.uuid4()),
            "new_date": timezone.now().isoformat(),
        }
        response = authenticated_client.post(
            "/api/calendar/reschedule/", data, format="json"
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_suggest_time_slots(self, authenticated_client, user):
        """Test GET /api/calendar/suggest-time-slots/?date=...&duration_mins=..."""
        target_date = (timezone.now().date() + timedelta(days=1)).strftime("%Y-%m-%d")

        response = authenticated_client.get(
            f"/api/calendar/suggest-time-slots/?date={target_date}&duration_mins=60"
        )

        assert response.status_code == status.HTTP_200_OK
        assert "slots" in response.data
        assert response.data["date"] == target_date
        assert response.data["duration_mins"] == 60

    def test_suggest_time_slots_missing_params(self, authenticated_client):
        """Test GET /api/calendar/suggest-time-slots/ without params returns 400"""
        response = authenticated_client.get("/api/calendar/suggest-time-slots/")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_suggest_time_slots_with_existing_events(self, authenticated_client, user):
        """Test time slot suggestions avoid existing events"""
        tomorrow = timezone.now().date() + timedelta(days=1)
        target_date = tomorrow.strftime("%Y-%m-%d")

        # Create an event blocking 10:00-11:00
        CalendarEvent.objects.create(
            user=user,
            title="Morning Meeting",
            start_time=timezone.make_aware(datetime.combine(tomorrow, dt_time(10, 0))),
            end_time=timezone.make_aware(datetime.combine(tomorrow, dt_time(11, 0))),
            status="scheduled",
        )

        response = authenticated_client.get(
            f"/api/calendar/suggest-time-slots/?date={target_date}&duration_mins=60"
        )

        assert response.status_code == status.HTTP_200_OK
        assert "slots" in response.data
        # All suggested slots should not overlap with 10:00-11:00
        for slot in response.data["slots"]:
            slot_start = datetime.fromisoformat(slot["start"])
            slot_end = datetime.fromisoformat(slot["end"])
            event_start = datetime.combine(tomorrow, dt_time(10, 0)).replace(
                tzinfo=dt_timezone.utc
            )
            event_end = datetime.combine(tomorrow, dt_time(11, 0)).replace(
                tzinfo=dt_timezone.utc
            )
            # No overlap: slot ends before event starts or slot starts after event ends
            assert slot_end <= event_start or slot_start >= event_end


class TestCalendarEventViewSet:
    """Test CalendarEvent CRUD endpoints"""

    def test_list_events(self, authenticated_client, user):
        """Test GET /api/calendar/events/"""
        now = timezone.now()
        CalendarEvent.objects.create(
            user=user,
            title="Event 1",
            start_time=now,
            end_time=now + timedelta(hours=1),
        )
        CalendarEvent.objects.create(
            user=user,
            title="Event 2",
            start_time=now + timedelta(hours=2),
            end_time=now + timedelta(hours=3),
        )

        response = authenticated_client.get("/api/calendar/events/")

        assert response.status_code == status.HTTP_200_OK
        # CalendarEventViewSet overrides list() and returns a plain list
        assert len(response.data) == 2

    def test_create_event(self, authenticated_client, user):
        """Test POST /api/calendar/events/"""
        now = timezone.now() + timedelta(hours=1)
        data = {
            "title": "New Event",
            "start_time": now.isoformat(),
            "end_time": (now + timedelta(hours=1)).isoformat(),
        }

        response = authenticated_client.post(
            "/api/calendar/events/", data, format="json"
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["title"] == "New Event"
        # title is encrypted — verify event was created via count
        assert CalendarEvent.objects.filter(user=user).count() == 1

    def test_create_event_conflict(self, authenticated_client, user):
        """Test POST /api/calendar/events/ with conflicting time returns 409"""
        now = timezone.now() + timedelta(hours=1)
        CalendarEvent.objects.create(
            user=user,
            title="Existing Event",
            start_time=now,
            end_time=now + timedelta(hours=1),
        )

        data = {
            "title": "Conflicting Event",
            "start_time": (now + timedelta(minutes=30)).isoformat(),
            "end_time": (now + timedelta(hours=2)).isoformat(),
        }

        response = authenticated_client.post(
            "/api/calendar/events/", data, format="json"
        )

        assert response.status_code == status.HTTP_409_CONFLICT
        assert "conflicts" in response.data

    def test_create_event_force_through_conflict(self, authenticated_client, user):
        """Test POST /api/calendar/events/ with force=true bypasses conflict"""
        now = timezone.now() + timedelta(hours=1)
        CalendarEvent.objects.create(
            user=user,
            title="Existing Event",
            start_time=now,
            end_time=now + timedelta(hours=1),
        )

        data = {
            "title": "Forced Event",
            "start_time": (now + timedelta(minutes=30)).isoformat(),
            "end_time": (now + timedelta(hours=2)).isoformat(),
            "force": True,
        }

        response = authenticated_client.post(
            "/api/calendar/events/", data, format="json"
        )

        assert response.status_code == status.HTTP_201_CREATED

    def test_reschedule_event(self, authenticated_client, user):
        """Test PATCH /api/calendar/events/{id}/reschedule/"""
        now = timezone.now() + timedelta(hours=1)
        event = CalendarEvent.objects.create(
            user=user,
            title="Event to Reschedule",
            start_time=now,
            end_time=now + timedelta(hours=1),
        )

        new_start = now + timedelta(days=1)
        new_end = new_start + timedelta(hours=1)

        data = {
            "start_time": new_start.isoformat(),
            "end_time": new_end.isoformat(),
        }

        response = authenticated_client.patch(
            f"/api/calendar/events/{event.id}/reschedule/", data, format="json"
        )

        assert response.status_code == status.HTTP_200_OK
        event.refresh_from_db()
        assert event.start_time == new_start
        assert event.end_time == new_end

    def test_delete_event(self, authenticated_client, user):
        """Test DELETE /api/calendar/events/{id}/"""
        now = timezone.now()
        event = CalendarEvent.objects.create(
            user=user,
            title="Event to Delete",
            start_time=now,
            end_time=now + timedelta(hours=1),
        )

        response = authenticated_client.delete(f"/api/calendar/events/{event.id}/")

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not CalendarEvent.objects.filter(id=event.id).exists()


class TestTimeBlockViewSet:
    """Test TimeBlock CRUD endpoints"""

    def test_list_time_blocks(self, authenticated_client, user):
        """Test GET /api/calendar/timeblocks/"""
        TimeBlock.objects.create(
            user=user,
            block_type="work",
            day_of_week=0,
            start_time=dt_time(9, 0),
            end_time=dt_time(17, 0),
        )

        response = authenticated_client.get("/api/calendar/timeblocks/")

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]) == 1

    def test_create_time_block(self, authenticated_client, user):
        """Test POST /api/calendar/timeblocks/"""
        data = {
            "block_type": "exercise",
            "day_of_week": 1,
            "start_time": "06:00",
            "end_time": "07:00",
        }

        response = authenticated_client.post(
            "/api/calendar/timeblocks/", data, format="json"
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["block_type"] == "exercise"
        assert TimeBlock.objects.filter(user=user, block_type="exercise").exists()


class TestCalendarEventModel:
    """Test CalendarEvent model"""

    def test_event_str(self, db, user):
        """Test CalendarEvent string representation"""
        now = timezone.now()
        event = CalendarEvent.objects.create(
            user=user,
            title="Test Event",
            start_time=now,
            end_time=now + timedelta(hours=1),
        )
        assert str(event) == f"Test Event at {now}"

    def test_event_default_status(self, db, user):
        """Test CalendarEvent default status is 'scheduled'"""
        now = timezone.now()
        event = CalendarEvent.objects.create(
            user=user,
            title="New Event",
            start_time=now,
            end_time=now + timedelta(hours=1),
        )
        assert event.status == "scheduled"

    def test_event_with_task_link(self, db, user, complete_dream_structure):
        """Test CalendarEvent linked to a Task"""
        task = complete_dream_structure["tasks"].first()
        now = timezone.now()
        event = CalendarEvent.objects.create(
            user=user,
            task=task,
            title=task.title,
            start_time=now,
            end_time=now + timedelta(minutes=task.duration_mins or 30),
        )
        assert event.task == task


class TestTimeBlockModel:
    """Test TimeBlock model"""

    def test_time_block_str(self, db, user):
        """Test TimeBlock string representation"""
        block = TimeBlock.objects.create(
            user=user,
            block_type="work",
            day_of_week=0,
            start_time=dt_time(9, 0),
            end_time=dt_time(17, 0),
        )
        assert str(block) == f"Mon {dt_time(9, 0)}-{dt_time(17, 0)}: work"

    def test_time_block_focus_label(self, db, user):
        """Test TimeBlock focus block includes [FOCUS] in str."""
        block = TimeBlock.objects.create(
            user=user,
            block_type="work",
            day_of_week=2,
            start_time=dt_time(9, 0),
            end_time=dt_time(12, 0),
            focus_block=True,
        )
        result = str(block)
        assert "[FOCUS]" in result
        assert "Wed" in result

    def test_time_block_all_days(self, db, user):
        """Test TimeBlock can be created for each day of the week."""
        days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        for i, day in enumerate(days):
            block = TimeBlock.objects.create(
                user=user,
                block_type="personal",
                day_of_week=i,
                start_time=dt_time(8, 0),
                end_time=dt_time(9, 0),
            )
            assert day in str(block)

    def test_time_block_default_values(self, db, user):
        """Test TimeBlock default values."""
        block = TimeBlock.objects.create(
            user=user,
            block_type="exercise",
            day_of_week=5,
            start_time=dt_time(6, 0),
            end_time=dt_time(7, 0),
        )
        assert block.is_active is True
        assert block.focus_block is False

    def test_time_block_types(self, db, user):
        """Test all block types can be created."""
        for code, _ in TimeBlock.BLOCK_TYPE_CHOICES:
            block = TimeBlock.objects.create(
                user=user,
                block_type=code,
                day_of_week=0,
                start_time=dt_time(10, 0),
                end_time=dt_time(11, 0),
            )
            assert block.block_type == code
            block.delete()


# ===================================================================
# TimeBlockTemplate model tests
# ===================================================================


class TestTimeBlockTemplateModel:
    """Test TimeBlockTemplate model."""

    def test_create_template(self, db, user):
        from apps.calendar.models import TimeBlockTemplate

        tpl = TimeBlockTemplate.objects.create(
            user=user,
            name="Morning Routine",
            description="My morning schedule",
            blocks=[
                {
                    "block_type": "exercise",
                    "day_of_week": 0,
                    "start_time": "06:00",
                    "end_time": "07:00",
                },
                {
                    "block_type": "work",
                    "day_of_week": 0,
                    "start_time": "09:00",
                    "end_time": "17:00",
                },
            ],
        )
        assert tpl.pk is not None
        assert len(tpl.blocks) == 2

    def test_template_str_user(self, db, user):
        from apps.calendar.models import TimeBlockTemplate

        tpl = TimeBlockTemplate.objects.create(
            user=user,
            name="Work Template",
            blocks=[],
            is_preset=False,
        )
        result = str(tpl)
        assert "Work Template" in result
        assert user.email in result

    def test_template_str_preset(self, db, user):
        from apps.calendar.models import TimeBlockTemplate

        tpl = TimeBlockTemplate.objects.create(
            user=user,
            name="Default Schedule",
            blocks=[],
            is_preset=True,
        )
        result = str(tpl)
        assert "Default Schedule" in result
        assert "preset" in result

    def test_template_ordering(self, db, user):
        """Presets come before user templates."""
        from apps.calendar.models import TimeBlockTemplate

        user_tpl = TimeBlockTemplate.objects.create(
            user=user,
            name="User Template",
            blocks=[],
            is_preset=False,
        )
        preset_tpl = TimeBlockTemplate.objects.create(
            user=user,
            name="Preset Template",
            blocks=[],
            is_preset=True,
        )
        templates = list(TimeBlockTemplate.objects.filter(user=user))
        # Ordering: -is_preset, -created_at -> presets first
        assert templates[0] == preset_tpl
        assert templates[1] == user_tpl


# ===================================================================
# GoogleCalendarIntegration model tests
# ===================================================================


class TestGoogleCalendarIntegrationModel:
    """Test GoogleCalendarIntegration model."""

    def test_create_integration(self, db, user):
        from apps.calendar.models import GoogleCalendarIntegration

        integration = GoogleCalendarIntegration.objects.create(
            user=user,
            access_token="ya29.test_access_token",
            refresh_token="1//test_refresh_token",
            token_expiry=timezone.now() + timedelta(hours=1),
        )
        assert integration.pk is not None
        assert integration.calendar_id == "primary"
        assert integration.sync_enabled is True
        assert integration.sync_direction == "both"

    def test_integration_auto_generates_ical_token(self, db, user):
        from apps.calendar.models import GoogleCalendarIntegration

        integration = GoogleCalendarIntegration.objects.create(
            user=user,
            access_token="ya29.test",
            refresh_token="1//test",
            token_expiry=timezone.now() + timedelta(hours=1),
        )
        assert integration.ical_feed_token != ""
        assert len(integration.ical_feed_token) > 20

    def test_integration_str(self, db, user):
        from apps.calendar.models import GoogleCalendarIntegration

        integration = GoogleCalendarIntegration.objects.create(
            user=user,
            access_token="ya29.test",
            refresh_token="1//test",
            token_expiry=timezone.now() + timedelta(hours=1),
        )
        result = str(integration)
        assert user.email in result
        assert "primary" in result

    def test_one_to_one_constraint(self, db, user):
        from apps.calendar.models import GoogleCalendarIntegration

        GoogleCalendarIntegration.objects.create(
            user=user,
            access_token="ya29.test",
            refresh_token="1//test",
            token_expiry=timezone.now() + timedelta(hours=1),
        )
        import pytest

        with pytest.raises(Exception):
            GoogleCalendarIntegration.objects.create(
                user=user,
                access_token="ya29.test2",
                refresh_token="1//test2",
                token_expiry=timezone.now() + timedelta(hours=2),
            )

    def test_sync_direction_choices(self, db, user):
        from apps.calendar.models import GoogleCalendarIntegration

        for choice, _ in GoogleCalendarIntegration.SYNC_DIRECTION_CHOICES:
            integration = GoogleCalendarIntegration(
                user=user,
                access_token="ya29.test",
                refresh_token="1//test",
                token_expiry=timezone.now() + timedelta(hours=1),
                sync_direction=choice,
            )
            assert integration.sync_direction == choice


# ===================================================================
# RecurrenceException model tests
# ===================================================================


class TestRecurrenceExceptionModel:
    """Test RecurrenceException model."""

    def test_create_skip_exception(self, db, user):
        from apps.calendar.models import RecurrenceException

        now = timezone.now()
        event = CalendarEvent.objects.create(
            user=user,
            title="Weekly Meeting",
            start_time=now,
            end_time=now + timedelta(hours=1),
            is_recurring=True,
        )
        exc = RecurrenceException.objects.create(
            parent_event=event,
            original_date=now.date(),
            skip_occurrence=True,
        )
        assert exc.pk is not None
        assert "Skip" in str(exc)

    def test_create_modify_exception(self, db, user):
        from apps.calendar.models import RecurrenceException

        now = timezone.now()
        event = CalendarEvent.objects.create(
            user=user,
            title="Daily Standup",
            start_time=now,
            end_time=now + timedelta(minutes=30),
            is_recurring=True,
        )
        modified_start = now + timedelta(hours=2)
        exc = RecurrenceException.objects.create(
            parent_event=event,
            original_date=now.date(),
            skip_occurrence=False,
            modified_title="Late Standup",
            modified_start_time=modified_start,
            modified_end_time=modified_start + timedelta(minutes=30),
        )
        assert "Modify" in str(exc)

    def test_unique_parent_date(self, db, user):
        """Cannot have two exceptions for the same parent + date."""
        import pytest

        from apps.calendar.models import RecurrenceException

        now = timezone.now()
        event = CalendarEvent.objects.create(
            user=user,
            title="Recurring",
            start_time=now,
            end_time=now + timedelta(hours=1),
            is_recurring=True,
        )
        RecurrenceException.objects.create(
            parent_event=event,
            original_date=now.date(),
            skip_occurrence=True,
        )
        with pytest.raises(Exception):
            RecurrenceException.objects.create(
                parent_event=event,
                original_date=now.date(),
                skip_occurrence=False,
            )


# ===================================================================
# CalendarShare model tests
# ===================================================================


class TestCalendarShareModel:
    """Test CalendarShare model."""

    def test_create_share(self, db, user):
        from apps.calendar.models import CalendarShare
        from apps.users.models import User

        other = User.objects.create_user(
            email="sharebuddy@example.com", password="pass123"
        )
        share = CalendarShare.objects.create(
            owner=user,
            shared_with=other,
            permission="view",
        )
        assert share.pk is not None
        assert share.is_active is True
        assert share.share_token != ""

    def test_share_auto_generates_token(self, db, user):
        from apps.calendar.models import CalendarShare

        share = CalendarShare.objects.create(
            owner=user,
            permission="suggest",
        )
        assert share.share_token != ""
        assert len(share.share_token) > 20

    def test_share_str_with_user(self, db, user):
        from apps.calendar.models import CalendarShare
        from apps.users.models import User

        other = User.objects.create_user(
            email="sharewith@example.com", password="pass123"
        )
        share = CalendarShare.objects.create(
            owner=user,
            shared_with=other,
        )
        result = str(share)
        assert user.email in result
        assert other.email in result

    def test_share_str_link_only(self, db, user):
        from apps.calendar.models import CalendarShare

        share = CalendarShare.objects.create(
            owner=user,
        )
        result = str(share)
        assert "link:" in result

    def test_unique_owner_shared_with(self, db, user):
        """Cannot share with the same user twice."""
        import pytest

        from apps.calendar.models import CalendarShare
        from apps.users.models import User

        other = User.objects.create_user(
            email="uniqueshare@example.com", password="pass123"
        )
        CalendarShare.objects.create(owner=user, shared_with=other)
        with pytest.raises(Exception):
            CalendarShare.objects.create(owner=user, shared_with=other)


# ===================================================================
# Habit model tests
# ===================================================================


class TestHabitModel:
    """Test Habit model."""

    def test_create_habit(self, db, user):
        from apps.calendar.models import Habit

        habit = Habit.objects.create(
            user=user,
            name="Meditate",
            frequency="daily",
            target_per_day=1,
        )
        assert habit.pk is not None
        assert habit.streak_current == 0
        assert habit.streak_best == 0
        assert habit.is_active is True

    def test_habit_str(self, db, user):
        from apps.calendar.models import Habit

        habit = Habit.objects.create(
            user=user,
            name="Exercise",
            frequency="daily",
            icon="dumbbell",
        )
        result = str(habit)
        assert "dumbbell" in result
        assert "Exercise" in result
        assert "daily" in result

    def test_habit_frequency_choices(self, db, user):
        from apps.calendar.models import Habit

        for freq, _ in Habit.FREQUENCY_CHOICES:
            habit = Habit.objects.create(
                user=user,
                name=f"Habit {freq}",
                frequency=freq,
            )
            assert habit.frequency == freq
            habit.delete()

    def test_habit_custom_days(self, db, user):
        from apps.calendar.models import Habit

        habit = Habit.objects.create(
            user=user,
            name="Custom Habit",
            frequency="custom",
            custom_days=[0, 2, 4],  # Mon, Wed, Fri
        )
        assert habit.custom_days == [0, 2, 4]


# ===================================================================
# HabitCompletion model tests
# ===================================================================


class TestHabitCompletionModel:
    """Test HabitCompletion model."""

    def test_create_completion(self, db, user):
        from apps.calendar.models import Habit, HabitCompletion

        habit = Habit.objects.create(
            user=user, name="Read", frequency="daily"
        )
        today = timezone.now().date()
        completion = HabitCompletion.objects.create(
            habit=habit,
            date=today,
            count=1,
        )
        assert completion.pk is not None
        assert str(completion) == f"Read - {today} (x1)"

    def test_completion_unique_habit_date(self, db, user):
        """Cannot complete the same habit twice on the same date."""
        import pytest

        from apps.calendar.models import Habit, HabitCompletion

        habit = Habit.objects.create(
            user=user, name="Drink Water", frequency="daily"
        )
        today = timezone.now().date()
        HabitCompletion.objects.create(habit=habit, date=today)
        with pytest.raises(Exception):
            HabitCompletion.objects.create(habit=habit, date=today)

    def test_completion_different_dates(self, db, user):
        """Completions on different dates are allowed."""
        from apps.calendar.models import Habit, HabitCompletion

        habit = Habit.objects.create(
            user=user, name="Walk", frequency="daily"
        )
        today = timezone.now().date()
        yesterday = today - timedelta(days=1)
        HabitCompletion.objects.create(habit=habit, date=today)
        HabitCompletion.objects.create(habit=habit, date=yesterday)
        assert HabitCompletion.objects.filter(habit=habit).count() == 2


# ===================================================================
# CalendarEvent extended model tests
# ===================================================================


class TestCalendarEventExtended:
    """Extended tests for CalendarEvent model."""

    def test_event_categories(self, db, user):
        """All category choices create valid events."""
        for code, _ in CalendarEvent.CATEGORY_CHOICES:
            now = timezone.now()
            event = CalendarEvent.objects.create(
                user=user,
                title=f"Cat {code}",
                start_time=now,
                end_time=now + timedelta(hours=1),
                category=code,
            )
            assert event.category == code
            event.delete()

    def test_event_sync_status_choices(self, db, user):
        """All sync status choices are valid."""
        for code, _ in CalendarEvent.SYNC_STATUS_CHOICES:
            now = timezone.now()
            event = CalendarEvent.objects.create(
                user=user,
                title=f"Sync {code}",
                start_time=now,
                end_time=now + timedelta(hours=1),
                sync_status=code,
            )
            assert event.sync_status == code
            event.delete()

    def test_recurring_event(self, db, user):
        """Recurring event with recurrence rule."""
        now = timezone.now()
        event = CalendarEvent.objects.create(
            user=user,
            title="Weekly Team Sync",
            start_time=now,
            end_time=now + timedelta(hours=1),
            is_recurring=True,
            recurrence_rule={
                "frequency": "weekly",
                "interval": 1,
                "days_of_week": [1],
            },
        )
        assert event.is_recurring is True
        assert event.recurrence_rule["frequency"] == "weekly"

    def test_event_all_day(self, db, user):
        """All-day event."""
        now = timezone.now()
        event = CalendarEvent.objects.create(
            user=user,
            title="Holiday",
            start_time=now,
            end_time=now + timedelta(days=1),
            all_day=True,
        )
        assert event.all_day is True

    def test_event_with_reminders(self, db, user):
        """Event with multiple reminders."""
        now = timezone.now()
        event = CalendarEvent.objects.create(
            user=user,
            title="Important Meeting",
            start_time=now + timedelta(hours=3),
            end_time=now + timedelta(hours=4),
            reminders=[
                {"minutes_before": 15, "type": "push"},
                {"minutes_before": 60, "type": "email"},
            ],
        )
        assert len(event.reminders) == 2

    def test_event_parent_child(self, db, user):
        """Recurring instance links to parent event."""
        now = timezone.now()
        parent = CalendarEvent.objects.create(
            user=user,
            title="Recurring Parent",
            start_time=now,
            end_time=now + timedelta(hours=1),
            is_recurring=True,
        )
        child = CalendarEvent.objects.create(
            user=user,
            title="Recurring Parent",
            start_time=now + timedelta(weeks=1),
            end_time=now + timedelta(weeks=1, hours=1),
            parent_event=parent,
        )
        assert child.parent_event == parent
        assert parent.recurring_instances.count() == 1
