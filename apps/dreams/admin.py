"""
Django admin configuration for Dreams app.
"""

from django.contrib import admin
from .models import Dream, Goal, Task, Obstacle


class GoalInline(admin.TabularInline):
    """Inline admin for Goals within Dream."""
    model = Goal
    extra = 0
    fields = ['title', 'order', 'status', 'progress_percentage']
    readonly_fields = ['progress_percentage']


class ObstacleInline(admin.TabularInline):
    """Inline admin for Obstacles within Dream."""
    model = Obstacle
    extra = 0
    fields = ['title', 'obstacle_type', 'status']


@admin.register(Dream)
class DreamAdmin(admin.ModelAdmin):
    """Admin interface for Dream model."""

    list_display = ['title', 'user', 'status', 'category', 'progress_percentage', 'target_date', 'created_at']
    list_filter = ['status', 'category', 'created_at']
    search_fields = ['title', 'description', 'user__email']
    ordering = ['-created_at']
    readonly_fields = ['progress_percentage', 'created_at', 'updated_at']

    inlines = [GoalInline, ObstacleInline]

    fieldsets = (
        ('Basic Info', {
            'fields': ('user', 'title', 'description', 'category', 'priority')
        }),
        ('Scheduling', {
            'fields': ('target_date', 'status', 'completed_at')
        }),
        ('Progress', {
            'fields': ('progress_percentage', 'has_two_minute_start')
        }),
        ('AI & Vision', {
            'fields': ('ai_analysis', 'vision_image_url'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


class TaskInline(admin.TabularInline):
    """Inline admin for Tasks within Goal."""
    model = Task
    extra = 0
    fields = ['title', 'order', 'status', 'scheduled_date', 'duration_mins']


@admin.register(Goal)
class GoalAdmin(admin.ModelAdmin):
    """Admin interface for Goal model."""

    list_display = ['title', 'dream', 'order', 'status', 'progress_percentage', 'scheduled_start']
    list_filter = ['status', 'created_at']
    search_fields = ['title', 'description', 'dream__title']
    ordering = ['dream', 'order']
    readonly_fields = ['progress_percentage', 'created_at', 'updated_at']

    inlines = [TaskInline]

    fieldsets = (
        ('Basic Info', {
            'fields': ('dream', 'title', 'description', 'order')
        }),
        ('Scheduling', {
            'fields': ('estimated_minutes', 'scheduled_start', 'scheduled_end', 'status', 'completed_at')
        }),
        ('Progress & Reminders', {
            'fields': ('progress_percentage', 'reminder_enabled', 'reminder_time')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    """Admin interface for Task model."""

    list_display = ['title', 'goal', 'order', 'status', 'scheduled_date', 'duration_mins', 'is_two_minute_start']
    list_filter = ['status', 'is_two_minute_start', 'created_at']
    search_fields = ['title', 'description', 'goal__title']
    ordering = ['goal', 'scheduled_date', 'order']
    readonly_fields = ['created_at', 'updated_at']

    fieldsets = (
        ('Basic Info', {
            'fields': ('goal', 'title', 'description', 'order')
        }),
        ('Scheduling', {
            'fields': ('scheduled_date', 'scheduled_time', 'duration_mins', 'recurrence')
        }),
        ('Status', {
            'fields': ('status', 'completed_at', 'is_two_minute_start')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(Obstacle)
class ObstacleAdmin(admin.ModelAdmin):
    """Admin interface for Obstacle model."""

    list_display = ['title', 'dream', 'obstacle_type', 'status', 'created_at']
    list_filter = ['obstacle_type', 'status', 'created_at']
    search_fields = ['title', 'description', 'dream__title']
    readonly_fields = ['created_at', 'updated_at']
