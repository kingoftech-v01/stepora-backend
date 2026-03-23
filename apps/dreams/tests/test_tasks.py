"""
Tests for apps/dreams/tasks.py — Celery tasks.

Covers:
- generate_dream_plan_task (mock OpenAI + AI validators)
- generate_two_minute_start
- auto_schedule_tasks
- detect_obstacles
- update_dream_progress
- check_overdue_tasks
- suggest_task_adjustments
- Helper functions: set_plan_status, get_plan_status, _parse_date
"""

import uuid
from datetime import timedelta
from unittest.mock import Mock, patch

import pytest
from django.utils import timezone

from apps.dreams.models import Dream, DreamMilestone, Goal, Obstacle, Task
from apps.notifications.models import Notification

# ──────────────────────────────────────────────────────────────────────
#  Helpers: set_plan_status / get_plan_status / _parse_date
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestPlanStatusHelpers:
    """Tests for plan status Redis helpers."""

    def test_set_and_get_plan_status(self):
        """set_plan_status stores status and get_plan_status retrieves it."""
        from apps.dreams.tasks import get_plan_status, set_plan_status

        dream_id = str(uuid.uuid4())
        set_plan_status(dream_id, "generating", message="Test")

        status = get_plan_status(dream_id)
        assert status is not None
        assert status["status"] == "generating"
        assert status["message"] == "Test"

    def test_get_plan_status_returns_none_for_missing(self):
        """get_plan_status returns None for nonexistent key."""
        from apps.dreams.tasks import get_plan_status

        assert get_plan_status(str(uuid.uuid4())) is None


class TestParseDate:
    """Tests for the _parse_date helper."""

    def test_valid_date(self):
        from apps.dreams.tasks import _parse_date

        result = _parse_date("2026-03-15")
        assert result is not None
        assert result.year == 2026
        assert result.month == 3
        assert result.day == 15

    def test_none_returns_none(self):
        from apps.dreams.tasks import _parse_date

        assert _parse_date(None) is None

    def test_empty_string_returns_none(self):
        from apps.dreams.tasks import _parse_date

        assert _parse_date("") is None

    def test_invalid_format_returns_none(self):
        from apps.dreams.tasks import _parse_date

        assert _parse_date("not-a-date") is None

    def test_trims_trailing_chars(self):
        from apps.dreams.tasks import _parse_date

        result = _parse_date("2026-01-01T12:00:00")
        assert result is not None
        assert result.year == 2026


# ──────────────────────────────────────────────────────────────────────
#  generate_dream_plan_task
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestGenerateDreamPlanTask:
    """Tests for generate_dream_plan_task."""

    @patch("core.ai_usage.AIUsageTracker")
    @patch("core.ai_validators.validate_plan_response")
    @patch("core.ai_validators.check_plan_calibration_coherence")
    @patch("apps.dreams.tasks.OpenAIService")
    def test_successful_plan_generation(
        self,
        mock_ai_cls,
        mock_coherence,
        mock_validate,
        mock_tracker_cls,
        dream_user,
    ):
        """generate_dream_plan_task creates milestones, goals, and tasks."""
        dream = Dream.objects.create(
            user=dream_user,
            title="Test Plan",
            description="Test plan generation",
            status="active",
        )

        # Build a mock plan with milestones, goals, tasks
        mock_task = Mock(
            title="Task 1",
            description="desc",
            order=1,
            duration_mins=30,
            day_number=1,
            expected_date=None,
            deadline_date=None,
        )
        mock_goal = Mock(
            title="Goal 1",
            description="desc",
            order=1,
            estimated_minutes=60,
            expected_date=None,
            deadline_date=None,
            tasks=[mock_task],
        )
        mock_obstacle = Mock(
            title="Obstacle 1",
            description="desc",
            solution="solution",
            goal_order=None,
        )
        mock_milestone = Mock(
            title="Milestone 1",
            description="desc",
            order=1,
            target_day=7,
            expected_date=None,
            deadline_date=None,
            goals=[mock_goal],
            obstacles=[mock_obstacle],
        )
        mock_plan_obstacle = Mock(
            title="Global Obstacle",
            description="desc",
            solution="sol",
            milestone_order=None,
            goal_order=None,
        )
        mock_plan = Mock(
            milestones=[mock_milestone],
            goals=[],
            potential_obstacles=[mock_plan_obstacle],
        )
        mock_plan.model_dump.return_value = {"milestones": [], "goals": []}

        mock_ai = Mock()
        mock_ai.generate_plan.return_value = {"milestones": []}
        mock_ai_cls.return_value = mock_ai

        mock_validate.return_value = mock_plan
        mock_coherence.return_value = []

        mock_tracker = Mock()
        mock_tracker_cls.return_value = mock_tracker

        from apps.dreams.tasks import generate_dream_plan_task

        result = generate_dream_plan_task(str(dream.id), str(dream_user.id))

        assert result["status"] == "completed"
        assert result["milestones"] >= 1
        assert result["goals"] >= 1
        assert result["tasks"] >= 1
        assert DreamMilestone.objects.filter(dream=dream).count() >= 1
        assert Goal.objects.filter(dream=dream).count() >= 1
        assert Task.objects.filter(goal__dream=dream).count() >= 1
        assert Obstacle.objects.filter(dream=dream).count() >= 1

    def test_dream_not_found(self, dream_user):
        """generate_dream_plan_task returns failed for nonexistent dream."""
        from apps.dreams.tasks import generate_dream_plan_task

        result = generate_dream_plan_task(str(uuid.uuid4()), str(dream_user.id))
        assert result["status"] == "failed"
        assert result["error"] == "dream_not_found"


