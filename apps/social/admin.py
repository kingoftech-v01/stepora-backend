"""
Django admin configuration for the Social system.

Provides admin interfaces for managing friendships, follows,
and activity feed items.
"""

from django.contrib import admin

from .models import Friendship, UserFollow, ActivityFeedItem, BlockedUser, ReportedUser


@admin.register(Friendship)
class FriendshipAdmin(admin.ModelAdmin):
    """Admin interface for Friendship model."""

    list_display = ['user1', 'user2', 'status', 'created_at', 'updated_at']
    list_filter = ['status', 'created_at']
    search_fields = [
        'user1__email', 'user1__display_name',
        'user2__email', 'user2__display_name',
    ]
    ordering = ['-created_at']
    readonly_fields = ['created_at', 'updated_at']
    raw_id_fields = ['user1', 'user2']

    fieldsets = (
        ('Users', {
            'fields': ('user1', 'user2')
        }),
        ('Status', {
            'fields': ('status',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(UserFollow)
class UserFollowAdmin(admin.ModelAdmin):
    """Admin interface for UserFollow model."""

    list_display = ['follower', 'following', 'created_at']
    list_filter = ['created_at']
    search_fields = [
        'follower__email', 'follower__display_name',
        'following__email', 'following__display_name',
    ]
    ordering = ['-created_at']
    readonly_fields = ['created_at']
    raw_id_fields = ['follower', 'following']

    fieldsets = (
        ('Relationship', {
            'fields': ('follower', 'following')
        }),
        ('Timestamps', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )


@admin.register(ActivityFeedItem)
class ActivityFeedItemAdmin(admin.ModelAdmin):
    """Admin interface for ActivityFeedItem model."""

    list_display = ['user', 'activity_type', 'content_preview', 'related_user', 'created_at']
    list_filter = ['activity_type', 'created_at']
    search_fields = ['user__email', 'user__display_name']
    ordering = ['-created_at']
    readonly_fields = ['created_at']
    raw_id_fields = ['user', 'related_user']

    fieldsets = (
        ('Activity', {
            'fields': ('user', 'activity_type', 'content')
        }),
        ('Relations', {
            'fields': ('related_user', 'data'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )

    def content_preview(self, obj):
        """Display a truncated preview of the content JSON."""
        content_str = str(obj.content)
        return content_str[:80] + '...' if len(content_str) > 80 else content_str
    content_preview.short_description = 'Content'


@admin.register(BlockedUser)
class BlockedUserAdmin(admin.ModelAdmin):
    """Admin interface for BlockedUser model."""

    list_display = ['blocker', 'blocked', 'reason_preview', 'created_at']
    list_filter = ['created_at']
    search_fields = [
        'blocker__email', 'blocker__display_name',
        'blocked__email', 'blocked__display_name',
    ]
    ordering = ['-created_at']
    readonly_fields = ['created_at']
    raw_id_fields = ['blocker', 'blocked']

    def reason_preview(self, obj):
        if not obj.reason:
            return '-'
        return obj.reason[:60] + '...' if len(obj.reason) > 60 else obj.reason
    reason_preview.short_description = 'Reason'


@admin.register(ReportedUser)
class ReportedUserAdmin(admin.ModelAdmin):
    """Admin interface for ReportedUser model."""

    list_display = ['reporter', 'reported', 'category', 'status', 'created_at']
    list_filter = ['status', 'category', 'created_at']
    search_fields = [
        'reporter__email', 'reporter__display_name',
        'reported__email', 'reported__display_name',
        'reason',
    ]
    ordering = ['-created_at']
    readonly_fields = ['created_at', 'updated_at']
    raw_id_fields = ['reporter', 'reported']

    fieldsets = (
        ('Report', {
            'fields': ('reporter', 'reported', 'reason', 'category')
        }),
        ('Review', {
            'fields': ('status', 'admin_notes')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
