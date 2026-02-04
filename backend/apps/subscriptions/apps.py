"""
App configuration for the Subscriptions app.
"""

from django.apps import AppConfig


class SubscriptionsConfig(AppConfig):
    """Configuration for the Subscriptions app handling Stripe billing."""

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.subscriptions'
    verbose_name = 'Subscriptions'

    def ready(self):
        """Import signals when the app is ready."""
        import apps.subscriptions.signals  # noqa: F401
