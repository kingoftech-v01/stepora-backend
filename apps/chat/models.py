"""
Models for friend/buddy chat and voice/video calls.

Standalone chat app that owns buddy messaging and call functionality.
AI conversation models are in apps.ai.
"""

import uuid

from django.conf import settings
from django.db import models
from encrypted_model_fields.fields import EncryptedCharField, EncryptedTextField



class ChatConversation(models.Model):
    """Friend/buddy chat conversation."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="chat_conversations"
    )
    target_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="chat_conversations_as_target",
        help_text="The other participant in a friend/buddy chat conversation.",
    )
    buddy_pairing = models.ForeignKey(
        "buddies.BuddyPairing",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="chat_conversations",
        help_text="If set, this is a buddy-to-buddy chat conversation.",
    )

    title = EncryptedCharField(
        max_length=255,
        blank=True,
        help_text="Optional conversation title (encrypted at rest)",
    )

    # Metadata
    total_messages = models.IntegerField(default=0)

    # Status
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "chat"
        db_table = "chat_conversations"
        ordering = ["-updated_at"]
        indexes = [
            models.Index(fields=["user", "-updated_at"]),
        ]

    def __str__(self):
        return f"Chat - {self.user.email}"


class ChatMessage(models.Model):
    """Individual message in a friend/buddy chat conversation."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.ForeignKey(
        ChatConversation, on_delete=models.CASCADE, related_name="messages"
    )

    ROLE_CHOICES = [
        ("user", "User"),
        ("system", "System"),
    ]
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default="user", db_index=True)
    content = EncryptedTextField(help_text="Message content (encrypted at rest).")

    # Voice message support
    audio_url = models.URLField(
        max_length=500,
        blank=True,
        help_text="URL to the uploaded audio file for voice messages.",
    )
    audio_duration = models.PositiveIntegerField(
        null=True, blank=True, help_text="Duration of the audio file in seconds."
    )

    # Image support
    image_url = models.URLField(
        max_length=500,
        blank=True,
        help_text="URL to an uploaded image.",
    )

    # Interaction fields
    is_pinned = models.BooleanField(default=False)
    is_liked = models.BooleanField(default=False)
    reactions = models.JSONField(
        default=list, blank=True, help_text="List of reaction emojis"
    )

    # Metadata (sender_id, etc.)
    metadata = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "chat"
        db_table = "chat_messages"
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["conversation", "created_at"]),
            models.Index(fields=["role"]),
        ]

    def __str__(self):
        content_preview = (
            self.content[:50] + "..." if len(self.content) > 50 else self.content
        )
        return f"{self.role}: {content_preview}"


class MessageReadStatus(models.Model):
    """High-water mark for tracking last-read message per user per conversation."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    conversation = models.ForeignKey(
        ChatConversation, on_delete=models.CASCADE, related_name="read_statuses"
    )
    last_read_message = models.ForeignKey(
        ChatMessage, on_delete=models.SET_NULL, null=True, blank=True
    )
    last_read_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "chat"
        db_table = "chat_message_read_statuses"
        constraints = [
            models.UniqueConstraint(
                fields=["user", "conversation"], name="unique_chat_read_status"
            ),
        ]

    def __str__(self):
        return f"{self.user} read {self.conversation} up to {self.last_read_message_id}"


class Call(models.Model):
    """Voice/video call between two buddy users."""

    CALL_TYPE_CHOICES = [
        ("voice", "Voice"),
        ("video", "Video"),
    ]
    STATUS_CHOICES = [
        ("ringing", "Ringing"),
        ("accepted", "Accepted"),
        ("in_progress", "In Progress"),
        ("completed", "Completed"),
        ("rejected", "Rejected"),
        ("missed", "Missed"),
        ("cancelled", "Cancelled"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    caller = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="outgoing_calls"
    )
    callee = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="incoming_calls"
    )
    buddy_pairing = models.ForeignKey(
        "buddies.BuddyPairing",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="calls",
    )
    call_type = models.CharField(
        max_length=5, choices=CALL_TYPE_CHOICES, default="voice"
    )
    status = models.CharField(
        max_length=15, choices=STATUS_CHOICES, default="ringing", db_index=True
    )
    started_at = models.DateTimeField(null=True, blank=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    duration_seconds = models.IntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "chat"
        db_table = "chat_calls"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["caller", "-created_at"]),
            models.Index(fields=["callee", "-created_at"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self):
        return f"{self.call_type} call: {self.caller} -> {self.callee} ({self.status})"
