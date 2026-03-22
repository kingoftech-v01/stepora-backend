"""
Tests for apps.leagues.serializers — League serializer logic.

Covers: LeagueSerializer, LeagueStandingSerializer (computed fields),
SeasonSerializer, SeasonRewardSerializer, LeaderboardEntrySerializer,
LeagueSeasonSerializer, SeasonParticipantSerializer,
LeagueGroupSerializer, SeasonConfigSerializer.
"""

from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework.test import APIRequestFactory

from apps.gamification.models import GamificationProfile
from apps.leagues.models import (
    League,
    LeagueGroup,
    LeagueGroupMembership,
    LeagueSeason,
    LeagueStanding,
    SeasonConfig,
    SeasonParticipant,
    SeasonReward,
)
from apps.leagues.serializers import (
    LeaderboardEntrySerializer,
    LeagueGroupSerializer,
    LeagueSeasonSerializer,
    LeagueSerializer,
    LeagueStandingSerializer,
    SeasonConfigSerializer,
    SeasonParticipantSerializer,
    SeasonRewardSerializer,
    SeasonSerializer,
)
from apps.users.models import User

# ── Helpers ───────────────────────────────────────────────────────────


def _make_user(email, xp=0, display_name=None):
    u = User.objects.create_user(
        email=email,
        password="testpass123",
        display_name=display_name or email.split("@")[0],
    )
    u.xp = xp
    u.save(update_fields=["xp"])
    return u


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
    from django.core.cache import cache

    cache.delete("season_config_singleton")
    config, _ = SeasonConfig.objects.get_or_create(
        pk=SeasonConfig.objects.values_list("pk", flat=True).first()
        or __import__("uuid").uuid4(),
        defaults={
            "promotion_xp_threshold": 1000,
            "relegation_xp_threshold": 100,
        },
    )
    config.promotion_xp_threshold = 1000
    config.relegation_xp_threshold = 100
    config.save()
    return config


factory = APIRequestFactory()


# ══════════════════════════════════════════════════════════════════════
#  LeagueSerializer
# ══════════════════════════════════════════════════════════════════════


class TestLeagueSerializer:
    def test_serializes_all_fields(self, bronze_league):
        data = LeagueSerializer(bronze_league).data
        assert data["name"] == "Bronze League"
        assert data["tier"] == "bronze"
        assert data["min_xp"] == 0
        assert data["max_xp"] == 499
        assert data["tier_order"] == 0
        assert "id" in data
        assert "color_hex" in data

    def test_legend_max_xp_null(self, legend_league):
        data = LeagueSerializer(legend_league).data
        assert data["max_xp"] is None
        assert data["tier_order"] == 6

    def test_read_only(self, bronze_league):
        """All fields should be read-only."""
        serializer = LeagueSerializer(
            bronze_league, data={"name": "Hacked"}
        )
        # Serializer should still be valid (read-only fields are ignored)
        assert serializer.is_valid()


# ══════════════════════════════════════════════════════════════════════
#  LeagueStandingSerializer
# ══════════════════════════════════════════════════════════════════════


