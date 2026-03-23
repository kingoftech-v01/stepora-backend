"""
Serializers for Chat app (friend/buddy chat only).
"""

from typing import Optional

from django.utils.translation import gettext as _
from rest_framework import serializers

from core.sanitizers import sanitize_text

from .models import (
    Call,
    ChatConversation,
    ChatMessage,
)


class ChatMessageSerializer(serializers.ModelSerializer):
    """Serializer for ChatMessage model."""

    class Meta:
        model = ChatMessage
        fields = [
            "id",
            "conversation",
            "role",
            "content",
            "audio_url",
            "audio_duration",
            "image_url",
            "is_pinned",
            "is_liked",
            "reactions",
            "metadata",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]
        extra_kwargs = {
            "id": {"help_text": "Unique identifier for the message."},
            "conversation": {"help_text": "Conversation this message belongs to."},
            "role": {"help_text": "Role of the message sender."},
            "content": {"help_text": "Text content of the message."},
            "audio_url": {"help_text": "URL to an attached audio recording."},
            "audio_duration": {
                "help_text": "Duration of the audio recording in seconds."
            },
            "image_url": {"help_text": "URL to an attached image."},
            "is_pinned": {"help_text": "Whether this message is pinned."},
            "is_liked": {"help_text": "Whether the user liked this message."},
            "reactions": {"help_text": "Emoji reactions on this message."},
            "metadata": {"help_text": "Additional metadata for the message."},
            "created_at": {"help_text": "Timestamp when the message was created."},
        }


class ChatMessageCreateSerializer(serializers.Serializer):
    """Serializer for creating/sending a chat message."""

    content = serializers.CharField(
        max_length=5000, help_text="Text content of the message to send."
    )

    def validate_content(self, value):
        """Validate and sanitize message content."""
        if not value.strip():
            raise serializers.ValidationError(_("Message content cannot be empty"))
        return sanitize_text(value.strip())


class ChatConversationSerializer(serializers.ModelSerializer):
    """Basic serializer for ChatConversation model."""

    last_message = serializers.SerializerMethodField(
        help_text="Preview of the most recent message."
    )
    unread_count = serializers.SerializerMethodField(
        help_text="Number of unread messages for the current user."
    )
    target_user = serializers.SerializerMethodField(
        help_text="Other participant info for buddy/friend chat conversations."
    )

    class Meta:
        model = ChatConversation
        fields = [
            "id",
            "user",
            "title",
            "total_messages",
            "is_active",
            "last_message",
            "unread_count",
            "target_user",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "user",
            "total_messages",
            "created_at",
            "updated_at",
        ]
        extra_kwargs = {
            "id": {"help_text": "Unique identifier for the conversation."},
            "user": {"help_text": "Owner of the conversation."},
            "title": {"help_text": "Title of the conversation."},
            "total_messages": {
                "help_text": "Total number of messages in the conversation."
            },
            "is_active": {"help_text": "Whether the conversation is still active."},
            "created_at": {"help_text": "Timestamp when the conversation was created."},
            "updated_at": {
                "help_text": "Timestamp when the conversation was last updated."
            },
        }

    def get_last_message(self, obj) -> Optional[dict]:
        """Get the last message in the conversation."""
        if hasattr(obj, "_last_message_list"):
            last_msg = obj._last_message_list[0] if obj._last_message_list else None
        else:
            last_msg = obj.messages.order_by("-created_at").first()
        if last_msg:
            return {
                "role": last_msg.role,
                "content": (
                    last_msg.content[:100] + "..."
                    if len(last_msg.content) > 100
                    else last_msg.content
                ),
                "created_at": last_msg.created_at,
            }
        return None

    def get_unread_count(self, obj) -> int:
        """Count messages after the user's last-read high-water mark."""
        request = self.context.get("request")
        if not request or not request.user or not request.user.is_authenticated:
            return 0

        user_id_str = str(request.user.id)

        read_status = None
        if (
            hasattr(obj, "_prefetched_objects_cache")
            and "read_statuses" in obj._prefetched_objects_cache
        ):
            for rs in obj.read_statuses.all():
                if rs.user_id == request.user.id:
                    read_status = rs
                    break
        else:
            read_status = obj.read_statuses.filter(user=request.user).first()

        if read_status and read_status.last_read_message:
            return (
                obj.messages.filter(
                    created_at__gt=read_status.last_read_message.created_at
                )
                .exclude(metadata__sender_id=user_id_str)
                .exclude(role="system")
                .count()
            )

        return (
            obj.messages.exclude(metadata__sender_id=user_id_str)
            .exclude(role="system")
            .filter(role="user")
            .count()
        )

    def get_target_user(self, obj) -> Optional[dict]:
        """Get the other participant's info for friend chat conversations."""
        request = self.context.get("request")
        if not request or not request.user:
            return None

        def _user_dict(u):
            return {
                "id": str(u.id),
                "display_name": u.display_name or u.email,
                "avatar": u.avatar.url if getattr(u, "avatar", None) else "",
            }

        # Use the target_user FK if set
        if obj.target_user_id:
            if obj.target_user_id != request.user.id:
                return _user_dict(obj.target_user)
            return _user_dict(obj.user)

        # Fallback: if current user is NOT the conv owner,
        # the owner IS the other participant
        if obj.user_id != request.user.id:
            return _user_dict(obj.user)

        return None


class ChatConversationDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for ChatConversation with messages (latest 50)."""

    messages = serializers.SerializerMethodField(
        help_text="Latest messages in the conversation (max 50)."
    )

    class Meta:
        model = ChatConversation
        fields = [
            "id",
            "user",
            "title",
            "total_messages",
            "is_active",
            "messages",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "user",
            "total_messages",
            "created_at",
            "updated_at",
        ]

    def get_messages(self, obj):
        """Return the latest 50 messages to prevent response bloat."""
        msgs = obj.messages.order_by("-created_at")[:50]
        return ChatMessageSerializer(reversed(list(msgs)), many=True).data


class CallHistorySerializer(serializers.ModelSerializer):
    """Serializer for call history entries."""

    caller_name = serializers.CharField(source="caller.display_name", read_only=True)
    callee_name = serializers.CharField(source="callee.display_name", read_only=True)
    caller_id = serializers.UUIDField(source="caller.id", read_only=True)
    callee_id = serializers.UUIDField(source="callee.id", read_only=True)

    class Meta:
        model = Call
        fields = [
            "id",
            "caller_id",
            "callee_id",
            "caller_name",
            "callee_name",
            "call_type",
            "status",
            "started_at",
            "ended_at",
            "duration_seconds",
            "created_at",
        ]
        read_only_fields = fields
