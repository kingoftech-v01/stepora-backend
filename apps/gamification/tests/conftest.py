"""
Test fixtures for gamification app tests.
"""

import pytest

from apps.users.models import User


@pytest.fixture
def gamification_user(db):
    """Create a test user for gamification tests."""
    return User.objects.create_user(
        email="gamification@test.com",
        password="testpass123",
        display_name="Gamification Tester",
    )


@pytest.fixture
def gamification_profile(gamification_user):
    """Create a GamificationProfile for the test user."""
    from apps.gamification.models import GamificationProfile

    profile, _ = GamificationProfile.objects.get_or_create(user=gamification_user)
    return profile


@pytest.fixture
def achievement(db):
    """Create a test achievement."""
    from apps.gamification.models import Achievement

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
