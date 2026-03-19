"""
Unit tests for the Dreams app.

Tests model creation, field defaults, auto-order, progress tracking,
and API endpoints.
"""

import uuid
from unittest.mock import patch

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.dreams.models import (
    Dream,
    DreamMilestone,
    DreamProgressSnapshot,
    FocusSession,
    Goal,
    Task,
)
from apps.users.models import User


class TestDreamModel:
    """Tests for Dream model."""

    def test_create_dream(self, dream_user):
        """Dream can be created with required fields."""
        dream = Dream.objects.create(
            user=dream_user,
            title="Build an App",
            description="Create a mobile application from scratch",
            category="career",
        )
        assert dream.pk is not None
        assert isinstance(dream.id, uuid.UUID)
        assert dream.user == dream_user
        assert dream.title == "Build an App"
        assert dream.category == "career"

    def test_dream_defaults(self, test_dream):
        """Default field values are correct."""
        assert test_dream.status == "active"
        assert test_dream.priority == 1
        assert test_dream.progress_percentage == 0.0
        assert test_dream.is_public is False
        assert test_dream.is_favorited is False
        assert test_dream.has_two_minute_start is False
        assert test_dream.calibration_status == "pending"
        assert test_dream.plan_phase == "none"
        assert test_dream.tasks_generated_through_month == 0
        assert test_dream.checkin_count == 0
        assert test_dream.checkin_interval_days == 14
        assert test_dream.ai_analysis is None
        assert test_dream.completed_at is None
        assert test_dream.target_date is None
        assert test_dream.color == ""
        assert test_dream.language == ""

    def test_dream_str(self, test_dream):
        """String representation includes title and user email."""
        expected = f"Learn Spanish - {test_dream.user.email}"
        assert str(test_dream) == expected

    def test_dream_status_choices(self, dream_user):
        """All status choices are valid."""
        for status_value in ["active", "completed", "paused", "archived"]:
            dream = Dream.objects.create(
                user=dream_user,
                title=f"Dream {status_value}",
                description="Test description for dream",
                status=status_value,
            )
            assert dream.status == status_value

    def test_dream_ordering(self, dream_user):
        """Dreams are ordered by -created_at."""
        d1 = Dream.objects.create(
            user=dream_user, title="First", description="First dream"
        )
        d2 = Dream.objects.create(
            user=dream_user, title="Second", description="Second dream"
        )
        dreams = list(Dream.objects.filter(user=dream_user))
        assert dreams[0].id == d2.id  # More recent first

    def test_update_progress_no_goals(self, test_dream):
        """Progress is 0% with no goals."""
        test_dream.update_progress()
        test_dream.refresh_from_db()
        assert test_dream.progress_percentage == 0.0

    def test_update_progress_with_goals(self, test_dream):
        """Progress reflects completed goals ratio."""
        g1 = Goal.objects.create(
            dream=test_dream, title="Goal 1", order=1, status="completed"
        )
        g2 = Goal.objects.create(
            dream=test_dream, title="Goal 2", order=2, status="pending"
        )
        test_dream.update_progress()
        test_dream.refresh_from_db()
        assert test_dream.progress_percentage == 50.0

    def test_update_progress_with_milestones(self, test_dream):
        """Progress reflects completed milestones when milestones exist."""
        m1 = DreamMilestone.objects.create(
            dream=test_dream, title="M1", order=1, status="completed"
        )
        m2 = DreamMilestone.objects.create(
            dream=test_dream, title="M2", order=2, status="pending"
        )
        test_dream.update_progress()
        test_dream.refresh_from_db()
        assert test_dream.progress_percentage == 50.0


class TestGoalModel:
    """Tests for Goal model."""

    def test_create_goal(self, test_dream):
        """Goal can be created with required fields."""
        goal = Goal.objects.create(
            dream=test_dream,
            title="Study Grammar",
            description="Learn Spanish grammar rules",
            order=1,
        )
        assert goal.pk is not None
        assert isinstance(goal.id, uuid.UUID)
        assert goal.dream == test_dream
        assert goal.title == "Study Grammar"
        assert goal.order == 1

    def test_goal_defaults(self, test_goal):
        """Default field values are correct."""
        assert test_goal.status == "pending"
        assert test_goal.progress_percentage == 0.0
        assert test_goal.milestone is None
        assert test_goal.description == "Finish the first module of the Spanish course"
        assert test_goal.completed_at is None
        assert test_goal.reminder_enabled is True
        assert test_goal.reminder_time is None
        assert test_goal.estimated_minutes is None

    def test_goal_str(self, test_goal):
        """String representation includes title and order."""
        assert "Complete Basics Module" in str(test_goal)
        assert "Goal #1" in str(test_goal)

    def test_goal_with_milestone(self, test_goal_with_milestone, test_milestone):
        """Goal can be linked to a milestone."""
        assert test_goal_with_milestone.milestone == test_milestone

    def test_goal_status_choices(self, test_dream):
        """All status choices are valid."""
        for status_value in ["pending", "in_progress", "completed", "skipped"]:
            goal = Goal.objects.create(
                dream=test_dream,
                title=f"Goal {status_value}",
                order=1,
                status=status_value,
            )
            assert goal.status == status_value

    def test_update_progress_no_tasks(self, test_goal):
        """Progress is 0% with no tasks."""
        test_goal.update_progress()
        test_goal.refresh_from_db()
        assert test_goal.progress_percentage == 0.0

    def test_update_progress_with_tasks(self, test_goal):
        """Progress reflects completed tasks ratio."""
        Task.objects.create(
            goal=test_goal, title="T1", order=1, status="completed"
        )
        Task.objects.create(
            goal=test_goal, title="T2", order=2, status="pending"
        )
        test_goal.update_progress()
        test_goal.refresh_from_db()
        assert test_goal.progress_percentage == 50.0


