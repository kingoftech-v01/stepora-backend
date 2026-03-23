"""
Tests for apps/subscriptions/signals.py — Signal handlers.

Covers:
- sync_user_subscription_field
- create_stripe_customer_on_user_creation
- auto_create_stripe_price_for_plan
- auto_sync_stripe_coupon_for_discount
- auto_resync_coupons_on_promotion_update
"""

from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from django.utils import timezone

from apps.subscriptions.models import (
    Promotion,
    PromotionPlanDiscount,
    StripeCustomer,
    Subscription,
    SubscriptionPlan,
)
from apps.users.models import User

# ── sync_user_subscription_field ─────────────────────────────────────


@pytest.mark.django_db
class TestSyncUserSubscriptionField:
    """Tests for the signal that syncs User.subscription on Subscription save."""

    def test_saves_plan_slug_on_user(self):
        """Saving a subscription updates User.subscription to the plan slug."""
        plan, _ = SubscriptionPlan.objects.get_or_create(
            slug="premium",
            defaults={"name": "Premium", "price_monthly": Decimal("19.99")},
        )
        user = User.objects.create_user(email="sync_slug@test.com", password="t")
        Subscription.objects.update_or_create(
            user=user,
            defaults={"plan": plan, "status": "active"},
        )
        user.refresh_from_db()
        assert user.subscription == "premium"

    def test_updates_on_plan_change(self):
        """Changing plan updates User.subscription."""
        free_plan, _ = SubscriptionPlan.objects.get_or_create(
            slug="free",
            defaults={"name": "Free", "price_monthly": Decimal("0.00")},
        )
        premium_plan, _ = SubscriptionPlan.objects.get_or_create(
            slug="premium",
            defaults={"name": "Premium", "price_monthly": Decimal("19.99")},
        )
        user = User.objects.create_user(email="sync_change@test.com", password="t")
        sub, _ = Subscription.objects.update_or_create(
            user=user,
            defaults={"plan": premium_plan, "status": "active"},
        )
        user.refresh_from_db()
        assert user.subscription == "premium"

        # Reload to get fresh FK reference
        sub.refresh_from_db()
        sub.plan = free_plan
        sub.save()
        db_val = User.objects.filter(pk=user.pk).values_list(
            "subscription", flat=True
        ).first()
        assert db_val == "free"


# ── create_stripe_customer_on_user_creation ──────────────────────────


@pytest.mark.django_db
class TestCreateStripeCustomerOnUserCreation:
    """Tests for the post_save signal on User that creates StripeCustomer."""

    @patch("apps.subscriptions.services.stripe.Customer.create")
    def test_creates_customer_for_new_user(self, mock_stripe_create):
        """New user creation triggers Stripe customer creation."""
        SubscriptionPlan.objects.get_or_create(
            slug="free",
            defaults={"name": "Free", "price_monthly": Decimal("0.00")},
        )
        mock_stripe_create.return_value = MagicMock(id="cus_signal_test")
        user = User.objects.create_user(
            email="signal_cust@test.com", password="t"
        )
        sc = StripeCustomer.objects.filter(user=user).first()
        assert sc is not None
        assert sc.stripe_customer_id == "cus_signal_test"

    @patch("apps.subscriptions.services.stripe.Customer.create")
    def test_creates_free_subscription(self, mock_stripe_create):
        """New user gets a free subscription automatically."""
        free_plan, _ = SubscriptionPlan.objects.get_or_create(
            slug="free",
            defaults={"name": "Free", "price_monthly": Decimal("0.00")},
        )
        mock_stripe_create.return_value = MagicMock(id="cus_free_sub")
        user = User.objects.create_user(
            email="signal_freesub@test.com", password="t"
        )
        sub = Subscription.objects.filter(user=user).first()
        assert sub is not None
        assert sub.plan == free_plan
        assert sub.status == "active"

    @patch("apps.subscriptions.services.stripe.Customer.create")
    @patch("apps.subscriptions.services.stripe.Customer.retrieve")
    def test_does_not_create_customer_on_update(
        self, mock_retrieve, mock_create
    ):
        """Updating an existing user does not create a new Stripe customer."""
        SubscriptionPlan.objects.get_or_create(
            slug="free",
            defaults={"name": "Free", "price_monthly": Decimal("0.00")},
        )
        mock_create.return_value = MagicMock(id="cus_once")
        user = User.objects.create_user(
            email="signal_noupdate@test.com", password="t"
        )
        mock_create.reset_mock()
        mock_retrieve.reset_mock()

        user.display_name = "Updated"
        user.save()
        mock_create.assert_not_called()

    @patch(
        "apps.subscriptions.services.stripe.Customer.create",
        side_effect=Exception("Stripe down"),
    )
    def test_user_creation_succeeds_even_if_stripe_fails(self, mock_create):
        """User registration does not fail when Stripe is unreachable."""
        SubscriptionPlan.objects.get_or_create(
            slug="free",
            defaults={"name": "Free", "price_monthly": Decimal("0.00")},
        )
        user = User.objects.create_user(
            email="signal_stripe_fail@test.com", password="t"
        )
        assert user.pk is not None


