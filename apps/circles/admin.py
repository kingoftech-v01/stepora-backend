"""
Django admin configuration for the Circles system.

Provides admin interfaces for managing circles, memberships, posts,
and challenges with inline editing and filtering capabilities.
"""

from django.contrib import admin

from .models import (
    Circle, CircleMembership, CirclePost, CircleChallenge,
    PostReaction, CircleInvitation, ChallengeProgress,
    CircleMessage, CircleCall, CircleCallParticipant,
)


class CircleMembershipInline(admin.TabularInline):
    """Inline admin for CircleMembership within Circle."""

    model = CircleMembership
    extra = 0
    fields = ['user', 'role', 'joined_at']
    readonly_fields = ['joined_at']
    raw_id_fields = ['user']


class CirclePostInline(admin.TabularInline):
    """Inline admin for CirclePost within Circle."""

    model = CirclePost
    extra = 0
    fields = ['author', 'content', 'created_at']
    readonly_fields = ['created_at']
    raw_id_fields = ['author']


class CircleChallengeInline(admin.TabularInline):
    """Inline admin for CircleChallenge within Circle."""

    model = CircleChallenge
    extra = 0
    fields = ['title', 'status', 'start_date', 'end_date']


@admin.register(Circle)
class CircleAdmin(admin.ModelAdmin):
    """Admin interface for Circle model."""

    list_display = [
        'name', 'category', 'is_public', 'creator',
        'max_members', 'member_count', 'created_at',
    ]
    list_filter = ['category', 'is_public', 'created_at']
    search_fields = ['name', 'description', 'creator__email', 'creator__display_name']
    ordering = ['-created_at']
    readonly_fields = ['created_at', 'updated_at']
    raw_id_fields = ['creator']

    inlines = [CircleMembershipInline, CircleChallengeInline, CirclePostInline]

    fieldsets = (
        ('Basic Info', {
            'fields': ('name', 'description', 'category')
        }),
        ('Settings', {
            'fields': ('is_public', 'max_members', 'creator')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def member_count(self, obj):
        """Display the current member count."""
        return obj.member_count
    member_count.short_description = 'Members'


@admin.register(CircleMembership)
class CircleMembershipAdmin(admin.ModelAdmin):
    """Admin interface for CircleMembership model."""

    list_display = ['user', 'circle', 'role', 'joined_at']
    list_filter = ['role', 'joined_at']
    search_fields = ['user__email', 'user__display_name', 'circle__name']
    ordering = ['-joined_at']
    raw_id_fields = ['user', 'circle']

    fieldsets = (
        ('Membership', {
            'fields': ('circle', 'user', 'role')
        }),
    )


@admin.register(CirclePost)
class CirclePostAdmin(admin.ModelAdmin):
    """Admin interface for CirclePost model."""

    list_display = ['author', 'circle', 'content_preview', 'created_at']
    list_filter = ['circle', 'created_at']
    search_fields = ['content', 'author__email', 'author__display_name']
    ordering = ['-created_at']
    readonly_fields = ['created_at', 'updated_at']
    raw_id_fields = ['author', 'circle']

    fieldsets = (
        ('Post', {
            'fields': ('circle', 'author', 'content')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def content_preview(self, obj):
        """Display a truncated preview of the post content."""
        return obj.content[:80] + '...' if len(obj.content) > 80 else obj.content
    content_preview.short_description = 'Content'


@admin.register(CircleChallenge)
class CircleChallengeAdmin(admin.ModelAdmin):
    """Admin interface for CircleChallenge model."""

    list_display = [
        'title', 'circle', 'status', 'start_date',
        'end_date', 'participant_count', 'created_at',
    ]
    list_filter = ['status', 'start_date', 'circle']
    search_fields = ['title', 'description', 'circle__name']
    ordering = ['-start_date']
    readonly_fields = ['created_at', 'updated_at']
    raw_id_fields = ['circle']
    filter_horizontal = ['participants']

    fieldsets = (
        ('Challenge Info', {
            'fields': ('circle', 'title', 'description', 'status')
        }),
        ('Dates', {
            'fields': ('start_date', 'end_date')
        }),
        ('Participants', {
            'fields': ('participants',),
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def participant_count(self, obj):
        """Display the number of participants."""
        return obj.participant_count
    participant_count.short_description = 'Participants'


@admin.register(PostReaction)
class PostReactionAdmin(admin.ModelAdmin):
    """Admin interface for PostReaction model."""

    list_display = ['user', 'post', 'reaction_type', 'created_at']
    list_filter = ['reaction_type', 'created_at']
    search_fields = ['user__email', 'user__display_name']
    readonly_fields = ['created_at']
    raw_id_fields = ['user', 'post']


@admin.register(CircleInvitation)
class CircleInvitationAdmin(admin.ModelAdmin):
    """Admin interface for CircleInvitation model."""

    list_display = ['circle', 'inviter', 'invitee', 'invite_code', 'status', 'expires_at', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['circle__name', 'inviter__email', 'invitee__email', 'invite_code']
    readonly_fields = ['created_at']
    raw_id_fields = ['circle', 'inviter', 'invitee']


@admin.register(ChallengeProgress)
class ChallengeProgressAdmin(admin.ModelAdmin):
    """Admin interface for ChallengeProgress model."""

    list_display = ['user', 'challenge', 'progress_value', 'created_at']
    list_filter = ['created_at']
    search_fields = ['user__email', 'user__display_name', 'challenge__title']
    readonly_fields = ['created_at']
    raw_id_fields = ['user', 'challenge']


@admin.register(CircleMessage)
class CircleMessageAdmin(admin.ModelAdmin):
    """Admin interface for CircleMessage model."""

    list_display = ['sender', 'circle', 'content_preview', 'created_at']
    list_filter = ['created_at']
    search_fields = ['sender__email', 'sender__display_name', 'circle__name']
    readonly_fields = ['created_at']
    raw_id_fields = ['sender', 'circle']

    def content_preview(self, obj):
        """Display a truncated preview of the message content."""
        return obj.content[:80] + '...' if len(obj.content) > 80 else obj.content
    content_preview.short_description = 'Content'


@admin.register(CircleCall)
class CircleCallAdmin(admin.ModelAdmin):
    """Admin interface for CircleCall model."""

    list_display = ['circle', 'initiator', 'call_type', 'status', 'started_at', 'ended_at', 'duration_seconds']
    list_filter = ['call_type', 'status', 'started_at']
    search_fields = ['circle__name', 'initiator__email', 'agora_channel']
    readonly_fields = ['started_at']
    raw_id_fields = ['circle', 'initiator']


@admin.register(CircleCallParticipant)
class CircleCallParticipantAdmin(admin.ModelAdmin):
    """Admin interface for CircleCallParticipant model."""

    list_display = ['user', 'call', 'joined_at', 'left_at']
    list_filter = ['joined_at']
    search_fields = ['user__email', 'user__display_name']
    readonly_fields = ['joined_at']
    raw_id_fields = ['user', 'call']
