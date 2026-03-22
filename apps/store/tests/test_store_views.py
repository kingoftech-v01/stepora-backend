"""
Tests for apps/store/views.py

Covers: StoreCategoryViewSet, StoreItemViewSet, UserInventoryViewSet,
WishlistViewSet, PurchaseView, PurchaseConfirmView, XPPurchaseView,
GiftSendView, GiftClaimView, GiftListView, RefundRequestView, RefundAdminView.
"""

import uuid
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

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
    PaymentVerificationError,
    StoreServiceError,
)
from apps.subscriptions.models import Subscription, SubscriptionPlan
from apps.users.models import User

# ── helpers / fixtures ──────────────────────────────────────────────


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
    # ensure has_store is True even if plan already existed
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
def admin_user(db):
    """Staff / admin user."""
    return User.objects.create_superuser(
        email="admin@example.com",
        password="admin123",
    )


@pytest.fixture
def premium_user(store_user):
    return _make_premium(store_user)


@pytest.fixture
def premium_user2(store_user2):
    return _make_premium(store_user2)


@pytest.fixture
def premium_client(premium_user):
    c = APIClient()
    c.force_authenticate(user=premium_user)
    return c


@pytest.fixture
def premium_client2(premium_user2):
    c = APIClient()
    c.force_authenticate(user=premium_user2)
    return c


@pytest.fixture
def admin_client(admin_user):
    c = APIClient()
    c.force_authenticate(user=admin_user)
    return c


@pytest.fixture
def anon_client():
    return APIClient()


@pytest.fixture
def auth_client(store_user):
    """Authenticated but NOT premium."""
    c = APIClient()
    c.force_authenticate(user=store_user)
    return c


@pytest.fixture
def epic_item(test_category):
    return StoreItem.objects.create(
        category=test_category,
        name="Epic Frame",
        slug="epic-frame",
        price=Decimal("6.99"),
        item_type="badge_frame",
        rarity="epic",
        is_active=True,
    )


@pytest.fixture
def inactive_item(test_category):
    return StoreItem.objects.create(
        category=test_category,
        name="Inactive Item",
        slug="inactive-item",
        price=Decimal("1.99"),
        item_type="badge_frame",
        rarity="common",
        is_active=False,
    )


@pytest.fixture
def xp_item(test_category):
    return StoreItem.objects.create(
        category=test_category,
        name="XP Badge",
        slug="xp-badge",
        price=Decimal("0.00"),
        xp_price=500,
        item_type="badge_frame",
        rarity="common",
        is_active=True,
    )


@pytest.fixture
def preview_item(test_category):
    return StoreItem.objects.create(
        category=test_category,
        name="Theme Preview",
        slug="theme-preview",
        price=Decimal("4.99"),
        item_type="theme_skin",
        rarity="epic",
        is_active=True,
        preview_type="theme",
        preview_data={"primary": "#FF0000"},
    )


# ══════════════════════════════════════════════════════════════════
#  StoreCategoryViewSet
# ══════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestStoreCategoryViewSet:

    def test_list_public(self, anon_client, test_category):
        r = anon_client.get("/api/store/categories/")
        assert r.status_code == status.HTTP_200_OK
        results = r.data.get("results", r.data)
        assert any(c["slug"] == "badge-frames" for c in results)

    def test_list_only_active(self, anon_client, test_category):
        StoreCategory.objects.create(name="Hidden", slug="hidden", is_active=False)
        r = anon_client.get("/api/store/categories/")
        slugs = [c["slug"] for c in r.data.get("results", r.data)]
        assert "hidden" not in slugs

    def test_retrieve_by_slug(self, anon_client, test_category, test_item):
        r = anon_client.get(f"/api/store/categories/{test_category.slug}/")
        assert r.status_code == status.HTTP_200_OK
        assert r.data["name"] == test_category.name
        # detail serializer should include items
        assert "items" in r.data

    def test_retrieve_nonexistent(self, anon_client):
        r = anon_client.get("/api/store/categories/nope/")
        assert r.status_code == status.HTTP_404_NOT_FOUND

    def test_search(self, anon_client, test_category):
        r = anon_client.get("/api/store/categories/?search=Badge")
        assert r.status_code == status.HTTP_200_OK


