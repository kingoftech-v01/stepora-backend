from django.contrib import admin

from .models import AppBundle


@admin.register(AppBundle)
class AppBundleAdmin(admin.ModelAdmin):
    list_display = [
        "bundle_id", "platform", "strategy", "min_app_version",
        "is_active", "created_at",
    ]
    list_filter = ["is_active", "platform", "strategy"]
    list_editable = ["is_active", "strategy"]
    search_fields = ["bundle_id", "message"]
    readonly_fields = ["created_at"]
    ordering = ["-created_at"]
    fieldsets = [
        (None, {
            "fields": ["bundle_id", "bundle_file", "checksum"],
        }),
        ("Targeting", {
            "fields": ["platform", "min_app_version"],
        }),
        ("Behavior", {
            "fields": ["strategy", "message", "is_active"],
        }),
        ("Info", {
            "fields": ["created_at"],
        }),
    ]
