"""
Django application configuration for the Store app.

Handles cosmetic item purchases including badge frames, theme skins,
avatar decorations, chat bubbles, and power-ups via Stripe one-time payments.
"""

from django.apps import AppConfig


class StoreConfig(AppConfig):
    """Configuration for the in-app store application."""

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.store'
    verbose_name = 'Store'

    def ready(self):
        """Perform initialization when the app is ready."""
        pass