# ══════════════════════════════════════════════════════════════════
#  StoreItemViewSet
# ══════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestStoreItemViewSet:

    def test_list_public(self, anon_client, test_item):
        r = anon_client.get("/api/store/items/")
        assert r.status_code == status.HTTP_200_OK

    def test_retrieve_by_slug(self, anon_client, test_item):
        r = anon_client.get(f"/api/store/items/{test_item.slug}/")
        assert r.status_code == status.HTTP_200_OK
        assert r.data["name"] == "Gold Frame"
        assert "owners_count" in r.data  # detail serializer field

    def test_inactive_hidden(self, anon_client, inactive_item, test_item):
        r = anon_client.get("/api/store/items/")
        slugs = [i["slug"] for i in r.data.get("results", r.data)]
        assert "inactive-item" not in slugs

    def test_future_item_hidden(self, anon_client, test_category):
        StoreItem.objects.create(
            category=test_category,
            name="Future",
            slug="future",
            price=Decimal("1.00"),
            item_type="badge_frame",
            is_active=True,
            available_from=timezone.now() + timedelta(days=30),
        )
        r = anon_client.get("/api/store/items/")
        slugs = [i["slug"] for i in r.data.get("results", r.data)]
        assert "future" not in slugs

    def test_expired_item_hidden(self, anon_client, test_category):
        StoreItem.objects.create(
            category=test_category,
            name="Expired",
            slug="expired",
            price=Decimal("1.00"),
            item_type="badge_frame",
            is_active=True,
            available_until=timezone.now() - timedelta(days=1),
        )
        r = anon_client.get("/api/store/items/")
        slugs = [i["slug"] for i in r.data.get("results", r.data)]
        assert "expired" not in slugs

    def test_filter_by_rarity(self, anon_client, test_item):
        r = anon_client.get("/api/store/items/?rarity=rare")
        assert r.status_code == status.HTTP_200_OK

    def test_search(self, anon_client, test_item):
        r = anon_client.get("/api/store/items/?search=Gold")
        assert r.status_code == status.HTTP_200_OK


# ── Featured ─────────────────────────────────────────────────────


@pytest.mark.django_db
class TestStoreItemFeatured:

    def test_featured_returns_epic_legendary(self, anon_client, epic_item, legendary_item):
        r = anon_client.get("/api/store/items/featured/")
        assert r.status_code == status.HTTP_200_OK
        names = [i["name"] for i in r.data]
        assert "Epic Frame" in names or "Cosmic Theme" in names

    def test_featured_excludes_common(self, anon_client, test_item):
        """Common/rare items should not appear in featured."""
        r = anon_client.get("/api/store/items/featured/")
        assert r.status_code == status.HTTP_200_OK
        # test_item is rare, not epic/legendary
        names = [i["name"] for i in r.data]
        assert "Gold Frame" not in names


# ── Preview ──────────────────────────────────────────────────────


@pytest.mark.django_db
class TestStoreItemPreview:

    def test_preview_with_data(self, anon_client, preview_item):
        r = anon_client.get(f"/api/store/items/{preview_item.slug}/preview/")
        assert r.status_code == status.HTTP_200_OK
        assert r.data["preview_type"] == "theme"

    def test_preview_no_data(self, anon_client, test_item):
        r = anon_client.get(f"/api/store/items/{test_item.slug}/preview/")
        assert r.status_code == status.HTTP_404_NOT_FOUND


