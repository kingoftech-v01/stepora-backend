"""
Signals for the Subscriptions app.

- Creates a free Subscription + Stripe customer when a new User is registered.
- Keeps User.subscription CharField in sync whenever a Subscription is saved.
"""

import logging

from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver

logger = logging.getLogger(__name__)


@receiver(post_save, sender="subscriptions.Subscription")
def sync_user_subscription_field(sender, instance, **kwargs):
    """
    Keep User.subscription CharField in sync with the Subscription model.

    This fires whenever a Subscription row is saved (webhook, admin, code).
    The CharField is a denormalized cache used by permission classes for
    fast reads — the Subscription model remains the source of truth.
    """
    try:
        user = instance.user
        new_slug = instance.plan.slug if instance.plan else "free"
        if getattr(user, "subscription", None) != new_slug:
            type(user).objects.filter(pk=user.pk).update(subscription=new_slug)
    except Exception:
        logger.exception(
            "Failed to sync User.subscription for subscription %s",
            instance.pk,
        )


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_stripe_customer_on_user_creation(sender, instance, created, **kwargs):
    """
    Create a Stripe customer when a new User is created.

    We import the service lazily inside the handler to avoid circular
    imports and to allow the signal to be registered at app startup
    without pulling in the full Stripe SDK.

    The Stripe API call is wrapped in a try/except so that user
    registration never fails due to a transient Stripe outage.
    Customers that fail to create here will be created lazily when
    they first attempt a checkout.

    Args:
        sender: The User model class.
        instance: The User instance that was saved.
        created: True if this is a newly created record.
        **kwargs: Extra signal arguments.
    """
    if not created:
        return

    # Create a free-tier Subscription so every user has one from day one.
    try:
        from .models import Subscription, SubscriptionPlan

        free_plan = SubscriptionPlan.objects.filter(slug="free").first()
        if free_plan:
            Subscription.objects.get_or_create(
                user=instance,
                defaults={
                    "plan": free_plan,
                    "status": "active",
                    "stripe_subscription_id": "",
                },
            )
            logger.info("Free subscription created for new user %s", instance.email)
    except Exception:
        logger.exception(
            "Failed to create free subscription for user %s.",
            instance.email,
        )

    try:
        from .services import StripeService

        StripeService.create_customer(instance)
        logger.info("Stripe customer created for new user %s", instance.email)
    except Exception:
        # Do not block user registration if Stripe is unreachable.
        # The customer will be created lazily at checkout time.
        logger.exception(
            "Failed to create Stripe customer for new user %s. "
            "Will retry at checkout time.",
            instance.email,
        )


@receiver(post_save, sender="subscriptions.SubscriptionPlan")
def auto_create_stripe_price_for_plan(sender, instance, **kwargs):
    """
    Auto-create a Stripe Product + Price when a plan is saved with
    an empty stripe_price_id. Zero manual Stripe configuration needed.
    """
    import stripe as _stripe

    # Guard against recursive signal from our own save(update_fields=...)
    update_fields = kwargs.get("update_fields")
    if update_fields and "stripe_price_id" in update_fields:
        return

    # Skip if already has a price, is free, or no Stripe key configured
    if instance.stripe_price_id or instance.is_free or not _stripe.api_key:
        return

    try:
        from .services import PromotionService

        price_id = PromotionService.create_stripe_price_for_plan(instance)
        instance.stripe_price_id = price_id
        instance.save(update_fields=["stripe_price_id", "updated_at"])
        logger.info(
            "Auto-created Stripe price %s for plan '%s'",
            price_id,
            instance.name,
        )
    except Exception:
        logger.exception(
            "Failed to auto-create Stripe price for plan '%s'. "
            "Set stripe_price_id manually or retry.",
            instance.name,
        )


@receiver(post_save, sender="subscriptions.PromotionPlanDiscount")
def auto_create_stripe_coupon_for_discount(sender, instance, **kwargs):
    """
    Auto-create a Stripe Coupon when a PromotionPlanDiscount is saved
    with an empty stripe_coupon_id.
    """
    import stripe as _stripe

    # Guard against recursive signal
    update_fields = kwargs.get("update_fields")
    if update_fields and "stripe_coupon_id" in update_fields:
        return

    if instance.stripe_coupon_id or not _stripe.api_key:
        return

    try:
        from .services import PromotionService

        coupon_id = PromotionService.create_stripe_coupon(instance)
        instance.stripe_coupon_id = coupon_id
        instance.save(update_fields=["stripe_coupon_id", "updated_at"])
        logger.info(
            "Auto-created Stripe coupon %s for promotion '%s' plan '%s'",
            coupon_id,
            instance.promotion.name,
            instance.plan.name,
        )
    except Exception:
        logger.exception(
            "Failed to auto-create Stripe coupon for promotion '%s' plan '%s'.",
            instance.promotion.name,
            instance.plan.name,
        )
