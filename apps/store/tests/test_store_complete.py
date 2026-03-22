"""
Comprehensive tests for the Store app.

Target: 95%+ coverage of models, services, serializers, views.

Covers:
- StoreCategory: list, detail, items count, inactive filtering
- StoreItem: list, detail, featured, preview, filtering, availability windows
- Purchase: Stripe payment intent, XP purchase, confirm, already owned
- UserInventory: list, equip/unequip, history, filter
- Wishlist: add, remove, duplicate prevention
- Gift: send, claim, list, self-gift prevention
- RefundRequest: request, admin approve/reject, duplicate prevention
- IDOR: can't access other users' inventory/gifts
- Stripe mock for all payment flows
- Permission checks (auth, premium, admin)
"""

import uuid
from datetime import timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch

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
from apps.store.services import (
    InsufficientXPError,
    InventoryNotFoundError,
    ItemAlreadyOwnedError,
    ItemNotActiveError,
    ItemNotFoundError,
    PaymentVerificationError,
    StoreService,
    StoreServiceError,
)
from apps.subscriptions.models import Subscription, SubscriptionPlan
from apps.users.models import User


# ══════════════════════════════════════════════════════════════════
#  Helpers & Fixtures
# ══════════════════════════════════════════════════════════════════


def _make_premium(user):
    """Give *user* an active premium subscription so CanUseStore passes."""
    plan, _ = SubscriptionPlan.objects.get_or_create(
        slug="premium",
        defaults={
            "name": "Premium",
            "price_monthly": Decimal("9.99"),
            "is_active": True,
            "has_store": True,
        },
    )
    if not plan.has_store:
        plan.has_store = True
        plan.save(update_fields=["has_store"])
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
def user_a(db):
    return User.objects.create_user(
        email="usera@test.com", password="pass1234", display_name="User A"
    )


@pytest.fixture
def user_b(db):
    return User.objects.create_user(
        email="userb@test.com", password="pass1234", display_name="User B"
    )


@pytest.fixture
def admin_user(db):
    return User.objects.create_superuser(
        email="admin@test.com", password="admin1234"
    )


@pytest.fixture
def premium_a(user_a):
    return _make_premium(user_a)


@pytest.fixture
def premium_b(user_b):
    return _make_premium(user_b)


@pytest.fixture
def client_a(user_a):
    c = APIClient()
    c.force_authenticate(user=user_a)
    return c


@pytest.fixture
def client_b(user_b):
    c = APIClient()
    c.force_authenticate(user=user_b)
    return c


@pytest.fixture
def premium_client_a(premium_a):
    c = APIClient()
    c.force_authenticate(user=premium_a)
    return c


@pytest.fixture
def premium_client_b(premium_b):
    c = APIClient()
    c.force_authenticate(user=premium_b)
    return c


@pytest.fixture
def admin_client(admin_user):
    c = APIClient()
    c.force_authenticate(user=admin_user)
    return c


@pytest.fixture
def anon():
    return APIClient()


@pytest.fixture
def cat_badges(db):
    return StoreCategory.objects.create(
        name="Badge Frames", slug="badge-frames", display_order=1, is_active=True
    )


@pytest.fixture
def cat_themes(db):
    return StoreCategory.objects.create(
        name="Theme Skins", slug="theme-skins", display_order=2, is_active=True
    )


@pytest.fixture
def cat_inactive(db):
    return StoreCategory.objects.create(
        name="Secret Cat", slug="secret-cat", display_order=99, is_active=False
    )


@pytest.fixture
def item_gold(cat_badges):
    return StoreItem.objects.create(
        category=cat_badges,
        name="Gold Frame",
        slug="gold-frame",
        price=Decimal("4.99"),
        item_type="badge_frame",
        rarity="rare",
        is_active=True,
    )


@pytest.fixture
def item_silver(cat_badges):
    return StoreItem.objects.create(
        category=cat_badges,
        name="Silver Frame",
        slug="silver-frame",
        price=Decimal("2.99"),
        item_type="badge_frame",
        rarity="common",
        is_active=True,
    )


@pytest.fixture
def item_epic(cat_badges):
    return StoreItem.objects.create(
        category=cat_badges,
        name="Epic Frame",
        slug="epic-frame",
        price=Decimal("6.99"),
        item_type="badge_frame",
        rarity="epic",
        is_active=True,
    )


@pytest.fixture
def item_legendary(cat_themes):
    return StoreItem.objects.create(
        category=cat_themes,
        name="Cosmic Theme",
        slug="cosmic-theme",
        price=Decimal("9.99"),
        item_type="theme_skin",
        rarity="legendary",
        is_active=True,
    )


@pytest.fixture
def item_inactive(cat_badges):
    return StoreItem.objects.create(
        category=cat_badges,
        name="Disabled Item",
        slug="disabled-item",
        price=Decimal("1.99"),
        item_type="badge_frame",
        rarity="common",
        is_active=False,
    )


@pytest.fixture
def item_xp(cat_badges):
    return StoreItem.objects.create(
        category=cat_badges,
        name="XP Badge",
        slug="xp-badge",
        price=Decimal("0.00"),
        xp_price=500,
        item_type="badge_frame",
        rarity="common",
        is_active=True,
    )


@pytest.fixture
def item_preview(cat_themes):
    return StoreItem.objects.create(
        category=cat_themes,
        name="Preview Theme",
        slug="preview-theme",
        price=Decimal("4.99"),
        item_type="theme_skin",
        rarity="epic",
        is_active=True,
        preview_type="theme",
        preview_data={"accent": "#8B5CF6", "bg": "#1a1a2e"},
    )


@pytest.fixture
def item_future(cat_badges):
    return StoreItem.objects.create(
        category=cat_badges,
        name="Future Item",
        slug="future-item",
        price=Decimal("1.00"),
        item_type="badge_frame",
        is_active=True,
        available_from=timezone.now() + timedelta(days=30),
    )


@pytest.fixture
def item_expired(cat_badges):
    return StoreItem.objects.create(
        category=cat_badges,
        name="Expired Item",
        slug="expired-item",
        price=Decimal("1.00"),
        item_type="badge_frame",
        is_active=True,
        available_until=timezone.now() - timedelta(days=1),
    )


@pytest.fixture
def inv_a_gold(user_a, item_gold):
    return UserInventory.objects.create(
        user=user_a,
        item=item_gold,
        stripe_payment_intent_id="pi_test_001",
        is_equipped=False,
    )


