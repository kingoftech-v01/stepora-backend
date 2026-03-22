"""
Django admin configuration for Dreams app.

Plan-related admin classes (Goal, Task, Milestone, etc.) are in apps.plans.admin.
"""

from django.contrib import admin

# Import Goal/Obstacle for inline use (still valid via backward-compat)
from apps.plans.models import Goal, Obstacle

from .models import (
    Dream,
    DreamCollaborator,
    DreamJournal,
    DreamTag,
    DreamTagging,
    DreamTemplate,
    ProgressPhoto,
    SharedDream,
    VisionBoardImage,
)


class GoalInline(admin.TabularInline):
    """Inline admin for Goals within Dream."""

    model = Goal
    extra = 0
    fields = ["title", "order", "status", "progress_percentage"]
    readonly_fields = ["progress_percentage"]


class ObstacleInline(admin.TabularInline):
    """Inline admin for Obstacles within Dream."""

    model = Obstacle
    extra = 0
    fields = ["title", "obstacle_type", "status"]


@admin.register(Dream)
class DreamAdmin(admin.ModelAdmin):
    """Admin interface for Dream model."""

    list_display = [
        "title",
        "user",
        "status",
        "category",
        "progress_percentage",
        "target_date",
        "created_at",
    ]
    list_filter = ["status", "category", "created_at"]
    search_fields = ["title", "description", "user__email"]
    ordering = ["-created_at"]
    readonly_fields = ["progress_percentage", "created_at", "updated_at"]

    inlines = [GoalInline, ObstacleInline]

    fieldsets = (
        (
            "Basic Info",
            {"fields": ("user", "title", "description", "category", "priority")},
        ),
        ("Scheduling", {"fields": ("target_date", "status", "completed_at")}),
        ("Progress", {"fields": ("progress_percentage", "has_two_minute_start")}),
        (
            "AI & Vision",
            {"fields": ("ai_analysis", "vision_image_url"), "classes": ("collapse",)},
        ),
        (
            "Timestamps",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )


@admin.register(DreamTemplate)
class DreamTemplateAdmin(admin.ModelAdmin):
    """Admin interface for DreamTemplate model."""

    list_display = [
        "title", "category", "difficulty", "is_featured", "is_active",
        "usage_count", "created_at",
    ]
    list_filter = ["category", "difficulty", "is_featured", "is_active"]
    search_fields = ["title", "description"]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(DreamCollaborator)
class DreamCollaboratorAdmin(admin.ModelAdmin):
    list_display = ["user", "dream", "role", "created_at"]
    list_filter = ["role", "created_at"]
    search_fields = ["user__email", "user__display_name", "dream__title"]
    readonly_fields = ["created_at"]
    raw_id_fields = ["dream", "user"]


@admin.register(SharedDream)
class SharedDreamAdmin(admin.ModelAdmin):
    list_display = ["dream", "shared_by", "shared_with", "permission", "created_at"]
    list_filter = ["permission", "created_at"]
    search_fields = ["dream__title", "shared_by__email", "shared_with__email"]
    readonly_fields = ["created_at"]
    raw_id_fields = ["dream", "shared_by", "shared_with"]


@admin.register(VisionBoardImage)
class VisionBoardImageAdmin(admin.ModelAdmin):
    list_display = ["dream", "order", "caption", "is_ai_generated", "created_at"]
    list_filter = ["is_ai_generated", "created_at"]
    search_fields = ["caption", "dream__title"]
    readonly_fields = ["created_at"]
    raw_id_fields = ["dream"]


@admin.register(DreamTag)
class DreamTagAdmin(admin.ModelAdmin):
    list_display = ["name", "created_at"]
    search_fields = ["name"]
    ordering = ["name"]
    readonly_fields = ["id", "created_at"]


@admin.register(DreamTagging)
class DreamTaggingAdmin(admin.ModelAdmin):
    list_display = ["dream", "tag", "created_at"]
    list_filter = ["created_at"]
    search_fields = ["dream__title", "tag__name"]
    ordering = ["-created_at"]
    readonly_fields = ["id", "created_at"]
    raw_id_fields = ["dream", "tag"]


@admin.register(DreamJournal)
class DreamJournalAdmin(admin.ModelAdmin):
    list_display = ["dream", "title", "mood", "created_at"]
    list_filter = ["mood", "created_at"]
    search_fields = ["title", "content", "dream__title"]
    ordering = ["-created_at"]
    readonly_fields = ["id", "created_at", "updated_at"]
    raw_id_fields = ["dream"]


@admin.register(ProgressPhoto)
class ProgressPhotoAdmin(admin.ModelAdmin):
    list_display = ["dream", "taken_at", "created_at"]
    list_filter = ["taken_at", "created_at"]
    search_fields = ["dream__title"]
    ordering = ["-taken_at"]
    readonly_fields = ["id", "created_at", "updated_at"]
    raw_id_fields = ["dream"]
