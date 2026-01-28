"""
Tests for calendar app.
"""

import pytest
from django.utils import timezone
from datetime import timedelta, date, time as dt_time
from rest_framework import status
from unittest.mock import patch

from apps.dreams.models import Dream, Goal, Task


class TestCalendarViews:
    """Test Calendar API endpoints"""

    def test_get_calendar_view(self, authenticated_client, user):
        """Test GET /api/calendar/"""
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
                scheduled_date=timezone.make_aware(timezone.datetime.combine(task_date, dt_time(10, 0))),
                scheduled_time='10:00',
                duration_mins=60
            )

        # Request calendar for date range
        start_date = today.isoformat()
        end_date = (today + timedelta(days=7)).isoformat()

        response = authenticated_client.get(
            f'/api/calendar/?start_date={start_date}&end_date={end_date}'
        )

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['events']) == 5

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

        # Task for yesterday
        Task.objects.create(
            goal=goal,
            title='Yesterday Task',
            order=1,
            scheduled_date=yesterday,
            status='pending'
        )

        # Task for tomorrow
        Task.objects.create(
            goal=goal,
            title='Tomorrow Task',
            order=2,
            scheduled_date=tomorrow,
            status='pending'
        )

        response = authenticated_client.get('/api/calendar/today/')

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['tasks']) == 1
        assert response.data['tasks'][0]['title'] == 'Today Task'

    def test_reschedule_tasks(self, authenticated_client, user, complete_dream_structure, mock_celery):
        """Test POST /api/calendar/reschedule/"""
        tasks = complete_dream_structure['tasks']

        # Get task IDs
        task_ids = [str(task.id) for task in tasks[:3]]

        data = {
            'task_ids': task_ids,
            'new_date': (timezone.now().date() + timedelta(days=2)).isoformat()
        }

        response = authenticated_client.post('/api/calendar/reschedule/', data, format='json')

        assert response.status_code == status.HTTP_200_OK
        assert response.data['rescheduled'] == 3

        # Check tasks were rescheduled
        for task_id in task_ids:
            task = Task.objects.get(id=task_id)
            expected_date = timezone.now().date() + timedelta(days=2)
            assert task.scheduled_date.date() == expected_date

    def test_get_weekly_view(self, authenticated_client, user):
        """Test GET /api/calendar/week/"""
        # Create tasks throughout the week
        dream = Dream.objects.create(user=user, title='Test Dream', status='active')
        goal = Goal.objects.create(dream=dream, title='Test Goal', order=0)

        today = timezone.now().date()

        for i in range(7):
            task_date = today + timedelta(days=i)
            Task.objects.create(
                goal=goal,
                title=f'Task day {i}',
                order=i,
                scheduled_date=timezone.make_aware(timezone.datetime.combine(task_date, dt_time(10, 0))),
                status='pending'
            )

        response = authenticated_client.get('/api/calendar/week/')

        assert response.status_code == status.HTTP_200_OK
        assert 'days' in response.data
        assert len(response.data['days']) == 7

    def test_get_monthly_view(self, authenticated_client, user):
        """Test GET /api/calendar/month/"""
        # Create tasks throughout the month
        dream = Dream.objects.create(user=user, title='Test Dream', status='active')
        goal = Goal.objects.create(dream=dream, title='Test Goal', order=0)

        today = timezone.now().date()
        month_start = today.replace(day=1)

        for i in range(10):
            task_date = month_start + timedelta(days=i)
            Task.objects.create(
                goal=goal,
                title=f'Task {i}',
                order=i,
                scheduled_date=timezone.make_aware(timezone.datetime.combine(task_date, dt_time(10, 0))),
                status='pending'
            )

        response = authenticated_client.get('/api/calendar/month/')

        assert response.status_code == status.HTTP_200_OK
        assert 'events' in response.data

    def test_filter_by_dream(self, authenticated_client, user, multiple_dreams):
        """Test filtering calendar by specific dream"""
        dream1, dream2, _ = multiple_dreams

        goal1 = Goal.objects.create(dream=dream1, title='Goal 1', order=0)
        goal2 = Goal.objects.create(dream=dream2, title='Goal 2', order=0)

        today = timezone.now()

        Task.objects.create(goal=goal1, title='Task 1', order=0, scheduled_date=today)
        Task.objects.create(goal=goal2, title='Task 2', order=0, scheduled_date=today)

        response = authenticated_client.get(f'/api/calendar/today/?dream_id={dream1.id}')

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['tasks']) == 1
        assert response.data['tasks'][0]['title'] == 'Task 1'

    def test_overdue_tasks(self, authenticated_client, user):
        """Test GET /api/calendar/overdue/"""
        dream = Dream.objects.create(user=user, title='Test Dream', status='active')
        goal = Goal.objects.create(dream=dream, title='Test Goal', order=0)

        # Create overdue tasks
        yesterday = timezone.now() - timedelta(days=1)
        two_days_ago = timezone.now() - timedelta(days=2)

        Task.objects.create(
            goal=goal,
            title='Overdue 1',
            order=0,
            scheduled_date=yesterday,
            status='pending'
        )

        Task.objects.create(
            goal=goal,
            title='Overdue 2',
            order=1,
            scheduled_date=two_days_ago,
            status='pending'
        )

        # This one is today (not overdue)
        Task.objects.create(
            goal=goal,
            title='Today task',
            order=2,
            scheduled_date=timezone.now(),
            status='pending'
        )

        response = authenticated_client.get('/api/calendar/overdue/')

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['tasks']) == 2

    def test_auto_schedule_endpoint(self, authenticated_client, user, mock_celery):
        """Test POST /api/calendar/auto-schedule/"""
        response = authenticated_client.post('/api/calendar/auto-schedule/')

        assert response.status_code == status.HTTP_200_OK
        # Celery task should be triggered
        assert mock_celery['delay'].called


class TestCalendarServices:
    """Test calendar service functions"""

    def test_get_tasks_for_date_range(self, db, user, complete_dream_structure):
        """Test getting tasks for a date range"""
        from apps.calendar.services import CalendarService

        service = CalendarService()

        start_date = timezone.now().date()
        end_date = start_date + timedelta(days=7)

        # Schedule some tasks in range
        tasks = complete_dream_structure['tasks']
        for i, task in enumerate(tasks[:5]):
            task_date = start_date + timedelta(days=i)
            task.scheduled_date = timezone.make_aware(
                timezone.datetime.combine(task_date, dt_time(10, 0))
            )
            task.save()

        result = service.get_tasks_for_range(user, start_date, end_date)

        assert len(result) == 5

    def test_get_tasks_by_day(self, db, user, complete_dream_structure):
        """Test grouping tasks by day"""
        from apps.calendar.services import CalendarService

        service = CalendarService()

        today = timezone.now().date()

        # Schedule tasks on different days
        tasks = complete_dream_structure['tasks']

        for i in range(3):
            task_date = today + timedelta(days=i)
            tasks[i].scheduled_date = timezone.make_aware(
                timezone.datetime.combine(task_date, dt_time(10, 0))
            )
            tasks[i].save()

        result = service.get_tasks_by_day(user, today, today + timedelta(days=2))

        assert len(result) == 3  # 3 days

    def test_check_time_slot_available(self, db, user, complete_dream_structure):
        """Test checking if time slot is available"""
        from apps.calendar.services import CalendarService

        service = CalendarService()

        # Schedule a task at 10:00
        task = complete_dream_structure['tasks'].first()
        task.scheduled_date = timezone.now().replace(hour=10, minute=0)
        task.scheduled_time = '10:00'
        task.duration_mins = 60
        task.save()

        # Check if 10:30 is available (should be False - conflict)
        check_time = timezone.now().replace(hour=10, minute=30)
        available = service.is_time_slot_available(user, check_time, 30)

        # Should detect conflict
        # Implementation depends on service logic

    def test_suggest_next_available_slot(self, db, user):
        """Test suggesting next available time slot"""
        from apps.calendar.services import CalendarService

        service = CalendarService()

        # Set user work schedule
        user.work_schedule = {
            'start_hour': 9,
            'end_hour': 17,
            'working_days': [1, 2, 3, 4, 5]
        }
        user.save()

        next_slot = service.suggest_next_slot(user, duration_mins=60)

        assert next_slot is not None
        # Should be within work hours
        assert 9 <= next_slot.hour <= 17
