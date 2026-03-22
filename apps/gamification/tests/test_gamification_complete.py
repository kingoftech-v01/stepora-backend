"""
Comprehensive tests for the Gamification app.

Covers: models, services, views, serializers, signals, tasks, edge cases.
Target: 95%+ coverage of apps/gamification/.
"""

import uuid
from datetime import date, timedelta
from unittest.mock import MagicMock, patch

import pytest
from django.db import IntegrityError
from django.test.utils import override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.gamification.models import (
    Achievement,
    DailyActivity,
    GamificationProfile,
    HabitChain,
    UserAchievement,
)
from apps.gamification.serializers import (
    AchievementSerializer,
    DailyActivitySerializer,
    GamificationProfileSerializer,
    HabitChainSerializer,
    UserAchievementSerializer,
)
from apps.gamification.services import AchievementService, StreakService, XPService
from apps.users.models import User


# ═══════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════

@pytest.fixture
def user(db):
    """Standard test user."""
    return User.objects.create_user(
        email="gam_test@stepora.app",
        password="Testpass123!",
        display_name="Gam Tester",
    )


@pytest.fixture
def user2(db):
    """Second test user for leaderboard / ranking tests."""
    return User.objects.create_user(
        email="gam_test2@stepora.app",
        password="Testpass123!",
        display_name="Gam Tester 2",
    )


@pytest.fixture
def profile(user):
    """GamificationProfile for the test user."""
    p, _ = GamificationProfile.objects.get_or_create(user=user)
    return p


@pytest.fixture
def achievement_first_dream(db):
    return Achievement.objects.create(
        name="First Dream",
        description="Create your first dream",
        icon="sparkles",
        category="dreams",
        rarity="common",
        xp_reward=50,
        condition_type="first_dream",
        condition_value=1,
    )


@pytest.fixture
def achievement_streak_7(db):
    return Achievement.objects.create(
        name="Week Warrior",
        description="7-day streak",
        icon="flame",
        category="streaks",
        rarity="uncommon",
        xp_reward=100,
        condition_type="streak_days",
        condition_value=7,
    )


@pytest.fixture
def achievement_streak_30(db):
    return Achievement.objects.create(
        name="Monthly Master",
        description="30-day streak",
        icon="flame",
        category="streaks",
        rarity="rare",
        xp_reward=300,
        condition_type="streak_days",
        condition_value=30,
    )


@pytest.fixture
def achievement_tasks_10(db):
    return Achievement.objects.create(
        name="Task Crusher",
        description="Complete 10 tasks",
        icon="check_circle",
        category="tasks",
        rarity="common",
        xp_reward=75,
        condition_type="tasks_completed",
        condition_value=10,
    )


@pytest.fixture
def achievement_xp_1000(db):
    return Achievement.objects.create(
        name="XP Hoarder",
        description="Earn 1000 XP",
        icon="zap",
        category="special",
        rarity="epic",
        xp_reward=200,
        condition_type="xp_earned",
        condition_value=1000,
    )


@pytest.fixture
def achievement_level_5(db):
    return Achievement.objects.create(
        name="Level 5",
        description="Reach level 5",
        icon="trophy",
        category="special",
        rarity="rare",
        xp_reward=150,
        condition_type="level_reached",
        condition_value=5,
    )


@pytest.fixture
def inactive_achievement(db):
    return Achievement.objects.create(
        name="Inactive Test",
        description="Should not appear",
        icon="lock",
        category="special",
        rarity="legendary",
        xp_reward=500,
        condition_type="xp_earned",
        condition_value=99999,
        is_active=False,
    )


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def auth_client(api_client, user):
    api_client.force_authenticate(user=user)
    return api_client


# ═══════════════════════════════════════════════════════════════════
# Model Tests: GamificationProfile
# ═══════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestGamificationProfileModel:
    """GamificationProfile model tests."""

    def test_auto_create_via_signal(self, user):
        """Signal should auto-create profile on user creation."""
        assert GamificationProfile.objects.filter(user=user).exists()

    def test_default_values(self, profile):
        assert profile.health_xp == 0
        assert profile.career_xp == 0
        assert profile.relationships_xp == 0
        assert profile.personal_growth_xp == 0
        assert profile.finance_xp == 0
        assert profile.hobbies_xp == 0
        assert profile.streak_jokers == 3
        assert profile.badges == []
        assert profile.achievements == []

    def test_get_attribute_level_zero_xp(self, profile):
        assert profile.get_attribute_level("health") == 1

    def test_get_attribute_level_100_xp(self, profile):
        profile.health_xp = 100
        profile.save()
        assert profile.get_attribute_level("health") == 2

    def test_get_attribute_level_250_xp(self, profile):
        profile.health_xp = 250
        profile.save()
        assert profile.get_attribute_level("health") == 3

    def test_get_attribute_level_999_xp(self, profile):
        profile.health_xp = 999
        profile.save()
        assert profile.get_attribute_level("health") == 10

    def test_add_attribute_xp_atomic(self, profile):
        profile.add_attribute_xp("career", 75)
        assert profile.career_xp == 75

    def test_add_attribute_xp_cumulative(self, profile):
        profile.add_attribute_xp("finance", 30)
        profile.add_attribute_xp("finance", 70)
        assert profile.finance_xp == 100

    def test_add_attribute_xp_all_categories(self, profile):
        for cat in ["health", "career", "relationships", "personal_growth", "finance", "hobbies"]:
            profile.add_attribute_xp(cat, 50)
        profile.refresh_from_db()
        assert profile.health_xp == 50
        assert profile.career_xp == 50
        assert profile.relationships_xp == 50
        assert profile.personal_growth_xp == 50
        assert profile.finance_xp == 50
        assert profile.hobbies_xp == 50

    def test_str_representation(self, profile):
        assert "Gamification" in str(profile)
        assert profile.user.email in str(profile)

    def test_uuid_primary_key(self, profile):
        assert isinstance(profile.id, uuid.UUID)


