"""
Tests for calendar app.
"""

import pytest
from django.utils import timezone
from datetime import timedelta, date, time as dt_time, datetime, timezone as dt_timezone
from rest_framework import status
from unittest.mock import patch

from apps.dreams.models import Dream, Goal, Task
from apps.calendar.models import CalendarEvent, TimeBlock


class TestCalendarViews:
    """Test Calendar API endpoints"""

    def test_get_calendar_view(self, authenticated_client, user):
        """Test GET /api/calendar/view/?start=...&end=..."""
        # Create some scheduled tasks
        dream = Dream.objects.create(user=user, title='Test Dream', status='active')
        goal = Goal.objects.create(dream=dream, title='Test Goal', order=0)

        today = timezone.now().date()
        for i in range(5):
            task_date = today + timedelta(days=i)
            Task.objects.create(
                goal=goal,
                title=f'Task {i}',
                order=i,
                scheduled_date=timezone.make_aware(
                    datetime.combine(task_date, dt_time(10, 0))
                ),
                scheduled_time='10:00',
                duration_mins=60
            )

        # Request calendar for date range using the view action
        start_dt = datetime.combine(today, dt_time(0, 0)).strftime('%Y-%m-%dT%H:%M:%S')
        end_dt = datetime.combine(today + timedelta(days=7), dt_time(0, 0)).strftime('%Y-%m-%dT%H:%M:%S')

        response = authenticated_client.get(
            '/api/calendar/view/',
            {'start': start_dt, 'end': end_dt}
        )

        assert response.status_code == status.HTTP_200_OK
        # The view action returns a plain list of calendar task dicts
        assert len(response.data) == 5

    def test_get_calendar_view_missing_params(self, authenticated_client):
        """Test GET /api/calendar/view/ without required params returns 400"""
        response = authenticated_client.get('/api/calendar/view/')
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_get_today_tasks(self, authenticated_client, user):
        """Test GET /api/calendar/today/"""
        # Create tasks for today
        dream = Dream.objects.create(user=user, title='Test Dream', status='active')
        goal = Goal.objects.create(dream=dream, title='Test Goal', order=0)

        today = timezone.now()
        yesterday = today - timedelta(days=1)
        tomorrow = today + timedelta(days=1)

        # Task for today
        Task.objects.create(
            goal=goal,
            title='Today Task',
            order=0,
            scheduled_date=today,
            status='pending'
        )

        # Task for yesterday (should not appear)
        Task.objects.create(
            goal=goal,
            title='Yesterday Task',
            order=1,
            scheduled_date=yesterday,
            status='pending'
        )

        # Task for tomorrow (should not appear)
        Task.objects.create(
            goal=goal,
            title='Tomorrow Task',
            order=2,
            scheduled_date=tomorrow,
            status='pending'
        )

        response = authenticated_client.get('/api/calendar/today/')

        assert response.status_code == status.HTTP_200_OK
        # The today action returns a plain list
        assert len(response.data) == 1
        assert response.data[0]['task_title'] == 'Today Task'

    def test_reschedule_task(self, authenticated_client, user, complete_dream_structure):
        """Test POST /api/calendar/reschedule/"""
        task = complete_dream_structure['tasks'].first()

        new_date = (timezone.now() + timedelta(days=5)).isoformat()

        data = {
            'task_id': str(task.id),
            'new_date': new_date,
        }

        response = authenticated_client.post('/api/calendar/reschedule/', data, format='json')

        assert response.status_code == status.HTTP_200_OK
        assert response.data['message'] == 'Task rescheduled successfully'
        assert str(response.data['task_id']) == str(task.id)

    def test_reschedule_task_missing_params(self, authenticated_client):
        """Test POST /api/calendar/reschedule/ without required params returns 400"""
        response = authenticated_client.post('/api/calendar/reschedule/', {}, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_reschedule_task_not_found(self, authenticated_client, user):
        """Test POST /api/calendar/reschedule/ with nonexistent task returns 404"""
        import uuid
        data = {
            'task_id': str(uuid.uuid4()),
            'new_date': timezone.now().isoformat(),
        }
        response = authenticated_client.post('/api/calendar/reschedule/', data, format='json')
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_suggest_time_slots(self, authenticated_client, user):
        """Test GET /api/calendar/suggest-time-slots/?date=...&duration_mins=..."""
        target_date = (timezone.now().date() + timedelta(days=1)).strftime('%Y-%m-%d')

        response = authenticated_client.get(
            f'/api/calendar/suggest-time-slots/?date={target_date}&duration_mins=60'
        )

        assert response.status_code == status.HTTP_200_OK
        assert 'slots' in response.data
        assert response.data['date'] == target_date
        assert response.data['duration_mins'] == 60

    def test_suggest_time_slots_missing_params(self, authenticated_client):
        """Test GET /api/calendar/suggest-time-slots/ without params returns 400"""
        response = authenticated_client.get('/api/calendar/suggest-time-slots/')
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_suggest_time_slots_with_existing_events(self, authenticated_client, user):
        """Test time slot suggestions avoid existing events"""
        tomorrow = timezone.now().date() + timedelta(days=1)
        target_date = tomorrow.strftime('%Y-%m-%d')

        # Create an event blocking 10:00-11:00
        CalendarEvent.objects.create(
            user=user,
            title='Morning Meeting',
            start_time=timezone.make_aware(datetime.combine(tomorrow, dt_time(10, 0))),
            end_time=timezone.make_aware(datetime.combine(tomorrow, dt_time(11, 0))),
            status='scheduled',
        )

        response = authenticated_client.get(
            f'/api/calendar/suggest-time-slots/?date={target_date}&duration_mins=60'
        )

        assert response.status_code == status.HTTP_200_OK
        assert 'slots' in response.data
        # All suggested slots should not overlap with 10:00-11:00
        for slot in response.data['slots']:
            slot_start = datetime.fromisoformat(slot['start'])
            slot_end = datetime.fromisoformat(slot['end'])
            event_start = datetime.combine(tomorrow, dt_time(10, 0)).replace(tzinfo=dt_timezone.utc)
            event_end = datetime.combine(tomorrow, dt_time(11, 0)).replace(tzinfo=dt_timezone.utc)
            # No overlap: slot ends before event starts or slot starts after event ends
            assert slot_end <= event_start or slot_start >= event_end


class TestCalendarEventViewSet:
    """Test CalendarEvent CRUD endpoints"""

    def test_list_events(self, authenticated_client, user):
        """Test GET /api/calendar/events/"""
        now = timezone.now()
        CalendarEvent.objects.create(
            user=user,
            title='Event 1',
            start_time=now,
            end_time=now + timedelta(hours=1),
        )
        CalendarEvent.objects.create(
            user=user,
            title='Event 2',
            start_time=now + timedelta(hours=2),
            end_time=now + timedelta(hours=3),
        )

        response = authenticated_client.get('/api/calendar/events/')

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['results']) == 2

    def test_create_event(self, authenticated_client, user):
        """Test POST /api/calendar/events/"""
        now = timezone.now() + timedelta(hours=1)
        data = {
            'title': 'New Event',
            'start_time': now.isoformat(),
            'end_time': (now + timedelta(hours=1)).isoformat(),
        }

        response = authenticated_client.post('/api/calendar/events/', data, format='json')

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['title'] == 'New Event'
        assert CalendarEvent.objects.filter(user=user, title='New Event').exists()

    def test_create_event_conflict(self, authenticated_client, user):
        """Test POST /api/calendar/events/ with conflicting time returns 409"""
        now = timezone.now() + timedelta(hours=1)
        CalendarEvent.objects.create(
            user=user,
            title='Existing Event',
            start_time=now,
            end_time=now + timedelta(hours=1),
        )

        data = {
            'title': 'Conflicting Event',
            'start_time': (now + timedelta(minutes=30)).isoformat(),
            'end_time': (now + timedelta(hours=2)).isoformat(),
        }

        response = authenticated_client.post('/api/calendar/events/', data, format='json')

        assert response.status_code == status.HTTP_409_CONFLICT
        assert 'conflicts' in response.data

    def test_create_event_force_through_conflict(self, authenticated_client, user):
        """Test POST /api/calendar/events/ with force=true bypasses conflict"""
        now = timezone.now() + timedelta(hours=1)
        CalendarEvent.objects.create(
            user=user,
            title='Existing Event',
            start_time=now,
            end_time=now + timedelta(hours=1),
        )

        data = {
            'title': 'Forced Event',
            'start_time': (now + timedelta(minutes=30)).isoformat(),
            'end_time': (now + timedelta(hours=2)).isoformat(),
            'force': True,
        }

        response = authenticated_client.post('/api/calendar/events/', data, format='json')

        assert response.status_code == status.HTTP_201_CREATED

    def test_reschedule_event(self, authenticated_client, user):
        """Test PATCH /api/calendar/events/{id}/reschedule/"""
        now = timezone.now() + timedelta(hours=1)
        event = CalendarEvent.objects.create(
            user=user,
            title='Event to Reschedule',
            start_time=now,
            end_time=now + timedelta(hours=1),
        )

        new_start = now + timedelta(days=1)
        new_end = new_start + timedelta(hours=1)

        data = {
            'start_time': new_start.isoformat(),
            'end_time': new_end.isoformat(),
        }

        response = authenticated_client.patch(
            f'/api/calendar/events/{event.id}/reschedule/',
            data,
            format='json'
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
            title='Event to Delete',
            start_time=now,
            end_time=now + timedelta(hours=1),
        )

        response = authenticated_client.delete(f'/api/calendar/events/{event.id}/')

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not CalendarEvent.objects.filter(id=event.id).exists()


