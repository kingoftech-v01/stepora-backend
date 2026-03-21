"""
Tests for apps/store/services.py

Covers: StoreService — payment intents, purchase confirmation, XP purchases,
inventory management (equip/unequip), gift send/claim, refund request/process.
All Stripe calls are mocked.
"""

import uuid
from decimal import Decimal
from unittest.mock import MagicMock, PropertyMock, patch

import pytest
from django.utils import timezone

from apps.store.models import (
    Gift,
    RefundRequest,
    StoreCategory,
    StoreItem,
    UserInventory,
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
from apps.users.models import User


# ── fixtures ────────────────────────────────────────────────────


@pytest.fixture
def user_with_xp(store_user):
    """Give the user enough XP for purchases."""
    store_user.xp = 1000
    store_user.save(update_fields=["xp"])
    return store_user


@pytest.fixture
def xp_item(test_category):
    return StoreItem.objects.create(
        category=test_category,
        name="XP Widget",
        slug="xp-widget",
        price=Decimal("0.00"),
        xp_price=500,
        item_type="badge_frame",
        rarity="common",
        is_active=True,
    )


@pytest.fixture
def inactive_item(test_category):
    return StoreItem.objects.create(
        category=test_category,
        name="Disabled Item",
        slug="disabled-item",
        price=Decimal("1.99"),
        item_type="badge_frame",
        rarity="common",
        is_active=False,
    )


# ══════════════════════════════════════════════════════════════════
#  create_payment_intent
# ══════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestCreatePaymentIntent:

    @patch("apps.store.services.stripe.PaymentIntent.create")
    def test_success(self, mock_stripe, store_user, test_item):
        mock_stripe.return_value = MagicMock(
            id="pi_test_001",
            client_secret="pi_test_secret",
        )
        result = StoreService.create_payment_intent(store_user, test_item)
        assert result["payment_intent_id"] == "pi_test_001"
        assert result["client_secret"] == "pi_test_secret"
        assert result["amount"] == int(test_item.price * 100)
        mock_stripe.assert_called_once()

    def test_inactive_item(self, store_user, inactive_item):
        with pytest.raises(ItemNotActiveError):
            StoreService.create_payment_intent(store_user, inactive_item)

    def test_already_owned(self, store_user, test_item, user_inventory_entry):
        with pytest.raises(ItemAlreadyOwnedError):
            StoreService.create_payment_intent(store_user, test_item)

    @patch("apps.store.services.stripe.PaymentIntent.create")
    def test_stripe_error(self, mock_stripe, store_user, test_item):
        import stripe
        mock_stripe.side_effect = stripe.error.StripeError("boom")
        with pytest.raises(PaymentVerificationError, match="Payment processing failed"):
            StoreService.create_payment_intent(store_user, test_item)


# ══════════════════════════════════════════════════════════════════
#  confirm_purchase
# ══════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestConfirmPurchase:

    def _mock_payment_intent(self, item, user, pi_status="succeeded"):
        """Build a mock PaymentIntent dict-like object."""
        amount = int(item.price * 100)
        pi = MagicMock()
        pi.status = pi_status
        pi.amount = amount
        pi.get.return_value = {
            "user_id": str(user.id),
            "item_id": str(item.id),
        }
        return pi

    @patch("apps.store.services.stripe.PaymentIntent.retrieve")
    def test_success(self, mock_retrieve, store_user, test_item):
        mock_retrieve.return_value = self._mock_payment_intent(test_item, store_user)
        inv = StoreService.confirm_purchase(store_user, test_item, "pi_ok")
        assert inv.user == store_user
        assert inv.item == test_item
        assert inv.stripe_payment_intent_id == "pi_ok"

    @patch("apps.store.services.stripe.PaymentIntent.retrieve")
    def test_already_owned(self, mock_retrieve, store_user, test_item, user_inventory_entry):
        with pytest.raises(ItemAlreadyOwnedError):
            StoreService.confirm_purchase(store_user, test_item, "pi_dup")

    @patch("apps.store.services.stripe.PaymentIntent.retrieve")
    def test_payment_not_succeeded(self, mock_retrieve, store_user, test_item):
        mock_retrieve.return_value = self._mock_payment_intent(
            test_item, store_user, pi_status="requires_payment_method"
        )
        with pytest.raises(PaymentVerificationError, match="not been completed"):
            StoreService.confirm_purchase(store_user, test_item, "pi_pending")

    @patch("apps.store.services.stripe.PaymentIntent.retrieve")
    def test_amount_mismatch(self, mock_retrieve, store_user, test_item):
        pi = self._mock_payment_intent(test_item, store_user)
        pi.amount = 1  # wrong amount
        mock_retrieve.return_value = pi
        with pytest.raises(PaymentVerificationError, match="amount does not match"):
            StoreService.confirm_purchase(store_user, test_item, "pi_wrong_amount")

    @patch("apps.store.services.stripe.PaymentIntent.retrieve")
    def test_user_mismatch(self, mock_retrieve, store_user, store_user2, test_item):
        pi = self._mock_payment_intent(test_item, store_user2)  # different user in metadata
        mock_retrieve.return_value = pi
        with pytest.raises(PaymentVerificationError, match="user mismatch"):
            StoreService.confirm_purchase(store_user, test_item, "pi_wrong_user")

    @patch("apps.store.services.stripe.PaymentIntent.retrieve")
    def test_stripe_retrieve_error(self, mock_retrieve, store_user, test_item):
        import stripe
        mock_retrieve.side_effect = stripe.error.StripeError("retrieval failed")
        with pytest.raises(PaymentVerificationError, match="Unable to verify"):
            StoreService.confirm_purchase(store_user, test_item, "pi_stripe_err")


# ══════════════════════════════════════════════════════════════════
#  get_user_inventory
# ══════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestGetUserInventory:

    def test_returns_queryset(self, store_user, user_inventory_entry):
        qs = StoreService.get_user_inventory(store_user)
        assert user_inventory_entry in qs

    def test_empty_for_new_user(self, store_user2):
        qs = StoreService.get_user_inventory(store_user2)
        assert qs.count() == 0


# ══════════════════════════════════════════════════════════════════
#  equip_item / unequip_item
# ══════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestEquipUnequip:

    def test_equip(self, store_user, user_inventory_entry):
        result = StoreService.equip_item(store_user, user_inventory_entry.id)
        assert result.is_equipped is True

    def test_equip_unequips_same_type(self, store_user, test_category):
        """Equipping a badge_frame unequips any previously equipped badge_frame."""
        item_a = StoreItem.objects.create(
            category=test_category,
            name="Frame A",
            slug="frame-a",
            price=Decimal("1.99"),
            item_type="badge_frame",
            is_active=True,
        )
        item_b = StoreItem.objects.create(
            category=test_category,
            name="Frame B",
            slug="frame-b",
            price=Decimal("2.99"),
            item_type="badge_frame",
            is_active=True,
        )
        inv_a = UserInventory.objects.create(user=store_user, item=item_a, is_equipped=True)
        inv_b = UserInventory.objects.create(user=store_user, item=item_b, is_equipped=False)

        StoreService.equip_item(store_user, inv_b.id)
        inv_a.refresh_from_db()
        inv_b.refresh_from_db()
        assert inv_a.is_equipped is False
        assert inv_b.is_equipped is True

    def test_equip_nonexistent(self, store_user):
        with pytest.raises(InventoryNotFoundError):
            StoreService.equip_item(store_user, uuid.uuid4())

    def test_equip_other_users_item(self, store_user2, user_inventory_entry):
        """Cannot equip items belonging to another user."""
        with pytest.raises(InventoryNotFoundError):
            StoreService.equip_item(store_user2, user_inventory_entry.id)

    def test_unequip(self, store_user, user_inventory_entry):
        user_inventory_entry.is_equipped = True
        user_inventory_entry.save()
        result = StoreService.unequip_item(store_user, user_inventory_entry.id)
        assert result.is_equipped is False

    def test_unequip_nonexistent(self, store_user):
        with pytest.raises(InventoryNotFoundError):
            StoreService.unequip_item(store_user, uuid.uuid4())


# ══════════════════════════════════════════════════════════════════
#  purchase_with_xp
# ══════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestPurchaseWithXP:

    def test_success(self, user_with_xp, xp_item):
        inv = StoreService.purchase_with_xp(user_with_xp, xp_item)
        assert inv.user == user_with_xp
        assert inv.item == xp_item
        user_with_xp.refresh_from_db()
        assert user_with_xp.xp == 500  # 1000 - 500

    def test_insufficient_xp(self, store_user, xp_item):
        """store_user has xp=0 by default."""
        with pytest.raises(InsufficientXPError, match="Insufficient XP"):
            StoreService.purchase_with_xp(store_user, xp_item)

    def test_inactive_item(self, user_with_xp, inactive_item):
        with pytest.raises(ItemNotActiveError):
            StoreService.purchase_with_xp(user_with_xp, inactive_item)

    def test_already_owned(self, user_with_xp, xp_item):
        UserInventory.objects.create(user=user_with_xp, item=xp_item)
        with pytest.raises(ItemAlreadyOwnedError):
            StoreService.purchase_with_xp(user_with_xp, xp_item)

    def test_zero_xp_price(self, user_with_xp, test_item):
        """test_item has xp_price=0 so cannot be purchased with XP."""
        with pytest.raises(ItemNotActiveError, match="cannot be purchased with XP"):
            StoreService.purchase_with_xp(user_with_xp, test_item)


# ══════════════════════════════════════════════════════════════════
#  send_gift
# ══════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestSendGift:

    @patch("apps.store.services.stripe.PaymentIntent.create")
    def test_success(self, mock_stripe, store_user, store_user2, test_item):
        mock_stripe.return_value = MagicMock(
            id="pi_gift_001",
            client_secret="pi_gift_secret",
        )
        result = StoreService.send_gift(store_user, store_user2, test_item, message="Hi!")
        assert "gift_id" in result
        assert result["client_secret"] == "pi_gift_secret"
        gift = Gift.objects.get(id=result["gift_id"])
        assert gift.sender == store_user
        assert gift.recipient == store_user2

    def test_inactive_item(self, store_user, store_user2, inactive_item):
        with pytest.raises(ItemNotActiveError):
            StoreService.send_gift(store_user, store_user2, inactive_item)

    def test_self_gift(self, store_user, test_item):
        with pytest.raises(StoreServiceError, match="cannot gift"):
            StoreService.send_gift(store_user, store_user, test_item)

    def test_recipient_already_owns(self, store_user, store_user2, test_item):
        UserInventory.objects.create(user=store_user2, item=test_item)
        with pytest.raises(ItemAlreadyOwnedError):
            StoreService.send_gift(store_user, store_user2, test_item)

    @patch("apps.store.services.stripe.PaymentIntent.create")
    def test_stripe_error(self, mock_stripe, store_user, store_user2, test_item):
        import stripe
        mock_stripe.side_effect = stripe.error.StripeError("stripe down")
        with pytest.raises(PaymentVerificationError, match="Payment failed"):
            StoreService.send_gift(store_user, store_user2, test_item)


# ══════════════════════════════════════════════════════════════════
#  claim_gift
# ══════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestClaimGift:

    def test_success(self, store_user, store_user2, test_item):
        gift = Gift.objects.create(
            sender=store_user,
            recipient=store_user2,
            item=test_item,
            stripe_payment_intent_id="pi_gift_claim",
            is_claimed=False,
        )
        inv = StoreService.claim_gift(store_user2, gift.id)
        assert inv.user == store_user2
        assert inv.item == test_item
        gift.refresh_from_db()
        assert gift.is_claimed is True
        assert gift.claimed_at is not None

    def test_nonexistent_gift(self, store_user):
        with pytest.raises(ItemNotFoundError, match="not found"):
            StoreService.claim_gift(store_user, uuid.uuid4())

    def test_already_claimed(self, store_user, store_user2, test_item):
        gift = Gift.objects.create(
            sender=store_user,
            recipient=store_user2,
            item=test_item,
            stripe_payment_intent_id="pi_g",
            is_claimed=True,
            claimed_at=timezone.now(),
        )
        with pytest.raises(ItemNotFoundError):
            StoreService.claim_gift(store_user2, gift.id)

    def test_claim_when_already_owns_item(self, store_user, store_user2, test_item):
        gift = Gift.objects.create(
            sender=store_user,
            recipient=store_user2,
            item=test_item,
            stripe_payment_intent_id="pi_gc",
            is_claimed=False,
        )
        UserInventory.objects.create(user=store_user2, item=test_item)
        with pytest.raises(ItemAlreadyOwnedError):
            StoreService.claim_gift(store_user2, gift.id)

    def test_wrong_recipient(self, store_user, store_user2, test_item):
        gift = Gift.objects.create(
            sender=store_user2,
            recipient=store_user2,
            item=test_item,
            stripe_payment_intent_id="pi_gw",
            is_claimed=False,
        )
        # store_user is NOT the recipient
        with pytest.raises(ItemNotFoundError):
            StoreService.claim_gift(store_user, gift.id)


# ══════════════════════════════════════════════════════════════════
#  request_refund
# ══════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestRequestRefund:

    def test_success(self, store_user, user_inventory_entry):
        rr = StoreService.request_refund(store_user, user_inventory_entry.id, "Didn't like it")
        assert rr.status == "pending"
        assert rr.user == store_user

    def test_inventory_not_found(self, store_user):
        with pytest.raises(InventoryNotFoundError):
            StoreService.request_refund(store_user, uuid.uuid4(), "reason")

    def test_xp_purchase_cannot_refund(self, store_user, xp_item):
        inv = UserInventory.objects.create(
            user=store_user, item=xp_item, stripe_payment_intent_id=""
        )
        with pytest.raises(StoreServiceError, match="not purchased with money"):
            StoreService.request_refund(store_user, inv.id, "want refund")

    def test_duplicate_pending_refund(self, store_user, user_inventory_entry):
        StoreService.request_refund(store_user, user_inventory_entry.id, "first")
        with pytest.raises(StoreServiceError, match="already pending"):
            StoreService.request_refund(store_user, user_inventory_entry.id, "second")


# ══════════════════════════════════════════════════════════════════
#  process_refund
# ══════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestProcessRefund:

    @patch("apps.store.services.stripe.Refund.create")
    @patch.object(UserInventory, "delete")
    def test_approve(self, mock_inv_delete, mock_refund, store_user, user_inventory_entry):
        mock_refund.return_value = MagicMock(id="re_123")
        rr = RefundRequest.objects.create(
            user=store_user,
            inventory_entry=user_inventory_entry,
            reason="test",
            status="pending",
        )
        result = StoreService.process_refund(rr.id, approve=True, admin_notes="OK")
        assert result.status == "refunded"
        assert result.stripe_refund_id == "re_123"
        assert result.admin_notes == "OK"
        mock_inv_delete.assert_called_once()
        mock_refund.assert_called_once_with(payment_intent=user_inventory_entry.stripe_payment_intent_id)

    def test_reject(self, store_user, user_inventory_entry):
        rr = RefundRequest.objects.create(
            user=store_user,
            inventory_entry=user_inventory_entry,
            reason="test",
            status="pending",
        )
        result = StoreService.process_refund(rr.id, approve=False, admin_notes="No")
        assert result.status == "rejected"
        assert result.admin_notes == "No"
        # Inventory should still exist
        assert UserInventory.objects.filter(id=user_inventory_entry.id).exists()

    def test_already_processed(self, store_user, user_inventory_entry):
        rr = RefundRequest.objects.create(
            user=store_user,
            inventory_entry=user_inventory_entry,
            reason="test",
            status="refunded",
        )
        with pytest.raises(ItemNotFoundError, match="already processed"):
            StoreService.process_refund(rr.id, approve=True)

    @patch("apps.store.services.stripe.Refund.create")
    def test_stripe_refund_error(self, mock_refund, store_user, user_inventory_entry):
        import stripe
        mock_refund.side_effect = stripe.error.StripeError("refund failed")
        rr = RefundRequest.objects.create(
            user=store_user,
            inventory_entry=user_inventory_entry,
            reason="test",
            status="pending",
        )
        with pytest.raises(PaymentVerificationError, match="Stripe refund failed"):
            StoreService.process_refund(rr.id, approve=True)