# ══════════════════════════════════════════════════════════════════
#  StoreCategory: list, detail, items count
# ══════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestStoreCategory:

    def test_list_categories_public(self, anon, cat_badges, cat_themes):
        """Anonymous users can list active categories."""
        r = anon.get("/api/store/categories/")
        assert r.status_code == status.HTTP_200_OK
        results = r.data.get("results", r.data)
        slugs = [c["slug"] for c in results]
        assert "badge-frames" in slugs
        assert "theme-skins" in slugs

    def test_list_excludes_inactive(self, anon, cat_badges, cat_inactive):
        """Inactive categories are hidden from listing."""
        r = anon.get("/api/store/categories/")
        results = r.data.get("results", r.data)
        slugs = [c["slug"] for c in results]
        assert "secret-cat" not in slugs

    def test_detail_by_slug(self, anon, cat_badges, item_gold):
        """Retrieve category detail with nested items."""
        r = anon.get(f"/api/store/categories/{cat_badges.slug}/")
        assert r.status_code == status.HTTP_200_OK
        assert r.data["name"] == "Badge Frames"
        assert "items" in r.data
        assert len(r.data["items"]) >= 1

    def test_detail_excludes_inactive_items(self, anon, cat_badges, item_gold, item_inactive):
        """Detail view only shows active items."""
        r = anon.get(f"/api/store/categories/{cat_badges.slug}/")
        names = [i["name"] for i in r.data["items"]]
        assert "Gold Frame" in names
        assert "Disabled Item" not in names

    def test_items_count(self, anon, cat_badges, item_gold, item_silver, item_inactive):
        """items_count reflects only active items."""
        r = anon.get("/api/store/categories/")
        results = r.data.get("results", r.data)
        badge_cat = next(c for c in results if c["slug"] == "badge-frames")
        assert badge_cat["items_count"] == 2  # gold + silver, not inactive

    def test_detail_nonexistent(self, anon):
        """Nonexistent slug returns 404."""
        r = anon.get("/api/store/categories/nope/")
        assert r.status_code == status.HTTP_404_NOT_FOUND

    def test_ordering(self, anon, cat_badges, cat_themes):
        """Categories are ordered by display_order."""
        r = anon.get("/api/store/categories/")
        results = r.data.get("results", r.data)
        orders = [c["display_order"] for c in results]
        assert orders == sorted(orders)


# ══════════════════════════════════════════════════════════════════
#  StoreItem: list, detail, featured, preview, filtering
# ══════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestStoreItem:

    def test_list_public(self, anon, item_gold):
        """Items list is publicly accessible."""
        r = anon.get("/api/store/items/")
        assert r.status_code == status.HTTP_200_OK

    def test_list_excludes_inactive(self, anon, item_gold, item_inactive):
        """Inactive items are hidden."""
        r = anon.get("/api/store/items/")
        slugs = [i["slug"] for i in r.data.get("results", r.data)]
        assert "gold-frame" in slugs
        assert "disabled-item" not in slugs

    def test_list_excludes_future(self, anon, item_gold, item_future):
        """Items not yet available are hidden."""
        r = anon.get("/api/store/items/")
        slugs = [i["slug"] for i in r.data.get("results", r.data)]
        assert "future-item" not in slugs

    def test_list_excludes_expired(self, anon, item_gold, item_expired):
        """Expired items are hidden."""
        r = anon.get("/api/store/items/")
        slugs = [i["slug"] for i in r.data.get("results", r.data)]
        assert "expired-item" not in slugs

    def test_detail_by_slug(self, anon, item_gold):
        """Detail view returns extra fields."""
        r = anon.get(f"/api/store/items/{item_gold.slug}/")
        assert r.status_code == status.HTTP_200_OK
        assert r.data["name"] == "Gold Frame"
        assert "owners_count" in r.data
        assert "is_owned" in r.data

    def test_detail_is_owned_authenticated(self, client_a, item_gold, inv_a_gold):
        """is_owned=True for items the user owns."""
        r = client_a.get(f"/api/store/items/{item_gold.slug}/")
        assert r.data["is_owned"] is True

    def test_detail_is_owned_false(self, client_b, item_gold):
        """is_owned=False for items the user doesn't own."""
        r = client_b.get(f"/api/store/items/{item_gold.slug}/")
        assert r.data["is_owned"] is False

    def test_detail_is_owned_anonymous(self, anon, item_gold):
        """is_owned=False for anonymous users."""
        r = anon.get(f"/api/store/items/{item_gold.slug}/")
        assert r.data["is_owned"] is False

    def test_owners_count(self, anon, item_gold, inv_a_gold):
        """owners_count reflects actual ownership."""
        r = anon.get(f"/api/store/items/{item_gold.slug}/")
        assert r.data["owners_count"] == 1

    def test_filter_by_rarity(self, anon, item_gold, item_silver):
        """Filter by rarity works."""
        r = anon.get("/api/store/items/?rarity=rare")
        assert r.status_code == status.HTTP_200_OK
        results = r.data.get("results", r.data)
        assert all(i["rarity"] == "rare" for i in results)

    def test_filter_by_item_type(self, anon, item_gold, item_legendary):
        """Filter by item_type works."""
        r = anon.get("/api/store/items/?item_type=badge_frame")
        results = r.data.get("results", r.data)
        assert all(i["item_type"] == "badge_frame" for i in results)

    def test_filter_by_category_slug(self, anon, item_gold, item_legendary, cat_badges):
        """Filter by category slug."""
        r = anon.get(f"/api/store/items/?category__slug={cat_badges.slug}")
        results = r.data.get("results", r.data)
        assert all(i["category_name"] == "Badge Frames" for i in results)

    def test_search(self, anon, item_gold, item_silver):
        """Search by name."""
        r = anon.get("/api/store/items/?search=Gold")
        results = r.data.get("results", r.data)
        assert any(i["name"] == "Gold Frame" for i in results)

    def test_detail_nonexistent(self, anon):
        """Nonexistent slug returns 404."""
        r = anon.get("/api/store/items/nope/")
        assert r.status_code == status.HTTP_404_NOT_FOUND


# ── Featured ──────────────────────────────────────────────────────


@pytest.mark.django_db
class TestFeatured:

    def test_featured_returns_epic_legendary(self, anon, item_epic, item_legendary):
        """Featured endpoint returns epic and legendary items."""
        r = anon.get("/api/store/items/featured/")
        assert r.status_code == status.HTTP_200_OK
        rarities = {i["rarity"] for i in r.data}
        assert rarities.issubset({"epic", "legendary"})

    def test_featured_excludes_common_rare(self, anon, item_gold, item_silver):
        """Common/rare items are excluded from featured."""
        r = anon.get("/api/store/items/featured/")
        assert r.status_code == status.HTTP_200_OK
        assert len(r.data) == 0

    def test_featured_max_10(self, anon, cat_badges):
        """Featured returns at most 10 items."""
        for i in range(15):
            StoreItem.objects.create(
                category=cat_badges,
                name=f"Legendary {i}",
                slug=f"legendary-{i}",
                price=Decimal("9.99"),
                item_type="badge_frame",
                rarity="legendary",
                is_active=True,
            )
        r = anon.get("/api/store/items/featured/")
        assert len(r.data) <= 10


# ── Preview ───────────────────────────────────────────────────────


