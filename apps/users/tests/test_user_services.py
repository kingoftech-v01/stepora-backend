"""
Tests for apps.users.services — UserStatsService, AchievementService.

Note: The actual ProfileService (avatar upload, data export, account deletion)
is NOT present in apps/users/services.py. The file contains UserStatsService
and AchievementService, so we test those. BuddyMatchingService is a
backward-compat re-export tested in apps/buddies/tests/.
"""

from datetime import timedelta

import pytest
from django.utils import timezone

from apps.dreams.models import Dream, Goal, Task
from apps.users.services import AchievementService, UserStatsService

# ══════════════════════════════════════════════════════════════════════
#  UserStatsService
# ══════════════════════════════════════════════════════════════════════


class TestUserStatsService:
    """Tests for user statistics computation."""

    def test_get_stats_empty_user(self, users_user):
        """Stats for a user with no dreams/tasks returns zeros."""
        stats = UserStatsService.get_user_stats(users_user)
        assert stats["level"] == users_user.level
        assert stats["xp"] == users_user.xp
        assert stats["streak_days"] == users_user.streak_days
        assert stats["total_dreams"] == 0
        assert stats["active_dreams"] == 0
        assert stats["completed_dreams"] == 0
        assert stats["total_tasks_completed"] == 0
        assert stats["tasks_completed_this_week"] == 0
        assert stats["member_since"] == users_user.created_at

    def test_get_stats_with_dreams(self, users_user):
        """Stats reflect dream counts correctly."""
        Dream.objects.create(
            user=users_user, title="D1", description="d", status="active"
        )
        Dream.objects.create(
            user=users_user, title="D2", description="d", status="completed"
        )
        Dream.objects.create(
            user=users_user, title="D3", description="d", status="paused"
        )

        stats = UserStatsService.get_user_stats(users_user)
        assert stats["total_dreams"] == 3
        assert stats["active_dreams"] == 1
        assert stats["completed_dreams"] == 1

    def test_get_stats_tasks_completed(self, users_user):
        """Stats count completed tasks across all dreams/goals."""
        dream = Dream.objects.create(
            user=users_user, title="D", description="d", status="active"
        )
        goal = Goal.objects.create(dream=dream, title="G", order=0, status="pending")
        Task.objects.create(goal=goal, title="T1", order=0, status="completed")
        Task.objects.create(goal=goal, title="T2", order=1, status="completed")
        Task.objects.create(goal=goal, title="T3", order=2, status="pending")

        stats = UserStatsService.get_user_stats(users_user)
        assert stats["total_tasks_completed"] == 2

    def test_get_stats_tasks_this_week(self, users_user):
        """Stats count tasks completed in the current week."""
        dream = Dream.objects.create(
            user=users_user, title="D", description="d", status="active"
        )
        goal = Goal.objects.create(dream=dream, title="G", order=0, status="pending")
        # Task completed recently
        t1 = Task.objects.create(
            goal=goal, title="T1", order=0, status="completed"
        )
        t1.completed_at = timezone.now() - timedelta(days=1)
        t1.save(update_fields=["completed_at"])
        # Task completed long ago
        t2 = Task.objects.create(
            goal=goal, title="T2", order=1, status="completed"
        )
        t2.completed_at = timezone.now() - timedelta(days=30)
        t2.save(update_fields=["completed_at"])

        stats = UserStatsService.get_user_stats(users_user)
        assert stats["tasks_completed_this_week"] == 1

    def test_get_stats_xp_to_next_level(self, users_user):
        """xp_to_next_level is correctly derived from XP."""
        users_user.xp = 150
        users_user.save(update_fields=["xp"])
        stats = UserStatsService.get_user_stats(users_user)
        assert stats["xp_to_next_level"] == 50  # 100 - (150 % 100)

    def test_get_stats_subscription_field(self, users_user):
        """Stats include the subscription field."""
        stats = UserStatsService.get_user_stats(users_user)
        assert stats["subscription"] == users_user.subscription


# ══════════════════════════════════════════════════════════════════════
#  AchievementService
# ══════════════════════════════════════════════════════════════════════


