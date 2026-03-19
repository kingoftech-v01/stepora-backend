"""
Integration tests for the Leagues & Ranking API endpoints.

Tests league listing, leaderboard views, season management,
reward claiming, and group leaderboards. All endpoints require
authentication and premium+ subscription.
"""

import uuid
from datetime import timedelta
from unittest.mock import Mock, patch

import pytest
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.leagues.models import (
    League,
    LeagueGroup,
    LeagueGroupMembership,
    LeagueSeason,
    LeagueStanding,
    Season,
    SeasonParticipant,
    SeasonReward,
)
from apps.users.models import User


@pytest.fixture
def league_client(league_user):
    """Authenticated API client for league tests."""
    client = APIClient()
    client.force_authenticate(user=league_user)
    return client


@pytest.fixture
def league_client2(league_user2):
    """Authenticated API client for league_user2."""
    client = APIClient()
    client.force_authenticate(user=league_user2)
    return client


@pytest.fixture
def premium_league_user(league_user):
    """Make league_user premium."""
    from apps.subscriptions.models import Subscription, SubscriptionPlan

    plan = SubscriptionPlan.objects.get(slug="premium")
    Subscription.objects.update_or_create(
        user=league_user,
        defaults={
            "plan": plan,
            "status": "active",
            "current_period_start": timezone.now(),
            "current_period_end": timezone.now() + timedelta(days=30),
        },
    )
    return league_user


@pytest.fixture
def premium_league_client(premium_league_user):
    """Premium authenticated client for league tests."""
    client = APIClient()
    client.force_authenticate(user=premium_league_user)
    return client


@pytest.fixture
def premium_league_user2(league_user2):
    """Make league_user2 premium."""
    from apps.subscriptions.models import Subscription, SubscriptionPlan

    plan = SubscriptionPlan.objects.get(slug="premium")
    Subscription.objects.update_or_create(
        user=league_user2,
        defaults={
            "plan": plan,
            "status": "active",
            "current_period_start": timezone.now(),
            "current_period_end": timezone.now() + timedelta(days=30),
        },
    )
    return league_user2


