"""
State-only migration that declares all chat models in apps.chat
without touching the database (tables already exist under apps.conversations).

Uses SeparateDatabaseAndState with database_operations=[] so Django
knows about the models but does not attempt to CREATE the tables.
"""

import uuid

import django.db.models.deletion
import encrypted_model_fields.fields
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("buddies", "0001_initial"),
        ("dreams", "0001_initial"),
        ("users", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.CreateModel(
                    name="Conversation",
                    fields=[
                        (
                            "id",
                            models.UUIDField(
                                default=uuid.uuid4,
                                editable=False,
                                primary_key=True,
                                serialize=False,
                            ),
                        ),
                        (
                            "conversation_type",
                            models.CharField(
                                choices=[
                                    ("dream_creation", "Dream Creation"),
                                    ("planning", "Planning"),
                                    ("check_in", "Check In"),
                                    ("adjustment", "Adjustment"),
                                    ("general", "General"),
                                    ("motivation", "Motivation"),
                                    ("rescue", "Rescue"),
                                    ("buddy_chat", "Buddy Chat"),
                                ],
                                db_index=True,
                                default="general",
                                max_length=20,
                            ),
                        ),
                        (
                            "title",
                            encrypted_model_fields.fields.EncryptedCharField(
                                blank=True,
                                help_text="Optional conversation title (encrypted at rest)",
                                max_length=255,
                            ),
                        ),
                        (
                            "is_pinned",
                            models.BooleanField(
                                default=False,
                                help_text="Whether this conversation is pinned",
                            ),
                        ),
                        ("total_messages", models.IntegerField(default=0)),
                        ("total_tokens_used", models.IntegerField(default=0)),
                        ("is_active", models.BooleanField(default=True)),
                        ("created_at", models.DateTimeField(auto_now_add=True)),
                        ("updated_at", models.DateTimeField(auto_now=True)),
                        (
                            "buddy_pairing",
                            models.ForeignKey(
                                blank=True,
                                help_text="If set, this is a buddy-to-buddy chat conversation.",
                                null=True,
                                on_delete=django.db.models.deletion.SET_NULL,
                                related_name="conversations",
                                to="buddies.buddypairing",
                            ),
                        ),
                        (
                            "dream",
                            models.ForeignKey(
                                blank=True,
                                null=True,
                                on_delete=django.db.models.deletion.SET_NULL,
                                related_name="conversations",
                                to="dreams.dream",
                            ),
                        ),
                        (
                            "user",
                            models.ForeignKey(
                                on_delete=django.db.models.deletion.CASCADE,
                                related_name="conversations",
                                to=settings.AUTH_USER_MODEL,
                            ),
                        ),
                    ],
                    options={
                        "db_table": "conversations",
                        "ordering": ["-updated_at"],
                    },
                ),
                migrations.CreateModel(
                    name="ConversationTemplate",
                    fields=[
                        (
                            "id",
                            models.UUIDField(
                                default=uuid.uuid4,
                                editable=False,
                                primary_key=True,
                                serialize=False,
                            ),
                        ),
                        ("name", models.CharField(max_length=200)),
                        (
                            "conversation_type",
                            models.CharField(
                                choices=[
                                    ("dream_creation", "Dream Creation"),
                                    ("planning", "Planning"),
                                    ("check_in", "Check In"),
                                    ("adjustment", "Adjustment"),
                                    ("general", "General"),
                                    ("motivation", "Motivation"),
                                    ("rescue", "Rescue"),
                                    ("buddy_chat", "Buddy Chat"),
                                ],
                                default="general",
                                max_length=20,
                            ),
                        ),
                        (
                            "system_prompt",
                            models.TextField(
                                help_text="Custom system prompt for this template."
                            ),
                        ),
                        (
                            "starter_messages",
                            models.JSONField(
                                blank=True,
                                default=list,
                                help_text='List of starter message dicts: [{"role": "assistant", "content": "..."}]',
                            ),
                        ),
                        (
                            "description",
                            models.TextField(
                                blank=True,
                                help_text="Description shown to users when browsing templates.",
                            ),
                        ),
                        (
                            "icon",
                            models.CharField(
                                blank=True,
                                help_text="Emoji or icon identifier for the template.",
                                max_length=50,
                            ),
                        ),
                        ("is_active", models.BooleanField(default=True)),
                        ("created_at", models.DateTimeField(auto_now_add=True)),
                        ("updated_at", models.DateTimeField(auto_now=True)),
                    ],
                    options={
                        "db_table": "conversation_templates",
                        "ordering": ["name"],
                    },
                ),
                migrations.CreateModel(
                    name="Message",
                    fields=[
                        (
                            "id",
                            models.UUIDField(
                                default=uuid.uuid4,
                                editable=False,
                                primary_key=True,
                                serialize=False,
                            ),
                        ),
                        (
                            "role",
                            models.CharField(
                                choices=[
                                    ("user", "User"),
                                    ("assistant", "Assistant"),
                                    ("system", "System"),
                                ],
                                db_index=True,
                                max_length=10,
                            ),
                        ),
                        (
                            "content",
                            encrypted_model_fields.fields.EncryptedTextField(
                                help_text="Message content (encrypted at rest)."
                            ),
                        ),
                        (
                            "audio_url",
                            models.URLField(
                                blank=True,
                                help_text="URL to the uploaded audio file for voice messages.",
                                max_length=500,
                            ),
                        ),
                        (
                            "audio_duration",
                            models.PositiveIntegerField(
                                blank=True,
                                help_text="Duration of the audio file in seconds.",
                                null=True,
                            ),
                        ),
                        (
                            "transcription",
                            encrypted_model_fields.fields.EncryptedTextField(
                                blank=True,
                                default="",
                                help_text="Whisper transcription of the audio message (encrypted at rest).",
                            ),
                        ),
                        (
                            "image_url",
                            models.URLField(
                                blank=True,
                                help_text="URL to an uploaded image for GPT-4 Vision analysis.",
                                max_length=500,
                            ),
                        ),
                        ("is_pinned", models.BooleanField(default=False)),
                        ("is_liked", models.BooleanField(default=False)),
                        (
                            "reactions",
                            models.JSONField(
                                blank=True,
                                default=list,
                                help_text="List of reaction emojis",
                            ),
                        ),
                        (
                            "metadata",
                            models.JSONField(blank=True, default=dict),
                        ),
                        ("created_at", models.DateTimeField(auto_now_add=True)),
                        (
                            "conversation",
                            models.ForeignKey(
                                on_delete=django.db.models.deletion.CASCADE,
                                related_name="messages",
                                to="chat.conversation",
                            ),
                        ),
                    ],
                    options={
                        "db_table": "messages",
                        "ordering": ["created_at"],
                    },
                ),
                migrations.CreateModel(
                    name="ConversationBranch",
                    fields=[
                        (
                            "id",
                            models.UUIDField(
                                default=uuid.uuid4,
                                editable=False,
                                primary_key=True,
                                serialize=False,
                            ),
                        ),
                        (
                            "name",
                            models.CharField(
                                blank=True,
                                help_text="Optional label for this branch.",
                                max_length=100,
                            ),
                        ),
                        ("created_at", models.DateTimeField(auto_now_add=True)),
                        (
                            "conversation",
                            models.ForeignKey(
                                on_delete=django.db.models.deletion.CASCADE,
                                related_name="branches",
                                to="chat.conversation",
                            ),
                        ),
                        (
                            "parent_message",
                            models.ForeignKey(
                                help_text="The message from which this branch diverges.",
                                on_delete=django.db.models.deletion.CASCADE,
                                related_name="branches",
                                to="chat.message",
                            ),
                        ),
                    ],
                    options={
                        "db_table": "conversation_branches",
                        "ordering": ["-created_at"],
                    },
                ),
                # Add branch FK to Message
                migrations.AddField(
                    model_name="message",
                    name="branch",
                    field=models.ForeignKey(
                        blank=True,
                        help_text="Branch this message belongs to (null = main conversation).",
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="messages",
                        to="chat.conversationbranch",
                    ),
                ),
                migrations.CreateModel(
                    name="ConversationSummary",
                    fields=[
                        (
                            "id",
                            models.UUIDField(
                                default=uuid.uuid4,
                                editable=False,
                                primary_key=True,
                                serialize=False,
                            ),
                        ),
                        (
                            "summary",
                            encrypted_model_fields.fields.EncryptedTextField(),
                        ),
                        ("key_points", models.JSONField(default=list)),
                        ("created_at", models.DateTimeField(auto_now_add=True)),
                        (
                            "conversation",
                            models.ForeignKey(
                                on_delete=django.db.models.deletion.CASCADE,
                                related_name="summaries",
                                to="chat.conversation",
                            ),
                        ),
                        (
                            "end_message",
                            models.ForeignKey(
                                on_delete=django.db.models.deletion.CASCADE,
                                related_name="summary_ends",
                                to="chat.message",
                            ),
                        ),
                        (
                            "start_message",
                            models.ForeignKey(
                                on_delete=django.db.models.deletion.CASCADE,
                                related_name="summary_starts",
                                to="chat.message",
                            ),
                        ),
                    ],
                    options={
                        "db_table": "conversation_summaries",
                        "ordering": ["-created_at"],
                    },
                ),
                migrations.CreateModel(
                    name="Call",
                    fields=[
                        (
                            "id",
                            models.UUIDField(
                                default=uuid.uuid4,
                                editable=False,
                                primary_key=True,
                                serialize=False,
                            ),
                        ),
                        (
                            "call_type",
                            models.CharField(
                                choices=[("voice", "Voice"), ("video", "Video")],
                                default="voice",
                                max_length=5,
                            ),
                        ),
                        (
                            "status",
                            models.CharField(
                                choices=[
                                    ("ringing", "Ringing"),
                                    ("accepted", "Accepted"),
                                    ("in_progress", "In Progress"),
                                    ("completed", "Completed"),
                                    ("rejected", "Rejected"),
                                    ("missed", "Missed"),
                                    ("cancelled", "Cancelled"),
                                ],
                                db_index=True,
                                default="ringing",
                                max_length=15,
                            ),
                        ),
                        (
                            "started_at",
                            models.DateTimeField(blank=True, null=True),
                        ),
                        (
                            "ended_at",
                            models.DateTimeField(blank=True, null=True),
                        ),
                        ("duration_seconds", models.IntegerField(default=0)),
                        ("created_at", models.DateTimeField(auto_now_add=True)),
                        ("updated_at", models.DateTimeField(auto_now=True)),
                        (
                            "buddy_pairing",
                            models.ForeignKey(
                                blank=True,
                                null=True,
                                on_delete=django.db.models.deletion.SET_NULL,
                                related_name="calls",
                                to="buddies.buddypairing",
                            ),
                        ),
                        (
                            "callee",
                            models.ForeignKey(
                                on_delete=django.db.models.deletion.CASCADE,
                                related_name="incoming_calls",
                                to=settings.AUTH_USER_MODEL,
                            ),
                        ),
                        (
                            "caller",
                            models.ForeignKey(
                                on_delete=django.db.models.deletion.CASCADE,
                                related_name="outgoing_calls",
                                to=settings.AUTH_USER_MODEL,
                            ),
                        ),
                    ],
                    options={
                        "db_table": "calls",
                        "ordering": ["-created_at"],
                    },
                ),
                migrations.CreateModel(
                    name="MessageReadStatus",
                    fields=[
                        (
                            "id",
                            models.BigAutoField(
                                auto_created=True,
                                primary_key=True,
                                serialize=False,
                                verbose_name="ID",
                            ),
                        ),
                        ("last_read_at", models.DateTimeField(auto_now=True)),
                        (
                            "conversation",
                            models.ForeignKey(
                                on_delete=django.db.models.deletion.CASCADE,
                                related_name="read_statuses",
                                to="chat.conversation",
                            ),
                        ),
                        (
                            "last_read_message",
                            models.ForeignKey(
                                blank=True,
                                null=True,
                                on_delete=django.db.models.deletion.SET_NULL,
                                to="chat.message",
                            ),
                        ),
                        (
                            "user",
                            models.ForeignKey(
                                on_delete=django.db.models.deletion.CASCADE,
                                to=settings.AUTH_USER_MODEL,
                            ),
                        ),
                    ],
                    options={
                        "db_table": "message_read_statuses",
                    },
                ),
                migrations.AddConstraint(
                    model_name="messagereadstatus",
                    constraint=models.UniqueConstraint(
                        fields=("user", "conversation"),
                        name="unique_read_status",
                    ),
                ),
                migrations.CreateModel(
                    name="ChatMemory",
                    fields=[
                        (
                            "id",
                            models.UUIDField(
                                default=uuid.uuid4,
                                editable=False,
                                primary_key=True,
                                serialize=False,
                            ),
                        ),
                        (
                            "key",
                            models.CharField(
                                choices=[
                                    ("preference", "Preference"),
                                    ("fact", "Fact"),
                                    ("goal_context", "Goal Context"),
                                    ("style", "Style"),
                                ],
                                db_index=True,
                                default="fact",
                                help_text="Memory category (preference, fact, goal_context, style).",
                                max_length=100,
                            ),
                        ),
                        (
                            "content",
                            encrypted_model_fields.fields.EncryptedTextField(
                                help_text="The remembered information (encrypted at rest)."
                            ),
                        ),
                        (
                            "importance",
                            models.IntegerField(
                                default=3,
                                help_text="Importance level from 1 (low) to 5 (critical).",
                            ),
                        ),
                        ("is_active", models.BooleanField(default=True)),
                        ("created_at", models.DateTimeField(auto_now_add=True)),
                        ("updated_at", models.DateTimeField(auto_now=True)),
                        (
                            "source_conversation",
                            models.ForeignKey(
                                blank=True,
                                help_text="Conversation this memory was extracted from.",
                                null=True,
                                on_delete=django.db.models.deletion.SET_NULL,
                                related_name="extracted_memories",
                                to="chat.conversation",
                            ),
                        ),
                        (
                            "user",
                            models.ForeignKey(
                                on_delete=django.db.models.deletion.CASCADE,
                                related_name="chat_memories",
                                to=settings.AUTH_USER_MODEL,
                            ),
                        ),
                    ],
                    options={
                        "db_table": "chat_memories",
                        "ordering": ["-importance", "-updated_at"],
                    },
                ),
            ],
        ),
    ]
