"""
Tests for gamification views.
"""

import pytest
from rest_framework.test import APIClient

from apps.gamification.models import (
    Achievement,
    GamificationProfile,
)
from apps.users.models import User


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def auth_user(db):
    user = User.objects.create_user(
        email="gamview@test.com",
        password="testpass123",
        display_name="Gam View User",
    )
    return user


@pytest.fixture
def auth_client(api_client, auth_user):
    api_client.force_authenticate(user=auth_user)
    return api_client


@pytest.mark.django_db
class TestGamificationProfileView:
    """Tests for GamificationProfileView."""

    def test_get_profile(self, auth_client, auth_user):
        response = auth_client.get("/api/v1/gamification/profile/")
        assert response.status_code == 200
        assert "health_xp" in response.data
        assert "skill_radar" in response.data

    def test_unauthenticated(self, api_client):
        response = api_client.get("/api/v1/gamification/profile/")
        assert response.status_code == 401


@pytest.mark.django_db
class TestAchievementsView:
    """Tests for AchievementsView."""

    def test_get_achievements(self, auth_client):
        Achievement.objects.create(
            name="Test Achievement",
            description="Test",
            icon="star",
            category="dreams",
            condition_type="first_dream",
            condition_value=1,
        )
        response = auth_client.get("/api/v1/gamification/achievements/")
        assert response.status_code == 200
        assert "achievements" in response.data
        assert response.data["total_count"] == 1


@pytest.mark.django_db
class TestStreakDetailsView:
    """Tests for StreakDetailsView."""

    def test_get_streak_details(self, auth_client, auth_user):
        response = auth_client.get("/api/v1/gamification/streak-details/")
        assert response.status_code == 200
        assert "current_streak" in response.data
        assert "longest_streak" in response.data
        assert "streak_history" in response.data
        assert len(response.data["streak_history"]) == 14


@pytest.mark.django_db
class TestStreakFreezeView:
    """Tests for StreakFreezeView."""

    def test_use_streak_freeze(self, auth_client, auth_user):
        GamificationProfile.objects.get_or_create(user=auth_user)
        response = auth_client.post("/api/v1/gamification/streak-freeze/")
        assert response.status_code == 200
        assert response.data["freeze_count"] == 2

    def test_no_freezes_available(self, auth_client, auth_user):
        profile, _ = GamificationProfile.objects.get_or_create(user=auth_user)
        profile.streak_jokers = 0
        profile.save()
        response = auth_client.post("/api/v1/gamification/streak-freeze/")
        assert response.status_code == 400


@pytest.mark.django_db
class TestLeaderboardStatsView:
    """Tests for LeaderboardStatsView."""

    def test_get_leaderboard(self, auth_client, auth_user):
        response = auth_client.get("/api/v1/gamification/leaderboard/")
        assert response.status_code == 200
        assert "xp_rank" in response.data
        assert "streak_rank" in response.data
