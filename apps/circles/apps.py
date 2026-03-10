"""
Application configuration for the Circles app.

Provides Dream Circles: small groups of users who share goals,
post updates, and participate in challenges together.
"""

from django.apps import AppConfig


class CirclesConfig(AppConfig):
    """Configuration for the Circles application."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.circles"
    verbose_name = "Dream Circles"
