"""
Additional tests for subscriptions app — coverage gap filler.

Covers edge cases and flows not fully tested in other test files:
- Webhook handlers: missing metadata, unknown subscription, promotion redemption
- PromotionService: recreate_stripe_coupon with changelog, get_discount_for_checkout edge cases
- Analytics endpoint with admin user
- Checkout with promotion_id flow
- PromotionChangeLog model
- Serializer edge cases
- IDOR protection (subscription scoping)
"""

import uuid
from datetime import timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
import stripe
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.subscriptions.models import (
    Promotion,
    PromotionChangeLog,
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
    _timestamp_to_datetime,
)
from apps.users.models import User


# ═══════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════


@pytest.fixture
def admin_user(db):
    """Create a staff/admin user."""
    user = User.objects.create_user(
        email="admin_sub@example.com",
        password="testpass123",
        display_name="Admin",
    )
    user.is_staff = True
    user.save(update_fields=["is_staff"])
    return user


@pytest.fixture
def admin_client(admin_user):
    """Authenticated admin API client."""
    client = APIClient()
    client.force_authenticate(user=admin_user)
    return client


@pytest.fixture
def other_user(db):
    """A second user for IDOR tests."""
    return User.objects.create_user(
        email="other_sub_user@example.com",
        password="testpass123",
        display_name="Other User",
    )


@pytest.fixture
def other_client(other_user):
    """Authenticated client for other_user."""
    client = APIClient()
    client.force_authenticate(user=other_user)
    return client