# ── auto_create_stripe_price_for_plan ────────────────────────────────


@pytest.mark.django_db
class TestAutoCreateStripePriceForPlan:
    """Tests for the signal that auto-creates Stripe prices for plans."""

    @patch("stripe.api_key", "sk_test_fake")
    @patch("apps.subscriptions.services.stripe.Price.create")
    @patch("apps.subscriptions.services.stripe.Product.create")
    def test_auto_creates_price_for_paid_plan(self, mock_product, mock_price):
        """Saving a paid plan without stripe_price_id auto-creates it."""
        mock_product.return_value = MagicMock(id="prod_auto")
        mock_price.return_value = MagicMock(id="price_auto")

        plan = SubscriptionPlan.objects.create(
            name="AutoPrice",
            slug="autoprice_sig",
            price_monthly=Decimal("14.99"),
            stripe_price_id="",
        )
        plan.refresh_from_db()
        assert plan.stripe_price_id == "price_auto"

    def test_skips_free_plan(self):
        """Signal does not create Stripe price for the free plan."""
        with patch("stripe.api_key", "sk_test"):
            plan, created = SubscriptionPlan.objects.get_or_create(
                slug="free_nosignal",
                defaults={
                    "name": "Free NoSignal",
                    "price_monthly": Decimal("0.00"),
                    "stripe_price_id": "",
                },
            )
            if not created:
                plan.stripe_price_id = ""
                plan.save()
            plan.refresh_from_db()
            assert plan.stripe_price_id == ""

    def test_skips_if_price_already_set(self):
        """Signal does not overwrite an existing stripe_price_id."""
        with patch("stripe.api_key", "sk_test"):
            plan = SubscriptionPlan.objects.create(
                slug="priceset_sig",
                name="PriceSet",
                price_monthly=Decimal("19.99"),
                stripe_price_id="price_existing",
            )
            plan.refresh_from_db()
            assert plan.stripe_price_id == "price_existing"

    def test_skips_if_no_stripe_key(self):
        """Signal does not try to create price when stripe.api_key is empty."""
        with patch("stripe.api_key", ""):
            plan = SubscriptionPlan.objects.create(
                name="NoKey",
                slug="nokey_sig",
                price_monthly=Decimal("9.99"),
                stripe_price_id="",
            )
            plan.refresh_from_db()
            assert plan.stripe_price_id == ""


# ── auto_sync_stripe_coupon_for_discount ─────────────────────────────


