"""
Tests for apps/store/serializers.py

Covers: all store serializers — StoreItemSerializer, StoreItemDetailSerializer,
StoreCategorySerializer, StoreCategoryDetailSerializer, UserInventorySerializer,
PurchaseSerializer, PurchaseConfirmSerializer, EquipSerializer, WishlistSerializer,
XPPurchaseSerializer, GiftSendSerializer, GiftSerializer, RefundRequestSerializer,
RefundRequestDisplaySerializer, ItemPreviewSerializer, RefundProcessSerializer.
"""

import uuid
from decimal import Decimal

import pytest
from django.test import RequestFactory
from rest_framework.request import Request

from apps.store.models import (
    Gift,
    RefundRequest,
    StoreCategory,
    StoreItem,
    UserInventory,
    Wishlist,
)
from apps.store.serializers import (
    EquipSerializer,
    GiftSendSerializer,
    GiftSerializer,
    ItemPreviewSerializer,
    PurchaseConfirmSerializer,
    PurchaseSerializer,
    RefundProcessSerializer,
    RefundRequestDisplaySerializer,
    RefundRequestSerializer,
    StoreCategoryDetailSerializer,
    StoreCategorySerializer,
    StoreItemDetailSerializer,
    StoreItemSerializer,
    UserInventorySerializer,
    WishlistSerializer,
    XPPurchaseSerializer,
)
from apps.users.models import User


# ── helpers ──────────────────────────────────────────────────────

def _drf_request(user=None):
    """Build a minimal DRF Request with optional user."""
    factory = RequestFactory()
    django_request = factory.get("/")
    drf_request = Request(django_request)
    if user:
        drf_request.user = user
    return drf_request


@pytest.fixture
def inactive_item(test_category):
    return StoreItem.objects.create(
        category=test_category,
        name="Dead Item",
        slug="dead-item",
        price=Decimal("1.00"),
        item_type="badge_frame",
        rarity="common",
        is_active=False,
    )


@pytest.fixture
def xp_item(test_category):
    return StoreItem.objects.create(
        category=test_category,
        name="XP Bubble",
        slug="xp-bubble",
        price=Decimal("0.00"),
        xp_price=300,
        item_type="chat_bubble",
        rarity="common",
        is_active=True,
    )


# ══════════════════════════════════════════════════════════════════
#  StoreItemSerializer
# ══════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestStoreItemSerializer:

    def test_serializes_item(self, test_item):
        data = StoreItemSerializer(test_item).data
        assert data["name"] == "Gold Frame"
        assert data["rarity"] == "rare"
        assert data["rarity_display"] == "Rare"
        assert data["item_type_display"] == "Badge Frame"
        assert data["category_name"] == "Badge Frames"

    def test_read_only_fields(self, test_item):
        data = StoreItemSerializer(test_item).data
        assert "id" in data
        assert "created_at" in data


# ══════════════════════════════════════════════════════════════════
#  StoreItemDetailSerializer
# ══════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestStoreItemDetailSerializer:

    def test_owners_count_zero(self, test_item):
        data = StoreItemDetailSerializer(test_item, context={"request": _drf_request()}).data
        assert data["owners_count"] == 0

    def test_owners_count_with_owner(self, test_item, user_inventory_entry):
        data = StoreItemDetailSerializer(test_item, context={"request": _drf_request()}).data
        assert data["owners_count"] == 1

    def test_is_owned_true(self, store_user, test_item, user_inventory_entry):
        request = _drf_request(user=store_user)
        data = StoreItemDetailSerializer(test_item, context={"request": request}).data
        assert data["is_owned"] is True

    def test_is_owned_false(self, store_user2, test_item):
        request = _drf_request(user=store_user2)
        data = StoreItemDetailSerializer(test_item, context={"request": request}).data
        assert data["is_owned"] is False

    def test_is_owned_anonymous(self, test_item):
        data = StoreItemDetailSerializer(test_item, context={"request": _drf_request()}).data
        assert data["is_owned"] is False


# ══════════════════════════════════════════════════════════════════
#  StoreCategorySerializer / StoreCategoryDetailSerializer
# ══════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestStoreCategorySerializers:

    def test_basic_serialization(self, test_category):
        data = StoreCategorySerializer(test_category).data
        assert data["name"] == "Badge Frames"
        assert data["slug"] == "badge-frames"

    def test_items_count(self, test_category, test_item):
        data = StoreCategorySerializer(test_category).data
        assert data["items_count"] == 1

    def test_items_count_excludes_inactive(self, test_category, test_item, inactive_item):
        # inactive_item is in test_category too
        data = StoreCategorySerializer(test_category).data
        assert data["items_count"] == 1  # only the active one

    def test_detail_includes_items(self, test_category, test_item):
        data = StoreCategoryDetailSerializer(
            test_category, context={"request": _drf_request()}
        ).data
        assert "items" in data
        assert len(data["items"]) == 1
        assert data["items"][0]["name"] == "Gold Frame"

    def test_detail_excludes_inactive_items(self, test_category, test_item, inactive_item):
        data = StoreCategoryDetailSerializer(
            test_category, context={"request": _drf_request()}
        ).data
        names = [i["name"] for i in data["items"]]
        assert "Dead Item" not in names