# ═══════════════════════════════════════════════════════════════════
# Model Tests: Achievement
# ═══════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestAchievementModel:
    """Achievement model tests."""

    def test_create(self, achievement_first_dream):
        assert achievement_first_dream.name == "First Dream"
        assert achievement_first_dream.xp_reward == 50
        assert achievement_first_dream.is_active is True
        assert achievement_first_dream.rarity == "common"

    def test_str_includes_icon_and_name(self, achievement_first_dream):
        s = str(achievement_first_dream)
        assert "sparkles" in s
        assert "First Dream" in s

    def test_unique_name(self, achievement_first_dream):
        with pytest.raises(IntegrityError):
            Achievement.objects.create(
                name="First Dream",
                description="Duplicate",
                icon="star",
                category="dreams",
                condition_type="first_dream",
                condition_value=1,
            )

    def test_ordering(self, db):
        a1 = Achievement.objects.create(
            name="A1", description="x", icon="star", category="dreams",
            condition_type="first_dream", condition_value=1,
        )
        a2 = Achievement.objects.create(
            name="A2", description="x", icon="star", category="dreams",
            condition_type="dreams_created", condition_value=5,
        )
        a3 = Achievement.objects.create(
            name="A3", description="x", icon="star", category="streaks",
            condition_type="streak_days", condition_value=7,
        )
        ordered = list(Achievement.objects.all())
        # Ordering is ["category", "condition_value"]
        assert ordered[0] == a1  # dreams, 1
        assert ordered[1] == a2  # dreams, 5
        assert ordered[2] == a3  # streaks, 7

    def test_all_rarity_choices(self, db):
        for rarity in ["common", "uncommon", "rare", "epic", "legendary"]:
            ach = Achievement.objects.create(
                name=f"Rarity_{rarity}",
                description=f"Test {rarity}",
                icon="star",
                category="special",
                condition_type="xp_earned",
                condition_value=1,
                rarity=rarity,
            )
            assert ach.rarity == rarity

    def test_all_category_choices(self, db):
        for category in ["streaks", "dreams", "social", "tasks", "special", "profile"]:
            ach = Achievement.objects.create(
                name=f"Cat_{category}",
                description=f"Test {category}",
                icon="star",
                category=category,
                condition_type="xp_earned",
                condition_value=1,
            )
            assert ach.category == category

    def test_inactive_achievement(self, inactive_achievement):
        active = Achievement.objects.filter(is_active=True)
        assert inactive_achievement not in active


# ═══════════════════════════════════════════════════════════════════
# Model Tests: UserAchievement
# ═══════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestUserAchievementModel:
    """UserAchievement model tests."""

    def test_grant(self, user, achievement_first_dream):
        ua = UserAchievement.objects.create(
            user=user, achievement=achievement_first_dream,
        )
        assert ua.user == user
        assert ua.achievement == achievement_first_dream
        assert ua.progress == 0
        assert ua.unlocked_at is not None

    def test_no_duplicate(self, user, achievement_first_dream):
        UserAchievement.objects.create(user=user, achievement=achievement_first_dream)
        with pytest.raises(IntegrityError):
            UserAchievement.objects.create(user=user, achievement=achievement_first_dream)

    def test_xp_reward_on_grant(self, user, achievement_first_dream):
        """XP should increase when achievement service grants."""
        old_xp = user.xp
        UserAchievement.objects.create(user=user, achievement=achievement_first_dream)
        user.add_xp(achievement_first_dream.xp_reward)
        user.refresh_from_db()
        assert user.xp == old_xp + 50

    def test_ordering_by_unlocked_at(self, user, achievement_first_dream, achievement_streak_7):
        ua1 = UserAchievement.objects.create(user=user, achievement=achievement_first_dream)
        ua2 = UserAchievement.objects.create(user=user, achievement=achievement_streak_7)
        ordered = list(UserAchievement.objects.filter(user=user))
        # Ordering is ["-unlocked_at"] so latest first
        assert ordered[0] == ua2
        assert ordered[1] == ua1

    def test_str(self, user, achievement_first_dream):
        ua = UserAchievement.objects.create(user=user, achievement=achievement_first_dream)
        s = str(ua)
        assert user.email in s
        assert "First Dream" in s


