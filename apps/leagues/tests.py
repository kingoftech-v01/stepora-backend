"""
Tests for the Leagues & Ranking system.

Covers:
- Model creation and constraints
- League assignment by XP
- Standing updates and rank calculation
- Leaderboard retrieval (global, league, nearby)
- Promotion and demotion logic
- Season reward calculation and claiming
- API endpoints (leagues, leaderboards, seasons)
- Signal-driven standing updates on XP change
"""

import uuid
from datetime import timedelta

import pytest
from django.utils import timezone as django_timezone
from rest_framework.test import APIClient

from apps.leagues.models import League, LeagueStanding, Season, SeasonReward
from apps.leagues.services import LeagueService
from apps.users.models import GamificationProfile, User

# ---------------------------------------------------------------------------
# Local fixture overrides – make all users premium so CanUseLeague passes
# ---------------------------------------------------------------------------


@pytest.fixture
def user(db):
    """Override global ``user`` fixture: create a **premium** user so that
    CanUseLeague (premium+ required) does not block API requests."""
    return User.objects.create_user(
        email=f"league_premium_{uuid.uuid4().hex[:8]}@example.com",
        password="testpassword123",
        display_name="Premium League User",
        subscription="premium",
        subscription_ends=django_timezone.now() + timedelta(days=30),
    )


@pytest.fixture
def authenticated_client(user):
    """Override global ``authenticated_client`` fixture: authenticate with the
    premium *user* defined above."""
    client = APIClient()
    client.force_authenticate(user=user)
    return client


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def leagues(db):
    """Create all seven league tiers and return them as a dict keyed by tier."""
    data = [
        ("bronze", "Bronze League", 0, 499, "#CD7F32"),
        ("silver", "Silver League", 500, 1499, "#C0C0C0"),
        ("gold", "Gold League", 1500, 3499, "#FFD700"),
        ("platinum", "Platinum League", 3500, 6999, "#E5E4E2"),
        ("diamond", "Diamond League", 7000, 11999, "#B9F2FF"),
        ("master", "Master League", 12000, 19999, "#9B59B6"),
        ("legend", "Legend League", 20000, None, "#FF6B35"),
    ]
    result = {}
    for tier, name, min_xp, max_xp, color in data:
        league, _ = League.objects.get_or_create(
            tier=tier,
            defaults={
                "name": name,
                "min_xp": min_xp,
                "max_xp": max_xp,
                "color_hex": color,
                "rewards": [{"type": "badge", "name": f"{name} Badge"}],
            },
        )
        result[tier] = league
    return result


@pytest.fixture
def active_season(db):
    """Create and return an active season spanning 90 days."""
    now = django_timezone.now()
    return Season.objects.create(
        name="Test Season 1",
        start_date=now - timedelta(days=10),
        end_date=now + timedelta(days=80),
        is_active=True,
        rewards=[{"tier": "bronze", "rewards": ["Test Badge"]}],
    )


@pytest.fixture
def ended_season(db):
    """Create and return an ended season."""
    now = django_timezone.now()
    return Season.objects.create(
        name="Past Season",
        start_date=now - timedelta(days=100),
        end_date=now - timedelta(days=10),
        is_active=False,
        rewards=[],
    )


@pytest.fixture
def league_user(db):
    """Create a premium test user for league tests (premium subscription
    required for CanUseLeague permission)."""
    return User.objects.create(
        email=f"league_{uuid.uuid4().hex[:8]}@example.com",
        display_name="League Tester",
        xp=0,
        level=1,
        streak_days=0,
        subscription="premium",
        subscription_ends=django_timezone.now() + timedelta(days=30),
    )


@pytest.fixture
def league_user_with_gamification(league_user):
    """Create a test user with a gamification profile."""
    GamificationProfile.objects.create(
        user=league_user,
        badges=["early_bird", "streak_7"],
        achievements=["first_task"],
    )
    return league_user


