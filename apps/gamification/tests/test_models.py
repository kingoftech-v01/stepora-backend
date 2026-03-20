"""
Tests for gamification models.
"""

import pytest

from apps.gamification.models import (
    Achievement,
    DailyActivity,
    GamificationProfile,
    HabitChain,
    UserAchievement,
)


@pytest.mark.django_db
class TestGamificationProfile:
    """Tests for the GamificationProfile model."""

    def test_create_profile(self, gamification_user):
        profile, created = GamificationProfile.objects.get_or_create(
            user=gamification_user
        )
        assert profile.user == gamification_user
        assert profile.streak_jokers == 3

    def test_get_attribute_level_default(self, gamification_profile):
        assert gamification_profile.get_attribute_level("health") == 1

    def test_get_attribute_level_with_xp(self, gamification_profile):
        gamification_profile.health_xp = 250
        gamification_profile.save()
        assert gamification_profile.get_attribute_level("health") == 3

    def test_add_attribute_xp(self, gamification_profile):
        gamification_profile.health_xp = 0
        gamification_profile.save()
        gamification_profile.add_attribute_xp("health", 50)
        assert gamification_profile.health_xp == 50

    def test_add_attribute_xp_cumulative(self, gamification_profile):
        gamification_profile.health_xp = 0
        gamification_profile.save()
        gamification_profile.add_attribute_xp("health", 50)
        gamification_profile.add_attribute_xp("health", 30)
        assert gamification_profile.health_xp == 80

    def test_str_representation(self, gamification_profile):
        assert "Gamification" in str(gamification_profile)


@pytest.mark.django_db
class TestAchievement:
    """Tests for the Achievement model."""

    def test_create_achievement(self, achievement):
        assert achievement.name == "First Dream"
        assert achievement.xp_reward == 50
        assert achievement.is_active is True

    def test_str_representation(self, achievement):
        assert "sparkles" in str(achievement)
        assert "First Dream" in str(achievement)


@pytest.mark.django_db
class TestUserAchievement:
    """Tests for the UserAchievement model."""

    def test_unlock_achievement(self, gamification_user, achievement):
        ua = UserAchievement.objects.create(
            user=gamification_user, achievement=achievement
        )
        assert ua.user == gamification_user
        assert ua.achievement == achievement
        assert ua.progress == 0

    def test_unique_constraint(self, gamification_user, achievement):
        UserAchievement.objects.create(
            user=gamification_user, achievement=achievement
        )
        with pytest.raises(Exception):
            UserAchievement.objects.create(
                user=gamification_user, achievement=achievement
            )


@pytest.mark.django_db
class TestDailyActivity:
    """Tests for the DailyActivity model."""

    def test_record_task_completion(self, gamification_user):
        activity = DailyActivity.record_task_completion(
            user=gamification_user, xp_earned=10, duration_mins=15
        )
        assert activity.tasks_completed == 1
        assert activity.xp_earned == 10
        assert activity.minutes_active == 15

    def test_record_task_completion_cumulative(self, gamification_user):
        DailyActivity.record_task_completion(
            user=gamification_user, xp_earned=10, duration_mins=15
        )
        activity = DailyActivity.record_task_completion(
            user=gamification_user, xp_earned=20, duration_mins=30
        )
        assert activity.tasks_completed == 2
        assert activity.xp_earned == 30
        assert activity.minutes_active == 45


@pytest.mark.django_db
class TestHabitChain:
    """Tests for the HabitChain model."""

    def test_create_habit_event(self, gamification_user):
        from datetime import date

        habit = HabitChain.objects.create(
            user=gamification_user,
            date=date.today(),
            chain_type="task_completion",
        )
        assert habit.completed is True
        assert habit.chain_type == "task_completion"
