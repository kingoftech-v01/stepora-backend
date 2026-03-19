"""
Fixtures for updates app tests.
"""

import pytest
from rest_framework.test import APIClient

from apps.users.models import User


@pytest.fixture
def updates_user(db):
    """Create a normal user for updates tests."""
    return User.objects.create_user(
        email="updatesuser@example.com",
        password="testpass123",
    )


@pytest.fixture
def updates_admin(db):
    """Create an admin user for updates tests."""
    return User.objects.create_superuser(
        email="updatesadmin@example.com",
        password="adminpass123",
    )


@pytest.fixture
def updates_client(updates_user):
    """Authenticated API client for normal user."""
    client = APIClient()
    client.force_authenticate(user=updates_user)
    return client


@pytest.fixture
def admin_client(updates_admin):
    """Authenticated API client for admin user."""
    client = APIClient()
    client.force_authenticate(user=updates_admin)
    return client


@pytest.fixture
def anon_client():
    """Unauthenticated API client."""
    return APIClient()
