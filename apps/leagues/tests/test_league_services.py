"""
Tests for apps.leagues.services — LeagueService business logic.

Covers: get_user_league, update_standing, _recalculate_ranks,
get_leaderboard, promote_demote_users, calculate_season_rewards,
get_nearby_ranks, increment_tasks/dreams_completed,
assign_user_to_group, rebalance_league_groups,
compute_season_end_promotions, create_next_season,
get_group_leaderboard.
"""

from datetime import timedelta
from unittest.mock import patch

import pytest
from django.utils import timezone

from apps.gamification.models import GamificationProfile
from apps.leagues.models import (
    League,
    LeagueGroup,
    LeagueGroupMembership,
    LeagueStanding,
    Season,
    SeasonConfig,
    SeasonReward,
)
from apps.leagues.services import LeagueService
from apps.users.models import User

# ── Helpers / Fixtures ────────────────────────────────────────────────


@pytest.fixture
def gold_league(db):
    league, _ = League.objects.get_or_create(
        tier="gold",
        defaults={
            "name": "Gold League",
            "min_xp": 1500,
            "max_xp": 3499,
            "color_hex": "#FFD700",
        },
    )
    return league


@pytest.fixture
def season_config(db):
    """Ensure a SeasonConfig singleton exists with known values."""
    from django.core.cache import cache

    cache.delete("season_config_singleton")
    config, _ = SeasonConfig.objects.get_or_create(
        pk=SeasonConfig.objects.values_list("pk", flat=True).first()
        or __import__("uuid").uuid4(),
        defaults={
            "group_target_size": 5,
            "group_max_size": 10,
            "promotion_xp_threshold": 1000,
            "relegation_xp_threshold": 100,
            "auto_create_next_season": True,
            "season_duration_days": 90,
        },
    )
    # Force known values regardless of whether it was just created
    config.group_target_size = 5
    config.group_max_size = 10
    config.promotion_xp_threshold = 1000
    config.relegation_xp_threshold = 100
    config.auto_create_next_season = True
    config.season_duration_days = 90
    config.save()
    return config


def _make_user(email, xp=0, display_name=None):
    u = User.objects.create_user(
        email=email,
        password="testpass123",
        display_name=display_name or email.split("@")[0],
    )
    u.xp = xp
    u.save(update_fields=["xp"])
    return u


# ══════════════════════════════════════════════════════════════════════
#  get_user_league
# ══════════════════════════════════════════════════════════════════════


class TestGetUserLeague:
    def test_exact_range_match(self, bronze_league, silver_league, gold_league):
        user = _make_user("bronze@test.com", xp=200)
        assert LeagueService.get_user_league(user) == bronze_league

    def test_silver_range(self, bronze_league, silver_league, gold_league):
        user = _make_user("silver@test.com", xp=700)
        assert LeagueService.get_user_league(user) == silver_league

    def test_top_league_no_max(self, bronze_league, legend_league):
        user = _make_user("legend@test.com", xp=50000)
        assert LeagueService.get_user_league(user) == legend_league

    def test_fallback_lowest_league(self, bronze_league, silver_league):
        """XP below any range still returns the lowest league."""
        user = _make_user("fallback@test.com", xp=0)
        result = LeagueService.get_user_league(user)
        assert result == bronze_league

    def test_no_leagues_returns_none(self, db):
        League.objects.all().delete()
        user = _make_user("noleg@test.com", xp=100)
        assert LeagueService.get_user_league(user) is None


# ══════════════════════════════════════════════════════════════════════
#  update_standing
# ══════════════════════════════════════════════════════════════════════


