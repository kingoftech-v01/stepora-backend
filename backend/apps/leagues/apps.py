"""
Application configuration for the Leagues app.

Provides competitive ranking system with leagues, leaderboards,
seasons, and rewards. Users can see others' scores and badges
but NOT their dreams.
"""

from django.apps import AppConfig


class LeaguesConfig(AppConfig):
    """Configuration for the Leagues application."""

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.leagues'
    verbose_name = 'Leagues & Rankings'

    def ready(self):
        """Import signals when the app is ready."""
        import apps.leagues.signals  # noqa: F401