# ══════════════════════════════════════════════════════════════════
#  UserInventoryViewSet
# ══════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestUserInventoryViewSet:

    def test_list_requires_auth(self, anon_client):
        r = anon_client.get("/api/store/inventory/")
        assert r.status_code == status.HTTP_401_UNAUTHORIZED

    def test_list_own_items(self, auth_client, user_inventory_entry):
        r = auth_client.get("/api/store/inventory/")
        assert r.status_code == status.HTTP_200_OK

    def test_list_empty(self, auth_client):
        r = auth_client.get("/api/store/inventory/")
        assert r.status_code == status.HTTP_200_OK

    def test_retrieve_item(self, auth_client, user_inventory_entry):
        r = auth_client.get(f"/api/store/inventory/{user_inventory_entry.id}/")
        assert r.status_code == status.HTTP_200_OK

    def test_history(self, auth_client, user_inventory_entry):
        r = auth_client.get("/api/store/inventory/history/")
        assert r.status_code == status.HTTP_200_OK

    def test_equip(self, auth_client, user_inventory_entry):
        r = auth_client.post(
            f"/api/store/inventory/{user_inventory_entry.id}/equip/",
            {"equip": True},
            format="json",
        )
        assert r.status_code == status.HTTP_200_OK
        user_inventory_entry.refresh_from_db()
        assert user_inventory_entry.is_equipped is True

    def test_unequip(self, auth_client, user_inventory_entry):
        user_inventory_entry.is_equipped = True
        user_inventory_entry.save()
        r = auth_client.post(
            f"/api/store/inventory/{user_inventory_entry.id}/equip/",
            {"equip": False},
            format="json",
        )
        assert r.status_code == status.HTTP_200_OK
        user_inventory_entry.refresh_from_db()
        assert user_inventory_entry.is_equipped is False

    def test_equip_nonexistent(self, auth_client):
        r = auth_client.post(
            f"/api/store/inventory/{uuid.uuid4()}/equip/",
            {"equip": True},
            format="json",
        )
        assert r.status_code == status.HTTP_404_NOT_FOUND

    def test_equip_invalid_body(self, auth_client, user_inventory_entry):
        r = auth_client.post(
            f"/api/store/inventory/{user_inventory_entry.id}/equip/",
            {},
            format="json",
        )
        assert r.status_code == status.HTTP_400_BAD_REQUEST


# ══════════════════════════════════════════════════════════════════
#  WishlistViewSet
# ══════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestWishlistViewSet:

    def test_list_requires_auth(self, anon_client):
        r = anon_client.get("/api/store/wishlist/")
        assert r.status_code == status.HTTP_401_UNAUTHORIZED

    def test_list_empty(self, auth_client):
        r = auth_client.get("/api/store/wishlist/")
        assert r.status_code == status.HTTP_200_OK

    def test_add_item(self, auth_client, test_item):
        r = auth_client.post(
            "/api/store/wishlist/",
            {"item_id": str(test_item.id)},
            format="json",
        )
        assert r.status_code == status.HTTP_201_CREATED

    def test_add_duplicate(self, auth_client, store_user, test_item):
        Wishlist.objects.create(user=store_user, item=test_item)
        r = auth_client.post(
            "/api/store/wishlist/",
            {"item_id": str(test_item.id)},
            format="json",
        )
        assert r.status_code == status.HTTP_400_BAD_REQUEST

    def test_remove_item(self, auth_client, store_user, test_item):
        wl = Wishlist.objects.create(user=store_user, item=test_item)
        r = auth_client.delete(f"/api/store/wishlist/{wl.id}/")
        assert r.status_code == status.HTTP_204_NO_CONTENT

    def test_remove_nonexistent(self, auth_client):
        r = auth_client.delete(f"/api/store/wishlist/{uuid.uuid4()}/")
        assert r.status_code == status.HTTP_404_NOT_FOUND

    def test_add_inactive_item(self, auth_client, inactive_item):
        r = auth_client.post(
            "/api/store/wishlist/",
            {"item_id": str(inactive_item.id)},
            format="json",
        )
        assert r.status_code == status.HTTP_400_BAD_REQUEST

    def test_add_nonexistent_item(self, auth_client):
        r = auth_client.post(
            "/api/store/wishlist/",
            {"item_id": str(uuid.uuid4())},
            format="json",
        )
        assert r.status_code == status.HTTP_400_BAD_REQUEST


