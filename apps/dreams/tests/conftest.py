"""
Shared fixtures for Dreams app tests.
"""

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.dreams.models import (
    Dream,
    DreamMilestone,
    DreamProgressSnapshot,
    FocusSession,
    Goal,
    Task,
)
from apps.users.models import User


@pytest.fixture
def dream_user(db):
    """Create a test user for dream tests."""
    return User.objects.create_user(
        email="dream_user@example.com",
        password="testpassword123",
        display_name="Dream User",
        timezone="Europe/Paris",
    )


@pytest.fixture
def dream_user2(db):
    """Create a second test user for dream tests."""
    return User.objects.create_user(
        email="dream_user2@example.com",
        password="testpassword123",
        display_name="Dream User 2",
        timezone="Europe/Paris",
    )


@pytest.fixture
def dream_client(dream_user):
    """Return an authenticated API client for dream tests."""
    client = APIClient()
    client.force_authenticate(user=dream_user)
    return client


@pytest.fixture
def dream_client2(dream_user2):
    """Return an authenticated API client for dream_user2."""
    client = APIClient()
    client.force_authenticate(user=dream_user2)
    return client


@pytest.fixture
def test_dream(db, dream_user):
    """Create a test dream."""
    return Dream.objects.create(
        user=dream_user,
        title="Learn Spanish",
        description="Become fluent in Spanish language",
        category="education",
        status="active",
        priority=1,
    )


@pytest.fixture
def test_milestone(db, test_dream):
    """Create a test milestone."""
    return DreamMilestone.objects.create(
        dream=test_dream,
        title="Month 1 - Basics",
        description="Learn basic vocabulary and grammar",
        order=1,
        status="pending",
    )


@pytest.fixture
def test_goal(db, test_dream):
    """Create a test goal."""
    return Goal.objects.create(
        dream=test_dream,
        title="Complete Basics Module",
        description="Finish the first module of the Spanish course",
        order=1,
        status="pending",
    )


@pytest.fixture
def test_goal_with_milestone(db, test_dream, test_milestone):
    """Create a test goal linked to a milestone."""
    return Goal.objects.create(
        dream=test_dream,
        milestone=test_milestone,
        title="Learn 100 Words",
        description="Memorize 100 basic Spanish words",
        order=1,
        status="pending",
    )


@pytest.fixture
def test_task(db, test_goal):
    """Create a test task."""
    return Task.objects.create(
        goal=test_goal,
        title="Study vocabulary",
        description="Study 10 new words today",
        order=1,
        duration_mins=30,
        status="pending",
    )


@pytest.fixture
def test_focus_session(db, dream_user, test_task):
    """Create a test focus session."""
    return FocusSession.objects.create(
        user=dream_user,
        task=test_task,
        duration_minutes=25,
        session_type="work",
    )
