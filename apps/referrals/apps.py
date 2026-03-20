"""App config for Referrals."""

from django.apps import AppConfig


class ReferralsConfig(AppConfig):
    name = "apps.referrals"
    label = "referrals"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self):
        import apps.referrals.signals  # noqa: F401
