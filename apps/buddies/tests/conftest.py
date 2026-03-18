"""
Fixtures for buddies tests.
"""

from datetime import timedelta

import pytest
from django.utils import timezone

from apps.buddies.models import BuddyPairing
from apps.users.models import User


@pytest.fixture
def buddy_user1(db):
    """Create first buddy user."""
    return User.objects.create_user(
        email="buddy1@example.com",
        password="testpass123",
        display_name="Buddy One",
        timezone="Europe/Paris",
    )


@pytest.fixture
def buddy_user2(db):
    """Create second buddy user."""
    return User.objects.create_user(
        email="buddy2@example.com",
        password="testpass123",
        display_name="Buddy Two",
        timezone="Europe/Paris",
    )


@pytest.fixture
def buddy_user3(db):
    """Create third buddy user."""
    return User.objects.create_user(
        email="buddy3@example.com",
        password="testpass123",
        display_name="Buddy Three",
        timezone="America/New_York",
    )


@pytest.fixture
def active_pairing(db, buddy_user1, buddy_user2):
    """Create an active buddy pairing."""
    return BuddyPairing.objects.create(
        user1=buddy_user1,
        user2=buddy_user2,
        status="active",
        compatibility_score=0.75,
    )


@pytest.fixture
def pending_pairing(db, buddy_user1, buddy_user3):
    """Create a pending buddy pairing."""
    return BuddyPairing.objects.create(
        user1=buddy_user1,
        user2=buddy_user3,
        status="pending",
        compatibility_score=0.5,
        expires_at=timezone.now() + timedelta(days=7),
    )
