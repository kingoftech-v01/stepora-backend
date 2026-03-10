"""
Conversation and Message models for AI chat.
"""

import uuid

from django.conf import settings
from django.db import models
from encrypted_model_fields.fields import EncryptedCharField, EncryptedTextField

from apps.dreams.models import Dream
from apps.users.models import User


class Conversation(models.Model):
    """AI conversation session, also used for buddy-to-buddy chat."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="conversations"
    )
    dream = models.ForeignKey(
        Dream,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="conversations",
    )
    buddy_pairing = models.ForeignKey(
        "buddies.BuddyPairing",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="conversations",
        help_text="If set, this is a buddy-to-buddy chat conversation.",
    )

    TYPE_CHOICES = [
        ("dream_creation", "Dream Creation"),
        ("planning", "Planning"),
        ("check_in", "Check In"),
        ("adjustment", "Adjustment"),
        ("general", "General"),
        ("motivation", "Motivation"),
        ("rescue", "Rescue"),
        ("buddy_chat", "Buddy Chat"),
    ]
    conversation_type = models.CharField(
        max_length=20, choices=TYPE_CHOICES, default="general", db_index=True
    )

    title = EncryptedCharField(
        max_length=255,
        blank=True,
        help_text="Optional conversation title (encrypted at rest)",
    )
    is_pinned = models.BooleanField(
        default=False, help_text="Whether this conversation is pinned"
    )

    # Metadata
    total_messages = models.IntegerField(default=0)
    total_tokens_used = models.IntegerField(default=0)

    # Status
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "conversations"
        ordering = ["-updated_at"]
        indexes = [
            models.Index(fields=["user", "-updated_at"]),
            models.Index(fields=["conversation_type"]),
        ]

    def __str__(self):
        return f"{self.conversation_type} - {self.user.email}"

    def add_message(self, role, content, metadata=None):
        """Add a message to this conversation."""
        message = Message.objects.create(
            conversation=self, role=role, content=content, metadata=metadata or {}
        )

        self.total_messages += 1
        if metadata and "tokens_used" in metadata:
            self.total_tokens_used += metadata["tokens_used"]
        self.save(update_fields=["total_messages", "total_tokens_used", "updated_at"])

        return message

    def get_messages_for_api(self, limit=20, max_tokens=None):
        """Get recent messages formatted for OpenAI API, with dream context, memory, and summary."""
        api_messages = []

        # Inject user memory context (cross-conversation recall)
        from integrations.openai_service import OpenAIService

        memory_context = OpenAIService.build_memory_context(self.user)
        if memory_context:
            api_messages.append(
                {
                    "role": "system",
                    "content": memory_context,
                }
            )

        # Always inject dream context if conversation is linked to a dream
        if self.dream:
            dream = self.dream
            dream_context = (
                f"DREAM CONTEXT (always active — base all responses on this dream):\n"
                f"- Dream Title: {dream.title}\n"
                f"- Dream Description: {dream.description}\n"
                f"- Category: {dream.category}\n"
                f"- Status: {dream.status}\n"
                f"- Progress: {dream.progress_percentage:.0f}%\n"
            )

            # Add calibration profile if available
            if dream.calibration_status == "completed" and dream.ai_analysis:
                cal_summary = dream.ai_analysis.get("calibration_summary", {})
                if cal_summary:
                    profile = cal_summary.get("user_profile", {})
                    if profile:
                        dream_context += (
                            f"- Experience Level: {profile.get('experience_level', 'unknown')}\n"
                            f"- Available Hours/Week: {profile.get('available_hours_per_week', 'unknown')}\n"
                            f"- Primary Motivation: {profile.get('primary_motivation', 'unknown')}\n"
                        )

            # Add current goals with status (top 5)
            goals = list(dream.goals.order_by("order")[:5])
            if goals:
                dream_context += "\nCurrent Goals:\n"
                for g in goals:
                    dream_context += (
                        f"  - {g.title} ({g.status}, {g.progress_percentage:.0f}%)\n"
                    )

            api_messages.append(
                {
                    "role": "system",
                    "content": dream_context,
                }
            )

        elif self.conversation_type != "buddy_chat":
            # Fallback: look up user's most recent active dream for context
            recent_dream = (
                Dream.objects.filter(user=self.user, status="active")
                .order_by("-updated_at")
                .first()
            )
            if recent_dream:
                api_messages.append(
                    {
                        "role": "system",
                        "content": (
                            f"Note: This conversation is not linked to a specific dream, "
                            f"but the user's most recent active dream is: "
                            f'"{recent_dream.title}" ({recent_dream.progress_percentage:.0f}% complete). '
                            f"You may reference it if relevant to the conversation."
                        ),
                    }
                )

        # Prepend latest summary as system context if available
        latest_summary = self.summaries.order_by("-created_at").first()
        if latest_summary:
            api_messages.append(
                {
                    "role": "system",
                    "content": f"Previous conversation summary: {latest_summary.summary}",
                }
            )

        messages = self.messages.order_by("-created_at")[:limit]
        messages = list(reversed(messages))  # Chronological order

        # Token-based trimming if tiktoken available
        if max_tokens:
            try:
                import tiktoken

                enc = tiktoken.encoding_for_model("gpt-4")
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

        api_messages.extend(
            [
                {
                    "role": msg.role,
                    "content": msg.content,
                }
                for msg in messages
            ]
        )

        return api_messages


class Message(models.Model):
    """Individual message in a conversation."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.ForeignKey(
        Conversation, on_delete=models.CASCADE, related_name="messages"
    )

    ROLE_CHOICES = [
        ("user", "User"),
        ("assistant", "Assistant"),
        ("system", "System"),
    ]
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, db_index=True)
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
    transcription = EncryptedTextField(
        blank=True,
        default="",
        help_text="Whisper transcription of the audio message (encrypted at rest).",
    )

    # Image analysis support
    image_url = models.URLField(
        max_length=500,
        blank=True,
        help_text="URL to an uploaded image for GPT-4 Vision analysis.",
    )

    # Interaction fields
    is_pinned = models.BooleanField(default=False)
    is_liked = models.BooleanField(default=False)
    reactions = models.JSONField(
        default=list, blank=True, help_text="List of reaction emojis"
    )

    # Branch support
    branch = models.ForeignKey(
        "ConversationBranch",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="messages",
        help_text="Branch this message belongs to (null = main conversation).",
    )

    # Metadata (tokens used, model version, etc.)
    metadata = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "messages"
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["conversation", "created_at"]),
            models.Index(fields=["role"]),
            models.Index(fields=["branch", "created_at"]),
        ]

    def __str__(self):
        content_preview = (
            self.content[:50] + "..." if len(self.content) > 50 else self.content
        )
        return f"{self.role}: {content_preview}"


