"""
Django admin configuration for Conversations app.
"""

from django.contrib import admin
from .models import Conversation, Message, ConversationSummary


class MessageInline(admin.TabularInline):
    """Inline admin for Messages within Conversation."""
    model = Message
    extra = 0
    fields = ['role', 'content_preview', 'created_at']
    readonly_fields = ['content_preview', 'created_at']
    can_delete = False

    def content_preview(self, obj):
        return obj.content[:100] + '...' if len(obj.content) > 100 else obj.content
    content_preview.short_description = 'Content'


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    """Admin interface for Conversation model."""

    list_display = ['id', 'user', 'conversation_type', 'dream', 'total_messages', 'total_tokens_used', 'is_active', 'created_at']
    list_filter = ['conversation_type', 'is_active', 'created_at']
    search_fields = ['user__email', 'dream__title']
    ordering = ['-updated_at']
    readonly_fields = ['total_messages', 'total_tokens_used', 'created_at', 'updated_at']

    inlines = [MessageInline]

    fieldsets = (
        ('Basic Info', {
            'fields': ('user', 'dream', 'conversation_type', 'is_active')
        }),
        ('Statistics', {
            'fields': ('total_messages', 'total_tokens_used')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    """Admin interface for Message model."""

    list_display = ['conversation', 'role', 'content_preview', 'created_at']
    list_filter = ['role', 'created_at']
    search_fields = ['content', 'conversation__user__email']
    ordering = ['-created_at']
    readonly_fields = ['created_at']

    def content_preview(self, obj):
        return obj.content[:100] + '...' if len(obj.content) > 100 else obj.content
    content_preview.short_description = 'Content'


@admin.register(ConversationSummary)
class ConversationSummaryAdmin(admin.ModelAdmin):
    """Admin interface for Conversation summaries."""

    list_display = ['conversation', 'summary_preview', 'created_at']
    list_filter = ['created_at']
    search_fields = ['summary', 'conversation__user__email']
    readonly_fields = ['created_at']

    def summary_preview(self, obj):
        return obj.summary[:100] + '...' if len(obj.summary) > 100 else obj.summary
    summary_preview.short_description = 'Summary'
