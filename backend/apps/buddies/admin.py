"""
Django admin configuration for the Buddies system.

Provides admin interfaces for managing buddy pairings and
encouragement messages.
"""

from django.contrib import admin

from .models import BuddyPairing, BuddyEncouragement


class BuddyEncouragementInline(admin.TabularInline):
    """Inline admin for BuddyEncouragement within BuddyPairing."""

    model = BuddyEncouragement
    extra = 0
    fields = ['sender', 'message', 'created_at']
    readonly_fields = ['created_at']
    raw_id_fields = ['sender']


@admin.register(BuddyPairing)
class BuddyPairingAdmin(admin.ModelAdmin):
    """Admin interface for BuddyPairing model."""

    list_display = [
        'user1', 'user2', 'status', 'compatibility_score',
        'created_at', 'ended_at',
    ]
    list_filter = ['status', 'created_at']
    search_fields = [
        'user1__email', 'user1__display_name',
        'user2__email', 'user2__display_name',
    ]
    ordering = ['-created_at']
    readonly_fields = ['created_at', 'updated_at']
    raw_id_fields = ['user1', 'user2']

    inlines = [BuddyEncouragementInline]

    fieldsets = (
        ('Users', {
            'fields': ('user1', 'user2')
        }),
        ('Status', {
            'fields': ('status', 'compatibility_score')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'ended_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(BuddyEncouragement)
class BuddyEncouragementAdmin(admin.ModelAdmin):
    """Admin interface for BuddyEncouragement model."""

    list_display = ['sender', 'pairing', 'message_preview', 'created_at']
    list_filter = ['created_at']
    search_fields = ['sender__email', 'sender__display_name', 'message']
    ordering = ['-created_at']
    readonly_fields = ['created_at']
    raw_id_fields = ['sender', 'pairing']

    fieldsets = (
        ('Encouragement', {
            'fields': ('pairing', 'sender', 'message')
        }),
        ('Timestamps', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )

    def message_preview(self, obj):
        """Display a truncated preview of the message."""
        if not obj.message:
            return '(no message)'
        return obj.message[:80] + '...' if len(obj.message) > 80 else obj.message
    message_preview.short_description = 'Message'
