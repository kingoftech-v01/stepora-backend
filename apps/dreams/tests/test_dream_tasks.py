"""
Tests for apps/dreams/tasks.py — Celery tasks.

Covers:
- generate_dream_plan_task (skeleton, partial, full plan generation)
- generate_dream_skeleton_task
- generate_initial_tasks_task
- generate_two_minute_start
- generate_vision_board
- cleanup_abandoned_dreams
- smart_archive_dreams
- update_dream_progress
- detect_obstacles
- auto_schedule_tasks
- check_overdue_tasks
- suggest_task_adjustments
- run_biweekly_checkins
- Helper functions: set_plan_status, get_plan_status, _parse_date, _check_milestone
"""

import json
import uuid
from datetime import timedelta
from unittest.mock import Mock, patch

import pytest
from django.utils import timezone

from apps.dreams.models import Dream, DreamMilestone, Goal, Obstacle, PlanCheckIn, Task
from apps.notifications.models import Notification
from apps.users.models import User


# ──────────────────────────────────────────────────────────────────────
#  Helpers: set_plan_status / get_plan_status / _parse_date
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestPlanStatusHelpers:
    """Tests for plan status Redis helpers."""

    def test_set_and_get_plan_status(self):
        from apps.dreams.tasks import get_plan_status, set_plan_status

        dream_id = str(uuid.uuid4())
        set_plan_status(dream_id, "generating", message="Test")

        status = get_plan_status(dream_id)
        assert status is not None
        assert status["status"] == "generating"
        assert status["message"] == "Test"

    def test_get_plan_status_returns_none_for_missing(self):
        from apps.dreams.tasks import get_plan_status

        assert get_plan_status(str(uuid.uuid4())) is None

    def test_set_plan_status_with_extra_data(self):
        from apps.dreams.tasks import get_plan_status, set_plan_status

        dream_id = str(uuid.uuid4())
        set_plan_status(dream_id, "completed", milestones=3, goals=5, tasks=10)

        status = get_plan_status(dream_id)
        assert status["status"] == "completed"
        assert status["milestones"] == 3
        assert status["goals"] == 5
        assert status["tasks"] == 10


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

        mock_task = Mock(
            title="Task 1", description="desc", order=1,
            duration_mins=30, day_number=1,
            expected_date=None, deadline_date=None,
        )
        mock_goal = Mock(
            title="Goal 1", description="desc", order=1,
            estimated_minutes=60, expected_date=None, deadline_date=None,
            tasks=[mock_task],
        )
        mock_obstacle = Mock(
            title="Obstacle 1", description="desc",
            solution="solution", goal_order=None,
        )
        mock_milestone = Mock(
            title="Milestone 1", description="desc", order=1,
            target_day=7, expected_date=None, deadline_date=None,
            goals=[mock_goal], obstacles=[mock_obstacle],
        )
        mock_plan_obstacle = Mock(
            title="Global Obstacle", description="desc",
            solution="sol", milestone_order=None, goal_order=None,
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
        from apps.dreams.tasks import generate_dream_plan_task

        result = generate_dream_plan_task(str(uuid.uuid4()), str(dream_user.id))
        assert result["status"] == "failed"
        assert result["error"] == "dream_not_found"

    @patch("core.ai_usage.AIUsageTracker")
    @patch("core.ai_validators.validate_plan_response")
    @patch("core.ai_validators.check_plan_calibration_coherence")
    @patch("apps.dreams.tasks.OpenAIService")
    def test_legacy_plan_without_milestones(
        self,
        mock_ai_cls,
        mock_coherence,
        mock_validate,
        mock_tracker_cls,
        dream_user,
    ):
        """generate_dream_plan_task handles legacy plans with goals only."""
        dream = Dream.objects.create(
            user=dream_user, title="Legacy", description="d", status="active",
        )

        mock_task = Mock(
            title="T", description="d", order=1,
            duration_mins=15, day_number=None,
            expected_date=None, deadline_date=None,
        )
        mock_goal = Mock(
            title="G", description="d", order=1,
            estimated_minutes=30, tasks=[mock_task],
            expected_date=None, deadline_date=None,
        )
        mock_plan_obs = Mock(
            title="Obs", description="d", solution="s",
            milestone_order=None, goal_order=None,
        )
        mock_plan = Mock(
            milestones=[],  # No milestones
            goals=[mock_goal],
            potential_obstacles=[mock_plan_obs],
        )
        mock_plan.model_dump.return_value = {"milestones": [], "goals": []}

        mock_ai = Mock()
        mock_ai.generate_plan.return_value = {}
        mock_ai_cls.return_value = mock_ai
        mock_validate.return_value = mock_plan
        mock_coherence.return_value = []
        mock_tracker_cls.return_value = Mock()

        from apps.dreams.tasks import generate_dream_plan_task

        result = generate_dream_plan_task(str(dream.id), str(dream_user.id))
        assert result["status"] == "completed"
        assert Goal.objects.filter(dream=dream).count() >= 1
        assert Task.objects.filter(goal__dream=dream).count() >= 1


# ──────────────────────────────────────────────────────────────────────
#  generate_dream_skeleton_task
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestGenerateDreamSkeletonTask:
    """Tests for generate_dream_skeleton_task (Phase 1)."""

    @patch("apps.dreams.tasks.generate_initial_tasks_task")
    @patch("core.ai_usage.AIUsageTracker")
    @patch("core.ai_validators.validate_skeleton_response")
    @patch("apps.dreams.tasks.OpenAIService")
    def test_creates_milestones_and_goals(
        self,
        mock_ai_cls,
        mock_validate,
        mock_tracker_cls,
        mock_chain_task,
        dream_user,
    ):
        """Skeleton task creates milestones and goals, then chains to task generation."""
        dream = Dream.objects.create(
            user=dream_user, title="Skeleton", description="test",
            status="active",
        )

        mock_goal_data = Mock(
            title="G1", description="d", order=1,
            estimated_minutes=60,
            expected_date=None, deadline_date=None,
        )
        mock_obs = Mock(title="Obs1", description="d", solution="s")
        mock_top_obs = Mock(title="TopObs", description="d", solution="s",
                            milestone_order=None, goal_order=None)
        mock_milestone = Mock(
            title="M1", description="d", order=1,
            target_day=7, expected_date=None, deadline_date=None,
            goals=[mock_goal_data], obstacles=[mock_obs],
        )
        mock_skeleton = Mock(
            milestones=[mock_milestone],
            potential_obstacles=[mock_top_obs],
        )
        mock_skeleton.model_dump.return_value = {"milestones": []}

        mock_ai = Mock()
        mock_ai.generate_skeleton.return_value = {}
        mock_ai_cls.return_value = mock_ai
        mock_validate.return_value = mock_skeleton
        mock_tracker_cls.return_value = Mock()

        from apps.dreams.tasks import generate_dream_skeleton_task

        result = generate_dream_skeleton_task(str(dream.id), str(dream_user.id))

        assert result["status"] == "skeleton_complete"
        assert result["milestones"] == 1
        assert DreamMilestone.objects.filter(dream=dream).count() == 1
        assert Goal.objects.filter(dream=dream).count() == 1
        assert Obstacle.objects.filter(dream=dream).count() >= 1
        mock_chain_task.apply_async.assert_called_once()

        dream.refresh_from_db()
        assert dream.plan_phase == "skeleton"

    def test_dream_not_found(self, dream_user):
        from apps.dreams.tasks import generate_dream_skeleton_task

        result = generate_dream_skeleton_task(str(uuid.uuid4()), str(dream_user.id))
        assert result["status"] == "failed"
        assert result["error"] == "dream_not_found"


# ──────────────────────────────────────────────────────────────────────
#  generate_initial_tasks_task
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestGenerateInitialTasksTask:
    """Tests for generate_initial_tasks_task (Phase 2)."""

    @patch("core.ai_validators.validate_task_patches")
    @patch("apps.dreams.tasks.OpenAIService")
    def test_creates_tasks_for_existing_skeleton(
        self, mock_ai_cls, mock_validate, dream_user,
    ):
        """Phase 2 creates tasks for the skeleton's milestones and goals."""
        dream = Dream.objects.create(
            user=dream_user, title="Tasks", description="test",
            status="active", plan_phase="skeleton",
            plan_skeleton={"milestones": [{"order": 1}]},
        )
        ms = DreamMilestone.objects.create(
            dream=dream, title="M1", order=1, has_tasks=False,
        )
        goal = Goal.objects.create(
            dream=dream, milestone=ms, title="G1", order=1,
        )

        mock_task_data = Mock(
            title="T1", description="d", order=1,
            duration_mins=30, day_number=None,
            expected_date=None, deadline_date=None,
        )
        mock_patch = Mock(
            milestone_order=1, goal_order=1,
            tasks=[mock_task_data],
        )
        mock_validate.return_value = [mock_patch]

        mock_ai = Mock()
        mock_ai.generate_tasks_for_months.return_value = []
        mock_ai_cls.return_value = mock_ai

        from apps.dreams.tasks import generate_initial_tasks_task

        result = generate_initial_tasks_task(str(dream.id), str(dream_user.id))
        assert result["status"] == "completed"
        assert result["tasks"] >= 1
        assert Task.objects.filter(goal=goal).count() >= 1

        ms.refresh_from_db()
        assert ms.has_tasks is True

        dream.refresh_from_db()
        assert dream.plan_phase in ("partial", "full")

    def test_skips_wrong_phase(self, dream_user):
        """Phase 2 skips dreams not in skeleton/partial phase."""
        dream = Dream.objects.create(
            user=dream_user, title="Wrong", description="d",
            status="active", plan_phase="full",
            plan_skeleton={"milestones": []},
        )

        from apps.dreams.tasks import generate_initial_tasks_task

        result = generate_initial_tasks_task(str(dream.id), str(dream_user.id))
        assert result["status"] == "skipped"

    def test_dream_not_found(self, dream_user):
        from apps.dreams.tasks import generate_initial_tasks_task

        result = generate_initial_tasks_task(str(uuid.uuid4()), str(dream_user.id))
        assert result["status"] == "failed"


# ──────────────────────────────────────────────────────────────────────
#  generate_two_minute_start
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestGenerateTwoMinuteStart:
    """Tests for generate_two_minute_start task."""

    @patch("apps.dreams.tasks.OpenAIService")
    def test_creates_micro_action(self, mock_ai_cls, dream_user):
        dream = Dream.objects.create(
            user=dream_user, title="Guitar", description="Beginner",
            status="active", has_two_minute_start=False,
        )

        mock_ai = Mock()
        mock_ai.generate_two_minute_start.return_value = "Watch a 2-min intro"
        mock_ai_cls.return_value = mock_ai

        from apps.dreams.tasks import generate_two_minute_start

        result = generate_two_minute_start(str(dream.id))
        assert result["created"] is True

        dream.refresh_from_db()
        assert dream.has_two_minute_start is True
        assert Task.objects.filter(goal__dream=dream).exists()

    @patch("apps.dreams.tasks.OpenAIService")
    def test_skips_if_already_has_two_minute_start(self, mock_ai_cls, dream_user):
        dream = Dream.objects.create(
            user=dream_user, title="G", description="d",
            status="active", has_two_minute_start=True,
        )

        from apps.dreams.tasks import generate_two_minute_start

        result = generate_two_minute_start(str(dream.id))
        assert result["created"] is False
        assert result["reason"] == "already_exists"

    def test_dream_not_found(self, db):
        from apps.dreams.tasks import generate_two_minute_start

        result = generate_two_minute_start(str(uuid.uuid4()))
        assert result["created"] is False
        assert result["error"] == "dream_not_found"


# ──────────────────────────────────────────────────────────────────────
#  generate_vision_board
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestGenerateVisionBoard:
    """Tests for generate_vision_board task."""

    @patch("apps.dreams.tasks.OpenAIService")
    def test_generates_vision_image(self, mock_ai_cls, dream_user):
        dream = Dream.objects.create(
            user=dream_user, title="Beach House", description="Own a beach house",
            status="active",
        )

        mock_ai = Mock()
        mock_ai.generate_vision_image.return_value = "https://img.example.com/vision.png"
        mock_ai_cls.return_value = mock_ai

        from apps.dreams.tasks import generate_vision_board

        result = generate_vision_board(str(dream.id))
        assert result["created"] is True
        assert result["url"] == "https://img.example.com/vision.png"

        dream.refresh_from_db()
        assert dream.vision_image_url == "https://img.example.com/vision.png"

        # Notification should be created
        assert Notification.objects.filter(
            user=dream_user, notification_type="vision_ready"
        ).exists()

    @patch("apps.dreams.tasks.OpenAIService")
    def test_skips_if_vision_exists(self, mock_ai_cls, dream_user):
        dream = Dream.objects.create(
            user=dream_user, title="D", description="d",
            status="active", vision_image_url="https://existing.com/img.png",
        )

        from apps.dreams.tasks import generate_vision_board

        result = generate_vision_board(str(dream.id))
        assert result["created"] is False
        assert result["reason"] == "already_exists"

    def test_dream_not_found(self, db):
        from apps.dreams.tasks import generate_vision_board

        result = generate_vision_board(str(uuid.uuid4()))
        assert result["created"] is False
        assert result["error"] == "dream_not_found"


# ──────────────────────────────────────────────────────────────────────
#  cleanup_abandoned_dreams
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestCleanupAbandonedDreams:
    """Tests for cleanup_abandoned_dreams task."""

    def test_archives_inactive_dreams(self, dream_user):
        dream = Dream.objects.create(
            user=dream_user, title="Old Dream", description="d",
            status="active",
        )
        # Set updated_at to 100 days ago
        Dream.objects.filter(id=dream.id).update(
            updated_at=timezone.now() - timedelta(days=100)
        )

        from apps.dreams.tasks import cleanup_abandoned_dreams

        result = cleanup_abandoned_dreams()
        assert result["archived"] >= 1

        dream.refresh_from_db()
        assert dream.status == "archived"

        assert Notification.objects.filter(
            user=dream_user, notification_type="dream_archived"
        ).exists()

    def test_keeps_recent_dreams(self, dream_user):
        Dream.objects.create(
            user=dream_user, title="Recent", description="d",
            status="active",
        )

        from apps.dreams.tasks import cleanup_abandoned_dreams

        result = cleanup_abandoned_dreams()
        assert result["archived"] == 0

    def test_ignores_non_active_dreams(self, dream_user):
        dream = Dream.objects.create(
            user=dream_user, title="Completed", description="d",
            status="completed",
        )
        Dream.objects.filter(id=dream.id).update(
            updated_at=timezone.now() - timedelta(days=100)
        )

        from apps.dreams.tasks import cleanup_abandoned_dreams

        result = cleanup_abandoned_dreams()
        assert result["archived"] == 0


# ──────────────────────────────────────────────────────────────────────
#  smart_archive_dreams
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestSmartArchiveDreams:
    """Tests for smart_archive_dreams task."""

    def test_pauses_inactive_dreams(self, dream_user):
        dream = Dream.objects.create(
            user=dream_user, title="Inactive", description="d",
            status="active",
        )
        Dream.objects.filter(id=dream.id).update(
            updated_at=timezone.now() - timedelta(days=35)
        )

        from apps.dreams.tasks import smart_archive_dreams

        result = smart_archive_dreams()
        assert result["paused"] >= 1

        dream.refresh_from_db()
        assert dream.status == "paused"

        assert Notification.objects.filter(
            user=dream_user, notification_type="dream_paused"
        ).exists()

    def test_skips_dreams_with_recent_task_activity(self, dream_user):
        dream = Dream.objects.create(
            user=dream_user, title="Active Tasks", description="d",
            status="active",
        )
        Dream.objects.filter(id=dream.id).update(
            updated_at=timezone.now() - timedelta(days=35)
        )
        goal = Goal.objects.create(dream=dream, title="G", order=1)
        Task.objects.create(
            goal=goal, title="T", order=1, status="completed",
            completed_at=timezone.now() - timedelta(days=5),
        )

        from apps.dreams.tasks import smart_archive_dreams

        result = smart_archive_dreams()
        assert result["paused"] == 0

    def test_keeps_recently_updated_dreams(self, dream_user):
        Dream.objects.create(
            user=dream_user, title="Recent", description="d",
            status="active",
        )

        from apps.dreams.tasks import smart_archive_dreams

        result = smart_archive_dreams()
        assert result["paused"] == 0


# ──────────────────────────────────────────────────────────────────────
#  update_dream_progress
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestUpdateDreamProgress:
    """Tests for update_dream_progress task."""

    def test_updates_progress(self, dream_user):
        dream = Dream.objects.create(
            user=dream_user, title="D", description="d", status="active"
        )
        goal = Goal.objects.create(dream=dream, title="G", order=1)
        Task.objects.create(
            goal=goal, title="T1", order=1, status="completed",
            completed_at=timezone.now(),
        )
        Task.objects.create(goal=goal, title="T2", order=2, status="pending")

        from apps.dreams.tasks import update_dream_progress

        result = update_dream_progress()
        assert result["updated"] >= 1

        dream.refresh_from_db()
        assert dream.progress_percentage == 50.0

    def test_completes_dream_at_100(self, dream_user):
        dream = Dream.objects.create(
            user=dream_user, title="Complete", description="d", status="active"
        )
        goal = Goal.objects.create(dream=dream, title="G", order=1)
        Task.objects.create(
            goal=goal, title="T1", order=1, status="completed",
            completed_at=timezone.now(),
        )

        from apps.dreams.tasks import update_dream_progress

        update_dream_progress()

        dream.refresh_from_db()
        assert dream.progress_percentage == 100.0
        assert dream.status == "completed"
        assert dream.completed_at is not None

        assert Notification.objects.filter(
            user=dream_user, notification_type="dream_completed"
        ).exists()

    def test_no_active_dreams(self, dream_user):
        from apps.dreams.tasks import update_dream_progress

        result = update_dream_progress()
        assert result["updated"] == 0

    def test_milestone_notification_at_50_percent(self, dream_user):
        """Crossing 50% sends a progress milestone notification."""
        dream = Dream.objects.create(
            user=dream_user, title="Half", description="d", status="active",
            progress_percentage=40.0,
        )
        goal = Goal.objects.create(dream=dream, title="G", order=1)
        # 3 of 4 tasks completed = 75% (crosses 50%)
        for i in range(3):
            Task.objects.create(
                goal=goal, title=f"T{i}", order=i, status="completed",
                completed_at=timezone.now(),
            )
        Task.objects.create(goal=goal, title="T3", order=3, status="pending")

        from apps.dreams.tasks import update_dream_progress

        update_dream_progress()

        # Should have progress notification
        assert Notification.objects.filter(
            user=dream_user, notification_type="progress"
        ).exists()


# ──────────────────────────────────────────────────────────────────────
#  detect_obstacles
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestDetectObstacles:
    """Tests for detect_obstacles task."""

    @patch("apps.dreams.tasks.OpenAIService")
    def test_creates_obstacles(self, mock_ai_cls, dream_user):
        dream = Dream.objects.create(
            user=dream_user, title="D", description="d", status="active"
        )

        mock_ai = Mock()
        mock_ai.predict_obstacles_simple.return_value = [
            {"title": "Time", "description": "Time issue", "solution": "Plan"},
        ]
        mock_ai_cls.return_value = mock_ai

        from apps.dreams.tasks import detect_obstacles

        result = detect_obstacles(str(dream.id))
        assert result["created"] == 1
        assert Obstacle.objects.filter(dream=dream).count() == 1

    def test_dream_not_found(self, db):
        from apps.dreams.tasks import detect_obstacles

        result = detect_obstacles(str(uuid.uuid4()))
        assert result["created"] == 0
        assert result["error"] == "dream_not_found"


# ──────────────────────────────────────────────────────────────────────
#  auto_schedule_tasks
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestAutoScheduleTasks:
    """Tests for auto_schedule_tasks task."""

    def test_schedules_unscheduled_tasks(self, dream_user):
        dream = Dream.objects.create(
            user=dream_user, title="D", description="d", status="active"
        )
        goal = Goal.objects.create(dream=dream, title="G", order=1)
        Task.objects.create(goal=goal, title="T1", order=1, status="pending", duration_mins=30)
        Task.objects.create(goal=goal, title="T2", order=2, status="pending", duration_mins=30)

        from apps.dreams.tasks import auto_schedule_tasks

        result = auto_schedule_tasks(str(dream_user.id))
        assert result["scheduled"] == 2

        for task in Task.objects.filter(goal=goal):
            assert task.scheduled_date is not None

    def test_no_unscheduled_tasks(self, dream_user):
        from apps.dreams.tasks import auto_schedule_tasks

        result = auto_schedule_tasks(str(dream_user.id))
        assert result["scheduled"] == 0

    def test_user_not_found(self, db):
        from apps.dreams.tasks import auto_schedule_tasks

        result = auto_schedule_tasks(str(uuid.uuid4()))
        assert result["scheduled"] == 0
        assert result["error"] == "user_not_found"


# ──────────────────────────────────────────────────────────────────────
#  check_overdue_tasks
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestCheckOverdueTasks:
    """Tests for check_overdue_tasks task."""

    def test_sends_overdue_notification(self, dream_user):
        dream = Dream.objects.create(
            user=dream_user, title="D", description="d", status="active"
        )
        goal = Goal.objects.create(dream=dream, title="G", order=1)
        yesterday = timezone.now() - timedelta(days=1)
        Task.objects.create(
            goal=goal, title="Overdue", order=1, status="pending",
            scheduled_date=yesterday,
        )

        from apps.dreams.tasks import check_overdue_tasks

        result = check_overdue_tasks()
        assert result["sent"] >= 1
        assert Notification.objects.filter(
            user=dream_user, notification_type="overdue_tasks"
        ).exists()

    def test_no_overdue_tasks(self, dream_user):
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
    def test_sends_suggestions_for_low_rate(self, mock_ai_cls, dream_user):
        dream = Dream.objects.create(
            user=dream_user, title="D", description="d", status="active"
        )
        goal = Goal.objects.create(dream=dream, title="G", order=1)

        for i in range(10):
            Task.objects.create(
                goal=goal, title=f"T{i}", order=i,
                status="completed" if i < 2 else "pending",
                completed_at=timezone.now() if i < 2 else None,
            )

        mock_ai = Mock()
        mock_ai.generate_task_adjustments.return_value = {
            "summary": "Break into smaller tasks",
            "detailed": ["Reduce duration"],
        }
        mock_ai_cls.return_value = mock_ai

        from apps.dreams.tasks import suggest_task_adjustments

        result = suggest_task_adjustments(str(dream_user.id))
        assert result["sent"] is True
        assert result["completion_rate"] == 20.0

    def test_skips_good_rate(self, dream_user):
        dream = Dream.objects.create(
            user=dream_user, title="D", description="d", status="active"
        )
        goal = Goal.objects.create(dream=dream, title="G", order=1)
        Task.objects.create(
            goal=goal, title="T1", order=1, status="completed",
            completed_at=timezone.now(),
        )

        from apps.dreams.tasks import suggest_task_adjustments

        result = suggest_task_adjustments(str(dream_user.id))
        assert result["sent"] is False
        assert result["completion_rate"] == 100.0

    def test_user_not_found(self, db):
        from apps.dreams.tasks import suggest_task_adjustments

        result = suggest_task_adjustments(str(uuid.uuid4()))
        assert result["sent"] is False
        assert result["error"] == "user_not_found"


# ──────────────────────────────────────────────────────────────────────
#  run_biweekly_checkins
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestRunBiweeklyCheckins:
    """Tests for run_biweekly_checkins task."""

    @patch("apps.dreams.tasks.generate_checkin_questionnaire_task")
    def test_dispatches_checkins_for_due_dreams(self, mock_task, dream_user):
        dream = Dream.objects.create(
            user=dream_user, title="Due", description="d",
            status="active", plan_phase="partial",
            next_checkin_at=timezone.now() - timedelta(hours=1),
        )

        from apps.dreams.tasks import run_biweekly_checkins

        result = run_biweekly_checkins()
        assert result["dispatched"] >= 1
        assert PlanCheckIn.objects.filter(dream=dream).exists()
        mock_task.apply_async.assert_called()

    @patch("apps.dreams.tasks.generate_checkin_questionnaire_task")
    def test_skips_dreams_with_active_checkin(self, mock_task, dream_user):
        dream = Dream.objects.create(
            user=dream_user, title="Active", description="d",
            status="active", plan_phase="partial",
            next_checkin_at=timezone.now() - timedelta(hours=1),
        )
        PlanCheckIn.objects.create(
            dream=dream, status="pending", scheduled_for=timezone.now(),
        )

        from apps.dreams.tasks import run_biweekly_checkins

        result = run_biweekly_checkins()
        assert result["dispatched"] == 0

    @patch("apps.dreams.tasks.generate_checkin_questionnaire_task")
    def test_skips_dreams_not_due(self, mock_task, dream_user):
        Dream.objects.create(
            user=dream_user, title="Future", description="d",
            status="active", plan_phase="partial",
            next_checkin_at=timezone.now() + timedelta(days=7),
        )

        from apps.dreams.tasks import run_biweekly_checkins

        result = run_biweekly_checkins()
        assert result["dispatched"] == 0


# ──────────────────────────────────────────────────────────────────────
#  _check_milestone helper
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestCheckMilestoneHelper:
    """Tests for the _check_milestone helper function."""

    def test_crossing_25_sends_notification(self, dream_user):
        from apps.dreams.tasks import _check_milestone

        dream = Dream.objects.create(
            user=dream_user, title="D", description="d", status="active",
        )

        _check_milestone(dream, 20.0, 30.0)

        assert Notification.objects.filter(
            user=dream_user, notification_type="progress"
        ).exists()

    def test_no_crossing_no_notification(self, dream_user):
        from apps.dreams.tasks import _check_milestone

        dream = Dream.objects.create(
            user=dream_user, title="D", description="d", status="active",
        )

        _check_milestone(dream, 30.0, 40.0)

        assert not Notification.objects.filter(
            user=dream_user, notification_type="progress"
        ).exists()
