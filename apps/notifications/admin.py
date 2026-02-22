"""
Django admin configuration for Notifications app.
"""

from django.contrib import admin
from .models import Notification, NotificationTemplate, NotificationBatch


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    """Admin interface for Notification model."""

    list_display = ['title', 'user', 'notification_type', 'status', 'scheduled_for', 'sent_at']
    list_filter = ['notification_type', 'status', 'scheduled_for', 'created_at']
    search_fields = ['title', 'body', 'user__email']
    ordering = ['-scheduled_for']
    readonly_fields = ['sent_at', 'read_at', 'created_at']

    fieldsets = (
        ('Basic Info', {
            'fields': ('user', 'notification_type', 'title', 'body')
        }),
        ('Data & Deep Linking', {
            'fields': ('data',),
            'classes': ('collapse',)
        }),
        ('Scheduling', {
            'fields': ('scheduled_for', 'status', 'sent_at', 'read_at')
        }),
        ('Retry Logic', {
            'fields': ('retry_count', 'max_retries', 'error_message'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at',)
        }),
    )

    actions = ['mark_as_sent', 'mark_as_cancelled']

    def mark_as_sent(self, request, queryset):
        """Mark selected notifications as sent."""
        updated = queryset.update(status='sent')
        self.message_user(request, f'{updated} notifications marked as sent.')
    mark_as_sent.short_description = 'Mark selected as sent'

    def mark_as_cancelled(self, request, queryset):
        """Cancel selected notifications."""
        updated = queryset.update(status='cancelled')
        self.message_user(request, f'{updated} notifications cancelled.')
    mark_as_cancelled.short_description = 'Cancel selected notifications'


@admin.register(NotificationTemplate)
class NotificationTemplateAdmin(admin.ModelAdmin):
    """Admin interface for Notification templates."""

    list_display = ['name', 'notification_type', 'is_active', 'created_at']
    list_filter = ['notification_type', 'is_active', 'created_at']
    search_fields = ['name', 'title_template', 'body_template']
    readonly_fields = ['created_at', 'updated_at']

    fieldsets = (
        ('Basic Info', {
            'fields': ('name', 'notification_type', 'is_active')
        }),
        ('Template', {
            'fields': ('title_template', 'body_template', 'available_variables')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )


@admin.register(NotificationBatch)
class NotificationBatchAdmin(admin.ModelAdmin):
    """Admin interface for Notification batches."""

    list_display = ['name', 'notification_type', 'status', 'progress', 'created_at']
    list_filter = ['notification_type', 'status', 'created_at']
    search_fields = ['name']
    readonly_fields = ['total_scheduled', 'total_sent', 'total_failed', 'completed_at', 'created_at']

    def progress(self, obj):
        if obj.total_scheduled == 0:
            return '0%'
        percentage = (obj.total_sent / obj.total_scheduled) * 100
        return f'{percentage:.1f}% ({obj.total_sent}/{obj.total_scheduled})'
    progress.short_description = 'Progress'