class TestLeagueStandingSerializer:
    def test_basic_fields(self, league_standing, season_config):
        data = LeagueStandingSerializer(league_standing).data
        assert data["rank"] == 1
        assert data["xp_earned_this_season"] == 100
        assert data["tasks_completed"] == 5
        assert data["user_display_name"] == "League User"
        assert data["league_name"] == "Bronze League"
        assert data["league_tier"] == "bronze"

    def test_user_avatar_url(self, league_standing, season_config):
        data = LeagueStandingSerializer(league_standing).data
        # get_effective_avatar_url returns "" for users without avatar
        assert "user_avatar_url" in data

    def test_user_badges_empty(self, league_standing, season_config):
        data = LeagueStandingSerializer(league_standing).data
        assert data["user_badges"] == []

    def test_user_badges_populated(
        self, league_standing, league_user, season_config
    ):
        GamificationProfile.objects.update_or_create(
            user=league_user, defaults={"badges": ["star", "achiever"]}
        )
        # Refresh to pick up the updated gamification profile
        league_standing.refresh_from_db()
        # Clear cached user relation so serializer fetches fresh data
        standing = LeagueStanding.objects.select_related(
            "user", "league", "user__gamification"
        ).get(pk=league_standing.pk)
        data = LeagueStandingSerializer(standing).data
        assert data["user_badges"] == ["star", "achiever"]

    def test_group_fields_none_without_membership(
        self, league_standing, season_config
    ):
        data = LeagueStandingSerializer(league_standing).data
        assert data["group_number"] is None
        assert data["group_id"] is None
        assert data["rank_in_group"] is None

    def test_group_fields_with_membership(
        self, league_standing, bronze_league, test_season, season_config
    ):
        group = LeagueGroup.objects.create(
            season=test_season, league=bronze_league,
            group_number=3, is_active=True,
        )
        LeagueGroupMembership.objects.create(
            group=group, standing=league_standing
        )
        # Clear the cached membership
        if hasattr(league_standing, "_cached_group_membership"):
            delattr(league_standing, "_cached_group_membership")

        data = LeagueStandingSerializer(league_standing).data
        assert data["group_number"] == 3
        assert data["group_id"] == str(group.id)
        assert data["rank_in_group"] == 1

    def test_promotion_eligible_true(
        self, league_standing, season_config
    ):
        league_standing.xp_earned_this_season = 1500
        league_standing.save(update_fields=["xp_earned_this_season"])
        data = LeagueStandingSerializer(league_standing).data
        assert data["promotion_eligible"] is True

    def test_promotion_eligible_false(
        self, league_standing, season_config
    ):
        league_standing.xp_earned_this_season = 50
        league_standing.save(update_fields=["xp_earned_this_season"])
        data = LeagueStandingSerializer(league_standing).data
        assert data["promotion_eligible"] is False

    def test_relegation_risk_true(
        self, league_standing, season_config
    ):
        league_standing.xp_earned_this_season = 50
        league_standing.save(update_fields=["xp_earned_this_season"])
        data = LeagueStandingSerializer(league_standing).data
        assert data["relegation_risk"] is True

    def test_relegation_risk_false(
        self, league_standing, season_config
    ):
        league_standing.xp_earned_this_season = 500
        league_standing.save(update_fields=["xp_earned_this_season"])
        data = LeagueStandingSerializer(league_standing).data
        assert data["relegation_risk"] is False


# ══════════════════════════════════════════════════════════════════════
#  SeasonSerializer
# ══════════════════════════════════════════════════════════════════════


class TestSeasonSerializer:
    def test_active_season_fields(self, test_season, season_config):
        data = SeasonSerializer(test_season).data
        assert data["name"] == "Test Season 1"
        assert data["is_active"] is True
        assert data["is_current"] is True
        assert data["has_ended"] is False
        assert data["days_remaining"] > 0
        assert data["seconds_remaining"] > 0
        assert data["ends_at"] is not None

    def test_ended_season_fields(self, ended_season, season_config):
        data = SeasonSerializer(ended_season).data
        assert data["has_ended"] is True
        assert data["days_remaining"] == 0
        assert data["seconds_remaining"] == 0

    def test_thresholds(self, test_season, season_config):
        data = SeasonSerializer(test_season).data
        assert data["thresholds"]["promotion_xp"] == 1000
        assert data["thresholds"]["relegation_xp"] == 100

    def test_status_field(self, test_season, season_config):
        data = SeasonSerializer(test_season).data
        assert data["status"] == "active"


# ══════════════════════════════════════════════════════════════════════
#  SeasonRewardSerializer
# ══════════════════════════════════════════════════════════════════════


