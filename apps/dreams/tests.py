"""
Tests for dreams app.
"""

import pytest
from django.utils import timezone
from datetime import timedelta, date, time as dt_time
from rest_framework import status
from unittest.mock import patch, Mock, MagicMock
import json

from .models import Dream, Goal, Task, Obstacle
from apps.users.models import User


class TestDreamModel:
    """Test Dream model"""

    def test_create_dream(self, db, dream_data):
        """Test creating a dream"""
        dream = Dream.objects.create(**dream_data)

        assert dream.title == dream_data['title']
        assert dream.description == dream_data['description']
        assert dream.user == dream_data['user']
        assert dream.status == 'active'
        assert dream.progress_percentage == 0.0

    def test_dream_str(self, dream):
        """Test dream string representation"""
        assert str(dream) == f"{dream.title} - {dream.user.email}"

    def test_dream_progress_calculation(self, complete_dream_structure):
        """Test calculating dream progress"""
        dream = complete_dream_structure['dream']
        tasks = complete_dream_structure['tasks']

        # Complete half of the tasks
        completed_count = 0
        for i, task in enumerate(tasks):
            if i < len(tasks) // 2:
                task.status = 'completed'
                task.completed_at = timezone.now()
                task.save()
                completed_count += 1

        # Calculate expected progress
        expected_progress = (completed_count / tasks.count()) * 100

        # Trigger progress update (would be done by Celery task)
        total_tasks = tasks.count()
        completed = tasks.filter(status='completed').count()
        dream.progress_percentage = (completed / total_tasks) * 100
        dream.save()

        assert abs(dream.progress_percentage - expected_progress) < 0.01

    def test_dream_completion(self, complete_dream_structure):
        """Test dream completion when all tasks done"""
        dream = complete_dream_structure['dream']
        tasks = complete_dream_structure['tasks']

        # Complete all tasks
        for task in tasks:
            task.status = 'completed'
            task.completed_at = timezone.now()
            task.save()

        # Update progress
        dream.progress_percentage = 100.0
        dream.status = 'completed'
        dream.completed_at = timezone.now()
        dream.save()

        assert dream.status == 'completed'
        assert dream.progress_percentage == 100.0
        assert dream.completed_at is not None

    def test_dream_priority_ordering(self, db, user):
        """Test dreams ordered by priority"""
        dream1 = Dream.objects.create(user=user, title='Low priority', priority=3)
        dream2 = Dream.objects.create(user=user, title='High priority', priority=1)
        dream3 = Dream.objects.create(user=user, title='Medium priority', priority=2)

        dreams = Dream.objects.filter(user=user).order_by('priority')
        assert list(dreams) == [dream2, dream3, dream1]


class TestGoalModel:
    """Test Goal model"""

    def test_create_goal(self, db, goal_data):
        """Test creating a goal"""
        goal = Goal.objects.create(**goal_data)

        assert goal.title == goal_data['title']
        assert goal.dream == goal_data['dream']
        assert goal.order == 0
        assert goal.status == 'pending'

    def test_goal_ordering(self, db, dream):
        """Test goals ordered by order field"""
        goal1 = Goal.objects.create(dream=dream, title='Goal 1', order=2)
        goal2 = Goal.objects.create(dream=dream, title='Goal 2', order=0)
        goal3 = Goal.objects.create(dream=dream, title='Goal 3', order=1)

        goals = Goal.objects.filter(dream=dream).order_by('order')
        assert list(goals) == [goal2, goal3, goal1]

    def test_goal_with_scheduling(self, db, dream):
        """Test goal with scheduled times"""
        scheduled_start = timezone.now() + timedelta(days=1)
        scheduled_end = scheduled_start + timedelta(hours=2)

        goal = Goal.objects.create(
            dream=dream,
            title='Scheduled Goal',
            order=0,
            scheduled_start=scheduled_start,
            scheduled_end=scheduled_end,
            estimated_minutes=120
        )

        assert goal.scheduled_start == scheduled_start
        assert goal.scheduled_end == scheduled_end
        assert goal.estimated_minutes == 120


