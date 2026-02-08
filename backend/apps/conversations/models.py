"""
Conversation and Message models for AI chat.
"""

import uuid
from django.db import models
from apps.users.models import User
from apps.dreams.models import Dream


class Conversation(models.Model):
    """AI conversation session, also used for buddy-to-buddy chat."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='conversations')
    dream = models.ForeignKey(
        Dream,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='conversations'
    )
    buddy_pairing = models.ForeignKey(
        'buddies.BuddyPairing',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='conversations',
        help_text='If set, this is a buddy-to-buddy chat conversation.'
    )

    TYPE_CHOICES = [
        ('dream_creation', 'Dream Creation'),
        ('planning', 'Planning'),
        ('check_in', 'Check In'),
        ('adjustment', 'Adjustment'),
        ('general', 'General'),
        ('motivation', 'Motivation'),
        ('rescue', 'Rescue'),
        ('buddy_chat', 'Buddy Chat'),
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

    def get_messages_for_api(self, limit=20, max_tokens=None):
        """Get recent messages formatted for OpenAI API, with summary context."""
        api_messages = []

        # Prepend latest summary as system context if available
        latest_summary = self.summaries.order_by('-created_at').first()
        if latest_summary:
            api_messages.append({
                'role': 'system',
                'content': f"Previous conversation summary: {latest_summary.summary}",
            })

        messages = self.messages.order_by('-created_at')[:limit]
        messages = list(reversed(messages))  # Chronological order

        # Token-based trimming if tiktoken available
        if max_tokens:
            try:
                import tiktoken
                enc = tiktoken.encoding_for_model('gpt-4')
                total_tokens = 0
                trimmed = []
                for msg in reversed(messages):
                    msg_tokens = len(enc.encode(msg.content))
                    if total_tokens + msg_tokens > max_tokens:
                        break
                    trimmed.insert(0, msg)
                    total_tokens += msg_tokens
                messages = trimmed
            except ImportError:
                pass

        api_messages.extend([
            {
                'role': msg.role,
                'content': msg.content,
            }
            for msg in messages
        ])

        return api_messages


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

    # Voice message support
    audio_url = models.URLField(
        max_length=500,
        blank=True,
        help_text='URL to the uploaded audio file for voice messages.'
    )
    transcription = models.TextField(
        blank=True,
        help_text='Whisper transcription of the audio message.'
    )

    # Image analysis support
    image_url = models.URLField(
        max_length=500,
        blank=True,
        help_text='URL to an uploaded image for GPT-4 Vision analysis.'
    )

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


class ConversationTemplate(models.Model):
    """Pre-built conversation templates for common use cases."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    conversation_type = models.CharField(
        max_length=20,
        choices=Conversation.TYPE_CHOICES,
        default='general',
    )
    system_prompt = models.TextField(
        help_text='Custom system prompt for this template.'
    )
    starter_messages = models.JSONField(
        default=list,
        blank=True,
        help_text='List of starter message dicts: [{"role": "assistant", "content": "..."}]'
    )
    description = models.TextField(
        blank=True,
        help_text='Description shown to users when browsing templates.'
    )
    icon = models.CharField(
        max_length=50,
        blank=True,
        help_text='Emoji or icon identifier for the template.'
    )
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'conversation_templates'
        ordering = ['name']

    def __str__(self):
        return f"Template: {self.name} ({self.conversation_type})"
