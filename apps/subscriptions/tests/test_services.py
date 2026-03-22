"""
Comprehensive tests for apps/subscriptions/services.py.

Covers: Checkout session creation, subscription status sync, plan change
(upgrade/downgrade), cancel subscription, reactivate subscription,
webhook handling, promotion application, StripeCustomer creation/lookup.

All Stripe API calls are mocked.
"""

import uuid
from datetime import timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
import stripe
from django.utils import timezone

from apps.subscriptions.models import (
    Promotion,
    PromotionPlanDiscount,
    PromotionRedemption,
    StripeCustomer,
    StripeWebhookEvent,
    Subscription,
    SubscriptionPlan,
)
from apps.subscriptions.services import (
    PromotionService,
    StripeService,
    _revoke_downgraded_features,
    _sync_user_subscription,
    _timestamp_to_datetime,
)
from apps.users.models import User

# ─── Fixtures ───────────────────────────────────────────────────


@pytest.fixture
def user(db):
    return User.objects.create_user(
        email="svctest@test.com",
        password="testpass123",
        display_name="Service Test",
    )


@pytest.fixture
def user2(db):
    return User.objects.create_user(
        email="svctest2@test.com",
        password="testpass123",
        display_name="Service Test 2",
    )


@pytest.fixture
def free_plan(db):
    plan, _ = SubscriptionPlan.objects.update_or_create(
        slug="free",
        defaults={
            "name": "Free",
            "price_monthly": Decimal("0.00"),
            "dream_limit": 3,
        },
    )
    return plan


@pytest.fixture
def premium_plan(db):
    plan, _ = SubscriptionPlan.objects.update_or_create(
        slug="premium",
        defaults={
            "name": "Premium",
            "price_monthly": Decimal("19.99"),
            "stripe_price_id": "price_test_premium",
            "dream_limit": 10,
            "has_ai": True,
            "has_buddy": True,
        },
    )
    return plan