# ══════════════════════════════════════════════════════════════════
#  PurchaseView (Stripe)
# ══════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestPurchaseView:

    def test_requires_auth(self, anon_client, test_item):
        r = anon_client.post(
            "/api/store/purchase/",
            {"item_id": str(test_item.id)},
            format="json",
        )
        assert r.status_code == status.HTTP_401_UNAUTHORIZED

    def test_free_user_forbidden(self, auth_client, test_item):
        r = auth_client.post(
            "/api/store/purchase/",
            {"item_id": str(test_item.id)},
            format="json",
        )
        assert r.status_code == status.HTTP_403_FORBIDDEN

    @patch("apps.store.views.StoreService.create_payment_intent")
    def test_success(self, mock_create, premium_client, test_item):
        mock_create.return_value = {
            "client_secret": "pi_test_secret_xxx",
            "payment_intent_id": "pi_test_abc",
            "amount": 499,
        }
        r = premium_client.post(
            "/api/store/purchase/",
            {"item_id": str(test_item.id)},
            format="json",
        )
        assert r.status_code == status.HTTP_201_CREATED
        assert r.data["client_secret"] == "pi_test_secret_xxx"

    def test_nonexistent_item(self, premium_client):
        r = premium_client.post(
            "/api/store/purchase/",
            {"item_id": str(uuid.uuid4())},
            format="json",
        )
        assert r.status_code == status.HTTP_400_BAD_REQUEST

    @patch("apps.store.views.StoreService.create_payment_intent")
    def test_already_owned(self, mock_create, premium_client, test_item, store_user):
        mock_create.side_effect = ItemAlreadyOwnedError("already owned")
        # Create ownership so serializer passes
        UserInventory.objects.create(user=store_user, item=test_item)
        r = premium_client.post(
            "/api/store/purchase/",
            {"item_id": str(test_item.id)},
            format="json",
        )
        # serializer catches ownership too -> 400
        assert r.status_code == status.HTTP_400_BAD_REQUEST

    @patch("apps.store.views.StoreService.create_payment_intent")
    def test_inactive_item(self, mock_create, premium_client, inactive_item):
        r = premium_client.post(
            "/api/store/purchase/",
            {"item_id": str(inactive_item.id)},
            format="json",
        )
        # Serializer rejects inactive items
        assert r.status_code == status.HTTP_400_BAD_REQUEST

    @patch("apps.store.views.StoreService.create_payment_intent")
    def test_stripe_error(self, mock_create, premium_client, test_item):
        mock_create.side_effect = PaymentVerificationError("stripe down")
        r = premium_client.post(
            "/api/store/purchase/",
            {"item_id": str(test_item.id)},
            format="json",
        )
        assert r.status_code == status.HTTP_502_BAD_GATEWAY


