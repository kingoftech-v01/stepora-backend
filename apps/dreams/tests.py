"""
Tests for dreams app.
"""

from datetime import timedelta
from unittest.mock import Mock, patch

from django.utils import timezone
from rest_framework import status

from apps.users.models import User

from .models import Dream, Goal, Obstacle, Task


def _set_user_plan(user, slug):
    """Upgrade a user via the Subscription table (source of truth)."""
    from apps.subscriptions.models import Subscription, SubscriptionPlan

    plan = SubscriptionPlan.objects.filter(slug=slug).first()
    if not plan:
        return
    sub, _ = Subscription.objects.get_or_create(
        user=user,
        defaults={"plan": plan, "status": "active"},
    )
    if sub.plan_id != plan.pk or sub.status != "active":
        sub.plan = plan
        sub.status = "active"
        sub.save(update_fields=["plan", "status"])
    if hasattr(user, "_cached_plan"):
        del user._cached_plan


class TestDreamModel:
    """Test Dream model"""

    def test_create_dream(self, db, dream_data):
        """Test creating a dream"""
        dream = Dream.objects.create(**dream_data)

        assert dream.title == dream_data["title"]
        assert dream.description == dream_data["description"]
        assert dream.user == dream_data["user"]
        assert dream.status == "active"
        assert dream.progress_percentage == 0.0

    def test_dream_str(self, dream):
        """Test dream string representation"""
        assert str(dream) == f"{dream.title} - {dream.user.email}"

    def test_dream_progress_calculation(self, complete_dream_structure):
        """Test calculating dream progress"""
        dream = complete_dream_structure["dream"]
        tasks = complete_dream_structure["tasks"]

        # Complete half of the tasks
        completed_count = 0
        for i, task in enumerate(tasks):
            if i < len(tasks) // 2:
                task.status = "completed"
                task.completed_at = timezone.now()
                task.save()
                completed_count += 1

        # Calculate expected progress
        expected_progress = (completed_count / tasks.count()) * 100

        # Trigger progress update (would be done by Celery task)
        total_tasks = tasks.count()
        completed = tasks.filter(status="completed").count()
        dream.progress_percentage = (completed / total_tasks) * 100
        dream.save()

        assert abs(dream.progress_percentage - expected_progress) < 0.01

    def test_dream_completion(self, complete_dream_structure):
        """Test dream completion when all tasks done"""
        dream = complete_dream_structure["dream"]
        tasks = complete_dream_structure["tasks"]

        # Complete all tasks
        for task in tasks:
            task.status = "completed"
            task.completed_at = timezone.now()
            task.save()

        # Update progress
        dream.progress_percentage = 100.0
        dream.status = "completed"
        dream.completed_at = timezone.now()
        dream.save()

        assert dream.status == "completed"
        assert dream.progress_percentage == 100.0
        assert dream.completed_at is not None

    def test_dream_priority_ordering(self, db, user):
        """Test dreams ordered by priority"""
        dream1 = Dream.objects.create(user=user, title="Low priority", priority=3)
        dream2 = Dream.objects.create(user=user, title="High priority", priority=1)
        dream3 = Dream.objects.create(user=user, title="Medium priority", priority=2)

        dreams = Dream.objects.filter(user=user).order_by("priority")
        assert list(dreams) == [dream2, dream3, dream1]


class TestGoalModel:
    """Test Goal model"""

    def test_create_goal(self, db, goal_data):
        """Test creating a goal"""
        goal = Goal.objects.create(**goal_data)

        assert goal.title == goal_data["title"]
        assert goal.dream == goal_data["dream"]
        assert goal.order == 0
        assert goal.status == "pending"

    def test_goal_ordering(self, db, dream):
        """Test goals ordered by order field"""
        goal1 = Goal.objects.create(dream=dream, title="Goal 1", order=2)
        goal2 = Goal.objects.create(dream=dream, title="Goal 2", order=0)
        goal3 = Goal.objects.create(dream=dream, title="Goal 3", order=1)

        goals = Goal.objects.filter(dream=dream).order_by("order")
        assert list(goals) == [goal2, goal3, goal1]

    def test_goal_with_scheduling(self, db, dream):
        """Test goal with scheduled times"""
        scheduled_start = timezone.now() + timedelta(days=1)
        scheduled_end = scheduled_start + timedelta(hours=2)

        goal = Goal.objects.create(
            dream=dream,
            title="Scheduled Goal",
            order=0,
            scheduled_start=scheduled_start,
            scheduled_end=scheduled_end,
            estimated_minutes=120,
        )

        assert goal.scheduled_start == scheduled_start
        assert goal.scheduled_end == scheduled_end
        assert goal.estimated_minutes == 120


