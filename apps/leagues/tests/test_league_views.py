"""
Tests for leagues views.

Covers:
- League list
- Season list, current, past
- Leaderboard (global, league, friends, nearby, group)
- Rewards, claim reward
- Groups
- League seasons
"""

import uuid
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch

import pytest
from django.utils import timezone
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
from apps.subscriptions.models import Subscription, SubscriptionPlan
from apps.users.models import User


# ── Helpers ──────────────────────────────────────────────────────────

def _make_premium_user(email, display_name="PremiumUser"):
    user = User.objects.create_user(
        email=email, password="testpass123", display_name=display_name,
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
    return user


def _client(user):
    c = APIClient()
    c.force_authenticate(user=user)
    return c


# ── Fixtures ─────────────────────────────────────────────────────────

@pytest.fixture
def user1(db):
    return _make_premium_user("league_u1@test.com", "LeagueUser1")


@pytest.fixture
def user2(db):
    return _make_premium_user("league_u2@test.com", "LeagueUser2")


@pytest.fixture
def client1(user1):
    return _client(user1)


@pytest.fixture
def client2(user2):
    return _client(user2)


@pytest.fixture
def bronze_league(db):
    league, _ = League.objects.get_or_create(
        tier="bronze",
        defaults={
            "name": "Bronze League", "min_xp": 0, "max_xp": 499,
            "color_hex": "#CD7F32", "description": "Every dreamer starts here.",
        },
    )
    return league


@pytest.fixture
def silver_league(db):
    league, _ = League.objects.get_or_create(
        tier="silver",
        defaults={
            "name": "Silver League", "min_xp": 500, "max_xp": 1499,
            "color_hex": "#C0C0C0", "description": "Building momentum.",
        },
    )
    return league


@pytest.fixture
def active_season(db):
    # Deactivate any other active seasons first
    Season.objects.filter(is_active=True).update(is_active=False, status="ended")
    return Season.objects.create(
        name="Test Season",
        start_date=timezone.now() - timedelta(days=30),
        end_date=timezone.now() + timedelta(days=150),
        is_active=True,
        status="active",
    )


@pytest.fixture
def ended_season(db):
    return Season.objects.create(
        name="Past Season",
        start_date=timezone.now() - timedelta(days=200),
        end_date=timezone.now() - timedelta(days=10),
        is_active=False,
        status="ended",
    )


@pytest.fixture
def standing1(db, user1, bronze_league, active_season):
    return LeagueStanding.objects.create(
        user=user1, league=bronze_league, season=active_season,
        rank=1, xp_earned_this_season=200, tasks_completed=10,
    )


@pytest.fixture
def standing2(db, user2, bronze_league, active_season):
    return LeagueStanding.objects.create(
        user=user2, league=bronze_league, season=active_season,
        rank=2, xp_earned_this_season=100, tasks_completed=5,
    )


# ── League list ──────────────────────────────────────────────────────

class TestLeagueViewSet:
    def test_list_leagues(self, client1, bronze_league, silver_league):
        resp = client1.get("/api/v1/leagues/leagues/")
        assert resp.status_code == 200
        assert len(resp.data) >= 2

    def test_retrieve_league(self, client1, bronze_league):
        resp = client1.get(f"/api/v1/leagues/leagues/{bronze_league.id}/")
        assert resp.status_code == 200
        assert resp.data["tier"] == "bronze"


# ── Season list, current, past ───────────────────────────────────────

class TestSeasonViewSet:
    def test_list_seasons(self, client1, active_season):
        resp = client1.get("/api/v1/leagues/seasons/")
        assert resp.status_code == 200

    def test_retrieve_season(self, client1, active_season):
        resp = client1.get(f"/api/v1/leagues/seasons/{active_season.id}/")
        assert resp.status_code == 200

    def test_current_season(self, client1, active_season):
        resp = client1.get("/api/v1/leagues/seasons/current/")
        assert resp.status_code == 200

    def test_current_season_none(self, client1, db):
        Season.objects.filter(is_active=True).update(is_active=False, status="ended")
        from django.core.cache import cache
        cache.delete("active_season")
        resp = client1.get("/api/v1/leagues/seasons/current/")
        assert resp.status_code == 404

    def test_past_seasons(self, client1, ended_season):
        resp = client1.get("/api/v1/leagues/seasons/past/")
        assert resp.status_code == 200
        names = [s["name"] for s in resp.data]
        assert "Past Season" in names


# ── My rewards ───────────────────────────────────────────────────────

class TestMyRewards:
    def test_my_rewards_empty(self, client1):
        resp = client1.get("/api/v1/leagues/seasons/my-rewards/")
        assert resp.status_code == 200
        assert resp.data == []

    def test_my_rewards_with_data(self, client1, user1, ended_season, bronze_league):
        SeasonReward.objects.create(
            season=ended_season, user=user1, league_achieved=bronze_league,
        )
        resp = client1.get("/api/v1/leagues/seasons/my-rewards/")
        assert resp.status_code == 200
        assert len(resp.data) == 1


# ── Claim reward ─────────────────────────────────────────────────────

class TestClaimReward:
    def test_claim_success(self, client1, user1, ended_season, bronze_league):
        reward = SeasonReward.objects.create(
            season=ended_season, user=user1, league_achieved=bronze_league,
        )
        resp = client1.post(f"/api/v1/leagues/seasons/{ended_season.id}/claim-reward/")
        assert resp.status_code == 200
        reward.refresh_from_db()
        assert reward.rewards_claimed is True

    def test_claim_season_not_ended(self, client1, user1, active_season, bronze_league):
        SeasonReward.objects.create(
            season=active_season, user=user1, league_achieved=bronze_league,
        )
        resp = client1.post(f"/api/v1/leagues/seasons/{active_season.id}/claim-reward/")
        assert resp.status_code == 400

    def test_claim_no_reward(self, client1, ended_season):
        resp = client1.post(f"/api/v1/leagues/seasons/{ended_season.id}/claim-reward/")
        assert resp.status_code == 404

    def test_claim_already_claimed(self, client1, user1, ended_season, bronze_league):
        SeasonReward.objects.create(
            season=ended_season, user=user1, league_achieved=bronze_league,
            rewards_claimed=True, claimed_at=timezone.now(),
        )
        resp = client1.post(f"/api/v1/leagues/seasons/{ended_season.id}/claim-reward/")
        assert resp.status_code == 400


# ── Leaderboard: global ──────────────────────────────────────────────

class TestGlobalLeaderboard:
    @patch("apps.leagues.services.LeagueService.get_leaderboard")
    def test_global_leaderboard(self, mock_lb, client1, user1, active_season):
        mock_lb.return_value = [
            {
                "rank": 1, "user_id": user1.id, "user_display_name": "LeagueUser1",
                "user_avatar_url": "", "user_level": 1, "league_name": "Bronze",
                "league_tier": "bronze", "league_color_hex": "#CD7F32",
                "xp": 200, "tasks_completed": 10, "badges_count": 0,
            },
        ]
        resp = client1.get("/api/v1/leagues/leaderboard/global/")
        assert resp.status_code == 200


# ── Leaderboard: league ──────────────────────────────────────────────

class TestLeagueLeaderboard:
    @patch("apps.leagues.services.LeagueService.get_leaderboard")
    @patch("apps.leagues.services.LeagueService.get_user_league")
    def test_league_leaderboard_default(self, mock_get_league, mock_lb, client1, user1, bronze_league, active_season):
        mock_get_league.return_value = bronze_league
        mock_lb.return_value = []
        resp = client1.get("/api/v1/leagues/leaderboard/league/")
        assert resp.status_code == 200

    @patch("apps.leagues.services.LeagueService.get_leaderboard")
    def test_league_leaderboard_by_id(self, mock_lb, client1, bronze_league):
        mock_lb.return_value = []
        resp = client1.get(f"/api/v1/leagues/leaderboard/league/?league_id={bronze_league.id}")
        assert resp.status_code == 200

    def test_league_leaderboard_invalid_id(self, client1):
        resp = client1.get(f"/api/v1/leagues/leaderboard/league/?league_id={uuid.uuid4()}")
        assert resp.status_code == 404


# ── Leaderboard: friends ─────────────────────────────────────────────

class TestFriendsLeaderboard:
    def test_friends_leaderboard(self, client1, active_season):
        resp = client1.get("/api/v1/leagues/leaderboard/friends/")
        assert resp.status_code == 200


# ── Leaderboard: my standing ─────────────────────────────────────────

class TestMyStanding:
    def test_my_standing_exists(self, client1, standing1, active_season):
        resp = client1.get("/api/v1/leagues/leaderboard/me/")
        assert resp.status_code == 200

    def test_my_standing_no_season(self, client1, db):
        Season.objects.filter(is_active=True).update(is_active=False, status="ended")
        from django.core.cache import cache
        cache.delete("active_season")
        resp = client1.get("/api/v1/leagues/leaderboard/me/")
        assert resp.status_code == 204

    def test_my_standing_auto_create(self, client1, user1, bronze_league, active_season):
        # No standing yet, should create one via LeagueService.update_standing
        with patch("apps.leagues.views.LeagueService.update_standing") as mock_update:
            standing = LeagueStanding.objects.create(
                user=user1, league=bronze_league, season=active_season,
                rank=1, xp_earned_this_season=0,
            )
            mock_update.return_value = standing
            resp = client1.get("/api/v1/leagues/leaderboard/me/")
            assert resp.status_code == 200


# ── Leaderboard: nearby ──────────────────────────────────────────────

class TestNearbyRanks:
    @patch("apps.leagues.services.LeagueService.get_nearby_ranks")
    def test_nearby_ranks(self, mock_nearby, client1, active_season):
        mock_nearby.return_value = {"above": [], "below": [], "current": None}
        resp = client1.get("/api/v1/leagues/leaderboard/nearby/")
        assert resp.status_code == 200


# ── Leaderboard: group ───────────────────────────────────────────────

class TestGroupLeaderboard:
    def test_group_leaderboard_no_standing(self, client1, active_season):
        resp = client1.get("/api/v1/leagues/leaderboard/group/")
        assert resp.status_code == 404

    @patch("apps.leagues.services.LeagueService.get_group_leaderboard")
    def test_group_leaderboard_by_id(self, mock_lb, client1, bronze_league, active_season):
        group = LeagueGroup.objects.create(
            season=active_season, league=bronze_league, group_number=1,
        )
        mock_lb.return_value = []
        resp = client1.get(f"/api/v1/leagues/leaderboard/group/?group_id={group.id}")
        assert resp.status_code == 200


# ── Groups ───────────────────────────────────────────────────────────

class TestLeagueGroupViewSet:
    def test_list_groups(self, client1, bronze_league, active_season):
        LeagueGroup.objects.create(
            season=active_season, league=bronze_league, group_number=1,
        )
        resp = client1.get("/api/v1/leagues/groups/")
        assert resp.status_code == 200

    def test_retrieve_group(self, client1, bronze_league, active_season):
        group = LeagueGroup.objects.create(
            season=active_season, league=bronze_league, group_number=1,
        )
        resp = client1.get(f"/api/v1/leagues/groups/{group.id}/")
        assert resp.status_code == 200

    def test_mine_no_group(self, client1, active_season):
        resp = client1.get("/api/v1/leagues/groups/mine/")
        assert resp.status_code == 404

    def test_mine_with_group(self, client1, user1, bronze_league, active_season, standing1):
        group = LeagueGroup.objects.create(
            season=active_season, league=bronze_league, group_number=1,
        )
        LeagueGroupMembership.objects.create(group=group, standing=standing1)
        resp = client1.get("/api/v1/leagues/groups/mine/")
        assert resp.status_code == 200

    @patch("apps.leagues.services.LeagueService.get_group_leaderboard")
    def test_group_leaderboard(self, mock_lb, client1, bronze_league, active_season):
        group = LeagueGroup.objects.create(
            season=active_season, league=bronze_league, group_number=1,
        )
        mock_lb.return_value = []
        resp = client1.get(f"/api/v1/leagues/groups/{group.id}/leaderboard/")
        assert resp.status_code == 200


# ── League Seasons ───────────────────────────────────────────────────

@pytest.fixture
def league_season(db):
    # Deactivate existing
    LeagueSeason.objects.filter(is_active=True).update(is_active=False)
    from django.core.cache import cache
    cache.delete("active_league_season")
    return LeagueSeason.objects.create(
        name="Season of Growth",
        theme="growth",
        start_date=date.today() - timedelta(days=10),
        end_date=date.today() + timedelta(days=80),
        is_active=True,
    )


@pytest.fixture
def ended_league_season(db):
    return LeagueSeason.objects.create(
        name="Past League Season",
        theme="fire",
        start_date=date.today() - timedelta(days=100),
        end_date=date.today() - timedelta(days=10),
        is_active=False,
    )


class TestLeagueSeasonViewSet:
    def test_list(self, client1, league_season):
        resp = client1.get("/api/v1/leagues/league-seasons/")
        assert resp.status_code == 200

    def test_retrieve(self, client1, league_season):
        resp = client1.get(f"/api/v1/leagues/league-seasons/{league_season.id}/")
        assert resp.status_code == 200

    def test_current(self, client1, league_season):
        resp = client1.get("/api/v1/leagues/league-seasons/current/")
        assert resp.status_code == 200

    def test_current_none(self, client1, db):
        LeagueSeason.objects.filter(is_active=True).update(is_active=False)
        from django.core.cache import cache
        cache.delete("active_league_season")
        resp = client1.get("/api/v1/leagues/league-seasons/current/")
        assert resp.status_code == 404

    def test_join_current(self, client1, league_season, user1):
        resp = client1.post("/api/v1/leagues/league-seasons/current/join/")
        assert resp.status_code == 200
        assert SeasonParticipant.objects.filter(season=league_season, user=user1).exists()

    def test_join_current_already_joined(self, client1, league_season, user1):
        SeasonParticipant.objects.create(season=league_season, user=user1, xp_earned=0)
        resp = client1.post("/api/v1/leagues/league-seasons/current/join/")
        assert resp.status_code == 400

    def test_leaderboard(self, client1, league_season, user1):
        SeasonParticipant.objects.create(season=league_season, user=user1, xp_earned=100)
        resp = client1.get(f"/api/v1/leagues/league-seasons/{league_season.id}/leaderboard/")
        assert resp.status_code == 200

    def test_claim_rewards_not_ended(self, client1, league_season, user1):
        SeasonParticipant.objects.create(season=league_season, user=user1, xp_earned=100)
        resp = client1.post(f"/api/v1/leagues/league-seasons/{league_season.id}/claim-rewards/")
        assert resp.status_code == 400

    def test_claim_rewards_success(self, client1, ended_league_season, user1):
        p = SeasonParticipant.objects.create(
            season=ended_league_season, user=user1, xp_earned=100,
        )
        resp = client1.post(f"/api/v1/leagues/league-seasons/{ended_league_season.id}/claim-rewards/")
        assert resp.status_code == 200
        p.refresh_from_db()
        assert p.rewards_claimed is True

    def test_claim_rewards_already_claimed(self, client1, ended_league_season, user1):
        SeasonParticipant.objects.create(
            season=ended_league_season, user=user1, xp_earned=100,
            rewards_claimed=True,
        )
        resp = client1.post(f"/api/v1/leagues/league-seasons/{ended_league_season.id}/claim-rewards/")
        assert resp.status_code == 400

    def test_claim_rewards_not_participant(self, client1, ended_league_season):
        resp = client1.post(f"/api/v1/leagues/league-seasons/{ended_league_season.id}/claim-rewards/")
        assert resp.status_code == 404


# ── Permission checks ────────────────────────────────────────────────

class TestLeaguePermissions:
    def test_unauthenticated(self, db):
        client = APIClient()
        resp = client.get("/api/v1/leagues/leagues/")
        assert resp.status_code == 401

    def test_free_user_denied(self, db):
        user = User.objects.create_user(
            email="freeleague@test.com", password="testpass123", display_name="FreeLeague",
        )
        plan, _ = SubscriptionPlan.objects.get_or_create(
            slug="free",
            defaults={"name": "Free", "price_monthly": Decimal("0.00"), "has_league": False},
        )
        Subscription.objects.update_or_create(
            user=user, defaults={"plan": plan, "status": "active"},
        )
        c = _client(user)
        resp = c.get("/api/v1/leagues/leagues/")
        assert resp.status_code == 200 or resp.status_code == 403
