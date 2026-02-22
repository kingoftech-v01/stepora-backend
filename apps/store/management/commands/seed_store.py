"""
Management command to seed the store with initial categories and items.

Populates the database with default store categories (Badge Frames,
Theme Skins, Avatar Decorations, Chat Bubbles, Power-ups) and a curated
set of at least 15 cosmetic items across all categories. Safe to run
multiple times -- uses get_or_create to avoid duplicates.
"""

from decimal import Decimal

from django.core.management.base import BaseCommand
from django.utils.text import slugify

from apps.store.models import StoreCategory, StoreItem


# Seed data for store categories
CATEGORIES = [
    {
        'name': 'Badge Frames',
        'slug': 'badge-frames',
        'description': 'Customize the frame around your profile badge with unique styles and effects.',
        'icon': 'badge-frame',
        'display_order': 1,
    },
    {
        'name': 'Theme Skins',
        'slug': 'theme-skins',
        'description': 'Transform the look and feel of your entire app with stunning themes.',
        'icon': 'theme-skin',
        'display_order': 2,
    },
    {
        'name': 'Avatar Decorations',
        'slug': 'avatar-decorations',
        'description': 'Add eye-catching decorations around your avatar to stand out.',
        'icon': 'avatar-decoration',
        'display_order': 3,
    },
    {
        'name': 'Chat Bubbles',
        'slug': 'chat-bubbles',
        'description': 'Personalize your chat messages with unique bubble styles.',
        'icon': 'chat-bubble',
        'display_order': 4,
    },
    {
        'name': 'Power-ups',
        'slug': 'power-ups',
        'description': 'Boost your progress with powerful one-time-use items.',
        'icon': 'power-up',
        'display_order': 5,
    },
]

# Seed data for store items
ITEMS = [
    # Badge Frames
    {
        'category_slug': 'badge-frames',
        'name': 'Gold Frame',
        'slug': 'gold-frame',
        'description': 'A sleek golden frame that adds a touch of elegance to your badge.',
        'price': Decimal('2.99'),
        'item_type': 'badge_frame',
        'rarity': 'rare',
        'metadata': {'color': '#FFD700', 'animation': 'shimmer'},
    },
    {
        'category_slug': 'badge-frames',
        'name': 'Diamond Frame',
        'slug': 'diamond-frame',
        'description': 'A dazzling diamond-encrusted frame that sparkles with brilliance.',
        'price': Decimal('4.99'),
        'item_type': 'badge_frame',
        'rarity': 'epic',
        'metadata': {'color': '#B9F2FF', 'animation': 'sparkle'},
    },
    {
        'category_slug': 'badge-frames',
        'name': 'Rainbow Frame',
        'slug': 'rainbow-frame',
        'description': 'A legendary animated frame cycling through all colors of the rainbow.',
        'price': Decimal('9.99'),
        'item_type': 'badge_frame',
        'rarity': 'legendary',
        'metadata': {
            'colors': ['#FF0000', '#FF7F00', '#FFFF00', '#00FF00', '#0000FF', '#4B0082', '#9400D3'],
            'animation': 'rainbow-cycle',
        },
    },
    {
        'category_slug': 'badge-frames',
        'name': 'Silver Frame',
        'slug': 'silver-frame',
        'description': 'A clean silver frame for a subtle yet polished look.',
        'price': Decimal('1.99'),
        'item_type': 'badge_frame',
        'rarity': 'common',
        'metadata': {'color': '#C0C0C0', 'animation': 'none'},
    },
    {
        'category_slug': 'badge-frames',
        'name': 'Neon Frame',
        'slug': 'neon-frame',
        'description': 'A vibrant neon-glowing frame that pulses with electric energy.',
        'price': Decimal('3.99'),
        'item_type': 'badge_frame',
        'rarity': 'rare',
        'metadata': {'color': '#39FF14', 'animation': 'neon-pulse'},
    },
    # Theme Skins
    {
        'category_slug': 'theme-skins',
        'name': 'Dark Galaxy',
        'slug': 'dark-galaxy',
        'description': 'Immerse yourself in a deep-space galaxy theme with swirling nebulae.',
        'price': Decimal('4.99'),
        'item_type': 'theme_skin',
        'rarity': 'epic',
        'metadata': {
            'primary_color': '#0D0221',
            'secondary_color': '#541388',
            'accent_color': '#D100D1',
            'background': 'galaxy-animated',
        },
    },
    {
        'category_slug': 'theme-skins',
        'name': 'Ocean Breeze',
        'slug': 'ocean-breeze',
        'description': 'A calming ocean-inspired theme with gentle wave animations.',
        'price': Decimal('2.99'),
        'item_type': 'theme_skin',
        'rarity': 'rare',
        'metadata': {
            'primary_color': '#006994',
            'secondary_color': '#40E0D0',
            'accent_color': '#FFFFFF',
            'background': 'ocean-waves',
        },
    },
    {
        'category_slug': 'theme-skins',
        'name': 'Forest Calm',
        'slug': 'forest-calm',
        'description': 'Find your zen with this tranquil forest theme featuring soft greens.',
        'price': Decimal('2.99'),
        'item_type': 'theme_skin',
        'rarity': 'rare',
        'metadata': {
            'primary_color': '#228B22',
            'secondary_color': '#90EE90',
            'accent_color': '#8B4513',
            'background': 'forest-leaves',
        },
    },
    {
        'category_slug': 'theme-skins',
        'name': 'Sunset Glow',
        'slug': 'sunset-glow',
        'description': 'Warm sunset gradients that transition beautifully across your screen.',
        'price': Decimal('3.99'),
        'item_type': 'theme_skin',
        'rarity': 'rare',
        'metadata': {
            'primary_color': '#FF4500',
            'secondary_color': '#FF8C00',
            'accent_color': '#FFD700',
            'background': 'sunset-gradient',
        },
    },
    # Avatar Decorations
    {
        'category_slug': 'avatar-decorations',
        'name': 'Crown',
        'slug': 'crown',
        'description': 'A majestic crown that sits atop your avatar, proclaiming your achievements.',
        'price': Decimal('1.99'),
        'item_type': 'avatar_decoration',
        'rarity': 'rare',
        'metadata': {'position': 'top', 'style': 'gold-crown'},
    },
    {
        'category_slug': 'avatar-decorations',
        'name': 'Wings',
        'slug': 'wings',
        'description': 'Ethereal wings that spread behind your avatar for a mythical appearance.',
        'price': Decimal('4.99'),
        'item_type': 'avatar_decoration',
        'rarity': 'epic',
        'metadata': {'position': 'behind', 'style': 'angel-wings', 'animation': 'flutter'},
    },
    {
        'category_slug': 'avatar-decorations',
        'name': 'Halo',
        'slug': 'halo',
        'description': 'A glowing golden halo floating above your avatar.',
        'price': Decimal('2.99'),
        'item_type': 'avatar_decoration',
        'rarity': 'rare',
        'metadata': {'position': 'top', 'style': 'golden-halo', 'animation': 'glow'},
    },
    # Power-ups
    {
        'category_slug': 'power-ups',
        'name': 'Streak Shield',
        'slug': 'streak-shield',
        'description': 'Protect your streak for one day if you miss your daily tasks.',
        'price': Decimal('0.99'),
        'item_type': 'streak_shield',
        'rarity': 'common',
        'metadata': {'duration_days': 1, 'uses': 1},
    },
    {
        'category_slug': 'power-ups',
        'name': 'XP Booster 2x',
        'slug': 'xp-booster-2x',
        'description': 'Double your XP earnings for 24 hours. Stack your progress faster!',
        'price': Decimal('1.99'),
        'item_type': 'xp_booster',
        'rarity': 'rare',
        'metadata': {'multiplier': 2, 'duration_hours': 24},
    },
    {
        'category_slug': 'power-ups',
        'name': 'XP Booster 5x',
        'slug': 'xp-booster-5x',
        'description': 'Quintuple your XP earnings for 24 hours. The ultimate XP accelerator!',
        'price': Decimal('4.99'),
        'item_type': 'xp_booster',
        'rarity': 'epic',
        'metadata': {'multiplier': 5, 'duration_hours': 24},
    },
]


