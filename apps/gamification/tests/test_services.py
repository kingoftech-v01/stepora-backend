"""
Tests for gamification services.
"""

import pytest

from apps.gamification.models import Achievement, UserAchievement
from apps.gamification.services import AchievementService, XPService
from apps.users.models import User


@pytest.fixture
def service_user(db):
    return User.objects.create_user(
        email="gamservice@test.com",
        password="testpass123",
        display_name="Service Tester",
    )


@pytest.mark.django_db
class TestAchievementService:
    """Tests for AchievementService."""

    def test_check_achievements_unlocks(self, service_user):
        # Create a dream so first_dream condition is met
        from apps.dreams.models import Dream

        Dream.objects.create(
            user=service_user,
            title="Test Dream",
            description="Test",
        )

        # Create achievement
        ach = Achievement.objects.create(
            name="First Dream Test",
            description="Create your first dream",
            icon="sparkles",
            category="dreams",
            condition_type="first_dream",
            condition_value=1,
        )

        newly_unlocked = AchievementService.check_achievements(service_user)
        assert len(newly_unlocked) == 1
        assert newly_unlocked[0].id == ach.id
        assert UserAchievement.objects.filter(
            user=service_user, achievement=ach
        ).exists()

    def test_check_achievements_idempotent(self, service_user):
        from apps.dreams.models import Dream

        Dream.objects.create(
            user=service_user,
            title="Test Dream",
            description="Test",
        )

        Achievement.objects.create(
            name="First Dream Idem",
            description="Create first dream",
            icon="sparkles",
            category="dreams",
            condition_type="first_dream",
            condition_value=1,
        )

        first = AchievementService.check_achievements(service_user)
        second = AchievementService.check_achievements(service_user)
        assert len(first) == 1
        assert len(second) == 0


@pytest.mark.django_db
class TestXPService:
    """Tests for XPService."""

    def test_award_xp(self, service_user):
        leveled = XPService.award_xp(service_user, 50)
        service_user.refresh_from_db()
        assert service_user.xp == 50
        assert leveled is False

    def test_award_xp_with_category(self, service_user):
        from apps.gamification.models import GamificationProfile

        GamificationProfile.objects.get_or_create(user=service_user)
        XPService.award_xp(service_user, 50, category="health")
        profile = GamificationProfile.objects.get(user=service_user)
        assert profile.health_xp == 50

    def test_get_level_info(self, service_user):
        service_user.xp = 250
        service_user.level = 3
        service_user.save()
        info = XPService.get_level_info(service_user)
        assert info["level"] == 3
        assert info["xp"] == 250
