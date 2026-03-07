"""
Signals for the Subscriptions app.

Automatically creates a Stripe customer record when a new User is saved
for the first time. This ensures every user in the system has a
corresponding Stripe customer, which simplifies checkout and billing
operations later.
"""

import logging

from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver

logger = logging.getLogger(__name__)


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
        from .models import SubscriptionPlan, Subscription
        free_plan = SubscriptionPlan.objects.filter(slug='free').first()
        if free_plan:
            Subscription.objects.get_or_create(
                user=instance,
                defaults={
                    'plan': free_plan,
                    'status': 'active',
                    'stripe_subscription_id': '',
                },
            )
            logger.info(
                "Free subscription created for new user %s", instance.email
            )
    except Exception:
        logger.exception(
            "Failed to create free subscription for user %s.",
            instance.email,
        )

    try:
        from .services import StripeService
        StripeService.create_customer(instance)
        logger.info(
            "Stripe customer created for new user %s", instance.email
        )
    except Exception:
        # Do not block user registration if Stripe is unreachable.
        # The customer will be created lazily at checkout time.
        logger.exception(
            "Failed to create Stripe customer for new user %s. "
            "Will retry at checkout time.",
            instance.email,
        )
