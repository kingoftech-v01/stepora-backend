"""Management command to seed subscription plans."""

from django.core.management.base import BaseCommand
from apps.subscriptions.models import SubscriptionPlan


class Command(BaseCommand):
    help = 'Seed the default subscription plans (Free, Premium, Pro)'

    def handle(self, *args, **options):
        plans = SubscriptionPlan.seed_plans()
        for plan in plans:
            self.stdout.write(self.style.SUCCESS(f'  {plan.name} - ${plan.price_monthly}/mo'))
        self.stdout.write(self.style.SUCCESS(f'Seeded {len(plans)} subscription plans.'))
