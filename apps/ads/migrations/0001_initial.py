"""Initial migration for the Ads app — creates the AdPlacement model."""

import uuid

from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="AdPlacement",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "name",
                    models.CharField(
                        help_text="Machine-readable placement name (e.g. home_banner, between_dreams)",
                        max_length=100,
                        unique=True,
                    ),
                ),
                (
                    "display_name",
                    models.CharField(
                        blank=True,
                        default="",
                        help_text="Human-readable label for the admin panel",
                        max_length=200,
                    ),
                ),
                (
                    "ad_type",
                    models.CharField(
                        choices=[
                            ("banner", "Banner"),
                            ("interstitial", "Interstitial"),
                            ("native", "Native"),
                        ],
                        help_text="Type of ad unit rendered at this placement",
                        max_length=20,
                    ),
                ),
                (
                    "is_active",
                    models.BooleanField(
                        default=True,
                        help_text="Whether this placement is currently serving ads",
                    ),
                ),
                (
                    "frequency",
                    models.PositiveIntegerField(
                        default=1,
                        help_text=(
                            "Show ad every N views/items. "
                            "For interstitials: every N page transitions. "
                            "For native: every N list items."
                        ),
                    ),
                ),
                (
                    "priority",
                    models.PositiveIntegerField(
                        default=0,
                        help_text="Higher priority placements are returned first",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "db_table": "ad_placements",
                "ordering": ["-priority", "name"],
            },
        ),
    ]
