"""
Fixtures for subscriptions tests.
"""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.conf import settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.subscriptions.models import (
    Promotion,
    PromotionPlanDiscount,
    StripeCustomer,
    Subscription,
    SubscriptionPlan,
)
from apps.users.models import User


@pytest.fixture(scope="session")
def django_db_modify_db_settings():
    """Use a unique test database name to avoid collisions with parallel sessions."""
    test_cfg = settings.DATABASES["default"].setdefault("TEST", {})
    test_cfg["NAME"] = "test_stepora_subscriptions"


@pytest.fixture
def free_plan(db):
    """Get or create the free plan."""
    plan, _ = SubscriptionPlan.objects.get_or_create(
        slug="free",
        defaults={
            "name": "Free",
            "price_monthly": Decimal("0.00"),
            "dream_limit": 3,
            "has_ai": False,
            "has_buddy": False,
            "has_circles": False,
        },
    )
    return plan


@pytest.fixture
def premium_plan(db):
    """Get or create the premium plan."""
    plan, _ = SubscriptionPlan.objects.get_or_create(
        slug="premium",
        defaults={
            "name": "Premium",
            "price_monthly": Decimal("19.99"),
            "stripe_price_id": "price_test_premium",
            "dream_limit": 10,
            "has_ai": True,
            "has_buddy": True,
            "has_circles": True,
        },
    )
    return plan


@pytest.fixture
def pro_plan(db):
    """Get or create the pro plan."""
    plan, _ = SubscriptionPlan.objects.get_or_create(
        slug="pro",
        defaults={
            "name": "Pro",
            "price_monthly": Decimal("29.99"),
            "stripe_price_id": "price_test_pro",
            "dream_limit": -1,
            "has_ai": True,
            "has_buddy": True,
            "has_circles": True,
            "has_circle_create": True,
            "has_vision_board": True,
        },
    )
    return plan


@pytest.fixture
def sub_user(db):
    """Create a user for subscription tests."""
    return User.objects.create_user(
        email="subuser@example.com",
        password="testpass123",
        display_name="Sub User",
    )


@pytest.fixture
def sub_user2(db):
    """Create a second user for subscription tests."""
    return User.objects.create_user(
        email="subuser2@example.com",
        password="testpass123",
        display_name="Sub User 2",
    )


@pytest.fixture
def sub_client(sub_user):
    """Authenticated API client for sub_user."""
    client = APIClient()
    client.force_authenticate(user=sub_user)
    return client


@pytest.fixture
def free_subscription(db, sub_user, free_plan):
    """Create a free subscription for sub_user."""
    sub, _ = Subscription.objects.update_or_create(
        user=sub_user,
        defaults={
            "plan": free_plan,
            "status": "active",
        },
    )
    return sub


@pytest.fixture
def premium_subscription(db, sub_user, premium_plan):
    """Create an active premium subscription for sub_user."""
    sub, _ = Subscription.objects.update_or_create(
        user=sub_user,
        defaults={
            "plan": premium_plan,
            "status": "active",
            "stripe_subscription_id": "sub_test_123",
            "current_period_start": timezone.now(),
            "current_period_end": timezone.now() + timedelta(days=30),
        },
    )
    return sub


@pytest.fixture
def stripe_customer(db, sub_user):
    """Create a StripeCustomer record for sub_user."""
    sc, _ = StripeCustomer.objects.get_or_create(
        user=sub_user,
        defaults={"stripe_customer_id": "cus_test_123"},
    )
    return sc


@pytest.fixture
def active_promotion(db, premium_plan):
    """Create an active promotion with a plan discount."""
    promo = Promotion.objects.create(
        name="Test Promo",
        description="50% off premium",
        start_date=timezone.now() - timedelta(days=1),
        end_date=timezone.now() + timedelta(days=30),
        discount_type="percentage",
        max_redemptions=100,
        is_active=True,
    )
    PromotionPlanDiscount.objects.create(
        promotion=promo,
        plan=premium_plan,
        discount_value=Decimal("50.00"),
        stripe_coupon_id="coupon_test_50off",
    )
    return promo


@pytest.fixture
def anon_client():
    """Unauthenticated API client."""
    return APIClient()