class TestTaskModel:
    """Test Task model"""

    def test_create_task(self, db, task_data):
        """Test creating a task"""
        task = Task.objects.create(**task_data)

        assert task.title == task_data["title"]
        assert task.goal == task_data["goal"]
        assert task.status == "pending"
        assert task.duration_mins == 30

    def test_task_completion(self, task):
        """Test completing a task"""
        task.status = "completed"
        task.completed_at = timezone.now()
        task.save()

        assert task.status == "completed"
        assert task.completed_at is not None

    def test_task_with_recurrence(self, db, goal):
        """Test task with recurrence pattern"""
        recurrence_pattern = {
            "frequency": "daily",
            "interval": 1,
            "days_of_week": [1, 3, 5],  # Mon, Wed, Fri
        }

        task = Task.objects.create(
            goal=goal, title="Recurring Task", order=0, recurrence=recurrence_pattern
        )

        assert task.recurrence["frequency"] == "daily"
        assert task.recurrence["days_of_week"] == [1, 3, 5]

    def test_task_scheduling(self, db, goal):
        """Test task scheduling"""
        scheduled_date = timezone.now() + timedelta(days=1)

        task = Task.objects.create(
            goal=goal,
            title="Scheduled Task",
            order=0,
            scheduled_date=scheduled_date,
            scheduled_time="14:30",
            duration_mins=45,
        )

        assert task.scheduled_date.date() == scheduled_date.date()
        assert task.scheduled_time == "14:30"
        assert task.duration_mins == 45


class TestObstacleModel:
    """Test Obstacle model"""

    def test_create_predicted_obstacle(self, db, dream):
        """Test creating a predicted obstacle"""
        obstacle = Obstacle.objects.create(
            dream=dream,
            title="Time management",
            description="Finding enough time to study",
            obstacle_type="predicted",
            solution="Break study sessions into 30-minute blocks",
        )

        assert obstacle.dream == dream
        assert obstacle.obstacle_type == "predicted"
        assert obstacle.status == "active"

    def test_resolve_obstacle(self, db, dream):
        """Test resolving an obstacle"""
        obstacle = Obstacle.objects.create(
            dream=dream,
            title="Learning curve",
            description="Steep learning curve for the topic",
            obstacle_type="actual",
        )

        obstacle.status = "resolved"
        obstacle.save()

        obstacle.refresh_from_db()
        assert obstacle.status == "resolved"

    def test_obstacle_str(self, db, dream):
        """Test obstacle string representation"""
        obstacle = Obstacle.objects.create(
            dream=dream,
            title="Technical issue",
            description="Environment setup problems",
            obstacle_type="predicted",
        )

        assert str(obstacle) == "Obstacle: Technical issue"