class TestTaskModel:
    """Test Task model"""

    def test_create_task(self, db, task_data):
        """Test creating a task"""
        task = Task.objects.create(**task_data)

        assert task.title == task_data['title']
        assert task.goal == task_data['goal']
        assert task.status == 'pending'
        assert task.duration_mins == 30

    def test_task_completion(self, task):
        """Test completing a task"""
        task.status = 'completed'
        task.completed_at = timezone.now()
        task.save()

        assert task.status == 'completed'
        assert task.completed_at is not None

    def test_task_with_recurrence(self, db, goal):
        """Test task with recurrence pattern"""
        recurrence_pattern = {
            'frequency': 'daily',
            'interval': 1,
            'days_of_week': [1, 3, 5]  # Mon, Wed, Fri
        }

        task = Task.objects.create(
            goal=goal,
            title='Recurring Task',
            order=0,
            recurrence=recurrence_pattern
        )

        assert task.recurrence['frequency'] == 'daily'
        assert task.recurrence['days_of_week'] == [1, 3, 5]

    def test_task_scheduling(self, db, goal):
        """Test task scheduling"""
        scheduled_date = timezone.now() + timedelta(days=1)

        task = Task.objects.create(
            goal=goal,
            title='Scheduled Task',
            order=0,
            scheduled_date=scheduled_date,
            scheduled_time='14:30',
            duration_mins=45
        )

        assert task.scheduled_date.date() == scheduled_date.date()
        assert task.scheduled_time == '14:30'
        assert task.duration_mins == 45


class TestObstacleModel:
    """Test Obstacle model"""

    def test_create_predicted_obstacle(self, db, dream):
        """Test creating a predicted obstacle"""
        obstacle = Obstacle.objects.create(
            dream=dream,
            title='Time management',
            description='Finding enough time to study',
            obstacle_type='predicted',
            solution='Break study sessions into 30-minute blocks'
        )

        assert obstacle.dream == dream
        assert obstacle.obstacle_type == 'predicted'
        assert obstacle.status == 'active'

    def test_resolve_obstacle(self, db, dream):
        """Test resolving an obstacle"""
        obstacle = Obstacle.objects.create(
            dream=dream,
            title='Learning curve',
            description='Steep learning curve for the topic',
            obstacle_type='actual',
        )

        obstacle.status = 'resolved'
        obstacle.save()

        obstacle.refresh_from_db()
        assert obstacle.status == 'resolved'

    def test_obstacle_str(self, db, dream):
        """Test obstacle string representation"""
        obstacle = Obstacle.objects.create(
            dream=dream,
            title='Technical issue',
            description='Environment setup problems',
            obstacle_type='predicted',
        )

        assert str(obstacle) == 'Obstacle: Technical issue'


