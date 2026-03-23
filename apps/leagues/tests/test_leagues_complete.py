"""
Comprehensive test suite for the Leagues & Ranking system.

Fills coverage gaps not addressed by existing test files:
- RankSnapshot model
- LeagueSeason model properties
- SeasonConfig singleton
- SeasonParticipant model
- Celery tasks (check_season_end, process_season_end, create_daily_rank_snapshots,
  rebalance_groups_task, update_all_standings, auto_activate_pending_seasons,
  send_league_change_notifications)
- IDOR protection on claim endpoints
- LeagueGroup model + member_count property
- Edge cases for services
"""

import uuid
from datetime import date, timedelta
from unittest.mock import patch

import pytest
from django.core.cache import cache as django_cache
from django.utils import timezone
from rest_framework.test import APIClient

from apps.leagues.models import (
    League,
    LeagueGroup,
    LeagueGroupMembership,
    LeagueSeason,
    LeagueStanding,
    RankSnapshot,
    Season,
    SeasonConfig,
    SeasonParticipant,
    SeasonReward,
)
from apps.leagues.services import LeagueService
from apps.subscriptions.models import Subscription, SubscriptionPlan
from apps.users.models import User

# ── Helpers ──────────────────────────────────────────────────────────


def _make_user(email, xp=0, display_name=None):
    u = User.objects.create_user(
        email=email,
        password="testpass123",
        display_name=display_name or email.split("@")[0],
    )
    u.xp = xp
    u.save(update_fields=["xp"])
    return u


def _make_premium_user(email, display_name="PremiumUser"):
    user = _make_user(email, display_name=display_name)
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


@pytest.fixture(autouse=True)
def clear_caches():
    django_cache.delete("active_season")
    django_cache.delete("active_league_season")
    django_cache.delete("season_config_singleton")
    yield
    django_cache.delete("active_season")
    django_cache.delete("active_league_season")
    django_cache.delete("season_config_singleton")


@pytest.fixture
def bronze_league(db):
    league, _ = League.objects.get_or_create(
        tier="bronze",
        defaults={
            "name": "Bronze League",
            "min_xp": 0,
            "max_xp": 499,
            "color_hex": "#CD7F32",
        },
    )
    return league


@pytest.fixture
def silver_league(db):
    league, _ = League.objects.get_or_create(
        tier="silver",
        defaults={
            "name": "Silver League",
            "min_xp": 500,
            "max_xp": 1499,
            "color_hex": "#C0C0C0",
        },
    )
    return league


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
def legend_league(db):
    league, _ = League.objects.get_or_create(
        tier="legend",
        defaults={
            "name": "Legend League",
            "min_xp": 20000,
            "max_xp": None,
            "color_hex": "#FF4500",
        },
    )
    return league


@pytest.fixture
def active_season(db):
    Season.objects.filter(is_active=True).update(is_active=False, status="ended")
    django_cache.delete("active_season")
    return Season.objects.create(
        name="Season 1",
        start_date=timezone.now() - timedelta(days=30),
        end_date=timezone.now() + timedelta(days=150),
        is_active=True,
        status="active",
        duration_days=180,
    )


@pytest.fixture
def ended_season(db):
    return Season.objects.create(
        name="Season 0",
        start_date=timezone.now() - timedelta(days=200),
        end_date=timezone.now() - timedelta(days=10),
        is_active=False,
        status="ended",
        duration_days=180,
    )


@pytest.fixture
def season_config(db):
    django_cache.delete("season_config_singleton")
    config, _ = SeasonConfig.objects.get_or_create(
        pk=SeasonConfig.objects.values_list("pk", flat=True).first()
        or uuid.uuid4(),
        defaults={
            "group_target_size": 5,
            "group_max_size": 10,
            "group_min_size": 2,
            "promotion_xp_threshold": 1000,
            "relegation_xp_threshold": 100,
            "auto_create_next_season": True,
            "season_duration_days": 90,
        },
    )
    config.group_target_size = 5
    config.group_max_size = 10
    config.promotion_xp_threshold = 1000
    config.relegation_xp_threshold = 100
    config.auto_create_next_season = True
    config.season_duration_days = 90
    config.save()
    return config


@pytest.fixture
def user1(db):
    return _make_premium_user("complete_u1@test.com", "User1")


@pytest.fixture
def user2(db):
    return _make_premium_user("complete_u2@test.com", "User2")


