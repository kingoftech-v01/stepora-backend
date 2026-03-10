"""
Django admin configuration for Dreams app.
"""

from django.contrib import admin

from .models import (
    CalibrationResponse,
    Dream,
    DreamCollaborator,
    DreamJournal,
    DreamMilestone,
    DreamProgressSnapshot,
    DreamTag,
    DreamTagging,
    DreamTemplate,
    FocusSession,
    Goal,
    Obstacle,
    PlanCheckIn,
    ProgressPhoto,
    SharedDream,
    Task,
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


class TaskInline(admin.TabularInline):
    """Inline admin for Tasks within Goal."""

    model = Task
    extra = 0
    fields = ["title", "order", "status", "scheduled_date", "duration_mins"]


@admin.register(Goal)
class GoalAdmin(admin.ModelAdmin):
    """Admin interface for Goal model."""

    list_display = [
        "title",
        "dream",
        "order",
        "status",
        "progress_percentage",
        "scheduled_start",
    ]
    list_filter = ["status", "created_at"]
    search_fields = ["title", "description", "dream__title"]
    ordering = ["dream", "order"]
    readonly_fields = ["progress_percentage", "created_at", "updated_at"]

    inlines = [TaskInline]

    fieldsets = (
        ("Basic Info", {"fields": ("dream", "title", "description", "order")}),
        (
            "Scheduling",
            {
                "fields": (
                    "estimated_minutes",
                    "scheduled_start",
                    "scheduled_end",
                    "status",
                    "completed_at",
                )
            },
        ),
        (
            "Progress & Reminders",
            {"fields": ("progress_percentage", "reminder_enabled", "reminder_time")},
        ),
        (
            "Timestamps",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    """Admin interface for Task model."""

    list_display = [
        "title",
        "goal",
        "order",
        "status",
        "scheduled_date",
        "duration_mins",
        "is_two_minute_start",
    ]
    list_filter = ["status", "is_two_minute_start", "created_at"]
    search_fields = ["title", "description", "goal__title"]
    ordering = ["goal", "scheduled_date", "order"]
    readonly_fields = ["created_at", "updated_at"]

    fieldsets = (
        ("Basic Info", {"fields": ("goal", "title", "description", "order")}),
        (
            "Scheduling",
            {
                "fields": (
                    "scheduled_date",
                    "scheduled_time",
                    "duration_mins",
                    "recurrence",
                )
            },
        ),
        ("Status", {"fields": ("status", "completed_at", "is_two_minute_start")}),
        (
            "Timestamps",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )


@admin.register(Obstacle)
class ObstacleAdmin(admin.ModelAdmin):
    """Admin interface for Obstacle model."""

    list_display = ["title", "dream", "obstacle_type", "status", "created_at"]
    list_filter = ["obstacle_type", "status", "created_at"]
    search_fields = ["title", "description", "dream__title"]
    readonly_fields = ["created_at", "updated_at"]
    raw_id_fields = ["dream", "milestone", "goal"]


@admin.register(DreamMilestone)
class DreamMilestoneAdmin(admin.ModelAdmin):
    """Admin interface for DreamMilestone model."""

    list_display = [
        "title",
        "dream",
        "order",
        "status",
        "progress_percentage",
        "target_date",
        "created_at",
    ]
    list_filter = ["status", "created_at"]
    search_fields = ["title", "description", "dream__title"]
    ordering = ["dream", "order"]
    readonly_fields = ["progress_percentage", "created_at", "updated_at"]
    raw_id_fields = ["dream"]


@admin.register(DreamTemplate)
class DreamTemplateAdmin(admin.ModelAdmin):
    """Admin interface for DreamTemplate model."""

    list_display = [
        "title",
        "category",
        "difficulty",
        "is_featured",
        "is_active",
        "usage_count",
        "created_at",
    ]
    list_filter = ["category", "difficulty", "is_featured", "is_active"]
    search_fields = ["title", "description"]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(DreamCollaborator)
class DreamCollaboratorAdmin(admin.ModelAdmin):
    """Admin interface for DreamCollaborator model."""

    list_display = ["user", "dream", "role", "created_at"]
    list_filter = ["role", "created_at"]
    search_fields = ["user__email", "user__display_name", "dream__title"]
    readonly_fields = ["created_at"]
    raw_id_fields = ["dream", "user"]


@admin.register(SharedDream)
class SharedDreamAdmin(admin.ModelAdmin):
    """Admin interface for SharedDream model."""

    list_display = ["dream", "shared_by", "shared_with", "permission", "created_at"]
    list_filter = ["permission", "created_at"]
    search_fields = ["dream__title", "shared_by__email", "shared_with__email"]
    readonly_fields = ["created_at"]
    raw_id_fields = ["dream", "shared_by", "shared_with"]


@admin.register(DreamProgressSnapshot)
class DreamProgressSnapshotAdmin(admin.ModelAdmin):
    """Admin interface for DreamProgressSnapshot model."""

    list_display = ["dream", "date", "progress_percentage", "created_at"]
    list_filter = ["date"]
    search_fields = ["dream__title"]
    readonly_fields = ["created_at"]
    raw_id_fields = ["dream"]


@admin.register(VisionBoardImage)
class VisionBoardImageAdmin(admin.ModelAdmin):
    """Admin interface for VisionBoardImage model."""

    list_display = ["dream", "order", "caption", "is_ai_generated", "created_at"]
    list_filter = ["is_ai_generated", "created_at"]
    search_fields = ["caption", "dream__title"]
    readonly_fields = ["created_at"]
    raw_id_fields = ["dream"]


@admin.register(PlanCheckIn)
class PlanCheckInAdmin(admin.ModelAdmin):
    """Admin interface for PlanCheckIn model."""

    list_display = [
        "dream",
        "status",
        "triggered_by",
        "pace_status",
        "scheduled_for",
        "completed_at",
        "created_at",
    ]
    list_filter = ["status", "triggered_by", "pace_status", "created_at"]
    search_fields = ["dream__title", "coaching_message"]
    readonly_fields = ["created_at"]
    raw_id_fields = ["dream", "conversation"]


@admin.register(CalibrationResponse)
class CalibrationResponseAdmin(admin.ModelAdmin):
    """Admin interface for CalibrationResponse model."""

    list_display = ["dream", "question_number", "category", "created_at"]
    list_filter = ["category", "created_at"]
    search_fields = ["question", "dream__title"]
    readonly_fields = ["created_at"]
    raw_id_fields = ["dream"]


@admin.register(DreamTag)
class DreamTagAdmin(admin.ModelAdmin):
    """Admin interface for DreamTag model."""

    list_display = ["name", "created_at"]
    search_fields = ["name"]
    ordering = ["name"]
    readonly_fields = ["id", "created_at"]


@admin.register(DreamTagging)
class DreamTaggingAdmin(admin.ModelAdmin):
    """Admin interface for DreamTagging model."""

    list_display = ["dream", "tag", "created_at"]
    list_filter = ["created_at"]
    search_fields = ["dream__title", "tag__name"]
    ordering = ["-created_at"]
    readonly_fields = ["id", "created_at"]
    raw_id_fields = ["dream", "tag"]


@admin.register(FocusSession)
class FocusSessionAdmin(admin.ModelAdmin):
    """Admin interface for FocusSession model."""

    list_display = [
        "user",
        "task",
        "session_type",
        "duration_minutes",
        "actual_minutes",
        "completed",
        "started_at",
    ]
    list_filter = ["session_type", "completed", "started_at"]
    search_fields = ["user__email", "user__display_name"]
    ordering = ["-started_at"]
    readonly_fields = ["id", "started_at"]
    raw_id_fields = ["user", "task"]


@admin.register(DreamJournal)
class DreamJournalAdmin(admin.ModelAdmin):
    """Admin interface for DreamJournal model."""

    list_display = ["dream", "title", "mood", "created_at"]
    list_filter = ["mood", "created_at"]
    search_fields = ["title", "content", "dream__title"]
    ordering = ["-created_at"]
    readonly_fields = ["id", "created_at", "updated_at"]
    raw_id_fields = ["dream"]


@admin.register(ProgressPhoto)
class ProgressPhotoAdmin(admin.ModelAdmin):
    """Admin interface for ProgressPhoto model."""

    list_display = ["dream", "taken_at", "created_at"]
    list_filter = ["taken_at", "created_at"]
    search_fields = ["dream__title"]
    ordering = ["-taken_at"]
    readonly_fields = ["id", "created_at", "updated_at"]
    raw_id_fields = ["dream"]
