"""
Fixtures for store tests.
"""

from decimal import Decimal

import pytest

from apps.store.models import StoreCategory, StoreItem, UserInventory
from apps.users.models import User


@pytest.fixture
def store_user(db):
    """Create a user for store tests."""
    return User.objects.create_user(
        email="storeuser@example.com",
        password="testpass123",
        display_name="Store User",
    )


@pytest.fixture
def store_user2(db):
    """Create a second user for store tests."""
    return User.objects.create_user(
        email="storeuser2@example.com",
        password="testpass123",
        display_name="Store User 2",
    )


@pytest.fixture
def test_category(db):
    """Create a test store category."""
    return StoreCategory.objects.create(
        name="Badge Frames",
        slug="badge-frames",
        description="Decorative badge frames",
        display_order=1,
        is_active=True,
    )


@pytest.fixture
def test_category2(db):
    """Create a second test category."""
    return StoreCategory.objects.create(
        name="Theme Skins",
        slug="theme-skins",
        description="Custom themes",
        display_order=2,
        is_active=True,
    )


@pytest.fixture
def test_item(db, test_category):
    """Create a test store item."""
    return StoreItem.objects.create(
        category=test_category,
        name="Gold Frame",
        slug="gold-frame",
        description="A golden badge frame",
        price=Decimal("4.99"),
        item_type="badge_frame",
        rarity="rare",
        is_active=True,
    )


@pytest.fixture
def test_item2(db, test_category):
    """Create a second store item."""
    return StoreItem.objects.create(
        category=test_category,
        name="Silver Frame",
        slug="silver-frame",
        price=Decimal("2.99"),
        item_type="badge_frame",
        rarity="common",
        is_active=True,
    )


@pytest.fixture
def legendary_item(db, test_category2):
    """Create a legendary store item."""
    return StoreItem.objects.create(
        category=test_category2,
        name="Cosmic Theme",
        slug="cosmic-theme",
        price=Decimal("9.99"),
        item_type="theme_skin",
        rarity="legendary",
        is_active=True,
    )


@pytest.fixture
def user_inventory_entry(db, store_user, test_item):
    """Create a user inventory entry (owned item)."""
    return UserInventory.objects.create(
        user=store_user,
        item=test_item,
        stripe_payment_intent_id="pi_test_123",
        is_equipped=False,
    )