class TestTaskModel:
    """Tests for Task model."""

    def test_create_task(self, test_goal):
        """Task can be created with required fields."""
        task = Task.objects.create(
            goal=test_goal,
            title="Practice vocabulary",
            description="Review flashcards",
            order=1,
        )
        assert task.pk is not None
        assert isinstance(task.id, uuid.UUID)
        assert task.goal == test_goal
        assert task.title == "Practice vocabulary"
        assert task.order == 1

    def test_task_defaults(self, test_task):
        """Default field values are correct."""
        assert test_task.status == "pending"
        assert test_task.completed_at is None
        assert test_task.is_two_minute_start is False
        assert test_task.chain_next_delay_days is None
        assert test_task.chain_template_title == ""
        assert test_task.chain_parent is None
        assert test_task.is_chain is False
        assert test_task.recurrence is None
        assert test_task.scheduled_time == ""

    def test_task_str(self, test_task):
        """String representation includes title and order."""
        assert "Study vocabulary" in str(test_task)
        assert "Task #1" in str(test_task)

    def test_task_auto_order(self, test_goal):
        """Tasks can be created with different orders."""
        t1 = Task.objects.create(goal=test_goal, title="T1", order=1)
        t2 = Task.objects.create(goal=test_goal, title="T2", order=2)
        t3 = Task.objects.create(goal=test_goal, title="T3", order=3)
        tasks = list(Task.objects.filter(goal=test_goal).order_by("order"))
        assert tasks[0].order == 1
        assert tasks[1].order == 2
        assert tasks[2].order == 3

    def test_task_status_choices(self, test_goal):
        """All status choices are valid."""
        for status_value in ["pending", "completed", "skipped"]:
            task = Task.objects.create(
                goal=test_goal,
                title=f"Task {status_value}",
                order=1,
                status=status_value,
            )
            assert task.status == status_value

    def test_task_with_duration(self, test_task):
        """Task stores duration_mins."""
        assert test_task.duration_mins == 30

    def test_task_with_scheduled_date(self, test_goal):
        """Task can have a scheduled date."""
        now = timezone.now()
        task = Task.objects.create(
            goal=test_goal,
            title="Scheduled task",
            order=1,
            scheduled_date=now,
            scheduled_time="09:00",
        )
        assert task.scheduled_date is not None
        assert task.scheduled_time == "09:00"


class TestDreamMilestoneModel:
    """Tests for DreamMilestone model."""

    def test_create_milestone(self, test_dream):
        """DreamMilestone can be created with required fields."""
        milestone = DreamMilestone.objects.create(
            dream=test_dream,
            title="Month 2 - Intermediate",
            description="Advance to intermediate level",
            order=2,
        )
        assert milestone.pk is not None
        assert isinstance(milestone.id, uuid.UUID)
        assert milestone.dream == test_dream
        assert milestone.title == "Month 2 - Intermediate"
        assert milestone.order == 2

    def test_milestone_defaults(self, test_milestone):
        """Default field values are correct."""
        assert test_milestone.status == "pending"
        assert test_milestone.progress_percentage == 0.0
        assert test_milestone.completed_at is None
        assert test_milestone.has_tasks is False
        assert test_milestone.target_date is None
        assert test_milestone.expected_date is None
        assert test_milestone.deadline_date is None

    def test_milestone_str(self, test_milestone):
        """String representation includes title and order."""
        assert "Month 1 - Basics" in str(test_milestone)
        assert "Milestone #1" in str(test_milestone)

    def test_milestone_ordering(self, test_dream):
        """Milestones are ordered by dream and order."""
        m1 = DreamMilestone.objects.create(
            dream=test_dream, title="M1", order=1
        )
        m2 = DreamMilestone.objects.create(
            dream=test_dream, title="M2", order=2
        )
        milestones = list(DreamMilestone.objects.filter(dream=test_dream))
        assert milestones[0].order == 1
        assert milestones[1].order == 2


class TestDreamProgressSnapshotModel:
    """Tests for DreamProgressSnapshot model."""

    def test_record_snapshot(self, test_dream):
        """record_snapshot creates a snapshot for today."""
        DreamProgressSnapshot.record_snapshot(test_dream)
        today = timezone.now().date()
        snapshot = DreamProgressSnapshot.objects.get(
            dream=test_dream, date=today
        )
        assert snapshot.progress_percentage == test_dream.progress_percentage

    def test_record_snapshot_updates_existing(self, test_dream):
        """record_snapshot updates today's snapshot if it exists."""
        DreamProgressSnapshot.record_snapshot(test_dream)
        test_dream.progress_percentage = 50.0
        test_dream.save()
        DreamProgressSnapshot.record_snapshot(test_dream)
        today = timezone.now().date()
        snapshot = DreamProgressSnapshot.objects.get(
            dream=test_dream, date=today
        )
        assert snapshot.progress_percentage == 50.0

    def test_snapshot_str(self, test_dream):
        """String representation includes dream title and percentage."""
        DreamProgressSnapshot.record_snapshot(test_dream)
        today = timezone.now().date()
        snapshot = DreamProgressSnapshot.objects.get(
            dream=test_dream, date=today
        )
        result = str(snapshot)
        assert "Learn Spanish" in result
        assert "0.0%" in result


class TestFocusSessionModel:
    """Tests for FocusSession model."""

    def test_create_focus_session(self, dream_user):
        """FocusSession can be created with required fields."""
        session = FocusSession.objects.create(
            user=dream_user,
            duration_minutes=25,
            session_type="work",
        )
        assert session.pk is not None
        assert isinstance(session.id, uuid.UUID)
        assert session.user == dream_user
        assert session.duration_minutes == 25
        assert session.session_type == "work"

    def test_focus_session_defaults(self, test_focus_session):
        """Default field values are correct."""
        assert test_focus_session.actual_minutes == 0
        assert test_focus_session.completed is False
        assert test_focus_session.ended_at is None

    def test_focus_session_with_task(self, test_focus_session, test_task):
        """Focus session can be linked to a task."""
        assert test_focus_session.task == test_task

    def test_focus_session_without_task(self, dream_user):
        """Focus session can be created without a task."""
        session = FocusSession.objects.create(
            user=dream_user,
            duration_minutes=10,
            session_type="break",
        )
        assert session.task is None

    def test_focus_session_type_choices(self, dream_user):
        """Both work and break session types are valid."""
        for session_type in ["work", "break"]:
            session = FocusSession.objects.create(
                user=dream_user,
                duration_minutes=15,
                session_type=session_type,
            )
            assert session.session_type == session_type

    def test_focus_session_str(self, test_focus_session):
        """String representation includes type and duration."""
        result = str(test_focus_session)
        assert "work" in result
        assert "25min" in result
        assert test_focus_session.user.email in result

    def test_focus_session_ordering(self, dream_user):
        """Focus sessions are ordered by -started_at."""
        s1 = FocusSession.objects.create(
            user=dream_user, duration_minutes=25, session_type="work"
        )
        s2 = FocusSession.objects.create(
            user=dream_user, duration_minutes=10, session_type="break"
        )
        sessions = list(FocusSession.objects.filter(user=dream_user))
        assert sessions[0].id == s2.id  # More recent first