# ══════════════════════════════════════════════════════════════════
#  UserInventorySerializer
# ══════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestUserInventorySerializer:

    def test_serialization(self, user_inventory_entry):
        data = UserInventorySerializer(
            user_inventory_entry, context={"request": _drf_request()}
        ).data
        assert data["is_equipped"] is False
        assert "item" in data
        assert data["item"]["name"] == "Gold Frame"
        assert "item_id" in data


# ══════════════════════════════════════════════════════════════════
#  PurchaseSerializer
# ══════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestPurchaseSerializer:

    def test_valid(self, test_item, store_user):
        ser = PurchaseSerializer(
            data={"item_id": str(test_item.id)},
            context={"request": _drf_request(user=store_user)},
        )
        assert ser.is_valid(), ser.errors

    def test_nonexistent_item(self, store_user):
        ser = PurchaseSerializer(
            data={"item_id": str(uuid.uuid4())},
            context={"request": _drf_request(user=store_user)},
        )
        assert not ser.is_valid()

    def test_inactive_item(self, inactive_item, store_user):
        ser = PurchaseSerializer(
            data={"item_id": str(inactive_item.id)},
            context={"request": _drf_request(user=store_user)},
        )
        assert not ser.is_valid()

    def test_already_owned(self, test_item, store_user, user_inventory_entry):
        ser = PurchaseSerializer(
            data={"item_id": str(test_item.id)},
            context={"request": _drf_request(user=store_user)},
        )
        assert not ser.is_valid()


# ══════════════════════════════════════════════════════════════════
#  PurchaseConfirmSerializer
# ══════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestPurchaseConfirmSerializer:

    def test_valid(self, test_item):
        ser = PurchaseConfirmSerializer(data={
            "item_id": str(test_item.id),
            "payment_intent_id": "pi_test_xyz",
        })
        assert ser.is_valid(), ser.errors

    def test_invalid_pi_format(self, test_item):
        ser = PurchaseConfirmSerializer(data={
            "item_id": str(test_item.id),
            "payment_intent_id": "bad_format",
        })
        assert not ser.is_valid()
        assert "payment_intent_id" in ser.errors

    def test_nonexistent_item(self):
        ser = PurchaseConfirmSerializer(data={
            "item_id": str(uuid.uuid4()),
            "payment_intent_id": "pi_test_xyz",
        })
        assert not ser.is_valid()


# ══════════════════════════════════════════════════════════════════
#  EquipSerializer
# ══════════════════════════════════════════════════════════════════


class TestEquipSerializer:

    def test_valid_equip(self):
        ser = EquipSerializer(data={"equip": True})
        assert ser.is_valid()
        assert ser.validated_data["equip"] is True

    def test_valid_unequip(self):
        ser = EquipSerializer(data={"equip": False})
        assert ser.is_valid()
        assert ser.validated_data["equip"] is False

    def test_missing_field(self):
        ser = EquipSerializer(data={})
        assert not ser.is_valid()


# ══════════════════════════════════════════════════════════════════
#  WishlistSerializer
# ══════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestWishlistSerializer:

    def test_valid(self, test_item, store_user):
        ser = WishlistSerializer(
            data={"item_id": str(test_item.id)},
            context={"request": _drf_request(user=store_user)},
        )
        assert ser.is_valid(), ser.errors

    def test_nonexistent_item(self, store_user):
        ser = WishlistSerializer(
            data={"item_id": str(uuid.uuid4())},
            context={"request": _drf_request(user=store_user)},
        )
        assert not ser.is_valid()

    def test_inactive_item(self, inactive_item, store_user):
        ser = WishlistSerializer(
            data={"item_id": str(inactive_item.id)},
            context={"request": _drf_request(user=store_user)},
        )
        assert not ser.is_valid()

    def test_duplicate(self, test_item, store_user):
        Wishlist.objects.create(user=store_user, item=test_item)
        ser = WishlistSerializer(
            data={"item_id": str(test_item.id)},
            context={"request": _drf_request(user=store_user)},
        )
        assert not ser.is_valid()

    def test_serializes_existing(self, store_user, test_item):
        wl = Wishlist.objects.create(user=store_user, item=test_item)
        data = WishlistSerializer(wl, context={"request": _drf_request()}).data
        assert data["item"]["name"] == "Gold Frame"


# ══════════════════════════════════════════════════════════════════
#  XPPurchaseSerializer
# ══════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestXPPurchaseSerializer:

    def test_valid(self, xp_item):
        ser = XPPurchaseSerializer(data={"item_id": str(xp_item.id)})
        assert ser.is_valid(), ser.errors

    def test_nonexistent(self):
        ser = XPPurchaseSerializer(data={"item_id": str(uuid.uuid4())})
        assert not ser.is_valid()

    def test_inactive(self, inactive_item):
        ser = XPPurchaseSerializer(data={"item_id": str(inactive_item.id)})
        assert not ser.is_valid()

    def test_zero_xp_price(self, test_item):
        """test_item has xp_price=0."""
        ser = XPPurchaseSerializer(data={"item_id": str(test_item.id)})
        assert not ser.is_valid()


