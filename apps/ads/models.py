"""
Models for the Ads app.

Defines ad placement configuration used to control where and how
self-promotional ads are displayed to free-tier users.
"""

import uuid

from django.db import models


class AdPlacement(models.Model):
    """
    Configures an ad slot in the application.

    Each placement corresponds to a specific location in the UI
    (e.g. home banner, between dream cards, chat footer).
    Admins can toggle placements on/off and control display frequency
    without code changes.
    """

    AD_TYPE_CHOICES = [
        ("banner", "Banner"),
        ("interstitial", "Interstitial"),
        ("native", "Native"),
    ]

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    name = models.CharField(
        max_length=100,
        unique=True,
        help_text="Machine-readable placement name (e.g. home_banner, between_dreams)",
    )
    display_name = models.CharField(
        max_length=200,
        blank=True,
        default="",
        help_text="Human-readable label for the admin panel",
    )
    ad_type = models.CharField(
        max_length=20,
        choices=AD_TYPE_CHOICES,
        help_text="Type of ad unit rendered at this placement",
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this placement is currently serving ads",
    )
    frequency = models.PositiveIntegerField(
        default=1,
        help_text=(
            "Show ad every N views/items. "
            "For interstitials: every N page transitions. "
            "For native: every N list items."
        ),
    )
    priority = models.PositiveIntegerField(
        default=0,
        help_text="Higher priority placements are returned first",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "ad_placements"
        ordering = ["-priority", "name"]

    def __str__(self):
        return f"{self.name} ({self.get_ad_type_display()}, {'active' if self.is_active else 'inactive'})"