# ═══════════════════════════════════════════════════════════════════
# Model Tests: DailyActivity
# ═══════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestDailyActivityModel:
    """DailyActivity model tests."""

    def test_record_task_completion(self, user):
        activity = DailyActivity.record_task_completion(
            user=user, xp_earned=10, duration_mins=15,
        )
        assert activity.tasks_completed == 1
        assert activity.xp_earned == 10
        assert activity.minutes_active == 15
        assert activity.date == timezone.now().date()

    def test_record_cumulative(self, user):
        DailyActivity.record_task_completion(user=user, xp_earned=10, duration_mins=5)
        activity = DailyActivity.record_task_completion(user=user, xp_earned=20, duration_mins=10)
        assert activity.tasks_completed == 2
        assert activity.xp_earned == 30
        assert activity.minutes_active == 15

    def test_unique_user_date(self, user):
        today = timezone.now().date()
        DailyActivity.objects.create(user=user, date=today)
        with pytest.raises(IntegrityError):
            DailyActivity.objects.create(user=user, date=today)

    def test_different_dates_allowed(self, user):
        today = timezone.now().date()
        yesterday = today - timedelta(days=1)
        DailyActivity.objects.create(user=user, date=today)
        DailyActivity.objects.create(user=user, date=yesterday)
        assert DailyActivity.objects.filter(user=user).count() == 2

    def test_ordering(self, user):
        today = timezone.now().date()
        a1 = DailyActivity.objects.create(user=user, date=today - timedelta(days=2))
        a2 = DailyActivity.objects.create(user=user, date=today - timedelta(days=1))
        a3 = DailyActivity.objects.create(user=user, date=today)
        ordered = list(DailyActivity.objects.filter(user=user))
        assert ordered == [a3, a2, a1]  # -date ordering

    def test_str(self, user):
        activity = DailyActivity.record_task_completion(user=user, xp_earned=5)
        s = str(activity)
        assert user.email in s
        assert "1 tasks" in s

    def test_record_defaults(self, user):
        activity = DailyActivity.record_task_completion(user=user)
        assert activity.xp_earned == 0
        assert activity.minutes_active == 0


# ═══════════════════════════════════════════════════════════════════
# Model Tests: HabitChain
# ═══════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestHabitChainModel:
    """HabitChain model tests."""

    def test_create_task_completion(self, user):
        hc = HabitChain.objects.create(
            user=user, date=date.today(), chain_type="task_completion",
        )
        assert hc.completed is True
        assert hc.chain_type == "task_completion"
        assert hc.dream is None

    def test_create_check_in(self, user):
        hc = HabitChain.objects.create(
            user=user, date=date.today(), chain_type="check_in",
        )
        assert hc.chain_type == "check_in"

    def test_create_focus_timer(self, user):
        hc = HabitChain.objects.create(
            user=user, date=date.today(), chain_type="focus_timer",
        )
        assert hc.chain_type == "focus_timer"

    def test_with_dream(self, user):
        from apps.dreams.models import Dream

        dream = Dream.objects.create(user=user, title="Test Dream", description="Test")
        hc = HabitChain.objects.create(
            user=user, date=date.today(), chain_type="task_completion", dream=dream,
        )
        assert hc.dream == dream

    def test_str(self, user):
        hc = HabitChain.objects.create(
            user=user, date=date.today(), chain_type="check_in",
        )
        s = str(hc)
        assert user.email in s
        assert "check_in" in s

    def test_ordering(self, user):
        today = date.today()
        hc1 = HabitChain.objects.create(user=user, date=today - timedelta(days=1), chain_type="check_in")
        hc2 = HabitChain.objects.create(user=user, date=today, chain_type="check_in")
        ordered = list(HabitChain.objects.filter(user=user))
        assert ordered[0] == hc2  # more recent first


# ═══════════════════════════════════════════════════════════════════
# Service Tests: AchievementService
# ═══════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestAchievementService:
    """AchievementService.check_achievements tests."""

    def test_unlocks_first_dream(self, user, achievement_first_dream):
        from apps.dreams.models import Dream

        Dream.objects.create(user=user, title="My Dream", description="Test")

        newly = AchievementService.check_achievements(user)
        assert len(newly) == 1
        assert newly[0].id == achievement_first_dream.id
        assert UserAchievement.objects.filter(user=user, achievement=achievement_first_dream).exists()

    def test_idempotent(self, user, achievement_first_dream):
        from apps.dreams.models import Dream

        Dream.objects.create(user=user, title="My Dream", description="Test")

        first = AchievementService.check_achievements(user)
        second = AchievementService.check_achievements(user)
        assert len(first) == 1
        assert len(second) == 0

    def test_no_unlock_if_condition_not_met(self, user, achievement_streak_7):
        """User has 0 streak, should not unlock streak_7 achievement."""
        user.streak_days = 0
        user.save()
        newly = AchievementService.check_achievements(user)
        assert len(newly) == 0

    def test_unlocks_streak_achievement(self, user, achievement_streak_7):
        User.objects.filter(id=user.id).update(streak_days=7)
        user.refresh_from_db()
        newly = AchievementService.check_achievements(user)
        assert len(newly) == 1
        assert newly[0].name == "Week Warrior"

    def test_awards_xp_on_unlock(self, user, achievement_first_dream):
        from apps.dreams.models import Dream

        Dream.objects.create(user=user, title="Dream", description="Test")
        old_xp = user.xp

        AchievementService.check_achievements(user)
        user.refresh_from_db()
        assert user.xp == old_xp + 50

    def test_multiple_achievements_at_once(self, user, achievement_first_dream, achievement_streak_7):
        from apps.dreams.models import Dream

        Dream.objects.create(user=user, title="Dream", description="Test")
        User.objects.filter(id=user.id).update(streak_days=10)
        user.refresh_from_db()

        newly = AchievementService.check_achievements(user)
        assert len(newly) == 2

    def test_skips_inactive_achievements(self, user, inactive_achievement):
        user.xp = 999999
        user.save()
        newly = AchievementService.check_achievements(user)
        assert all(a.id != inactive_achievement.id for a in newly)

    @patch("apps.notifications.services.NotificationService.create")
    def test_sends_notification_on_unlock(self, mock_create, user, achievement_first_dream):
        from apps.dreams.models import Dream

        Dream.objects.create(user=user, title="Dream", description="Test")
        AchievementService.check_achievements(user)
        mock_create.assert_called_once()

    @patch("apps.notifications.services.NotificationService.create")
    def test_notification_failure_does_not_block(self, mock_create, user, achievement_first_dream):
        mock_create.side_effect = Exception("Notification service down")
        from apps.dreams.models import Dream

        Dream.objects.create(user=user, title="Dream", description="Test")
        # Should not raise
        newly = AchievementService.check_achievements(user)
        assert len(newly) == 1


