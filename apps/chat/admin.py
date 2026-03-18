"""
Django admin configuration for Chat app (friend/buddy chat and calls).
"""

from django.contrib import admin

from .models import (
    Call,
    ChatConversation,
    ChatMessage,
    MessageReadStatus,
)


class ChatMessageInline(admin.TabularInline):
    """Inline admin for ChatMessages within ChatConversation."""

    model = ChatMessage
    extra = 0
    fields = ["role", "content_preview", "created_at"]
    readonly_fields = ["content_preview", "created_at"]
    can_delete = False

    def content_preview(self, obj):
        return obj.content[:100] + "..." if len(obj.content) > 100 else obj.content

    content_preview.short_description = "Content"


@admin.register(ChatConversation)
class ChatConversationAdmin(admin.ModelAdmin):
    """Admin interface for ChatConversation model."""

    list_display = [
        "id",
        "user",
        "target_user",
        "total_messages",
        "is_active",
        "created_at",
    ]
    list_filter = ["is_active", "created_at"]
    search_fields = ["user__email", "target_user__email"]
    ordering = ["-updated_at"]
    readonly_fields = [
        "total_messages",
        "created_at",
        "updated_at",
    ]

    inlines = [ChatMessageInline]

    fieldsets = (
        ("Basic Info", {"fields": ("user", "target_user", "buddy_pairing", "is_active")}),
        ("Statistics", {"fields": ("total_messages",)}),
        ("Timestamps", {"fields": ("created_at", "updated_at")}),
    )


@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    """Admin interface for ChatMessage model."""

    list_display = ["conversation", "role", "content_preview", "created_at"]
    list_filter = ["role", "created_at"]
    search_fields = ["content", "conversation__user__email"]
    ordering = ["-created_at"]
    readonly_fields = ["created_at"]

    def content_preview(self, obj):
        return obj.content[:100] + "..." if len(obj.content) > 100 else obj.content

    content_preview.short_description = "Content"


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
