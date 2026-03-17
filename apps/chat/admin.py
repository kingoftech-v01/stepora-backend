"""
Django admin configuration for Chat app.
"""

from django.contrib import admin

from .models import (
    Call,
    ChatMemory,
    Conversation,
    ConversationBranch,
    ConversationSummary,
    ConversationTemplate,
    Message,
    MessageReadStatus,
)


class MessageInline(admin.TabularInline):
    """Inline admin for Messages within Conversation."""

    model = Message
    extra = 0
    fields = ["role", "content_preview", "created_at"]
    readonly_fields = ["content_preview", "created_at"]
    can_delete = False

    def content_preview(self, obj):
        return obj.content[:100] + "..." if len(obj.content) > 100 else obj.content

    content_preview.short_description = "Content"


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    """Admin interface for Conversation model."""

    list_display = [
        "id",
        "user",
        "conversation_type",
        "dream",
        "total_messages",
        "total_tokens_used",
        "is_active",
        "created_at",
    ]
    list_filter = ["conversation_type", "is_active", "created_at"]
    search_fields = ["user__email", "dream__title"]
    ordering = ["-updated_at"]
    readonly_fields = [
        "total_messages",
        "total_tokens_used",
        "created_at",
        "updated_at",
    ]

    inlines = [MessageInline]

    fieldsets = (
        ("Basic Info", {"fields": ("user", "dream", "conversation_type", "is_active")}),
        ("Statistics", {"fields": ("total_messages", "total_tokens_used")}),
        ("Timestamps", {"fields": ("created_at", "updated_at")}),
    )


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    """Admin interface for Message model."""

    list_display = ["conversation", "role", "content_preview", "created_at"]
    list_filter = ["role", "created_at"]
    search_fields = ["content", "conversation__user__email"]
    ordering = ["-created_at"]
    readonly_fields = ["created_at"]

    def content_preview(self, obj):
        return obj.content[:100] + "..." if len(obj.content) > 100 else obj.content

    content_preview.short_description = "Content"


@admin.register(ConversationSummary)
class ConversationSummaryAdmin(admin.ModelAdmin):
    """Admin interface for Conversation summaries."""

    list_display = ["conversation", "summary_preview", "created_at"]
    list_filter = ["created_at"]
    search_fields = ["summary", "conversation__user__email"]
    readonly_fields = ["created_at"]

    def summary_preview(self, obj):
        return obj.summary[:100] + "..." if len(obj.summary) > 100 else obj.summary

    summary_preview.short_description = "Summary"


@admin.register(ConversationBranch)
class ConversationBranchAdmin(admin.ModelAdmin):
    """Admin interface for ConversationBranch model."""

    list_display = ["id", "conversation", "name", "parent_message", "created_at"]
    list_filter = ["created_at"]
    search_fields = ["name", "conversation__user__email"]
    ordering = ["-created_at"]
    readonly_fields = ["id", "created_at"]
    raw_id_fields = ["conversation", "parent_message"]


@admin.register(Call)
class CallAdmin(admin.ModelAdmin):
    """Admin interface for Call model."""

    list_display = [
        "caller",
        "callee",
        "call_type",
        "status",
        "duration_seconds",
        "started_at",
        "ended_at",
        "created_at",
    ]
    list_filter = ["call_type", "status", "created_at"]
    search_fields = [
        "caller__email",
        "caller__display_name",
        "callee__email",
        "callee__display_name",
    ]
    ordering = ["-created_at"]
    readonly_fields = ["id", "created_at", "updated_at"]
    raw_id_fields = ["caller", "callee", "buddy_pairing"]


@admin.register(MessageReadStatus)
class MessageReadStatusAdmin(admin.ModelAdmin):
    """Admin interface for MessageReadStatus model."""

    list_display = ["user", "conversation", "last_read_message", "last_read_at"]
    list_filter = ["last_read_at"]
    search_fields = ["user__email", "user__display_name"]
    ordering = ["-last_read_at"]
    readonly_fields = ["last_read_at"]
    raw_id_fields = ["user", "conversation", "last_read_message"]


@admin.register(ChatMemory)
class ChatMemoryAdmin(admin.ModelAdmin):
    """Admin interface for ChatMemory model."""

    list_display = [
        "user",
        "key",
        "importance",
        "is_active",
        "created_at",
        "updated_at",
    ]
    list_filter = ["key", "importance", "is_active", "created_at"]
    search_fields = ["user__email", "user__display_name"]
    ordering = ["-importance", "-updated_at"]
    readonly_fields = ["id", "created_at", "updated_at"]
    raw_id_fields = ["user", "source_conversation"]


@admin.register(ConversationTemplate)
class ConversationTemplateAdmin(admin.ModelAdmin):
    """Admin interface for ConversationTemplate model."""

    list_display = ["name", "conversation_type", "icon", "is_active", "created_at"]
    list_filter = ["conversation_type", "is_active", "created_at"]
    search_fields = ["name", "description"]
    ordering = ["name"]
    readonly_fields = ["id", "created_at", "updated_at"]