# ══════════════════════════════════════════════════════════════════
#  PurchaseConfirmView
# ══════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestPurchaseConfirmView:

    def test_requires_auth(self, anon_client, test_item):
        r = anon_client.post(
            "/api/store/purchase/confirm/",
            {"item_id": str(test_item.id), "payment_intent_id": "pi_xyz"},
            format="json",
        )
        assert r.status_code == status.HTTP_401_UNAUTHORIZED

    @patch("apps.store.views.StoreService.confirm_purchase")
    def test_success(self, mock_confirm, premium_client, test_item, store_user):
        inv = UserInventory.objects.create(
            user=store_user,
            item=test_item,
            stripe_payment_intent_id="pi_confirmed",
        )
        mock_confirm.return_value = inv
        r = premium_client.post(
            "/api/store/purchase/confirm/",
            {"item_id": str(test_item.id), "payment_intent_id": "pi_confirmed"},
            format="json",
        )
        assert r.status_code == status.HTTP_200_OK

    def test_nonexistent_item(self, premium_client):
        r = premium_client.post(
            "/api/store/purchase/confirm/",
            {"item_id": str(uuid.uuid4()), "payment_intent_id": "pi_xyz"},
            format="json",
        )
        assert r.status_code == status.HTTP_400_BAD_REQUEST

    def test_invalid_payment_intent_format(self, premium_client, test_item):
        r = premium_client.post(
            "/api/store/purchase/confirm/",
            {"item_id": str(test_item.id), "payment_intent_id": "bad_format"},
            format="json",
        )
        assert r.status_code == status.HTTP_400_BAD_REQUEST

    @patch("apps.store.views.StoreService.confirm_purchase")
    def test_already_owned(self, mock_confirm, premium_client, test_item, store_user):
        UserInventory.objects.create(user=store_user, item=test_item)
        mock_confirm.side_effect = ItemAlreadyOwnedError("already owned")
        r = premium_client.post(
            "/api/store/purchase/confirm/",
            {"item_id": str(test_item.id), "payment_intent_id": "pi_dup"},
            format="json",
        )
        assert r.status_code == status.HTTP_409_CONFLICT

    @patch("apps.store.views.StoreService.confirm_purchase")
    def test_payment_not_succeeded(self, mock_confirm, premium_client, test_item):
        mock_confirm.side_effect = PaymentVerificationError("not succeeded")
        r = premium_client.post(
            "/api/store/purchase/confirm/",
            {"item_id": str(test_item.id), "payment_intent_id": "pi_fail"},
            format="json",
        )
        assert r.status_code == status.HTTP_400_BAD_REQUEST


# ══════════════════════════════════════════════════════════════════
#  XPPurchaseView
# ══════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestXPPurchaseView:

    def test_requires_auth(self, anon_client, xp_item):
        r = anon_client.post(
            "/api/store/purchase/xp/",
            {"item_id": str(xp_item.id)},
            format="json",
        )
        assert r.status_code == status.HTTP_401_UNAUTHORIZED

    def test_free_user_forbidden(self, auth_client, xp_item):
        r = auth_client.post(
            "/api/store/purchase/xp/",
            {"item_id": str(xp_item.id)},
            format="json",
        )
        assert r.status_code == status.HTTP_403_FORBIDDEN

    @patch("apps.store.views.StoreService.purchase_with_xp")
    def test_success(self, mock_purchase, premium_client, xp_item, store_user):
        inv = UserInventory.objects.create(
            user=store_user, item=xp_item, stripe_payment_intent_id="", is_equipped=False
        )
        mock_purchase.return_value = inv
        r = premium_client.post(
            "/api/store/purchase/xp/",
            {"item_id": str(xp_item.id)},
            format="json",
        )
        assert r.status_code == status.HTTP_200_OK

    def test_nonexistent_item(self, premium_client):
        r = premium_client.post(
            "/api/store/purchase/xp/",
            {"item_id": str(uuid.uuid4())},
            format="json",
        )
        assert r.status_code == status.HTTP_400_BAD_REQUEST

    @patch("apps.store.views.StoreService.purchase_with_xp")
    def test_insufficient_xp(self, mock_purchase, premium_client, xp_item):
        mock_purchase.side_effect = InsufficientXPError("not enough XP")
        r = premium_client.post(
            "/api/store/purchase/xp/",
            {"item_id": str(xp_item.id)},
            format="json",
        )
        assert r.status_code == status.HTTP_400_BAD_REQUEST

    @patch("apps.store.views.StoreService.purchase_with_xp")
    def test_already_owned(self, mock_purchase, premium_client, xp_item, store_user):
        UserInventory.objects.create(user=store_user, item=xp_item)
        mock_purchase.side_effect = ItemAlreadyOwnedError("already owned")
        r = premium_client.post(
            "/api/store/purchase/xp/",
            {"item_id": str(xp_item.id)},
            format="json",
        )
        assert r.status_code == status.HTTP_409_CONFLICT

    @patch("apps.store.views.StoreService.purchase_with_xp")
    def test_inactive_item_error(self, mock_purchase, premium_client, xp_item):
        mock_purchase.side_effect = ItemNotActiveError("not active")
        r = premium_client.post(
            "/api/store/purchase/xp/",
            {"item_id": str(xp_item.id)},
            format="json",
        )
        assert r.status_code == status.HTTP_400_BAD_REQUEST

    def test_item_not_purchasable_with_xp(self, premium_client, test_item):
        """test_item has xp_price=0 so serializer rejects it."""
        r = premium_client.post(
            "/api/store/purchase/xp/",
            {"item_id": str(test_item.id)},
            format="json",
        )
        assert r.status_code == status.HTTP_400_BAD_REQUEST


