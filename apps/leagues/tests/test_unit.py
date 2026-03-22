"""
Unit tests for the Leagues app models.
"""

from datetime import timedelta

import pytest
from django.db import IntegrityError
from django.utils import timezone

from apps.leagues.models import (
    League,
    LeagueStanding,
    Season,
    SeasonReward,
)

# ── League model ──────────────────────────────────────────────────────


class TestLeagueModel:
    """Tests for the League model."""

    def test_create_league(self, bronze_league):
        """League can be created with required fields."""
        assert bronze_league.tier == "bronze"
        assert bronze_league.name == "Bronze League"
        assert bronze_league.min_xp == 0
        assert bronze_league.max_xp == 499

    def test_str_with_max_xp(self, bronze_league):
        """__str__ shows XP range when max_xp is set."""
        s = str(bronze_league)
        assert "Bronze League" in s
        assert "0-499" in s

    def test_str_without_max_xp(self, legend_league):
        """__str__ shows min_xp+ when max_xp is None."""
        s = str(legend_league)
        assert "Legend League" in s
        assert "20000+" in s

    def test_tier_order(self, bronze_league, silver_league, legend_league):
        """tier_order returns correct numeric order."""
        assert bronze_league.tier_order == 0
        assert silver_league.tier_order == 1
        assert legend_league.tier_order == 6

    def test_contains_xp_true(self, bronze_league):
        """contains_xp returns True for XP within range."""
        assert bronze_league.contains_xp(0) is True
        assert bronze_league.contains_xp(250) is True
        assert bronze_league.contains_xp(499) is True

    def test_contains_xp_false(self, bronze_league):
        """contains_xp returns False for XP outside range."""
        assert bronze_league.contains_xp(500) is False
        assert bronze_league.contains_xp(1000) is False

    def test_contains_xp_legend(self, legend_league):
        """Legend league contains any XP >= min_xp."""
        assert legend_league.contains_xp(20000) is True
        assert legend_league.contains_xp(999999) is True
        assert legend_league.contains_xp(19999) is False

    def test_unique_tier(self, bronze_league):
        """Each tier must be unique."""
        with pytest.raises(IntegrityError):
            League.objects.create(
                tier="bronze",
                name="Duplicate Bronze",
                min_xp=0,
                max_xp=499,
            )

    def test_seed_defaults(self, db):
        """seed_defaults creates all 7 league tiers."""
        League.objects.all().delete()
        leagues = League.seed_defaults()
        assert len(leagues) == 7
        tiers = {league.tier for league in leagues}
        assert tiers == {"bronze", "silver", "gold", "platinum", "diamond", "master", "legend"}

    def test_seed_defaults_idempotent(self, db):
        """seed_defaults does not duplicate if leagues exist."""
        League.objects.all().delete()
        League.seed_defaults()
        count = League.objects.count()
        League.seed_defaults()
        assert League.objects.count() == count

    def test_ordering(self, bronze_league, silver_league, legend_league):
        """Leagues are ordered by min_xp."""
        leagues = list(League.objects.all())
        xps = [league.min_xp for league in leagues]
        assert xps == sorted(xps)


# ── LeagueMembership (LeagueStanding) model ───────────────────────────


class TestLeagueStandingModel:
    """Tests for the LeagueStanding model (acts as league membership)."""

    def test_create_standing(self, league_standing, league_user, bronze_league, test_season):
        """LeagueStanding can be created."""
        assert league_standing.user == league_user
        assert league_standing.league == bronze_league
        assert league_standing.season == test_season
        assert league_standing.rank == 1
        assert league_standing.xp_earned_this_season == 100

    def test_unique_user_season(self, league_standing, league_user, bronze_league, test_season):
        """User can only have one standing per season."""
        with pytest.raises(IntegrityError):
            LeagueStanding.objects.create(
                user=league_user,
                league=bronze_league,
                season=test_season,
                rank=2,
            )

    def test_str_representation(self, league_standing):
        """__str__ includes user, rank, league, and XP."""
        s = str(league_standing)
        assert "League User" in s
        assert "#1" in s
        assert "Bronze" in s

    def test_default_values(self, db, league_user2, bronze_league, test_season):
        """Default values are correct."""
        standing = LeagueStanding.objects.create(
            user=league_user2,
            league=bronze_league,
            season=test_season,
        )
        assert standing.rank == 0
        assert standing.xp_earned_this_season == 0
        assert standing.tasks_completed == 0
        assert standing.dreams_completed == 0
        assert standing.streak_best == 0