# ═══════════════════════════════════════════════════════════════════
# Service Tests: StreakService
# ═══════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestStreakService:
    """StreakService tests."""

    def test_record_activity_new_streak(self, user):
        """First activity should set streak to 1."""
        StreakService.record_activity(user, "task_completion")
        user.refresh_from_db()
        assert user.streak_days == 1
        assert user.streak_updated_at == timezone.now().date()

    def test_record_activity_consecutive_day(self, user):
        yesterday = timezone.now().date() - timedelta(days=1)
        User.objects.filter(id=user.id).update(
            streak_days=5, streak_updated_at=yesterday,
        )
        user.refresh_from_db()

        StreakService.record_activity(user, "check_in")
        user.refresh_from_db()
        assert user.streak_days == 6

    def test_record_activity_gap_resets(self, user):
        three_days_ago = timezone.now().date() - timedelta(days=3)
        User.objects.filter(id=user.id).update(
            streak_days=10, streak_updated_at=three_days_ago,
        )
        user.refresh_from_db()

        StreakService.record_activity(user, "task_completion")
        user.refresh_from_db()
        assert user.streak_days == 1  # Reset to 1

    def test_record_activity_idempotent_same_day(self, user):
        StreakService.record_activity(user, "task_completion")
        user.refresh_from_db()
        streak_after_first = user.streak_days

        StreakService.record_activity(user, "check_in")
        user.refresh_from_db()
        assert user.streak_days == streak_after_first  # No change

    def test_record_activity_creates_habit_chain(self, user):
        StreakService.record_activity(user, "focus_timer")
        assert HabitChain.objects.filter(
            user=user, chain_type="focus_timer", date=timezone.now().date(),
        ).exists()

    def test_record_activity_with_dream(self, user):
        from apps.dreams.models import Dream

        dream = Dream.objects.create(user=user, title="Test", description="Test")
        StreakService.record_activity(user, "task_completion", dream=dream)
        hc = HabitChain.objects.get(user=user, chain_type="task_completion")
        assert hc.dream == dream

    def test_updates_longest_streak(self, user):
        yesterday = timezone.now().date() - timedelta(days=1)
        User.objects.filter(id=user.id).update(
            streak_days=9, longest_streak=5, streak_updated_at=yesterday,
        )
        user.refresh_from_db()

        StreakService.record_activity(user, "task_completion")
        user.refresh_from_db()
        assert user.streak_days == 10
        assert user.longest_streak == 10

    def test_xp_multiplier_thresholds(self):
        assert StreakService.get_xp_multiplier(0) == 1.0
        assert StreakService.get_xp_multiplier(6) == 1.0
        assert StreakService.get_xp_multiplier(7) == 1.5
        assert StreakService.get_xp_multiplier(29) == 1.5
        assert StreakService.get_xp_multiplier(30) == 2.0
        assert StreakService.get_xp_multiplier(99) == 2.0
        assert StreakService.get_xp_multiplier(100) == 3.0
        assert StreakService.get_xp_multiplier(365) == 3.0

    def test_get_streak_summary(self, user):
        User.objects.filter(id=user.id).update(
            streak_days=14, longest_streak=14,
            streak_updated_at=timezone.now().date(),
        )
        user.refresh_from_db()

        summary = StreakService.get_streak_summary(user)
        assert summary["current_streak"] == 14
        assert summary["longest_streak"] == 14
        assert summary["xp_multiplier"] == 1.5
        assert summary["xp_multiplier_label"] == "1.5x"
        assert summary["next_milestone"] == 30
        assert summary["milestones"] == [7, 14, 30, 60, 90, 180, 365]

    def test_get_streak_summary_no_multiplier(self, user):
        summary = StreakService.get_streak_summary(user)
        assert summary["xp_multiplier"] == 1.0
        assert summary["xp_multiplier_label"] is None

    def test_get_streak_summary_past_all_milestones(self, user):
        User.objects.filter(id=user.id).update(streak_days=400, longest_streak=400)
        user.refresh_from_db()
        summary = StreakService.get_streak_summary(user)
        assert summary["next_milestone"] is None

    def test_get_calendar_heatmap(self, user):
        today = timezone.now().date()
        DailyActivity.objects.create(user=user, date=today, tasks_completed=5)
        DailyActivity.objects.create(
            user=user, date=today - timedelta(days=1), tasks_completed=1,
        )

        heatmap = StreakService.get_calendar_heatmap(user, days=7)
        assert len(heatmap) == 7

        last = heatmap[-1]
        assert last["date"] == today.isoformat()
        assert last["count"] == 5
        assert last["level"] == 3  # count > 3 -> level 3

        second_last = heatmap[-2]
        assert second_last["count"] == 1
        assert second_last["level"] == 1

        # Day with no activity
        empty = heatmap[0]
        assert empty["count"] == 0
        assert empty["level"] == 0

    def test_get_calendar_heatmap_level_2(self, user):
        today = timezone.now().date()
        DailyActivity.objects.create(user=user, date=today, tasks_completed=2)
        heatmap = StreakService.get_calendar_heatmap(user, days=1)
        assert heatmap[0]["level"] == 2

    def test_reset_broken_streaks(self, user, user2):
        three_days_ago = timezone.now().date() - timedelta(days=3)
        User.objects.filter(id=user.id).update(
            streak_days=10, streak_updated_at=three_days_ago,
        )

        result = StreakService.reset_broken_streaks()
        assert result["reset"] >= 1

        user.refresh_from_db()
        assert user.streak_days == 0

    def test_reset_broken_streaks_at_risk_notification(self, user):
        yesterday = timezone.now().date() - timedelta(days=1)
        User.objects.filter(id=user.id).update(
            streak_days=5, streak_updated_at=yesterday,
        )

        with patch.object(StreakService, "_send_at_risk_notification") as mock_notify:
            result = StreakService.reset_broken_streaks()
            assert result["notified"] >= 1
            mock_notify.assert_called()

    def test_reset_broken_does_not_notify_small_streaks(self, user):
        yesterday = timezone.now().date() - timedelta(days=1)
        User.objects.filter(id=user.id).update(
            streak_days=2, streak_updated_at=yesterday,
        )

        with patch.object(StreakService, "_send_at_risk_notification") as mock_notify:
            StreakService.reset_broken_streaks()
            mock_notify.assert_not_called()

    @patch("apps.notifications.models.Notification.objects.create")
    def test_streak_milestone_notification(self, mock_create, user):
        yesterday = timezone.now().date() - timedelta(days=1)
        User.objects.filter(id=user.id).update(
            streak_days=6, streak_updated_at=yesterday,
        )
        user.refresh_from_db()

        StreakService.record_activity(user, "task_completion")
        user.refresh_from_db()
        assert user.streak_days == 7
        # Should have created a milestone notification
        mock_create.assert_called()

    @patch("apps.notifications.models.Notification.objects.create")
    def test_no_milestone_notification_at_non_milestone(self, mock_create, user):
        yesterday = timezone.now().date() - timedelta(days=1)
        User.objects.filter(id=user.id).update(
            streak_days=4, streak_updated_at=yesterday,
        )
        user.refresh_from_db()

        StreakService.record_activity(user, "task_completion")
        user.refresh_from_db()
        assert user.streak_days == 5
        mock_create.assert_not_called()