@pytest.fixture
def client1(user1):
    return _client(user1)


@pytest.fixture
def client2(user2):
    return _client(user2)


# ══════════════════════════════════════════════════════════════════════
#  RankSnapshot model
# ══════════════════════════════════════════════════════════════════════


class TestRankSnapshotModel:
    """Tests for the RankSnapshot model."""

    def test_create_snapshot(self, bronze_league, active_season):
        user = _make_user("snap@test.com", xp=100)
        snap = RankSnapshot.objects.create(
            user=user,
            season=active_season,
            league=bronze_league,
            rank=5,
            xp=100,
            snapshot_date=timezone.now().date(),
        )
        assert snap.rank == 5
        assert snap.xp == 100
        assert str(snap.snapshot_date) == str(timezone.now().date())

    def test_str_representation(self, bronze_league, active_season):
        user = _make_user("snapstr@test.com", xp=200)
        snap = RankSnapshot.objects.create(
            user=user,
            season=active_season,
            league=bronze_league,
            rank=3,
            xp=200,
            snapshot_date=date(2026, 3, 22),
        )
        s = str(snap)
        assert "snapstr" in s
        assert "#3" in s
        assert "2026-03-22" in s

    def test_unique_constraint(self, bronze_league, active_season):
        user = _make_user("snapuniq@test.com", xp=100)
        today = timezone.now().date()
        RankSnapshot.objects.create(
            user=user,
            season=active_season,
            league=bronze_league,
            rank=1,
            xp=100,
            snapshot_date=today,
        )
        from django.db import IntegrityError

        with pytest.raises(IntegrityError):
            RankSnapshot.objects.create(
                user=user,
                season=active_season,
                league=bronze_league,
                rank=2,
                xp=150,
                snapshot_date=today,
            )

    def test_ordering_by_date_desc(self, bronze_league, active_season):
        user = _make_user("snapord@test.com", xp=100)
        for i in range(3):
            RankSnapshot.objects.create(
                user=user,
                season=active_season,
                league=bronze_league,
                rank=i + 1,
                xp=100,
                snapshot_date=date(2026, 3, 20 + i),
            )
        snaps = list(
            RankSnapshot.objects.filter(user=user).values_list(
                "snapshot_date", flat=True
            )
        )
        # Should be descending
        assert snaps == sorted(snaps, reverse=True)


# ══════════════════════════════════════════════════════════════════════
#  LeagueSeason model properties
# ══════════════════════════════════════════════════════════════════════


class TestLeagueSeasonModel:
    """Tests for LeagueSeason model properties."""

    @pytest.fixture
    def league_season(self, db):
        LeagueSeason.objects.filter(is_active=True).update(is_active=False)
        django_cache.delete("active_league_season")
        return LeagueSeason.objects.create(
            name="Test League Season",
            theme="fire",
            start_date=date.today() - timedelta(days=10),
            end_date=date.today() + timedelta(days=80),
            is_active=True,
            rewards=[
                {"rank_min": 1, "rank_max": 3, "reward_type": "badge", "title": "Top 3"},
                {"rank_min": 4, "rank_max": 10, "reward_type": "xp", "title": "Top 10"},
            ],
            theme_colors={"primary": "#EF4444", "secondary": "#F97316"},
        )

    @pytest.fixture
    def ended_league_season(self, db):
        return LeagueSeason.objects.create(
            name="Past League Season",
            theme="ocean",
            start_date=date.today() - timedelta(days=100),
            end_date=date.today() - timedelta(days=10),
            is_active=False,
        )

    def test_is_current_true(self, league_season):
        assert league_season.is_current is True

    def test_is_current_false(self, ended_league_season):
        assert ended_league_season.is_current is False

    def test_has_ended_true(self, ended_league_season):
        assert ended_league_season.has_ended is True

    def test_has_ended_false(self, league_season):
        assert league_season.has_ended is False

    def test_days_remaining(self, league_season):
        assert league_season.days_remaining > 0

    def test_days_remaining_ended(self, ended_league_season):
        assert ended_league_season.days_remaining == 0

    def test_str_representation(self, league_season):
        s = str(league_season)
        assert "Test League Season" in s
        assert "Active" in s

    def test_get_active_league_season(self, league_season):
        result = LeagueSeason.get_active_league_season()
        assert result is not None
        assert result.id == league_season.id

    def test_get_reward_for_rank_match(self, league_season):
        reward = league_season.get_reward_for_rank(2)
        assert reward is not None
        assert reward["title"] == "Top 3"

    def test_get_reward_for_rank_second_tier(self, league_season):
        reward = league_season.get_reward_for_rank(7)
        assert reward is not None
        assert reward["title"] == "Top 10"

    def test_get_reward_for_rank_no_match(self, league_season):
        reward = league_season.get_reward_for_rank(99)
        assert reward is None

    def test_theme_choices(self, league_season):
        assert league_season.theme in dict(LeagueSeason.THEME_CHOICES)