# ──────────────────────────────────────────────────────────────────────
#  generate_two_minute_start
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestGenerateTwoMinuteStart:
    """Tests for generate_two_minute_start task."""

    @patch("apps.dreams.tasks.OpenAIService")
    def test_creates_micro_action(self, mock_ai_cls, dream_user):
        """generate_two_minute_start creates a 2-minute task."""
        dream = Dream.objects.create(
            user=dream_user,
            title="Learn Guitar",
            description="Beginner guitar",
            status="active",
            has_two_minute_start=False,
        )

        mock_ai = Mock()
        mock_ai.generate_two_minute_start.return_value = "Watch a 2-min intro video"
        mock_ai_cls.return_value = mock_ai

        from apps.dreams.tasks import generate_two_minute_start

        result = generate_two_minute_start(str(dream.id))
        assert result["created"] is True

        dream.refresh_from_db()
        assert dream.has_two_minute_start is True

        # Task should exist
        tasks = Task.objects.filter(goal__dream=dream)
        assert tasks.exists()
        assert tasks.first().duration_mins == 2

    @patch("apps.dreams.tasks.OpenAIService")
    def test_skips_if_already_has_two_minute_start(self, mock_ai_cls, dream_user):
        """generate_two_minute_start skips dreams that already have one."""
        dream = Dream.objects.create(
            user=dream_user,
            title="Learn Guitar",
            description="Beginner guitar",
            status="active",
            has_two_minute_start=True,
        )

        from apps.dreams.tasks import generate_two_minute_start

        result = generate_two_minute_start(str(dream.id))
        assert result["created"] is False
        assert result["reason"] == "already_exists"

    def test_dream_not_found(self, db):
        """generate_two_minute_start handles missing dream."""
        from apps.dreams.tasks import generate_two_minute_start

        result = generate_two_minute_start(str(uuid.uuid4()))
        assert result["created"] is False
        assert result["error"] == "dream_not_found"