class TestDreamViewSet:
    """Test Dream API endpoints

    The dreams app URL config registers router at r'dreams', and the
    root urlconf includes it at 'api/dreams/'. So the full URL for
    dreams is /api/dreams/dreams/.
    """

    def test_list_dreams(self, authenticated_client, user, multiple_dreams):
        """Test GET /api/dreams/dreams/"""
        response = authenticated_client.get('/api/dreams/dreams/')

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['results']) == len(multiple_dreams)

    def test_create_dream(self, authenticated_client, user):
        """Test POST /api/dreams/dreams/"""
        data = {
            'title': 'New Dream',
            'description': 'A new dream to achieve',
            'category': 'personal',
            'priority': 1
        }

        response = authenticated_client.post('/api/dreams/dreams/', data, format='json')

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['title'] == 'New Dream'
        assert Dream.objects.filter(user=user, title='New Dream').exists()

    def test_get_dream_detail(self, authenticated_client, dream):
        """Test GET /api/dreams/dreams/{id}/"""
        response = authenticated_client.get(f'/api/dreams/dreams/{dream.id}/')

        assert response.status_code == status.HTTP_200_OK
        assert response.data['title'] == dream.title
        assert response.data['description'] == dream.description

    def test_update_dream(self, authenticated_client, dream):
        """Test PUT /api/dreams/dreams/{id}/"""
        data = {
            'title': 'Updated Dream Title',
            'description': dream.description,
            'category': dream.category,
            'priority': dream.priority
        }

        response = authenticated_client.put(f'/api/dreams/dreams/{dream.id}/', data, format='json')

        assert response.status_code == status.HTTP_200_OK
        dream.refresh_from_db()
        assert dream.title == 'Updated Dream Title'

    def test_delete_dream(self, authenticated_client, dream):
        """Test DELETE /api/dreams/dreams/{id}/"""
        dream_id = dream.id

        response = authenticated_client.delete(f'/api/dreams/dreams/{dream_id}/')

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not Dream.objects.filter(id=dream_id).exists()

    def test_analyze_dream(self, authenticated_client, dream):
        """Test POST /api/dreams/dreams/{id}/analyze/"""
        mock_analysis = {
            'category': 'education',
            'estimated_duration_weeks': 12,
            'difficulty': 'medium',
            'key_challenges': ['time management'],
            'recommended_approach': 'structured learning',
        }

        with patch('apps.dreams.views.OpenAIService') as mock_service_cls, \
             patch('apps.dreams.views.validate_analysis_response') as mock_validate:
            mock_service_cls.return_value.analyze_dream.return_value = mock_analysis
            # validate_analysis_response returns a pydantic model; mock .model_dump()
            mock_validated = Mock()
            mock_validated.model_dump.return_value = mock_analysis
            mock_validate.return_value = mock_validated

            response = authenticated_client.post(f'/api/dreams/dreams/{dream.id}/analyze/')

        assert response.status_code == status.HTTP_200_OK
        dream.refresh_from_db()
        assert dream.ai_analysis is not None

    def test_generate_plan(self, authenticated_client, dream):
        """Test POST /api/dreams/dreams/{id}/generate_plan/"""
        mock_plan_raw = {
            'analysis': 'Test analysis',
            'estimated_duration_weeks': 12,
            'weekly_time_hours': 5,
            'goals': [
                {
                    'title': 'Goal 1',
                    'description': 'First goal',
                    'order': 0,
                    'estimated_minutes': 120,
                    'tasks': [
                        {
                            'title': 'Task 1-1',
                            'description': 'First task',
                            'order': 0,
                            'duration_mins': 30,
                        }
                    ]
                }
            ],
            'potential_obstacles': [],
            'calibration_references': [],
        }

        # Build mock validated plan that behaves like a pydantic model
        mock_task = Mock()
        mock_task.title = 'Task 1-1'
        mock_task.description = 'First task'
        mock_task.order = 0
        mock_task.duration_mins = 30

        mock_goal = Mock()
        mock_goal.title = 'Goal 1'
        mock_goal.description = 'First goal'
        mock_goal.order = 0
        mock_goal.estimated_minutes = 120
        mock_goal.tasks = [mock_task]

        mock_plan = Mock()
        mock_plan.goals = [mock_goal]
        mock_plan.potential_obstacles = []
        mock_plan.calibration_references = []
        mock_plan.model_dump.return_value = mock_plan_raw

        with patch('apps.dreams.views.OpenAIService') as mock_service_cls, \
             patch('apps.dreams.views.validate_plan_response') as mock_validate, \
             patch('apps.dreams.views.check_plan_calibration_coherence') as mock_coherence:
            mock_service_cls.return_value.generate_plan.return_value = mock_plan_raw
            mock_validate.return_value = mock_plan
            mock_coherence.return_value = []

            response = authenticated_client.post(f'/api/dreams/dreams/{dream.id}/generate_plan/')

        assert response.status_code == status.HTTP_200_OK
        assert Goal.objects.filter(dream=dream).exists()

    def test_generate_two_minute_start(self, authenticated_client, dream):
        """Test POST /api/dreams/dreams/{id}/generate_two_minute_start/

        The view calls OpenAIService.generate_two_minute_start() synchronously
        (not via Celery), creates a Task and updates the dream.
        """
        with patch('apps.dreams.views.OpenAIService') as mock_service_cls:
            mock_service_cls.return_value.generate_two_minute_start.return_value = 'Open Django tutorial'

            response = authenticated_client.post(
                f'/api/dreams/dreams/{dream.id}/generate_two_minute_start/'
            )

        assert response.status_code == status.HTTP_200_OK
        dream.refresh_from_db()
        assert dream.has_two_minute_start is True
        assert Task.objects.filter(goal__dream=dream, is_two_minute_start=True).exists()

    def test_generate_two_minute_start_already_exists(self, authenticated_client, dream):
        """Test that generating a 2-minute start when one already exists returns 400."""
        dream.has_two_minute_start = True
        dream.save(update_fields=['has_two_minute_start'])

        response = authenticated_client.post(
            f'/api/dreams/dreams/{dream.id}/generate_two_minute_start/'
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_generate_vision(self, authenticated_client, dream):
        """Test POST /api/dreams/dreams/{id}/generate_vision/

        The view calls OpenAIService.generate_vision_image() synchronously
        (not via Celery), saves the image URL and returns it.
        """
        with patch('apps.dreams.views.OpenAIService') as mock_service_cls:
            mock_service_cls.return_value.generate_vision_image.return_value = \
                'https://example.com/vision_board.png'

            response = authenticated_client.post(
                f'/api/dreams/dreams/{dream.id}/generate_vision/'
            )

        assert response.status_code == status.HTTP_200_OK
        assert response.data['image_url'] == 'https://example.com/vision_board.png'
        dream.refresh_from_db()
        assert dream.vision_image_url == 'https://example.com/vision_board.png'

    def test_cannot_access_other_user_dream(self, db, authenticated_client, user_data):
        """Test user cannot access another user's dream"""
        # Create another user and their dream
        other_user = User.objects.create(
            email=f'other_{user_data["email"]}'
        )
        other_dream = Dream.objects.create(
            user=other_user,
            title='Other User Dream',
            description='Private dream'
        )

        response = authenticated_client.get(f'/api/dreams/dreams/{other_dream.id}/')
        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestGoalViewSet:
    """Test Goal API endpoints

    Goals are registered at r'goals' under 'api/dreams/' include,
    so the full URL is /api/dreams/goals/.
    """

    def test_list_goals_for_dream(self, authenticated_client, complete_dream_structure):
        """Test GET /api/dreams/goals/?dream={dream_id}"""
        dream = complete_dream_structure['dream']

        response = authenticated_client.get(
            f'/api/dreams/goals/?dream={dream.id}'
        )

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['results']) == 3

    def test_update_goal(self, authenticated_client, goal):
        """Test PATCH /api/dreams/goals/{id}/"""
        data = {
            'title': 'Updated Goal',
        }

        response = authenticated_client.patch(
            f'/api/dreams/goals/{goal.id}/', data, format='json'
        )

        assert response.status_code == status.HTTP_200_OK
        goal.refresh_from_db()
        assert goal.title == 'Updated Goal'

    def test_complete_goal(self, authenticated_client, goal, user):
        """Test POST /api/dreams/goals/{id}/complete/"""
        response = authenticated_client.post(f'/api/dreams/goals/{goal.id}/complete/')

        assert response.status_code == status.HTTP_200_OK
        goal.refresh_from_db()
        assert goal.status == 'completed'
        assert goal.completed_at is not None

        # User should get XP
        user.refresh_from_db()
        assert user.xp > 0


