"""
Fixtures for circles tests.
"""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.circles.models import (
    Circle,
    CircleChallenge,
    CircleMembership,
    CirclePost,
)
from apps.subscriptions.models import Subscription, SubscriptionPlan
from apps.users.models import User


@pytest.fixture
def circle_user(db):
    """Create a user with premium subscription for circle access."""
    user = User.objects.create_user(
        email="circleuser@example.com",
        password="testpass123",
        display_name="Circle User",
    )
    plan, _ = SubscriptionPlan.objects.get_or_create(
        slug="premium",
        defaults={
            "name": "Premium",
            "price_monthly": Decimal("19.99"),
            "has_circles": True,
            "has_circle_create": False,
        },
    )
    Subscription.objects.update_or_create(
        user=user,
        defaults={
            "plan": plan,
            "status": "active",
            "current_period_start": timezone.now(),
            "current_period_end": timezone.now() + timedelta(days=30),
        },
    )
    return user


@pytest.fixture
def circle_pro_user(db):
    """Create a user with pro subscription (can create circles)."""
    user = User.objects.create_user(
        email="circlepro@example.com",
        password="testpass123",
        display_name="Circle Pro User",
    )
    plan, _ = SubscriptionPlan.objects.get_or_create(
        slug="pro",
        defaults={
            "name": "Pro",
            "price_monthly": Decimal("29.99"),
            "has_circles": True,
            "has_circle_create": True,
        },
    )
    Subscription.objects.update_or_create(
        user=user,
        defaults={
            "plan": plan,
            "status": "active",
            "current_period_start": timezone.now(),
            "current_period_end": timezone.now() + timedelta(days=30),
        },
    )
    return user


@pytest.fixture
def free_circle_user(db):
    """Create a free user (no circle access)."""
    user = User.objects.create_user(
        email="freecirc@example.com",
        password="testpass123",
        display_name="Free Circle User",
    )
    plan, _ = SubscriptionPlan.objects.get_or_create(
        slug="free",
        defaults={
            "name": "Free",
            "price_monthly": Decimal("0.00"),
            "has_circles": False,
        },
    )
    Subscription.objects.update_or_create(
        user=user,
        defaults={"plan": plan, "status": "active"},
    )
    return user


@pytest.fixture
def circle_client(circle_user):
    """Authenticated API client for premium circle user."""
    client = APIClient()
    client.force_authenticate(user=circle_user)
    return client


@pytest.fixture
def circle_pro_client(circle_pro_user):
    """Authenticated API client for pro circle user."""
    client = APIClient()
    client.force_authenticate(user=circle_pro_user)
    return client


@pytest.fixture
def free_circle_client(free_circle_user):
    """Authenticated API client for free user."""
    client = APIClient()
    client.force_authenticate(user=free_circle_user)
    return client


@pytest.fixture
def test_circle(db, circle_pro_user):
    """Create a public test circle."""
    circle = Circle.objects.create(
        name="Test Circle",
        description="A test circle",
        category="career",
        is_public=True,
        creator=circle_pro_user,
        max_members=20,
    )
    CircleMembership.objects.create(
        circle=circle,
        user=circle_pro_user,
        role="admin",
    )
    return circle


@pytest.fixture
def private_circle(db, circle_pro_user):
    """Create a private test circle."""
    circle = Circle.objects.create(
        name="Private Circle",
        description="A private circle",
        category="education",
        is_public=False,
        creator=circle_pro_user,
        max_members=10,
    )
    CircleMembership.objects.create(
        circle=circle,
        user=circle_pro_user,
        role="admin",
    )
    return circle


@pytest.fixture
def test_post(db, test_circle, circle_pro_user):
    """Create a test post in a circle."""
    return CirclePost.objects.create(
        circle=test_circle,
        author=circle_pro_user,
        content="This is a test post",
    )


@pytest.fixture
def test_challenge(db, test_circle, circle_pro_user):
    """Create a test challenge in a circle."""
    return CircleChallenge.objects.create(
        circle=test_circle,
        creator=circle_pro_user,
        title="Test Challenge",
        description="A test challenge",
        challenge_type="tasks_completed",
        target_value=10,
        start_date=timezone.now(),
        end_date=timezone.now() + timedelta(days=7),
        status="active",
    )


@pytest.fixture
def anon_client():
    """Unauthenticated API client."""
    return APIClient()