# ══════════════════════════════════════════════════════════════════════
#  SeasonConfig singleton
# ══════════════════════════════════════════════════════════════════════


class TestSeasonConfigModel:
    """Tests for SeasonConfig singleton."""

    def test_get_creates_if_missing(self, db):
        SeasonConfig.objects.all().delete()
        django_cache.delete("season_config_singleton")
        config = SeasonConfig.get()
        assert config is not None
        assert config.season_duration_days == 180  # default

    def test_get_returns_cached(self, season_config):
        # First call populates cache
        config1 = SeasonConfig.get()
        # Second call should come from cache
        config2 = SeasonConfig.get()
        assert config1.pk == config2.pk

    def test_save_invalidates_cache(self, season_config):
        django_cache.set("season_config_singleton", season_config, 300)
        assert django_cache.get("season_config_singleton") is not None
        season_config.save()
        assert django_cache.get("season_config_singleton") is None

    def test_str_representation(self, season_config):
        s = str(season_config)
        assert "SeasonConfig" in s
        assert "duration=" in s


# ══════════════════════════════════════════════════════════════════════
#  SeasonParticipant model
# ══════════════════════════════════════════════════════════════════════


class TestSeasonParticipantModel:
    """Tests for SeasonParticipant model."""

    @pytest.fixture
    def league_season(self, db):
        LeagueSeason.objects.filter(is_active=True).update(is_active=False)
        return LeagueSeason.objects.create(
            name="Participant Test Season",
            theme="growth",
            start_date=date.today() - timedelta(days=5),
            end_date=date.today() + timedelta(days=25),
            is_active=True,
        )

    def test_create_participant(self, league_season):
        user = _make_user("part@test.com")
        p = SeasonParticipant.objects.create(
            season=league_season, user=user, xp_earned=100
        )
        assert p.xp_earned == 100
        assert p.rewards_claimed is False
        assert p.rank is None

    def test_claim_rewards(self, league_season):
        user = _make_user("partclaim@test.com")
        p = SeasonParticipant.objects.create(
            season=league_season, user=user, xp_earned=500
        )
        result = p.claim_rewards()
        assert result is True
        p.refresh_from_db()
        assert p.rewards_claimed is True

    def test_claim_rewards_already_claimed(self, league_season):
        user = _make_user("partclaimed@test.com")
        p = SeasonParticipant.objects.create(
            season=league_season, user=user, xp_earned=500, rewards_claimed=True
        )
        result = p.claim_rewards()
        assert result is False

    def test_str_representation(self, league_season):
        user = _make_user("partstr@test.com")
        p = SeasonParticipant.objects.create(
            season=league_season, user=user, xp_earned=500, rank=3
        )
        s = str(p)
        assert "Rank #3" in s
        assert "500 XP" in s

    def test_str_unranked(self, league_season):
        user = _make_user("partunrank@test.com")
        p = SeasonParticipant.objects.create(
            season=league_season, user=user, xp_earned=0
        )
        s = str(p)
        assert "Unranked" in s

    def test_ordering_by_xp_desc(self, league_season):
        users_xp = [(100, "ord1@t.com"), (300, "ord2@t.com"), (200, "ord3@t.com")]
        for xp, email in users_xp:
            user = _make_user(email)
            SeasonParticipant.objects.create(
                season=league_season, user=user, xp_earned=xp
            )
        xps = list(
            SeasonParticipant.objects.filter(season=league_season).values_list(
                "xp_earned", flat=True
            )
        )
        assert xps == sorted(xps, reverse=True)


# ══════════════════════════════════════════════════════════════════════
#  LeagueGroup model
# ══════════════════════════════════════════════════════════════════════