@pytest.mark.django_db
class TestPreview:

    def test_preview_with_data(self, anon, item_preview):
        """Preview returns type and data."""
        r = anon.get(f"/api/store/items/{item_preview.slug}/preview/")
        assert r.status_code == status.HTTP_200_OK
        assert r.data["preview_type"] == "theme"
        assert r.data["preview_data"]["accent"] == "#8B5CF6"

    def test_preview_no_data(self, anon, item_gold):
        """Preview returns 404 when item has no preview config."""
        r = anon.get(f"/api/store/items/{item_gold.slug}/preview/")
        assert r.status_code == status.HTTP_404_NOT_FOUND

    def test_preview_is_owned(self, client_a, item_preview, user_a):
        """Preview serializer includes is_owned field."""
        UserInventory.objects.create(user=user_a, item=item_preview)
        r = client_a.get(f"/api/store/items/{item_preview.slug}/preview/")
        assert r.data["is_owned"] is True


# ══════════════════════════════════════════════════════════════════
#  Purchase: Stripe payment, XP purchase, confirm, already owned
# ══════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestPurchaseStripe:

    def test_requires_auth(self, anon, item_gold):
        r = anon.post("/api/store/purchase/", {"item_id": str(item_gold.id)}, format="json")
        assert r.status_code == status.HTTP_401_UNAUTHORIZED

    def test_free_user_forbidden(self, client_a, item_gold):
        r = client_a.post("/api/store/purchase/", {"item_id": str(item_gold.id)}, format="json")
        assert r.status_code == status.HTTP_403_FORBIDDEN

    @patch("apps.store.views.StoreService.create_payment_intent")
    def test_success(self, mock_create, premium_client_a, item_gold):
        mock_create.return_value = {
            "client_secret": "pi_secret",
            "payment_intent_id": "pi_123",
            "amount": 499,
        }
        r = premium_client_a.post(
            "/api/store/purchase/", {"item_id": str(item_gold.id)}, format="json"
        )
        assert r.status_code == status.HTTP_201_CREATED
        assert r.data["client_secret"] == "pi_secret"

    def test_nonexistent_item(self, premium_client_a):
        r = premium_client_a.post(
            "/api/store/purchase/", {"item_id": str(uuid.uuid4())}, format="json"
        )
        assert r.status_code == status.HTTP_400_BAD_REQUEST

    def test_inactive_item_rejected(self, premium_client_a, item_inactive):
        r = premium_client_a.post(
            "/api/store/purchase/", {"item_id": str(item_inactive.id)}, format="json"
        )
        assert r.status_code == status.HTTP_400_BAD_REQUEST

    def test_already_owned_by_serializer(self, premium_client_a, item_gold, inv_a_gold):
        """Serializer catches ownership before reaching the service."""
        r = premium_client_a.post(
            "/api/store/purchase/", {"item_id": str(item_gold.id)}, format="json"
        )
        assert r.status_code == status.HTTP_400_BAD_REQUEST

    @patch("apps.store.views.StoreService.create_payment_intent")
    def test_stripe_error_502(self, mock_create, premium_client_a, item_gold):
        mock_create.side_effect = PaymentVerificationError("stripe down")
        r = premium_client_a.post(
            "/api/store/purchase/", {"item_id": str(item_gold.id)}, format="json"
        )
        assert r.status_code == status.HTTP_502_BAD_GATEWAY


@pytest.mark.django_db
class TestPurchaseConfirm:

    def test_requires_auth(self, anon, item_gold):
        r = anon.post(
            "/api/store/purchase/confirm/",
            {"item_id": str(item_gold.id), "payment_intent_id": "pi_x"},
            format="json",
        )
        assert r.status_code == status.HTTP_401_UNAUTHORIZED

    @patch("apps.store.views.StoreService.confirm_purchase")
    def test_success(self, mock_confirm, premium_client_a, item_gold, user_a):
        inv = UserInventory.objects.create(
            user=user_a, item=item_gold, stripe_payment_intent_id="pi_ok"
        )
        mock_confirm.return_value = inv
        r = premium_client_a.post(
            "/api/store/purchase/confirm/",
            {"item_id": str(item_gold.id), "payment_intent_id": "pi_ok"},
            format="json",
        )
        assert r.status_code == status.HTTP_200_OK

    def test_invalid_payment_intent_format(self, premium_client_a, item_gold):
        r = premium_client_a.post(
            "/api/store/purchase/confirm/",
            {"item_id": str(item_gold.id), "payment_intent_id": "bad"},
            format="json",
        )
        assert r.status_code == status.HTTP_400_BAD_REQUEST

    @patch("apps.store.views.StoreService.confirm_purchase")
    def test_already_owned(self, mock_confirm, premium_client_a, item_gold, inv_a_gold):
        mock_confirm.side_effect = ItemAlreadyOwnedError("owned")
        r = premium_client_a.post(
            "/api/store/purchase/confirm/",
            {"item_id": str(item_gold.id), "payment_intent_id": "pi_dup"},
            format="json",
        )
        assert r.status_code == status.HTTP_409_CONFLICT

    @patch("apps.store.views.StoreService.confirm_purchase")
    def test_payment_not_succeeded(self, mock_confirm, premium_client_a, item_gold):
        mock_confirm.side_effect = PaymentVerificationError("pending")
        r = premium_client_a.post(
            "/api/store/purchase/confirm/",
            {"item_id": str(item_gold.id), "payment_intent_id": "pi_fail"},
            format="json",
        )
        assert r.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
class TestXPPurchase:

    def test_requires_auth(self, anon, item_xp):
        r = anon.post("/api/store/purchase/xp/", {"item_id": str(item_xp.id)}, format="json")
        assert r.status_code == status.HTTP_401_UNAUTHORIZED

    def test_free_user_forbidden(self, client_a, item_xp):
        r = client_a.post("/api/store/purchase/xp/", {"item_id": str(item_xp.id)}, format="json")
        assert r.status_code == status.HTTP_403_FORBIDDEN

    @patch("apps.store.views.StoreService.purchase_with_xp")
    def test_success(self, mock_purchase, premium_client_a, item_xp, user_a):
        inv = UserInventory.objects.create(user=user_a, item=item_xp, is_equipped=False)
        mock_purchase.return_value = inv
        r = premium_client_a.post(
            "/api/store/purchase/xp/", {"item_id": str(item_xp.id)}, format="json"
        )
        assert r.status_code == status.HTTP_200_OK

    @patch("apps.store.views.StoreService.purchase_with_xp")
    def test_insufficient_xp(self, mock_purchase, premium_client_a, item_xp):
        mock_purchase.side_effect = InsufficientXPError("not enough")
        r = premium_client_a.post(
            "/api/store/purchase/xp/", {"item_id": str(item_xp.id)}, format="json"
        )
        assert r.status_code == status.HTTP_400_BAD_REQUEST

    @patch("apps.store.views.StoreService.purchase_with_xp")
    def test_already_owned(self, mock_purchase, premium_client_a, item_xp, inv_a_gold):
        mock_purchase.side_effect = ItemAlreadyOwnedError("owned")
        r = premium_client_a.post(
            "/api/store/purchase/xp/", {"item_id": str(item_xp.id)}, format="json"
        )
        assert r.status_code == status.HTTP_409_CONFLICT

    def test_item_not_purchasable_with_xp(self, premium_client_a, item_gold):
        """item_gold has xp_price=0, serializer rejects it."""
        r = premium_client_a.post(
            "/api/store/purchase/xp/", {"item_id": str(item_gold.id)}, format="json"
        )
        assert r.status_code == status.HTTP_400_BAD_REQUEST

    def test_nonexistent_item(self, premium_client_a):
        r = premium_client_a.post(
            "/api/store/purchase/xp/", {"item_id": str(uuid.uuid4())}, format="json"
        )
        assert r.status_code == status.HTTP_400_BAD_REQUEST