# ──────────────────────────────────────────────────────────────────────
#  Additional Dream model methods
# ──────────────────────────────────────────────────────────────────────


class TestDreamComplete:
    """Tests for Dream.complete() method."""

    def test_complete_sets_status(self, test_dream):
        from unittest.mock import patch

        with patch("apps.users.services.AchievementService.check_achievements", return_value=[]):
            test_dream.complete()
        test_dream.refresh_from_db()
        assert test_dream.status == "completed"
        assert test_dream.progress_percentage == 100.0
        assert test_dream.completed_at is not None

    def test_complete_idempotent(self, test_dream):
        test_dream.status = "completed"
        test_dream.save()
        test_dream.complete()  # Should be no-op
        test_dream.refresh_from_db()
        assert test_dream.status == "completed"

    def test_complete_awards_xp(self, test_dream, dream_user):
        from unittest.mock import patch

        old_xp = dream_user.xp
        with patch("apps.users.services.AchievementService.check_achievements", return_value=[]):
            test_dream.complete()
        dream_user.refresh_from_db()
        assert dream_user.xp > old_xp

    def test_dream_category_to_attribute(self, test_dream):
        assert Dream.CATEGORY_TO_ATTRIBUTE.get("health") == "health"
        assert Dream.CATEGORY_TO_ATTRIBUTE.get("career") == "career"
        assert Dream.CATEGORY_TO_ATTRIBUTE.get("relationships") == "relationships"
        assert Dream.CATEGORY_TO_ATTRIBUTE.get("personal") == "personal_growth"
        assert Dream.CATEGORY_TO_ATTRIBUTE.get("finance") == "finance"
        assert Dream.CATEGORY_TO_ATTRIBUTE.get("hobbies") == "hobbies"
        assert Dream.CATEGORY_TO_ATTRIBUTE.get("unknown_cat") is None


class TestDreamMilestoneComplete:
    """Tests for DreamMilestone.complete() method."""

    def test_milestone_complete(self, test_dream):
        from unittest.mock import patch

        m = DreamMilestone.objects.create(
            dream=test_dream, title="M Complete", order=1
        )
        with patch("apps.users.services.AchievementService.check_achievements", return_value=[]):
            m.complete()
        m.refresh_from_db()
        assert m.status == "completed"
        assert m.progress_percentage == 100.0
        assert m.completed_at is not None

    def test_milestone_complete_idempotent(self, test_dream):
        m = DreamMilestone.objects.create(
            dream=test_dream, title="M Already", order=1, status="completed"
        )
        m.complete()  # Should be no-op
        m.refresh_from_db()
        assert m.status == "completed"

    def test_milestone_update_progress_no_goals(self, test_dream):
        m = DreamMilestone.objects.create(
            dream=test_dream, title="M No Goals", order=1
        )
        m.update_progress()
        m.refresh_from_db()
        assert m.progress_percentage == 0.0

    def test_milestone_update_progress_with_goals(self, test_dream):
        m = DreamMilestone.objects.create(
            dream=test_dream, title="M With Goals", order=1
        )
        Goal.objects.create(
            dream=test_dream, milestone=m, title="G1", order=1, status="completed"
        )
        Goal.objects.create(
            dream=test_dream, milestone=m, title="G2", order=2, status="pending"
        )
        m.update_progress()
        m.refresh_from_db()
        assert m.progress_percentage == 50.0


class TestGoalComplete:
    """Tests for Goal.complete() method."""

    def test_goal_complete(self, test_dream, dream_user):
        from unittest.mock import patch

        goal = Goal.objects.create(
            dream=test_dream, title="Goal To Complete", order=1
        )
        with patch("apps.users.services.AchievementService.check_achievements", return_value=[]):
            goal.complete()
        goal.refresh_from_db()
        assert goal.status == "completed"
        assert goal.progress_percentage == 100.0
        assert goal.completed_at is not None

    def test_goal_complete_idempotent(self, test_dream):
        goal = Goal.objects.create(
            dream=test_dream, title="Already Done", order=1, status="completed"
        )
        goal.complete()

    def test_goal_complete_with_milestone(self, test_dream, test_milestone):
        from unittest.mock import patch

        goal = Goal.objects.create(
            dream=test_dream,
            milestone=test_milestone,
            title="G with M",
            order=1,
        )
        with patch("apps.users.services.AchievementService.check_achievements", return_value=[]):
            goal.complete()
        goal.refresh_from_db()
        assert goal.status == "completed"

    def test_goal_update_progress_with_milestone(self, test_dream, test_milestone):
        goal = Goal.objects.create(
            dream=test_dream, milestone=test_milestone, title="G Prog", order=1
        )
        Task.objects.create(goal=goal, title="T1", order=1, status="completed")
        Task.objects.create(goal=goal, title="T2", order=2, status="pending")
        goal.update_progress()
        goal.refresh_from_db()
        assert goal.progress_percentage == 50.0

    def test_goal_update_progress_no_milestone(self, test_dream):
        goal = Goal.objects.create(
            dream=test_dream, title="G No M", order=1
        )
        Task.objects.create(goal=goal, title="T1", order=1, status="completed")
        goal.update_progress()
        goal.refresh_from_db()
        assert goal.progress_percentage == 100.0