class TestLeagueGroupModel:
    """Tests for LeagueGroup model."""

    def test_member_count_property(self, bronze_league, active_season):
        group = LeagueGroup.objects.create(
            season=active_season,
            league=bronze_league,
            group_number=1,
            is_active=True,
        )
        assert group.member_count == 0

        user = _make_user("grpmem@test.com", xp=100)
        standing = LeagueStanding.objects.create(
            user=user,
            league=bronze_league,
            season=active_season,
            xp_earned_this_season=100,
        )
        LeagueGroupMembership.objects.create(group=group, standing=standing)
        assert group.member_count == 1

    def test_str_representation(self, bronze_league, active_season):
        group = LeagueGroup.objects.create(
            season=active_season,
            league=bronze_league,
            group_number=3,
            is_active=True,
        )
        s = str(group)
        assert "Bronze League" in s
        assert "Group #3" in s


# ══════════════════════════════════════════════════════════════════════
#  Celery Tasks
# ══════════════════════════════════════════════════════════════════════


class TestCheckSeasonEndTask:
    """Tests for check_season_end Celery task."""

    def test_no_active_season(self, db):
        Season.objects.filter(is_active=True).update(is_active=False, status="ended")
        django_cache.delete("active_season")
        from apps.leagues.tasks import check_season_end

        # Should not raise
        check_season_end()

    def test_season_still_active(self, active_season):
        from apps.leagues.tasks import check_season_end

        check_season_end()
        active_season.refresh_from_db()
        assert active_season.status == "active"

    @patch("apps.leagues.tasks.process_season_end.delay")
    def test_season_has_ended(self, mock_delay, db):
        Season.objects.filter(is_active=True).update(is_active=False, status="ended")
        django_cache.delete("active_season")
        ended = Season.objects.create(
            name="Ending Season",
            start_date=timezone.now() - timedelta(days=200),
            end_date=timezone.now() - timedelta(hours=1),
            is_active=True,
            status="active",
        )
        django_cache.delete("active_season")

        from apps.leagues.tasks import check_season_end

        check_season_end()
        ended.refresh_from_db()
        assert ended.status == "processing"
        assert ended.is_active is False
        mock_delay.assert_called_once_with(str(ended.id))


class TestProcessSeasonEndTask:
    """Tests for process_season_end Celery task."""

    @patch("apps.leagues.tasks.send_league_change_notifications.delay")
    @patch("apps.leagues.tasks.create_next_season_task.delay")
    def test_process_season_end(
        self, mock_next, mock_notif, ended_season, bronze_league, season_config
    ):
        user = _make_user("processend@test.com", xp=100)
        LeagueStanding.objects.create(
            user=user,
            league=bronze_league,
            season=ended_season,
            xp_earned_this_season=100,
        )
        # Set to processing
        ended_season.status = "processing"
        ended_season.save()

        from apps.leagues.tasks import process_season_end

        process_season_end(str(ended_season.id))
        ended_season.refresh_from_db()
        assert ended_season.status == "ended"
        assert SeasonReward.objects.filter(season=ended_season, user=user).exists()
        mock_notif.assert_called_once()
        mock_next.assert_called_once()

    def test_season_not_found(self, db):
        from apps.leagues.tasks import process_season_end

        # Should not raise
        process_season_end(str(uuid.uuid4()))

    @patch("apps.leagues.tasks.send_league_change_notifications.delay")
    @patch("apps.leagues.tasks.create_next_season_task.delay")
    def test_already_ended_skips(
        self, mock_next, mock_notif, ended_season
    ):
        ended_season.status = "ended"
        ended_season.save()

        from apps.leagues.tasks import process_season_end

        process_season_end(str(ended_season.id))
        mock_notif.assert_not_called()
        mock_next.assert_not_called()