# ══════════════════════════════════════════════════════════════════
#  UserInventory: list, equip/unequip, history
# ══════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestUserInventory:

    def test_list_requires_auth(self, anon):
        r = anon.get("/api/store/inventory/")
        assert r.status_code == status.HTTP_401_UNAUTHORIZED

    def test_list_own_items(self, client_a, inv_a_gold):
        r = client_a.get("/api/store/inventory/")
        assert r.status_code == status.HTTP_200_OK
        results = r.data.get("results", r.data)
        assert len(results) >= 1

    def test_list_empty(self, client_b):
        """User B has no items."""
        r = client_b.get("/api/store/inventory/")
        assert r.status_code == status.HTTP_200_OK
        results = r.data.get("results", r.data)
        assert len(results) == 0

    def test_retrieve_own_item(self, client_a, inv_a_gold):
        r = client_a.get(f"/api/store/inventory/{inv_a_gold.id}/")
        assert r.status_code == status.HTTP_200_OK
        assert r.data["id"] == str(inv_a_gold.id)

    def test_history(self, client_a, inv_a_gold):
        r = client_a.get("/api/store/inventory/history/")
        assert r.status_code == status.HTTP_200_OK

    def test_filter_by_equipped(self, client_a, inv_a_gold):
        r = client_a.get("/api/store/inventory/?is_equipped=false")
        assert r.status_code == status.HTTP_200_OK

    def test_equip(self, client_a, inv_a_gold):
        r = client_a.post(
            f"/api/store/inventory/{inv_a_gold.id}/equip/",
            {"equip": True},
            format="json",
        )
        assert r.status_code == status.HTTP_200_OK
        inv_a_gold.refresh_from_db()
        assert inv_a_gold.is_equipped is True

    def test_unequip(self, client_a, inv_a_gold):
        inv_a_gold.is_equipped = True
        inv_a_gold.save()
        r = client_a.post(
            f"/api/store/inventory/{inv_a_gold.id}/equip/",
            {"equip": False},
            format="json",
        )
        assert r.status_code == status.HTTP_200_OK
        inv_a_gold.refresh_from_db()
        assert inv_a_gold.is_equipped is False

    def test_equip_unequips_same_type(self, user_a, client_a, cat_badges):
        """Only one badge_frame should be equipped at a time."""
        item1 = StoreItem.objects.create(
            category=cat_badges, name="F1", slug="f1", price=Decimal("1"),
            item_type="badge_frame", is_active=True,
        )
        item2 = StoreItem.objects.create(
            category=cat_badges, name="F2", slug="f2", price=Decimal("1"),
            item_type="badge_frame", is_active=True,
        )
        inv1 = UserInventory.objects.create(user=user_a, item=item1, is_equipped=True)
        inv2 = UserInventory.objects.create(user=user_a, item=item2, is_equipped=False)

        r = client_a.post(
            f"/api/store/inventory/{inv2.id}/equip/",
            {"equip": True},
            format="json",
        )
        assert r.status_code == status.HTTP_200_OK
        inv1.refresh_from_db()
        inv2.refresh_from_db()
        assert inv1.is_equipped is False
        assert inv2.is_equipped is True

    def test_equip_nonexistent(self, client_a):
        r = client_a.post(
            f"/api/store/inventory/{uuid.uuid4()}/equip/",
            {"equip": True},
            format="json",
        )
        assert r.status_code == status.HTTP_404_NOT_FOUND

    def test_equip_invalid_body(self, client_a, inv_a_gold):
        r = client_a.post(
            f"/api/store/inventory/{inv_a_gold.id}/equip/",
            {},
            format="json",
        )
        assert r.status_code == status.HTTP_400_BAD_REQUEST


# ══════════════════════════════════════════════════════════════════
#  IDOR: can't access other users' inventory/gifts
# ══════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestIDOR:

    def test_cannot_see_other_users_inventory(self, client_b, inv_a_gold):
        """User B cannot retrieve User A's inventory entry."""
        r = client_b.get(f"/api/store/inventory/{inv_a_gold.id}/")
        assert r.status_code == status.HTTP_404_NOT_FOUND

    def test_cannot_equip_other_users_item(self, client_b, inv_a_gold):
        """User B cannot equip User A's item."""
        r = client_b.post(
            f"/api/store/inventory/{inv_a_gold.id}/equip/",
            {"equip": True},
            format="json",
        )
        assert r.status_code == status.HTTP_404_NOT_FOUND

    def test_cannot_see_others_gifts(self, client_a, client_b, user_a, user_b, item_gold):
        """Gift list only returns gifts for the authenticated user."""
        Gift.objects.create(
            sender=user_a, recipient=user_b, item=item_gold,
            stripe_payment_intent_id="pi_g", is_claimed=False,
        )
        # User A (the sender) should not see it in THEIR gift list (recipient-only)
        r = client_a.get("/api/store/gifts/")
        assert r.status_code == status.HTTP_200_OK
        assert len(r.data) == 0

        # User B (the recipient) should see it
        r = client_b.get("/api/store/gifts/")
        assert r.status_code == status.HTTP_200_OK
        assert len(r.data) == 1

    def test_cannot_claim_others_gift(self, client_a, user_a, user_b, item_gold):
        """User A cannot claim a gift addressed to User B."""
        gift = Gift.objects.create(
            sender=user_a, recipient=user_b, item=item_gold,
            stripe_payment_intent_id="pi_gc", is_claimed=False,
        )
        # User A tries to claim (they are sender, not recipient)
        r = client_a.post(f"/api/store/gifts/{gift.id}/claim/")
        assert r.status_code == status.HTTP_400_BAD_REQUEST

    def test_cannot_refund_other_users_item(self, client_b, inv_a_gold):
        """User B cannot request a refund for User A's item."""
        r = client_b.post(
            "/api/store/refunds/",
            {"inventory_id": str(inv_a_gold.id), "reason": "I want it"},
            format="json",
        )
        # Service raises InventoryNotFoundError -> 400
        assert r.status_code == status.HTTP_400_BAD_REQUEST