class TestAchievementService:
    """Tests for achievement checking and unlocking."""

    @pytest.fixture
    def setup_achievements(self, users_user):
        """Create some test achievements."""
        from apps.users.models import Achievement

        a1 = Achievement.objects.create(
            name="First Dream",
            description="Create your first dream",
            condition_type="first_dream",
            condition_value=1,
            xp_reward=50,
            is_active=True,
        )
        a2 = Achievement.objects.create(
            name="Streak Master",
            description="Reach 7 day streak",
            condition_type="streak_days",
            condition_value=7,
            xp_reward=100,
            is_active=True,
        )
        a3 = Achievement.objects.create(
            name="Inactive Achievement",
            description="Should not be checked",
            condition_type="first_dream",
            condition_value=1,
            xp_reward=10,
            is_active=False,
        )
        return {"a1": a1, "a2": a2, "a3": a3}

    def test_no_achievements_unlocked_initially(self, users_user, setup_achievements):
        """User with no dreams/streaks unlocks nothing."""
        unlocked = AchievementService.check_achievements(users_user)
        assert len(unlocked) == 0

    def test_unlock_first_dream(self, users_user, setup_achievements):
        """Creating a dream unlocks 'First Dream' achievement."""
        Dream.objects.create(
            user=users_user, title="My Dream", description="d", status="active"
        )
        unlocked = AchievementService.check_achievements(users_user)
        names = [a.name for a in unlocked]
        assert "First Dream" in names

    def test_unlock_streak_achievement(self, users_user, setup_achievements):
        """Reaching streak_days >= 7 unlocks streak achievement."""
        users_user.streak_days = 10
        users_user.save(update_fields=["streak_days"])
        unlocked = AchievementService.check_achievements(users_user)
        names = [a.name for a in unlocked]
        assert "Streak Master" in names

    def test_inactive_achievements_not_checked(self, users_user, setup_achievements):
        """Inactive achievements are never unlocked."""
        Dream.objects.create(
            user=users_user, title="D", description="d", status="active"
        )
        unlocked = AchievementService.check_achievements(users_user)
        names = [a.name for a in unlocked]
        assert "Inactive Achievement" not in names

    def test_already_unlocked_not_duplicated(self, users_user, setup_achievements):
        """An achievement already unlocked is not unlocked again."""
        from apps.users.models import UserAchievement

        Dream.objects.create(
            user=users_user, title="D", description="d", status="active"
        )
        # First check — should unlock
        first = AchievementService.check_achievements(users_user)
        assert len(first) == 1

        # Second check — should NOT re-unlock
        second = AchievementService.check_achievements(users_user)
        assert len(second) == 0

        # Only one UserAchievement record exists
        assert (
            UserAchievement.objects.filter(
                user=users_user, achievement=setup_achievements["a1"]
            ).count()
            == 1
        )

    def test_xp_reward_applied(self, users_user, setup_achievements):
        """Unlocking an achievement grants XP to the user."""
        initial_xp = users_user.xp
        Dream.objects.create(
            user=users_user, title="D", description="d", status="active"
        )
        AchievementService.check_achievements(users_user)
        users_user.refresh_from_db()
        assert users_user.xp == initial_xp + 50  # a1.xp_reward

    def test_notification_created_on_unlock(self, users_user, setup_achievements):
        """Unlocking an achievement creates a notification."""
        from apps.notifications.models import Notification

        Dream.objects.create(
            user=users_user, title="D", description="d", status="active"
        )
        AchievementService.check_achievements(users_user)
        notif = Notification.objects.filter(
            user=users_user, notification_type="achievement"
        )
        assert notif.exists()
        assert "First Dream" in notif.first().title

    def test_multiple_achievements_unlocked_at_once(self, users_user, setup_achievements):
        """Multiple achievements can be unlocked in a single check."""
        Dream.objects.create(
            user=users_user, title="D", description="d", status="active"
        )
        users_user.streak_days = 7
        users_user.save(update_fields=["streak_days"])
        unlocked = AchievementService.check_achievements(users_user)
        assert len(unlocked) == 2


# ══════════════════════════════════════════════════════════════════════
#  Backward-compat re-exports
# ══════════════════════════════════════════════════════════════════════


class TestBackwardCompatImports:
    """Verify that the backward-compat re-exports work."""

    def test_buddy_matching_service_importable(self):
        """BuddyMatchingService is importable from apps.users.services."""
        from apps.users.services import BuddyMatchingService

        assert BuddyMatchingService is not None

    def test_buddy_pairing_importable(self):
        """BuddyPairing is importable from apps.users.services."""
        from apps.users.services import BuddyPairing

        assert BuddyPairing is not None