class TestSeasonRewardSerializer:
    def test_reward_fields(self, league_user, bronze_league, test_season):
        reward = SeasonReward.objects.create(
            season=test_season,
            user=league_user,
            league_achieved=bronze_league,
        )
        data = SeasonRewardSerializer(reward).data
        assert data["season_name"] == "Test Season 1"
        assert data["league_name"] == "Bronze League"
        assert data["league_tier"] == "bronze"
        assert data["rewards_claimed"] is False
        assert data["claimed_at"] is None

    def test_claimed_reward(self, league_user, bronze_league, test_season):
        reward = SeasonReward.objects.create(
            season=test_season,
            user=league_user,
            league_achieved=bronze_league,
            rewards_claimed=True,
            claimed_at=timezone.now(),
        )
        data = SeasonRewardSerializer(reward).data
        assert data["rewards_claimed"] is True
        assert data["claimed_at"] is not None


# ══════════════════════════════════════════════════════════════════════
#  LeaderboardEntrySerializer
# ══════════════════════════════════════════════════════════════════════


class TestLeaderboardEntrySerializer:
    def test_valid_data(self):
        entry = {
            "rank": 1,
            "user_id": "12345678-1234-1234-1234-123456789012",
            "user_display_name": "Test User",
            "user_avatar_url": "",
            "user_level": 5,
            "league_name": "Bronze League",
            "league_tier": "bronze",
            "league_color_hex": "#CD7F32",
            "xp": 500,
            "tasks_completed": 10,
            "badges_count": 3,
            "is_current_user": True,
        }
        serializer = LeaderboardEntrySerializer(data=entry)
        assert serializer.is_valid(), serializer.errors

    def test_fields_present(self):
        entry = {
            "rank": 2,
            "user_id": "12345678-1234-1234-1234-123456789012",
            "user_display_name": "Another",
            "user_avatar_url": "",
            "user_level": 1,
            "league_name": "Silver",
            "league_tier": "silver",
            "league_color_hex": "#C0C0C0",
            "xp": 100,
            "tasks_completed": 0,
            "badges_count": 0,
            "is_current_user": False,
        }
        serializer = LeaderboardEntrySerializer(data=entry)
        assert serializer.is_valid()
        data = serializer.validated_data
        assert data["rank"] == 2
        assert data["is_current_user"] is False


# ══════════════════════════════════════════════════════════════════════
#  LeagueSeasonSerializer
# ══════════════════════════════════════════════════════════════════════


class TestLeagueSeasonSerializer:
    @pytest.fixture
    def league_season(self, db):
        return LeagueSeason.objects.create(
            name="Season of Growth",
            theme="growth",
            description="Test season",
            start_date=timezone.now().date() - timedelta(days=10),
            end_date=timezone.now().date() + timedelta(days=80),
            is_active=True,
            rewards=[
                {"rank_min": 1, "rank_max": 3, "reward_type": "badge", "title": "Top 3"},
            ],
            theme_colors={"primary": "#00FF00"},
        )

    def test_basic_fields(self, league_season):
        data = LeagueSeasonSerializer(league_season).data
        assert data["name"] == "Season of Growth"
        assert data["theme"] == "growth"
        assert data["is_active"] is True
        assert data["is_current"] is True
        assert data["has_ended"] is False
        assert data["days_remaining"] > 0

    def test_participant_count_zero(self, league_season):
        data = LeagueSeasonSerializer(league_season).data
        assert data["participant_count"] == 0

    def test_participant_count_nonzero(self, league_season):
        u = _make_user("lspart@test.com")
        SeasonParticipant.objects.create(
            season=league_season, user=u, xp_earned=100
        )
        data = LeagueSeasonSerializer(league_season).data
        assert data["participant_count"] == 1

    def test_user_participation_unauthenticated(self, league_season):
        data = LeagueSeasonSerializer(league_season).data
        # No request context → None
        assert data["user_participation"] is None

    def test_user_participation_authenticated(self, league_season):
        u = _make_user("lsauth@test.com")
        SeasonParticipant.objects.create(
            season=league_season, user=u, xp_earned=250, rank=5
        )
        request = factory.get("/")
        request.user = u
        data = LeagueSeasonSerializer(
            league_season, context={"request": request}
        ).data
        assert data["user_participation"] is not None
        assert data["user_participation"]["xp_earned"] == 250
        assert data["user_participation"]["rank"] == 5

    def test_user_participation_not_joined(self, league_season):
        u = _make_user("lsnotjoin@test.com")
        request = factory.get("/")
        request.user = u
        data = LeagueSeasonSerializer(
            league_season, context={"request": request}
        ).data
        assert data["user_participation"] is None


