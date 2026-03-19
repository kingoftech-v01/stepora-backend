"""
Unit tests for the Store app models.
"""

from decimal import Decimal

import pytest
from django.db import IntegrityError

from apps.store.models import (
    Gift,
    StoreCategory,
    StoreItem,
    UserInventory,
    Wishlist,
)
from apps.users.models import User


# ── StoreItem model ───────────────────────────────────────────────────


class TestStoreItemModel:
    """Tests for the StoreItem model."""

    def test_create_item(self, test_item, test_category):
        """StoreItem can be created with required fields."""
        assert test_item.name == "Gold Frame"
        assert test_item.slug == "gold-frame"
        assert test_item.price == Decimal("4.99")
        assert test_item.item_type == "badge_frame"
        assert test_item.rarity == "rare"
        assert test_item.category == test_category

    def test_str_representation(self, test_item):
        """__str__ includes name, rarity, and price."""
        s = str(test_item)
        assert "Gold Frame" in s
        assert "Rare" in s
        assert "4.99" in s

    def test_item_type_choices(self, test_category):
        """All item types can be created."""
        for code, _ in StoreItem.ITEM_TYPE_CHOICES:
            item = StoreItem.objects.create(
                category=test_category,
                name=f"Item {code}",
                slug=f"item-{code}",
                price=Decimal("1.99"),
                item_type=code,
            )
            assert item.item_type == code

    def test_rarity_choices(self, test_category):
        """All rarity levels can be assigned."""
        for code, _ in StoreItem.RARITY_CHOICES:
            item = StoreItem.objects.create(
                category=test_category,
                name=f"Rarity {code}",
                slug=f"rarity-{code}",
                price=Decimal("1.99"),
                item_type="badge_frame",
                rarity=code,
            )
            assert item.rarity == code

    def test_unique_slug(self, test_item, test_category):
        """Slug must be unique."""
        with pytest.raises(IntegrityError):
            StoreItem.objects.create(
                category=test_category,
                name="Duplicate",
                slug="gold-frame",
                price=Decimal("1.99"),
                item_type="badge_frame",
            )

    def test_metadata_field(self, test_category):
        """Metadata JSON field stores data correctly."""
        item = StoreItem.objects.create(
            category=test_category,
            name="Animated Frame",
            slug="animated-frame",
            price=Decimal("7.99"),
            item_type="badge_frame",
            metadata={"animation": "pulse", "color": "#FF0000"},
        )
        item.refresh_from_db()
        assert item.metadata["animation"] == "pulse"

    def test_xp_price(self, test_category):
        """Items can have an XP price for XP-based purchasing."""
        item = StoreItem.objects.create(
            category=test_category,
            name="XP Item",
            slug="xp-item",
            price=Decimal("0.00"),
            item_type="badge_frame",
            xp_price=500,
        )
        assert item.xp_price == 500

    def test_default_xp_price_is_zero(self, test_item):
        """Default xp_price is 0."""
        assert test_item.xp_price == 0

    def test_is_active_default(self, test_item):
        """Items are active by default."""
        assert test_item.is_active is True

    def test_preview_fields(self, test_category):
        """Preview type and data can be set."""
        item = StoreItem.objects.create(
            category=test_category,
            name="Preview Item",
            slug="preview-item",
            price=Decimal("3.99"),
            item_type="theme_skin",
            preview_type="theme",
            preview_data={"accent": "#8B5CF6", "bg": "#1a1a2e"},
        )
        assert item.preview_type == "theme"
        assert item.preview_data["accent"] == "#8B5CF6"


# ── StoreCategory model ──────────────────────────────────────────────


class TestStoreCategoryModel:
    """Tests for the StoreCategory model."""

    def test_create_category(self, test_category):
        """StoreCategory can be created."""
        assert test_category.name == "Badge Frames"
        assert test_category.slug == "badge-frames"

    def test_str_representation(self, test_category):
        """__str__ returns category name."""
        assert str(test_category) == "Badge Frames"

    def test_unique_name(self, test_category):
        """Category name must be unique."""
        with pytest.raises(IntegrityError):
            StoreCategory.objects.create(
                name="Badge Frames",
                slug="badge-frames-dup",
            )

    def test_unique_slug(self, test_category):
        """Category slug must be unique."""
        with pytest.raises(IntegrityError):
            StoreCategory.objects.create(
                name="Different Name",
                slug="badge-frames",
            )

    def test_ordering(self, test_category, test_category2):
        """Categories ordered by display_order."""
        categories = list(StoreCategory.objects.all())
        orders = [c.display_order for c in categories]
        assert orders == sorted(orders)