# ═══════════════════════════════════════════════════════════════════
# Service Tests: StreakService.use_streak_freeze
# ═══════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestStreakFreeze:
    """StreakService.use_streak_freeze tests."""

    def _make_premium(self, user):
        """Helper to make user premium for freeze tests."""
        from apps.subscriptions.models import Subscription, SubscriptionPlan

        plan, _ = SubscriptionPlan.objects.get_or_create(
            slug="premium",
            defaults={
                "name": "Premium",
                "price_monthly": 9.99,
                "dream_limit": -1,
                "ai_analyses_limit": -1,
            },
        )
        Subscription.objects.update_or_create(
            user=user,
            defaults={
                "plan": plan,
                "status": "active",
                "current_period_start": timezone.now(),
                "current_period_end": timezone.now() + timedelta(days=30),
            },
        )

    def test_non_premium_rejected(self, user, profile):
        User.objects.filter(id=user.id).update(streak_days=5)
        user.refresh_from_db()
        result = StreakService.use_streak_freeze(user)
        assert result["success"] is False
        assert "premium" in result["message"].lower()

    def test_zero_streak_rejected(self, user, profile):
        self._make_premium(user)
        result = StreakService.use_streak_freeze(user)
        assert result["success"] is False
        assert "No active streak" in result["message"]

    def test_no_jokers_rejected(self, user, profile):
        self._make_premium(user)
        User.objects.filter(id=user.id).update(streak_days=5)
        user.refresh_from_db()
        profile.streak_jokers = 0
        profile.save()

        result = StreakService.use_streak_freeze(user)
        assert result["success"] is False
        assert "No streak freezes" in result["message"]

    def test_success(self, user, profile):
        self._make_premium(user)
        User.objects.filter(id=user.id).update(streak_days=10)
        user.refresh_from_db()

        result = StreakService.use_streak_freeze(user)
        assert result["success"] is True
        assert result["freeze_count"] == 2
        user.refresh_from_db()
        assert user.streak_updated_at == timezone.now().date()
        assert user.streak_freeze_used_at == timezone.now().date()

    def test_max_one_per_week(self, user, profile):
        self._make_premium(user)
        User.objects.filter(id=user.id).update(
            streak_days=10, streak_freeze_used_at=timezone.now().date() - timedelta(days=3),
        )
        user.refresh_from_db()

        result = StreakService.use_streak_freeze(user)
        assert result["success"] is False
        assert "one streak freeze per week" in result["message"]

    def test_allowed_after_one_week(self, user, profile):
        self._make_premium(user)
        User.objects.filter(id=user.id).update(
            streak_days=10, streak_freeze_used_at=timezone.now().date() - timedelta(days=8),
        )
        user.refresh_from_db()

        result = StreakService.use_streak_freeze(user)
        assert result["success"] is True


