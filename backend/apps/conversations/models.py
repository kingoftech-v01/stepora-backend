"""
Conversation and Message models for AI chat.
"""

import uuid
from django.db import models
from apps.users.models import User
from apps.dreams.models import Dream


class Conversation(models.Model):
    """AI conversation session."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='conversations')
    dream = models.ForeignKey(
        Dream,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='conversations'
    )

    TYPE_CHOICES = [
        ('dream_creation', 'Dream Creation'),
        ('planning', 'Planning'),
        ('check_in', 'Check In'),
        ('adjustment', 'Adjustment'),
        ('general', 'General'),
        ('motivation', 'Motivation'),
        ('rescue', 'Rescue'),
    ]
    conversation_type = models.CharField(
        max_length=20,
        choices=TYPE_CHOICES,
        default='general',
        db_index=True
    )

    # Metadata
    total_messages = models.IntegerField(default=0)
    total_tokens_used = models.IntegerField(default=0)

    # Status
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'conversations'
        ordering = ['-updated_at']
        indexes = [
            models.Index(fields=['user', '-updated_at']),
            models.Index(fields=['conversation_type']),
        ]

    def __str__(self):
        return f"{self.conversation_type} - {self.user.email}"

    def add_message(self, role, content, metadata=None):
        """Add a message to this conversation."""
        message = Message.objects.create(
            conversation=self,
            role=role,
            content=content,
            metadata=metadata or {}
        )

        self.total_messages += 1
        if metadata and 'tokens_used' in metadata:
            self.total_tokens_used += metadata['tokens_used']
        self.save(update_fields=['total_messages', 'total_tokens_used', 'updated_at'])

        return message

    def get_messages_for_api(self, limit=20):
        """Get recent messages formatted for OpenAI API."""
        messages = self.messages.order_by('-created_at')[:limit]
        messages = list(reversed(messages))  # Chronological order

        return [
            {
                'role': msg.role,
                'content': msg.content,
            }
            for msg in messages
        ]


class Message(models.Model):
    """Individual message in a conversation."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name='messages'
    )

    ROLE_CHOICES = [
        ('user', 'User'),
        ('assistant', 'Assistant'),
        ('system', 'System'),
    ]
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, db_index=True)
    content = models.TextField()

    # Metadata (tokens used, model version, etc.)
    metadata = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'messages'
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['conversation', 'created_at']),
            models.Index(fields=['role']),
        ]

    def __str__(self):
        content_preview = self.content[:50] + '...' if len(self.content) > 50 else self.content
        return f"{self.role}: {content_preview}"


class ConversationSummary(models.Model):
    """Summarized conversation for long-term context."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name='summaries'
    )

    summary = models.TextField()
    key_points = models.JSONField(default=list)

    # Messages range this summary covers
    start_message = models.ForeignKey(
        Message,
        on_delete=models.CASCADE,
        related_name='summary_starts'
    )
    end_message = models.ForeignKey(
        Message,
        on_delete=models.CASCADE,
        related_name='summary_ends'
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'conversation_summaries'
        ordering = ['-created_at']

    def __str__(self):
        return f"Summary: {self.conversation.id} ({self.start_message.id} to {self.end_message.id})"