class TestUpdateStanding:
    def test_creates_new_standing(
        self, bronze_league, test_season, season_config
    ):
        user = _make_user("newstanding@test.com", xp=100)
        with patch("apps.leagues.models.cache") as mcache:
            mcache.get.return_value = test_season
            standing = LeagueService.update_standing(user)
        assert standing is not None
        assert standing.user == user
        assert standing.league == bronze_league

    def test_returns_none_without_active_season(self, bronze_league, db):
        user = _make_user("noseas@test.com", xp=100)
        with patch("apps.leagues.models.cache") as mcache:
            mcache.get.return_value = None
            standing = LeagueService.update_standing(user)
        assert standing is None

    def test_updates_existing_standing(
        self, bronze_league, silver_league, test_season, season_config
    ):
        user = _make_user("update@test.com", xp=100)
        with patch("apps.leagues.models.cache") as mcache:
            mcache.get.return_value = test_season
            LeagueService.update_standing(user)
            # Now boost XP to silver range
            user.xp = 700
            user.save(update_fields=["xp"])
            standing = LeagueService.update_standing(user)
        assert standing.league == silver_league
        assert standing.xp_earned_this_season == 700

    def test_streak_best_updated(
        self, bronze_league, test_season, season_config
    ):
        user = _make_user("streak@test.com", xp=100)
        user.streak_days = 10
        user.save(update_fields=["streak_days"])
        with patch("apps.leagues.models.cache") as mcache:
            mcache.get.return_value = test_season
            standing = LeagueService.update_standing(user)
        assert standing.streak_best >= 10


# ══════════════════════════════════════════════════════════════════════
#  _recalculate_ranks
# ══════════════════════════════════════════════════════════════════════


class TestRecalculateRanks:
    def test_dense_ranking(self, bronze_league, test_season):
        u1 = _make_user("rank1@test.com", xp=300)
        u2 = _make_user("rank2@test.com", xp=200)
        u3 = _make_user("rank3@test.com", xp=200)
        LeagueStanding.objects.create(
            user=u1, league=bronze_league, season=test_season,
            xp_earned_this_season=300, rank=0,
        )
        LeagueStanding.objects.create(
            user=u2, league=bronze_league, season=test_season,
            xp_earned_this_season=200, rank=0,
        )
        LeagueStanding.objects.create(
            user=u3, league=bronze_league, season=test_season,
            xp_earned_this_season=200, rank=0,
        )
        LeagueService._recalculate_ranks(test_season)
        s1 = LeagueStanding.objects.get(user=u1, season=test_season)
        s2 = LeagueStanding.objects.get(user=u2, season=test_season)
        s3 = LeagueStanding.objects.get(user=u3, season=test_season)
        assert s1.rank == 1
        # Tied users get the same dense rank
        assert s2.rank == s3.rank == 2


# ══════════════════════════════════════════════════════════════════════
#  get_leaderboard
# ══════════════════════════════════════════════════════════════════════


class TestGetLeaderboard:
    def test_empty_leaderboard_no_season(self, db):
        with patch("apps.leagues.models.cache") as mcache:
            mcache.get.return_value = None
            entries = LeagueService.get_leaderboard()
        assert entries == []

    def test_leaderboard_entries(self, bronze_league, test_season):
        u1 = _make_user("lb1@test.com", xp=300)
        u2 = _make_user("lb2@test.com", xp=200)
        LeagueStanding.objects.create(
            user=u1, league=bronze_league, season=test_season,
            xp_earned_this_season=300,
        )
        LeagueStanding.objects.create(
            user=u2, league=bronze_league, season=test_season,
            xp_earned_this_season=200,
        )
        entries = LeagueService.get_leaderboard(season=test_season)
        assert len(entries) == 2
        assert entries[0]["rank"] == 1
        assert entries[0]["xp"] == 300
        assert entries[1]["rank"] == 2

    def test_leaderboard_filtered_by_league(
        self, bronze_league, silver_league, test_season
    ):
        u1 = _make_user("filtlb1@test.com", xp=100)
        u2 = _make_user("filtlb2@test.com", xp=700)
        LeagueStanding.objects.create(
            user=u1, league=bronze_league, season=test_season,
            xp_earned_this_season=100,
        )
        LeagueStanding.objects.create(
            user=u2, league=silver_league, season=test_season,
            xp_earned_this_season=700,
        )
        entries = LeagueService.get_leaderboard(
            league=bronze_league, season=test_season
        )
        assert len(entries) == 1
        assert entries[0]["league_name"] == "Bronze League"

    def test_leaderboard_limit(self, bronze_league, test_season):
        for i in range(5):
            u = _make_user(f"lim{i}@test.com", xp=100 + i)
            LeagueStanding.objects.create(
                user=u, league=bronze_league, season=test_season,
                xp_earned_this_season=100 + i,
            )
        entries = LeagueService.get_leaderboard(season=test_season, limit=3)
        assert len(entries) == 3

    def test_leaderboard_entry_fields(self, bronze_league, test_season):
        u = _make_user("fields@test.com", xp=100)
        LeagueStanding.objects.create(
            user=u, league=bronze_league, season=test_season,
            xp_earned_this_season=100, tasks_completed=3,
        )
        entries = LeagueService.get_leaderboard(season=test_season)
        entry = entries[0]
        assert "rank" in entry
        assert "user_id" in entry
        assert "user_display_name" in entry
        assert "league_name" in entry
        assert "xp" in entry
        assert "badges_count" in entry
        assert entry["is_current_user"] is False

    def test_leaderboard_with_gamification_badges(
        self, bronze_league, test_season
    ):
        u = _make_user("badges@test.com", xp=100)
        # Signal auto-creates profile, so update it
        GamificationProfile.objects.update_or_create(
            user=u, defaults={"badges": ["badge1", "badge2"]}
        )
        LeagueStanding.objects.create(
            user=u, league=bronze_league, season=test_season,
            xp_earned_this_season=100,
        )
        entries = LeagueService.get_leaderboard(season=test_season)
        assert entries[0]["badges_count"] == 2


