"""Management command to ensure Stripe webhook endpoint is configured."""

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Ensure Stripe webhook endpoint exists and secret is configured."

    def add_arguments(self, parser):
        parser.add_argument(
            "--url",
            type=str,
            default="",
            help="Override webhook URL (auto-detected if empty)",
        )

    def handle(self, *args, **options):
        from apps.subscriptions.services import StripeService

        url = options["url"]
        secret = StripeService.ensure_webhook(webhook_url=url)

        if secret:
            self.stdout.write(
                self.style.SUCCESS("Stripe webhook configured successfully.")
            )
        else:
            self.stdout.write(
                self.style.WARNING(
                    "Stripe webhook not configured. Check logs for details."
                )
            )