# ═══════════════════════════════════════════════════════════════════
# Webhook Handler Edge Cases
# ═══════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestWebhookHandlerEdgeCases:
    """Tests for webhook event handler edge cases."""

    @patch("apps.subscriptions.services.STRIPE_WEBHOOK_SECRET", "whsec_test")
    @patch("apps.subscriptions.services.stripe.Webhook.construct_event")
    def test_checkout_completed_missing_user_id(self, mock_construct, db):
        """checkout.session.completed with missing user_id is handled gracefully."""
        mock_construct.return_value = {
            "id": f"evt_no_user_{uuid.uuid4().hex[:8]}",
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "metadata": {
                        "plan_slug": "premium",
                    },
                    "subscription": "sub_xxx",
                },
            },
        }
        result = StripeService.handle_webhook_event(b"payload", "sig")
        assert result["status"] == "ok"

    @patch("apps.subscriptions.services.STRIPE_WEBHOOK_SECRET", "whsec_test")
    @patch("apps.subscriptions.services.stripe.Webhook.construct_event")
    def test_checkout_completed_missing_subscription_id(self, mock_construct, sub_user):
        """checkout.session.completed with missing subscription ID is handled."""
        mock_construct.return_value = {
            "id": f"evt_no_sub_{uuid.uuid4().hex[:8]}",
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "metadata": {
                        "stepora_user_id": str(sub_user.id),
                        "plan_slug": "premium",
                    },
                    "subscription": None,
                },
            },
        }
        result = StripeService.handle_webhook_event(b"payload", "sig")
        assert result["status"] == "ok"

    @patch("apps.subscriptions.services.STRIPE_WEBHOOK_SECRET", "whsec_test")
    @patch("apps.subscriptions.services.stripe.Webhook.construct_event")
    def test_checkout_completed_nonexistent_user(self, mock_construct, db):
        """checkout.session.completed with a non-existent user_id is handled."""
        mock_construct.return_value = {
            "id": f"evt_bad_user_{uuid.uuid4().hex[:8]}",
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "metadata": {
                        "stepora_user_id": str(uuid.uuid4()),
                        "plan_slug": "premium",
                    },
                    "subscription": "sub_xxx",
                },
            },
        }
        result = StripeService.handle_webhook_event(b"payload", "sig")
        assert result["status"] == "ok"

    @patch("apps.subscriptions.services.STRIPE_WEBHOOK_SECRET", "whsec_test")
    @patch("apps.subscriptions.services.stripe.Webhook.construct_event")
    def test_checkout_completed_nonexistent_plan(
        self, mock_construct, sub_user, free_plan
    ):
        """checkout.session.completed with bad plan_slug is handled."""
        mock_construct.return_value = {
            "id": f"evt_bad_plan_{uuid.uuid4().hex[:8]}",
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "metadata": {
                        "stepora_user_id": str(sub_user.id),
                        "plan_slug": "nonexistent_plan",
                    },
                    "subscription": "sub_xxx",
                },
            },
        }
        result = StripeService.handle_webhook_event(b"payload", "sig")
        assert result["status"] == "ok"

    @patch("apps.subscriptions.services.STRIPE_WEBHOOK_SECRET", "whsec_test")
    @patch("apps.subscriptions.services.stripe.Webhook.construct_event")
    @patch("apps.subscriptions.services.stripe.Subscription.retrieve")
    def test_checkout_completed_with_promotion_redemption(
        self, mock_retrieve, mock_construct, sub_user, premium_plan, active_promotion
    ):
        """checkout.session.completed records promotion redemption."""
        mock_retrieve.return_value = {
            "status": "active",
            "current_period_start": 1700000000,
            "current_period_end": 1702592000,
            "cancel_at_period_end": False,
        }
        mock_construct.return_value = {
            "id": f"evt_promo_{uuid.uuid4().hex[:8]}",
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "metadata": {
                        "stepora_user_id": str(sub_user.id),
                        "plan_slug": "premium",
                        "promotion_id": str(active_promotion.id),
                    },
                    "subscription": "sub_promo_123",
                },
            },
        }
        result = StripeService.handle_webhook_event(b"payload", "sig")
        assert result["status"] == "ok"

        # Check promotion redemption was recorded
        redemption = PromotionRedemption.objects.filter(
            user=sub_user, promotion=active_promotion
        ).first()
        assert redemption is not None

    @patch("apps.subscriptions.services.STRIPE_WEBHOOK_SECRET", "whsec_test")
    @patch("apps.subscriptions.services.stripe.Webhook.construct_event")
    def test_invoice_paid_unknown_subscription(self, mock_construct, db):
        """invoice.paid for unknown subscription does not crash."""
        mock_construct.return_value = {
            "id": f"evt_inv_unk_{uuid.uuid4().hex[:8]}",
            "type": "invoice.paid",
            "data": {
                "object": {
                    "subscription": "sub_unknown_xxx",
                    "amount_paid": 1999,
                },
            },
        }
        result = StripeService.handle_webhook_event(b"payload", "sig")
        assert result["status"] == "ok"

    @patch("apps.subscriptions.services.STRIPE_WEBHOOK_SECRET", "whsec_test")
    @patch("apps.subscriptions.services.stripe.Webhook.construct_event")
    def test_invoice_paid_no_subscription_field(self, mock_construct, db):
        """invoice.paid with no subscription field is handled."""
        mock_construct.return_value = {
            "id": f"evt_inv_nosub_{uuid.uuid4().hex[:8]}",
            "type": "invoice.paid",
            "data": {
                "object": {
                    "amount_paid": 0,
                },
            },
        }
        result = StripeService.handle_webhook_event(b"payload", "sig")
        assert result["status"] == "ok"

    @patch("apps.subscriptions.services.STRIPE_WEBHOOK_SECRET", "whsec_test")
    @patch("apps.subscriptions.services.stripe.Webhook.construct_event")
    def test_invoice_payment_failed_unknown_subscription(self, mock_construct, db):
        """invoice.payment_failed for unknown subscription does not crash."""
        mock_construct.return_value = {
            "id": f"evt_fail_unk_{uuid.uuid4().hex[:8]}",
            "type": "invoice.payment_failed",
            "data": {
                "object": {
                    "subscription": "sub_unknown_yyy",
                },
            },
        }
        result = StripeService.handle_webhook_event(b"payload", "sig")
        assert result["status"] == "ok"

    @patch("apps.subscriptions.services.STRIPE_WEBHOOK_SECRET", "whsec_test")
    @patch("apps.subscriptions.services.stripe.Webhook.construct_event")
    def test_subscription_updated_unknown_subscription(self, mock_construct, db):
        """subscription.updated for unknown subscription does not crash."""
        mock_construct.return_value = {
            "id": f"evt_upd_unk_{uuid.uuid4().hex[:8]}",
            "type": "customer.subscription.updated",
            "data": {
                "object": {
                    "id": "sub_unknown_zzz",
                    "status": "active",
                    "current_period_start": 1700000000,
                    "current_period_end": 1702592000,
                    "cancel_at_period_end": False,
                    "items": {"data": []},
                },
            },
        }
        result = StripeService.handle_webhook_event(b"payload", "sig")
        assert result["status"] == "ok"

    @patch("apps.subscriptions.services.STRIPE_WEBHOOK_SECRET", "whsec_test")
    @patch("apps.subscriptions.services.stripe.Webhook.construct_event")
    def test_subscription_updated_with_plan_change(
        self, mock_construct, sub_user, premium_plan, pro_plan, premium_subscription
    ):
        """subscription.updated with a new price changes the local plan."""
        # Ensure pro_plan has the expected stripe_price_id
        pro_plan.stripe_price_id = "price_test_pro"
        pro_plan.save(update_fields=["stripe_price_id"])

        mock_construct.return_value = {
            "id": f"evt_upd_chg_{uuid.uuid4().hex[:8]}",
            "type": "customer.subscription.updated",
            "data": {
                "object": {
                    "id": "sub_test_123",
                    "status": "active",
                    "current_period_start": 1700000000,
                    "current_period_end": 1702592000,
                    "cancel_at_period_end": False,
                    "items": {
                        "data": [
                            {"price": {"id": "price_test_pro"}},
                        ]
                    },
                },
            },
        }
        result = StripeService.handle_webhook_event(b"payload", "sig")
        assert result["status"] == "ok"

        # Reload subscription from DB to reflect handler's changes
        sub = Subscription.objects.get(pk=premium_subscription.pk)
        assert sub.plan == pro_plan
        # Pending plan should be cleared
        assert sub.pending_plan is None
        assert sub.stripe_schedule_id == ""

    @patch("apps.subscriptions.services.STRIPE_WEBHOOK_SECRET", "whsec_test")
    @patch("apps.subscriptions.services.stripe.Webhook.construct_event")
    def test_subscription_updated_no_plan_change(
        self, mock_construct, sub_user, premium_plan, premium_subscription
    ):
        """subscription.updated without plan change just updates period."""
        mock_construct.return_value = {
            "id": f"evt_upd_nochg_{uuid.uuid4().hex[:8]}",
            "type": "customer.subscription.updated",
            "data": {
                "object": {
                    "id": "sub_test_123",
                    "status": "active",
                    "current_period_start": 1700000000,
                    "current_period_end": 1702592000,
                    "cancel_at_period_end": False,
                    "items": {
                        "data": [
                            {"price": {"id": "price_test_premium"}},
                        ]
                    },
                },
            },
        }
        result = StripeService.handle_webhook_event(b"payload", "sig")
        assert result["status"] == "ok"

        premium_subscription.refresh_from_db()
        assert premium_subscription.plan == premium_plan

    @patch("apps.subscriptions.services.STRIPE_WEBHOOK_SECRET", "whsec_test")
    @patch("apps.subscriptions.services.stripe.Webhook.construct_event")
    def test_subscription_deleted_unknown(self, mock_construct, db):
        """subscription.deleted for unknown subscription does not crash."""
        mock_construct.return_value = {
            "id": f"evt_del_unk_{uuid.uuid4().hex[:8]}",
            "type": "customer.subscription.deleted",
            "data": {
                "object": {
                    "id": "sub_totally_unknown",
                },
            },
        }
        result = StripeService.handle_webhook_event(b"payload", "sig")
        assert result["status"] == "ok"

    @patch("apps.subscriptions.services.STRIPE_WEBHOOK_SECRET", "whsec_test")
    @patch("apps.subscriptions.services.stripe.Webhook.construct_event")
    def test_signature_verification_failure(self, mock_construct, db):
        """Invalid signature raises ValueError."""
        mock_construct.side_effect = stripe.error.SignatureVerificationError(
            "Invalid signature", sig_header="bad"
        )
        with pytest.raises(ValueError, match="Invalid webhook signature"):
            StripeService.handle_webhook_event(b"payload", "bad_sig")


# ═══════════════════════════════════════════════════════════════════
# PromotionService: recreate_stripe_coupon
# ═══════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestRecreateStripeCoupon:
    """Tests for PromotionService.recreate_stripe_coupon."""

    @patch("apps.subscriptions.services.stripe.Coupon.create")
    @patch("apps.subscriptions.services.stripe.Coupon.delete")
    def test_recreate_deletes_old_and_creates_new(
        self, mock_delete, mock_create, active_promotion, premium_plan
    ):
        """recreate_stripe_coupon deletes old coupon and creates a new one."""
        mock_create.return_value = MagicMock(id="coupon_recreated_new")
        discount = active_promotion.plan_discounts.first()
        old_id = discount.stripe_coupon_id

        new_id = PromotionService.recreate_stripe_coupon(discount)
        assert new_id == "coupon_recreated_new"
        mock_delete.assert_called_once_with(old_id)

    @patch("apps.subscriptions.services.stripe.Coupon.create")
    @patch("apps.subscriptions.services.stripe.Coupon.delete")
    def test_recreate_creates_changelog(
        self, mock_delete, mock_create, active_promotion, premium_plan
    ):
        """recreate_stripe_coupon creates a PromotionChangeLog entry."""
        mock_create.return_value = MagicMock(id="coupon_log_test")
        discount = active_promotion.plan_discounts.first()

        PromotionService.recreate_stripe_coupon(discount)

        # Should have a changelog entry with action="coupon_recreated"
        log = PromotionChangeLog.objects.filter(
            promotion=active_promotion,
            new_stripe_coupon_id="coupon_log_test",
        ).first()
        assert log is not None
        assert log.action == "coupon_recreated"

    @patch("apps.subscriptions.services.stripe.Coupon.create")
    def test_recreate_with_no_old_coupon(self, mock_create, premium_plan):
        """recreate_stripe_coupon works when there is no old coupon."""
        mock_create.return_value = MagicMock(id="coupon_fresh")
        promo = Promotion.objects.create(
            name="Fresh Promo",
            start_date=timezone.now(),
            discount_type="percentage",
            is_active=True,
        )
        discount = PromotionPlanDiscount.objects.create(
            promotion=promo,
            plan=premium_plan,
            discount_value=Decimal("15.00"),
            stripe_coupon_id="",
        )
        new_id = PromotionService.recreate_stripe_coupon(discount)
        assert new_id == "coupon_fresh"


# ═══════════════════════════════════════════════════════════════════
# PromotionService: get_discount_for_checkout edge cases
# ═══════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestGetDiscountForCheckoutEdgeCases:
    """Tests for PromotionService.get_discount_for_checkout edge cases."""

    def test_promotion_not_eligible(self, sub_user, premium_plan):
        """get_discount_for_checkout raises if promo is not eligible for user."""
        promo = Promotion.objects.create(
            name="Email Only Promo",
            start_date=timezone.now() - timedelta(days=1),
            is_active=True,
            condition_type="email_endswith",
            condition_value="@special.edu",
        )
        PromotionPlanDiscount.objects.create(
            promotion=promo,
            plan=premium_plan,
            discount_value=Decimal("20.00"),
            stripe_coupon_id="coupon_special",
        )
        with pytest.raises(ValueError, match="not available"):
            PromotionService.get_discount_for_checkout(
                sub_user, str(promo.id), premium_plan
            )

    def test_no_discount_for_plan(self, sub_user, pro_plan, active_promotion):
        """get_discount_for_checkout raises if promo doesn't apply to the plan."""
        # active_promotion has discount for premium, not pro
        with pytest.raises(ValueError, match="does not apply"):
            PromotionService.get_discount_for_checkout(
                sub_user, str(active_promotion.id), pro_plan
            )

    def test_no_stripe_coupon_id(self, sub_user, premium_plan):
        """get_discount_for_checkout raises if coupon not yet configured."""
        promo = Promotion.objects.create(
            name="No Coupon Promo",
            start_date=timezone.now() - timedelta(days=1),
            is_active=True,
        )
        PromotionPlanDiscount.objects.create(
            promotion=promo,
            plan=premium_plan,
            discount_value=Decimal("10.00"),
            stripe_coupon_id="",
        )
        with pytest.raises(ValueError, match="not yet configured"):
            PromotionService.get_discount_for_checkout(
                sub_user, str(promo.id), premium_plan
            )


# ═══════════════════════════════════════════════════════════════════
# PromotionService: Stripe coupon creation details
# ═══════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestStripeCouponCreationDetails:
    """Tests for PromotionService.create_stripe_coupon with various configurations."""

    @patch("apps.subscriptions.services.stripe.Coupon.create")
    def test_coupon_with_duration_months(self, mock_create, premium_plan):
        """Coupon with duration_months > 1 uses 'repeating' duration."""
        mock_create.return_value = MagicMock(id="coupon_repeating")
        promo = Promotion.objects.create(
            name="Repeating Promo",
            start_date=timezone.now(),
            discount_type="percentage",
            duration_months=3,
            is_active=True,
        )
        discount = PromotionPlanDiscount.objects.create(
            promotion=promo,
            plan=premium_plan,
            discount_value=Decimal("25.00"),
        )
        PromotionService.create_stripe_coupon(discount)
        call_kwargs = mock_create.call_args[1]
        assert call_kwargs["duration"] == "repeating"
        assert call_kwargs["duration_in_months"] == 3

    @patch("apps.subscriptions.services.stripe.Coupon.create")
    def test_coupon_once_duration(self, mock_create, premium_plan):
        """Coupon with duration_months <= 1 uses 'once' duration."""
        mock_create.return_value = MagicMock(id="coupon_once")
        promo = Promotion.objects.create(
            name="Once Promo",
            start_date=timezone.now(),
            discount_type="percentage",
            duration_months=1,
            is_active=True,
        )
        discount = PromotionPlanDiscount.objects.create(
            promotion=promo,
            plan=premium_plan,
            discount_value=Decimal("10.00"),
        )
        PromotionService.create_stripe_coupon(discount)
        call_kwargs = mock_create.call_args[1]
        assert call_kwargs["duration"] == "once"

    @patch("apps.subscriptions.services.stripe.Coupon.create")
    def test_coupon_with_max_redemptions(self, mock_create, premium_plan):
        """Coupon with max_redemptions passes it to Stripe."""
        mock_create.return_value = MagicMock(id="coupon_max")
        promo = Promotion.objects.create(
            name="Max Promo",
            start_date=timezone.now(),
            discount_type="percentage",
            max_redemptions=50,
            is_active=True,
        )
        discount = PromotionPlanDiscount.objects.create(
            promotion=promo,
            plan=premium_plan,
            discount_value=Decimal("15.00"),
        )
        PromotionService.create_stripe_coupon(discount)
        call_kwargs = mock_create.call_args[1]
        assert call_kwargs["max_redemptions"] == 50

    @patch("apps.subscriptions.services.stripe.Coupon.create")
    def test_coupon_with_end_date(self, mock_create, premium_plan):
        """Coupon with end_date passes redeem_by to Stripe."""
        mock_create.return_value = MagicMock(id="coupon_end")
        end = timezone.now() + timedelta(days=30)
        promo = Promotion.objects.create(
            name="End Date Promo",
            start_date=timezone.now(),
            end_date=end,
            discount_type="percentage",
            is_active=True,
        )
        discount = PromotionPlanDiscount.objects.create(
            promotion=promo,
            plan=premium_plan,
            discount_value=Decimal("10.00"),
        )
        PromotionService.create_stripe_coupon(discount)
        call_kwargs = mock_create.call_args[1]
        assert "redeem_by" in call_kwargs
        assert call_kwargs["redeem_by"] == int(end.timestamp())


# ═══════════════════════════════════════════════════════════════════
# Analytics Admin Endpoint
# ═══════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestAnalyticsAdminEndpoint:
    """Tests for the admin-only analytics endpoint."""

    def test_analytics_admin_access(self, admin_client, free_plan):
        """Admin user can access subscription analytics."""
        # Ensure admin has a subscription
        Subscription.objects.get_or_create(
            user=User.objects.get(email="admin_sub@example.com"),
            defaults={"plan": free_plan, "status": "active"},
        )
        response = admin_client.get("/api/subscriptions/subscription/analytics/")
        assert response.status_code == status.HTTP_200_OK
        data = response.data
        assert "mrr" in data
        assert "active_subscriptions" in data
        assert "churn_rate_percent" in data
        assert "conversion_rate_percent" in data
        assert "total_users" in data
        assert "trialing" in data


# ═══════════════════════════════════════════════════════════════════
# Checkout with Promotion ID
# ═══════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestCheckoutWithPromotion:
    """Tests for checkout endpoint with promotion_id."""

    @patch("apps.subscriptions.views.StripeService.create_checkout_session")
    @patch("apps.subscriptions.views.PromotionService.get_discount_for_checkout")
    def test_checkout_with_promotion_id(
        self,
        mock_get_discount,
        mock_create_session,
        sub_client,
        free_subscription,
        premium_plan,
        active_promotion,
    ):
        """Checkout resolves promotion_id to coupon_code."""
        mock_discount = MagicMock()
        mock_discount.stripe_coupon_id = "coupon_test_50off"
        mock_get_discount.return_value = mock_discount

        mock_session = MagicMock()
        mock_session.url = "https://checkout.stripe.com/promo"
        mock_session.id = "cs_promo_123"
        mock_create_session.return_value = mock_session

        response = sub_client.post(
            "/api/subscriptions/subscription/checkout/",
            {
                "plan_slug": "premium",
                "promotion_id": str(active_promotion.id),
            },
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert "checkout_url" in response.data

        # Verify create_checkout_session was called with the resolved coupon
        call_kwargs = mock_create_session.call_args
        assert call_kwargs.kwargs.get("coupon_code") == "coupon_test_50off" or \
               (len(call_kwargs.args) > 4 and call_kwargs.args[4] == "coupon_test_50off")

    @patch("apps.subscriptions.views.PromotionService.get_discount_for_checkout")
    def test_checkout_with_invalid_promotion(
        self, mock_get_discount, sub_client, free_subscription, premium_plan
    ):
        """Checkout with invalid promotion_id returns 400."""
        mock_get_discount.side_effect = ValueError("Promotion not found.")

        response = sub_client.post(
            "/api/subscriptions/subscription/checkout/",
            {
                "plan_slug": "premium",
                "promotion_id": str(uuid.uuid4()),
            },
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST


# ═══════════════════════════════════════════════════════════════════
# IDOR Protection
# ═══════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestIDORProtection:
    """Tests that subscription endpoints are scoped to the authenticated user."""

    def test_current_subscription_scoped(
        self, other_client, sub_user, premium_subscription, free_plan
    ):
        """User cannot see another user's subscription via /current/."""
        response = other_client.get("/api/subscriptions/subscription/current/")
        # other_user should see their own sub (auto-created free), not sub_user's premium
        if response.status_code == status.HTTP_200_OK:
            assert response.data["plan"]["slug"] != "premium"
        else:
            # 404 if no subscription record
            assert response.status_code == status.HTTP_404_NOT_FOUND

    @patch("apps.subscriptions.views.StripeService.cancel_subscription")
    def test_cancel_scoped_to_user(self, mock_cancel, other_client, premium_subscription):
        """Cancel endpoint only affects the authenticated user."""
        mock_cancel.return_value = None
        response = other_client.post("/api/subscriptions/subscription/cancel/")
        # cancel_subscription is called with other_user, not sub_user
        called_user = mock_cancel.call_args[0][0]
        assert called_user.email != "subuser@example.com"


# ═══════════════════════════════════════════════════════════════════
# PromotionChangeLog Model
# ═══════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestPromotionChangeLogModel:
    """Tests for the PromotionChangeLog model."""

    def test_create_changelog(self, active_promotion, premium_plan):
        """PromotionChangeLog can be created with all fields."""
        discount = active_promotion.plan_discounts.first()
        log = PromotionChangeLog.objects.create(
            promotion=active_promotion,
            plan_discount=discount,
            action="coupon_created",
            new_stripe_coupon_id="coupon_log_test",
            details={
                "plan": "premium",
                "discount_type": "percentage",
                "discount_value": "50.00",
            },
        )
        assert log.pk is not None
        assert log.action == "coupon_created"

    def test_str_representation(self, active_promotion):
        """__str__ shows action and promotion name."""
        log = PromotionChangeLog.objects.create(
            promotion=active_promotion,
            action="coupon_deleted",
            old_stripe_coupon_id="coupon_del",
        )
        s = str(log)
        assert "coupon_deleted" in s
        assert "Test Promo" in s

    def test_action_choices(self, active_promotion):
        """All action choices are valid."""
        for action_code, _ in PromotionChangeLog.ACTION_CHOICES:
            log = PromotionChangeLog.objects.create(
                promotion=active_promotion,
                action=action_code,
            )
            assert log.action == action_code


# ═══════════════════════════════════════════════════════════════════
# Promotion eligibility: exhausted, expired, inactive
# ═══════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestPromotionEligibility:
    """Tests for promotion eligibility edge cases."""

    def test_exhausted_promotion_not_returned(self, sub_user, premium_plan):
        """Exhausted promotion is not in active promotions."""
        promo = Promotion.objects.create(
            name="Exhausted Promo",
            start_date=timezone.now() - timedelta(days=1),
            discount_type="percentage",
            max_redemptions=1,
            is_active=True,
        )
        discount = PromotionPlanDiscount.objects.create(
            promotion=promo,
            plan=premium_plan,
            discount_value=Decimal("10.00"),
            stripe_coupon_id="coupon_exh",
        )
        # Create a redemption to exhaust it
        other = User.objects.create_user(
            email="exhaust_user@example.com", password="test123"
        )
        PromotionRedemption.objects.create(
            promotion=promo,
            user=other,
            promotion_plan_discount=discount,
            stripe_coupon_id="coupon_exh",
        )
        promos = PromotionService.get_active_promotions(sub_user)
        assert promo not in promos

    def test_expired_promotion_not_returned(self, sub_user, premium_plan):
        """Expired promotion is not in active promotions."""
        promo = Promotion.objects.create(
            name="Expired Promo",
            start_date=timezone.now() - timedelta(days=30),
            end_date=timezone.now() - timedelta(days=1),
            discount_type="percentage",
            is_active=True,
        )
        promos = PromotionService.get_active_promotions(sub_user)
        assert promo not in promos

    def test_inactive_promotion_not_returned(self, sub_user, premium_plan):
        """Inactive promotion is not in active promotions."""
        promo = Promotion.objects.create(
            name="Inactive Promo",
            start_date=timezone.now() - timedelta(days=1),
            discount_type="percentage",
            is_active=False,
        )
        promos = PromotionService.get_active_promotions(sub_user)
        assert promo not in promos

    def test_future_promotion_not_returned(self, sub_user, premium_plan):
        """Promotion that hasn't started yet is not in active promotions."""
        promo = Promotion.objects.create(
            name="Future Promo",
            start_date=timezone.now() + timedelta(days=7),
            discount_type="percentage",
            is_active=True,
        )
        promos = PromotionService.get_active_promotions(sub_user)
        assert promo not in promos

    def test_email_condition_matching(self, premium_plan):
        """Promotion with email_endswith condition matches correct users."""
        promo = Promotion.objects.create(
            name="EDU Promo",
            start_date=timezone.now() - timedelta(days=1),
            discount_type="percentage",
            condition_type="email_endswith",
            condition_value=".edu",
            is_active=True,
        )
        PromotionPlanDiscount.objects.create(
            promotion=promo,
            plan=premium_plan,
            discount_value=Decimal("20.00"),
            stripe_coupon_id="coupon_edu",
        )

        edu_user = User.objects.create_user(
            email="student@university.edu", password="test123"
        )
        non_edu_user = User.objects.create_user(
            email="user@gmail.com", password="test123"
        )

        assert promo in PromotionService.get_active_promotions(edu_user)
        assert promo not in PromotionService.get_active_promotions(non_edu_user)

    def test_no_end_date_means_always_active(self, sub_user, premium_plan):
        """Promotion with no end_date remains active indefinitely."""
        promo = Promotion.objects.create(
            name="Forever Promo",
            start_date=timezone.now() - timedelta(days=365),
            end_date=None,
            discount_type="percentage",
            is_active=True,
        )
        PromotionPlanDiscount.objects.create(
            promotion=promo,
            plan=premium_plan,
            discount_value=Decimal("5.00"),
            stripe_coupon_id="coupon_forever",
        )
        promos = PromotionService.get_active_promotions(sub_user)
        assert promo in promos


# ═══════════════════════════════════════════════════════════════════
# Revoke Downgraded Features
# ═══════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestRevokeDowngradedFeatures:
    """Tests for _revoke_downgraded_features helper."""

    def test_revoke_on_free_plan(self, sub_user, free_plan):
        """Revoking features for free plan does not crash."""
        _revoke_downgraded_features(sub_user, free_plan)

    def test_revoke_on_premium_plan(self, sub_user, premium_plan):
        """Revoking features for premium plan does not crash."""
        _revoke_downgraded_features(sub_user, premium_plan)

    def test_revoke_on_pro_plan(self, sub_user, pro_plan):
        """Revoking features for pro plan skips store item unequip."""
        _revoke_downgraded_features(sub_user, pro_plan)


# ═══════════════════════════════════════════════════════════════════
# Timestamp Helper
# ═══════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestTimestampHelper:
    """Tests for _timestamp_to_datetime helper."""

    def test_zero_timestamp(self):
        """Zero timestamp is converted correctly."""
        result = _timestamp_to_datetime(0)
        assert result is not None
        assert result.year == 1970

    def test_float_timestamp(self):
        """Float timestamps are handled."""
        result = _timestamp_to_datetime(1700000000.5)
        assert result is not None

    def test_large_timestamp(self):
        """Large timestamps are handled."""
        result = _timestamp_to_datetime(2000000000)
        assert result is not None


# ═══════════════════════════════════════════════════════════════════
# Stripe Error Handling in Views
# ═══════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestStripeErrorHandling:
    """Tests that Stripe errors are properly caught and return 502."""

    @patch(
        "apps.subscriptions.views.StripeService.create_checkout_session",
        side_effect=stripe.error.StripeError("Stripe down"),
    )
    def test_checkout_stripe_error(self, mock_svc, sub_client, free_subscription, premium_plan):
        """Checkout returns 502 on Stripe error."""
        response = sub_client.post(
            "/api/subscriptions/subscription/checkout/",
            {"plan_slug": "premium"},
            format="json",
        )
        assert response.status_code == status.HTTP_502_BAD_GATEWAY

    @patch(
        "apps.subscriptions.views.StripeService.create_portal_session",
        side_effect=stripe.error.StripeError("Stripe down"),
    )
    def test_portal_stripe_error(self, mock_svc, sub_client, free_subscription):
        """Portal returns 502 on Stripe error."""
        response = sub_client.post(
            "/api/subscriptions/subscription/portal/",
            {},
            format="json",
        )
        assert response.status_code == status.HTTP_502_BAD_GATEWAY

    @patch(
        "apps.subscriptions.views.StripeService.cancel_subscription",
        side_effect=stripe.error.StripeError("Stripe down"),
    )
    def test_cancel_stripe_error(self, mock_svc, sub_client, premium_subscription):
        """Cancel returns 502 on Stripe error."""
        response = sub_client.post("/api/subscriptions/subscription/cancel/")
        assert response.status_code == status.HTTP_502_BAD_GATEWAY

    @patch(
        "apps.subscriptions.views.StripeService.reactivate_subscription",
        side_effect=stripe.error.StripeError("Stripe down"),
    )
    def test_reactivate_stripe_error(self, mock_svc, sub_client, premium_subscription):
        """Reactivate returns 502 on Stripe error."""
        response = sub_client.post("/api/subscriptions/subscription/reactivate/")
        assert response.status_code == status.HTTP_502_BAD_GATEWAY

    @patch(
        "apps.subscriptions.views.StripeService.change_plan",
        side_effect=stripe.error.StripeError("Stripe down"),
    )
    def test_change_plan_stripe_error(self, mock_svc, sub_client, premium_subscription, pro_plan):
        """Change plan returns 502 on Stripe error."""
        response = sub_client.post(
            "/api/subscriptions/subscription/change-plan/",
            {"plan_slug": "pro"},
            format="json",
        )
        assert response.status_code == status.HTTP_502_BAD_GATEWAY

    @patch(
        "apps.subscriptions.views.StripeService.sync_subscription_status",
        side_effect=stripe.error.StripeError("Stripe down"),
    )
    def test_sync_stripe_error(self, mock_svc, sub_client, premium_subscription):
        """Sync returns 502 on Stripe error."""
        response = sub_client.post("/api/subscriptions/subscription/sync/")
        assert response.status_code == status.HTTP_502_BAD_GATEWAY

    @patch(
        "apps.subscriptions.views.StripeService.list_invoices",
        side_effect=stripe.error.StripeError("Stripe down"),
    )
    def test_invoices_stripe_error(self, mock_svc, sub_client, free_subscription):
        """Invoices returns 502 on Stripe error."""
        response = sub_client.get("/api/subscriptions/subscription/invoices/")
        assert response.status_code == status.HTTP_502_BAD_GATEWAY

    @patch(
        "apps.subscriptions.views.StripeService.apply_coupon",
        side_effect=stripe.error.StripeError("Stripe down"),
    )
    def test_apply_coupon_stripe_error(self, mock_svc, sub_client, premium_subscription):
        """Apply coupon returns 502 on Stripe error."""
        response = sub_client.post(
            "/api/subscriptions/subscription/current/apply-coupon/",
            {"coupon_code": "TEST"},
            format="json",
        )
        assert response.status_code == status.HTTP_502_BAD_GATEWAY

    @patch(
        "apps.subscriptions.views.StripeService.cancel_pending_change",
        side_effect=stripe.error.StripeError("Stripe down"),
    )
    def test_cancel_pending_stripe_error(self, mock_svc, sub_client, premium_subscription):
        """Cancel pending change returns 502 on Stripe error."""
        response = sub_client.post(
            "/api/subscriptions/subscription/cancel-pending-change/"
        )
        assert response.status_code == status.HTTP_502_BAD_GATEWAY

    @patch(
        "apps.subscriptions.views.StripeService.change_plan",
        side_effect=ValueError("requires_checkout:Need checkout flow"),
    )
    def test_change_plan_requires_checkout(self, mock_svc, sub_client, premium_subscription, pro_plan):
        """Change plan returns requires_checkout code."""
        response = sub_client.post(
            "/api/subscriptions/subscription/change-plan/",
            {"plan_slug": "pro"},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data.get("code") == "requires_checkout"


# ═══════════════════════════════════════════════════════════════════
# Checkout Free-Plan Downgrade Edge Cases
# ═══════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestCheckoutFreePlanDowngrade:
    """Tests for checkout endpoint when user selects the free plan."""

    @patch("apps.subscriptions.views.StripeService.cancel_subscription")
    def test_checkout_free_returns_404_when_no_sub(
        self, mock_cancel, sub_client, free_subscription, free_plan
    ):
        """Checking out with free plan when no active sub returns 404."""
        mock_cancel.return_value = None
        response = sub_client.post(
            "/api/subscriptions/subscription/checkout/",
            {"plan_slug": "free"},
            format="json",
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    @patch(
        "apps.subscriptions.views.StripeService.cancel_subscription",
        side_effect=stripe.error.StripeError("Stripe down"),
    )
    def test_checkout_free_stripe_error(
        self, mock_cancel, sub_client, premium_subscription, free_plan
    ):
        """Checking out with free plan with Stripe error returns 502."""
        response = sub_client.post(
            "/api/subscriptions/subscription/checkout/",
            {"plan_slug": "free"},
            format="json",
        )
        assert response.status_code == status.HTTP_502_BAD_GATEWAY
