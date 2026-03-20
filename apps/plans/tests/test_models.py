"""
Tests for plans models.
"""

import pytest
from django.utils import timezone

from apps.plans.models import (
    CalibrationResponse,
    DreamMilestone,
    DreamProgressSnapshot,
    FocusSession,
    Goal,
    Obstacle,
    PlanCheckIn,
    Task,
)


@pytest.mark.django_db
class TestDreamMilestone:
    def test_create(self, plans_dream):
        ms = DreamMilestone.objects.create(
            dream=plans_dream, title="Milestone 1", order=1
        )
        assert ms.status == "pending"
        assert ms.progress_percentage == 0.0

    def test_complete(self, plans_milestone):
        plans_milestone.complete()
        plans_milestone.refresh_from_db()
        assert plans_milestone.status == "completed"
        assert plans_milestone.completed_at is not None


@pytest.mark.django_db
class TestGoal:
    def test_create(self, plans_dream, plans_milestone):
        goal = Goal.objects.create(
            dream=plans_dream,
            milestone=plans_milestone,
            title="Goal 1",
            order=1,
        )
        assert goal.status == "pending"

    def test_complete(self, plans_goal):
        plans_goal.complete()
        plans_goal.refresh_from_db()
        assert plans_goal.status == "completed"


@pytest.mark.django_db
class TestTask:
    def test_create(self, plans_goal):
        task = Task.objects.create(
            goal=plans_goal, title="Task 1", order=1, duration_mins=15
        )
        assert task.status == "pending"

    def test_complete(self, plans_task):
        plans_task.complete()
        plans_task.refresh_from_db()
        assert plans_task.status == "completed"
        assert plans_task.completed_at is not None

    def test_chain_position_no_chain(self, plans_task):
        pos, total = plans_task.get_chain_position()
        assert pos is None
        assert total is None


@pytest.mark.django_db
class TestObstacle:
    def test_create(self, plans_dream):
        obs = Obstacle.objects.create(
            dream=plans_dream,
            title="Test Obstacle",
            description="A test obstacle",
        )
        assert obs.status == "active"
        assert obs.obstacle_type == "predicted"


@pytest.mark.django_db
class TestCalibrationResponse:
    def test_create(self, plans_dream):
        cr = CalibrationResponse.objects.create(
            dream=plans_dream,
            question="Test question?",
            answer="Test answer",
            question_number=1,
        )
        assert str(cr).startswith("Q1:")


@pytest.mark.django_db
class TestPlanCheckIn:
    def test_create(self, plans_dream):
        ci = PlanCheckIn.objects.create(
            dream=plans_dream,
            scheduled_for=timezone.now(),
        )
        assert ci.status == "pending"


@pytest.mark.django_db
class TestDreamProgressSnapshot:
    def test_record_snapshot(self, plans_dream):
        plans_dream.progress_percentage = 50.0
        plans_dream.save()
        DreamProgressSnapshot.record_snapshot(plans_dream)
        snap = DreamProgressSnapshot.objects.get(dream=plans_dream)
        assert snap.progress_percentage == 50.0


@pytest.mark.django_db
class TestFocusSession:
    def test_create(self, plans_user):
        session = FocusSession.objects.create(
            user=plans_user,
            duration_minutes=25,
            session_type="work",
        )
        assert session.completed is False
        assert session.actual_minutes == 0