# ══════════════════════════════════════════════════════════════════════
#  SeasonParticipantSerializer
# ══════════════════════════════════════════════════════════════════════


class TestSeasonParticipantSerializer:
    @pytest.fixture
    def league_season(self, db):
        return LeagueSeason.objects.create(
            name="Participant Season",
            theme="fire",
            start_date=timezone.now().date() - timedelta(days=5),
            end_date=timezone.now().date() + timedelta(days=25),
            is_active=True,
            rewards=[
                {"rank_min": 1, "rank_max": 1, "reward_type": "title", "title": "Champion"},
            ],
        )

    def test_basic_fields(self, league_season):
        u = _make_user("spart@test.com")
        participant = SeasonParticipant.objects.create(
            season=league_season, user=u, xp_earned=500, rank=2
        )
        data = SeasonParticipantSerializer(participant).data
        assert data["xp_earned"] == 500
        assert data["rank"] == 2
        assert data["user_display_name"] == "spart"
        assert data["rewards_claimed"] is False

    def test_projected_reward_match(self, league_season):
        u = _make_user("spartreward@test.com")
        participant = SeasonParticipant.objects.create(
            season=league_season, user=u, xp_earned=1000, rank=1
        )
        data = SeasonParticipantSerializer(participant).data
        assert data["projected_reward"] is not None
        assert data["projected_reward"]["title"] == "Champion"

    def test_projected_reward_no_match(self, league_season):
        u = _make_user("spartno@test.com")
        participant = SeasonParticipant.objects.create(
            season=league_season, user=u, xp_earned=100, rank=99
        )
        data = SeasonParticipantSerializer(participant).data
        assert data["projected_reward"] is None

    def test_projected_reward_none_rank(self, league_season):
        u = _make_user("spartnone@test.com")
        participant = SeasonParticipant.objects.create(
            season=league_season, user=u, xp_earned=0
        )
        data = SeasonParticipantSerializer(participant).data
        assert data["projected_reward"] is None


# ══════════════════════════════════════════════════════════════════════
#  LeagueGroupSerializer
# ══════════════════════════════════════════════════════════════════════


class TestLeagueGroupSerializer:
    def test_group_fields(self, bronze_league, test_season):
        group = LeagueGroup.objects.create(
            season=test_season, league=bronze_league,
            group_number=1, is_active=True,
        )
        # LeagueGroupSerializer expects annotated member_count or model property
        data = LeagueGroupSerializer(group).data
        assert data["group_number"] == 1
        assert data["is_active"] is True
        assert data["league_name"] == "Bronze League"
        assert data["league_tier"] == "bronze"
        assert data["season_name"] == "Test Season 1"


# ══════════════════════════════════════════════════════════════════════
#  SeasonConfigSerializer
# ══════════════════════════════════════════════════════════════════════


class TestSeasonConfigSerializer:
    def test_config_fields(self, season_config):
        data = SeasonConfigSerializer(season_config).data
        assert data["promotion_xp_threshold"] == 1000
        assert data["relegation_xp_threshold"] == 100
        assert "group_target_size" in data
        assert "group_max_size" in data
        assert "auto_create_next_season" in data
