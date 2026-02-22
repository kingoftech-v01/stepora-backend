"""
Management command to seed leagues and create an initial season.

Creates the seven league tiers (Bronze through Legend) with their
XP ranges, colors, and default rewards. Also creates an initial
active season if none exists.

Usage:
    python manage.py seed_leagues
    python manage.py seed_leagues --force  # Recreate even if leagues exist
"""

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone as django_timezone

from apps.leagues.models import League, Season


# League seed data: tier, name, min_xp, max_xp, color_hex, description, rewards
LEAGUE_SEED_DATA = [
    {
        'tier': 'bronze',
        'name': 'Bronze League',
        'min_xp': 0,
        'max_xp': 499,
        'color_hex': '#CD7F32',
        'icon_url': '',
        'description': (
            'The starting league for all dreamers. Complete tasks and earn XP '
            'to climb the ranks. Every journey begins with a single step.'
        ),
        'rewards': [
            {'type': 'badge', 'name': 'Bronze Dreamer', 'icon': 'badge_bronze'},
            {'type': 'title', 'name': 'Apprentice Dreamer'},
        ],
    },
    {
        'tier': 'silver',
        'name': 'Silver League',
        'min_xp': 500,
        'max_xp': 1499,
        'color_hex': '#C0C0C0',
        'icon_url': '',
        'description': (
            'You have proven your dedication. Silver League dreamers are building '
            'momentum and developing strong habits.'
        ),
        'rewards': [
            {'type': 'badge', 'name': 'Silver Dreamer', 'icon': 'badge_silver'},
            {'type': 'title', 'name': 'Dedicated Dreamer'},
            {'type': 'xp_boost', 'name': '5% XP Boost', 'value': 0.05},
        ],
    },
    {
        'tier': 'gold',
        'name': 'Gold League',
        'min_xp': 1500,
        'max_xp': 3499,
        'color_hex': '#FFD700',
        'icon_url': '',
        'description': (
            'Gold League is for committed achievers. You are consistently '
            'turning dreams into reality with determination and focus.'
        ),
        'rewards': [
            {'type': 'badge', 'name': 'Gold Dreamer', 'icon': 'badge_gold'},
            {'type': 'title', 'name': 'Ambitious Dreamer'},
            {'type': 'xp_boost', 'name': '10% XP Boost', 'value': 0.10},
            {'type': 'feature', 'name': 'Custom Profile Frame'},
        ],
    },
    {
        'tier': 'platinum',
        'name': 'Platinum League',
        'min_xp': 3500,
        'max_xp': 6999,
        'color_hex': '#E5E4E2',
        'icon_url': '',
        'description': (
            'Platinum League dreamers are elite achievers. Your consistency '
            'and dedication set you apart from the crowd.'
        ),
        'rewards': [
            {'type': 'badge', 'name': 'Platinum Dreamer', 'icon': 'badge_platinum'},
            {'type': 'title', 'name': 'Elite Dreamer'},
            {'type': 'xp_boost', 'name': '15% XP Boost', 'value': 0.15},
            {'type': 'feature', 'name': 'Animated Profile Frame'},
            {'type': 'streak_joker', 'name': 'Bonus Streak Joker', 'value': 1},
        ],
    },
    {
        'tier': 'diamond',
        'name': 'Diamond League',
        'min_xp': 7000,
        'max_xp': 11999,
        'color_hex': '#B9F2FF',
        'icon_url': '',
        'description': (
            'Diamond League is reserved for exceptional dreamers. You have '
            'demonstrated extraordinary commitment to your goals.'
        ),
        'rewards': [
            {'type': 'badge', 'name': 'Diamond Dreamer', 'icon': 'badge_diamond'},
            {'type': 'title', 'name': 'Visionary Dreamer'},
            {'type': 'xp_boost', 'name': '20% XP Boost', 'value': 0.20},
            {'type': 'feature', 'name': 'Diamond Profile Effects'},
            {'type': 'streak_joker', 'name': 'Bonus Streak Jokers', 'value': 2},
        ],
    },
    {
        'tier': 'master',
        'name': 'Master League',
        'min_xp': 12000,
        'max_xp': 19999,
        'color_hex': '#9B59B6',
        'icon_url': '',
        'description': (
            'Master League dreamers are among the very best. Your mastery '
            'of goal-setting and execution is truly inspiring.'
        ),
        'rewards': [
            {'type': 'badge', 'name': 'Master Dreamer', 'icon': 'badge_master'},
            {'type': 'title', 'name': 'Master Dreamer'},
            {'type': 'xp_boost', 'name': '25% XP Boost', 'value': 0.25},
            {'type': 'feature', 'name': 'Master Profile Aura'},
            {'type': 'streak_joker', 'name': 'Bonus Streak Jokers', 'value': 3},
            {'type': 'feature', 'name': 'Priority AI Coaching'},
        ],
    },
    {
        'tier': 'legend',
        'name': 'Legend League',
        'min_xp': 20000,
        'max_xp': None,
        'color_hex': '#FF6B35',
        'icon_url': '',
        'description': (
            'Legend League is the pinnacle of achievement. You are a living '
            'testament to what happens when dreams meet relentless action. '
            'Your legacy inspires others to dream bigger.'
        ),
        'rewards': [
            {'type': 'badge', 'name': 'Legend Dreamer', 'icon': 'badge_legend'},
            {'type': 'title', 'name': 'Living Legend'},
            {'type': 'xp_boost', 'name': '30% XP Boost', 'value': 0.30},
            {'type': 'feature', 'name': 'Legendary Profile Effects'},
            {'type': 'streak_joker', 'name': 'Bonus Streak Jokers', 'value': 5},
            {'type': 'feature', 'name': 'Priority AI Coaching'},
            {'type': 'feature', 'name': 'Legend Hall of Fame'},
        ],
    },
]


