"""App config for Plans."""

from django.apps import AppConfig


class PlanConfig(AppConfig):
    name = "apps.plans"
    label = "plans"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self):
        import apps.plans.signals  # noqa: F401