@pytest.fixture
def multiple_league_users(db):
    """Create multiple users with varying XP for leaderboard testing."""
    users = []
    xp_values = [100, 500, 1500, 3500, 7000, 12000, 25000, 200, 800, 2000]
    for i, xp in enumerate(xp_values):
        user = User.objects.create(
            email=f"lb_user_{i}_{uuid.uuid4().hex[:8]}@example.com",
            display_name=f"User {i}",
            xp=xp,
            level=(xp // 100) + 1,
        )
        users.append(user)
    return users


@pytest.fixture
def authenticated_league_client(league_user):
    """Return an authenticated API client for the league user."""
    client = APIClient()
    client.force_authenticate(user=league_user)
    return client


# ---------------------------------------------------------------------------
# Model Tests
# ---------------------------------------------------------------------------


class TestLeagueModel:
    """Tests for the League model."""

    def test_league_creation(self, leagues):
        """Test that all seven leagues are created correctly."""
        assert League.objects.count() == 7

    def test_league_str_with_max_xp(self, leagues):
        """Test string representation for league with max_xp."""
        bronze = leagues["bronze"]
        assert "Bronze League" in str(bronze)
        assert "0-499 XP" in str(bronze)

    def test_league_str_without_max_xp(self, leagues):
        """Test string representation for league without max_xp (Legend)."""
        legend = leagues["legend"]
        assert "Legend League" in str(legend)
        assert "20000+ XP" in str(legend)

    def test_league_ordering(self, leagues):
        """Test that leagues are ordered by min_xp ascending."""
        ordered = list(League.objects.all())
        assert ordered[0].tier == "bronze"
        assert ordered[-1].tier == "legend"

    def test_league_tier_uniqueness(self, leagues):
        """Test that tier values are unique."""
        with pytest.raises(Exception):
            League.objects.create(
                name="Duplicate Bronze",
                tier="bronze",
                min_xp=0,
                max_xp=100,
            )

    def test_contains_xp_within_range(self, leagues):
        """Test contains_xp for XP within the league range."""
        assert leagues["bronze"].contains_xp(0) is True
        assert leagues["bronze"].contains_xp(250) is True
        assert leagues["bronze"].contains_xp(499) is True

    def test_contains_xp_outside_range(self, leagues):
        """Test contains_xp for XP outside the league range."""
        assert leagues["bronze"].contains_xp(500) is False
        assert leagues["silver"].contains_xp(0) is False

    def test_contains_xp_legend_no_upper_bound(self, leagues):
        """Test that Legend league accepts any XP >= min_xp."""
        assert leagues["legend"].contains_xp(20000) is True
        assert leagues["legend"].contains_xp(999999) is True
        assert leagues["legend"].contains_xp(19999) is False

    def test_tier_order_property(self, leagues):
        """Test the tier_order property returns correct order."""
        assert leagues["bronze"].tier_order == 0
        assert leagues["legend"].tier_order == 6


class TestSeasonModel:
    """Tests for the Season model."""

    def test_season_creation(self, active_season):
        """Test season creation with required fields."""
        assert active_season.name == "Test Season 1"
        assert active_season.is_active is True

    def test_season_str(self, active_season):
        """Test season string representation."""
        assert "Test Season 1" in str(active_season)
        assert "Active" in str(active_season)

    def test_is_current_property(self, active_season):
        """Test is_current property for an active season."""
        assert active_season.is_current is True

    def test_has_ended_property(self, active_season, ended_season):
        """Test has_ended property."""
        assert active_season.has_ended is False
        assert ended_season.has_ended is True

    def test_days_remaining(self, active_season):
        """Test days_remaining returns a positive number."""
        assert active_season.days_remaining > 0

    def test_days_remaining_ended_season(self, ended_season):
        """Test days_remaining returns 0 for ended season."""
        assert ended_season.days_remaining == 0

    def test_get_active_season(self, active_season):
        """Test get_active_season classmethod."""
        result = Season.get_active_season()
        assert result is not None
        assert result.id == active_season.id

    def test_get_active_season_none(self, db):
        """Test get_active_season returns None when no active season."""
        result = Season.get_active_season()
        assert result is None


class TestLeagueStandingModel:
    """Tests for the LeagueStanding model."""

    def test_standing_creation(self, leagues, active_season, league_user):
        """Test creating a league standing."""
        standing = LeagueStanding.objects.create(
            user=league_user,
            league=leagues["bronze"],
            season=active_season,
            rank=1,
            xp_earned_this_season=100,
        )
        assert standing.id is not None
        assert standing.rank == 1
        assert standing.tasks_completed == 0

    def test_standing_unique_user_season(self, leagues, active_season, league_user):
        """Test that a user can only have one standing per season."""
        LeagueStanding.objects.create(
            user=league_user,
            league=leagues["bronze"],
            season=active_season,
        )
        with pytest.raises(Exception):
            LeagueStanding.objects.create(
                user=league_user,
                league=leagues["silver"],
                season=active_season,
            )

    def test_standing_str(self, leagues, active_season, league_user):
        """Test standing string representation."""
        standing = LeagueStanding.objects.create(
            user=league_user,
            league=leagues["bronze"],
            season=active_season,
            rank=5,
            xp_earned_this_season=250,
        )
        result = str(standing)
        assert "Rank #5" in result
        assert "Bronze League" in result
        assert "250 XP" in result


class TestSeasonRewardModel:
    """Tests for the SeasonReward model."""

    def test_reward_creation(self, leagues, active_season, league_user):
        """Test creating a season reward."""
        reward = SeasonReward.objects.create(
            season=active_season,
            user=league_user,
            league_achieved=leagues["gold"],
        )
        assert reward.rewards_claimed is False
        assert reward.claimed_at is None

    def test_reward_claim(self, leagues, active_season, league_user):
        """Test claiming a season reward."""
        reward = SeasonReward.objects.create(
            season=active_season,
            user=league_user,
            league_achieved=leagues["gold"],
        )
        result = reward.claim()
        assert result is True
        assert reward.rewards_claimed is True
        assert reward.claimed_at is not None

    def test_reward_double_claim(self, leagues, active_season, league_user):
        """Test that claiming an already-claimed reward returns False."""
        reward = SeasonReward.objects.create(
            season=active_season,
            user=league_user,
            league_achieved=leagues["gold"],
        )
        reward.claim()
        result = reward.claim()
        assert result is False

    def test_reward_unique_season_user(self, leagues, active_season, league_user):
        """Test that a user can only have one reward per season."""
        SeasonReward.objects.create(
            season=active_season,
            user=league_user,
            league_achieved=leagues["gold"],
        )
        with pytest.raises(Exception):
            SeasonReward.objects.create(
                season=active_season,
                user=league_user,
                league_achieved=leagues["silver"],
            )


# ---------------------------------------------------------------------------
# Service Tests
# ---------------------------------------------------------------------------


class TestLeagueService:
    """Tests for the LeagueService class."""

    def test_get_user_league_bronze(self, leagues, league_user):
        """Test league assignment for 0 XP (Bronze)."""
        league_user.xp = 0
        league = LeagueService.get_user_league(league_user)
        assert league.tier == "bronze"

    def test_get_user_league_silver(self, leagues, league_user):
        """Test league assignment for 500 XP (Silver)."""
        league_user.xp = 500
        league = LeagueService.get_user_league(league_user)
        assert league.tier == "silver"

    def test_get_user_league_gold(self, leagues, league_user):
        """Test league assignment for 1500 XP (Gold)."""
        league_user.xp = 1500
        league = LeagueService.get_user_league(league_user)
        assert league.tier == "gold"

    def test_get_user_league_platinum(self, leagues, league_user):
        """Test league assignment for 3500 XP (Platinum)."""
        league_user.xp = 3500
        league = LeagueService.get_user_league(league_user)
        assert league.tier == "platinum"

    def test_get_user_league_diamond(self, leagues, league_user):
        """Test league assignment for 7000 XP (Diamond)."""
        league_user.xp = 7000
        league = LeagueService.get_user_league(league_user)
        assert league.tier == "diamond"

    def test_get_user_league_master(self, leagues, league_user):
        """Test league assignment for 12000 XP (Master)."""
        league_user.xp = 12000
        league = LeagueService.get_user_league(league_user)
        assert league.tier == "master"

    def test_get_user_league_legend(self, leagues, league_user):
        """Test league assignment for 20000+ XP (Legend)."""
        league_user.xp = 25000
        league = LeagueService.get_user_league(league_user)
        assert league.tier == "legend"

    def test_get_user_league_boundary_499(self, leagues, league_user):
        """Test league assignment at exact boundary (499 XP = Bronze)."""
        league_user.xp = 499
        league = LeagueService.get_user_league(league_user)
        assert league.tier == "bronze"

    def test_get_user_league_boundary_500(self, leagues, league_user):
        """Test league assignment at exact boundary (500 XP = Silver)."""
        league_user.xp = 500
        league = LeagueService.get_user_league(league_user)
        assert league.tier == "silver"

    def test_get_user_league_no_leagues(self, db, league_user):
        """Test get_user_league when no leagues exist."""
        league = LeagueService.get_user_league(league_user)
        assert league is None

    def test_update_standing_creates_new(self, leagues, active_season, league_user):
        """Test that update_standing creates a new standing if none exists."""
        league_user.xp = 600
        standing = LeagueService.update_standing(league_user)
        assert standing is not None
        assert standing.league.tier == "silver"
        assert standing.xp_earned_this_season == 600

    def test_update_standing_updates_existing(
        self, leagues, active_season, league_user
    ):
        """Test that update_standing updates an existing standing."""
        league_user.xp = 100
        LeagueService.update_standing(league_user)

        league_user.xp = 600
        standing = LeagueService.update_standing(league_user)
        assert standing.league.tier == "silver"
        assert standing.xp_earned_this_season == 600

    def test_update_standing_no_active_season(self, leagues, league_user):
        """Test update_standing returns None when no active season."""
        result = LeagueService.update_standing(league_user)
        assert result is None

    def test_update_standing_recalculates_ranks(
        self, leagues, active_season, multiple_league_users
    ):
        """Test that ranks are recalculated after standing updates."""
        for user in multiple_league_users:
            LeagueService.update_standing(user)

        standings = LeagueStanding.objects.filter(season=active_season).order_by("rank")

        # Verify ranks are sequential starting from 1
        for i, standing in enumerate(standings, start=1):
            assert standing.rank == i

        # Verify the highest XP user has rank 1
        top_standing = standings.first()
        assert top_standing.xp_earned_this_season == max(
            u.xp for u in multiple_league_users
        )

    def test_get_leaderboard_global(
        self, leagues, active_season, multiple_league_users
    ):
        """Test global leaderboard returns users sorted by XP."""
        for user in multiple_league_users:
            LeagueService.update_standing(user)

        entries = LeagueService.get_leaderboard(limit=100)
        assert len(entries) == len(multiple_league_users)
        assert entries[0]["xp"] >= entries[-1]["xp"]

    def test_get_leaderboard_with_limit(
        self, leagues, active_season, multiple_league_users
    ):
        """Test leaderboard respects the limit parameter."""
        for user in multiple_league_users:
            LeagueService.update_standing(user)

        entries = LeagueService.get_leaderboard(limit=3)
        assert len(entries) == 3

    def test_get_leaderboard_by_league(
        self, leagues, active_season, multiple_league_users
    ):
        """Test leaderboard filtered to a specific league."""
        for user in multiple_league_users:
            LeagueService.update_standing(user)

        entries = LeagueService.get_leaderboard(league=leagues["bronze"], limit=100)
        for entry in entries:
            assert entry["league_tier"] == "bronze"

    def test_get_leaderboard_no_active_season(self, leagues):
        """Test leaderboard returns empty list when no active season."""
        entries = LeagueService.get_leaderboard()
        assert entries == []

    def test_promote_demote_users(self, leagues, active_season, multiple_league_users):
        """Test promotion and demotion of users."""
        # First, create standings for all users
        for user in multiple_league_users:
            LeagueService.update_standing(user)

        # Manually set a user's league to be wrong (simulating they were
        # in a lower league before gaining XP)
        user_with_high_xp = [u for u in multiple_league_users if u.xp == 25000][0]
        standing = LeagueStanding.objects.get(
            user=user_with_high_xp, season=active_season
        )
        standing.league = leagues["bronze"]
        standing.save()

        result = LeagueService.promote_demote_users()
        assert result["promoted"] >= 1

        # Verify the user was promoted back to legend
        standing.refresh_from_db()
        assert standing.league.tier == "legend"

    def test_calculate_season_rewards(self, leagues, league_user):
        """Test season reward calculation for an ended season."""
        now = django_timezone.now()
        ended_season = Season.objects.create(
            name="Ended Season",
            start_date=now - timedelta(days=100),
            end_date=now - timedelta(days=1),
            is_active=True,
        )

        LeagueStanding.objects.create(
            user=league_user,
            league=leagues["gold"],
            season=ended_season,
            rank=1,
            xp_earned_this_season=2000,
        )

        count = LeagueService.calculate_season_rewards(ended_season)
        assert count == 1

        reward = SeasonReward.objects.get(user=league_user, season=ended_season)
        assert reward.league_achieved.tier == "gold"
        assert reward.rewards_claimed is False

        # Season should be deactivated
        ended_season.refresh_from_db()
        assert ended_season.is_active is False

    def test_calculate_season_rewards_not_ended(self, active_season):
        """Test that rewards cannot be calculated for active season."""
        count = LeagueService.calculate_season_rewards(active_season)
        assert count == 0

    def test_get_nearby_ranks(self, leagues, active_season, multiple_league_users):
        """Test getting users ranked near the current user."""
        for user in multiple_league_users:
            LeagueService.update_standing(user)

        # Pick a user in the middle of the ranking
        mid_user = multiple_league_users[3]
        result = LeagueService.get_nearby_ranks(mid_user, count=2)

        assert result["current"] is not None
        assert result["current"]["is_current_user"] is True
        assert result["current"]["user_id"] == mid_user.id

    def test_get_nearby_ranks_no_season(self, leagues, league_user):
        """Test nearby ranks returns empty when no active season."""
        result = LeagueService.get_nearby_ranks(league_user)
        assert result["current"] is None
        assert result["above"] == []
        assert result["below"] == []

    def test_get_nearby_ranks_no_standing(self, leagues, active_season, league_user):
        """Test nearby ranks when user has no standing."""
        result = LeagueService.get_nearby_ranks(league_user)
        assert result["current"] is None

    def test_increment_tasks_completed(self, leagues, active_season, league_user):
        """Test incrementing tasks_completed counter."""
        league_user.xp = 100
        LeagueService.update_standing(league_user)

        LeagueService.increment_tasks_completed(league_user)

        standing = LeagueStanding.objects.get(user=league_user, season=active_season)
        assert standing.tasks_completed == 1

    def test_increment_dreams_completed(self, leagues, active_season, league_user):
        """Test incrementing dreams_completed counter."""
        league_user.xp = 100
        LeagueService.update_standing(league_user)

        LeagueService.increment_dreams_completed(league_user)

        standing = LeagueStanding.objects.get(user=league_user, season=active_season)
        assert standing.dreams_completed == 1


# ---------------------------------------------------------------------------
# View / API Tests
# ---------------------------------------------------------------------------


class TestLeagueViewSet:
    """Tests for the League API endpoints."""

    def test_list_leagues(self, authenticated_league_client, leagues):
        """Test listing all leagues."""
        response = authenticated_league_client.get("/api/leagues/leagues/")
        assert response.status_code == 200
        assert len(response.data) == 7

    def test_list_leagues_ordered(self, authenticated_league_client, leagues):
        """Test that leagues are returned in order of min_xp."""
        response = authenticated_league_client.get("/api/leagues/leagues/")
        tiers = [entry["tier"] for entry in response.data]
        assert tiers == [
            "bronze",
            "silver",
            "gold",
            "platinum",
            "diamond",
            "master",
            "legend",
        ]

    def test_retrieve_league(self, authenticated_league_client, leagues):
        """Test retrieving a single league."""
        league_id = str(leagues["gold"].id)
        response = authenticated_league_client.get(f"/api/leagues/leagues/{league_id}/")
        assert response.status_code == 200
        assert response.data["tier"] == "gold"
        assert response.data["min_xp"] == 1500

    def test_leagues_unauthenticated(self, leagues):
        """Test that unauthenticated requests are rejected."""
        client = APIClient()
        response = client.get("/api/leagues/leagues/")
        assert response.status_code in [401, 403]


class TestLeaderboardViewSet:
    """Tests for the Leaderboard API endpoints."""

    def test_global_leaderboard(
        self, authenticated_league_client, leagues, active_season, multiple_league_users
    ):
        """Test the global leaderboard endpoint."""
        for user in multiple_league_users:
            LeagueService.update_standing(user)

        response = authenticated_league_client.get("/api/leagues/leaderboard/global/")
        assert response.status_code == 200
        assert len(response.data) == len(multiple_league_users)

    def test_global_leaderboard_with_limit(
        self, authenticated_league_client, leagues, active_season, multiple_league_users
    ):
        """Test global leaderboard with limit parameter."""
        for user in multiple_league_users:
            LeagueService.update_standing(user)

        response = authenticated_league_client.get(
            "/api/leagues/leaderboard/global/?limit=3"
        )
        assert response.status_code == 200
        assert len(response.data) == 3

    def test_league_leaderboard(
        self, authenticated_league_client, leagues, active_season, league_user
    ):
        """Test the league-specific leaderboard endpoint."""
        league_user.xp = 100
        LeagueService.update_standing(league_user)

        response = authenticated_league_client.get("/api/leagues/leaderboard/league/")
        assert response.status_code == 200

    def test_league_leaderboard_with_id(
        self, authenticated_league_client, leagues, active_season, multiple_league_users
    ):
        """Test league leaderboard filtered by league_id."""
        for user in multiple_league_users:
            LeagueService.update_standing(user)

        league_id = str(leagues["bronze"].id)
        response = authenticated_league_client.get(
            f"/api/leagues/leaderboard/league/?league_id={league_id}"
        )
        assert response.status_code == 200
        for entry in response.data:
            assert entry["league_tier"] == "bronze"

    def test_my_standing(
        self, authenticated_league_client, leagues, active_season, league_user
    ):
        """Test the my_standing endpoint."""
        league_user.xp = 750
        LeagueService.update_standing(league_user)

        response = authenticated_league_client.get("/api/leagues/leaderboard/me/")
        assert response.status_code == 200
        assert response.data["league_tier"] == "silver"
        assert response.data["xp_earned_this_season"] == 750

    def test_my_standing_creates_if_missing(
        self, authenticated_league_client, leagues, active_season, league_user
    ):
        """Test that my_standing creates a standing if user has none."""
        response = authenticated_league_client.get("/api/leagues/leaderboard/me/")
        assert response.status_code == 200

    def test_my_standing_no_active_season(self, authenticated_league_client, leagues):
        """Test my_standing returns 404 when no active season."""
        response = authenticated_league_client.get("/api/leagues/leaderboard/me/")
        assert response.status_code == 404

    def test_nearby_ranks(
        self,
        authenticated_league_client,
        leagues,
        active_season,
        league_user,
        multiple_league_users,
    ):
        """Test the nearby ranks endpoint."""
        league_user.xp = 750
        LeagueService.update_standing(league_user)
        for user in multiple_league_users:
            LeagueService.update_standing(user)

        response = authenticated_league_client.get(
            "/api/leagues/leaderboard/nearby/?count=3"
        )
        assert response.status_code == 200
        assert "current" in response.data
        assert "above" in response.data
        assert "below" in response.data

    def test_leaderboard_unauthenticated(self, leagues, active_season):
        """Test that unauthenticated leaderboard requests are rejected."""
        client = APIClient()
        response = client.get("/api/leagues/leaderboard/global/")
        assert response.status_code in [401, 403]


class TestSeasonViewSet:
    """Tests for the Season API endpoints."""

    def test_list_seasons(self, authenticated_league_client, active_season):
        """Test listing all seasons."""
        response = authenticated_league_client.get("/api/leagues/seasons/")
        assert response.status_code == 200
        assert len(response.data["results"]) >= 1

    def test_current_season(self, authenticated_league_client, active_season):
        """Test getting the current active season."""
        response = authenticated_league_client.get("/api/leagues/seasons/current/")
        assert response.status_code == 200
        assert response.data["is_active"] is True
        assert response.data["name"] == "Test Season 1"

    def test_current_season_none(self, authenticated_league_client):
        """Test current season returns 404 when none active."""
        response = authenticated_league_client.get("/api/leagues/seasons/current/")
        assert response.status_code == 404

    def test_past_seasons(
        self, authenticated_league_client, active_season, ended_season
    ):
        """Test listing past seasons."""
        response = authenticated_league_client.get("/api/leagues/seasons/past/")
        assert response.status_code == 200
        for season in response.data:
            assert season["is_active"] is False

    def test_claim_reward(self, authenticated_league_client, leagues, league_user):
        """Test claiming a season reward."""
        now = django_timezone.now()
        ended = Season.objects.create(
            name="Claimable Season",
            start_date=now - timedelta(days=100),
            end_date=now - timedelta(days=1),
            is_active=False,
        )
        SeasonReward.objects.create(
            season=ended,
            user=league_user,
            league_achieved=leagues["gold"],
        )

        response = authenticated_league_client.post(
            f"/api/leagues/seasons/{ended.id}/claim-reward/"
        )
        assert response.status_code == 200
        assert response.data["rewards_claimed"] is True

    def test_claim_reward_already_claimed(
        self, authenticated_league_client, leagues, league_user
    ):
        """Test claiming an already-claimed reward returns 400."""
        now = django_timezone.now()
        ended = Season.objects.create(
            name="Already Claimed Season",
            start_date=now - timedelta(days=100),
            end_date=now - timedelta(days=1),
            is_active=False,
        )
        reward = SeasonReward.objects.create(
            season=ended,
            user=league_user,
            league_achieved=leagues["gold"],
        )
        reward.claim()

        response = authenticated_league_client.post(
            f"/api/leagues/seasons/{ended.id}/claim-reward/"
        )
        assert response.status_code == 400

    def test_claim_reward_active_season(
        self, authenticated_league_client, active_season
    ):
        """Test claiming reward for active season returns 400."""
        response = authenticated_league_client.post(
            f"/api/leagues/seasons/{active_season.id}/claim-reward/"
        )
        assert response.status_code == 400

    def test_my_rewards(self, authenticated_league_client, leagues, league_user):
        """Test listing user's season rewards."""
        now = django_timezone.now()
        ended = Season.objects.create(
            name="Reward Season",
            start_date=now - timedelta(days=100),
            end_date=now - timedelta(days=1),
            is_active=False,
        )
        SeasonReward.objects.create(
            season=ended,
            user=league_user,
            league_achieved=leagues["silver"],
        )

        response = authenticated_league_client.get("/api/leagues/seasons/my-rewards/")
        assert response.status_code == 200
        assert len(response.data) >= 1


# ---------------------------------------------------------------------------
# Signal Tests
# ---------------------------------------------------------------------------


class TestLeagueSignals:
    """Tests for signal-driven league standing updates."""

    def test_xp_change_triggers_standing_update(
        self, leagues, active_season, league_user
    ):
        """Test that changing user XP triggers a standing update via signal."""
        # The signal should fire when we save the user with new XP
        league_user.xp = 1600
        league_user.save(update_fields=["xp"])

        standing = LeagueStanding.objects.filter(
            user=league_user, season=active_season
        ).first()

        assert standing is not None
        assert standing.league.tier == "gold"
        assert standing.xp_earned_this_season == 1600

    def test_no_update_when_xp_unchanged(self, leagues, active_season, league_user):
        """Test that saving without XP change does not trigger update."""
        initial_count = LeagueStanding.objects.count()
        league_user.display_name = "New Name"
        league_user.save(update_fields=["display_name"])

        # No standing should have been created since XP didn't change
        # (user starts at 0 XP, and we're not creating a new user)
        assert LeagueStanding.objects.count() == initial_count


# ---------------------------------------------------------------------------
# Leaderboard Query Performance Tests
# ---------------------------------------------------------------------------


class TestLeaderboardQueries:
    """Tests to verify leaderboard query correctness and indexing."""

    def test_leaderboard_sorted_descending_xp(
        self, leagues, active_season, multiple_league_users
    ):
        """Test that leaderboard is sorted by XP descending."""
        for user in multiple_league_users:
            LeagueService.update_standing(user)

        entries = LeagueService.get_leaderboard(limit=100)
        xp_values = [e["xp"] for e in entries]
        assert xp_values == sorted(xp_values, reverse=True)

    def test_leaderboard_ranks_sequential(
        self, leagues, active_season, multiple_league_users
    ):
        """Test that ranks are sequential starting from 1."""
        for user in multiple_league_users:
            LeagueService.update_standing(user)

        entries = LeagueService.get_leaderboard(limit=100)
        ranks = [e["rank"] for e in entries]
        assert ranks == list(range(1, len(entries) + 1))

    def test_league_filter_correctness(
        self, leagues, active_season, multiple_league_users
    ):
        """Test that league filter returns only users in that league."""
        for user in multiple_league_users:
            LeagueService.update_standing(user)

        for tier_name, league in leagues.items():
            entries = LeagueService.get_leaderboard(league=league, limit=100)
            for entry in entries:
                assert entry["league_tier"] == tier_name

    def test_badges_count_included(
        self, leagues, active_season, league_user_with_gamification
    ):
        """Test that badges count is included in leaderboard entries."""
        league_user_with_gamification.xp = 100
        LeagueService.update_standing(league_user_with_gamification)

        entries = LeagueService.get_leaderboard(limit=100)
        assert len(entries) >= 1

        # Find our user
        user_entry = None
        for entry in entries:
            if entry["user_id"] == league_user_with_gamification.id:
                user_entry = entry
                break

        assert user_entry is not None
        assert user_entry["badges_count"] == 2  # 'early_bird' and 'streak_7'


# ---------------------------------------------------------------------------
# SeasonConfig Model Tests
# ---------------------------------------------------------------------------


class TestSeasonConfigModel:
    """Tests for the SeasonConfig singleton model."""

    def test_get_creates_singleton(self, db):
        """SeasonConfig.get() creates and returns a singleton."""
        from apps.leagues.models import SeasonConfig

        config = SeasonConfig.get()
        assert config is not None
        assert config.season_duration_days == 180
        assert config.group_target_size == 20
        assert config.group_max_size == 30
        assert config.group_min_size == 5

    def test_get_returns_same_instance(self, db):
        """SeasonConfig.get() returns the same instance on repeated calls."""
        from apps.leagues.models import SeasonConfig

        config1 = SeasonConfig.get()
        config2 = SeasonConfig.get()
        assert config1.pk == config2.pk

    def test_str_representation(self, db):
        from apps.leagues.models import SeasonConfig

        config = SeasonConfig.get()
        result = str(config)
        assert "180d" in result
        assert "20" in result
        assert "30" in result

    def test_save_invalidates_cache(self, db):
        """Saving SeasonConfig invalidates the cache."""
        from django.core.cache import cache

        from apps.leagues.models import SeasonConfig

        config = SeasonConfig.get()
        config.season_duration_days = 90
        config.save()

        # Cache should be invalidated
        assert cache.get("season_config_singleton") is None

        # Re-fetch should return updated value
        config2 = SeasonConfig.get()
        assert config2.season_duration_days == 90

    def test_default_values(self, db):
        from apps.leagues.models import SeasonConfig

        config = SeasonConfig.get()
        assert config.promotion_xp_threshold == 1000
        assert config.relegation_xp_threshold == 100
        assert config.auto_create_next_season is True


# ---------------------------------------------------------------------------
# LeagueGroup Model Tests
# ---------------------------------------------------------------------------


class TestLeagueGroupModel:
    """Tests for the LeagueGroup model."""

    def test_create_group(self, leagues, active_season):
        from apps.leagues.models import LeagueGroup

        group = LeagueGroup.objects.create(
            season=active_season,
            league=leagues["bronze"],
            group_number=1,
        )
        assert group.pk is not None
        assert group.is_active is True

    def test_group_str(self, leagues, active_season):
        from apps.leagues.models import LeagueGroup

        group = LeagueGroup.objects.create(
            season=active_season,
            league=leagues["gold"],
            group_number=3,
        )
        result = str(group)
        assert "Gold League" in result
        assert "Group #3" in result
        assert active_season.name in result

    def test_member_count_empty(self, leagues, active_season):
        from apps.leagues.models import LeagueGroup

        group = LeagueGroup.objects.create(
            season=active_season,
            league=leagues["bronze"],
            group_number=1,
        )
        assert group.member_count == 0

    def test_member_count_with_members(
        self, leagues, active_season, league_user
    ):
        from apps.leagues.models import (
            LeagueGroup,
            LeagueGroupMembership,
            LeagueStanding,
        )

        group = LeagueGroup.objects.create(
            season=active_season,
            league=leagues["bronze"],
            group_number=1,
        )
        standing = LeagueStanding.objects.create(
            user=league_user,
            league=leagues["bronze"],
            season=active_season,
            rank=1,
        )
        LeagueGroupMembership.objects.create(
            group=group,
            standing=standing,
        )
        assert group.member_count == 1

    def test_unique_group_constraint(self, leagues, active_season):
        """Cannot create two groups with the same season+league+number."""
        from apps.leagues.models import LeagueGroup

        LeagueGroup.objects.create(
            season=active_season,
            league=leagues["bronze"],
            group_number=1,
        )
        with pytest.raises(Exception):
            LeagueGroup.objects.create(
                season=active_season,
                league=leagues["bronze"],
                group_number=1,
            )


# ---------------------------------------------------------------------------
# LeagueGroupMembership Model Tests
# ---------------------------------------------------------------------------


class TestLeagueGroupMembershipModel:
    """Tests for the LeagueGroupMembership model."""

    def test_create_membership(self, leagues, active_season, league_user):
        from apps.leagues.models import (
            LeagueGroup,
            LeagueGroupMembership,
            LeagueStanding,
        )

        group = LeagueGroup.objects.create(
            season=active_season,
            league=leagues["silver"],
            group_number=1,
        )
        standing = LeagueStanding.objects.create(
            user=league_user,
            league=leagues["silver"],
            season=active_season,
            rank=1,
            xp_earned_this_season=600,
        )
        membership = LeagueGroupMembership.objects.create(
            group=group,
            standing=standing,
        )
        assert membership.pk is not None
        assert membership.promoted_from_group is None

    def test_one_to_one_standing(self, leagues, active_season, league_user):
        """A standing can only belong to one group."""
        from apps.leagues.models import (
            LeagueGroup,
            LeagueGroupMembership,
            LeagueStanding,
        )

        group1 = LeagueGroup.objects.create(
            season=active_season,
            league=leagues["bronze"],
            group_number=1,
        )
        group2 = LeagueGroup.objects.create(
            season=active_season,
            league=leagues["bronze"],
            group_number=2,
        )
        standing = LeagueStanding.objects.create(
            user=league_user,
            league=leagues["bronze"],
            season=active_season,
        )
        LeagueGroupMembership.objects.create(group=group1, standing=standing)
        with pytest.raises(Exception):
            LeagueGroupMembership.objects.create(
                group=group2, standing=standing
            )

    def test_membership_str(self, leagues, active_season, league_user):
        from apps.leagues.models import (
            LeagueGroup,
            LeagueGroupMembership,
            LeagueStanding,
        )

        group = LeagueGroup.objects.create(
            season=active_season,
            league=leagues["bronze"],
            group_number=1,
        )
        standing = LeagueStanding.objects.create(
            user=league_user,
            league=leagues["bronze"],
            season=active_season,
            rank=5,
            xp_earned_this_season=200,
        )
        membership = LeagueGroupMembership.objects.create(
            group=group, standing=standing
        )
        result = str(membership)
        assert "Bronze League" in result or "Group" in result

    def test_promotion_tracking(self, leagues, active_season, league_user):
        """Membership tracks which group the user was promoted from."""
        from apps.leagues.models import (
            LeagueGroup,
            LeagueGroupMembership,
            LeagueStanding,
        )

        old_group = LeagueGroup.objects.create(
            season=active_season,
            league=leagues["bronze"],
            group_number=1,
        )
        new_group = LeagueGroup.objects.create(
            season=active_season,
            league=leagues["silver"],
            group_number=1,
        )
        standing = LeagueStanding.objects.create(
            user=league_user,
            league=leagues["silver"],
            season=active_season,
        )
        membership = LeagueGroupMembership.objects.create(
            group=new_group,
            standing=standing,
            promoted_from_group=old_group,
        )
        assert membership.promoted_from_group == old_group


# ---------------------------------------------------------------------------
# RankSnapshot Model Tests
# ---------------------------------------------------------------------------


class TestRankSnapshotModel:
    """Tests for the RankSnapshot model."""

    def test_create_snapshot(self, leagues, active_season, league_user):
        from apps.leagues.models import RankSnapshot

        today = django_timezone.now().date()
        snapshot = RankSnapshot.objects.create(
            user=league_user,
            season=active_season,
            league=leagues["bronze"],
            rank=5,
            xp=250,
            snapshot_date=today,
        )
        assert snapshot.pk is not None
        assert snapshot.rank == 5
        assert snapshot.xp == 250

    def test_snapshot_str(self, leagues, active_season, league_user):
        from apps.leagues.models import RankSnapshot

        today = django_timezone.now().date()
        snapshot = RankSnapshot.objects.create(
            user=league_user,
            season=active_season,
            league=leagues["bronze"],
            rank=3,
            xp=400,
            snapshot_date=today,
        )
        result = str(snapshot)
        assert "Rank #3" in result
        assert str(today) in result

    def test_snapshot_unique_user_season_date(
        self, leagues, active_season, league_user
    ):
        """One snapshot per user+season+date."""
        from apps.leagues.models import RankSnapshot

        today = django_timezone.now().date()
        RankSnapshot.objects.create(
            user=league_user,
            season=active_season,
            league=leagues["bronze"],
            rank=1,
            xp=100,
            snapshot_date=today,
        )
        with pytest.raises(Exception):
            RankSnapshot.objects.create(
                user=league_user,
                season=active_season,
                league=leagues["bronze"],
                rank=2,
                xp=200,
                snapshot_date=today,
            )

    def test_snapshot_different_dates_allowed(
        self, leagues, active_season, league_user
    ):
        from apps.leagues.models import RankSnapshot

        today = django_timezone.now().date()
        from datetime import timedelta

        RankSnapshot.objects.create(
            user=league_user,
            season=active_season,
            league=leagues["bronze"],
            rank=5,
            xp=100,
            snapshot_date=today,
        )
        RankSnapshot.objects.create(
            user=league_user,
            season=active_season,
            league=leagues["bronze"],
            rank=4,
            xp=150,
            snapshot_date=today - timedelta(days=1),
        )
        assert (
            RankSnapshot.objects.filter(
                user=league_user, season=active_season
            ).count()
            == 2
        )

    def test_snapshot_ordering(self, leagues, active_season, league_user):
        """Snapshots ordered by -snapshot_date."""
        from apps.leagues.models import RankSnapshot

        today = django_timezone.now().date()
        from datetime import timedelta

        s1 = RankSnapshot.objects.create(
            user=league_user,
            season=active_season,
            league=leagues["bronze"],
            rank=5,
            xp=100,
            snapshot_date=today - timedelta(days=1),
        )
        s2 = RankSnapshot.objects.create(
            user=league_user,
            season=active_season,
            league=leagues["bronze"],
            rank=4,
            xp=200,
            snapshot_date=today,
        )
        snapshots = list(
            RankSnapshot.objects.filter(
                user=league_user, season=active_season
            )
        )
        assert snapshots[0] == s2  # Most recent first


# ---------------------------------------------------------------------------
# LeagueSeason Model Tests
# ---------------------------------------------------------------------------


class TestLeagueSeasonModel:
    """Tests for the LeagueSeason model."""

    def test_create_league_season(self, db):
        from apps.leagues.models import LeagueSeason

        today = django_timezone.now().date()
        season = LeagueSeason.objects.create(
            name="Season of Growth - Spring 2026",
            theme="growth",
            description="A season focused on personal growth.",
            start_date=today,
            end_date=today + timedelta(days=90),
            is_active=True,
            rewards=[
                {"rank_min": 1, "rank_max": 3, "reward_type": "badge", "reward_id": "gold_crown"},
            ],
            theme_colors={"primary": "#4CAF50", "secondary": "#81C784", "accent": "#A5D6A7"},
        )
        assert season.pk is not None
        assert season.is_active is True
        assert season.theme == "growth"

    def test_league_season_str(self, db):
        from apps.leagues.models import LeagueSeason

        today = django_timezone.now().date()
        season = LeagueSeason.objects.create(
            name="Fire Season",
            theme="fire",
            start_date=today,
            end_date=today + timedelta(days=60),
            is_active=True,
        )
        result = str(season)
        assert "Fire Season" in result
        assert "Active" in result

    def test_is_current_property(self, db):
        from apps.leagues.models import LeagueSeason

        today = django_timezone.now().date()
        season = LeagueSeason.objects.create(
            name="Current Season",
            start_date=today - timedelta(days=5),
            end_date=today + timedelta(days=50),
            is_active=True,
        )
        assert season.is_current is True

    def test_has_ended_property(self, db):
        from apps.leagues.models import LeagueSeason

        today = django_timezone.now().date()
        ended = LeagueSeason.objects.create(
            name="Ended Season",
            start_date=today - timedelta(days=100),
            end_date=today - timedelta(days=10),
            is_active=False,
        )
        assert ended.has_ended is True

        active = LeagueSeason.objects.create(
            name="Active Season",
            start_date=today - timedelta(days=5),
            end_date=today + timedelta(days=50),
            is_active=True,
        )
        assert active.has_ended is False

    def test_days_remaining(self, db):
        from apps.leagues.models import LeagueSeason

        today = django_timezone.now().date()
        season = LeagueSeason.objects.create(
            name="Days Test",
            start_date=today,
            end_date=today + timedelta(days=30),
            is_active=True,
        )
        assert season.days_remaining > 0
        assert season.days_remaining <= 30

    def test_days_remaining_ended(self, db):
        from apps.leagues.models import LeagueSeason

        today = django_timezone.now().date()
        season = LeagueSeason.objects.create(
            name="Ended Days",
            start_date=today - timedelta(days=60),
            end_date=today - timedelta(days=1),
            is_active=False,
        )
        assert season.days_remaining == 0

    def test_get_active_league_season(self, db):
        from apps.leagues.models import LeagueSeason

        today = django_timezone.now().date()
        season = LeagueSeason.objects.create(
            name="Active LS",
            start_date=today,
            end_date=today + timedelta(days=90),
            is_active=True,
        )
        result = LeagueSeason.get_active_league_season()
        assert result is not None
        assert result.pk == season.pk

    def test_get_active_league_season_none(self, db):
        from django.core.cache import cache

        from apps.leagues.models import LeagueSeason

        cache.delete("active_league_season")
        LeagueSeason.objects.filter(is_active=True).delete()
        result = LeagueSeason.get_active_league_season()
        assert result is None

    def test_get_reward_for_rank(self, db):
        from apps.leagues.models import LeagueSeason

        today = django_timezone.now().date()
        season = LeagueSeason.objects.create(
            name="Reward Season",
            start_date=today,
            end_date=today + timedelta(days=60),
            rewards=[
                {"rank_min": 1, "rank_max": 3, "reward_type": "badge", "title": "Top 3"},
                {"rank_min": 4, "rank_max": 10, "reward_type": "xp", "title": "Top 10"},
            ],
        )
        reward = season.get_reward_for_rank(1)
        assert reward is not None
        assert reward["title"] == "Top 3"

        reward = season.get_reward_for_rank(5)
        assert reward is not None
        assert reward["title"] == "Top 10"

        reward = season.get_reward_for_rank(11)
        assert reward is None

    def test_theme_choices(self, db):
        from apps.leagues.models import LeagueSeason

        today = django_timezone.now().date()
        for theme, _ in LeagueSeason.THEME_CHOICES:
            season = LeagueSeason(
                name=f"Theme {theme}",
                theme=theme,
                start_date=today,
                end_date=today + timedelta(days=30),
            )
            assert season.theme == theme


# ---------------------------------------------------------------------------
# SeasonParticipant Model Tests
# ---------------------------------------------------------------------------


class TestSeasonParticipantModel:
    """Tests for the SeasonParticipant model."""

    @pytest.fixture
    def league_season(self, db):
        from apps.leagues.models import LeagueSeason

        today = django_timezone.now().date()
        return LeagueSeason.objects.create(
            name="Participant Test Season",
            start_date=today,
            end_date=today + timedelta(days=90),
            is_active=True,
        )

    def test_create_participant(self, league_season, league_user):
        from apps.leagues.models import SeasonParticipant

        participant = SeasonParticipant.objects.create(
            season=league_season,
            user=league_user,
            xp_earned=500,
        )
        assert participant.pk is not None
        assert participant.xp_earned == 500
        assert participant.rank is None
        assert participant.rewards_claimed is False

    def test_participant_str(self, league_season, league_user):
        from apps.leagues.models import SeasonParticipant

        participant = SeasonParticipant.objects.create(
            season=league_season,
            user=league_user,
            xp_earned=1000,
            rank=5,
        )
        result = str(participant)
        assert "Rank #5" in result
        assert "1000 XP" in result

    def test_participant_str_unranked(self, league_season, league_user):
        from apps.leagues.models import SeasonParticipant

        participant = SeasonParticipant.objects.create(
            season=league_season,
            user=league_user,
        )
        result = str(participant)
        assert "Unranked" in result

    def test_claim_rewards(self, league_season, league_user):
        from apps.leagues.models import SeasonParticipant

        participant = SeasonParticipant.objects.create(
            season=league_season,
            user=league_user,
            rank=1,
        )
        result = participant.claim_rewards()
        assert result is True
        assert participant.rewards_claimed is True

    def test_claim_rewards_double(self, league_season, league_user):
        from apps.leagues.models import SeasonParticipant

        participant = SeasonParticipant.objects.create(
            season=league_season,
            user=league_user,
        )
        participant.claim_rewards()
        result = participant.claim_rewards()
        assert result is False

    def test_unique_season_user(self, league_season, league_user):
        """A user can only participate once per season."""
        from apps.leagues.models import SeasonParticipant

        SeasonParticipant.objects.create(
            season=league_season,
            user=league_user,
        )
        with pytest.raises(Exception):
            SeasonParticipant.objects.create(
                season=league_season,
                user=league_user,
            )

    def test_participant_ordering(self, league_season):
        """Participants ordered by -xp_earned."""
        from apps.leagues.models import SeasonParticipant

        u1 = User.objects.create(
            email=f"sp1_{uuid.uuid4().hex[:8]}@example.com",
            xp=100,
        )
        u2 = User.objects.create(
            email=f"sp2_{uuid.uuid4().hex[:8]}@example.com",
            xp=500,
        )
        SeasonParticipant.objects.create(
            season=league_season, user=u1, xp_earned=100
        )
        SeasonParticipant.objects.create(
            season=league_season, user=u2, xp_earned=500
        )
        participants = list(
            SeasonParticipant.objects.filter(season=league_season)
        )
        assert participants[0].xp_earned >= participants[1].xp_earned


# ---------------------------------------------------------------------------
# Season model – extended
# ---------------------------------------------------------------------------


class TestSeasonModelExtended:
    """Extended tests for the Season model."""

    def test_seconds_remaining(self, active_season):
        """Test seconds_remaining for active season."""
        assert active_season.seconds_remaining > 0

    def test_seconds_remaining_ended(self, ended_season):
        """Test seconds_remaining for ended season."""
        assert ended_season.seconds_remaining == 0

    def test_ends_at_alias(self, active_season):
        """Test ends_at property is an alias for end_date."""
        assert active_season.ends_at == active_season.end_date

    def test_season_save_syncs_is_active(self, db):
        """Saving with status='active' sets is_active=True."""
        now = django_timezone.now()
        season = Season.objects.create(
            name="Sync Test",
            start_date=now,
            end_date=now + timedelta(days=30),
            status="active",
        )
        assert season.is_active is True

        season.status = "ended"
        season.save()
        assert season.is_active is False

    def test_season_str_with_status(self, db):
        now = django_timezone.now()
        season = Season.objects.create(
            name="Status Test",
            start_date=now,
            end_date=now + timedelta(days=30),
            status="pending",
        )
        result = str(season)
        assert "Status Test" in result
        assert "Pending" in result


# ---------------------------------------------------------------------------
# League model – seed_defaults
# ---------------------------------------------------------------------------


class TestLeagueSeedDefaults:
    """Tests for League.seed_defaults classmethod."""

    def test_seed_defaults_creates_leagues(self, db):
        """seed_defaults creates all 7 tiers."""
        leagues = League.seed_defaults()
        assert len(leagues) == 7
        tiers = {l.tier for l in leagues}
        assert "bronze" in tiers
        assert "legend" in tiers

    def test_seed_defaults_idempotent(self, db):
        """Calling seed_defaults twice does not duplicate."""
        League.seed_defaults()
        League.seed_defaults()
        assert League.objects.count() == 7