class Command(BaseCommand):
    """
    Seed the database with league tiers and an initial season.

    Creates seven league tiers from Bronze to Legend with appropriate
    XP ranges, colors, descriptions, and rewards. Also creates an
    initial active season if none exists.
    """

    help = 'Seed league tiers and create an initial season.'

    def add_arguments(self, parser):
        """Add command-line arguments."""
        parser.add_argument(
            '--force',
            action='store_true',
            help='Delete existing leagues and recreate them.',
        )

    def handle(self, *args, **options):
        """Execute the command."""
        force = options.get('force', False)

        self._seed_leagues(force)
        self._seed_initial_season()

        self.stdout.write(
            self.style.SUCCESS('Successfully seeded leagues and initial season.')
        )

    def _seed_leagues(self, force: bool) -> None:
        """
        Create or update league tiers in the database.

        Args:
            force: If True, delete all existing leagues before seeding.
        """
        if force:
            deleted_count, _ = League.objects.all().delete()
            self.stdout.write(
                self.style.WARNING(f'Deleted {deleted_count} existing leagues.')
            )

        existing_count = League.objects.count()
        if existing_count > 0 and not force:
            self.stdout.write(
                self.style.NOTICE(
                    f'{existing_count} leagues already exist. '
                    'Use --force to recreate them.'
                )
            )
            return

        for data in LEAGUE_SEED_DATA:
            league, created = League.objects.update_or_create(
                tier=data['tier'],
                defaults={
                    'name': data['name'],
                    'min_xp': data['min_xp'],
                    'max_xp': data['max_xp'],
                    'color_hex': data['color_hex'],
                    'icon_url': data['icon_url'],
                    'description': data['description'],
                    'rewards': data['rewards'],
                },
            )

            action_str = 'Created' if created else 'Updated'
            xp_range = (
                f"{data['min_xp']}-{data['max_xp']}"
                if data['max_xp'] is not None
                else f"{data['min_xp']}+"
            )
            self.stdout.write(
                f"  {action_str} {league.name} ({xp_range} XP) {data['color_hex']}"
            )

        self.stdout.write(
            self.style.SUCCESS(f'Seeded {len(LEAGUE_SEED_DATA)} leagues.')
        )

    def _seed_initial_season(self) -> None:
        """Create an initial active season if none exists."""
        active_season = Season.get_active_season()
        if active_season:
            self.stdout.write(
                self.style.NOTICE(
                    f'Active season already exists: "{active_season.name}". '
                    'Skipping initial season creation.'
                )
            )
            return

        now = django_timezone.now()
        season = Season.objects.create(
            name='Season 1 - Winter 2026',
            start_date=now,
            end_date=now + timedelta(days=90),
            is_active=True,
            rewards=[
                {
                    'tier': 'bronze',
                    'rewards': ['Bronze Season Badge'],
                },
                {
                    'tier': 'silver',
                    'rewards': ['Silver Season Badge', '100 Bonus XP'],
                },
                {
                    'tier': 'gold',
                    'rewards': ['Gold Season Badge', '250 Bonus XP', 'Gold Frame'],
                },
                {
                    'tier': 'platinum',
                    'rewards': ['Platinum Season Badge', '500 Bonus XP', 'Platinum Frame'],
                },
                {
                    'tier': 'diamond',
                    'rewards': ['Diamond Season Badge', '1000 Bonus XP', 'Diamond Frame', 'Streak Joker'],
                },
                {
                    'tier': 'master',
                    'rewards': ['Master Season Badge', '2000 Bonus XP', 'Master Frame', '2 Streak Jokers'],
                },
                {
                    'tier': 'legend',
                    'rewards': ['Legend Season Badge', '5000 Bonus XP', 'Legend Frame', '3 Streak Jokers', 'Hall of Fame Entry'],
                },
            ],
        )

        self.stdout.write(
            self.style.SUCCESS(
                f'Created initial season: "{season.name}" '
                f'(ends {season.end_date.strftime("%Y-%m-%d")}).'
            )
        )