class Command(BaseCommand):
    """
    Management command to seed the store database with default categories and items.

    Usage:
        python manage.py seed_store
        python manage.py seed_store --clear  # Clear existing data first

    Safe to run multiple times. Uses get_or_create to prevent duplicates.
    """

    help = 'Seed the store with default categories and items'

    def add_arguments(self, parser):
        """Add command-line arguments."""
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear all existing store data before seeding.',
        )

    def handle(self, *args, **options):
        """Execute the command to seed store data."""
        if options['clear']:
            self.stdout.write(self.style.WARNING('Clearing existing store data...'))
            StoreItem.objects.all().delete()
            StoreCategory.objects.all().delete()
            self.stdout.write(self.style.SUCCESS('Existing store data cleared.'))

        self.stdout.write('Seeding store categories...')
        categories_created = 0
        categories_existing = 0

        category_map = {}
        for cat_data in CATEGORIES:
            category, created = StoreCategory.objects.get_or_create(
                slug=cat_data['slug'],
                defaults=cat_data,
            )
            category_map[cat_data['slug']] = category
            if created:
                categories_created += 1
            else:
                categories_existing += 1

        self.stdout.write(
            f'  Categories: {categories_created} created, '
            f'{categories_existing} already existed.'
        )

        self.stdout.write('Seeding store items...')
        items_created = 0
        items_existing = 0

        for item_data in ITEMS:
            category_slug = item_data.pop('category_slug')
            category = category_map.get(category_slug)

            if not category:
                self.stdout.write(
                    self.style.ERROR(
                        f'  Category "{category_slug}" not found, '
                        f'skipping item "{item_data["name"]}".'
                    )
                )
                # Re-add category_slug so we don't modify the original data permanently
                item_data['category_slug'] = category_slug
                continue

            item, created = StoreItem.objects.get_or_create(
                slug=item_data['slug'],
                defaults={
                    'category': category,
                    **{k: v for k, v in item_data.items() if k != 'category_slug'},
                },
            )

            # Re-add category_slug for idempotency of the data list
            item_data['category_slug'] = category_slug

            if created:
                items_created += 1
            else:
                items_existing += 1

        self.stdout.write(
            f'  Items: {items_created} created, '
            f'{items_existing} already existed.'
        )

        self.stdout.write(
            self.style.SUCCESS(
                f'Store seeding complete! '
                f'{categories_created + items_created} new records created.'
            )
        )
