"""
Tests for plans views.
"""

import pytest
from rest_framework.test import APIClient

from apps.dreams.models import Dream
from apps.plans.models import DreamMilestone, FocusSession, Goal, Task
from apps.users.models import User


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def view_user(db):
    return User.objects.create_user(
        email="planview@test.com",
        password="testpass123",
    )


@pytest.fixture
def view_dream(view_user):
    return Dream.objects.create(
        user=view_user,
        title="View Dream",
        description="Test",
    )


@pytest.fixture
def auth_client(api_client, view_user):
    api_client.force_authenticate(user=view_user)
    return api_client


@pytest.mark.django_db
class TestMilestoneViewSet:
    def test_list_milestones(self, auth_client, view_dream):
        DreamMilestone.objects.create(dream=view_dream, title="M1", order=1)
        response = auth_client.get(f"/api/v1/plans/milestones/?dream={view_dream.id}")
        assert response.status_code == 200


@pytest.mark.django_db
class TestGoalViewSet:
    def test_list_goals(self, auth_client, view_dream):
        response = auth_client.get(f"/api/v1/plans/goals/?dream={view_dream.id}")
        assert response.status_code == 200


@pytest.mark.django_db
class TestTaskViewSet:
    def test_list_tasks(self, auth_client, view_dream):
        ms = DreamMilestone.objects.create(dream=view_dream, title="M1", order=1)
        goal = Goal.objects.create(dream=view_dream, milestone=ms, title="G1", order=1)
        Task.objects.create(goal=goal, title="T1", order=1)
        response = auth_client.get(f"/api/v1/plans/tasks/?goal={goal.id}")
        assert response.status_code == 200


@pytest.mark.django_db
class TestFocusSessionViews:
    def test_start_session(self, auth_client):
        response = auth_client.post(
            "/api/v1/plans/focus/start/",
            {"duration_minutes": 25, "session_type": "work"},
            format="json",
        )
        assert response.status_code == 201

    def test_history(self, auth_client, view_user):
        FocusSession.objects.create(user=view_user, duration_minutes=25)
        response = auth_client.get("/api/v1/plans/focus/history/")
        assert response.status_code == 200

    def test_stats(self, auth_client):
        response = auth_client.get("/api/v1/plans/focus/stats/")
        assert response.status_code == 200