class TestDreamViewSet:
    """Test Dream API endpoints

    The dreams app URL config registers router at r'dreams', and the
    root urlconf includes it at 'api/dreams/'. So the full URL for
    dreams is /api/dreams/dreams/.
    """

    def test_list_dreams(self, authenticated_client, user, multiple_dreams):
        """Test GET /api/dreams/dreams/"""
        response = authenticated_client.get("/api/dreams/dreams/")

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]) == len(multiple_dreams)

    def test_create_dream(self, authenticated_client, user):
        """Test POST /api/dreams/dreams/"""
        data = {
            "title": "New Dream",
            "description": "A new dream to achieve that is at least twenty characters",
            "category": "personal",
            "priority": 1,
        }

        with patch(
            "core.moderation.ContentModerationService.moderate_text"
        ) as mock_mod:
            mock_mod.return_value = Mock(is_flagged=False)
            response = authenticated_client.post(
                "/api/dreams/dreams/", data, format="json"
            )

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["title"] == "New Dream"
        # title is an encrypted field so filter(title=...) won't match;
        # look up by the returned id instead.
        dream_id = response.data["id"]
        assert Dream.objects.filter(id=dream_id, user=user).exists()

    def test_get_dream_detail(self, authenticated_client, dream):
        """Test GET /api/dreams/dreams/{id}/"""
        response = authenticated_client.get(f"/api/dreams/dreams/{dream.id}/")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["title"] == dream.title
        assert response.data["description"] == dream.description

    def test_update_dream(self, authenticated_client, dream):
        """Test PUT /api/dreams/dreams/{id}/"""
        data = {
            "title": "Updated Dream Title",
            "description": dream.description,
            "category": dream.category,
            "priority": dream.priority,
        }

        response = authenticated_client.put(
            f"/api/dreams/dreams/{dream.id}/", data, format="json"
        )

        assert response.status_code == status.HTTP_200_OK
        dream.refresh_from_db()
        assert dream.title == "Updated Dream Title"

    def test_delete_dream(self, authenticated_client, dream):
        """Test DELETE /api/dreams/dreams/{id}/"""
        dream_id = dream.id

        response = authenticated_client.delete(f"/api/dreams/dreams/{dream_id}/")

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not Dream.objects.filter(id=dream_id).exists()

    def test_analyze_dream(self, authenticated_client, dream):
        """Test POST /api/dreams/dreams/{id}/analyze/"""
        # Upgrade user to pro so AI permission gate is satisfied
        _set_user_plan(dream.user, "pro")

        mock_analysis = {
            "category": "education",
            "estimated_duration_weeks": 12,
            "difficulty": "medium",
            "key_challenges": ["time management"],
            "recommended_approach": "structured learning",
        }

        with patch("apps.dreams.views.OpenAIService") as mock_service_cls, patch(
            "apps.dreams.views.validate_analysis_response"
        ) as mock_validate:
            mock_service_cls.return_value.analyze_dream.return_value = mock_analysis
            # validate_analysis_response returns a pydantic model; mock .model_dump()
            mock_validated = Mock()
            mock_validated.model_dump.return_value = mock_analysis
            mock_validate.return_value = mock_validated

            response = authenticated_client.post(
                f"/api/dreams/dreams/{dream.id}/analyze/"
            )

        assert response.status_code == status.HTTP_200_OK
        dream.refresh_from_db()
        assert dream.ai_analysis is not None

    def test_generate_plan(self, authenticated_client, dream):
        """Test POST /api/dreams/dreams/{id}/generate_plan/

        The view now dispatches plan generation as a background Celery task
        and returns 202 Accepted with a status of 'generating'.
        """
        # Upgrade user to pro so AI permission gate is satisfied
        _set_user_plan(dream.user, "pro")

        with patch("apps.dreams.tasks.generate_dream_plan_task") as mock_task, patch(
            "apps.dreams.tasks.get_plan_status", return_value=None
        ), patch("apps.dreams.tasks.set_plan_status"):
            mock_task.delay.return_value = Mock(id="fake-task-id")

            response = authenticated_client.post(
                f"/api/dreams/dreams/{dream.id}/generate_plan/"
            )

        assert response.status_code == status.HTTP_202_ACCEPTED
        assert response.data["status"] == "generating"
        mock_task.delay.assert_called_once()

    def test_generate_two_minute_start(self, authenticated_client, dream):
        """Test POST /api/dreams/dreams/{id}/generate_two_minute_start/

        The view calls OpenAIService.generate_two_minute_start() synchronously
        (not via Celery), creates a Task and updates the dream.
        """
        # Upgrade user to pro so AI permission gate is satisfied
        _set_user_plan(dream.user, "pro")

        with patch("apps.dreams.views.OpenAIService") as mock_service_cls:
            mock_service_cls.return_value.generate_two_minute_start.return_value = (
                "Open Django tutorial"
            )

            response = authenticated_client.post(
                f"/api/dreams/dreams/{dream.id}/generate_two_minute_start/"
            )

        assert response.status_code == status.HTTP_200_OK
        dream.refresh_from_db()
        assert dream.has_two_minute_start is True
        assert Task.objects.filter(goal__dream=dream, is_two_minute_start=True).exists()

    def test_generate_two_minute_start_already_exists(
        self, authenticated_client, dream
    ):
        """Test that generating a 2-minute start when one already exists returns 400."""
        # Upgrade user to pro so AI permission gate is satisfied
        _set_user_plan(dream.user, "pro")

        dream.has_two_minute_start = True
        dream.save(update_fields=["has_two_minute_start"])

        response = authenticated_client.post(
            f"/api/dreams/dreams/{dream.id}/generate_two_minute_start/"
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_generate_vision(self, authenticated_client, dream):
        """Test POST /api/dreams/dreams/{id}/generate_vision/

        The view calls OpenAIService.generate_vision_image() synchronously
        (not via Celery), saves the image URL and returns it.
        """
        # Upgrade user to pro so vision board permission gate is satisfied
        _set_user_plan(dream.user, "pro")

        with patch("apps.dreams.views.OpenAIService") as mock_service_cls:
            mock_service_cls.return_value.generate_vision_image.return_value = (
                "https://example.com/vision_board.png"
            )

            response = authenticated_client.post(
                f"/api/dreams/dreams/{dream.id}/generate_vision/"
            )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["image_url"] == "https://example.com/vision_board.png"
        dream.refresh_from_db()
        assert dream.vision_image_url == "https://example.com/vision_board.png"

    def test_cannot_access_other_user_dream(self, db, authenticated_client, user_data):
        """Test user cannot access another user's dream"""
        # Create another user and their dream
        other_user = User.objects.create(email=f'other_{user_data["email"]}')
        other_dream = Dream.objects.create(
            user=other_user, title="Other User Dream", description="Private dream"
        )

        response = authenticated_client.get(f"/api/dreams/dreams/{other_dream.id}/")
        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestGoalViewSet:
    """Test Goal API endpoints

    Goals are registered at r'goals' under 'api/dreams/' include,
    so the full URL is /api/dreams/goals/.
    """

    def test_list_goals_for_dream(self, authenticated_client, complete_dream_structure):
        """Test GET /api/dreams/goals/?dream={dream_id}"""
        dream = complete_dream_structure["dream"]

        response = authenticated_client.get(f"/api/dreams/goals/?dream={dream.id}")

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]) == 3

    def test_update_goal(self, authenticated_client, goal):
        """Test PATCH /api/dreams/goals/{id}/"""
        data = {
            "title": "Updated Goal",
        }

        response = authenticated_client.patch(
            f"/api/dreams/goals/{goal.id}/", data, format="json"
        )

        assert response.status_code == status.HTTP_200_OK
        goal.refresh_from_db()
        assert goal.title == "Updated Goal"

    def test_complete_goal(self, authenticated_client, goal, user):
        """Test POST /api/dreams/goals/{id}/complete/"""
        response = authenticated_client.post(f"/api/dreams/goals/{goal.id}/complete/")

        assert response.status_code == status.HTTP_200_OK
        goal.refresh_from_db()
        assert goal.status == "completed"
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
        goal = complete_dream_structure["goals"][0]

        response = authenticated_client.get(f"/api/dreams/tasks/?goal={goal.id}")

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]) == 3

    def test_update_task(self, authenticated_client, task):
        """Test PATCH /api/dreams/tasks/{id}/"""
        data = {
            "title": "Updated Task",
        }

        response = authenticated_client.patch(
            f"/api/dreams/tasks/{task.id}/", data, format="json"
        )

        assert response.status_code == status.HTTP_200_OK
        task.refresh_from_db()
        assert task.title == "Updated Task"

    def test_complete_task(self, authenticated_client, task, user):
        """Test POST /api/dreams/tasks/{id}/complete/"""
        initial_xp = user.xp

        response = authenticated_client.post(f"/api/dreams/tasks/{task.id}/complete/")

        assert response.status_code == status.HTTP_200_OK
        task.refresh_from_db()
        assert task.status == "completed"
        assert task.completed_at is not None

        # User should get XP based on task duration
        user.refresh_from_db()
        assert user.xp > initial_xp

    def test_skip_task(self, authenticated_client, task):
        """Test POST /api/dreams/tasks/{id}/skip/"""
        response = authenticated_client.post(f"/api/dreams/tasks/{task.id}/skip/")

        assert response.status_code == status.HTTP_200_OK
        task.refresh_from_db()
        assert task.status == "skipped"


