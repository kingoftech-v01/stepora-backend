"""App config for Gamification."""

from django.apps import AppConfig


class GamificationConfig(AppConfig):
    name = "apps.gamification"
    label = "gamification"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self):
        import apps.gamification.signals  # noqa: F401