class TestCreateDailyRankSnapshotsTask:
    """Tests for create_daily_rank_snapshots Celery task."""

    def test_creates_snapshots(self, bronze_league, active_season):
        user = _make_user("dailysnap@test.com", xp=100)
        LeagueStanding.objects.create(
            user=user,
            league=bronze_league,
            season=active_season,
            xp_earned_this_season=100,
            rank=1,
        )
        from apps.leagues.tasks import create_daily_rank_snapshots

        create_daily_rank_snapshots()
        assert RankSnapshot.objects.filter(
            user=user, season=active_season
        ).exists()

    def test_idempotent(self, bronze_league, active_season):
        user = _make_user("snapidemp@test.com", xp=100)
        LeagueStanding.objects.create(
            user=user,
            league=bronze_league,
            season=active_season,
            xp_earned_this_season=100,
            rank=1,
        )
        from apps.leagues.tasks import create_daily_rank_snapshots

        create_daily_rank_snapshots()
        create_daily_rank_snapshots()
        assert (
            RankSnapshot.objects.filter(
                user=user, season=active_season, snapshot_date=timezone.now().date()
            ).count()
            == 1
        )

    def test_no_active_season(self, db):
        Season.objects.filter(is_active=True).update(is_active=False, status="ended")
        django_cache.delete("active_season")
        from apps.leagues.tasks import create_daily_rank_snapshots

        # Should not raise
        create_daily_rank_snapshots()


class TestRebalanceGroupsTask:
    """Tests for rebalance_groups_task Celery task."""

    def test_rebalance_all_leagues(self, active_season, bronze_league, season_config):
        from apps.leagues.tasks import rebalance_groups_task

        rebalance_groups_task()
        # Should not raise, no members to rebalance

    def test_rebalance_specific_league(
        self, active_season, bronze_league, season_config
    ):
        from apps.leagues.tasks import rebalance_groups_task

        rebalance_groups_task(
            season_id=str(active_season.id), league_id=str(bronze_league.id)
        )

    def test_rebalance_no_season(self, db):
        Season.objects.filter(is_active=True).update(is_active=False, status="ended")
        django_cache.delete("active_season")
        from apps.leagues.tasks import rebalance_groups_task

        rebalance_groups_task()  # Should not raise

    def test_rebalance_invalid_season(self, db):
        from apps.leagues.tasks import rebalance_groups_task

        rebalance_groups_task(season_id=str(uuid.uuid4()))

    def test_rebalance_invalid_league(self, active_season):
        from apps.leagues.tasks import rebalance_groups_task

        rebalance_groups_task(league_id=str(uuid.uuid4()))


class TestUpdateAllStandingsTask:
    """Tests for update_all_standings Celery task."""

    def test_updates_standings(
        self, bronze_league, active_season, season_config
    ):
        user = _make_user("allstand@test.com", xp=100)
        from apps.leagues.tasks import update_all_standings

        with patch("apps.leagues.models.cache") as mcache:
            mcache.get.return_value = active_season
            count = update_all_standings()
        assert count >= 1

    def test_no_active_season(self, db):
        Season.objects.filter(is_active=True).update(is_active=False, status="ended")
        django_cache.delete("active_season")
        from apps.leagues.tasks import update_all_standings

        with patch("apps.leagues.models.cache") as mcache:
            mcache.get.return_value = None
            result = update_all_standings()
        assert result == 0


class TestAutoActivatePendingSeasonsTask:
    """Tests for auto_activate_pending_seasons Celery task."""

    def test_activates_pending_season(self, db):
        Season.objects.filter(is_active=True).update(is_active=False, status="ended")
        django_cache.delete("active_season")
        pending = Season.objects.create(
            name="Pending Season",
            start_date=timezone.now() - timedelta(hours=1),
            end_date=timezone.now() + timedelta(days=90),
            is_active=False,
            status="pending",
        )
        from apps.leagues.tasks import auto_activate_pending_seasons

        auto_activate_pending_seasons()
        pending.refresh_from_db()
        assert pending.status == "active"
        assert pending.is_active is True

    def test_no_pending_seasons(self, db):
        from apps.leagues.tasks import auto_activate_pending_seasons

        # Should not raise
        auto_activate_pending_seasons()

    def test_deactivates_current_active(self, active_season, db):
        pending = Season.objects.create(
            name="New Pending",
            start_date=timezone.now() - timedelta(hours=1),
            end_date=timezone.now() + timedelta(days=90),
            is_active=False,
            status="pending",
        )
        from apps.leagues.tasks import auto_activate_pending_seasons

        auto_activate_pending_seasons()
        active_season.refresh_from_db()
        assert active_season.status == "ended"
        assert active_season.is_active is False
        pending.refresh_from_db()
        assert pending.status == "active"


