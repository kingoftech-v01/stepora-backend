"""
Application configuration for the Social app.

Provides social features: friendships, follows, activity feeds,
and user search for the Stepora community.
"""

from django.apps import AppConfig


class SocialConfig(AppConfig):
    """Configuration for the Social application."""

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.social'
    verbose_name = 'Social'