# ── UserInventory model ──────────────────────────────────────────────


class TestUserInventoryModel:
    """Tests for the UserInventory model."""

    def test_create_inventory(self, user_inventory_entry, store_user, test_item):
        """UserInventory can be created."""
        assert user_inventory_entry.user == store_user
        assert user_inventory_entry.item == test_item
        assert user_inventory_entry.is_equipped is False

    def test_str_representation(self, user_inventory_entry):
        """__str__ includes user email and item name."""
        s = str(user_inventory_entry)
        assert "storeuser@example.com" in s
        assert "Gold Frame" in s

    def test_equip_item(self, user_inventory_entry):
        """Item can be equipped."""
        user_inventory_entry.is_equipped = True
        user_inventory_entry.save()
        user_inventory_entry.refresh_from_db()
        assert user_inventory_entry.is_equipped is True
        assert "[EQUIPPED]" in str(user_inventory_entry)

    def test_unique_user_item(self, store_user, test_item, user_inventory_entry):
        """A user cannot own the same item twice."""
        with pytest.raises(IntegrityError):
            UserInventory.objects.create(
                user=store_user,
                item=test_item,
            )

    def test_different_users_same_item(self, store_user2, test_item):
        """Different users can own the same item."""
        entry = UserInventory.objects.create(
            user=store_user2,
            item=test_item,
        )
        assert entry.user == store_user2
        assert entry.item == test_item

    def test_stripe_payment_intent_stored(self, user_inventory_entry):
        """stripe_payment_intent_id is stored for audit."""
        assert user_inventory_entry.stripe_payment_intent_id == "pi_test_123"


# ── Wishlist model ────────────────────────────────────────────────────


class TestWishlistModel:
    """Tests for the Wishlist model."""

    def test_create_wishlist_entry(self, store_user, test_item):
        """Wishlist entry can be created."""
        entry = Wishlist.objects.create(user=store_user, item=test_item)
        assert entry.user == store_user
        assert entry.item == test_item

    def test_unique_user_item_wishlist(self, store_user, test_item):
        """A user cannot wishlist the same item twice."""
        Wishlist.objects.create(user=store_user, item=test_item)
        with pytest.raises(IntegrityError):
            Wishlist.objects.create(user=store_user, item=test_item)


# ── Gift model ────────────────────────────────────────────────────────


class TestGiftModel:
    """Tests for the Gift model."""

    def test_create_gift(self, store_user, store_user2, test_item):
        """Gift can be created."""
        gift = Gift.objects.create(
            sender=store_user,
            recipient=store_user2,
            item=test_item,
            message="Enjoy!",
        )
        assert gift.sender == store_user
        assert gift.recipient == store_user2
        assert gift.is_claimed is False

    def test_str_representation(self, store_user, store_user2, test_item):
        """__str__ includes item, sender, recipient, and status."""
        gift = Gift.objects.create(
            sender=store_user,
            recipient=store_user2,
            item=test_item,
        )
        s = str(gift)
        assert "Gold Frame" in s
        assert "pending" in s


# ══════════════════════════════════════════════════════════════════════
#  API ENDPOINT TESTS — Store
# ══════════════════════════════════════════════════════════════════════

import pytest


@pytest.mark.django_db
class TestStoreAPI:
    """Tests for Store API endpoints."""

    def test_list_items(self, store_user):
        from rest_framework.test import APIClient

        client = APIClient()
        client.force_authenticate(user=store_user)
        resp = client.get(
            "/api/store/items/",
            HTTP_ORIGIN="https://stepora.app",
        )
        assert resp.status_code in (200, 403)

    def test_list_categories(self, store_user):
        from rest_framework.test import APIClient

        client = APIClient()
        client.force_authenticate(user=store_user)
        resp = client.get(
            "/api/store/categories/",
            HTTP_ORIGIN="https://stepora.app",
        )
        assert resp.status_code in (200, 403)