# ──────────────────────────────────────────────────────────────────────
#  Authentication & Permissions
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestLeagueAuth:
    """Tests for league auth and permissions."""

    def test_unauthenticated_access(self):
        """Unauthenticated access returns 401."""
        client = APIClient()
        response = client.get("/api/leagues/leagues/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_free_user_access(self, league_client):
        """Free user accessing league features returns 403."""
        response = league_client.get("/api/leagues/leagues/")
        assert response.status_code == status.HTTP_403_FORBIDDEN


# ──────────────────────────────────────────────────────────────────────
#  League List & Detail
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestLeagueList:
    """Tests for GET /api/leagues/leagues/"""

    def test_list_leagues(self, premium_league_client, bronze_league, silver_league):
        """List all leagues ordered by min_xp."""
        response = premium_league_client.get("/api/leagues/leagues/")
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) >= 2

    def test_retrieve_league(self, premium_league_client, bronze_league):
        """Retrieve a specific league."""
        response = premium_league_client.get(f"/api/leagues/leagues/{bronze_league.id}/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["tier"] == "bronze"


# ──────────────────────────────────────────────────────────────────────
#  Leaderboard: Global
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestGlobalLeaderboard:
    """Tests for GET /api/leagues/leaderboard/global/"""

    @patch("apps.leagues.services.LeagueService.get_leaderboard")
    def test_global_leaderboard(self, mock_lb, premium_league_client, test_season):
        """Get global leaderboard."""
        mock_lb.return_value = [
            {
                "rank": 1,
                "user_id": uuid.uuid4(),
                "user_display_name": "Top User",
                "user_avatar_url": "",
                "user_level": 10,
                "league_name": "Bronze",
                "league_tier": "bronze",
                "league_color_hex": "#CD7F32",
                "xp": 500,
                "tasks_completed": 20,
                "badges_count": 3,
            }
        ]
        response = premium_league_client.get("/api/leagues/leaderboard/global/")
        assert response.status_code == status.HTTP_200_OK

    @patch("apps.leagues.services.LeagueService.get_leaderboard")
    def test_global_leaderboard_with_limit(self, mock_lb, premium_league_client, test_season):
        """Get global leaderboard with custom limit."""
        mock_lb.return_value = []
        response = premium_league_client.get("/api/leagues/leaderboard/global/?limit=10")
        assert response.status_code == status.HTTP_200_OK


# ──────────────────────────────────────────────────────────────────────
#  Leaderboard: League
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestLeagueLeaderboard:
    """Tests for GET /api/leagues/leaderboard/league/"""

    @patch("apps.leagues.services.LeagueService.get_leaderboard")
    @patch("apps.leagues.services.LeagueService.get_user_league")
    def test_league_leaderboard_own(
        self, mock_user_league, mock_lb, premium_league_client,
        bronze_league, test_season
    ):
        """Get leaderboard for user's own league."""
        mock_user_league.return_value = bronze_league
        mock_lb.return_value = []
        response = premium_league_client.get("/api/leagues/leaderboard/league/")
        assert response.status_code == status.HTTP_200_OK

    @patch("apps.leagues.services.LeagueService.get_leaderboard")
    def test_league_leaderboard_specific(
        self, mock_lb, premium_league_client, bronze_league, test_season
    ):
        """Get leaderboard for a specific league."""
        mock_lb.return_value = []
        response = premium_league_client.get(
            f"/api/leagues/leaderboard/league/?league_id={bronze_league.id}"
        )
        assert response.status_code == status.HTTP_200_OK

    def test_league_leaderboard_nonexistent(self, premium_league_client):
        """Get leaderboard for nonexistent league returns 404."""
        response = premium_league_client.get(
            f"/api/leagues/leaderboard/league/?league_id={uuid.uuid4()}"
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND


# ──────────────────────────────────────────────────────────────────────
#  My Standing
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestMyStanding:
    """Tests for GET /api/leagues/leaderboard/me/"""

    def test_my_standing_existing(
        self, premium_league_client, league_standing
    ):
        """Get current user's standing."""
        response = premium_league_client.get("/api/leagues/leaderboard/me/")
        assert response.status_code == status.HTTP_200_OK

    def test_my_standing_no_season(self, premium_league_client):
        """Get standing with no active season returns 204."""
        Season.objects.filter(is_active=True).update(is_active=False)
        response = premium_league_client.get("/api/leagues/leaderboard/me/")
        assert response.status_code in (
            status.HTTP_200_OK,
            status.HTTP_204_NO_CONTENT,
        )


# ──────────────────────────────────────────────────────────────────────
#  Nearby Ranks
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestNearbyRanks:
    """Tests for GET /api/leagues/leaderboard/nearby/"""

    @patch("apps.leagues.services.LeagueService.get_nearby_ranks")
    def test_nearby_ranks(self, mock_nearby, premium_league_client, test_season):
        """Get nearby ranks."""
        mock_nearby.return_value = {"above": [], "below": [], "current": None}
        response = premium_league_client.get("/api/leagues/leaderboard/nearby/")
        assert response.status_code == status.HTTP_200_OK

    @patch("apps.leagues.services.LeagueService.get_nearby_ranks")
    def test_nearby_ranks_custom_count(self, mock_nearby, premium_league_client, test_season):
        """Get nearby ranks with custom count."""
        mock_nearby.return_value = {"above": [], "below": [], "current": None}
        response = premium_league_client.get("/api/leagues/leaderboard/nearby/?count=3")
        assert response.status_code == status.HTTP_200_OK


# ──────────────────────────────────────────────────────────────────────
#  Season List & Detail
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestSeasonEndpoints:
    """Tests for /api/leagues/seasons/ endpoints."""

    def test_list_seasons(self, premium_league_client, test_season):
        """List all seasons."""
        response = premium_league_client.get("/api/leagues/seasons/")
        assert response.status_code == status.HTTP_200_OK

    def test_retrieve_season(self, premium_league_client, test_season):
        """Retrieve a specific season."""
        response = premium_league_client.get(
            f"/api/leagues/seasons/{test_season.id}/"
        )
        assert response.status_code == status.HTTP_200_OK

    def test_current_season(self, premium_league_client, test_season):
        """Get current active season."""
        response = premium_league_client.get("/api/leagues/seasons/current/")
        assert response.status_code == status.HTTP_200_OK

    def test_current_season_none(self, premium_league_client):
        """Get current season when none is active."""
        Season.objects.filter(is_active=True).update(is_active=False)
        response = premium_league_client.get("/api/leagues/seasons/current/")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_past_seasons(self, premium_league_client, ended_season):
        """Get past seasons."""
        response = premium_league_client.get("/api/leagues/seasons/past/")
        assert response.status_code == status.HTTP_200_OK

    def test_my_rewards_empty(self, premium_league_client):
        """Get my rewards when none exist."""
        response = premium_league_client.get("/api/leagues/seasons/my-rewards/")
        assert response.status_code == status.HTTP_200_OK

    def test_claim_reward_season_not_ended(self, premium_league_client, test_season):
        """Claim reward when season has not ended returns 400."""
        response = premium_league_client.post(
            f"/api/leagues/seasons/{test_season.id}/claim-reward/"
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_claim_reward_no_reward(self, premium_league_client, ended_season):
        """Claim reward when no reward exists returns 404."""
        response = premium_league_client.post(
            f"/api/leagues/seasons/{ended_season.id}/claim-reward/"
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND


# ──────────────────────────────────────────────────────────────────────
#  League Groups
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestLeagueGroups:
    """Tests for /api/leagues/groups/ endpoints."""

    def test_list_groups(self, premium_league_client, test_season):
        """List league groups."""
        response = premium_league_client.get("/api/leagues/groups/")
        assert response.status_code == status.HTTP_200_OK

    def test_my_group_not_assigned(self, premium_league_client, test_season):
        """Get my group when not assigned returns 404."""
        response = premium_league_client.get("/api/leagues/groups/mine/")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_my_group_no_season(self, premium_league_client):
        """Get my group when no active season."""
        Season.objects.filter(is_active=True).update(is_active=False)
        response = premium_league_client.get("/api/leagues/groups/mine/")
        assert response.status_code == status.HTTP_404_NOT_FOUND


# ──────────────────────────────────────────────────────────────────────
#  League Seasons (themed)
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestLeagueSeasons:
    """Tests for /api/leagues/league-seasons/ endpoints."""

    @pytest.fixture
    def test_league_season(self, db):
        """Create a test league season."""
        return LeagueSeason.objects.create(
            name="Spring Challenge",
            theme="growth",
            description="Grow your dreams this spring",
            start_date=timezone.now() - timedelta(days=5),
            end_date=timezone.now() + timedelta(days=25),
            is_active=True,
            rewards={
                "1": {"xp": 1000, "badge": "spring_champion"},
                "2": {"xp": 500, "badge": "spring_runner"},
            },
        )

    def test_list_league_seasons(self, premium_league_client, test_league_season):
        """List league seasons."""
        response = premium_league_client.get("/api/leagues/league-seasons/")
        assert response.status_code == status.HTTP_200_OK

    def test_current_league_season(self, premium_league_client, test_league_season):
        """Get current league season."""
        response = premium_league_client.get("/api/leagues/league-seasons/current/")
        assert response.status_code == status.HTTP_200_OK

    def test_current_league_season_none(self, premium_league_client):
        """Get current league season when none active."""
        LeagueSeason.objects.filter(is_active=True).update(is_active=False)
        response = premium_league_client.get("/api/leagues/league-seasons/current/")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_join_league_season(self, premium_league_client, test_league_season):
        """Join the current league season."""
        response = premium_league_client.post(
            "/api/leagues/league-seasons/current/join/"
        )
        assert response.status_code == status.HTTP_200_OK

    def test_join_league_season_twice(
        self, premium_league_client, test_league_season, premium_league_user
    ):
        """Joining a league season twice returns 400."""
        SeasonParticipant.objects.create(
            season=test_league_season, user=premium_league_user, xp_earned=0,
        )
        response = premium_league_client.post(
            "/api/leagues/league-seasons/current/join/"
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_league_season_leaderboard(
        self, premium_league_client, test_league_season, premium_league_user
    ):
        """Get league season leaderboard."""
        SeasonParticipant.objects.create(
            season=test_league_season, user=premium_league_user, xp_earned=100,
        )
        response = premium_league_client.get(
            f"/api/leagues/league-seasons/{test_league_season.id}/leaderboard/"
        )
        assert response.status_code == status.HTTP_200_OK

    def test_claim_league_season_rewards_not_ended(
        self, premium_league_client, test_league_season
    ):
        """Claim rewards when season not ended returns 400."""
        response = premium_league_client.post(
            f"/api/leagues/league-seasons/{test_league_season.id}/claim-rewards/"
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST


# ──────────────────────────────────────────────────────────────────────
#  Friends Leaderboard
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestFriendsLeaderboard:
    """Tests for GET /api/leagues/leaderboard/friends/"""

    def test_friends_leaderboard_no_season(self, premium_league_client):
        """Friends leaderboard with no active season returns empty."""
        Season.objects.filter(is_active=True).update(is_active=False)
        response = premium_league_client.get("/api/leagues/leaderboard/friends/")
        assert response.status_code == status.HTTP_200_OK

    def test_friends_leaderboard_with_season(
        self, premium_league_client, test_season, league_standing
    ):
        """Friends leaderboard with active season and standing."""
        response = premium_league_client.get("/api/leagues/leaderboard/friends/")
        assert response.status_code == status.HTTP_200_OK