class TestCeleryTasks:
    """Test Celery tasks for dreams

    Note: The Celery tasks use @shared_task(bind=True) which passes `self`
    as the first argument. However, the function signatures in tasks.py
    omit `self`, so we call them directly with just the expected arguments.
    """

    def test_generate_two_minute_start_task(self, db, dream):
        """Test generate_two_minute_start Celery task"""
        with patch("apps.dreams.tasks.OpenAIService") as mock_service_cls:
            mock_service_cls.return_value.generate_two_minute_start.return_value = (
                "Open Django tutorial website"
            )

            from apps.dreams.tasks import generate_two_minute_start

            result = generate_two_minute_start(str(dream.id))

            assert result["created"] is True
            assert result["action"] == "Open Django tutorial website"
            # Task is created with is_two_minute_start=True (title is encrypted,
            # so we cannot filter by title__contains).
            dream.refresh_from_db()
            assert dream.has_two_minute_start is True

    def test_generate_two_minute_start_task_already_exists(self, db, dream):
        """Test generate_two_minute_start returns early when start already exists"""
        dream.has_two_minute_start = True
        dream.save(update_fields=["has_two_minute_start"])

        from apps.dreams.tasks import generate_two_minute_start

        result = generate_two_minute_start(str(dream.id))

        assert result["created"] is False
        assert result["reason"] == "already_exists"

    def test_auto_schedule_tasks(self, db, user, complete_dream_structure):
        """Test auto_schedule_tasks task"""
        from apps.dreams.tasks import auto_schedule_tasks

        # Set work schedule
        user.work_schedule = {
            "start_hour": 9,
            "end_hour": 17,
            "working_days": [1, 2, 3, 4, 5],
        }
        user.save()

        result = auto_schedule_tasks(str(user.id))

        assert result["scheduled"] > 0

        # Check tasks are scheduled
        tasks = Task.objects.filter(goal__dream__user=user)
        scheduled_tasks = tasks.filter(scheduled_date__isnull=False)
        assert scheduled_tasks.count() > 0

    def test_update_dream_progress_task(self, db, complete_dream_structure):
        """Test update_dream_progress task"""
        dream = complete_dream_structure["dream"]
        tasks = complete_dream_structure["tasks"]

        # Complete some tasks
        for task in tasks[:5]:
            task.status = "completed"
            task.completed_at = timezone.now()
            task.save()

        from apps.dreams.tasks import update_dream_progress

        result = update_dream_progress()

        assert result["updated"] >= 1

        dream.refresh_from_db()
        assert dream.progress_percentage > 0

    def test_detect_obstacles_task(self, db, dream):
        """Test detect_obstacles task"""
        with patch("apps.dreams.tasks.OpenAIService") as mock_service_cls:
            mock_service_cls.return_value.predict_obstacles.return_value = [
                {
                    "title": "Time constraints",
                    "description": "Limited time available",
                    "likelihood": "medium",
                    "solution": "Use time blocking",
                }
            ]

            from apps.dreams.tasks import detect_obstacles

            result = detect_obstacles(str(dream.id))

            assert result["created"] > 0
            assert Obstacle.objects.filter(dream=dream).exists()

    def test_detect_obstacles_dream_not_found(self, db):
        """Test detect_obstacles with nonexistent dream"""
        import uuid

        from apps.dreams.tasks import detect_obstacles

        result = detect_obstacles(str(uuid.uuid4()))

        assert result["created"] == 0
        assert result["error"] == "dream_not_found"


