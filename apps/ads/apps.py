"""App configuration for the Ads app."""

from django.apps import AppConfig


class AdsConfig(AppConfig):
    """Configuration for the ads application."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.ads"
    verbose_name = "Ads"