# ══════════════════════════════════════════════════════════════════
#  Wishlist: add, remove, duplicate prevention
# ══════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestWishlist:

    def test_list_requires_auth(self, anon):
        r = anon.get("/api/store/wishlist/")
        assert r.status_code == status.HTTP_401_UNAUTHORIZED

    def test_add_item(self, client_a, item_gold):
        r = client_a.post(
            "/api/store/wishlist/", {"item_id": str(item_gold.id)}, format="json"
        )
        assert r.status_code == status.HTTP_201_CREATED
        assert Wishlist.objects.filter(user__email="usera@test.com", item=item_gold).exists()

    def test_add_duplicate_prevention(self, client_a, user_a, item_gold):
        """Cannot wishlist the same item twice."""
        Wishlist.objects.create(user=user_a, item=item_gold)
        r = client_a.post(
            "/api/store/wishlist/", {"item_id": str(item_gold.id)}, format="json"
        )
        assert r.status_code == status.HTTP_400_BAD_REQUEST

    def test_remove_item(self, client_a, user_a, item_gold):
        wl = Wishlist.objects.create(user=user_a, item=item_gold)
        r = client_a.delete(f"/api/store/wishlist/{wl.id}/")
        assert r.status_code == status.HTTP_204_NO_CONTENT
        assert not Wishlist.objects.filter(id=wl.id).exists()

    def test_remove_nonexistent(self, client_a):
        r = client_a.delete(f"/api/store/wishlist/{uuid.uuid4()}/")
        assert r.status_code == status.HTTP_404_NOT_FOUND

    def test_add_inactive_item(self, client_a, item_inactive):
        r = client_a.post(
            "/api/store/wishlist/", {"item_id": str(item_inactive.id)}, format="json"
        )
        assert r.status_code == status.HTTP_400_BAD_REQUEST

    def test_add_nonexistent_item(self, client_a):
        r = client_a.post(
            "/api/store/wishlist/", {"item_id": str(uuid.uuid4())}, format="json"
        )
        assert r.status_code == status.HTTP_400_BAD_REQUEST

    def test_list_own_wishlist(self, client_a, user_a, item_gold, item_silver):
        Wishlist.objects.create(user=user_a, item=item_gold)
        Wishlist.objects.create(user=user_a, item=item_silver)
        r = client_a.get("/api/store/wishlist/")
        assert r.status_code == status.HTTP_200_OK
        results = r.data.get("results", r.data)
        assert len(results) == 2


# ══════════════════════════════════════════════════════════════════
#  Gift: send, claim, list, self-gift prevention
# ══════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestGift:

    def test_send_requires_auth(self, anon, item_gold, user_b):
        r = anon.post(
            "/api/store/gifts/send/",
            {"item_id": str(item_gold.id), "recipient_id": str(user_b.id)},
            format="json",
        )
        assert r.status_code == status.HTTP_401_UNAUTHORIZED

    def test_send_free_user_forbidden(self, client_a, item_gold, user_b):
        r = client_a.post(
            "/api/store/gifts/send/",
            {"item_id": str(item_gold.id), "recipient_id": str(user_b.id)},
            format="json",
        )
        assert r.status_code == status.HTTP_403_FORBIDDEN

    @patch("apps.store.views.StoreService.send_gift")
    def test_send_success(self, mock_send, premium_client_a, item_gold, user_b):
        mock_send.return_value = {
            "gift_id": str(uuid.uuid4()),
            "client_secret": "pi_gift_secret",
            "payment_intent_id": "pi_gift",
            "amount": 499,
        }
        r = premium_client_a.post(
            "/api/store/gifts/send/",
            {
                "item_id": str(item_gold.id),
                "recipient_id": str(user_b.id),
                "message": "Enjoy!",
            },
            format="json",
        )
        assert r.status_code == status.HTTP_201_CREATED

    @patch("apps.store.views.StoreService.send_gift")
    def test_self_gift_prevention(self, mock_send, premium_client_a, item_gold, user_a):
        mock_send.side_effect = StoreServiceError("cannot gift to yourself")
        r = premium_client_a.post(
            "/api/store/gifts/send/",
            {"item_id": str(item_gold.id), "recipient_id": str(user_a.id)},
            format="json",
        )
        assert r.status_code == status.HTTP_400_BAD_REQUEST

    def test_send_nonexistent_item(self, premium_client_a, user_b):
        r = premium_client_a.post(
            "/api/store/gifts/send/",
            {"item_id": str(uuid.uuid4()), "recipient_id": str(user_b.id)},
            format="json",
        )
        assert r.status_code == status.HTTP_404_NOT_FOUND

    def test_send_nonexistent_recipient(self, premium_client_a, item_gold):
        r = premium_client_a.post(
            "/api/store/gifts/send/",
            {"item_id": str(item_gold.id), "recipient_id": str(uuid.uuid4())},
            format="json",
        )
        assert r.status_code == status.HTTP_404_NOT_FOUND

    def test_claim_requires_auth(self, anon):
        r = anon.post(f"/api/store/gifts/{uuid.uuid4()}/claim/")
        assert r.status_code == status.HTTP_401_UNAUTHORIZED

    @patch("apps.store.views.StoreService.claim_gift")
    def test_claim_success(self, mock_claim, client_b, user_b, item_gold):
        inv = UserInventory.objects.create(
            user=user_b, item=item_gold, stripe_payment_intent_id="pi_g"
        )
        mock_claim.return_value = inv
        r = client_b.post(f"/api/store/gifts/{uuid.uuid4()}/claim/")
        assert r.status_code == status.HTTP_200_OK

    def test_claim_nonexistent(self, client_a):
        r = client_a.post(f"/api/store/gifts/{uuid.uuid4()}/claim/")
        assert r.status_code == status.HTTP_400_BAD_REQUEST

    def test_list_requires_auth(self, anon):
        r = anon.get("/api/store/gifts/")
        assert r.status_code == status.HTTP_401_UNAUTHORIZED

    def test_list_empty(self, client_a):
        r = client_a.get("/api/store/gifts/")
        assert r.status_code == status.HTTP_200_OK
        assert r.data == []

    def test_list_unclaimed_only(self, client_b, user_a, user_b, item_gold, item_silver):
        """Gift list only shows unclaimed gifts."""
        Gift.objects.create(
            sender=user_a, recipient=user_b, item=item_gold,
            stripe_payment_intent_id="pi1", is_claimed=False,
        )
        Gift.objects.create(
            sender=user_a, recipient=user_b, item=item_silver,
            stripe_payment_intent_id="pi2", is_claimed=True,
            claimed_at=timezone.now(),
        )
        r = client_b.get("/api/store/gifts/")
        assert len(r.data) == 1
        assert r.data[0]["is_claimed"] is False


# ══════════════════════════════════════════════════════════════════
#  RefundRequest: request, admin approve/reject
# ══════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestRefundRequest:

    def test_requires_auth(self, anon):
        r = anon.get("/api/store/refunds/")
        assert r.status_code == status.HTTP_401_UNAUTHORIZED

    def test_list_empty(self, client_a):
        r = client_a.get("/api/store/refunds/")
        assert r.status_code == status.HTTP_200_OK

    @patch("apps.store.views.StoreService.request_refund")
    def test_request_refund(self, mock_refund, client_a, user_a, inv_a_gold):
        rr = RefundRequest.objects.create(
            user=user_a, inventory_entry=inv_a_gold, reason="not good", status="pending"
        )
        mock_refund.return_value = rr
        r = client_a.post(
            "/api/store/refunds/",
            {"inventory_id": str(inv_a_gold.id), "reason": "not good"},
            format="json",
        )
        assert r.status_code == status.HTTP_201_CREATED

    @patch("apps.store.views.StoreService.request_refund")
    def test_inventory_not_found(self, mock_refund, client_a):
        mock_refund.side_effect = InventoryNotFoundError("not found")
        r = client_a.post(
            "/api/store/refunds/",
            {"inventory_id": str(uuid.uuid4()), "reason": "test"},
            format="json",
        )
        assert r.status_code == status.HTTP_400_BAD_REQUEST

    @patch("apps.store.views.StoreService.request_refund")
    def test_xp_item_cannot_be_refunded(self, mock_refund, client_a, inv_a_gold):
        mock_refund.side_effect = StoreServiceError("not purchased with money")
        r = client_a.post(
            "/api/store/refunds/",
            {"inventory_id": str(inv_a_gold.id), "reason": "refund plz"},
            format="json",
        )
        assert r.status_code == status.HTTP_400_BAD_REQUEST

    def test_list_own_refunds(self, client_a, user_a, inv_a_gold):
        RefundRequest.objects.create(
            user=user_a, inventory_entry=inv_a_gold, reason="r1", status="pending"
        )
        r = client_a.get("/api/store/refunds/")
        assert r.status_code == status.HTTP_200_OK
        assert len(r.data) == 1


@pytest.mark.django_db
class TestRefundAdmin:

    def test_requires_admin(self, client_a):
        r = client_a.get("/api/store/admin/refunds/")
        assert r.status_code == status.HTTP_403_FORBIDDEN

    def test_list_all(self, admin_client, user_a, inv_a_gold):
        RefundRequest.objects.create(
            user=user_a, inventory_entry=inv_a_gold, reason="r1", status="pending"
        )
        r = admin_client.get("/api/store/admin/refunds/")
        assert r.status_code == status.HTTP_200_OK
        assert r.data["count"] >= 1

    def test_filter_by_status(self, admin_client, user_a, inv_a_gold):
        RefundRequest.objects.create(
            user=user_a, inventory_entry=inv_a_gold, reason="r1", status="pending"
        )
        r = admin_client.get("/api/store/admin/refunds/?status=pending")
        assert r.status_code == status.HTTP_200_OK
        assert r.data["count"] >= 1

    @patch("apps.store.views.StoreService.process_refund")
    def test_approve(self, mock_process, admin_client, user_a, inv_a_gold):
        rr = RefundRequest.objects.create(
            user=user_a, inventory_entry=inv_a_gold, reason="r1", status="pending"
        )

        def _approve(refund_request_id, approve, admin_notes=""):
            rr.status = "refunded"
            rr.admin_notes = admin_notes
            rr.save()

        mock_process.side_effect = _approve
        r = admin_client.post(
            "/api/store/admin/refunds/",
            {"refund_id": str(rr.id), "action": "approve", "admin_notes": "OK"},
            format="json",
        )
        assert r.status_code == status.HTTP_200_OK

    @patch("apps.store.views.StoreService.process_refund")
    def test_reject(self, mock_process, admin_client, user_a, inv_a_gold):
        rr = RefundRequest.objects.create(
            user=user_a, inventory_entry=inv_a_gold, reason="r1", status="pending"
        )

        def _reject(refund_request_id, approve, admin_notes=""):
            rr.status = "rejected"
            rr.admin_notes = admin_notes
            rr.save()

        mock_process.side_effect = _reject
        r = admin_client.post(
            "/api/store/admin/refunds/",
            {"refund_id": str(rr.id), "action": "reject", "admin_notes": "No"},
            format="json",
        )
        assert r.status_code == status.HTTP_200_OK

    def test_nonexistent_refund(self, admin_client):
        r = admin_client.post(
            "/api/store/admin/refunds/",
            {"refund_id": str(uuid.uuid4()), "action": "approve"},
            format="json",
        )
        assert r.status_code == status.HTTP_404_NOT_FOUND

    def test_already_processed(self, admin_client, user_a, inv_a_gold):
        rr = RefundRequest.objects.create(
            user=user_a, inventory_entry=inv_a_gold, reason="r1", status="refunded"
        )
        r = admin_client.post(
            "/api/store/admin/refunds/",
            {"refund_id": str(rr.id), "action": "approve"},
            format="json",
        )
        assert r.status_code == status.HTTP_400_BAD_REQUEST

    def test_invalid_action(self, admin_client, user_a, inv_a_gold):
        rr = RefundRequest.objects.create(
            user=user_a, inventory_entry=inv_a_gold, reason="r1", status="pending"
        )
        r = admin_client.post(
            "/api/store/admin/refunds/",
            {"refund_id": str(rr.id), "action": "cancel"},
            format="json",
        )
        assert r.status_code == status.HTTP_400_BAD_REQUEST


# ══════════════════════════════════════════════════════════════════
#  Service layer direct tests (with Stripe mocks)
# ══════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestServiceCreatePaymentIntent:

    @patch("apps.store.services.stripe.PaymentIntent.create")
    def test_success(self, mock_stripe, user_a, item_gold):
        mock_stripe.return_value = MagicMock(
            id="pi_svc_001", client_secret="pi_svc_secret"
        )
        result = StoreService.create_payment_intent(user_a, item_gold)
        assert result["payment_intent_id"] == "pi_svc_001"
        assert result["client_secret"] == "pi_svc_secret"
        assert result["amount"] == int(item_gold.price * 100)

    def test_inactive_item_raises(self, user_a, item_inactive):
        with pytest.raises(ItemNotActiveError):
            StoreService.create_payment_intent(user_a, item_inactive)

    def test_already_owned_raises(self, user_a, item_gold, inv_a_gold):
        with pytest.raises(ItemAlreadyOwnedError):
            StoreService.create_payment_intent(user_a, item_gold)

    @patch("apps.store.services.stripe.PaymentIntent.create")
    def test_stripe_error_raises(self, mock_stripe, user_a, item_gold):
        import stripe

        mock_stripe.side_effect = stripe.error.StripeError("boom")
        with pytest.raises(PaymentVerificationError, match="Payment processing failed"):
            StoreService.create_payment_intent(user_a, item_gold)