# ---------------------------------------------------------------------------
# Milestone CRUD Tests
# ---------------------------------------------------------------------------


class TestMilestoneViewSet:
    """Test DreamMilestone API endpoints.

    Milestones are registered at r'milestones' under 'api/dreams/' include,
    so the full URL is /api/dreams/milestones/.
    """

    def test_list_milestones_for_dream(self, authenticated_client, dream):
        """Test GET /api/dreams/milestones/?dream={dream_id}"""
        from apps.dreams.models import DreamMilestone

        DreamMilestone.objects.create(dream=dream, title="Month 1", order=1)
        DreamMilestone.objects.create(dream=dream, title="Month 2", order=2)

        response = authenticated_client.get(f"/api/dreams/milestones/?dream={dream.id}")

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]) == 2

    def test_create_milestone(self, authenticated_client, dream):
        """Test POST /api/dreams/milestones/"""
        from apps.dreams.models import DreamMilestone

        data = {
            "dream": str(dream.id),
            "title": "New Milestone",
            "description": "First milestone",
            "order": 1,
        }

        response = authenticated_client.post(
            "/api/dreams/milestones/", data, format="json"
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert DreamMilestone.objects.filter(dream=dream).count() == 1

    def test_complete_milestone(self, authenticated_client, dream):
        """Test POST /api/dreams/milestones/{id}/complete/"""
        from apps.dreams.models import DreamMilestone

        milestone = DreamMilestone.objects.create(
            dream=dream, title="Milestone to complete", order=1
        )

        response = authenticated_client.post(
            f"/api/dreams/milestones/{milestone.id}/complete/"
        )

        assert response.status_code == status.HTTP_200_OK
        milestone.refresh_from_db()
        assert milestone.status == "completed"
        assert milestone.completed_at is not None

    def test_complete_already_completed_milestone(self, authenticated_client, dream):
        """Test completing an already-completed milestone returns 400."""
        from apps.dreams.models import DreamMilestone

        milestone = DreamMilestone.objects.create(
            dream=dream,
            title="Done milestone",
            order=1,
            status="completed",
            completed_at=timezone.now(),
        )

        response = authenticated_client.post(
            f"/api/dreams/milestones/{milestone.id}/complete/"
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_milestone_idor_prevention(
        self, db, authenticated_client, user_data
    ):
        """Test that a user cannot access another user's milestones."""
        from apps.dreams.models import DreamMilestone

        other_user = User.objects.create(email=f'other_{user_data["email"]}')
        other_dream = Dream.objects.create(
            user=other_user, title="Other Dream", description="Private"
        )
        other_milestone = DreamMilestone.objects.create(
            dream=other_dream, title="Other Milestone", order=1
        )

        response = authenticated_client.get(
            f"/api/dreams/milestones/{other_milestone.id}/"
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND


# ---------------------------------------------------------------------------
# Journal CRUD Tests
# ---------------------------------------------------------------------------


class TestDreamJournalViewSet:
    """Test DreamJournal API endpoints.

    Journal entries are registered at r'journal' under 'api/dreams/' include,
    so the full URL is /api/dreams/journal/.
    """

    def test_list_journal_entries(self, authenticated_client, dream):
        """Test GET /api/dreams/journal/?dream={dream_id}"""
        from apps.dreams.models import DreamJournal

        DreamJournal.objects.create(
            dream=dream,
            title="Day 1",
            content="Started working on the dream today.",
            mood="motivated",
        )
        DreamJournal.objects.create(
            dream=dream,
            title="Day 2",
            content="Made progress on first goal.",
            mood="happy",
        )

        response = authenticated_client.get(f"/api/dreams/journal/?dream={dream.id}")

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]) == 2

    def test_create_journal_entry(self, authenticated_client, dream):
        """Test POST /api/dreams/journal/"""
        from apps.dreams.models import DreamJournal

        data = {
            "dream": str(dream.id),
            "title": "Reflection",
            "content": "Today I reflected on my progress.",
            "mood": "reflective",
        }

        response = authenticated_client.post(
            "/api/dreams/journal/", data, format="json"
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert DreamJournal.objects.filter(dream=dream).count() == 1

    def test_update_journal_entry(self, authenticated_client, dream):
        """Test PATCH /api/dreams/journal/{id}/"""
        from apps.dreams.models import DreamJournal

        entry = DreamJournal.objects.create(
            dream=dream,
            title="Initial",
            content="Content to update.",
            mood="neutral",
        )

        response = authenticated_client.patch(
            f"/api/dreams/journal/{entry.id}/",
            {"title": "Updated Title", "mood": "excited"},
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK
        entry.refresh_from_db()
        assert entry.title == "Updated Title"
        assert entry.mood == "excited"

    def test_delete_journal_entry(self, authenticated_client, dream):
        """Test DELETE /api/dreams/journal/{id}/"""
        from apps.dreams.models import DreamJournal

        entry = DreamJournal.objects.create(
            dream=dream,
            title="To Delete",
            content="Will be deleted.",
        )
        entry_id = entry.id

        response = authenticated_client.delete(f"/api/dreams/journal/{entry_id}/")

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not DreamJournal.objects.filter(id=entry_id).exists()

    def test_journal_idor_prevention(self, db, authenticated_client, user_data):
        """Test that a user cannot access another user's journal entries."""
        from apps.dreams.models import DreamJournal

        other_user = User.objects.create(email=f'other_{user_data["email"]}')
        other_dream = Dream.objects.create(
            user=other_user, title="Other Dream", description="Private"
        )
        other_entry = DreamJournal.objects.create(
            dream=other_dream,
            title="Private",
            content="Should not be accessible.",
        )

        response = authenticated_client.get(f"/api/dreams/journal/{other_entry.id}/")
        assert response.status_code == status.HTTP_404_NOT_FOUND


# ---------------------------------------------------------------------------
# IDOR Prevention Tests (Goals, Tasks, Obstacles)
# ---------------------------------------------------------------------------


class TestIDORPrevention:
    """Test that users cannot access/modify other users' goals, tasks, and obstacles."""

    def test_goal_idor_read(self, db, authenticated_client, user_data):
        """Test that a user cannot read another user's goals."""
        other_user = User.objects.create(email=f'other_goal_{user_data["email"]}')
        other_dream = Dream.objects.create(
            user=other_user, title="Other Dream", description="Secret"
        )
        other_goal = Goal.objects.create(
            dream=other_dream, title="Secret Goal", order=0
        )

        response = authenticated_client.get(f"/api/dreams/goals/{other_goal.id}/")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_goal_idor_update(self, db, authenticated_client, user_data):
        """Test that a user cannot update another user's goals."""
        other_user = User.objects.create(email=f'other_goal_up_{user_data["email"]}')
        other_dream = Dream.objects.create(
            user=other_user, title="Other Dream", description="Secret"
        )
        other_goal = Goal.objects.create(
            dream=other_dream, title="Secret Goal", order=0
        )

        response = authenticated_client.patch(
            f"/api/dreams/goals/{other_goal.id}/",
            {"title": "Hacked"},
            format="json",
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_task_idor_read(self, db, authenticated_client, user_data):
        """Test that a user cannot read another user's tasks."""
        other_user = User.objects.create(email=f'other_task_{user_data["email"]}')
        other_dream = Dream.objects.create(
            user=other_user, title="Other Dream", description="Secret"
        )
        other_goal = Goal.objects.create(
            dream=other_dream, title="Secret Goal", order=0
        )
        other_task = Task.objects.create(
            goal=other_goal, title="Secret Task", order=0
        )

        response = authenticated_client.get(f"/api/dreams/tasks/{other_task.id}/")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_task_idor_complete(self, db, authenticated_client, user_data):
        """Test that a user cannot complete another user's tasks."""
        other_user = User.objects.create(email=f'other_task_c_{user_data["email"]}')
        other_dream = Dream.objects.create(
            user=other_user, title="Other Dream", description="Secret"
        )
        other_goal = Goal.objects.create(
            dream=other_dream, title="Secret Goal", order=0
        )
        other_task = Task.objects.create(
            goal=other_goal, title="Secret Task", order=0
        )

        response = authenticated_client.post(
            f"/api/dreams/tasks/{other_task.id}/complete/"
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_obstacle_idor_read(self, db, authenticated_client, user_data):
        """Test that a user cannot read another user's obstacles."""
        from apps.dreams.models import Obstacle

        other_user = User.objects.create(email=f'other_obs_{user_data["email"]}')
        other_dream = Dream.objects.create(
            user=other_user, title="Other Dream", description="Secret"
        )
        other_obstacle = Obstacle.objects.create(
            dream=other_dream,
            title="Secret Obstacle",
            description="Should not be readable",
            obstacle_type="predicted",
        )

        response = authenticated_client.get(
            f"/api/dreams/obstacles/{other_obstacle.id}/"
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND


# ---------------------------------------------------------------------------
# Check-In Tests
# ---------------------------------------------------------------------------


class TestCheckInViewSet:
    """Test PlanCheckIn API endpoints.

    Check-ins are registered at r'checkins' under 'api/dreams/' include,
    so the full URL is /api/dreams/checkins/.
    """

    def test_list_checkins_for_dream(self, authenticated_client, dream):
        """Test GET /api/dreams/checkins/?dream={dream_id}"""
        from apps.dreams.models import PlanCheckIn

        PlanCheckIn.objects.create(
            dream=dream,
            status="completed",
            scheduled_for=timezone.now(),
            pace_status="on_track",
            coaching_message="Keep going!",
        )

        response = authenticated_client.get(
            f"/api/dreams/checkins/?dream={dream.id}"
        )

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]) == 1

    def test_checkin_detail(self, authenticated_client, dream):
        """Test GET /api/dreams/checkins/{id}/"""
        from apps.dreams.models import PlanCheckIn

        checkin = PlanCheckIn.objects.create(
            dream=dream,
            status="completed",
            scheduled_for=timezone.now(),
            pace_status="ahead",
            coaching_message="You are doing great!",
        )

        response = authenticated_client.get(f"/api/dreams/checkins/{checkin.id}/")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["pace_status"] == "ahead"

    def test_checkin_respond(self, authenticated_client, dream):
        """Test POST /api/dreams/checkins/{id}/respond/ submits questionnaire."""
        from apps.dreams.models import PlanCheckIn

        checkin = PlanCheckIn.objects.create(
            dream=dream,
            status="awaiting_user",
            scheduled_for=timezone.now(),
            questionnaire=[
                {
                    "id": "q1",
                    "question_type": "text",
                    "question": "How is your progress?",
                    "is_required": True,
                }
            ],
        )

        with patch("apps.dreams.tasks.process_checkin_responses_task") as mock_task:
            mock_task.apply_async.return_value = Mock(id="fake-task-id")

            response = authenticated_client.post(
                f"/api/dreams/checkins/{checkin.id}/respond/",
                {"responses": {"q1": "Going well!"}},
                format="json",
            )

        assert response.status_code == status.HTTP_202_ACCEPTED
        checkin.refresh_from_db()
        assert checkin.status == "ai_processing"
        assert checkin.user_responses["q1"] == "Going well!"

    def test_checkin_respond_not_awaiting(self, authenticated_client, dream):
        """Test responding to a check-in that is not awaiting user response."""
        from apps.dreams.models import PlanCheckIn

        checkin = PlanCheckIn.objects.create(
            dream=dream,
            status="completed",
            scheduled_for=timezone.now(),
        )

        response = authenticated_client.post(
            f"/api/dreams/checkins/{checkin.id}/respond/",
            {"responses": {"q1": "Answer"}},
            format="json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_checkin_idor_prevention(self, db, authenticated_client, user_data):
        """Test that a user cannot access another user's check-ins."""
        from apps.dreams.models import PlanCheckIn

        other_user = User.objects.create(email=f'other_ci_{user_data["email"]}')
        other_dream = Dream.objects.create(
            user=other_user, title="Other Dream", description="Private"
        )
        other_checkin = PlanCheckIn.objects.create(
            dream=other_dream,
            status="completed",
            scheduled_for=timezone.now(),
        )

        response = authenticated_client.get(
            f"/api/dreams/checkins/{other_checkin.id}/"
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND
