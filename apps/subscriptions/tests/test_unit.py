"""
Unit tests for the Subscriptions app models.
"""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.subscriptions.models import (
    Promotion,
    PromotionPlanDiscount,
    PromotionRedemption,
    Referral,
    StripeCustomer,
    StripeWebhookEvent,
    Subscription,
    SubscriptionPlan,
)
from apps.users.models import User


# ── SubscriptionPlan model ────────────────────────────────────────────


class TestSubscriptionPlanModel:
    """Tests for the SubscriptionPlan model."""

    def test_create_plan(self, free_plan):
        """SubscriptionPlan can be created with required fields."""
        assert free_plan.slug == "free"
        assert free_plan.name == "Free"
        assert free_plan.price_monthly == Decimal("0.00")

    def test_is_free_property_true(self, free_plan):
        """is_free returns True for a zero-price plan."""
        assert free_plan.is_free is True

    def test_is_free_property_false(self, premium_plan):
        """is_free returns False for a paid plan."""
        assert premium_plan.is_free is False

    def test_has_unlimited_dreams_true(self, pro_plan):
        """has_unlimited_dreams returns True when dream_limit is -1."""
        assert pro_plan.has_unlimited_dreams is True

    def test_has_unlimited_dreams_false(self, free_plan):
        """has_unlimited_dreams returns False when dream_limit is positive."""
        assert free_plan.has_unlimited_dreams is False

    def test_tier_order(self, free_plan, premium_plan, pro_plan):
        """tier_order returns correct numeric ordering."""
        assert free_plan.tier_order == 0
        assert premium_plan.tier_order == 1
        assert pro_plan.tier_order == 2

    def test_str_representation(self, premium_plan):
        """__str__ includes name and price."""
        s = str(premium_plan)
        assert "Premium" in s
        assert "19.99" in s

    def test_seed_plans(self, db):
        """seed_plans creates all default plans."""
        SubscriptionPlan.objects.all().delete()
        plans = SubscriptionPlan.seed_plans()
        assert len(plans) == 3
        slugs = {p.slug for p in plans}
        assert slugs == {"free", "premium", "pro"}

    def test_seed_plans_idempotent(self, db):
        """seed_plans can be called multiple times safely."""
        SubscriptionPlan.seed_plans()
        count_before = SubscriptionPlan.objects.count()
        SubscriptionPlan.seed_plans()
        count_after = SubscriptionPlan.objects.count()
        assert count_before == count_after

    def test_feature_flags(self, premium_plan, free_plan):
        """Premium plan has AI and buddy features, free does not."""
        assert premium_plan.has_ai is True
        assert premium_plan.has_buddy is True
        assert free_plan.has_ai is False
        assert free_plan.has_buddy is False

    def test_ordering_by_price(self, free_plan, premium_plan, pro_plan):
        """Plans are ordered by price_monthly (ascending)."""
        plans = list(SubscriptionPlan.objects.all())
        prices = [p.price_monthly for p in plans]
        assert prices == sorted(prices)


# ── Subscription model ────────────────────────────────────────────────


class TestSubscriptionModel:
    """Tests for the Subscription model."""

    def test_create_subscription(self, free_subscription, sub_user, free_plan):
        """Subscription is created with correct user and plan."""
        assert free_subscription.user == sub_user
        assert free_subscription.plan == free_plan
        assert free_subscription.status == "active"

    def test_is_active_property(self, free_subscription):
        """is_active returns True for active status."""
        free_subscription.status = "active"
        assert free_subscription.is_active is True

    def test_is_active_trialing(self, free_subscription):
        """is_active returns True for trialing status."""
        free_subscription.status = "trialing"
        assert free_subscription.is_active is True

    def test_is_active_canceled(self, free_subscription):
        """is_active returns False for canceled status."""
        free_subscription.status = "canceled"
        assert free_subscription.is_active is False

    def test_is_active_past_due(self, free_subscription):
        """is_active returns False for past_due status."""
        free_subscription.status = "past_due"
        assert free_subscription.is_active is False

    def test_str_representation(self, premium_subscription):
        """__str__ includes user email, plan name, and status."""
        s = str(premium_subscription)
        assert "subuser@example.com" in s
        assert "Premium" in s
        assert "active" in s

    def test_cancel_at_period_end(self, premium_subscription):
        """cancel_at_period_end field works correctly."""
        premium_subscription.cancel_at_period_end = True
        premium_subscription.save()
        premium_subscription.refresh_from_db()
        assert premium_subscription.cancel_at_period_end is True

    def test_pending_plan(self, premium_subscription, free_plan):
        """pending_plan can be set for scheduled downgrades."""
        premium_subscription.pending_plan = free_plan
        premium_subscription.pending_plan_effective_date = timezone.now() + timedelta(days=30)
        premium_subscription.save()
        premium_subscription.refresh_from_db()
        assert premium_subscription.pending_plan == free_plan

    def test_one_subscription_per_user(self, premium_subscription, sub_user, free_plan):
        """Only one subscription per user (OneToOneField enforced)."""
        from django.db import IntegrityError

        with pytest.raises(IntegrityError):
            Subscription.objects.create(
                user=sub_user,
                plan=free_plan,
                status="active",
            )


# ── StripeCustomer model ──────────────────────────────────────────────


class TestStripeCustomerModel:
    """Tests for the StripeCustomer model."""

    def test_create_stripe_customer(self, stripe_customer, sub_user):
        """StripeCustomer links user to Stripe ID."""
        assert stripe_customer.user == sub_user
        assert stripe_customer.stripe_customer_id == "cus_test_123"

    def test_str_representation(self, stripe_customer):
        """__str__ shows user email and Stripe ID."""
        s = str(stripe_customer)
        assert "subuser@example.com" in s
        assert "cus_test_123" in s

    def test_unique_stripe_customer_id(self, stripe_customer, sub_user2):
        """stripe_customer_id must be unique."""
        from django.db import IntegrityError

        with pytest.raises(IntegrityError):
            StripeCustomer.objects.create(
                user=sub_user2,
                stripe_customer_id="cus_test_123",
            )


# ── Promotion model ──────────────────────────────────────────────────


class TestPromotionModel:
    """Tests for the Promotion model."""

    def test_create_promotion(self, active_promotion):
        """Promotion is created with correct fields."""
        assert active_promotion.name == "Test Promo"
        assert active_promotion.discount_type == "percentage"
        assert active_promotion.is_active is True

    def test_redemption_count(self, active_promotion):
        """redemption_count returns 0 when no redemptions exist."""
        assert active_promotion.redemption_count == 0

    def test_is_exhausted_false(self, active_promotion):
        """is_exhausted returns False when below max_redemptions."""
        assert active_promotion.is_exhausted is False

    def test_is_exhausted_true(self, active_promotion, sub_user, premium_plan):
        """is_exhausted returns True when max_redemptions reached."""
        active_promotion.max_redemptions = 1
        active_promotion.save()
        discount = active_promotion.plan_discounts.first()
        PromotionRedemption.objects.create(
            promotion=active_promotion,
            user=sub_user,
            promotion_plan_discount=discount,
            stripe_coupon_id="coupon_test",
        )
        assert active_promotion.is_exhausted is True

    def test_is_exhausted_unlimited(self, db):
        """is_exhausted returns False when max_redemptions is None."""
        promo = Promotion.objects.create(
            name="Unlimited Promo",
            start_date=timezone.now(),
            discount_type="percentage",
            max_redemptions=None,
            is_active=True,
        )
        assert promo.is_exhausted is False

    def test_spots_remaining(self, active_promotion):
        """spots_remaining returns correct count."""
        assert active_promotion.spots_remaining == 100

    def test_spots_remaining_unlimited(self, db):
        """spots_remaining returns None when unlimited."""
        promo = Promotion.objects.create(
            name="Unlimited Promo",
            start_date=timezone.now(),
            discount_type="fixed_amount",
            max_redemptions=None,
            is_active=True,
        )
        assert promo.spots_remaining is None

    def test_str_representation(self, active_promotion):
        """__str__ shows name and discount type."""
        s = str(active_promotion)
        assert "Test Promo" in s
        assert "percentage" in s


# ── PromotionPlanDiscount model ───────────────────────────────────────


class TestPromotionPlanDiscountModel:
    """Tests for the PromotionPlanDiscount model."""

    def test_discounted_price_percentage(self, active_promotion, premium_plan):
        """discounted_price calculates percentage discount correctly."""
        discount = active_promotion.plan_discounts.first()
        # Premium is $19.99, 50% off = $9.995 rounded to $10.0
        expected = round(19.99 * 0.5, 2)
        assert discount.discounted_price == expected

    def test_discounted_price_fixed_amount(self, db, premium_plan):
        """discounted_price calculates fixed amount discount correctly."""
        promo = Promotion.objects.create(
            name="Fixed Promo",
            start_date=timezone.now(),
            discount_type="fixed_amount",
            is_active=True,
        )
        discount = PromotionPlanDiscount.objects.create(
            promotion=promo,
            plan=premium_plan,
            discount_value=Decimal("5.00"),
        )
        expected = round(19.99 - 5.00, 2)
        assert discount.discounted_price == expected

    def test_discounted_price_floor_zero(self, db, premium_plan):
        """discounted_price never goes below zero."""
        promo = Promotion.objects.create(
            name="Big Discount",
            start_date=timezone.now(),
            discount_type="fixed_amount",
            is_active=True,
        )
        discount = PromotionPlanDiscount.objects.create(
            promotion=promo,
            plan=premium_plan,
            discount_value=Decimal("999.99"),
        )
        assert discount.discounted_price == 0.0

    def test_str_representation(self, active_promotion):
        """__str__ shows promotion, plan, and value."""
        discount = active_promotion.plan_discounts.first()
        s = str(discount)
        assert "Test Promo" in s
        assert "Premium" in s
        assert "%" in s


# ── Referral model ────────────────────────────────────────────────────


class TestReferralModel:
    """Tests for the Referral model."""

    def test_get_referral_code(self, sub_user):
        """get_referral_code generates a deterministic code."""
        code = Referral.get_referral_code(sub_user)
        assert code.startswith("DP-REF-")
        assert len(code) == 15
        # Same user should produce the same code
        assert Referral.get_referral_code(sub_user) == code

    def test_resolve_referrer_valid(self, sub_user):
        """resolve_referrer finds the user from a valid code."""
        code = Referral.get_referral_code(sub_user)
        resolved = Referral.resolve_referrer(code)
        assert resolved is not None
        assert resolved.id == sub_user.id

    def test_resolve_referrer_invalid_code(self):
        """resolve_referrer returns None for invalid codes."""
        assert Referral.resolve_referrer("INVALID") is None
        assert Referral.resolve_referrer("") is None
        assert Referral.resolve_referrer(None) is None
        assert Referral.resolve_referrer("DP-REF-XXXXXXXX") is None  # invalid hex

    def test_get_referrer_stats(self, sub_user, sub_user2):
        """get_referrer_stats returns correct counts."""
        code = Referral.get_referral_code(sub_user)
        Referral.objects.create(
            referrer=sub_user,
            referred=sub_user2,
            referral_code=code,
            referred_has_paid=False,
        )
        stats = Referral.get_referrer_stats(sub_user)
        assert stats["total_referrals"] == 1
        assert stats["paid_referrals"] == 0
        assert stats["free_months_earned"] == 0

    def test_referrer_stats_with_paid(self, db, sub_user):
        """Stats correctly count paid referrals."""
        for i in range(3):
            referred = User.objects.create_user(
                email=f"referred{i}@example.com",
                password="testpass123",
            )
            Referral.objects.create(
                referrer=sub_user,
                referred=referred,
                referral_code=Referral.get_referral_code(sub_user),
                referred_has_paid=True,
            )
        stats = Referral.get_referrer_stats(sub_user)
        assert stats["paid_referrals"] == 3
        assert stats["free_months_earned"] == 1


# ── StripeWebhookEvent model ──────────────────────────────────────────


class TestStripeWebhookEventModel:
    """Tests for the StripeWebhookEvent model."""

    def test_create_webhook_event(self, db):
        """StripeWebhookEvent is created with correct fields."""
        event = StripeWebhookEvent.objects.create(
            stripe_event_id="evt_test_123",
            event_type="checkout.session.completed",
        )
        assert event.stripe_event_id == "evt_test_123"
        assert event.event_type == "checkout.session.completed"

    def test_unique_event_id(self, db):
        """Duplicate stripe_event_id raises IntegrityError."""
        from django.db import IntegrityError

        StripeWebhookEvent.objects.create(
            stripe_event_id="evt_dup",
            event_type="test",
        )
        with pytest.raises(IntegrityError):
            StripeWebhookEvent.objects.create(
                stripe_event_id="evt_dup",
                event_type="test",
            )
