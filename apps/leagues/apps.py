"""
Application configuration for the Leagues app.

Provides competitive ranking system with leagues, leaderboards,
seasons, and rewards. Users can see others' scores and badges
but NOT their dreams.
"""

import logging

from django.apps import AppConfig

logger = logging.getLogger(__name__)


class LeaguesConfig(AppConfig):
    """Configuration for the Leagues application."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.leagues"
    verbose_name = "Leagues & Rankings"

    def ready(self):
        """Import signals and register post_migrate hook for auto-seeding."""
        from django.db.models.signals import post_migrate

        import apps.leagues.signals  # noqa: F401

        post_migrate.connect(_seed_leagues_after_migrate, sender=self)


def _seed_leagues_after_migrate(sender, **kwargs):
    """Auto-seed default leagues on first run (after migrate)."""
    from .models import League

    if not League.objects.exists():
        League.seed_defaults()
        logger.info("Auto-seeded default leagues (Bronze → Legend).")