# ═══════════════════════════════════════════════════════════════════
# Service Tests: XPService
# ═══════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestXPService:
    """XPService tests."""

    def test_award_xp_basic(self, user):
        leveled = XPService.award_xp(user, 50)
        user.refresh_from_db()
        assert user.xp == 50
        assert leveled is False

    def test_award_xp_level_up(self, user):
        user.xp = 95
        user.level = 1
        user.save()
        leveled = XPService.award_xp(user, 10)
        user.refresh_from_db()
        assert user.xp == 105
        assert user.level == 2
        assert leveled is True

    def test_award_xp_with_category(self, user, profile):
        XPService.award_xp(user, 75, category="health")
        profile.refresh_from_db()
        assert profile.health_xp == 75

    def test_award_xp_without_category(self, user):
        XPService.award_xp(user, 30)
        user.refresh_from_db()
        assert user.xp == 30

    def test_get_level_info(self, user):
        user.xp = 250
        user.level = 3
        user.save()
        info = XPService.get_level_info(user)
        assert info["level"] == 3
        assert info["xp"] == 250
        assert info["xp_to_next_level"] == 50
        assert info["progress_percentage"] == 50

    def test_get_level_info_zero(self, user):
        info = XPService.get_level_info(user)
        assert info["level"] == 1
        assert info["xp"] == 0
        assert info["xp_to_next_level"] == 100
        assert info["progress_percentage"] == 0

    def test_multiple_level_ups(self, user):
        user.xp = 90
        user.level = 1
        user.save()
        leveled = XPService.award_xp(user, 210)
        user.refresh_from_db()
        assert user.xp == 300
        assert user.level == 4
        assert leveled is True


# ═══════════════════════════════════════════════════════════════════
# Serializer Tests
# ═══════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestSerializers:
    """Serializer tests."""

    def test_gamification_profile_serializer(self, profile):
        data = GamificationProfileSerializer(profile).data
        assert "health_xp" in data
        assert "health_level" in data
        assert "career_level" in data
        assert "relationships_level" in data
        assert "personal_growth_level" in data
        assert "finance_level" in data
        assert "hobbies_level" in data
        assert "skill_radar" in data
        assert "streak_jokers" in data
        assert data["health_level"] == 1
        assert len(data["skill_radar"]) == 6

    def test_skill_radar_data(self, profile):
        profile.health_xp = 200
        profile.career_xp = 100
        profile.save()
        data = GamificationProfileSerializer(profile).data
        radar = data["skill_radar"]
        health = next(c for c in radar if c["category"] == "health")
        assert health["xp"] == 200
        assert health["level"] == 3
        career = next(c for c in radar if c["category"] == "career")
        assert career["xp"] == 100
        assert career["level"] == 2

    def test_achievement_serializer(self, achievement_first_dream):
        data = AchievementSerializer(achievement_first_dream).data
        assert data["name"] == "First Dream"
        assert data["icon"] == "sparkles"
        assert data["category"] == "dreams"
        assert data["rarity"] == "common"
        assert data["xp_reward"] == 50
        assert data["condition_type"] == "first_dream"
        assert data["condition_value"] == 1
        assert data["is_active"] is True

    def test_user_achievement_serializer(self, user, achievement_first_dream):
        ua = UserAchievement.objects.create(user=user, achievement=achievement_first_dream)
        data = UserAchievementSerializer(ua).data
        assert "achievement" in data
        assert data["achievement"]["name"] == "First Dream"
        assert data["progress"] == 0

    def test_daily_activity_serializer(self, user):
        activity = DailyActivity.record_task_completion(user=user, xp_earned=10)
        data = DailyActivitySerializer(activity).data
        assert data["tasks_completed"] == 1
        assert data["xp_earned"] == 10

    def test_habit_chain_serializer(self, user):
        hc = HabitChain.objects.create(
            user=user, date=date.today(), chain_type="check_in",
        )
        data = HabitChainSerializer(hc).data
        assert data["chain_type"] == "check_in"
        assert data["completed"] is True
        assert "date" in data


# ═══════════════════════════════════════════════════════════════════
# View / API Tests
# ═══════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestGamificationProfileView:
    """GET /api/v1/gamification/profile/ tests."""

    def test_get_profile(self, auth_client, user):
        resp = auth_client.get("/api/v1/gamification/profile/")
        assert resp.status_code == 200
        assert "health_xp" in resp.data
        assert "skill_radar" in resp.data
        assert "streak_jokers" in resp.data

    def test_unauthenticated(self, api_client):
        resp = api_client.get("/api/v1/gamification/profile/")
        assert resp.status_code == 401

    def test_creates_profile_if_missing(self, auth_client, user):
        GamificationProfile.objects.filter(user=user).delete()
        resp = auth_client.get("/api/v1/gamification/profile/")
        assert resp.status_code == 200
        assert GamificationProfile.objects.filter(user=user).exists()