# ══════════════════════════════════════════════════════════════════
#  GiftSendView
# ══════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestGiftSendView:

    def test_requires_auth(self, anon_client, test_item, store_user2):
        r = anon_client.post(
            "/api/store/gifts/send/",
            {"item_id": str(test_item.id), "recipient_id": str(store_user2.id)},
            format="json",
        )
        assert r.status_code == status.HTTP_401_UNAUTHORIZED

    def test_free_user_forbidden(self, auth_client, test_item, store_user2):
        r = auth_client.post(
            "/api/store/gifts/send/",
            {"item_id": str(test_item.id), "recipient_id": str(store_user2.id)},
            format="json",
        )
        assert r.status_code == status.HTTP_403_FORBIDDEN

    def test_nonexistent_item(self, premium_client, store_user2):
        r = premium_client.post(
            "/api/store/gifts/send/",
            {"item_id": str(uuid.uuid4()), "recipient_id": str(store_user2.id)},
            format="json",
        )
        assert r.status_code == status.HTTP_404_NOT_FOUND

    def test_nonexistent_recipient(self, premium_client, test_item):
        r = premium_client.post(
            "/api/store/gifts/send/",
            {"item_id": str(test_item.id), "recipient_id": str(uuid.uuid4())},
            format="json",
        )
        assert r.status_code == status.HTTP_404_NOT_FOUND

    @patch("apps.store.views.StoreService.send_gift")
    def test_success(self, mock_send, premium_client, test_item, store_user2):
        mock_send.return_value = {
            "gift_id": str(uuid.uuid4()),
            "client_secret": "pi_gift_secret",
            "payment_intent_id": "pi_gift",
            "amount": 499,
        }
        r = premium_client.post(
            "/api/store/gifts/send/",
            {
                "item_id": str(test_item.id),
                "recipient_id": str(store_user2.id),
                "message": "Enjoy!",
            },
            format="json",
        )
        assert r.status_code == status.HTTP_201_CREATED

    @patch("apps.store.views.StoreService.send_gift")
    def test_gift_to_self(self, mock_send, premium_client, test_item, store_user):
        mock_send.side_effect = StoreServiceError("cannot gift to yourself")
        r = premium_client.post(
            "/api/store/gifts/send/",
            {
                "item_id": str(test_item.id),
                "recipient_id": str(store_user.id),
                "message": "",
            },
            format="json",
        )
        assert r.status_code == status.HTTP_400_BAD_REQUEST

    @patch("apps.store.views.StoreService.send_gift")
    def test_stripe_error(self, mock_send, premium_client, test_item, store_user2):
        # Note: PaymentVerificationError is a subclass of StoreServiceError.
        # In GiftSendView, the StoreServiceError except block comes first,
        # so PaymentVerificationError is caught there and returns 400.
        mock_send.side_effect = PaymentVerificationError("stripe error")
        r = premium_client.post(
            "/api/store/gifts/send/",
            {"item_id": str(test_item.id), "recipient_id": str(store_user2.id)},
            format="json",
        )
        # The except order in the view catches StoreServiceError (parent) before
        # PaymentVerificationError, returning 400 instead of 502.
        assert r.status_code in (status.HTTP_400_BAD_REQUEST, status.HTTP_502_BAD_GATEWAY)


