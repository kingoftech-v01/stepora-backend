"""
Django admin configuration for Plans app.
"""

from django.contrib import admin

from .models import (
    CalibrationResponse,
    DreamMilestone,
    DreamProgressSnapshot,
    FocusSession,
    Goal,
    Obstacle,
    PlanCheckIn,
    Task,
)


@admin.register(DreamMilestone)
class DreamMilestoneAdmin(admin.ModelAdmin):
    list_display = ["dream", "title", "order", "status", "progress_percentage", "target_date"]
    list_filter = ["status", "created_at"]
    search_fields = ["title", "dream__title"]
    readonly_fields = ["created_at", "updated_at"]
    raw_id_fields = ["dream"]


@admin.register(Goal)
class GoalAdmin(admin.ModelAdmin):
    list_display = ["dream", "milestone", "title", "order", "status", "progress_percentage"]
    list_filter = ["status", "created_at"]
    search_fields = ["title", "dream__title"]
    readonly_fields = ["created_at", "updated_at"]
    raw_id_fields = ["dream", "milestone"]


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ["title", "goal", "order", "status", "scheduled_date", "duration_mins"]
    list_filter = ["status", "created_at"]
    search_fields = ["title"]
    readonly_fields = ["created_at", "updated_at"]
    raw_id_fields = ["goal", "chain_parent"]


@admin.register(Obstacle)
class ObstacleAdmin(admin.ModelAdmin):
    list_display = ["title", "dream", "obstacle_type", "status"]
    list_filter = ["obstacle_type", "status"]
    search_fields = ["title", "dream__title"]
    readonly_fields = ["created_at", "updated_at"]
    raw_id_fields = ["dream", "milestone", "goal"]


@admin.register(CalibrationResponse)
class CalibrationResponseAdmin(admin.ModelAdmin):
    list_display = ["dream", "question_number", "category", "created_at"]
    list_filter = ["category", "created_at"]
    search_fields = ["question", "dream__title"]
    readonly_fields = ["created_at"]
    raw_id_fields = ["dream"]


@admin.register(PlanCheckIn)
class PlanCheckInAdmin(admin.ModelAdmin):
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
    raw_id_fields = ["dream"]


@admin.register(DreamProgressSnapshot)
class DreamProgressSnapshotAdmin(admin.ModelAdmin):
    list_display = ["dream", "date", "progress_percentage"]
    list_filter = ["date"]
    search_fields = ["dream__title"]
    readonly_fields = ["created_at"]
    raw_id_fields = ["dream"]


@admin.register(FocusSession)
class FocusSessionAdmin(admin.ModelAdmin):
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
