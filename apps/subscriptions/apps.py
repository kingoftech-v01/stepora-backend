"""
App configuration for the Subscriptions app.
"""

import logging

from django.apps import AppConfig

logger = logging.getLogger(__name__)


class SubscriptionsConfig(AppConfig):
    """Configuration for the Subscriptions app handling Stripe billing."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.subscriptions"
    verbose_name = "Subscriptions"

    def ready(self):
        """Import signals and register post_migrate hook for auto-seeding."""
        from django.db.models.signals import post_migrate

        import apps.subscriptions.signals  # noqa: F401

        post_migrate.connect(_seed_plans_after_migrate, sender=self)


def _seed_plans_after_migrate(sender, **kwargs):
    """Auto-seed default subscription plans on first run (after migrate)."""
    from .models import SubscriptionPlan

    if not SubscriptionPlan.objects.exists():
        SubscriptionPlan.seed_plans()
        logger.info(
            "Auto-seeded default subscription plans (Free $0, Premium $19.99, Pro $29.99)."
        )