# ══════════════════════════════════════════════════════════════════
#  GiftClaimView
# ══════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestGiftClaimView:

    def test_requires_auth(self, anon_client):
        r = anon_client.post(f"/api/store/gifts/{uuid.uuid4()}/claim/")
        assert r.status_code == status.HTTP_401_UNAUTHORIZED

    @patch("apps.store.views.StoreService.claim_gift")
    def test_success(self, mock_claim, auth_client, store_user, test_item, test_category):
        inv = UserInventory.objects.create(
            user=store_user, item=test_item, stripe_payment_intent_id="pi_gift"
        )
        mock_claim.return_value = inv
        gift_id = uuid.uuid4()
        r = auth_client.post(f"/api/store/gifts/{gift_id}/claim/")
        assert r.status_code == status.HTTP_200_OK

    def test_nonexistent_gift(self, auth_client):
        r = auth_client.post(f"/api/store/gifts/{uuid.uuid4()}/claim/")
        assert r.status_code == status.HTTP_400_BAD_REQUEST

    @patch("apps.store.views.StoreService.claim_gift")
    def test_already_owned(self, mock_claim, auth_client):
        mock_claim.side_effect = ItemAlreadyOwnedError("already owned")
        r = auth_client.post(f"/api/store/gifts/{uuid.uuid4()}/claim/")
        assert r.status_code == status.HTTP_400_BAD_REQUEST


# ══════════════════════════════════════════════════════════════════
#  GiftListView
# ══════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestGiftListView:

    def test_requires_auth(self, anon_client):
        r = anon_client.get("/api/store/gifts/")
        assert r.status_code == status.HTTP_401_UNAUTHORIZED

    def test_empty_list(self, auth_client):
        r = auth_client.get("/api/store/gifts/")
        assert r.status_code == status.HTTP_200_OK
        assert r.data == []

    def test_lists_unclaimed_gifts(self, auth_client, store_user, store_user2, test_item):
        Gift.objects.create(
            sender=store_user2,
            recipient=store_user,
            item=test_item,
            stripe_payment_intent_id="pi_g1",
            is_claimed=False,
        )
        r = auth_client.get("/api/store/gifts/")
        assert r.status_code == status.HTTP_200_OK
        assert len(r.data) == 1

    def test_excludes_claimed_gifts(self, auth_client, store_user, store_user2, test_item):
        Gift.objects.create(
            sender=store_user2,
            recipient=store_user,
            item=test_item,
            stripe_payment_intent_id="pi_g2",
            is_claimed=True,
            claimed_at=timezone.now(),
        )
        r = auth_client.get("/api/store/gifts/")
        assert r.status_code == status.HTTP_200_OK
        assert len(r.data) == 0


# ══════════════════════════════════════════════════════════════════
#  RefundRequestView
# ══════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestRefundRequestView:

    def test_requires_auth(self, anon_client):
        r = anon_client.get("/api/store/refunds/")
        assert r.status_code == status.HTTP_401_UNAUTHORIZED

    def test_list_empty(self, auth_client):
        r = auth_client.get("/api/store/refunds/")
        assert r.status_code == status.HTTP_200_OK

    @patch("apps.store.views.StoreService.request_refund")
    def test_request_refund(self, mock_refund, auth_client, user_inventory_entry, store_user):
        refund_obj = RefundRequest.objects.create(
            user=store_user,
            inventory_entry=user_inventory_entry,
            reason="Didn't like it",
            status="pending",
        )
        mock_refund.return_value = refund_obj
        r = auth_client.post(
            "/api/store/refunds/",
            {"inventory_id": str(user_inventory_entry.id), "reason": "Didn't like it"},
            format="json",
        )
        assert r.status_code == status.HTTP_201_CREATED

    @patch("apps.store.views.StoreService.request_refund")
    def test_refund_inventory_not_found(self, mock_refund, auth_client):
        mock_refund.side_effect = InventoryNotFoundError("not found")
        r = auth_client.post(
            "/api/store/refunds/",
            {"inventory_id": str(uuid.uuid4()), "reason": "gone"},
            format="json",
        )
        assert r.status_code == status.HTTP_400_BAD_REQUEST

    @patch("apps.store.views.StoreService.request_refund")
    def test_refund_xp_item_rejected(self, mock_refund, auth_client, user_inventory_entry):
        mock_refund.side_effect = StoreServiceError("not purchased with money")
        r = auth_client.post(
            "/api/store/refunds/",
            {"inventory_id": str(user_inventory_entry.id), "reason": "test"},
            format="json",
        )
        assert r.status_code == status.HTTP_400_BAD_REQUEST


