"""
Application configuration for the Dreams app.

Provides dream creation, goal/task management, AI-powered planning,
calibration, vision boards, and progress tracking.
"""

from django.apps import AppConfig


class DreamsConfig(AppConfig):
    """Configuration for the Dreams application."""

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.dreams'
    verbose_name = 'Dreams'

    def ready(self):
        """Import signals when the app is ready."""
        import apps.dreams.signals  # noqa: F401