class ConversationBranch(models.Model):
    """A branch point in a conversation, allowing exploration of alternate paths."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.ForeignKey(
        Conversation, on_delete=models.CASCADE, related_name="branches"
    )
    parent_message = models.ForeignKey(
        Message,
        on_delete=models.CASCADE,
        related_name="branches",
        help_text="The message from which this branch diverges.",
    )
    name = models.CharField(
        max_length=100, blank=True, help_text="Optional label for this branch."
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "conversation_branches"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["conversation", "-created_at"]),
            models.Index(fields=["parent_message"]),
        ]

    def __str__(self):
        label = self.name or "Unnamed branch"
        return f"Branch: {label} (from {self.parent_message_id})"


class ConversationSummary(models.Model):
    """Summarized conversation for long-term context."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.ForeignKey(
        Conversation, on_delete=models.CASCADE, related_name="summaries"
    )

    summary = EncryptedTextField()
    key_points = models.JSONField(default=list)

    # Messages range this summary covers
    start_message = models.ForeignKey(
        Message, on_delete=models.CASCADE, related_name="summary_starts"
    )
    end_message = models.ForeignKey(
        Message, on_delete=models.CASCADE, related_name="summary_ends"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "conversation_summaries"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Summary: {self.conversation.id} ({self.start_message.id} to {self.end_message.id})"


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
        User, on_delete=models.CASCADE, related_name="outgoing_calls"
    )
    callee = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="incoming_calls"
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
        db_table = "calls"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["caller", "-created_at"]),
            models.Index(fields=["callee", "-created_at"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self):
        return f"{self.call_type} call: {self.caller} -> {self.callee} ({self.status})"


class MessageReadStatus(models.Model):
    """High-water mark for tracking last-read message per user per conversation."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    conversation = models.ForeignKey(
        Conversation, on_delete=models.CASCADE, related_name="read_statuses"
    )
    last_read_message = models.ForeignKey(
        Message, on_delete=models.SET_NULL, null=True, blank=True
    )
    last_read_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "message_read_statuses"
        constraints = [
            models.UniqueConstraint(
                fields=["user", "conversation"], name="unique_read_status"
            ),
        ]

    def __str__(self):
        return f"{self.user} read {self.conversation} up to {self.last_read_message_id}"


class ChatMemory(models.Model):
    """Persistent memory extracted from AI conversations.

    Stores key facts, preferences, and context that the AI should
    remember across conversations for a given user.
    """

    KEY_CHOICES = [
        ("preference", "Preference"),
        ("fact", "Fact"),
        ("goal_context", "Goal Context"),
        ("style", "Style"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="chat_memories"
    )
    key = models.CharField(
        max_length=100,
        choices=KEY_CHOICES,
        default="fact",
        db_index=True,
        help_text="Memory category (preference, fact, goal_context, style).",
    )
    content = EncryptedTextField(
        help_text="The remembered information (encrypted at rest)."
    )
    source_conversation = models.ForeignKey(
        Conversation,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="extracted_memories",
        help_text="Conversation this memory was extracted from.",
    )
    importance = models.IntegerField(
        default=3, help_text="Importance level from 1 (low) to 5 (critical)."
    )
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "chat_memories"
        ordering = ["-importance", "-updated_at"]
        indexes = [
            models.Index(fields=["user", "-importance"]),
            models.Index(fields=["user", "key"]),
            models.Index(fields=["user", "is_active"]),
        ]

    def __str__(self):
        return (
            f"[{self.key}] {self.content[:60]}{'...' if len(self.content) > 60 else ''}"
        )


class ConversationTemplate(models.Model):
    """Pre-built conversation templates for common use cases."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    conversation_type = models.CharField(
        max_length=20,
        choices=Conversation.TYPE_CHOICES,
        default="general",
    )
    system_prompt = models.TextField(
        help_text="Custom system prompt for this template."
    )
    starter_messages = models.JSONField(
        default=list,
        blank=True,
        help_text='List of starter message dicts: [{"role": "assistant", "content": "..."}]',
    )
    description = models.TextField(
        blank=True, help_text="Description shown to users when browsing templates."
    )
    icon = models.CharField(
        max_length=50,
        blank=True,
        help_text="Emoji or icon identifier for the template.",
    )
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "conversation_templates"
        ordering = ["name"]

    def __str__(self):
        return f"Template: {self.name} ({self.conversation_type})"