@pytest.mark.django_db
class TestAutoSyncStripeCouponForDiscount:
    """Tests for the signal that auto-creates Stripe coupons for discounts."""

    @patch("stripe.api_key", "sk_test_fake")
    @patch("apps.subscriptions.services.stripe.Coupon.create")
    def test_creates_coupon_for_new_discount(self, mock_coupon):
        """Saving a new PromotionPlanDiscount creates a Stripe coupon."""
        mock_coupon.return_value = MagicMock(id="coupon_sig_new")
        plan, _ = SubscriptionPlan.objects.get_or_create(
            slug="premium",
            defaults={"name": "Premium", "price_monthly": Decimal("19.99")},
        )
        promo = Promotion.objects.create(
            name="Coupon Signal Promo",
            start_date=timezone.now(),
            discount_type="percentage",
            is_active=True,
        )
        discount = PromotionPlanDiscount.objects.create(
            promotion=promo,
            plan=plan,
            discount_value=Decimal("25.00"),
            stripe_coupon_id="",
        )
        discount.refresh_from_db()
        assert discount.stripe_coupon_id == "coupon_sig_new"

    @patch("stripe.api_key", "sk_test_fake")
    @patch("apps.subscriptions.services.stripe.Coupon.create")
    @patch("apps.subscriptions.services.stripe.Coupon.delete")
    def test_recreates_coupon_on_update(self, mock_delete, mock_create):
        """Updating a discount with existing coupon recreates it."""
        mock_create.return_value = MagicMock(id="coupon_sig_recreated")
        plan, _ = SubscriptionPlan.objects.get_or_create(
            slug="premium",
            defaults={"name": "Premium", "price_monthly": Decimal("19.99")},
        )
        promo = Promotion.objects.create(
            name="Recreate Signal Promo",
            start_date=timezone.now(),
            discount_type="percentage",
            is_active=True,
        )
        # Create discount — signal fires and creates a coupon
        discount = PromotionPlanDiscount.objects.create(
            promotion=promo,
            plan=plan,
            discount_value=Decimal("30.00"),
            stripe_coupon_id="",
        )
        discount.refresh_from_db()
        first_coupon = discount.stripe_coupon_id

        # Now update the discount value — signal should recreate
        mock_create.reset_mock()
        mock_delete.reset_mock()
        mock_create.return_value = MagicMock(id="coupon_sig_updated")

        discount.discount_value = Decimal("40.00")
        discount.save()
        discount.refresh_from_db()
        assert discount.stripe_coupon_id == "coupon_sig_updated"
        mock_delete.assert_called_once_with(first_coupon)

    def test_skips_if_no_stripe_key(self):
        """Signal does not create coupon when stripe.api_key is empty."""
        with patch("stripe.api_key", ""):
            plan, _ = SubscriptionPlan.objects.get_or_create(
                slug="premium",
                defaults={"name": "Premium", "price_monthly": Decimal("19.99")},
            )
            promo = Promotion.objects.create(
                name="NoKey Coupon",
                start_date=timezone.now(),
                discount_type="percentage",
                is_active=True,
            )
            discount = PromotionPlanDiscount.objects.create(
                promotion=promo,
                plan=plan,
                discount_value=Decimal("10.00"),
                stripe_coupon_id="",
            )
            discount.refresh_from_db()
            assert discount.stripe_coupon_id == ""


# ── auto_resync_coupons_on_promotion_update ──────────────────────────


@pytest.mark.django_db
class TestAutoResyncCouponsOnPromotionUpdate:
    """Tests for the signal that resyncs coupons when a Promotion is updated."""

    @patch("stripe.api_key", "sk_test_fake")
    @patch("apps.subscriptions.services.stripe.Coupon.create")
    @patch("apps.subscriptions.services.stripe.Coupon.delete")
    def test_resyncs_coupons_on_promotion_update(self, mock_delete, mock_create):
        """Updating a Promotion recreates all related Stripe coupons."""
        mock_create.return_value = MagicMock(id="coupon_initial")
        plan, _ = SubscriptionPlan.objects.get_or_create(
            slug="premium",
            defaults={"name": "Premium", "price_monthly": Decimal("19.99")},
        )
        promo = Promotion.objects.create(
            name="Resync Signal Promo",
            start_date=timezone.now(),
            discount_type="percentage",
            is_active=True,
        )
        # Create discount (signal fires, creates coupon)
        discount = PromotionPlanDiscount.objects.create(
            promotion=promo,
            plan=plan,
            discount_value=Decimal("20.00"),
            stripe_coupon_id="",
        )
        discount.refresh_from_db()
        initial_coupon = discount.stripe_coupon_id

        mock_create.reset_mock()
        mock_delete.reset_mock()
        mock_create.return_value = MagicMock(id="coupon_resynced")

        # Update the promotion name — triggers resync signal
        promo.name = "Updated Resync Signal Promo"
        promo.save()

        discount.refresh_from_db()
        assert discount.stripe_coupon_id == "coupon_resynced"
        mock_delete.assert_called_once_with(initial_coupon)

    @patch("stripe.api_key", "sk_test_fake")
    def test_does_not_resync_on_creation(self):
        """Signal does not resync coupons when Promotion is first created."""
        promo = Promotion.objects.create(
            name="New Promo No Resync Sig",
            start_date=timezone.now(),
            discount_type="percentage",
            is_active=True,
        )
        assert promo.pk is not None