# ══════════════════════════════════════════════════════════════════════
#  promote_demote_users
# ══════════════════════════════════════════════════════════════════════


class TestPromoteDemoteUsers:
    def test_no_season_returns_zeros(self, db):
        with patch("apps.leagues.models.cache") as mcache:
            mcache.get.return_value = None
            result = LeagueService.promote_demote_users()
        assert result == {"promoted": 0, "demoted": 0}

    def test_user_promoted(
        self, bronze_league, silver_league, test_season
    ):
        # User in bronze but has enough XP for silver
        u = _make_user("promo@test.com", xp=700)
        LeagueStanding.objects.create(
            user=u, league=bronze_league, season=test_season,
            xp_earned_this_season=700,
        )
        with patch("apps.leagues.models.cache") as mcache:
            mcache.get.return_value = test_season
            result = LeagueService.promote_demote_users()
        assert result["promoted"] == 1
        standing = LeagueStanding.objects.get(user=u, season=test_season)
        assert standing.league == silver_league

    def test_user_demoted(
        self, bronze_league, silver_league, test_season
    ):
        # User in silver but XP dropped to bronze range
        u = _make_user("demo@test.com", xp=100)
        LeagueStanding.objects.create(
            user=u, league=silver_league, season=test_season,
            xp_earned_this_season=100,
        )
        with patch("apps.leagues.models.cache") as mcache:
            mcache.get.return_value = test_season
            result = LeagueService.promote_demote_users()
        assert result["demoted"] == 1
        standing = LeagueStanding.objects.get(user=u, season=test_season)
        assert standing.league == bronze_league

    def test_no_change(self, bronze_league, test_season):
        u = _make_user("nochange@test.com", xp=200)
        LeagueStanding.objects.create(
            user=u, league=bronze_league, season=test_season,
            xp_earned_this_season=200,
        )
        with patch("apps.leagues.models.cache") as mcache:
            mcache.get.return_value = test_season
            result = LeagueService.promote_demote_users()
        assert result == {"promoted": 0, "demoted": 0}


# ══════════════════════════════════════════════════════════════════════
#  calculate_season_rewards
# ══════════════════════════════════════════════════════════════════════