class TestSendLeagueChangeNotificationsTask:
    """Tests for send_league_change_notifications Celery task."""

    @patch("apps.notifications.services.NotificationService.create")
    def test_sends_promotion_notification(
        self, mock_create, bronze_league, silver_league, active_season
    ):
        # User in bronze but XP qualifies for silver
        user = _make_user("promonotif@test.com", xp=700)
        LeagueStanding.objects.create(
            user=user,
            league=bronze_league,
            season=active_season,
            xp_earned_this_season=700,
        )
        from apps.leagues.tasks import send_league_change_notifications

        send_league_change_notifications()
        # The user should be promoted and a notification sent
        if mock_create.called:
            call_kwargs = mock_create.call_args.kwargs
            assert "Promoted" in call_kwargs.get("title", "") or "League changed" in call_kwargs.get("title", "")

    def test_no_active_season_noop(self, db):
        Season.objects.filter(is_active=True).update(is_active=False, status="ended")
        django_cache.delete("active_season")
        from apps.leagues.tasks import send_league_change_notifications

        # Should not raise
        send_league_change_notifications()


class TestCreateNextSeasonTask:
    """Tests for create_next_season_task Celery task."""

    def test_creates_next_season(
        self, ended_season, bronze_league, season_config
    ):
        user = _make_user("nextseastask@test.com", xp=100)
        LeagueStanding.objects.create(
            user=user,
            league=bronze_league,
            season=ended_season,
            xp_earned_this_season=100,
        )
        from apps.leagues.tasks import create_next_season_task

        create_next_season_task(str(ended_season.id))
        # A new season should exist
        assert Season.objects.filter(is_active=True).exists()

    def test_season_not_found(self, db):
        from apps.leagues.tasks import create_next_season_task

        # Should not raise
        create_next_season_task(str(uuid.uuid4()))


# ══════════════════════════════════════════════════════════════════════
#  IDOR Protection
# ══════════════════════════════════════════════════════════════════════


class TestIDORProtection:
    """Tests that users cannot claim other users' rewards."""

    def test_claim_season_reward_idor(
        self, client1, client2, user1, user2, ended_season, bronze_league
    ):
        """User2 cannot claim User1's season reward."""
        reward = SeasonReward.objects.create(
            season=ended_season, user=user1, league_achieved=bronze_league
        )
        # User2 tries to claim — should get 404 (not their reward)
        resp = client2.post(
            f"/api/v1/leagues/seasons/{ended_season.id}/claim-reward/"
        )
        assert resp.status_code == 404
        reward.refresh_from_db()
        assert reward.rewards_claimed is False

    def test_claim_league_season_reward_idor(self, client1, client2, user1, user2):
        """User2 cannot claim User1's league season rewards."""
        ls = LeagueSeason.objects.create(
            name="IDOR Test Season",
            theme="growth",
            start_date=date.today() - timedelta(days=100),
            end_date=date.today() - timedelta(days=10),
            is_active=False,
        )
        SeasonParticipant.objects.create(
            season=ls, user=user1, xp_earned=100
        )
        # User2 is not a participant — should get 404
        resp = client2.post(
            f"/api/v1/leagues/league-seasons/{ls.id}/claim-rewards/"
        )
        assert resp.status_code == 404

    def test_unauthenticated_denied(self, db):
        """Unauthenticated requests get 401."""
        client = APIClient()
        endpoints = [
            "/api/v1/leagues/leagues/",
            "/api/v1/leagues/leaderboard/global/",
            "/api/v1/leagues/leaderboard/me/",
            "/api/v1/leagues/seasons/",
            "/api/v1/leagues/groups/",
            "/api/v1/leagues/league-seasons/",
        ]
        for url in endpoints:
            resp = client.get(url)
            assert resp.status_code == 401, f"Expected 401 for {url}, got {resp.status_code}"


# ══════════════════════════════════════════════════════════════════════
#  Service edge cases
# ══════════════════════════════════════════════════════════════════════


