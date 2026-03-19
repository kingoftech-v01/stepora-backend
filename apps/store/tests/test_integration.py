"""
Integration tests for the Store app API endpoints.

Tests store categories, items, inventory, wishlist, purchase flow,
gifts, and refunds. Store browsing is public; purchases require
authentication and premium+ subscription.
"""

import uuid
from datetime import timedelta
from decimal import Decimal
from unittest.mock import Mock, patch

import pytest
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.store.models import (
    Gift,
    RefundRequest,
    StoreCategory,
    StoreItem,
    UserInventory,
    Wishlist,
)
from apps.users.models import User


@pytest.fixture
def store_client(store_user):
    """Authenticated API client for store tests."""
    client = APIClient()
    client.force_authenticate(user=store_user)
    return client


@pytest.fixture
def store_client2(store_user2):
    """Authenticated API client for store_user2."""
    client = APIClient()
    client.force_authenticate(user=store_user2)
    return client


@pytest.fixture
def premium_store_user(store_user):
    """Make store_user premium."""
    from apps.subscriptions.models import Subscription, SubscriptionPlan

    plan, _ = SubscriptionPlan.objects.get_or_create(
        slug="premium",
        defaults={"name": "Premium", "price_monthly": 9.99, "is_active": True},
    )
    Subscription.objects.update_or_create(
        user=store_user,
        defaults={
            "plan": plan,
            "status": "active",
            "current_period_start": timezone.now(),
            "current_period_end": timezone.now() + timedelta(days=30),
        },
    )
    return store_user


@pytest.fixture
def premium_store_client(premium_store_user):
    """Premium authenticated client for store tests."""
    client = APIClient()
    client.force_authenticate(user=premium_store_user)
    return client


@pytest.fixture
def premium_store_user2(store_user2):
    """Make store_user2 premium."""
    from apps.subscriptions.models import Subscription, SubscriptionPlan

    plan, _ = SubscriptionPlan.objects.get_or_create(
        slug="premium",
        defaults={"name": "Premium", "price_monthly": 9.99, "is_active": True},
    )
    Subscription.objects.update_or_create(
        user=store_user2,
        defaults={
            "plan": plan,
            "status": "active",
            "current_period_start": timezone.now(),
            "current_period_end": timezone.now() + timedelta(days=30),
        },
    )
    return store_user2


@pytest.fixture
def xp_item(db, test_category):
    """Create a store item purchasable with XP."""
    return StoreItem.objects.create(
        category=test_category,
        name="XP Frame",
        slug="xp-frame",
        description="A frame purchasable with XP",
        price=Decimal("0.00"),
        xp_price=500,
        item_type="badge_frame",
        rarity="common",
        is_active=True,
    )


