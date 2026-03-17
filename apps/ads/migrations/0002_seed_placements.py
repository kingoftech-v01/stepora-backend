"""Seed default ad placements."""

from django.db import migrations


def seed_placements(apps, schema_editor):
    AdPlacement = apps.get_model("ads", "AdPlacement")
    placements = [
        {
            "name": "home_banner",
            "display_name": "Home Dashboard Banner",
            "ad_type": "banner",
            "frequency": 1,
            "priority": 10,
        },
        {
            "name": "between_dreams",
            "display_name": "Between Dream Cards (Native)",
            "ad_type": "native",
            "frequency": 4,
            "priority": 8,
        },
        {
            "name": "social_feed",
            "display_name": "Social Feed (Native)",
            "ad_type": "native",
            "frequency": 5,
            "priority": 7,
        },
        {
            "name": "chat_bottom",
            "display_name": "Chat Bottom Banner",
            "ad_type": "banner",
            "frequency": 1,
            "priority": 6,
        },
        {
            "name": "page_interstitial",
            "display_name": "Between Page Navigations",
            "ad_type": "interstitial",
            "frequency": 5,
            "priority": 5,
        },
    ]
    for p in placements:
        AdPlacement.objects.update_or_create(
            name=p["name"],
            defaults=p,
        )


def reverse_seed(apps, schema_editor):
    AdPlacement = apps.get_model("ads", "AdPlacement")
    AdPlacement.objects.filter(
        name__in=[
            "home_banner",
            "between_dreams",
            "social_feed",
            "chat_bottom",
            "page_interstitial",
        ]
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("ads", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_placements, reverse_seed),
    ]