# ──────────────────────────────────────────────────────────────────────
#  auto_schedule_tasks
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestAutoScheduleTasks:
    """Tests for auto_schedule_tasks task."""

    def test_schedules_unscheduled_tasks(self, dream_user):
        """auto_schedule_tasks schedules pending tasks without a date."""
        dream = Dream.objects.create(
            user=dream_user, title="D", description="d", status="active"
        )
        goal = Goal.objects.create(dream=dream, title="G", order=1)
        Task.objects.create(
            goal=goal, title="T1", order=1, status="pending", duration_mins=30
        )
        Task.objects.create(
            goal=goal, title="T2", order=2, status="pending", duration_mins=30
        )

        from apps.dreams.tasks import auto_schedule_tasks

        result = auto_schedule_tasks(str(dream_user.id))
        assert result["scheduled"] == 2

        # Tasks should now have scheduled_date
        for task in Task.objects.filter(goal=goal):
            assert task.scheduled_date is not None

    def test_no_unscheduled_tasks(self, dream_user):
        """auto_schedule_tasks returns 0 when no tasks need scheduling."""
        from apps.dreams.tasks import auto_schedule_tasks

        result = auto_schedule_tasks(str(dream_user.id))
        assert result["scheduled"] == 0

    def test_user_not_found(self, db):
        """auto_schedule_tasks handles missing user."""
        from apps.dreams.tasks import auto_schedule_tasks

        result = auto_schedule_tasks(str(uuid.uuid4()))
        assert result["scheduled"] == 0
        assert result["error"] == "user_not_found"


# ──────────────────────────────────────────────────────────────────────
#  detect_obstacles
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestDetectObstacles:
    """Tests for detect_obstacles task."""

    @patch("apps.dreams.tasks.OpenAIService")
    def test_creates_obstacles(self, mock_ai_cls, dream_user):
        """detect_obstacles creates obstacle records from AI predictions."""
        dream = Dream.objects.create(
            user=dream_user, title="D", description="d", status="active"
        )

        mock_ai = Mock()
        mock_ai.predict_obstacles_simple.return_value = [
            {
                "title": "Time Management",
                "description": "May struggle with time",
                "solution": "Use a planner",
            },
        ]
        mock_ai_cls.return_value = mock_ai

        from apps.dreams.tasks import detect_obstacles

        result = detect_obstacles(str(dream.id))
        assert result["created"] == 1
        assert Obstacle.objects.filter(dream=dream).count() == 1

    def test_dream_not_found(self, db):
        """detect_obstacles handles missing dream."""
        from apps.dreams.tasks import detect_obstacles

        result = detect_obstacles(str(uuid.uuid4()))
        assert result["created"] == 0
        assert result["error"] == "dream_not_found"

    @patch("apps.dreams.tasks.OpenAIService")
    def test_creates_new_obstacles_only(self, mock_ai_cls, dream_user):
        """detect_obstacles creates new obstacles but uses get_or_create for dedup."""
        dream = Dream.objects.create(
            user=dream_user, title="D", description="d", status="active"
        )

        mock_ai = Mock()
        mock_ai.predict_obstacles_simple.return_value = [
            {"title": "New Obstacle", "description": "desc", "solution": "sol"},
            {"title": "Another Obstacle", "description": "desc2", "solution": "sol2"},
        ]
        mock_ai_cls.return_value = mock_ai

        from apps.dreams.tasks import detect_obstacles

        result = detect_obstacles(str(dream.id))
        assert result["created"] == 2
        assert Obstacle.objects.filter(dream=dream).count() == 2


# ──────────────────────────────────────────────────────────────────────
#  update_dream_progress
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestUpdateDreamProgress:
    """Tests for update_dream_progress task."""

    def test_updates_progress(self, dream_user):
        """update_dream_progress recalculates progress based on completed tasks."""
        dream = Dream.objects.create(
            user=dream_user, title="D", description="d", status="active"
        )
        goal = Goal.objects.create(dream=dream, title="G", order=1)
        Task.objects.create(
            goal=goal,
            title="T1",
            order=1,
            status="completed",
            completed_at=timezone.now(),
        )
        Task.objects.create(goal=goal, title="T2", order=2, status="pending")

        from apps.dreams.tasks import update_dream_progress

        result = update_dream_progress()
        assert result["updated"] >= 1

        dream.refresh_from_db()
        assert dream.progress_percentage == 50.0

    def test_completes_dream_at_100(self, dream_user):
        """update_dream_progress marks dream as completed at 100%."""
        dream = Dream.objects.create(
            user=dream_user, title="Complete", description="d", status="active"
        )
        goal = Goal.objects.create(dream=dream, title="G", order=1)
        Task.objects.create(
            goal=goal,
            title="T1",
            order=1,
            status="completed",
            completed_at=timezone.now(),
        )

        from apps.dreams.tasks import update_dream_progress

        update_dream_progress()

        dream.refresh_from_db()
        assert dream.progress_percentage == 100.0
        assert dream.status == "completed"
        assert dream.completed_at is not None

        # Should have a dream_completed notification
        assert Notification.objects.filter(
            user=dream_user, notification_type="dream_completed"
        ).exists()

    def test_no_active_dreams(self, dream_user):
        """update_dream_progress returns updated=0 when no active dreams."""
        from apps.dreams.tasks import update_dream_progress

        result = update_dream_progress()
        assert result["updated"] == 0