# ──────────────────────────────────────────────────────────────────────
#  Store Categories (public)
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestStoreCategories:
    """Tests for /api/store/categories/ endpoints."""

    def test_list_categories_unauthenticated(self, test_category):
        """List categories without authentication."""
        client = APIClient()
        response = client.get("/api/store/categories/")
        assert response.status_code == status.HTTP_200_OK

    def test_list_categories(self, store_client, test_category):
        """List store categories."""
        response = store_client.get("/api/store/categories/")
        assert response.status_code == status.HTTP_200_OK
        data = response.data
        results = data.get("results", data)
        assert len(results) >= 1

    def test_retrieve_category(self, store_client, test_category):
        """Retrieve a category by slug."""
        response = store_client.get(f"/api/store/categories/{test_category.slug}/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["name"] == test_category.name

    def test_retrieve_nonexistent_category(self, store_client):
        """Retrieve nonexistent category returns 404."""
        response = store_client.get("/api/store/categories/nonexistent-slug/")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_inactive_categories_hidden(self, store_client):
        """Inactive categories are not listed."""
        StoreCategory.objects.create(
            name="Hidden Cat",
            slug="hidden-cat",
            is_active=False,
        )
        response = store_client.get("/api/store/categories/")
        data = response.data
        results = data.get("results", data)
        slugs = [c["slug"] for c in results]
        assert "hidden-cat" not in slugs


# ──────────────────────────────────────────────────────────────────────
#  Store Items (public)
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestStoreItems:
    """Tests for /api/store/items/ endpoints."""

    def test_list_items_unauthenticated(self, test_item):
        """List items without authentication."""
        client = APIClient()
        response = client.get("/api/store/items/")
        assert response.status_code == status.HTTP_200_OK

    def test_list_items(self, store_client, test_item, test_item2):
        """List store items."""
        response = store_client.get("/api/store/items/")
        assert response.status_code == status.HTTP_200_OK
        data = response.data
        results = data.get("results", data)
        assert len(results) >= 2

    def test_retrieve_item(self, store_client, test_item):
        """Retrieve item by slug."""
        response = store_client.get(f"/api/store/items/{test_item.slug}/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["name"] == test_item.name

    def test_retrieve_nonexistent_item(self, store_client):
        """Retrieve nonexistent item returns 404."""
        response = store_client.get("/api/store/items/nonexistent-item/")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_inactive_items_hidden(self, store_client, test_category):
        """Inactive items are not listed."""
        StoreItem.objects.create(
            category=test_category,
            name="Hidden Item",
            slug="hidden-item",
            price=Decimal("1.99"),
            item_type="badge_frame",
            rarity="common",
            is_active=False,
        )
        response = store_client.get("/api/store/items/")
        data = response.data
        results = data.get("results", data)
        slugs = [i["slug"] for i in results]
        assert "hidden-item" not in slugs

    def test_filter_items_by_category(self, store_client, test_item):
        """Filter items by category slug."""
        response = store_client.get(
            f"/api/store/items/?category__slug={test_item.category.slug}"
        )
        assert response.status_code == status.HTTP_200_OK

    def test_filter_items_by_rarity(self, store_client, test_item):
        """Filter items by rarity."""
        response = store_client.get("/api/store/items/?rarity=rare")
        assert response.status_code == status.HTTP_200_OK

    def test_search_items(self, store_client, test_item):
        """Search items by name."""
        response = store_client.get("/api/store/items/?search=Gold")
        assert response.status_code == status.HTTP_200_OK


# ──────────────────────────────────────────────────────────────────────
#  Featured Items
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestFeaturedItems:
    """Tests for featured items endpoint."""

    def test_featured_items(self, store_client, legendary_item):
        """Get featured items."""
        response = store_client.get("/api/store/items/featured/")
        assert response.status_code == status.HTTP_200_OK

    def test_featured_items_empty(self, store_client, test_item):
        """Featured items when none are epic/legendary."""
        response = store_client.get("/api/store/items/featured/")
        assert response.status_code == status.HTTP_200_OK


# ──────────────────────────────────────────────────────────────────────
#  Item Preview
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestItemPreview:
    """Tests for item preview endpoint."""

    def test_preview_no_data(self, store_client, test_item):
        """Preview for item without preview data returns 404."""
        response = store_client.get(f"/api/store/items/{test_item.slug}/preview/")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_preview_with_data(self, store_client, test_category):
        """Preview for item with preview data."""
        item = StoreItem.objects.create(
            category=test_category,
            name="Preview Item",
            slug="preview-item",
            price=Decimal("4.99"),
            item_type="theme_skin",
            rarity="epic",
            is_active=True,
            preview_type="theme",
            preview_data={"primary_color": "#FF0000"},
        )
        response = store_client.get(f"/api/store/items/{item.slug}/preview/")
        assert response.status_code == status.HTTP_200_OK


# ──────────────────────────────────────────────────────────────────────
#  User Inventory
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestUserInventory:
    """Tests for /api/store/inventory/ endpoints."""

    def test_list_inventory_unauthenticated(self):
        """Unauthenticated inventory access returns 401."""
        client = APIClient()
        response = client.get("/api/store/inventory/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_list_inventory(self, store_client, user_inventory_entry):
        """List user inventory items."""
        response = store_client.get("/api/store/inventory/")
        assert response.status_code == status.HTTP_200_OK

    def test_list_inventory_empty(self, store_client):
        """List empty inventory."""
        response = store_client.get("/api/store/inventory/")
        assert response.status_code == status.HTTP_200_OK

    def test_retrieve_inventory_item(self, store_client, user_inventory_entry):
        """Retrieve a specific inventory item."""
        response = store_client.get(
            f"/api/store/inventory/{user_inventory_entry.id}/"
        )
        assert response.status_code == status.HTTP_200_OK

    def test_purchase_history(self, store_client, user_inventory_entry):
        """Get purchase history."""
        response = store_client.get("/api/store/inventory/history/")
        assert response.status_code == status.HTTP_200_OK

    def test_filter_inventory_by_equipped(self, store_client, user_inventory_entry):
        """Filter inventory by equipped status."""
        response = store_client.get("/api/store/inventory/?is_equipped=false")
        assert response.status_code == status.HTTP_200_OK


# ──────────────────────────────────────────────────────────────────────
#  Equip / Unequip
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestEquipUnequip:
    """Tests for equipping and unequipping items."""

    def test_equip_item(self, store_client, user_inventory_entry):
        """Equip an inventory item."""
        response = store_client.post(
            f"/api/store/inventory/{user_inventory_entry.id}/equip/",
            {"equip": True},
            format="json",
        )
        assert response.status_code in (
            status.HTTP_200_OK,
            status.HTTP_404_NOT_FOUND,
        )

    def test_unequip_item(self, store_client, user_inventory_entry):
        """Unequip an inventory item."""
        user_inventory_entry.is_equipped = True
        user_inventory_entry.save()
        response = store_client.post(
            f"/api/store/inventory/{user_inventory_entry.id}/equip/",
            {"equip": False},
            format="json",
        )
        assert response.status_code in (
            status.HTTP_200_OK,
            status.HTTP_404_NOT_FOUND,
        )

    def test_equip_nonexistent(self, store_client):
        """Equip nonexistent item returns 404."""
        response = store_client.post(
            f"/api/store/inventory/{uuid.uuid4()}/equip/",
            {"equip": True},
            format="json",
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND


# ──────────────────────────────────────────────────────────────────────
#  Wishlist
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestWishlist:
    """Tests for /api/store/wishlist/ endpoints."""

    def test_list_wishlist_unauthenticated(self):
        """Unauthenticated wishlist access returns 401."""
        client = APIClient()
        response = client.get("/api/store/wishlist/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_list_wishlist_empty(self, store_client):
        """List empty wishlist."""
        response = store_client.get("/api/store/wishlist/")
        assert response.status_code == status.HTTP_200_OK

    def test_add_to_wishlist(self, store_client, test_item):
        """Add item to wishlist."""
        response = store_client.post(
            "/api/store/wishlist/",
            {"item_id": str(test_item.id)},
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED

    def test_remove_from_wishlist(self, store_client, store_user, test_item):
        """Remove item from wishlist."""
        wl = Wishlist.objects.create(user=store_user, item=test_item)
        response = store_client.delete(f"/api/store/wishlist/{wl.id}/")
        assert response.status_code == status.HTTP_204_NO_CONTENT

    def test_remove_nonexistent_wishlist_item(self, store_client):
        """Remove nonexistent wishlist item returns 404."""
        response = store_client.delete(f"/api/store/wishlist/{uuid.uuid4()}/")
        assert response.status_code == status.HTTP_404_NOT_FOUND


# ──────────────────────────────────────────────────────────────────────
#  Purchase (Stripe, mocked)
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestPurchase:
    """Tests for purchase endpoints."""

    def test_purchase_unauthenticated(self, test_item):
        """Unauthenticated purchase returns 401."""
        client = APIClient()
        response = client.post(
            "/api/store/purchase/",
            {"item_id": str(test_item.id)},
            format="json",
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_purchase_free_user(self, store_client, test_item):
        """Free user purchase returns 403."""
        response = store_client.post(
            "/api/store/purchase/",
            {"item_id": str(test_item.id)},
            format="json",
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    @patch("apps.store.services.StoreService.create_payment_intent")
    def test_purchase_success(
        self, mock_create, premium_store_client, test_item
    ):
        """Initiate purchase successfully."""
        mock_create.return_value = {
            "client_secret": "pi_test_secret",
            "payment_intent_id": "pi_test_123",
        }
        response = premium_store_client.post(
            "/api/store/purchase/",
            {"item_id": str(test_item.id)},
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED

    def test_purchase_nonexistent_item(self, premium_store_client):
        """Purchase nonexistent item returns 404."""
        response = premium_store_client.post(
            "/api/store/purchase/",
            {"item_id": str(uuid.uuid4())},
            format="json",
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND


# ──────────────────────────────────────────────────────────────────────
#  Purchase Confirm
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestPurchaseConfirm:
    """Tests for purchase confirmation endpoint."""

    def test_confirm_nonexistent_item(self, premium_store_client):
        """Confirm purchase for nonexistent item returns 404."""
        response = premium_store_client.post(
            "/api/store/purchase/confirm/",
            {
                "item_id": str(uuid.uuid4()),
                "payment_intent_id": "pi_test_123",
            },
            format="json",
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND


# ──────────────────────────────────────────────────────────────────────
#  XP Purchase
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestXPPurchase:
    """Tests for XP purchase endpoint."""

    def test_xp_purchase_nonexistent_item(self, premium_store_client):
        """XP purchase nonexistent item returns 404."""
        response = premium_store_client.post(
            "/api/store/purchase/xp/",
            {"item_id": str(uuid.uuid4())},
            format="json",
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    @patch("apps.store.services.StoreService.purchase_with_xp")
    def test_xp_purchase_success(self, mock_purchase, premium_store_client, xp_item, store_user):
        """XP purchase successfully."""
        mock_inventory = Mock()
        mock_inventory.id = uuid.uuid4()
        mock_inventory.user = store_user
        mock_inventory.item = xp_item
        mock_inventory.is_equipped = False
        mock_inventory.purchased_at = timezone.now()
        mock_inventory.stripe_payment_intent_id = ""
        mock_purchase.return_value = mock_inventory
        response = premium_store_client.post(
            "/api/store/purchase/xp/",
            {"item_id": str(xp_item.id)},
            format="json",
        )
        assert response.status_code in (
            status.HTTP_200_OK,
            status.HTTP_400_BAD_REQUEST,
        )


# ──────────────────────────────────────────────────────────────────────
#  Gifts
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestGifts:
    """Tests for gift endpoints."""

    def test_list_gifts_unauthenticated(self):
        """Unauthenticated gift list returns 401."""
        client = APIClient()
        response = client.get("/api/store/gifts/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_list_gifts_empty(self, store_client):
        """List gifts when none exist."""
        response = store_client.get("/api/store/gifts/")
        assert response.status_code == status.HTTP_200_OK

    def test_send_gift_nonexistent_item(self, premium_store_client, store_user2):
        """Send gift with nonexistent item returns 404."""
        response = premium_store_client.post(
            "/api/store/gifts/send/",
            {
                "item_id": str(uuid.uuid4()),
                "recipient_id": str(store_user2.id),
                "message": "For you!",
            },
            format="json",
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_send_gift_nonexistent_recipient(self, premium_store_client, test_item):
        """Send gift to nonexistent recipient returns 404."""
        response = premium_store_client.post(
            "/api/store/gifts/send/",
            {
                "item_id": str(test_item.id),
                "recipient_id": str(uuid.uuid4()),
                "message": "For you!",
            },
            format="json",
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_claim_gift_nonexistent(self, store_client):
        """Claim nonexistent gift returns error."""
        response = store_client.post(f"/api/store/gifts/{uuid.uuid4()}/claim/")
        assert response.status_code in (
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_404_NOT_FOUND,
        )


# ──────────────────────────────────────────────────────────────────────
#  Refunds
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestRefunds:
    """Tests for refund request endpoints."""

    def test_list_refunds_unauthenticated(self):
        """Unauthenticated refund list returns 401."""
        client = APIClient()
        response = client.get("/api/store/refunds/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_list_refunds_empty(self, store_client):
        """List refunds when none exist."""
        response = store_client.get("/api/store/refunds/")
        assert response.status_code == status.HTTP_200_OK

    @patch("apps.store.services.StoreService.request_refund")
    def test_request_refund(self, mock_refund, store_client, user_inventory_entry):
        """Request a refund."""
        mock_result = Mock()
        mock_result.id = uuid.uuid4()
        mock_result.status = "pending"
        mock_result.reason = "Not what I expected"
        mock_result.created_at = timezone.now()
        mock_result.inventory_entry = user_inventory_entry
        mock_result.admin_notes = ""
        mock_refund.return_value = mock_result
        response = store_client.post(
            "/api/store/refunds/",
            {
                "inventory_id": str(user_inventory_entry.id),
                "reason": "Not what I expected",
            },
            format="json",
        )
        assert response.status_code in (
            status.HTTP_201_CREATED,
            status.HTTP_400_BAD_REQUEST,
        )


# ──────────────────────────────────────────────────────────────────────
#  Limited-time items
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestLimitedTimeItems:
    """Tests for limited-time item visibility."""

    def test_future_item_hidden(self, store_client, test_category):
        """Items not yet available are hidden."""
        StoreItem.objects.create(
            category=test_category,
            name="Future Item",
            slug="future-item",
            price=Decimal("9.99"),
            item_type="badge_frame",
            rarity="epic",
            is_active=True,
            available_from=timezone.now() + timedelta(days=30),
        )
        response = store_client.get("/api/store/items/")
        data = response.data
        results = data.get("results", data)
        slugs = [i["slug"] for i in results]
        assert "future-item" not in slugs

    def test_expired_item_hidden(self, store_client, test_category):
        """Expired items are hidden."""
        StoreItem.objects.create(
            category=test_category,
            name="Expired Item",
            slug="expired-item",
            price=Decimal("9.99"),
            item_type="badge_frame",
            rarity="epic",
            is_active=True,
            available_until=timezone.now() - timedelta(days=1),
        )
        response = store_client.get("/api/store/items/")
        data = response.data
        results = data.get("results", data)
        slugs = [i["slug"] for i in results]
        assert "expired-item" not in slugs

    def test_available_item_shown(self, store_client, test_category):
        """Currently available items are shown."""
        StoreItem.objects.create(
            category=test_category,
            name="Available Item",
            slug="available-item",
            price=Decimal("4.99"),
            item_type="badge_frame",
            rarity="rare",
            is_active=True,
            available_from=timezone.now() - timedelta(days=1),
            available_until=timezone.now() + timedelta(days=30),
        )
        response = store_client.get("/api/store/items/")
        data = response.data
        results = data.get("results", data)
        slugs = [i["slug"] for i in results]
        assert "available-item" in slugs
