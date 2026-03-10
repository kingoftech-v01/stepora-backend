"""
Django admin configuration for Calendar app.
"""

from django.contrib import admin
from .models import (
    CalendarEvent, TimeBlock, TimeBlockTemplate, CalendarShare,
    Habit, HabitCompletion, GoogleCalendarIntegration, RecurrenceException,
)


@admin.register(CalendarEvent)
class CalendarEventAdmin(admin.ModelAdmin):
    """Admin interface for Calendar events."""

    list_display = ['title', 'user', 'start_time', 'end_time', 'status', 'created_at']
    list_filter = ['status', 'start_time', 'created_at']
    search_fields = ['title', 'description', 'user__email', 'task__title']
    ordering = ['-start_time']
    readonly_fields = ['created_at', 'updated_at']

    fieldsets = (
        ('Basic Info', {
            'fields': ('user', 'task', 'title', 'description')
        }),
        ('Timing', {
            'fields': ('start_time', 'end_time', 'reminder_minutes_before', 'reminders', 'reminders_sent')
        }),
        ('Details', {
            'fields': ('location', 'status')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )


@admin.register(TimeBlock)
class TimeBlockAdmin(admin.ModelAdmin):
    """Admin interface for Time blocks."""

    list_display = ['user', 'day_name', 'start_time', 'end_time', 'block_type', 'is_active']
    list_filter = ['block_type', 'day_of_week', 'is_active', 'created_at']
    search_fields = ['user__email']
    ordering = ['user', 'day_of_week', 'start_time']
    readonly_fields = ['created_at', 'updated_at']

    def day_name(self, obj):
        days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        return days[obj.day_of_week]
    day_name.short_description = 'Day'


@admin.register(TimeBlockTemplate)
class TimeBlockTemplateAdmin(admin.ModelAdmin):
    """Admin interface for Time Block Templates."""

    list_display = ['name', 'user', 'is_preset', 'block_count', 'created_at']
    list_filter = ['is_preset', 'created_at']
    search_fields = ['name', 'description', 'user__email']
    ordering = ['-is_preset', '-created_at']
    readonly_fields = ['created_at', 'updated_at']

    def block_count(self, obj):
        if isinstance(obj.blocks, list):
            return len(obj.blocks)
        return 0
    block_count.short_description = 'Blocks'


@admin.register(CalendarShare)
class CalendarShareAdmin(admin.ModelAdmin):
    """Admin interface for Calendar Shares."""

    list_display = ['owner', 'shared_with', 'permission', 'is_active', 'created_at']
    list_filter = ['permission', 'is_active', 'created_at']
    search_fields = ['owner__email', 'shared_with__email', 'share_token']
    ordering = ['-created_at']
    readonly_fields = ['id', 'share_token', 'created_at']

    fieldsets = (
        ('Share Details', {
            'fields': ('id', 'owner', 'shared_with', 'permission', 'share_token')
        }),
        ('Status', {
            'fields': ('is_active', 'created_at')
        }),
    )


@admin.register(GoogleCalendarIntegration)
class GoogleCalendarIntegrationAdmin(admin.ModelAdmin):
    """Admin interface for GoogleCalendarIntegration model."""

    list_display = ['user', 'calendar_id', 'sync_enabled', 'sync_direction', 'last_sync_at', 'created_at']
    list_filter = ['sync_enabled', 'sync_direction', 'created_at']
    search_fields = ['user__email', 'user__display_name', 'calendar_id']
    ordering = ['-created_at']
    readonly_fields = ['id', 'created_at', 'updated_at']
    raw_id_fields = ['user']


@admin.register(RecurrenceException)
class RecurrenceExceptionAdmin(admin.ModelAdmin):
    """Admin interface for RecurrenceException model."""

    list_display = ['parent_event', 'original_date', 'skip_occurrence', 'modified_start_time', 'created_at']
    list_filter = ['skip_occurrence', 'created_at']
    search_fields = ['parent_event__title']
    ordering = ['original_date']
    readonly_fields = ['id', 'created_at']
    raw_id_fields = ['parent_event']


@admin.register(Habit)
class HabitAdmin(admin.ModelAdmin):
    """Admin interface for Habit model."""

    list_display = ['user', 'frequency', 'target_per_day', 'is_active', 'streak_current', 'streak_best', 'created_at']
    list_filter = ['frequency', 'is_active', 'created_at']
    search_fields = ['user__email', 'user__display_name']
    ordering = ['-created_at']
    readonly_fields = ['id', 'created_at', 'updated_at']
    raw_id_fields = ['user']


@admin.register(HabitCompletion)
class HabitCompletionAdmin(admin.ModelAdmin):
    """Admin interface for HabitCompletion model."""

    list_display = ['habit', 'date', 'count', 'completed_at']
    list_filter = ['date', 'completed_at']
    search_fields = ['habit__user__email', 'habit__user__display_name']
    ordering = ['-date']
    readonly_fields = ['id', 'completed_at']
    raw_id_fields = ['habit']
