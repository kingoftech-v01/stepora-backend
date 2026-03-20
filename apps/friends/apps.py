"""App config for Friends."""

from django.apps import AppConfig


class FriendsConfig(AppConfig):
    name = "apps.friends"
    label = "friends"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self):
        import apps.friends.signals  # noqa: F401