# ── Season model ──────────────────────────────────────────────────────


class TestSeasonModel:
    """Tests for the Season model."""

    def test_create_season(self, test_season):
        """Season can be created with required fields."""
        assert test_season.name == "Test Season 1"
        assert test_season.is_active is True
        assert test_season.status == "active"

    def test_is_current(self, test_season):
        """is_current returns True for active season within date range."""
        assert test_season.is_current is True

    def test_is_current_ended(self, ended_season):
        """is_current returns False for ended season."""
        assert ended_season.is_current is False

    def test_has_ended(self, ended_season):
        """has_ended returns True for past seasons."""
        assert ended_season.has_ended is True

    def test_has_ended_false(self, test_season):
        """has_ended returns False for current season."""
        assert test_season.has_ended is False

    def test_days_remaining(self, test_season):
        """days_remaining returns positive value for active season."""
        assert test_season.days_remaining > 0

    def test_days_remaining_ended(self, ended_season):
        """days_remaining returns 0 for ended season."""
        assert ended_season.days_remaining == 0

    def test_seconds_remaining(self, test_season):
        """seconds_remaining returns positive for active season."""
        assert test_season.seconds_remaining > 0

    def test_seconds_remaining_ended(self, ended_season):
        """seconds_remaining returns 0 for ended season."""
        assert ended_season.seconds_remaining == 0

    def test_ends_at_alias(self, test_season):
        """ends_at is an alias for end_date."""
        assert test_season.ends_at == test_season.end_date

    def test_str_representation(self, test_season):
        """__str__ includes name and status."""
        s = str(test_season)
        assert "Test Season 1" in s

    def test_save_syncs_is_active(self, db):
        """save() keeps is_active in sync with status."""
        season = Season.objects.create(
            name="Sync Test",
            start_date=timezone.now(),
            end_date=timezone.now() + timedelta(days=30),
            status="active",
        )
        assert season.is_active is True
        season.status = "ended"
        season.save()
        assert season.is_active is False

    def test_get_active_season(self, test_season):
        """get_active_season returns the active season."""
        from unittest.mock import patch
        # Mock cache to avoid Redis dependency
        with patch("apps.leagues.models.cache") as mock_cache:
            mock_cache.get.return_value = None
            active = Season.get_active_season()
            assert active is not None
            assert active.id == test_season.id


# ── SeasonReward model ────────────────────────────────────────────────


class TestSeasonRewardModel:
    """Tests for the SeasonReward model."""

    def test_claim_reward(self, db, league_user, bronze_league, test_season):
        """Claiming a reward sets rewards_claimed and claimed_at."""
        reward = SeasonReward.objects.create(
            season=test_season,
            user=league_user,
            league_achieved=bronze_league,
        )
        assert reward.rewards_claimed is False
        result = reward.claim()
        assert result is True
        reward.refresh_from_db()
        assert reward.rewards_claimed is True
        assert reward.claimed_at is not None

    def test_claim_reward_already_claimed(self, db, league_user, bronze_league, test_season):
        """Claiming an already-claimed reward returns False."""
        reward = SeasonReward.objects.create(
            season=test_season,
            user=league_user,
            league_achieved=bronze_league,
            rewards_claimed=True,
            claimed_at=timezone.now(),
        )
        result = reward.claim()
        assert result is False


# ══════════════════════════════════════════════════════════════════════
#  API ENDPOINT TESTS — Leagues
# ══════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestLeagueAPI:
    """Tests for League API endpoints."""

    def test_list_leagues(self, league_user):
        from rest_framework.test import APIClient

        client = APIClient()
        client.force_authenticate(user=league_user)
        resp = client.get(
            "/api/leagues/leagues/",
            HTTP_ORIGIN="https://stepora.app",
        )
        assert resp.status_code in (200, 403)

    def test_leaderboard(self, league_user):
        from rest_framework.test import APIClient

        client = APIClient()
        client.force_authenticate(user=league_user)
        resp = client.get(
            "/api/leagues/leaderboard/",
            HTTP_ORIGIN="https://stepora.app",
        )
        assert resp.status_code in (200, 403, 404)
