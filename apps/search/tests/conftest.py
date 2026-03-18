"""
Fixtures for search tests.
"""

import pytest

from apps.dreams.models import Dream, Goal, Task
from apps.users.models import User


@pytest.fixture
def search_user(db):
    """Create a user for search tests."""
    return User.objects.create_user(
        email="searchuser@example.com",
        password="testpass123",
        display_name="Search User",
    )


@pytest.fixture
def search_user2(db):
    """Create a second user for search tests."""
    return User.objects.create_user(
        email="searchuser2@example.com",
        password="testpass123",
        display_name="Another User",
    )


@pytest.fixture
def search_dream(db, search_user):
    """Create a dream for search tests."""
    return Dream.objects.create(
        user=search_user,
        title="Learn Python Programming",
        description="Master Python for data science and web development",
        category="education",
        status="active",
    )


@pytest.fixture
def search_dream2(db, search_user):
    """Create a second dream for search tests."""
    return Dream.objects.create(
        user=search_user,
        title="Build a Startup",
        description="Launch a tech startup for mobile apps",
        category="career",
        status="active",
    )


@pytest.fixture
def search_goal(db, search_dream):
    """Create a goal for search tests."""
    return Goal.objects.create(
        dream=search_dream,
        title="Complete Python Tutorial",
        description="Follow the official Python tutorial",
        order=0,
        status="pending",
    )


@pytest.fixture
def search_task(db, search_goal):
    """Create a task for search tests."""
    return Task.objects.create(
        goal=search_goal,
        title="Read Python Documentation",
        description="Read the official Python docs",
        order=0,
        duration_mins=60,
        status="pending",
    )