@pytest.mark.django_db
class TestAchievementsView:
    """GET /api/v1/gamification/achievements/ tests."""

    def test_empty(self, auth_client):
        resp = auth_client.get("/api/v1/gamification/achievements/")
        assert resp.status_code == 200
        assert resp.data["achievements"] == []
        assert resp.data["total_count"] == 0
        assert resp.data["unlocked_count"] == 0

    def test_with_achievements(self, auth_client, user, achievement_first_dream, achievement_streak_7):
        UserAchievement.objects.create(user=user, achievement=achievement_first_dream)
        resp = auth_client.get("/api/v1/gamification/achievements/")
        assert resp.status_code == 200
        assert resp.data["total_count"] == 2
        assert resp.data["unlocked_count"] == 1

        for a in resp.data["achievements"]:
            if a["name"] == "First Dream":
                assert a["unlocked"] is True
                assert a["progress"] == 1  # condition_value when unlocked with 0 progress
            elif a["name"] == "Week Warrior":
                assert a["unlocked"] is False

    def test_inactive_excluded(self, auth_client, inactive_achievement):
        resp = auth_client.get("/api/v1/gamification/achievements/")
        assert resp.data["total_count"] == 0

    def test_progress_capped(self, auth_client, user, achievement_tasks_10):
        """Progress should be capped at condition_value."""
        resp = auth_client.get("/api/v1/gamification/achievements/")
        # User has 0 tasks completed, so progress = 0
        a = resp.data["achievements"][0]
        assert a["progress"] <= a["requirement_value"]

    def test_unauthenticated(self, api_client):
        resp = api_client.get("/api/v1/gamification/achievements/")
        assert resp.status_code == 401


@pytest.mark.django_db
class TestActivityHeatmapView:
    """GET /api/v1/gamification/heatmap/ tests."""

    def test_default_28_days(self, auth_client, user):
        resp = auth_client.get("/api/v1/gamification/heatmap/")
        assert resp.status_code == 200
        assert len(resp.data["heatmap"]) == 28

    def test_custom_days(self, auth_client, user):
        resp = auth_client.get("/api/v1/gamification/heatmap/?days=7")
        assert resp.status_code == 200
        assert len(resp.data["heatmap"]) == 7

    def test_heatmap_with_data(self, auth_client, user):
        today = date.today()
        DailyActivity.objects.create(user=user, date=today, tasks_completed=5, xp_earned=100)
        resp = auth_client.get("/api/v1/gamification/heatmap/?days=1")
        entry = resp.data["heatmap"][0]
        assert entry["tasks_completed"] == 5
        assert entry["xp_earned"] == 100

    def test_unauthenticated(self, api_client):
        resp = api_client.get("/api/v1/gamification/heatmap/")
        assert resp.status_code == 401


@pytest.mark.django_db
class TestDailyStatsView:
    """GET /api/v1/gamification/daily-stats/ tests."""

    def test_no_activity(self, auth_client, user):
        resp = auth_client.get("/api/v1/gamification/daily-stats/")
        assert resp.status_code == 200
        assert resp.data["tasks_completed"] == 0
        assert resp.data["xp_earned"] == 0
        assert resp.data["level"] == user.level
        assert resp.data["streak_days"] == user.streak_days

    def test_with_activity(self, auth_client, user):
        DailyActivity.objects.create(
            user=user, date=date.today(),
            tasks_completed=3, xp_earned=45, minutes_active=30,
        )
        resp = auth_client.get("/api/v1/gamification/daily-stats/")
        assert resp.data["tasks_completed"] == 3
        assert resp.data["xp_earned"] == 45
        assert resp.data["minutes_active"] == 30

    def test_unauthenticated(self, api_client):
        resp = api_client.get("/api/v1/gamification/daily-stats/")
        assert resp.status_code == 401


@pytest.mark.django_db
class TestStreakDetailsView:
    """GET /api/v1/gamification/streak-details/ tests."""

    def test_basic(self, auth_client, user):
        resp = auth_client.get("/api/v1/gamification/streak-details/")
        assert resp.status_code == 200
        assert "current_streak" in resp.data
        assert "longest_streak" in resp.data
        assert "streak_history" in resp.data
        assert len(resp.data["streak_history"]) == 14
        assert "freeze_count" in resp.data
        assert "freeze_available" in resp.data

    def test_with_streak(self, api_client, user):
        User.objects.filter(id=user.id).update(streak_days=10)
        user.refresh_from_db()
        today = date.today()
        DailyActivity.objects.create(user=user, date=today, tasks_completed=1)
        DailyActivity.objects.create(
            user=user, date=today - timedelta(days=1), tasks_completed=2,
        )

        api_client.force_authenticate(user=user)
        resp = api_client.get("/api/v1/gamification/streak-details/")
        assert resp.data["current_streak"] == 10
        # streak_history last entry should be 1 (today had tasks)
        assert resp.data["streak_history"][-1] == 1

    def test_streak_frozen_indicator(self, api_client, user):
        User.objects.filter(id=user.id).update(streak_days=5)
        user.refresh_from_db()
        # No activity yesterday => streak_frozen should be True
        api_client.force_authenticate(user=user)
        resp = api_client.get("/api/v1/gamification/streak-details/")
        assert resp.data["streak_frozen"] is True

    def test_unauthenticated(self, api_client):
        resp = api_client.get("/api/v1/gamification/streak-details/")
        assert resp.status_code == 401


@pytest.mark.django_db
class TestStreakFreezeView:
    """POST /api/v1/gamification/streak-freeze/ tests."""

    def test_use_freeze(self, auth_client, user):
        GamificationProfile.objects.get_or_create(user=user)
        resp = auth_client.post("/api/v1/gamification/streak-freeze/")
        assert resp.status_code == 200
        assert resp.data["freeze_count"] == 2

    def test_no_freezes_left(self, auth_client, user):
        profile, _ = GamificationProfile.objects.get_or_create(user=user)
        profile.streak_jokers = 0
        profile.save()
        resp = auth_client.post("/api/v1/gamification/streak-freeze/")
        assert resp.status_code == 400

    def test_decrement_jokers(self, auth_client, user):
        profile, _ = GamificationProfile.objects.get_or_create(user=user)
        assert profile.streak_jokers == 3

        auth_client.post("/api/v1/gamification/streak-freeze/")
        auth_client.post("/api/v1/gamification/streak-freeze/")

        profile.refresh_from_db()
        assert profile.streak_jokers == 1

    def test_unauthenticated(self, api_client):
        resp = api_client.post("/api/v1/gamification/streak-freeze/")
        assert resp.status_code == 401


