"""
Test fixtures for friends app tests.
"""

import pytest

from apps.users.models import User


@pytest.fixture
def friend_user_a(db):
    return User.objects.create_user(
        email="frienda@test.com",
        password="testpass123",
        display_name="Friend A",
    )


@pytest.fixture
def friend_user_b(db):
    return User.objects.create_user(
        email="friendb@test.com",
        password="testpass123",
        display_name="Friend B",
    )


@pytest.fixture
def friend_user_c(db):
    return User.objects.create_user(
        email="friendc@test.com",
        password="testpass123",
        display_name="Friend C",
    )