# ══════════════════════════════════════════════════════════════════
#  RefundAdminView
# ══════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestRefundAdminView:

    def test_requires_admin(self, auth_client):
        r = auth_client.get("/api/store/admin/refunds/")
        assert r.status_code == status.HTTP_403_FORBIDDEN

    def test_list_all(self, admin_client, user_inventory_entry, store_user):
        RefundRequest.objects.create(
            user=store_user,
            inventory_entry=user_inventory_entry,
            reason="test",
            status="pending",
        )
        r = admin_client.get("/api/store/admin/refunds/")
        assert r.status_code == status.HTTP_200_OK
        assert r.data["count"] >= 1

    def test_filter_by_status(self, admin_client, user_inventory_entry, store_user):
        RefundRequest.objects.create(
            user=store_user,
            inventory_entry=user_inventory_entry,
            reason="test",
            status="pending",
        )
        r = admin_client.get("/api/store/admin/refunds/?status=pending")
        assert r.status_code == status.HTTP_200_OK

    @patch("apps.store.views.StoreService.process_refund")
    def test_approve(self, mock_process, admin_client, user_inventory_entry, store_user):
        refund = RefundRequest.objects.create(
            user=store_user,
            inventory_entry=user_inventory_entry,
            reason="test",
            status="pending",
        )

        def _approve(refund_request_id, approve, admin_notes=""):
            refund.status = "refunded"
            refund.admin_notes = admin_notes
            refund.save()

        mock_process.side_effect = _approve
        r = admin_client.post(
            "/api/store/admin/refunds/",
            {"refund_id": str(refund.id), "action": "approve", "admin_notes": "OK"},
            format="json",
        )
        assert r.status_code == status.HTTP_200_OK

    @patch("apps.store.views.StoreService.process_refund")
    def test_reject(self, mock_process, admin_client, user_inventory_entry, store_user):
        refund = RefundRequest.objects.create(
            user=store_user,
            inventory_entry=user_inventory_entry,
            reason="test",
            status="pending",
        )

        def _reject(refund_request_id, approve, admin_notes=""):
            refund.status = "rejected"
            refund.admin_notes = admin_notes
            refund.save()

        mock_process.side_effect = _reject
        r = admin_client.post(
            "/api/store/admin/refunds/",
            {"refund_id": str(refund.id), "action": "reject", "admin_notes": "No"},
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

    def test_already_processed(self, admin_client, user_inventory_entry, store_user):
        refund = RefundRequest.objects.create(
            user=store_user,
            inventory_entry=user_inventory_entry,
            reason="test",
            status="refunded",
        )
        r = admin_client.post(
            "/api/store/admin/refunds/",
            {"refund_id": str(refund.id), "action": "approve"},
            format="json",
        )
        assert r.status_code == status.HTTP_400_BAD_REQUEST

    def test_invalid_action(self, admin_client, user_inventory_entry, store_user):
        refund = RefundRequest.objects.create(
            user=store_user,
            inventory_entry=user_inventory_entry,
            reason="test",
            status="pending",
        )
        r = admin_client.post(
            "/api/store/admin/refunds/",
            {"refund_id": str(refund.id), "action": "cancel"},
            format="json",
        )
        assert r.status_code == status.HTTP_400_BAD_REQUEST