@pytest.fixture
def pro_plan(db):
    plan, _ = SubscriptionPlan.objects.update_or_create(
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
def stripe_customer(user):
    return StripeCustomer.objects.create(
        user=user,
        stripe_customer_id="cus_test_abc123",
    )


@pytest.fixture
def free_subscription(user, free_plan):
    sub, _ = Subscription.objects.update_or_create(
        user=user,
        defaults={
            "plan": free_plan,
            "status": "active",
        },
    )
    return sub


@pytest.fixture
def premium_subscription(user, premium_plan, stripe_customer):
    sub, _ = Subscription.objects.update_or_create(
        user=user,
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
def pro_subscription(user, pro_plan, stripe_customer):
    sub, _ = Subscription.objects.update_or_create(
        user=user,
        defaults={
            "plan": pro_plan,
            "status": "active",
            "stripe_subscription_id": "sub_test_pro",
            "current_period_start": timezone.now(),
            "current_period_end": timezone.now() + timedelta(days=30),
        },
    )
    return sub


@pytest.fixture
def admin_premium_subscription(user, premium_plan):
    """Admin-assigned subscription (no Stripe backing)."""
    sub, _ = Subscription.objects.update_or_create(
        user=user,
        defaults={
            "plan": premium_plan,
            "status": "active",
            "stripe_subscription_id": "",
            "current_period_start": timezone.now(),
            "current_period_end": timezone.now() + timedelta(days=30),
        },
    )
    return sub


@pytest.fixture
def active_promotion(db, premium_plan):
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


# ═══════════════════════════════════════════════════════════════════
# StripeCustomer Creation / Lookup
# ═══════════════════════════════════════════════════════════════════


class TestStripeCustomerCreation:
    """Tests for StripeService.create_customer."""

    @patch("apps.subscriptions.services.stripe.Customer.create")
    def test_create_new_customer(self, mock_create, user):
        mock_create.return_value = MagicMock(id="cus_new_123")
        result = StripeService.create_customer(user)
        assert result.stripe_customer_id == "cus_new_123"
        assert result.user == user
        mock_create.assert_called_once()

    @patch("apps.subscriptions.services.stripe.Customer.retrieve")
    def test_returns_existing_customer(self, mock_retrieve, user, stripe_customer):
        mock_retrieve.return_value = MagicMock(id="cus_test_abc123")
        result = StripeService.create_customer(user)
        assert result.id == stripe_customer.id
        mock_retrieve.assert_called_once_with("cus_test_abc123")

    @patch("apps.subscriptions.services.stripe.Customer.create")
    @patch("apps.subscriptions.services.stripe.Customer.retrieve")
    def test_recreates_if_stripe_customer_not_found(
        self, mock_retrieve, mock_create, user, stripe_customer
    ):
        mock_retrieve.side_effect = stripe.error.InvalidRequestError(
            "No such customer", param="id"
        )
        mock_create.return_value = MagicMock(id="cus_recreated")
        result = StripeService.create_customer(user)
        assert result.stripe_customer_id == "cus_recreated"


# ═══════════════════════════════════════════════════════════════════
# Checkout Session Creation
# ═══════════════════════════════════════════════════════════════════


class TestCheckoutSessionCreation:
    """Tests for StripeService.create_checkout_session."""

    @patch("apps.subscriptions.services.stripe.checkout.Session.create")
    @patch("apps.subscriptions.services.StripeService.create_customer")
    def test_create_checkout_session(
        self, mock_create_cust, mock_session, user, premium_plan, stripe_customer
    ):
        mock_create_cust.return_value = stripe_customer
        mock_session.return_value = MagicMock(id="cs_test_123", url="https://checkout.stripe.com/pay")
        session = StripeService.create_checkout_session(user, premium_plan)
        assert session.id == "cs_test_123"
        mock_session.assert_called_once()

    def test_checkout_free_plan_raises(self, user, free_plan):
        with pytest.raises(ValueError, match="Cannot create a checkout session for the free plan"):
            StripeService.create_checkout_session(user, free_plan)

    @patch("apps.subscriptions.services.stripe.checkout.Session.create")
    @patch("apps.subscriptions.services.StripeService.create_customer")
    @patch("apps.subscriptions.services.PromotionService.create_stripe_price_for_plan")
    def test_checkout_auto_creates_price(
        self, mock_price, mock_create_cust, mock_session, user, stripe_customer
    ):
        """If plan has no stripe_price_id, auto-create it."""
        plan = SubscriptionPlan.objects.create(
            name="NoPricePlan",
            slug="noprice",
            price_monthly=Decimal("9.99"),
            stripe_price_id="",
            dream_limit=5,
        )
        mock_price.return_value = "price_auto_123"
        mock_create_cust.return_value = stripe_customer
        mock_session.return_value = MagicMock(id="cs_auto")

        StripeService.create_checkout_session(user, plan)
        plan.refresh_from_db()
        assert plan.stripe_price_id == "price_auto_123"

    @patch("apps.subscriptions.services.stripe.checkout.Session.create")
    @patch("apps.subscriptions.services.StripeService.create_customer")
    def test_checkout_with_coupon(
        self, mock_create_cust, mock_session, user, premium_plan, stripe_customer
    ):
        mock_create_cust.return_value = stripe_customer
        mock_session.return_value = MagicMock(id="cs_coupon")

        session = StripeService.create_checkout_session(
            user, premium_plan, coupon_code="TEST50"
        )
        assert session.id == "cs_coupon"
        call_kwargs = mock_session.call_args[1]
        assert call_kwargs["discounts"] == [{"coupon": "TEST50"}]


# ═══════════════════════════════════════════════════════════════════
# Subscription Lifecycle: Cancel
# ═══════════════════════════════════════════════════════════════════


class TestCancelSubscription:
    """Tests for StripeService.cancel_subscription."""

    @patch("apps.subscriptions.services.stripe.Subscription.modify")
    def test_cancel_sets_cancel_at_period_end(self, mock_modify, user, premium_subscription):
        mock_modify.return_value = MagicMock()
        result = StripeService.cancel_subscription(user)
        assert result is not None
        assert result.cancel_at_period_end is True
        assert result.canceled_at is not None

    def test_cancel_no_active_subscription(self):
        # Use a completely fresh user with no subscriptions at all
        fresh_user = User.objects.create_user(
            email="canceltest@test.com", password="testpass123", display_name="Cancel Test"
        )
        Subscription.objects.filter(user=fresh_user).delete()
        result = StripeService.cancel_subscription(fresh_user)
        assert result is None

    def test_cancel_admin_assigned(self, user, admin_premium_subscription, free_plan):
        """Admin-assigned subscription cancels locally to free plan."""
        result = StripeService.cancel_subscription(user)
        assert result is not None
        assert result.plan == free_plan
        assert result.status == "canceled"


# ═══════════════════════════════════════════════════════════════════
# Subscription Lifecycle: Plan Change (upgrade/downgrade)
# ═══════════════════════════════════════════════════════════════════


class TestPlanChange:
    """Tests for StripeService.change_plan."""

    @patch("apps.subscriptions.services.stripe.Subscription.modify")
    @patch("apps.subscriptions.services.stripe.Subscription.retrieve")
    def test_upgrade(self, mock_retrieve, mock_modify, user, premium_subscription, pro_plan):
        mock_retrieve.return_value = {
            "items": {"data": [{"id": "si_test"}]},
        }
        mock_modify.return_value = MagicMock()

        result = StripeService.change_plan(user, pro_plan)
        assert result["action"] == "upgraded"
        assert result["subscription"].plan == pro_plan

    @patch("apps.subscriptions.services.stripe.SubscriptionSchedule.modify")
    @patch("apps.subscriptions.services.stripe.SubscriptionSchedule.create")
    @patch("apps.subscriptions.services.stripe.Subscription.retrieve")
    def test_downgrade(
        self, mock_retrieve, mock_schedule_create, mock_schedule_modify,
        user, pro_subscription, premium_plan,
    ):
        mock_retrieve.return_value = {
            "items": {"data": [{"id": "si_test"}]},
        }
        mock_schedule_create.return_value = MagicMock(
            id="sub_sched_123",
            **{"__getitem__": lambda self, key: {"phases": [{"start_date": 1000, "end_date": 2000}]}[key]},
        )
        # Use a real dict-like mock
        schedule_mock = MagicMock()
        schedule_mock.id = "sub_sched_123"
        schedule_mock.__getitem__ = lambda self, key: {"phases": [{"start_date": 1000, "end_date": 2000}]}[key]
        mock_schedule_create.return_value = schedule_mock

        mock_schedule_modify.return_value = MagicMock()

        result = StripeService.change_plan(user, premium_plan)
        assert result["action"] == "downgrade_scheduled"
        assert result["subscription"].pending_plan == premium_plan

    def test_change_to_same_plan(self, user, premium_subscription, premium_plan):
        with pytest.raises(ValueError, match="already on this plan"):
            StripeService.change_plan(user, premium_plan)

    def test_change_no_subscription(self, premium_plan):
        fresh_user = User.objects.create_user(
            email="changetest@test.com", password="testpass123", display_name="Change Test"
        )
        Subscription.objects.filter(user=fresh_user).delete()
        with pytest.raises(ValueError, match="No active subscription"):
            StripeService.change_plan(fresh_user, premium_plan)

    @patch("apps.subscriptions.services.stripe.Subscription.modify")
    def test_downgrade_to_free_delegates_to_cancel(self, mock_modify, user, premium_subscription, free_plan):
        mock_modify.return_value = MagicMock()
        result = StripeService.change_plan(user, free_plan)
        assert result["action"] == "downgrade_scheduled"

    def test_free_to_paid_requires_checkout(self, user, free_subscription, premium_plan):
        with pytest.raises(ValueError, match="requires_checkout"):
            StripeService.change_plan(user, premium_plan)

    def test_admin_assigned_upgrade(self, user, admin_premium_subscription, pro_plan):
        result = StripeService.change_plan(user, pro_plan)
        assert result["action"] == "upgraded"
        assert result["subscription"].plan == pro_plan


# ═══════════════════════════════════════════════════════════════════
# Reactivate Subscription
# ═══════════════════════════════════════════════════════════════════


class TestReactivateSubscription:
    """Tests for StripeService.reactivate_subscription."""

    @patch("apps.subscriptions.services.stripe.Subscription.modify")
    def test_reactivate(self, mock_modify, user, premium_subscription):
        premium_subscription.cancel_at_period_end = True
        premium_subscription.canceled_at = timezone.now()
        premium_subscription.save()

        mock_modify.return_value = MagicMock()
        result = StripeService.reactivate_subscription(user)
        assert result is not None
        assert result.cancel_at_period_end is False
        assert result.canceled_at is None

    def test_reactivate_no_canceling_subscription(self, user):
        result = StripeService.reactivate_subscription(user)
        assert result is None

    def test_reactivate_admin_assigned(self, user, admin_premium_subscription):
        admin_premium_subscription.cancel_at_period_end = True
        admin_premium_subscription.canceled_at = timezone.now()
        admin_premium_subscription.save()

        result = StripeService.reactivate_subscription(user)
        assert result is not None
        assert result.cancel_at_period_end is False


# ═══════════════════════════════════════════════════════════════════
# Apply Coupon
# ═══════════════════════════════════════════════════════════════════


class TestApplyCoupon:
    """Tests for StripeService.apply_coupon."""

    @patch("apps.subscriptions.services.stripe.Subscription.modify")
    def test_apply_coupon(self, mock_modify, user, premium_subscription):
        mock_modify.return_value = MagicMock()
        result = StripeService.apply_coupon(user, "TESTCOUPON")
        assert result == premium_subscription

    def test_apply_coupon_no_subscription(self, user):
        with pytest.raises(ValueError, match="No active paid subscription"):
            StripeService.apply_coupon(user, "COUPON")

    @patch("apps.subscriptions.services.stripe.Subscription.modify")
    def test_apply_invalid_coupon(self, mock_modify, user, premium_subscription):
        mock_modify.side_effect = stripe.error.InvalidRequestError(
            "No such coupon", param="coupon"
        )
        with pytest.raises(ValueError, match="Invalid coupon"):
            StripeService.apply_coupon(user, "BAD_COUPON")


# ═══════════════════════════════════════════════════════════════════
# Cancel Pending Change
# ═══════════════════════════════════════════════════════════════════


class TestCancelPendingChange:
    """Tests for StripeService.cancel_pending_change."""

    @patch("apps.subscriptions.services.stripe.SubscriptionSchedule.release")
    def test_cancel_pending_change(self, mock_release, user, premium_subscription):
        premium_subscription.stripe_schedule_id = "sub_sched_123"
        premium_subscription.save()

        mock_release.return_value = MagicMock()
        result = StripeService.cancel_pending_change(user)
        assert result is not None
        assert result.pending_plan is None
        assert result.stripe_schedule_id == ""

    def test_cancel_pending_no_pending(self, user):
        result = StripeService.cancel_pending_change(user)
        assert result is None


# ═══════════════════════════════════════════════════════════════════
# Webhook Handling
# ═══════════════════════════════════════════════════════════════════


class TestWebhookHandling:
    """Tests for StripeService.handle_webhook_event and individual handlers."""

    @patch("apps.subscriptions.services.STRIPE_WEBHOOK_SECRET", "whsec_test")
    @patch("apps.subscriptions.services.stripe.Webhook.construct_event")
    @patch("apps.subscriptions.services.stripe.Subscription.retrieve")
    def test_checkout_completed(
        self, mock_retrieve, mock_construct, user, premium_plan, free_plan
    ):
        mock_retrieve.return_value = {
            "status": "active",
            "current_period_start": 1700000000,
            "current_period_end": 1702592000,
            "cancel_at_period_end": False,
        }

        event_data = {
            "type": "checkout.session.completed",
            "id": f"evt_test_{uuid.uuid4().hex[:8]}",
            "data": {
                "object": {
                    "metadata": {
                        "stepora_user_id": str(user.id),
                        "plan_slug": "premium",
                    },
                    "subscription": "sub_new_123",
                },
            },
        }
        mock_construct.return_value = event_data

        result = StripeService.handle_webhook_event(b"payload", "sig_header")
        assert result["status"] == "ok"
        assert result["event_type"] == "checkout.session.completed"

        sub = Subscription.objects.filter(user=user).first()
        assert sub is not None
        assert sub.plan == premium_plan

    @patch("apps.subscriptions.services.STRIPE_WEBHOOK_SECRET", "whsec_test")
    @patch("apps.subscriptions.services.stripe.Webhook.construct_event")
    @patch("apps.subscriptions.services.stripe.Subscription.retrieve")
    def test_invoice_paid(
        self, mock_retrieve, mock_construct, user, premium_subscription
    ):
        mock_retrieve.return_value = {
            "status": "active",
            "current_period_start": 1700000000,
            "current_period_end": 1702592000,
        }

        event_data = {
            "type": "invoice.paid",
            "id": f"evt_inv_{uuid.uuid4().hex[:8]}",
            "data": {
                "object": {
                    "subscription": "sub_test_123",
                    "amount_paid": 1999,
                    "hosted_invoice_url": "https://invoice.stripe.com/test",
                },
            },
        }
        mock_construct.return_value = event_data

        result = StripeService.handle_webhook_event(b"payload", "sig_header")
        assert result["status"] == "ok"

    @patch("apps.subscriptions.services.STRIPE_WEBHOOK_SECRET", "whsec_test")
    @patch("apps.subscriptions.services.stripe.Webhook.construct_event")
    def test_invoice_payment_failed(self, mock_construct, user, premium_subscription):
        event_data = {
            "type": "invoice.payment_failed",
            "id": f"evt_fail_{uuid.uuid4().hex[:8]}",
            "data": {
                "object": {
                    "subscription": "sub_test_123",
                },
            },
        }
        mock_construct.return_value = event_data

        result = StripeService.handle_webhook_event(b"payload", "sig_header")
        assert result["status"] == "ok"

        premium_subscription.refresh_from_db()
        assert premium_subscription.status == "past_due"

    @patch("apps.subscriptions.services.STRIPE_WEBHOOK_SECRET", "whsec_test")
    @patch("apps.subscriptions.services.stripe.Webhook.construct_event")
    def test_subscription_updated(self, mock_construct, db, user, premium_subscription, pro_plan):
        event_data = {
            "type": "customer.subscription.updated",
            "id": f"evt_upd_{uuid.uuid4().hex[:8]}",
            "data": {
                "object": {
                    "id": "sub_test_123",
                    "status": "active",
                    "current_period_start": 1700000000,
                    "current_period_end": 1702592000,
                    "cancel_at_period_end": False,
                    "items": {
                        "data": [
                            {
                                "price": {"id": "price_test_pro"},
                            }
                        ]
                    },
                },
            },
        }
        mock_construct.return_value = event_data

        result = StripeService.handle_webhook_event(b"payload", "sig_header")
        assert result["status"] == "ok"

        premium_subscription.refresh_from_db()
        assert premium_subscription.plan == pro_plan

    @patch("apps.subscriptions.services.STRIPE_WEBHOOK_SECRET", "whsec_test")
    @patch("apps.subscriptions.services.stripe.Webhook.construct_event")
    def test_subscription_deleted(self, mock_construct, user, premium_subscription, free_plan):
        event_data = {
            "type": "customer.subscription.deleted",
            "id": f"evt_del_{uuid.uuid4().hex[:8]}",
            "data": {
                "object": {
                    "id": "sub_test_123",
                },
            },
        }
        mock_construct.return_value = event_data

        result = StripeService.handle_webhook_event(b"payload", "sig_header")
        assert result["status"] == "ok"

        premium_subscription.refresh_from_db()
        assert premium_subscription.plan == free_plan
        assert premium_subscription.stripe_subscription_id == ""

    @patch("apps.subscriptions.services.STRIPE_WEBHOOK_SECRET", "whsec_test")
    @patch("apps.subscriptions.services.stripe.Webhook.construct_event")
    def test_idempotent_webhook(self, mock_construct, user, premium_subscription):
        event_id = f"evt_dup_{uuid.uuid4().hex[:8]}"
        StripeWebhookEvent.objects.create(
            stripe_event_id=event_id,
            event_type="invoice.paid",
        )
        event_data = {
            "type": "invoice.paid",
            "id": event_id,
            "data": {"object": {"subscription": "sub_test_123"}},
        }
        mock_construct.return_value = event_data

        result = StripeService.handle_webhook_event(b"payload", "sig_header")
        assert result["status"] == "already_processed"

    @patch("apps.subscriptions.services.STRIPE_WEBHOOK_SECRET", "whsec_test")
    @patch("apps.subscriptions.services.stripe.Webhook.construct_event")
    def test_unhandled_event_type(self, mock_construct):
        event_data = {
            "type": "payment_intent.created",
            "id": f"evt_unknown_{uuid.uuid4().hex[:8]}",
            "data": {"object": {}},
        }
        mock_construct.return_value = event_data

        result = StripeService.handle_webhook_event(b"payload", "sig_header")
        assert result["status"] == "ok"

    def test_webhook_no_secret_raises(self):
        with patch("apps.subscriptions.services.STRIPE_WEBHOOK_SECRET", ""):
            with patch("apps.subscriptions.services.StripeService.ensure_webhook", return_value=""):
                with pytest.raises(ValueError, match="not configured"):
                    StripeService.handle_webhook_event(b"payload", "sig")


# ═══════════════════════════════════════════════════════════════════
# Subscription Status Sync
# ═══════════════════════════════════════════════════════════════════


class TestSyncSubscriptionStatus:
    """Tests for StripeService.sync_subscription_status."""

    @patch("apps.subscriptions.services.stripe.Subscription.retrieve")
    def test_sync_active(self, mock_retrieve, user, premium_subscription):
        mock_retrieve.return_value = {
            "status": "active",
            "current_period_start": 1700000000,
            "current_period_end": 1702592000,
            "cancel_at_period_end": False,
        }
        result = StripeService.sync_subscription_status(user)
        assert result is not None
        assert result.status == "active"

    def test_sync_no_subscription(self):
        fresh_user = User.objects.create_user(
            email="synctest@test.com", password="testpass123", display_name="Sync Test"
        )
        Subscription.objects.filter(user=fresh_user).delete()
        result = StripeService.sync_subscription_status(fresh_user)
        assert result is None

    def test_sync_free_subscription(self, user, free_subscription):
        result = StripeService.sync_subscription_status(user)
        assert result == free_subscription

    @patch("apps.subscriptions.services.stripe.Subscription.retrieve")
    def test_sync_stripe_not_found_reverts_to_free(
        self, mock_retrieve, user, premium_subscription, free_plan
    ):
        mock_retrieve.side_effect = stripe.error.InvalidRequestError(
            "No such subscription", param="id"
        )
        result = StripeService.sync_subscription_status(user)
        assert result.plan == free_plan
        assert result.stripe_subscription_id == ""


# ═══════════════════════════════════════════════════════════════════
# Promotion Service
# ═══════════════════════════════════════════════════════════════════


class TestPromotionService:
    """Tests for PromotionService methods."""

    def test_get_active_promotions(self, user, active_promotion):
        promos = PromotionService.get_active_promotions(user)
        assert len(promos) >= 1
        assert active_promotion in promos

    def test_get_active_promotions_excluded_if_redeemed(
        self, user, active_promotion, premium_plan
    ):
        discount = PromotionPlanDiscount.objects.filter(
            promotion=active_promotion
        ).first()
        PromotionRedemption.objects.create(
            promotion=active_promotion,
            user=user,
            promotion_plan_discount=discount,
            stripe_coupon_id="coupon_test_50off",
        )
        promos = PromotionService.get_active_promotions(user)
        assert active_promotion not in promos

    def test_get_active_promotions_email_condition(self, user):
        promo = Promotion.objects.create(
            name="Edu Promo",
            start_date=timezone.now() - timedelta(days=1),
            is_active=True,
            condition_type="email_endswith",
            condition_value=".edu",
        )
        promos = PromotionService.get_active_promotions(user)
        assert promo not in promos

    def test_get_active_promotions_new_users_only(self, user, premium_plan, free_plan):
        # Create a past paid subscription so user is not "new"
        Subscription.objects.update_or_create(
            user=user,
            defaults={"plan": premium_plan, "status": "canceled"},
        )
        promo = Promotion.objects.create(
            name="New User Promo",
            start_date=timezone.now() - timedelta(days=1),
            is_active=True,
            target_audience="new_users",
        )
        promos = PromotionService.get_active_promotions(user)
        assert promo not in promos

    @patch("apps.subscriptions.services.stripe.Coupon.create")
    def test_create_stripe_coupon_percentage(self, mock_create, active_promotion, premium_plan):
        mock_create.return_value = MagicMock(id="coupon_new_123")
        discount = PromotionPlanDiscount.objects.filter(
            promotion=active_promotion
        ).first()
        coupon_id = PromotionService.create_stripe_coupon(discount)
        assert coupon_id == "coupon_new_123"
        call_kwargs = mock_create.call_args[1]
        assert call_kwargs["percent_off"] == 50.0

    @patch("apps.subscriptions.services.stripe.Coupon.create")
    def test_create_stripe_coupon_fixed_amount(self, mock_create, premium_plan):
        promo = Promotion.objects.create(
            name="Fixed Promo",
            start_date=timezone.now() - timedelta(days=1),
            is_active=True,
            discount_type="fixed_amount",
        )
        discount = PromotionPlanDiscount.objects.create(
            promotion=promo,
            plan=premium_plan,
            discount_value=Decimal("5.00"),
        )
        mock_create.return_value = MagicMock(id="coupon_fixed")
        coupon_id = PromotionService.create_stripe_coupon(discount)
        assert coupon_id == "coupon_fixed"
        call_kwargs = mock_create.call_args[1]
        assert call_kwargs["amount_off"] == 500
        assert call_kwargs["currency"] == "usd"

    @patch("apps.subscriptions.services.stripe.Coupon.delete")
    def test_delete_stripe_coupon(self, mock_delete):
        PromotionService.delete_stripe_coupon("coupon_test")
        mock_delete.assert_called_once_with("coupon_test")

    @patch("apps.subscriptions.services.stripe.Coupon.delete")
    def test_delete_stripe_coupon_not_found(self, mock_delete):
        mock_delete.side_effect = stripe.error.InvalidRequestError(
            "No such coupon", param="id"
        )
        # Should not raise
        PromotionService.delete_stripe_coupon("coupon_gone")

    def test_record_redemption(self, user, active_promotion, premium_plan):
        discount = PromotionPlanDiscount.objects.filter(
            promotion=active_promotion
        ).first()
        redemption = PromotionService.record_redemption(user, active_promotion, discount)
        assert redemption.user == user
        assert redemption.promotion == active_promotion

    def test_record_redemption_idempotent(self, user, active_promotion, premium_plan):
        discount = PromotionPlanDiscount.objects.filter(
            promotion=active_promotion
        ).first()
        r1 = PromotionService.record_redemption(user, active_promotion, discount)
        r2 = PromotionService.record_redemption(user, active_promotion, discount)
        assert r1.id == r2.id

    def test_get_discount_for_checkout(self, user, active_promotion, premium_plan):
        discount = PromotionService.get_discount_for_checkout(
            user, str(active_promotion.id), premium_plan
        )
        assert discount.stripe_coupon_id == "coupon_test_50off"

    def test_get_discount_for_checkout_invalid_promo(self, user, premium_plan):
        with pytest.raises(ValueError, match="Promotion not found"):
            PromotionService.get_discount_for_checkout(
                user, str(uuid.uuid4()), premium_plan
            )

    @patch("apps.subscriptions.services.stripe.Product.create")
    @patch("apps.subscriptions.services.stripe.Price.create")
    def test_create_stripe_price_for_plan(self, mock_price, mock_product, premium_plan):
        mock_product.return_value = MagicMock(id="prod_test")
        mock_price.return_value = MagicMock(id="price_new_test")
        price_id = PromotionService.create_stripe_price_for_plan(premium_plan)
        assert price_id == "price_new_test"


# ═══════════════════════════════════════════════════════════════════
# Helper Functions
# ═══════════════════════════════════════════════════════════════════


class TestHelperFunctions:
    """Tests for module-level helper functions."""

    def test_timestamp_to_datetime(self):
        result = _timestamp_to_datetime(1700000000)
        assert result is not None
        assert result.year == 2023

    def test_timestamp_to_datetime_none(self):
        assert _timestamp_to_datetime(None) is None

    def test_sync_user_subscription(self, user, premium_plan):
        period_end = timezone.now() + timedelta(days=30)
        _sync_user_subscription(user, premium_plan, period_end)
        user.refresh_from_db()
        assert user.subscription_ends == period_end

    def test_revoke_downgraded_features(self, user, free_plan):
        """Should not raise even without store/buddy models."""
        _revoke_downgraded_features(user, free_plan)


# ═══════════════════════════════════════════════════════════════════
# Portal Session
# ═══════════════════════════════════════════════════════════════════


class TestPortalSession:
    """Tests for StripeService.create_portal_session."""

    @patch("apps.subscriptions.services.stripe.billing_portal.Session.create")
    def test_create_portal_session(self, mock_portal, user, stripe_customer):
        mock_portal.return_value = MagicMock(id="bps_test", url="https://portal.stripe.com")
        session = StripeService.create_portal_session(user)
        assert session.url == "https://portal.stripe.com"

    def test_portal_no_customer(self, user):
        with pytest.raises(ValueError, match="no Stripe customer"):
            StripeService.create_portal_session(user)


# ═══════════════════════════════════════════════════════════════════
# Analytics & Invoices
# ═══════════════════════════════════════════════════════════════════


class TestAnalyticsAndInvoices:
    """Tests for analytics and invoice listing."""

    def test_get_analytics(self, user, premium_subscription):
        analytics = StripeService.get_analytics()
        assert "mrr" in analytics
        assert "active_subscriptions" in analytics
        assert analytics["active_subscriptions"] >= 1

    @patch("apps.subscriptions.services.stripe.Invoice.list")
    def test_list_invoices(self, mock_list, user, stripe_customer):
        mock_list.return_value = {
            "data": [
                {
                    "id": "in_test_123",
                    "number": "INV-001",
                    "amount_due": 1999,
                    "amount_paid": 1999,
                    "currency": "usd",
                    "status": "paid",
                    "period_start": 1700000000,
                    "period_end": 1702592000,
                    "hosted_invoice_url": "https://invoice.stripe.com/test",
                    "invoice_pdf": "https://pdf.stripe.com/test",
                    "created": 1700000000,
                }
            ]
        }
        invoices = StripeService.list_invoices(user)
        assert len(invoices) == 1
        assert invoices[0]["id"] == "in_test_123"

    def test_list_invoices_no_customer(self, user):
        invoices = StripeService.list_invoices(user)
        assert invoices == []
