"""
Unit tests for the Dreams app.

Tests model creation, field defaults, auto-order, and progress tracking.
"""

import uuid

import pytest
from django.utils import timezone

from apps.dreams.models import (
    Dream,
    DreamMilestone,
    DreamProgressSnapshot,
    FocusSession,
    Goal,
    Task,
)


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