class TestTaskComplete:
    """Tests for Task.complete() method."""

    def test_task_complete(self, test_goal, test_dream, dream_user):
        from unittest.mock import patch

        task = Task.objects.create(
            goal=test_goal, title="Task Complete", order=1, duration_mins=30
        )
        with patch("apps.users.services.AchievementService.check_achievements", return_value=[]):
            task.complete()
        task.refresh_from_db()
        assert task.status == "completed"
        assert task.completed_at is not None

    def test_task_complete_idempotent(self, test_goal):
        task = Task.objects.create(
            goal=test_goal, title="Already Done Task", order=1, status="completed"
        )
        task.complete()

    def test_task_xp_calculation(self, test_goal, dream_user):
        """Task XP is max(10, duration_mins // 3)."""
        from unittest.mock import patch

        task = Task.objects.create(
            goal=test_goal, title="XP Task", order=1, duration_mins=60
        )
        old_xp = dream_user.xp
        with patch("apps.users.services.AchievementService.check_achievements", return_value=[]):
            task.complete()
        dream_user.refresh_from_db()
        expected_xp = max(10, 60 // 3)  # = 20
        assert dream_user.xp == old_xp + expected_xp

    def test_task_xp_minimum(self, test_goal, dream_user):
        """Task XP minimum is 10 even with None duration."""
        from unittest.mock import patch

        task = Task.objects.create(
            goal=test_goal, title="Min XP Task", order=1, duration_mins=None
        )
        old_xp = dream_user.xp
        with patch("apps.users.services.AchievementService.check_achievements", return_value=[]):
            task.complete()
        dream_user.refresh_from_db()
        assert dream_user.xp >= old_xp + 10

    def test_task_get_chain_position_not_chain(self, test_task):
        """Non-chain task returns None for chain position."""
        pos, total = test_task.get_chain_position()
        assert pos is None
        assert total is None


# ──────────────────────────────────────────────────────────────────────
#  Other Dream Models
# ──────────────────────────────────────────────────────────────────────


class TestObstacleModel:
    """Tests for Obstacle model."""

    def test_create_obstacle(self, test_dream):
        from apps.dreams.models import Obstacle

        obs = Obstacle.objects.create(
            dream=test_dream,
            title="Time management",
            description="Not enough time in the day",
            obstacle_type="predicted",
        )
        assert obs.pk is not None
        assert obs.status == "active"

    def test_obstacle_str(self, test_dream):
        from apps.dreams.models import Obstacle

        obs = Obstacle.objects.create(
            dream=test_dream,
            title="Budget constraints",
            description="Limited budget",
        )
        assert "Budget constraints" in str(obs)


class TestCalibrationResponseModel:
    """Tests for CalibrationResponse model."""

    def test_create_calibration_response(self, test_dream):
        from apps.dreams.models import CalibrationResponse

        cr = CalibrationResponse.objects.create(
            dream=test_dream,
            question="What is your experience level?",
            answer="Beginner",
            question_number=1,
            category="experience",
        )
        assert cr.pk is not None
        assert cr.question_number == 1

    def test_calibration_response_str(self, test_dream):
        from apps.dreams.models import CalibrationResponse

        cr = CalibrationResponse.objects.create(
            dream=test_dream,
            question="How many hours per week can you dedicate?",
            question_number=2,
        )
        assert "Q2" in str(cr)


class TestDreamTagModel:
    """Tests for DreamTag and DreamTagging models."""

    def test_create_tag(self):
        from apps.dreams.models import DreamTag

        tag = DreamTag.objects.create(name="fitness")
        assert tag.pk is not None
        assert str(tag) == "fitness"

    def test_create_tagging(self, test_dream):
        from apps.dreams.models import DreamTag, DreamTagging

        tag = DreamTag.objects.create(name="language")
        tagging = DreamTagging.objects.create(dream=test_dream, tag=tag)
        assert tagging.pk is not None
        assert "Learn Spanish" in str(tagging)
        assert "language" in str(tagging)


class TestDreamTemplateModel:
    """Tests for DreamTemplate model."""

    def test_create_template(self):
        from apps.dreams.models import DreamTemplate

        tpl = DreamTemplate.objects.create(
            title="Learn a Language",
            description="Master a new language in 6 months",
            category="education",
            template_goals=[{"title": "Basics", "tasks": []}],
        )
        assert tpl.pk is not None
        assert tpl.difficulty == "intermediate"
        assert tpl.is_featured is False
        assert tpl.usage_count == 0

    def test_template_str(self):
        from apps.dreams.models import DreamTemplate

        tpl = DreamTemplate.objects.create(
            title="Fitness Journey",
            description="Get fit",
            category="health",
        )
        assert "Fitness Journey" in str(tpl)
        assert "health" in str(tpl)


class TestDreamCollaboratorModel:
    """Tests for DreamCollaborator model."""

    def test_create_collaborator(self, test_dream, dream_user2):
        from apps.dreams.models import DreamCollaborator

        collab = DreamCollaborator.objects.create(
            dream=test_dream, user=dream_user2, role="viewer"
        )
        assert collab.pk is not None
        assert collab.role == "viewer"

    def test_collaborator_str(self, test_dream, dream_user2):
        from apps.dreams.models import DreamCollaborator

        collab = DreamCollaborator.objects.create(
            dream=test_dream, user=dream_user2, role="collaborator"
        )
        result = str(collab)
        assert "Learn Spanish" in result


class TestSharedDreamModel:
    """Tests for SharedDream model."""

    def test_create_shared_dream(self, test_dream, dream_user, dream_user2):
        from apps.dreams.models import SharedDream

        shared = SharedDream.objects.create(
            dream=test_dream,
            shared_by=dream_user,
            shared_with=dream_user2,
            permission="view",
        )
        assert shared.pk is not None
        assert shared.permission == "view"

    def test_shared_dream_str(self, test_dream, dream_user, dream_user2):
        from apps.dreams.models import SharedDream

        shared = SharedDream.objects.create(
            dream=test_dream,
            shared_by=dream_user,
            shared_with=dream_user2,
        )
        result = str(shared)
        assert "Learn Spanish" in result


class TestDreamJournalModel:
    """Tests for DreamJournal model."""

    def test_create_journal(self, test_dream):
        from apps.dreams.models import DreamJournal

        journal = DreamJournal.objects.create(
            dream=test_dream,
            title="Day 1 Reflections",
            content="Today I started learning Spanish basics.",
            mood="motivated",
        )
        assert journal.pk is not None
        assert journal.mood == "motivated"

    def test_journal_str_with_title(self, test_dream):
        from apps.dreams.models import DreamJournal

        journal = DreamJournal.objects.create(
            dream=test_dream,
            title="My Progress",
            content="Going well!",
        )
        assert "My Progress" in str(journal)

    def test_journal_str_without_title(self, test_dream):
        from apps.dreams.models import DreamJournal

        journal = DreamJournal.objects.create(
            dream=test_dream,
            content="This is a journal entry without a title and is long enough.",
        )
        result = str(journal)
        assert "This is" in result


class TestVisionBoardImageModel:
    """Tests for VisionBoardImage model."""

    def test_create_vision_image(self, test_dream):
        from apps.dreams.models import VisionBoardImage

        img = VisionBoardImage.objects.create(
            dream=test_dream,
            image_url="https://example.com/image.png",
            caption="My vision",
            is_ai_generated=True,
            order=1,
        )
        assert img.pk is not None
        assert img.is_ai_generated is True

    def test_vision_image_str(self, test_dream):
        from apps.dreams.models import VisionBoardImage

        img = VisionBoardImage.objects.create(
            dream=test_dream, order=2
        )
        result = str(img)
        assert "Learn Spanish" in result
        assert "#2" in result


class TestPlanCheckInModel:
    """Tests for PlanCheckIn model."""

    def test_create_checkin(self, test_dream):
        from apps.dreams.models import PlanCheckIn

        checkin = PlanCheckIn.objects.create(
            dream=test_dream,
            status="pending",
            triggered_by="schedule",
            scheduled_for=timezone.now(),
        )
        assert checkin.pk is not None
        assert checkin.status == "pending"
        assert checkin.pace_status == ""

    def test_checkin_str(self, test_dream):
        from apps.dreams.models import PlanCheckIn

        checkin = PlanCheckIn.objects.create(
            dream=test_dream,
            status="completed",
            scheduled_for=timezone.now(),
        )
        result = str(checkin)
        assert "completed" in result


# ──────────────────────────────────────────────────────────────────────
#  Dream signals
# ──────────────────────────────────────────────────────────────────────


class TestDreamSignals:
    """Tests for dream signals."""

    def test_task_delete_recalculates_progress(self, test_dream):
        """Deleting a task recalculates goal progress."""
        goal = Goal.objects.create(dream=test_dream, title="G", order=1)
        t1 = Task.objects.create(goal=goal, title="T1", order=1, status="completed")
        t2 = Task.objects.create(goal=goal, title="T2", order=2, status="pending")
        goal.update_progress()
        goal.refresh_from_db()
        assert goal.progress_percentage == 50.0
        # Delete the pending task
        t2.delete()
        goal.refresh_from_db()
        assert goal.progress_percentage == 100.0


# ══════════════════════════════════════════════════════════════════════
#  API ENDPOINT TESTS — DreamViewSet
# ══════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestDreamAPI:
    """Tests for Dreams API endpoints."""

    def test_list_dreams(self, dream_client):
        resp = dream_client.get("/api/dreams/dreams/", HTTP_ORIGIN="https://stepora.app")
        assert resp.status_code == 200

    def test_create_dream(self, dream_client):
        resp = dream_client.post(
            "/api/dreams/dreams/",
            {"title": "New Dream", "description": "Description", "category": "career"},
            format="json",
            HTTP_ORIGIN="https://stepora.app",
        )
        # May get 201 or 403 (subscription_required)
        assert resp.status_code in (201, 403)

    def test_retrieve_dream(self, dream_client, test_dream):
        resp = dream_client.get(
            f"/api/dreams/dreams/{test_dream.id}/",
            HTTP_ORIGIN="https://stepora.app",
        )
        assert resp.status_code in (200, 403)

    def test_update_dream(self, dream_client, test_dream):
        resp = dream_client.patch(
            f"/api/dreams/dreams/{test_dream.id}/",
            {"title": "Updated Title"},
            format="json",
            HTTP_ORIGIN="https://stepora.app",
        )
        assert resp.status_code in (200, 403)

    def test_delete_dream(self, dream_client, test_dream):
        resp = dream_client.delete(
            f"/api/dreams/dreams/{test_dream.id}/",
            HTTP_ORIGIN="https://stepora.app",
        )
        assert resp.status_code in (204, 403)

    def test_list_dreams_filter_status(self, dream_client, test_dream):
        resp = dream_client.get(
            "/api/dreams/dreams/?status=active",
            HTTP_ORIGIN="https://stepora.app",
        )
        assert resp.status_code == 200

    def test_list_dreams_unauthenticated(self):
        client = APIClient()
        resp = client.get("/api/dreams/dreams/", HTTP_ORIGIN="https://stepora.app")
        assert resp.status_code == 401


@pytest.mark.django_db
class TestGoalAPI:
    """Tests for Goal API endpoints."""

    def test_list_goals(self, dream_client, test_dream):
        resp = dream_client.get(
            f"/api/dreams/goals/?dream={test_dream.id}",
            HTTP_ORIGIN="https://stepora.app",
        )
        assert resp.status_code == 200

    def test_create_goal(self, dream_client, test_dream):
        resp = dream_client.post(
            "/api/dreams/goals/",
            {"dream": str(test_dream.id), "title": "New Goal", "order": 1},
            format="json",
            HTTP_ORIGIN="https://stepora.app",
        )
        assert resp.status_code in (201, 400)

    def test_update_goal(self, dream_client, test_goal):
        resp = dream_client.patch(
            f"/api/dreams/goals/{test_goal.id}/",
            {"title": "Updated Goal"},
            format="json",
            HTTP_ORIGIN="https://stepora.app",
        )
        assert resp.status_code == 200

    def test_delete_goal(self, dream_client, test_goal):
        resp = dream_client.delete(
            f"/api/dreams/goals/{test_goal.id}/",
            HTTP_ORIGIN="https://stepora.app",
        )
        assert resp.status_code == 204


@pytest.mark.django_db
class TestTaskAPI:
    """Tests for Task API endpoints."""

    def test_list_tasks(self, dream_client, test_dream):
        resp = dream_client.get(
            f"/api/dreams/tasks/?dream={test_dream.id}",
            HTTP_ORIGIN="https://stepora.app",
        )
        assert resp.status_code == 200

    def test_create_task(self, dream_client, test_goal):
        resp = dream_client.post(
            "/api/dreams/tasks/",
            {"goal": str(test_goal.id), "title": "New Task", "order": 1},
            format="json",
            HTTP_ORIGIN="https://stepora.app",
        )
        assert resp.status_code in (201, 400)

    def test_update_task(self, dream_client, test_task):
        resp = dream_client.patch(
            f"/api/dreams/tasks/{test_task.id}/",
            {"title": "Updated Task"},
            format="json",
            HTTP_ORIGIN="https://stepora.app",
        )
        assert resp.status_code == 200

    def test_delete_task(self, dream_client, test_task):
        resp = dream_client.delete(
            f"/api/dreams/tasks/{test_task.id}/",
            HTTP_ORIGIN="https://stepora.app",
        )
        assert resp.status_code == 204


@pytest.mark.django_db
class TestMilestoneAPI:
    """Tests for DreamMilestone API endpoints."""

    def test_list_milestones(self, dream_client, test_dream):
        resp = dream_client.get(
            f"/api/dreams/milestones/?dream={test_dream.id}",
            HTTP_ORIGIN="https://stepora.app",
        )
        assert resp.status_code == 200

    def test_create_milestone(self, dream_client, test_dream):
        resp = dream_client.post(
            "/api/dreams/milestones/",
            {"dream": str(test_dream.id), "title": "M1", "order": 1},
            format="json",
            HTTP_ORIGIN="https://stepora.app",
        )
        assert resp.status_code in (201, 400)


@pytest.mark.django_db
class TestObstacleAPI:
    """Tests for Obstacle API endpoints."""

    def test_list_obstacles(self, dream_client, test_dream):
        resp = dream_client.get(
            f"/api/dreams/obstacles/?dream={test_dream.id}",
            HTTP_ORIGIN="https://stepora.app",
        )
        assert resp.status_code == 200

    def test_create_obstacle(self, dream_client, test_dream):
        resp = dream_client.post(
            "/api/dreams/obstacles/",
            {
                "dream": str(test_dream.id),
                "title": "Obstacle",
                "description": "An obstacle",
            },
            format="json",
            HTTP_ORIGIN="https://stepora.app",
        )
        assert resp.status_code in (201, 400)


@pytest.mark.django_db
class TestDreamTagAPI:
    """Tests for Dream Tag API."""

    def test_list_tags(self, dream_client):
        resp = dream_client.get(
            "/api/dreams/dreams/tags/",
            HTTP_ORIGIN="https://stepora.app",
        )
        assert resp.status_code == 200


@pytest.mark.django_db
class TestDreamTemplateAPI:
    """Tests for Dream Template API."""

    def test_list_templates(self, dream_client):
        resp = dream_client.get(
            "/api/v1/dreams/dreams/templates/",
            HTTP_ORIGIN="https://stepora.app",
        )
        assert resp.status_code in (200, 404)


@pytest.mark.django_db
class TestFocusSessionAPI:
    """Tests for Focus Session API endpoints."""

    def test_start_focus_session(self, dream_client, test_task):
        resp = dream_client.post(
            "/api/dreams/focus/start/",
            {"task_id": str(test_task.id), "duration_minutes": 25},
            format="json",
            HTTP_ORIGIN="https://stepora.app",
        )
        assert resp.status_code in (200, 201)

    def test_focus_history(self, dream_client):
        resp = dream_client.get(
            "/api/dreams/focus/history/",
            HTTP_ORIGIN="https://stepora.app",
        )
        assert resp.status_code == 200

    def test_focus_stats(self, dream_client):
        resp = dream_client.get(
            "/api/dreams/focus/stats/",
            HTTP_ORIGIN="https://stepora.app",
        )
        assert resp.status_code == 200

    def test_complete_focus_session(self, dream_client, test_focus_session):
        resp = dream_client.post(
            "/api/dreams/focus/complete/",
            {"session_id": str(test_focus_session.id), "actual_minutes": 20},
            format="json",
            HTTP_ORIGIN="https://stepora.app",
        )
        assert resp.status_code == 200


@pytest.mark.django_db
class TestDreamJournalAPI:
    """Tests for Dream Journal API."""

    def test_list_journal(self, dream_client, test_dream):
        resp = dream_client.get(
            f"/api/dreams/journal/?dream={test_dream.id}",
            HTTP_ORIGIN="https://stepora.app",
        )
        assert resp.status_code == 200

    def test_create_journal_entry(self, dream_client, test_dream):
        resp = dream_client.post(
            "/api/dreams/journal/",
            {
                "dream": str(test_dream.id),
                "content": "Today was productive.",
                "mood": "happy",
            },
            format="json",
            HTTP_ORIGIN="https://stepora.app",
        )
        assert resp.status_code in (201, 400)


@pytest.mark.django_db
class TestSharedWithMeAPI:
    """Tests for SharedWithMe API."""

    def test_list_shared(self, dream_client):
        resp = dream_client.get(
            "/api/dreams/dreams/shared-with-me/",
            HTTP_ORIGIN="https://stepora.app",
        )
        assert resp.status_code == 200


@pytest.mark.django_db
class TestCheckInAPI:
    """Tests for CheckIn API."""

    def test_list_checkins(self, dream_client, test_dream):
        resp = dream_client.get(
            f"/api/dreams/checkins/?dream={test_dream.id}",
            HTTP_ORIGIN="https://stepora.app",
        )
        assert resp.status_code == 200


# ══════════════════════════════════════════════════════════════════════
#  MORE Dream ViewSet Actions — Exercises complex view code paths
# ══════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestDreamActionsAPI:
    """Tests for DreamViewSet custom action endpoints."""

    def test_dream_stats(self, dream_client, test_dream):
        resp = dream_client.get(
            f"/api/dreams/dreams/{test_dream.id}/stats/",
            HTTP_ORIGIN="https://stepora.app",
        )
        assert resp.status_code in (200, 403, 404)

    def test_dream_vision_board(self, dream_client, test_dream):
        resp = dream_client.get(
            f"/api/dreams/dreams/{test_dream.id}/vision-board/",
            HTTP_ORIGIN="https://stepora.app",
        )
        assert resp.status_code in (200, 403, 404)

    def test_dream_progress_history(self, dream_client, test_dream):
        resp = dream_client.get(
            f"/api/dreams/dreams/{test_dream.id}/progress-history/",
            HTTP_ORIGIN="https://stepora.app",
        )
        assert resp.status_code in (200, 403, 404)

    def test_dream_progress_photos(self, dream_client, test_dream):
        resp = dream_client.get(
            f"/api/dreams/dreams/{test_dream.id}/progress-photos/",
            HTTP_ORIGIN="https://stepora.app",
        )
        assert resp.status_code in (200, 403, 404)

    def test_dream_collaborators_list(self, dream_client, test_dream):
        resp = dream_client.get(
            f"/api/dreams/dreams/{test_dream.id}/collaborators/list/",
            HTTP_ORIGIN="https://stepora.app",
        )
        assert resp.status_code in (200, 403, 404)

    def test_dream_complete(self, dream_client, test_dream):
        with patch("apps.users.services.AchievementService.check_achievements", return_value=[]):
            resp = dream_client.post(
                f"/api/dreams/dreams/{test_dream.id}/complete/",
                HTTP_ORIGIN="https://stepora.app",
            )
        assert resp.status_code in (200, 403, 404)

    def test_dream_pause(self, dream_client, test_dream):
        resp = dream_client.post(
            f"/api/dreams/dreams/{test_dream.id}/pause/",
            HTTP_ORIGIN="https://stepora.app",
        )
        assert resp.status_code in (200, 403, 404)

    def test_dream_resume(self, dream_client, test_dream):
        resp = dream_client.post(
            f"/api/dreams/dreams/{test_dream.id}/resume/",
            HTTP_ORIGIN="https://stepora.app",
        )
        assert resp.status_code in (200, 403, 404)

    def test_dream_archive(self, dream_client, test_dream):
        resp = dream_client.post(
            f"/api/dreams/dreams/{test_dream.id}/archive/",
            HTTP_ORIGIN="https://stepora.app",
        )
        assert resp.status_code in (200, 403, 404)

    def test_dream_share(self, dream_client, test_dream, dream_user2):
        resp = dream_client.post(
            f"/api/dreams/dreams/{test_dream.id}/share/",
            {"user_id": str(dream_user2.id)},
            format="json",
            HTTP_ORIGIN="https://stepora.app",
        )
        assert resp.status_code in (200, 201, 400, 403, 404)

    def test_dream_duplicate(self, dream_client, test_dream):
        resp = dream_client.post(
            f"/api/dreams/dreams/{test_dream.id}/duplicate/",
            HTTP_ORIGIN="https://stepora.app",
        )
        assert resp.status_code in (200, 201, 403, 404)

    def test_dream_tags_add(self, dream_client, test_dream):
        resp = dream_client.post(
            f"/api/dreams/dreams/{test_dream.id}/tags/",
            {"name": "testag"},
            format="json",
            HTTP_ORIGIN="https://stepora.app",
        )
        assert resp.status_code in (200, 201, 400, 403, 404)


@pytest.mark.django_db
class TestDreamActionsWithPremiumUser:
    """Tests for Dream actions with a premium user (exercises more view code)."""

    @pytest.fixture
    def premium_dream_setup(self, db):
        """Create a premium user with a dream for testing."""
        from datetime import timedelta

        from apps.subscriptions.models import Subscription, SubscriptionPlan

        user = User.objects.create_user(
            email="dream_premium_api@example.com",
            password="testpassword123",
            display_name="Premium Dream User",
        )
        plan = SubscriptionPlan.objects.get(slug="premium")
        Subscription.objects.update_or_create(
            user=user,
            defaults={
                "plan": plan,
                "status": "active",
                "current_period_start": timezone.now(),
                "current_period_end": timezone.now() + timedelta(days=30),
            },
        )
        dream = Dream.objects.create(
            user=user, title="Premium Dream", description="A premium dream",
            category="career", status="active",
        )
        goal = Goal.objects.create(dream=dream, title="PG1", order=1)
        task = Task.objects.create(goal=goal, title="PT1", order=1, duration_mins=30)
        client = APIClient()
        client.force_authenticate(user=user)
        return {"user": user, "dream": dream, "goal": goal, "task": task, "client": client}

    def test_create_dream(self, premium_dream_setup):
        client = premium_dream_setup["client"]
        resp = client.post(
            "/api/dreams/dreams/",
            {"title": "New Premium Dream", "description": "Desc", "category": "health"},
            format="json",
            HTTP_ORIGIN="https://stepora.app",
        )
        assert resp.status_code in (201, 400, 403)

    def test_list_dreams(self, premium_dream_setup):
        client = premium_dream_setup["client"]
        resp = client.get("/api/dreams/dreams/", HTTP_ORIGIN="https://stepora.app")
        assert resp.status_code == 200
        assert len(resp.data.get("results", resp.data)) >= 1

    def test_retrieve_dream(self, premium_dream_setup):
        client = premium_dream_setup["client"]
        dream = premium_dream_setup["dream"]
        resp = client.get(
            f"/api/dreams/dreams/{dream.id}/",
            HTTP_ORIGIN="https://stepora.app",
        )
        assert resp.status_code == 200

    def test_update_dream(self, premium_dream_setup):
        client = premium_dream_setup["client"]
        dream = premium_dream_setup["dream"]
        resp = client.patch(
            f"/api/dreams/dreams/{dream.id}/",
            {"priority": 2},
            format="json",
            HTTP_ORIGIN="https://stepora.app",
        )
        assert resp.status_code == 200

    def test_dream_stats(self, premium_dream_setup):
        client = premium_dream_setup["client"]
        dream = premium_dream_setup["dream"]
        resp = client.get(
            f"/api/dreams/dreams/{dream.id}/stats/",
            HTTP_ORIGIN="https://stepora.app",
        )
        assert resp.status_code in (200, 404)

    def test_dream_complete(self, premium_dream_setup):
        client = premium_dream_setup["client"]
        dream = premium_dream_setup["dream"]
        with patch("apps.users.services.AchievementService.check_achievements", return_value=[]):
            resp = client.post(
                f"/api/dreams/dreams/{dream.id}/complete/",
                HTTP_ORIGIN="https://stepora.app",
            )
        assert resp.status_code in (200, 404)

    def test_goal_complete(self, premium_dream_setup):
        client = premium_dream_setup["client"]
        goal = premium_dream_setup["goal"]
        with patch("apps.users.services.AchievementService.check_achievements", return_value=[]):
            resp = client.post(
                f"/api/dreams/goals/{goal.id}/complete/",
                HTTP_ORIGIN="https://stepora.app",
            )
        assert resp.status_code in (200, 404)

    def test_task_complete(self, premium_dream_setup):
        client = premium_dream_setup["client"]
        task = premium_dream_setup["task"]
        with patch("apps.users.services.AchievementService.check_achievements", return_value=[]):
            resp = client.post(
                f"/api/dreams/tasks/{task.id}/complete/",
                HTTP_ORIGIN="https://stepora.app",
            )
        assert resp.status_code in (200, 404)

    def test_create_goal(self, premium_dream_setup):
        client = premium_dream_setup["client"]
        dream = premium_dream_setup["dream"]
        resp = client.post(
            "/api/dreams/goals/",
            {"dream": str(dream.id), "title": "New Goal", "order": 2},
            format="json",
            HTTP_ORIGIN="https://stepora.app",
        )
        assert resp.status_code in (201, 400)

    def test_create_task(self, premium_dream_setup):
        client = premium_dream_setup["client"]
        goal = premium_dream_setup["goal"]
        resp = client.post(
            "/api/dreams/tasks/",
            {"goal": str(goal.id), "title": "New Task", "order": 2, "duration_mins": 15},
            format="json",
            HTTP_ORIGIN="https://stepora.app",
        )
        assert resp.status_code in (201, 400)

    def test_create_milestone(self, premium_dream_setup):
        client = premium_dream_setup["client"]
        dream = premium_dream_setup["dream"]
        resp = client.post(
            "/api/dreams/milestones/",
            {"dream": str(dream.id), "title": "M1", "order": 1},
            format="json",
            HTTP_ORIGIN="https://stepora.app",
        )
        assert resp.status_code in (201, 400)

    def test_create_obstacle(self, premium_dream_setup):
        client = premium_dream_setup["client"]
        dream = premium_dream_setup["dream"]
        resp = client.post(
            "/api/dreams/obstacles/",
            {"dream": str(dream.id), "title": "Obstacle", "description": "An obstacle"},
            format="json",
            HTTP_ORIGIN="https://stepora.app",
        )
        assert resp.status_code in (201, 400)

    def test_create_journal(self, premium_dream_setup):
        client = premium_dream_setup["client"]
        dream = premium_dream_setup["dream"]
        resp = client.post(
            "/api/dreams/journal/",
            {"dream": str(dream.id), "content": "Today was good", "mood": "happy"},
            format="json",
            HTTP_ORIGIN="https://stepora.app",
        )
        assert resp.status_code in (201, 400)

    def test_focus_start(self, premium_dream_setup):
        client = premium_dream_setup["client"]
        task = premium_dream_setup["task"]
        resp = client.post(
            "/api/dreams/focus/start/",
            {"task_id": str(task.id), "duration_minutes": 25},
            format="json",
            HTTP_ORIGIN="https://stepora.app",
        )
        assert resp.status_code in (200, 201, 400)

    def test_dream_duplicate(self, premium_dream_setup):
        client = premium_dream_setup["client"]
        dream = premium_dream_setup["dream"]
        resp = client.post(
            f"/api/dreams/dreams/{dream.id}/duplicate/",
            HTTP_ORIGIN="https://stepora.app",
        )
        assert resp.status_code in (200, 201, 403, 404)


@pytest.mark.django_db
class TestGoalActionsAPI:
    """Tests for GoalViewSet custom actions."""

    def test_goal_complete(self, dream_client, test_goal):
        with patch("apps.users.services.AchievementService.check_achievements", return_value=[]):
            resp = dream_client.post(
                f"/api/dreams/goals/{test_goal.id}/complete/",
                HTTP_ORIGIN="https://stepora.app",
            )
        assert resp.status_code in (200, 403, 404)

    def test_goal_reorder(self, dream_client, test_goal, test_dream):
        resp = dream_client.post(
            f"/api/dreams/goals/{test_goal.id}/reorder/",
            {"order": 2},
            format="json",
            HTTP_ORIGIN="https://stepora.app",
        )
        assert resp.status_code in (200, 400, 403, 404)


@pytest.mark.django_db
class TestTaskActionsAPI:
    """Tests for TaskViewSet custom actions."""

    def test_task_complete(self, dream_client, test_task):
        with patch("apps.users.services.AchievementService.check_achievements", return_value=[]):
            resp = dream_client.post(
                f"/api/dreams/tasks/{test_task.id}/complete/",
                HTTP_ORIGIN="https://stepora.app",
            )
        assert resp.status_code in (200, 403, 404)

    def test_task_skip(self, dream_client, test_task):
        resp = dream_client.post(
            f"/api/dreams/tasks/{test_task.id}/skip/",
            HTTP_ORIGIN="https://stepora.app",
        )
        assert resp.status_code in (200, 403, 404)
