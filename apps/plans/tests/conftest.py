"""
Test fixtures for plans app tests.
"""

import pytest
from django.utils import timezone

from apps.dreams.models import Dream
from apps.users.models import User


@pytest.fixture
def plans_user(db):
    """Create a test user for plans tests."""
    return User.objects.create_user(
        email="plans@test.com",
        password="testpass123",
        display_name="Plans Tester",
    )


@pytest.fixture
def plans_dream(plans_user):
    """Create a test dream."""
    return Dream.objects.create(
        user=plans_user,
        title="Test Dream",
        description="A test dream for plans",
        status="active",
        target_date=timezone.now() + timezone.timedelta(days=180),
    )


@pytest.fixture
def plans_milestone(plans_dream):
    """Create a test milestone."""
    from apps.plans.models import DreamMilestone

    return DreamMilestone.objects.create(
        dream=plans_dream,
        title="Month 1",
        order=1,
    )


@pytest.fixture
def plans_goal(plans_dream, plans_milestone):
    """Create a test goal."""
    from apps.plans.models import Goal

    return Goal.objects.create(
        dream=plans_dream,
        milestone=plans_milestone,
        title="Test Goal",
        order=1,
    )


@pytest.fixture
def plans_task(plans_goal):
    """Create a test task."""
    from apps.plans.models import Task

    return Task.objects.create(
        goal=plans_goal,
        title="Test Task",
        order=1,
        duration_mins=30,
    )