class TestTimeBlockViewSet:
    """Test TimeBlock CRUD endpoints"""

    def test_list_time_blocks(self, authenticated_client, user):
        """Test GET /api/calendar/timeblocks/"""
        TimeBlock.objects.create(
            user=user,
            block_type='work',
            day_of_week=0,
            start_time=dt_time(9, 0),
            end_time=dt_time(17, 0),
        )

        response = authenticated_client.get('/api/calendar/timeblocks/')

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['results']) == 1

    def test_create_time_block(self, authenticated_client, user):
        """Test POST /api/calendar/timeblocks/"""
        data = {
            'block_type': 'exercise',
            'day_of_week': 1,
            'start_time': '06:00',
            'end_time': '07:00',
        }

        response = authenticated_client.post('/api/calendar/timeblocks/', data, format='json')

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['block_type'] == 'exercise'
        assert TimeBlock.objects.filter(user=user, block_type='exercise').exists()


class TestCalendarEventModel:
    """Test CalendarEvent model"""

    def test_event_str(self, db, user):
        """Test CalendarEvent string representation"""
        now = timezone.now()
        event = CalendarEvent.objects.create(
            user=user,
            title='Test Event',
            start_time=now,
            end_time=now + timedelta(hours=1),
        )
        assert str(event) == f"Test Event at {now}"

    def test_event_default_status(self, db, user):
        """Test CalendarEvent default status is 'scheduled'"""
        now = timezone.now()
        event = CalendarEvent.objects.create(
            user=user,
            title='New Event',
            start_time=now,
            end_time=now + timedelta(hours=1),
        )
        assert event.status == 'scheduled'

    def test_event_with_task_link(self, db, user, complete_dream_structure):
        """Test CalendarEvent linked to a Task"""
        task = complete_dream_structure['tasks'].first()
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
            block_type='work',
            day_of_week=0,
            start_time=dt_time(9, 0),
            end_time=dt_time(17, 0),
        )
        assert str(block) == f"Mon {dt_time(9, 0)}-{dt_time(17, 0)}: work"