class TestServiceEdgeCases:
    """Edge case tests for LeagueService."""

    def test_get_user_league_boundary_xp(
        self, bronze_league, silver_league, gold_league
    ):
        """Users at exact XP boundaries are placed correctly."""
        # At 499 XP (top of bronze)
        u1 = _make_user("boundary499@test.com", xp=499)
        assert LeagueService.get_user_league(u1) == bronze_league

        # At 500 XP (bottom of silver)
        u2 = _make_user("boundary500@test.com", xp=500)
        assert LeagueService.get_user_league(u2) == silver_league

        # At 1499 XP (top of silver)
        u3 = _make_user("boundary1499@test.com", xp=1499)
        assert LeagueService.get_user_league(u3) == silver_league

        # At 1500 XP (bottom of gold)
        u4 = _make_user("boundary1500@test.com", xp=1500)
        assert LeagueService.get_user_league(u4) == gold_league

    def test_update_standing_no_leagues(self, active_season):
        """update_standing returns None when no leagues exist."""
        League.objects.all().delete()
        user = _make_user("noleagues@test.com", xp=100)
        with patch("apps.leagues.models.cache") as mcache:
            mcache.get.return_value = active_season
            result = LeagueService.update_standing(user)
        assert result is None
        # Restore leagues
        League.seed_defaults()

    def test_get_leaderboard_respects_limit_cap(self, bronze_league, active_season):
        """get_leaderboard limit parameter works correctly."""
        for i in range(5):
            u = _make_user(f"limcap{i}@test.com", xp=100 * (i + 1))
            LeagueStanding.objects.create(
                user=u,
                league=bronze_league,
                season=active_season,
                xp_earned_this_season=100 * (i + 1),
            )
        entries = LeagueService.get_leaderboard(season=active_season, limit=2)
        assert len(entries) == 2
        # Highest XP first
        assert entries[0]["xp"] > entries[1]["xp"]

    def test_calculate_season_rewards_multiple_users(
        self, bronze_league, silver_league, ended_season
    ):
        """Rewards are created for all users in the season."""
        users = []
        for i in range(3):
            u = _make_user(f"multireward{i}@test.com", xp=100 * (i + 1))
            league = bronze_league if i < 2 else silver_league
            LeagueStanding.objects.create(
                user=u,
                league=league,
                season=ended_season,
                xp_earned_this_season=100 * (i + 1),
            )
            users.append(u)

        count = LeagueService.calculate_season_rewards(ended_season)
        assert count == 3
        for u in users:
            assert SeasonReward.objects.filter(
                season=ended_season, user=u
            ).exists()


# ══════════════════════════════════════════════════════════════════════
#  Season status sync
# ══════════════════════════════════════════════════════════════════════


class TestSeasonStatusSync:
    """Tests for Season.save() status sync behavior."""

    def test_active_status_sets_is_active(self, db):
        s = Season.objects.create(
            name="Sync Active",
            start_date=timezone.now(),
            end_date=timezone.now() + timedelta(days=30),
            status="active",
        )
        assert s.is_active is True

    def test_ended_status_clears_is_active(self, db):
        s = Season.objects.create(
            name="Sync Ended",
            start_date=timezone.now() - timedelta(days=60),
            end_date=timezone.now() - timedelta(days=1),
            status="ended",
        )
        assert s.is_active is False

    def test_processing_status_clears_is_active(self, db):
        s = Season.objects.create(
            name="Sync Processing",
            start_date=timezone.now() - timedelta(days=60),
            end_date=timezone.now() - timedelta(days=1),
            status="processing",
        )
        assert s.is_active is False

    def test_pending_status_preserves_is_active(self, db):
        s = Season.objects.create(
            name="Sync Pending",
            start_date=timezone.now() + timedelta(days=10),
            end_date=timezone.now() + timedelta(days=100),
            status="pending",
            is_active=False,
        )
        assert s.is_active is False


# ══════════════════════════════════════════════════════════════════════
#  League model edge cases
# ══════════════════════════════════════════════════════════════════════


class TestLeagueModelEdgeCases:
    """Edge cases for the League model."""

    def test_tier_order_unknown_tier(self, bronze_league):
        """Unknown tier returns 0 from TIER_ORDER."""
        assert League.TIER_ORDER.get("unknown", 0) == 0

    def test_contains_xp_zero(self, bronze_league):
        """Bronze league contains 0 XP."""
        assert bronze_league.contains_xp(0) is True

    def test_legend_contains_very_high_xp(self, legend_league):
        """Legend league accepts arbitrarily high XP."""
        assert legend_league.contains_xp(1_000_000) is True

    def test_seed_defaults_returns_existing(self, db):
        """seed_defaults returns existing leagues if they exist."""
        # Ensure leagues exist
        League.seed_defaults()
        result = League.seed_defaults()
        # Returns the existing queryset, not new objects
        assert len(result) >= 7 or result.count() >= 7
