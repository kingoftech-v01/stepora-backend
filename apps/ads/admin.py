"""Admin configuration for the Ads app."""

from django.contrib import admin

from .models import AdPlacement


@admin.register(AdPlacement)
class AdPlacementAdmin(admin.ModelAdmin):
    """Admin interface for managing ad placements."""

    list_display = [
        "name",
        "display_name",
        "ad_type",
        "is_active",
        "frequency",
        "priority",
        "created_at",
    ]
    list_filter = ["ad_type", "is_active"]
    list_editable = ["is_active", "frequency", "priority"]
    search_fields = ["name", "display_name"]
    ordering = ["-priority", "name"]
