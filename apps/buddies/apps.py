"""
Application configuration for the Buddies app.

Provides Dream Buddy pairing: accountability partners who share goals,
track progress together, and encourage each other.
"""

from django.apps import AppConfig


class BuddiesConfig(AppConfig):
    """Configuration for the Buddies application."""

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.buddies'
    verbose_name = 'Dream Buddies'