class TestCalculateSeasonRewards:
    def test_rewards_created_for_ended_season(
        self, bronze_league, ended_season
    ):
        u = _make_user("reward@test.com", xp=100)
        LeagueStanding.objects.create(
            user=u, league=bronze_league, season=ended_season,
            xp_earned_this_season=100,
        )
        count = LeagueService.calculate_season_rewards(ended_season)
        assert count == 1
        assert SeasonReward.objects.filter(
            season=ended_season, user=u
        ).exists()
        ended_season.refresh_from_db()
        assert ended_season.is_active is False

    def test_no_rewards_for_active_season(
        self, bronze_league, test_season
    ):
        count = LeagueService.calculate_season_rewards(test_season)
        assert count == 0

    def test_idempotent_rewards(self, bronze_league, ended_season):
        u = _make_user("idempotent@test.com", xp=100)
        LeagueStanding.objects.create(
            user=u, league=bronze_league, season=ended_season,
            xp_earned_this_season=100,
        )
        LeagueService.calculate_season_rewards(ended_season)
        # Re-activate for second call
        ended_season.is_active = False
        ended_season.save()
        count = LeagueService.calculate_season_rewards(ended_season)
        assert count == 0  # Already exists, not re-created
        assert SeasonReward.objects.filter(
            season=ended_season, user=u
        ).count() == 1


# ══════════════════════════════════════════════════════════════════════
#  get_nearby_ranks
# ══════════════════════════════════════════════════════════════════════


class TestGetNearbyRanks:
    def test_no_season(self, db):
        u = _make_user("nearby@test.com")
        with patch("apps.leagues.models.cache") as mcache:
            mcache.get.return_value = None
            result = LeagueService.get_nearby_ranks(u)
        assert result == {"above": [], "current": None, "below": []}

    def test_user_not_in_season(self, test_season):
        u = _make_user("notinseason@test.com")
        with patch("apps.leagues.models.cache") as mcache:
            mcache.get.return_value = test_season
            result = LeagueService.get_nearby_ranks(u)
        assert result["current"] is None

    def test_nearby_ranks_populated(self, bronze_league, test_season):
        users = []
        for i in range(5):
            u = _make_user(f"near{i}@test.com", xp=100 * (5 - i))
            LeagueStanding.objects.create(
                user=u, league=bronze_league, season=test_season,
                xp_earned_this_season=100 * (5 - i),
                rank=i + 1,
            )
            users.append(u)

        target = users[2]  # rank 3
        with patch("apps.leagues.models.cache") as mcache:
            mcache.get.return_value = test_season
            result = LeagueService.get_nearby_ranks(target, count=2)

        assert result["current"] is not None
        assert result["current"]["is_current_user"] is True
        assert len(result["above"]) > 0
        assert len(result["below"]) > 0


# ══════════════════════════════════════════════════════════════════════
#  increment_tasks_completed / increment_dreams_completed
# ══════════════════════════════════════════════════════════════════════


class TestIncrementCounters:
    def test_increment_tasks_completed(self, bronze_league, test_season):
        u = _make_user("inctask@test.com", xp=100)
        LeagueStanding.objects.create(
            user=u, league=bronze_league, season=test_season,
            xp_earned_this_season=100, tasks_completed=0,
        )
        with patch("apps.leagues.models.cache") as mcache:
            mcache.get.return_value = test_season
            LeagueService.increment_tasks_completed(u)
        standing = LeagueStanding.objects.get(user=u, season=test_season)
        assert standing.tasks_completed == 1

    def test_increment_dreams_completed(self, bronze_league, test_season):
        u = _make_user("incdream@test.com", xp=100)
        LeagueStanding.objects.create(
            user=u, league=bronze_league, season=test_season,
            xp_earned_this_season=100, dreams_completed=0,
        )
        with patch("apps.leagues.models.cache") as mcache:
            mcache.get.return_value = test_season
            LeagueService.increment_dreams_completed(u)
        standing = LeagueStanding.objects.get(user=u, season=test_season)
        assert standing.dreams_completed == 1

    def test_increment_no_season_noop(self, db):
        u = _make_user("noseasinc@test.com", xp=100)
        with patch("apps.leagues.models.cache") as mcache:
            mcache.get.return_value = None
            # Should not raise
            LeagueService.increment_tasks_completed(u)
            LeagueService.increment_dreams_completed(u)


# ══════════════════════════════════════════════════════════════════════
#  assign_user_to_group
# ══════════════════════════════════════════════════════════════════════


