"""
Fixtures for social app tests.
"""

import uuid
from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.users.models import User


@pytest.fixture
def social_user(db):
    """Create a user for social tests."""
    return User.objects.create_user(
        email="socialuser@example.com",
        password="testpassword123",
        display_name="Social User",
        timezone="Europe/Paris",
    )


@pytest.fixture
def social_user2(db):
    """Create a second user for social tests."""
    return User.objects.create_user(
        email="socialuser2@example.com",
        password="testpassword123",
        display_name="Social User 2",
        timezone="Europe/Paris",
    )


@pytest.fixture
def social_user3(db):
    """Create a third user for social tests."""
    return User.objects.create_user(
        email="socialuser3@example.com",
        password="testpassword123",
        display_name="Social User 3",
        timezone="Europe/Paris",
    )


@pytest.fixture
def social_client(social_user):
    """Authenticated API client for social_user."""
    client = APIClient()
    client.force_authenticate(user=social_user)
    return client


@pytest.fixture
def social_client2(social_user2):
    """Authenticated API client for social_user2."""
    client = APIClient()
    client.force_authenticate(user=social_user2)
    return client