@pytest.mark.django_db
class TestServiceConfirmPurchase:

    def _mock_pi(self, item, user, pi_status="succeeded"):
        pi = MagicMock()
        pi.status = pi_status
        pi.amount = int(item.price * 100)
        pi.get.return_value = {
            "user_id": str(user.id),
            "item_id": str(item.id),
        }
        return pi

    @patch("apps.store.services.stripe.PaymentIntent.retrieve")
    def test_success(self, mock_retrieve, user_a, item_gold):
        mock_retrieve.return_value = self._mock_pi(item_gold, user_a)
        inv = StoreService.confirm_purchase(user_a, item_gold, "pi_ok")
        assert inv.user == user_a
        assert inv.item == item_gold

    @patch("apps.store.services.stripe.PaymentIntent.retrieve")
    def test_already_owned(self, mock_retrieve, user_a, item_gold, inv_a_gold):
        with pytest.raises(ItemAlreadyOwnedError):
            StoreService.confirm_purchase(user_a, item_gold, "pi_dup")

    @patch("apps.store.services.stripe.PaymentIntent.retrieve")
    def test_payment_not_succeeded(self, mock_retrieve, user_a, item_gold):
        mock_retrieve.return_value = self._mock_pi(
            item_gold, user_a, pi_status="requires_payment_method"
        )
        with pytest.raises(PaymentVerificationError, match="not been completed"):
            StoreService.confirm_purchase(user_a, item_gold, "pi_pending")

    @patch("apps.store.services.stripe.PaymentIntent.retrieve")
    def test_amount_mismatch(self, mock_retrieve, user_a, item_gold):
        pi = self._mock_pi(item_gold, user_a)
        pi.amount = 1
        mock_retrieve.return_value = pi
        with pytest.raises(PaymentVerificationError, match="amount does not match"):
            StoreService.confirm_purchase(user_a, item_gold, "pi_wrong")

    @patch("apps.store.services.stripe.PaymentIntent.retrieve")
    def test_user_mismatch(self, mock_retrieve, user_a, user_b, item_gold):
        pi = self._mock_pi(item_gold, user_b)
        mock_retrieve.return_value = pi
        with pytest.raises(PaymentVerificationError, match="user mismatch"):
            StoreService.confirm_purchase(user_a, item_gold, "pi_wrong_user")

    @patch("apps.store.services.stripe.PaymentIntent.retrieve")
    def test_stripe_retrieve_error(self, mock_retrieve, user_a, item_gold):
        import stripe

        mock_retrieve.side_effect = stripe.error.StripeError("fail")
        with pytest.raises(PaymentVerificationError, match="Unable to verify"):
            StoreService.confirm_purchase(user_a, item_gold, "pi_err")


@pytest.mark.django_db
class TestServiceXPPurchase:

    @pytest.fixture
    def user_with_xp(self, user_a):
        user_a.xp = 1000
        user_a.save(update_fields=["xp"])
        return user_a

    def test_success(self, user_with_xp, item_xp):
        inv = StoreService.purchase_with_xp(user_with_xp, item_xp)
        assert inv.user == user_with_xp
        assert inv.item == item_xp
        user_with_xp.refresh_from_db()
        assert user_with_xp.xp == 500

    def test_insufficient_xp(self, user_a, item_xp):
        with pytest.raises(InsufficientXPError):
            StoreService.purchase_with_xp(user_a, item_xp)

    def test_inactive_item(self, user_with_xp, item_inactive):
        with pytest.raises(ItemNotActiveError):
            StoreService.purchase_with_xp(user_with_xp, item_inactive)

    def test_already_owned(self, user_with_xp, item_xp):
        UserInventory.objects.create(user=user_with_xp, item=item_xp)
        with pytest.raises(ItemAlreadyOwnedError):
            StoreService.purchase_with_xp(user_with_xp, item_xp)

    def test_zero_xp_price_rejected(self, user_with_xp, item_gold):
        with pytest.raises(ItemNotActiveError, match="cannot be purchased with XP"):
            StoreService.purchase_with_xp(user_with_xp, item_gold)


@pytest.mark.django_db
class TestServiceEquipUnequip:

    def test_equip(self, user_a, inv_a_gold):
        result = StoreService.equip_item(user_a, inv_a_gold.id)
        assert result.is_equipped is True

    def test_equip_nonexistent(self, user_a):
        with pytest.raises(InventoryNotFoundError):
            StoreService.equip_item(user_a, uuid.uuid4())

    def test_equip_other_users_item(self, user_b, inv_a_gold):
        with pytest.raises(InventoryNotFoundError):
            StoreService.equip_item(user_b, inv_a_gold.id)

    def test_unequip(self, user_a, inv_a_gold):
        inv_a_gold.is_equipped = True
        inv_a_gold.save()
        result = StoreService.unequip_item(user_a, inv_a_gold.id)
        assert result.is_equipped is False

    def test_unequip_nonexistent(self, user_a):
        with pytest.raises(InventoryNotFoundError):
            StoreService.unequip_item(user_a, uuid.uuid4())


@pytest.mark.django_db
class TestServiceSendGift:

    @patch("apps.store.services.stripe.PaymentIntent.create")
    def test_success(self, mock_stripe, user_a, user_b, item_gold):
        mock_stripe.return_value = MagicMock(
            id="pi_gift_svc", client_secret="pi_gift_secret"
        )
        result = StoreService.send_gift(user_a, user_b, item_gold, message="Hi!")
        assert "gift_id" in result
        gift = Gift.objects.get(id=result["gift_id"])
        assert gift.sender == user_a
        assert gift.recipient == user_b
        assert gift.message == "Hi!"

    def test_inactive_item(self, user_a, user_b, item_inactive):
        with pytest.raises(ItemNotActiveError):
            StoreService.send_gift(user_a, user_b, item_inactive)

    def test_self_gift_raises(self, user_a, item_gold):
        with pytest.raises(StoreServiceError, match="cannot gift"):
            StoreService.send_gift(user_a, user_a, item_gold)

    def test_recipient_already_owns(self, user_a, user_b, item_gold):
        UserInventory.objects.create(user=user_b, item=item_gold)
        with pytest.raises(ItemAlreadyOwnedError):
            StoreService.send_gift(user_a, user_b, item_gold)

    @patch("apps.store.services.stripe.PaymentIntent.create")
    def test_stripe_error(self, mock_stripe, user_a, user_b, item_gold):
        import stripe

        mock_stripe.side_effect = stripe.error.StripeError("stripe down")
        with pytest.raises(PaymentVerificationError, match="Payment failed"):
            StoreService.send_gift(user_a, user_b, item_gold)


@pytest.mark.django_db
class TestServiceClaimGift:

    def test_success(self, user_a, user_b, item_gold):
        gift = Gift.objects.create(
            sender=user_a, recipient=user_b, item=item_gold,
            stripe_payment_intent_id="pi_claim", is_claimed=False,
        )
        inv = StoreService.claim_gift(user_b, gift.id)
        assert inv.user == user_b
        assert inv.item == item_gold
        gift.refresh_from_db()
        assert gift.is_claimed is True
        assert gift.claimed_at is not None

    def test_nonexistent_gift(self, user_a):
        with pytest.raises(ItemNotFoundError):
            StoreService.claim_gift(user_a, uuid.uuid4())

    def test_already_claimed(self, user_a, user_b, item_gold):
        gift = Gift.objects.create(
            sender=user_a, recipient=user_b, item=item_gold,
            stripe_payment_intent_id="pi_cl", is_claimed=True,
            claimed_at=timezone.now(),
        )
        with pytest.raises(ItemNotFoundError):
            StoreService.claim_gift(user_b, gift.id)

    def test_claim_when_already_owns(self, user_a, user_b, item_gold):
        gift = Gift.objects.create(
            sender=user_a, recipient=user_b, item=item_gold,
            stripe_payment_intent_id="pi_cl2", is_claimed=False,
        )
        UserInventory.objects.create(user=user_b, item=item_gold)
        with pytest.raises(ItemAlreadyOwnedError):
            StoreService.claim_gift(user_b, gift.id)

    def test_wrong_recipient(self, user_a, user_b, item_gold):
        gift = Gift.objects.create(
            sender=user_a, recipient=user_b, item=item_gold,
            stripe_payment_intent_id="pi_wr", is_claimed=False,
        )
        with pytest.raises(ItemNotFoundError):
            StoreService.claim_gift(user_a, gift.id)  # user_a is sender, not recipient