class TestAssignUserToGroup:
    """Tests for assign_user_to_group."""

    def test_creates_group_if_none_exists(
        self, bronze_league, test_season, season_config
    ):
        u = _make_user("assigngrp@test.com", xp=100)
        standing = LeagueStanding.objects.create(
            user=u, league=bronze_league, season=test_season,
            xp_earned_this_season=100,
        )
        membership = LeagueService.assign_user_to_group(
            standing, test_season, bronze_league
        )
        assert membership is not None
        assert membership.group.group_number == 1
        assert membership.group.league == bronze_league

    def test_assigns_to_existing_group_with_room(
        self, bronze_league, test_season, season_config
    ):
        # Create a group with space
        group = LeagueGroup.objects.create(
            season=test_season, league=bronze_league,
            group_number=1, is_active=True,
        )
        u = _make_user("existgrp@test.com", xp=100)
        standing = LeagueStanding.objects.create(
            user=u, league=bronze_league, season=test_season,
            xp_earned_this_season=100,
        )
        membership = LeagueService.assign_user_to_group(
            standing, test_season, bronze_league
        )
        assert membership.group == group

    def test_creates_new_group_when_full(
        self, bronze_league, test_season, season_config
    ):
        # Set max to 1 for testing
        season_config.group_max_size = 1
        season_config.save()

        group = LeagueGroup.objects.create(
            season=test_season, league=bronze_league,
            group_number=1, is_active=True,
        )
        # Fill the group
        u1 = _make_user("fill1@test.com", xp=100)
        s1 = LeagueStanding.objects.create(
            user=u1, league=bronze_league, season=test_season,
            xp_earned_this_season=100,
        )
        LeagueGroupMembership.objects.create(group=group, standing=s1)

        # Now assign another user
        u2 = _make_user("fill2@test.com", xp=200)
        s2 = LeagueStanding.objects.create(
            user=u2, league=bronze_league, season=test_season,
            xp_earned_this_season=200,
        )
        membership = LeagueService.assign_user_to_group(
            s2, test_season, bronze_league
        )
        assert membership.group.group_number == 2

    def test_removes_old_membership_on_tier_change(
        self, bronze_league, silver_league, test_season, season_config
    ):
        u = _make_user("tierchg@test.com", xp=100)
        standing = LeagueStanding.objects.create(
            user=u, league=bronze_league, season=test_season,
            xp_earned_this_season=100,
        )
        LeagueService.assign_user_to_group(
            standing, test_season, bronze_league
        )
        assert LeagueGroupMembership.objects.filter(standing=standing).count() == 1

        # Re-assign to silver
        LeagueService.assign_user_to_group(
            standing, test_season, silver_league
        )
        assert LeagueGroupMembership.objects.filter(standing=standing).count() == 1
        membership = LeagueGroupMembership.objects.get(standing=standing)
        assert membership.group.league == silver_league


# ══════════════════════════════════════════════════════════════════════
#  rebalance_league_groups
# ══════════════════════════════════════════════════════════════════════


class TestRebalanceLeagueGroups:
    def test_no_members_returns_zeros(
        self, bronze_league, test_season, season_config
    ):
        result = LeagueService.rebalance_league_groups(
            test_season, bronze_league
        )
        assert result == {
            "groups_active": 0,
            "groups_deactivated": 0,
            "members_moved": 0,
        }

    def test_rebalance_distributes_evenly(
        self, bronze_league, test_season, season_config
    ):
        # target_size=5, create 8 members → should have 2 groups
        group = LeagueGroup.objects.create(
            season=test_season, league=bronze_league,
            group_number=1, is_active=True,
        )
        for i in range(8):
            u = _make_user(f"rebal{i}@test.com", xp=100 * (i + 1))
            s = LeagueStanding.objects.create(
                user=u, league=bronze_league, season=test_season,
                xp_earned_this_season=100 * (i + 1),
            )
            LeagueGroupMembership.objects.create(group=group, standing=s)

        result = LeagueService.rebalance_league_groups(
            test_season, bronze_league
        )
        assert result["groups_active"] >= 2
        assert result["members_moved"] >= 0


# ══════════════════════════════════════════════════════════════════════
#  compute_season_end_promotions
# ══════════════════════════════════════════════════════════════════════


