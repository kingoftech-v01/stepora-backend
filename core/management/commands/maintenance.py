"""
Management command to toggle maintenance mode via Redis cache.

Usage:
    python manage.py maintenance on      # Enable (auto-expires after 1 hour)
    python manage.py maintenance off     # Disable
    python manage.py maintenance status  # Check current status
"""

from django.core.cache import cache
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Toggle maintenance mode on/off via Redis cache"

    def add_arguments(self, parser):
        parser.add_argument(
            "action",
            choices=["on", "off", "status"],
            help="on = enable, off = disable, status = check current state",
        )
        parser.add_argument(
            "--timeout",
            type=int,
            default=3600,
            help="Auto-expire timeout in seconds (default: 3600 = 1 hour)",
        )

    def handle(self, *args, **options):
        action = options["action"]

        if action == "on":
            timeout = options["timeout"]
            cache.set("maintenance_mode", True, timeout=timeout)
            self.stdout.write(
                self.style.WARNING(
                    f"Maintenance mode ON (auto-expires in {timeout}s)"
                )
            )
        elif action == "off":
            cache.delete("maintenance_mode")
            self.stdout.write(self.style.SUCCESS("Maintenance mode OFF"))
        else:
            is_on = cache.get("maintenance_mode", False)
            self.stdout.write(
                f'Maintenance mode: {"ON" if is_on else "OFF"}'
            )
