"""
Django admin configuration for the Social system.

Provides admin interfaces for managing friendships, follows,
and activity feed items.
"""

from django.contrib import admin

from .models import (
    Friendship, UserFollow, ActivityFeedItem, BlockedUser, ReportedUser,
    Story, StoryView, ActivityLike, ActivityComment, DreamPost,
    DreamPostLike, DreamPostComment, DreamEncouragement, SocialEvent,
    SocialEventRegistration, RecentSearch, SavedPost, PostReaction,
)


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


@admin.register(Story)
class StoryAdmin(admin.ModelAdmin):
    list_display = ['user', 'media_type', 'created_at', 'expires_at', 'view_count']
    list_filter = ['media_type', 'created_at']
    search_fields = ['user__email', 'user__display_name', 'caption']
    readonly_fields = ['id', 'created_at', 'view_count']


@admin.register(StoryView)
class StoryViewAdmin(admin.ModelAdmin):
    list_display = ['story', 'user', 'viewed_at']
    list_filter = ['viewed_at']
    readonly_fields = ['id', 'viewed_at']
    raw_id_fields = ['story', 'user']


@admin.register(ActivityLike)
class ActivityLikeAdmin(admin.ModelAdmin):
    """Admin interface for ActivityLike model."""

    list_display = ['user', 'activity', 'created_at']
    list_filter = ['created_at']
    search_fields = ['user__email', 'user__display_name']
    readonly_fields = ['created_at']
    raw_id_fields = ['user', 'activity']


@admin.register(ActivityComment)
class ActivityCommentAdmin(admin.ModelAdmin):
    """Admin interface for ActivityComment model."""

    list_display = ['user', 'activity', 'created_at']
    list_filter = ['created_at']
    search_fields = ['user__email', 'user__display_name']
    readonly_fields = ['created_at']
    raw_id_fields = ['user', 'activity']


@admin.register(DreamPost)
class DreamPostAdmin(admin.ModelAdmin):
    """Admin interface for DreamPost model."""

    list_display = ['user', 'post_type', 'visibility', 'likes_count', 'comments_count', 'is_pinned', 'created_at']
    list_filter = ['post_type', 'visibility', 'media_type', 'is_pinned', 'created_at']
    search_fields = ['user__email', 'user__display_name', 'content']
    ordering = ['-created_at']
    readonly_fields = ['created_at', 'updated_at']
    raw_id_fields = ['user', 'dream', 'linked_goal', 'linked_milestone', 'linked_task']


@admin.register(DreamPostLike)
class DreamPostLikeAdmin(admin.ModelAdmin):
    """Admin interface for DreamPostLike model."""

    list_display = ['user', 'post', 'created_at']
    list_filter = ['created_at']
    search_fields = ['user__email', 'user__display_name']
    readonly_fields = ['created_at']
    raw_id_fields = ['user', 'post']


@admin.register(DreamPostComment)
class DreamPostCommentAdmin(admin.ModelAdmin):
    """Admin interface for DreamPostComment model."""

    list_display = ['user', 'post', 'parent', 'created_at']
    list_filter = ['created_at']
    search_fields = ['user__email', 'user__display_name', 'content']
    readonly_fields = ['created_at']
    raw_id_fields = ['user', 'post', 'parent']


@admin.register(DreamEncouragement)
class DreamEncouragementAdmin(admin.ModelAdmin):
    """Admin interface for DreamEncouragement model."""

    list_display = ['user', 'post', 'encouragement_type', 'created_at']
    list_filter = ['encouragement_type', 'created_at']
    search_fields = ['user__email', 'user__display_name']
    readonly_fields = ['created_at']
    raw_id_fields = ['user', 'post']


@admin.register(SocialEvent)
class SocialEventAdmin(admin.ModelAdmin):
    """Admin interface for SocialEvent model."""

    list_display = ['title', 'creator', 'event_type', 'status', 'start_time', 'end_time', 'participants_count', 'created_at']
    list_filter = ['event_type', 'status', 'created_at']
    search_fields = ['title', 'description', 'creator__email', 'creator__display_name']
    ordering = ['-created_at']
    readonly_fields = ['created_at', 'updated_at']
    raw_id_fields = ['creator', 'post', 'dream']


@admin.register(SocialEventRegistration)
class SocialEventRegistrationAdmin(admin.ModelAdmin):
    """Admin interface for SocialEventRegistration model."""

    list_display = ['user', 'event', 'status', 'registered_at']
    list_filter = ['status', 'registered_at']
    search_fields = ['user__email', 'user__display_name', 'event__title']
    readonly_fields = ['registered_at']
    raw_id_fields = ['user', 'event']


@admin.register(RecentSearch)
class RecentSearchAdmin(admin.ModelAdmin):
    """Admin interface for RecentSearch model."""

    list_display = ['user', 'query', 'search_type', 'created_at']
    list_filter = ['search_type', 'created_at']
    search_fields = ['user__email', 'user__display_name']
    readonly_fields = ['created_at']
    raw_id_fields = ['user']


@admin.register(SavedPost)
class SavedPostAdmin(admin.ModelAdmin):
    """Admin interface for SavedPost model."""

    list_display = ['user', 'post', 'created_at']
    list_filter = ['created_at']
    search_fields = ['user__email', 'user__display_name']
    ordering = ['-created_at']
    readonly_fields = ['id', 'created_at']
    raw_id_fields = ['user', 'post']


@admin.register(PostReaction)
class PostReactionAdmin(admin.ModelAdmin):
    """Admin interface for PostReaction (dream post emoji reactions) model."""

    list_display = ['user', 'post', 'reaction_type', 'created_at']
    list_filter = ['reaction_type', 'created_at']
    search_fields = ['user__email', 'user__display_name']
    ordering = ['-created_at']
    readonly_fields = ['id', 'created_at']
    raw_id_fields = ['user', 'post']
