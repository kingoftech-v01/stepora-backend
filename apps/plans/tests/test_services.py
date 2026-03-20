"""
Tests for plans services.
"""

import pytest
from django.utils import timezone

from apps.dreams.models import Dream
from apps.plans.models import DreamMilestone, Goal, PlanCheckIn, Task
from apps.plans.services import PlanService
from apps.users.models import User


@pytest.fixture
def svc_user(db):
    return User.objects.create_user(
        email="plansvc@test.com",
        password="testpass123",
    )


@pytest.fixture
def svc_dream(svc_user):
    return Dream.objects.create(
        user=svc_user,
        title="Service Dream",
        description="Test",
        target_date=timezone.now() + timezone.timedelta(days=180),
    )


@pytest.mark.django_db
class TestPlanService:
    def test_get_plan_summary(self, svc_dream):
        ms = DreamMilestone.objects.create(dream=svc_dream, title="M1", order=1)
        goal = Goal.objects.create(dream=svc_dream, milestone=ms, title="G1", order=1)
        Task.objects.create(goal=goal, title="T1", order=1)

        summary = PlanService.get_dream_plan_summary(svc_dream)
        assert summary["milestones"] == 1
        assert summary["goals"] == 1
        assert summary["total_tasks"] == 1
        assert summary["completed_tasks"] == 0

    def test_process_checkin(self, svc_dream):
        checkin = PlanCheckIn.objects.create(
            dream=svc_dream,
            scheduled_for=timezone.now(),
            status="ai_processing",
        )
        PlanService.process_checkin(checkin)
        checkin.refresh_from_db()
        assert checkin.pace_status != ""
        assert checkin.coaching_message != ""

    def test_compute_pace_on_track(self, svc_dream):
        pace = PlanService._compute_pace(svc_dream, overdue_count=0)
        assert pace in ("on_track", "ahead", "significantly_ahead")