@pytest.mark.django_db
class TestServiceRefund:

    def test_request_refund_success(self, user_a, inv_a_gold):
        rr = StoreService.request_refund(user_a, inv_a_gold.id, "not happy")
        assert rr.status == "pending"
        assert rr.user == user_a

    def test_request_refund_inventory_not_found(self, user_a):
        with pytest.raises(InventoryNotFoundError):
            StoreService.request_refund(user_a, uuid.uuid4(), "gone")

    def test_request_refund_xp_item_rejected(self, user_a, item_xp):
        inv = UserInventory.objects.create(
            user=user_a, item=item_xp, stripe_payment_intent_id=""
        )
        with pytest.raises(StoreServiceError, match="not purchased with money"):
            StoreService.request_refund(user_a, inv.id, "refund plz")

    def test_duplicate_pending_refund(self, user_a, inv_a_gold):
        StoreService.request_refund(user_a, inv_a_gold.id, "first")
        with pytest.raises(StoreServiceError, match="already pending"):
            StoreService.request_refund(user_a, inv_a_gold.id, "second")

    @patch("apps.store.services.stripe.Refund.create")
    @patch.object(UserInventory, "delete")
    def test_process_approve(self, mock_del, mock_refund, user_a, inv_a_gold):
        mock_refund.return_value = MagicMock(id="re_123")
        rr = RefundRequest.objects.create(
            user=user_a, inventory_entry=inv_a_gold, reason="test", status="pending"
        )
        result = StoreService.process_refund(rr.id, approve=True, admin_notes="OK")
        assert result.status == "refunded"
        assert result.stripe_refund_id == "re_123"
        mock_del.assert_called_once()

    def test_process_reject(self, user_a, inv_a_gold):
        rr = RefundRequest.objects.create(
            user=user_a, inventory_entry=inv_a_gold, reason="test", status="pending"
        )
        result = StoreService.process_refund(rr.id, approve=False, admin_notes="No")
        assert result.status == "rejected"
        assert UserInventory.objects.filter(id=inv_a_gold.id).exists()

    def test_process_already_processed(self, user_a, inv_a_gold):
        rr = RefundRequest.objects.create(
            user=user_a, inventory_entry=inv_a_gold, reason="test", status="refunded"
        )
        with pytest.raises(ItemNotFoundError, match="already processed"):
            StoreService.process_refund(rr.id, approve=True)

    @patch("apps.store.services.stripe.Refund.create")
    def test_stripe_refund_error(self, mock_refund, user_a, inv_a_gold):
        import stripe

        mock_refund.side_effect = stripe.error.StripeError("stripe down")
        rr = RefundRequest.objects.create(
            user=user_a, inventory_entry=inv_a_gold, reason="test", status="pending"
        )
        with pytest.raises(PaymentVerificationError, match="Stripe refund failed"):
            StoreService.process_refund(rr.id, approve=True)


# ══════════════════════════════════════════════════════════════════
#  Model unit tests
# ══════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestModels:

    def test_store_item_str(self, item_gold):
        s = str(item_gold)
        assert "Gold Frame" in s
        assert "Rare" in s
        assert "4.99" in s

    def test_store_category_str(self, cat_badges):
        assert str(cat_badges) == "Badge Frames"

    def test_user_inventory_str(self, inv_a_gold):
        s = str(inv_a_gold)
        assert "usera@test.com" in s
        assert "Gold Frame" in s

    def test_user_inventory_equipped_str(self, inv_a_gold):
        inv_a_gold.is_equipped = True
        inv_a_gold.save()
        assert "[EQUIPPED]" in str(inv_a_gold)

    def test_wishlist_str(self, user_a, item_gold):
        wl = Wishlist.objects.create(user=user_a, item=item_gold)
        s = str(wl)
        assert "usera@test.com" in s
        assert "Gold Frame" in s

    def test_gift_str(self, user_a, user_b, item_gold):
        gift = Gift.objects.create(
            sender=user_a, recipient=user_b, item=item_gold
        )
        s = str(gift)
        assert "Gold Frame" in s
        assert "pending" in s

    def test_refund_request_str(self, user_a, inv_a_gold):
        rr = RefundRequest.objects.create(
            user=user_a, inventory_entry=inv_a_gold, reason="test"
        )
        s = str(rr)
        assert "usera@test.com" in s
        assert "Gold Frame" in s

    def test_unique_user_inventory(self, user_a, item_gold, inv_a_gold):
        """Cannot own the same item twice."""
        from django.db import IntegrityError

        with pytest.raises(IntegrityError):
            UserInventory.objects.create(user=user_a, item=item_gold)

    def test_unique_wishlist(self, user_a, item_gold):
        """Cannot wishlist the same item twice."""
        from django.db import IntegrityError

        Wishlist.objects.create(user=user_a, item=item_gold)
        with pytest.raises(IntegrityError):
            Wishlist.objects.create(user=user_a, item=item_gold)

    def test_item_type_choices(self, cat_badges):
        for code, _ in StoreItem.ITEM_TYPE_CHOICES:
            item = StoreItem.objects.create(
                category=cat_badges,
                name=f"T-{code}",
                slug=f"t-{code}",
                price=Decimal("1.99"),
                item_type=code,
            )
            assert item.item_type == code

    def test_rarity_choices(self, cat_badges):
        for code, _ in StoreItem.RARITY_CHOICES:
            item = StoreItem.objects.create(
                category=cat_badges,
                name=f"R-{code}",
                slug=f"r-{code}",
                price=Decimal("1.99"),
                item_type="badge_frame",
                rarity=code,
            )
            assert item.rarity == code

    def test_metadata_json(self, cat_badges):
        item = StoreItem.objects.create(
            category=cat_badges,
            name="Animated",
            slug="animated",
            price=Decimal("7.99"),
            item_type="badge_frame",
            metadata={"animation": "pulse", "color": "#FF0000"},
        )
        item.refresh_from_db()
        assert item.metadata["animation"] == "pulse"

    def test_preview_fields(self, item_preview):
        assert item_preview.preview_type == "theme"
        assert item_preview.preview_data["accent"] == "#8B5CF6"

    def test_xp_price_default_zero(self, item_gold):
        assert item_gold.xp_price == 0

    def test_different_users_same_item(self, user_b, item_gold, inv_a_gold):
        """Two different users can own the same item."""
        inv_b = UserInventory.objects.create(user=user_b, item=item_gold)
        assert inv_b.user == user_b