@pytest.mark.django_db
class TestLeaderboardStatsView:
    """GET /api/v1/gamification/leaderboard/ tests."""

    def test_basic(self, auth_client, user):
        resp = auth_client.get("/api/v1/gamification/leaderboard/")
        assert resp.status_code == 200
        assert "xp_rank" in resp.data
        assert "streak_rank" in resp.data
        assert "total_users" in resp.data
        assert "xp" in resp.data
        assert "level" in resp.data

    def test_ranking(self, auth_client, user, user2):
        User.objects.filter(id=user.id).update(xp=100)
        User.objects.filter(id=user2.id).update(xp=200)
        user.refresh_from_db()

        resp = auth_client.get("/api/v1/gamification/leaderboard/")
        assert resp.data["xp_rank"] == 2  # user2 has more XP
        assert resp.data["total_users"] >= 2

    def test_unauthenticated(self, api_client):
        resp = api_client.get("/api/v1/gamification/leaderboard/")
        assert resp.status_code == 401


# ═══════════════════════════════════════════════════════════════════
# Task Tests
# ═══════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestTasks:
    """Celery task tests."""

    def test_check_broken_streaks_task(self, user):
        from apps.gamification.tasks import check_broken_streaks

        three_days_ago = timezone.now().date() - timedelta(days=3)
        User.objects.filter(id=user.id).update(
            streak_days=5, streak_updated_at=three_days_ago,
        )

        result = check_broken_streaks()
        assert "reset" in result
        assert "notified" in result
        user.refresh_from_db()
        assert user.streak_days == 0

    def test_refresh_leaderboard_cache_task(self):
        from apps.gamification.tasks import refresh_leaderboard_cache

        # Should not raise
        refresh_leaderboard_cache()


# ═══════════════════════════════════════════════════════════════════
# Signal Tests
# ═══════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestSignals:
    """Signal tests."""

    def test_auto_create_profile_on_user_creation(self, db):
        user = User.objects.create_user(
            email="signal_test@stepora.app",
            password="Testpass123!",
        )
        assert GamificationProfile.objects.filter(user=user).exists()

    def test_profile_not_duplicated_on_save(self, user):
        # Profile already exists from signal
        count_before = GamificationProfile.objects.filter(user=user).count()
        user.display_name = "Updated"
        user.save()
        count_after = GamificationProfile.objects.filter(user=user).count()
        assert count_before == count_after


# ═══════════════════════════════════════════════════════════════════
# Edge Cases
# ═══════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestEdgeCases:
    """Edge case and boundary tests."""

    def test_user_with_no_dreams_progress(self, auth_client, user, achievement_first_dream):
        resp = auth_client.get("/api/v1/gamification/achievements/")
        a = resp.data["achievements"][0]
        assert a["progress"] == 0
        assert a["unlocked"] is False

    def test_heatmap_all_zeros(self, auth_client, user):
        resp = auth_client.get("/api/v1/gamification/heatmap/?days=3")
        for entry in resp.data["heatmap"]:
            assert entry["tasks_completed"] == 0
            assert entry["xp_earned"] == 0

    def test_streak_freeze_view_creates_profile(self, auth_client, user):
        """Profile should be auto-created if missing."""
        GamificationProfile.objects.filter(user=user).delete()
        resp = auth_client.post("/api/v1/gamification/streak-freeze/")
        # Should not 500 -- profile is created via get_or_create
        assert resp.status_code in (200, 400)
        assert GamificationProfile.objects.filter(user=user).exists()

    def test_daily_stats_xp_to_next_level(self, auth_client, user):
        User.objects.filter(id=user.id).update(xp=75)
        user.refresh_from_db()
        resp = auth_client.get("/api/v1/gamification/daily-stats/")
        assert resp.data["xp_to_next_level"] == 25

    def test_concurrent_xp_adds(self, user, profile):
        """Simulate concurrent XP adds using atomic F()."""
        profile.add_attribute_xp("health", 50)
        profile.add_attribute_xp("health", 50)
        profile.refresh_from_db()
        assert profile.health_xp == 100

    def test_record_task_completion_concurrent(self, user):
        """Multiple simultaneous task completions."""
        for _ in range(5):
            DailyActivity.record_task_completion(user=user, xp_earned=10)
        activity = DailyActivity.objects.get(user=user, date=timezone.now().date())
        assert activity.tasks_completed == 5
        assert activity.xp_earned == 50

    def test_achievement_progress_capped_at_condition_value(self, user, achievement_streak_7):
        """Even with streak_days=100, progress is capped at condition_value."""
        User.objects.filter(id=user.id).update(streak_days=100)
        user.refresh_from_db()
        # Don't unlock -- check the raw progress in the view
        resp = auth_client_for(user).get("/api/v1/gamification/achievements/")
        for a in resp.data["achievements"]:
            assert a["progress"] <= a["requirement_value"]


def auth_client_for(user):
    """Helper to create an authenticated client for a user."""
    client = APIClient()
    client.force_authenticate(user=user)
    return client