# ══════════════════════════════════════════════════════════════════
#  GiftSendSerializer
# ══════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestGiftSendSerializer:

    def test_valid(self, test_item, store_user2):
        ser = GiftSendSerializer(data={
            "item_id": str(test_item.id),
            "recipient_id": str(store_user2.id),
            "message": "Enjoy!",
        })
        assert ser.is_valid(), ser.errors

    def test_without_message(self, test_item, store_user2):
        ser = GiftSendSerializer(data={
            "item_id": str(test_item.id),
            "recipient_id": str(store_user2.id),
        })
        assert ser.is_valid()

    def test_sanitizes_message(self, test_item, store_user2):
        ser = GiftSendSerializer(data={
            "item_id": str(test_item.id),
            "recipient_id": str(store_user2.id),
            "message": "<script>alert(1)</script>Hi",
        })
        assert ser.is_valid()
        assert "<script>" not in ser.validated_data["message"]


# ══════════════════════════════════════════════════════════════════
#  GiftSerializer (read-only display)
# ══════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestGiftSerializer:

    def test_serializes_gift(self, store_user, store_user2, test_item):
        gift = Gift.objects.create(
            sender=store_user,
            recipient=store_user2,
            item=test_item,
            message="Hey!",
            stripe_payment_intent_id="pi_g_test",
        )
        data = GiftSerializer(gift).data
        assert data["is_claimed"] is False
        assert "item" in data
        assert data["sender_name"] == store_user.display_name
        assert data["recipient_name"] == store_user2.display_name


# ══════════════════════════════════════════════════════════════════
#  RefundRequestSerializer
# ══════════════════════════════════════════════════════════════════


class TestRefundRequestSerializer:

    def test_valid(self):
        ser = RefundRequestSerializer(data={
            "inventory_id": str(uuid.uuid4()),
            "reason": "I changed my mind",
        })
        assert ser.is_valid(), ser.errors

    def test_sanitizes_reason(self):
        ser = RefundRequestSerializer(data={
            "inventory_id": str(uuid.uuid4()),
            "reason": "<img onerror=alert(1)>Bad",
        })
        assert ser.is_valid()
        assert "<img" not in ser.validated_data["reason"]

    def test_missing_reason(self):
        ser = RefundRequestSerializer(data={
            "inventory_id": str(uuid.uuid4()),
        })
        assert not ser.is_valid()


# ══════════════════════════════════════════════════════════════════
#  RefundRequestDisplaySerializer
# ══════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestRefundRequestDisplaySerializer:

    def test_serialization(self, store_user, user_inventory_entry):
        rr = RefundRequest.objects.create(
            user=store_user,
            inventory_entry=user_inventory_entry,
            reason="Test",
            status="pending",
        )
        data = RefundRequestDisplaySerializer(rr).data
        assert data["status"] == "pending"
        assert data["item_name"] == "Gold Frame"


# ══════════════════════════════════════════════════════════════════
#  ItemPreviewSerializer
# ══════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestItemPreviewSerializer:

    def test_serialization(self, test_category, store_user):
        item = StoreItem.objects.create(
            category=test_category,
            name="Preview Theme",
            slug="preview-theme",
            price=Decimal("4.99"),
            item_type="theme_skin",
            rarity="epic",
            is_active=True,
            preview_type="theme",
            preview_data={"accent": "#FFF"},
        )
        request = _drf_request(user=store_user)
        data = ItemPreviewSerializer(item, context={"request": request}).data
        assert data["preview_type"] == "theme"
        assert data["preview_data"]["accent"] == "#FFF"
        assert data["is_owned"] is False

    def test_is_owned_true(self, store_user, test_item, user_inventory_entry):
        request = _drf_request(user=store_user)
        data = ItemPreviewSerializer(test_item, context={"request": request}).data
        assert data["is_owned"] is True


# ══════════════════════════════════════════════════════════════════
#  RefundProcessSerializer
# ══════════════════════════════════════════════════════════════════


class TestRefundProcessSerializer:

    def test_approve(self):
        ser = RefundProcessSerializer(data={
            "refund_id": str(uuid.uuid4()),
            "action": "approve",
        })
        assert ser.is_valid(), ser.errors

    def test_reject(self):
        ser = RefundProcessSerializer(data={
            "refund_id": str(uuid.uuid4()),
            "action": "reject",
            "admin_notes": "Not eligible",
        })
        assert ser.is_valid(), ser.errors

    def test_invalid_action(self):
        ser = RefundProcessSerializer(data={
            "refund_id": str(uuid.uuid4()),
            "action": "cancel",
        })
        assert not ser.is_valid()
        assert "action" in ser.errors

    def test_missing_refund_id(self):
        ser = RefundProcessSerializer(data={"action": "approve"})
        assert not ser.is_valid()
