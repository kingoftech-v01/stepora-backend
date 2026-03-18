"""
Fixtures for users app tests.
"""

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.users.models import User, DailyActivity


@pytest.fixture
def users_user(db):
    """Create a user for users app tests."""
    return User.objects.create_user(
        email="userstest@example.com",
        password="testpassword123",
        display_name="Users Test User",
        timezone="Europe/Paris",
    )


@pytest.fixture
def users_client(users_user):
    """Authenticated API client for users_user."""
    client = APIClient()
    client.force_authenticate(user=users_user)
    return client


@pytest.fixture
def users_user2(db):
    """Create a second user for users app tests."""
    return User.objects.create_user(
        email="userstest2@example.com",
        password="testpassword123",
        display_name="Users Test User 2",
        timezone="America/New_York",
        profile_visibility="public",
    )


@pytest.fixture
def users_client2(users_user2):
    """Authenticated API client for users_user2."""
    client = APIClient()
    client.force_authenticate(user=users_user2)
    return client