# ──────────────────────────────────────────────────────────────────────
#  check_overdue_tasks
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestCheckOverdueTasks:
    """Tests for check_overdue_tasks task."""

    def test_sends_overdue_notification(self, dream_user):
        """check_overdue_tasks sends notification for overdue tasks."""
        dream = Dream.objects.create(
            user=dream_user, title="D", description="d", status="active"
        )
        goal = Goal.objects.create(dream=dream, title="G", order=1)

        # Create an overdue task (yesterday)
        yesterday = timezone.now() - timedelta(days=1)
        Task.objects.create(
            goal=goal,
            title="Overdue Task",
            order=1,
            status="pending",
            scheduled_date=yesterday,
        )

        from apps.dreams.tasks import check_overdue_tasks

        result = check_overdue_tasks()
        assert result["sent"] >= 1
        assert Notification.objects.filter(
            user=dream_user, notification_type="overdue_tasks"
        ).exists()

    def test_no_overdue_tasks(self, dream_user):
        """check_overdue_tasks returns 0 when no tasks are overdue."""
        from apps.dreams.tasks import check_overdue_tasks

        result = check_overdue_tasks()
        assert result["sent"] == 0


# ──────────────────────────────────────────────────────────────────────
#  suggest_task_adjustments
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestSuggestTaskAdjustments:
    """Tests for suggest_task_adjustments task."""

    @patch("apps.dreams.tasks.OpenAIService")
    def test_sends_suggestions_for_low_completion_rate(self, mock_ai_cls, dream_user):
        """suggest_task_adjustments sends suggestions when completion rate < 50%."""
        dream = Dream.objects.create(
            user=dream_user, title="D", description="d", status="active"
        )
        goal = Goal.objects.create(dream=dream, title="G", order=1)

        # Create 10 tasks, 2 completed (20% rate)
        for i in range(10):
            Task.objects.create(
                goal=goal,
                title=f"T{i}",
                order=i,
                status="completed" if i < 2 else "pending",
                completed_at=timezone.now() if i < 2 else None,
            )

        mock_ai = Mock()
        mock_ai.generate_task_adjustments.return_value = {
            "summary": "Break tasks into smaller chunks",
            "detailed": ["Reduce task duration", "Add buffer time"],
        }
        mock_ai_cls.return_value = mock_ai

        from apps.dreams.tasks import suggest_task_adjustments

        result = suggest_task_adjustments(str(dream_user.id))
        assert result["sent"] is True
        assert result["completion_rate"] == 20.0

    def test_skips_for_good_completion_rate(self, dream_user):
        """suggest_task_adjustments skips users with >= 50% completion rate."""
        dream = Dream.objects.create(
            user=dream_user, title="D", description="d", status="active"
        )
        goal = Goal.objects.create(dream=dream, title="G", order=1)

        # All tasks completed
        Task.objects.create(
            goal=goal,
            title="T1",
            order=1,
            status="completed",
            completed_at=timezone.now(),
        )

        from apps.dreams.tasks import suggest_task_adjustments

        result = suggest_task_adjustments(str(dream_user.id))
        assert result["sent"] is False
        assert result["completion_rate"] == 100.0

    def test_user_not_found(self, db):
        """suggest_task_adjustments handles missing user."""
        from apps.dreams.tasks import suggest_task_adjustments

        result = suggest_task_adjustments(str(uuid.uuid4()))
        assert result["sent"] is False
        assert result["error"] == "user_not_found"