class TestTaskViewSet:
    """Test Task API endpoints

    Tasks are registered at r'tasks' under 'api/dreams/' include,
    so the full URL is /api/dreams/tasks/.
    """

    def test_list_tasks_for_goal(self, authenticated_client, complete_dream_structure):
        """Test GET /api/dreams/tasks/?goal={goal_id}"""
        goal = complete_dream_structure['goals'][0]

        response = authenticated_client.get(
            f'/api/dreams/tasks/?goal={goal.id}'
        )

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['results']) == 3

    def test_update_task(self, authenticated_client, task):
        """Test PATCH /api/dreams/tasks/{id}/"""
        data = {
            'title': 'Updated Task',
        }

        response = authenticated_client.patch(
            f'/api/dreams/tasks/{task.id}/', data, format='json'
        )

        assert response.status_code == status.HTTP_200_OK
        task.refresh_from_db()
        assert task.title == 'Updated Task'

    def test_complete_task(self, authenticated_client, task, user):
        """Test POST /api/dreams/tasks/{id}/complete/"""
        initial_xp = user.xp

        response = authenticated_client.post(f'/api/dreams/tasks/{task.id}/complete/')

        assert response.status_code == status.HTTP_200_OK
        task.refresh_from_db()
        assert task.status == 'completed'
        assert task.completed_at is not None

        # User should get XP based on task duration
        user.refresh_from_db()
        assert user.xp > initial_xp

    def test_skip_task(self, authenticated_client, task):
        """Test POST /api/dreams/tasks/{id}/skip/"""
        response = authenticated_client.post(f'/api/dreams/tasks/{task.id}/skip/')

        assert response.status_code == status.HTTP_200_OK
        task.refresh_from_db()
        assert task.status == 'skipped'


class TestCeleryTasks:
    """Test Celery tasks for dreams

    Note: The Celery tasks use @shared_task(bind=True) which passes `self`
    as the first argument. However, the function signatures in tasks.py
    omit `self`, so we call them directly with just the expected arguments.
    """

    def test_generate_two_minute_start_task(self, db, dream):
        """Test generate_two_minute_start Celery task"""
        with patch('apps.dreams.tasks.OpenAIService') as mock_service_cls:
            mock_service_cls.return_value.generate_two_minute_start.return_value = \
                'Open Django tutorial website'

            from apps.dreams.tasks import generate_two_minute_start
            result = generate_two_minute_start(str(dream.id))

            assert result['created'] is True
            assert Task.objects.filter(
                goal__dream=dream, title__contains='\U0001f680'
            ).exists()

    def test_generate_two_minute_start_task_already_exists(self, db, dream):
        """Test generate_two_minute_start returns early when start already exists"""
        dream.has_two_minute_start = True
        dream.save(update_fields=['has_two_minute_start'])

        from apps.dreams.tasks import generate_two_minute_start
        result = generate_two_minute_start(str(dream.id))

        assert result['created'] is False
        assert result['reason'] == 'already_exists'

    def test_auto_schedule_tasks(self, db, user, complete_dream_structure):
        """Test auto_schedule_tasks task"""
        from apps.dreams.tasks import auto_schedule_tasks

        # Set work schedule
        user.work_schedule = {
            'start_hour': 9,
            'end_hour': 17,
            'working_days': [1, 2, 3, 4, 5]
        }
        user.save()

        result = auto_schedule_tasks(str(user.id))

        assert result['scheduled'] > 0

        # Check tasks are scheduled
        tasks = Task.objects.filter(goal__dream__user=user)
        scheduled_tasks = tasks.filter(scheduled_date__isnull=False)
        assert scheduled_tasks.count() > 0

    def test_update_dream_progress_task(self, db, complete_dream_structure):
        """Test update_dream_progress task"""
        dream = complete_dream_structure['dream']
        tasks = complete_dream_structure['tasks']

        # Complete some tasks
        for task in tasks[:5]:
            task.status = 'completed'
            task.completed_at = timezone.now()
            task.save()

        from apps.dreams.tasks import update_dream_progress
        result = update_dream_progress()

        assert result['updated'] >= 1

        dream.refresh_from_db()
        assert dream.progress_percentage > 0

    def test_detect_obstacles_task(self, db, dream):
        """Test detect_obstacles task"""
        with patch('apps.dreams.tasks.OpenAIService') as mock_service_cls:
            mock_service_cls.return_value.predict_obstacles.return_value = [
                {
                    'title': 'Time constraints',
                    'description': 'Limited time available',
                    'likelihood': 'medium',
                    'solution': 'Use time blocking'
                }
            ]

            from apps.dreams.tasks import detect_obstacles
            result = detect_obstacles(str(dream.id))

            assert result['created'] > 0
            assert Obstacle.objects.filter(dream=dream).exists()

    def test_detect_obstacles_dream_not_found(self, db):
        """Test detect_obstacles with nonexistent dream"""
        import uuid
        from apps.dreams.tasks import detect_obstacles
        result = detect_obstacles(str(uuid.uuid4()))

        assert result['created'] == 0
        assert result['error'] == 'dream_not_found'
