"""
Django admin configuration for Calendar app.
"""

from django.contrib import admin
from .models import CalendarEvent, TimeBlock


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
            'fields': ('start_time', 'end_time', 'reminder_minutes_before')
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