class TestComputeSeasonEndPromotions:
    def test_counts_promoted_and_relegated(
        self, bronze_league, test_season, season_config
    ):
        # promotion_xp_threshold=1000, relegation_xp_threshold=100
        u_promoted = _make_user("promoted@test.com", xp=1500)
        u_relegated = _make_user("relegated@test.com", xp=50)
        u_neutral = _make_user("neutral@test.com", xp=500)
        LeagueStanding.objects.create(
            user=u_promoted, league=bronze_league, season=test_season,
            xp_earned_this_season=1500,
        )
        LeagueStanding.objects.create(
            user=u_relegated, league=bronze_league, season=test_season,
            xp_earned_this_season=50,
        )
        LeagueStanding.objects.create(
            user=u_neutral, league=bronze_league, season=test_season,
            xp_earned_this_season=500,
        )
        result = LeagueService.compute_season_end_promotions(test_season)
        assert result["promoted"] == 1
        assert result["relegated"] == 1
        assert result["neutral"] == 1


# ══════════════════════════════════════════════════════════════════════
#  create_next_season
# ══════════════════════════════════════════════════════════════════════


class TestCreateNextSeason:
    def test_creates_next_season(
        self, bronze_league, ended_season, season_config
    ):
        u = _make_user("nextseas@test.com", xp=100)
        LeagueStanding.objects.create(
            user=u, league=bronze_league, season=ended_season,
            xp_earned_this_season=100,
        )
        # ended_season name must be parseable: "Past Season" → fallback num=2
        new_season = LeagueService.create_next_season(ended_season)
        assert new_season is not None
        assert "Season 2" in new_season.name
        assert new_season.is_active is True
        # Standings carried over
        assert LeagueStanding.objects.filter(
            season=new_season, user=u
        ).exists()

    def test_auto_create_disabled(
        self, ended_season, season_config
    ):
        season_config.auto_create_next_season = False
        season_config.save()
        result = LeagueService.create_next_season(ended_season)
        assert result is None

    def test_season_number_parsed(
        self, bronze_league, season_config
    ):
        ended = Season.objects.create(
            name="Season 5",
            start_date=timezone.now() - timedelta(days=100),
            end_date=timezone.now() - timedelta(days=1),
            is_active=False,
            status="ended",
        )
        new_season = LeagueService.create_next_season(ended)
        assert new_season is not None
        assert new_season.name == "Season 6"


# ══════════════════════════════════════════════════════════════════════
#  get_group_leaderboard
# ══════════════════════════════════════════════════════════════════════


class TestGetGroupLeaderboard:
    def test_group_leaderboard(
        self, bronze_league, test_season
    ):
        group = LeagueGroup.objects.create(
            season=test_season, league=bronze_league,
            group_number=1, is_active=True,
        )
        for i in range(3):
            u = _make_user(f"glb{i}@test.com", xp=100 * (3 - i))
            s = LeagueStanding.objects.create(
                user=u, league=bronze_league, season=test_season,
                xp_earned_this_season=100 * (3 - i),
            )
            LeagueGroupMembership.objects.create(group=group, standing=s)

        entries = LeagueService.get_group_leaderboard(group)
        assert len(entries) == 3
        assert entries[0]["rank"] == 1
        assert entries[0]["xp"] > entries[1]["xp"]
        assert "group_id" in entries[0]
        assert "group_number" in entries[0]

    def test_group_leaderboard_limit(self, bronze_league, test_season):
        group = LeagueGroup.objects.create(
            season=test_season, league=bronze_league,
            group_number=1, is_active=True,
        )
        for i in range(5):
            u = _make_user(f"glblim{i}@test.com", xp=100 * (i + 1))
            s = LeagueStanding.objects.create(
                user=u, league=bronze_league, season=test_season,
                xp_earned_this_season=100 * (i + 1),
            )
            LeagueGroupMembership.objects.create(group=group, standing=s)

        entries = LeagueService.get_group_leaderboard(group, limit=2)
        assert len(entries) == 2

    def test_empty_group(self, bronze_league, test_season):
        group = LeagueGroup.objects.create(
            season=test_season, league=bronze_league,
            group_number=1, is_active=True,
        )
        entries = LeagueService.get_group_leaderboard(group)
        assert entries == []
