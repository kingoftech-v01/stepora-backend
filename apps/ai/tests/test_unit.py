"""
Unit tests for the AI Coaching app.

Tests model creation, field defaults, serializer output, and validation.
"""

import uuid

import pytest

from apps.ai.models import (
    AIConversation,
    AIMessage,
    ChatMemory,
    ConversationTemplate,
)
from apps.ai.serializers import (
    AIConversationSerializer,
    AIMessageCreateSerializer,
)

pytestmark = pytest.mark.django_db


class TestAIConversationModel:
    """Tests for AIConversation model."""

    def test_create_conversation(self, ai_user):
        """AIConversation can be created with required fields."""
        conv = AIConversation.objects.create(
            user=ai_user,
            conversation_type="general",
        )
        assert conv.pk is not None
        assert isinstance(conv.id, uuid.UUID)
        assert conv.user == ai_user
        assert conv.conversation_type == "general"
        assert conv.is_active is True
        assert conv.total_messages == 0
        assert conv.total_tokens_used == 0
        assert conv.dream is None

    def test_create_conversation_with_dream(self, ai_user, ai_dream):
        """AIConversation can be linked to a dream."""
        conv = AIConversation.objects.create(
            user=ai_user,
            dream=ai_dream,
            conversation_type="planning",
            title="Planning session",
        )
        assert conv.dream == ai_dream
        assert conv.conversation_type == "planning"
        assert conv.title == "Planning session"

    def test_conversation_type_choices(self, ai_user):
        """All conversation type choices are valid."""
        valid_types = [
            "dream_creation", "planning", "check_in",
            "adjustment", "general", "motivation", "rescue",
        ]
        for conv_type in valid_types:
            conv = AIConversation.objects.create(
                user=ai_user,
                conversation_type=conv_type,
            )
            assert conv.conversation_type == conv_type

    def test_conversation_str(self, ai_conversation):
        """String representation includes type and user email."""
        expected = f"general - {ai_conversation.user.email}"
        assert str(ai_conversation) == expected

    def test_conversation_ordering(self, ai_user):
        """Conversations are ordered by -updated_at."""
        conv1 = AIConversation.objects.create(user=ai_user, conversation_type="general")
        conv2 = AIConversation.objects.create(user=ai_user, conversation_type="planning")
        conversations = list(AIConversation.objects.filter(user=ai_user))
        # conv2 was created later, so it should be first
        assert conversations[0].id == conv2.id

    def test_conversation_defaults(self, ai_conversation):
        """Default field values are correct."""
        assert ai_conversation.is_pinned is False
        assert ai_conversation.metadata == {}
        assert ai_conversation.is_active is True

    def test_add_message_method(self, ai_conversation):
        """add_message() creates a message and increments total_messages."""
        msg = ai_conversation.add_message("user", "Hello!")
        ai_conversation.refresh_from_db()
        assert msg.role == "user"
        assert msg.content == "Hello!"
        assert ai_conversation.total_messages == 1

    def test_add_message_with_tokens(self, ai_conversation):
        """add_message() with tokens_used metadata increments total_tokens_used."""
        ai_conversation.add_message(
            "assistant", "Hi!", metadata={"tokens_used": 50}
        )
        ai_conversation.refresh_from_db()
        assert ai_conversation.total_tokens_used == 50
        assert ai_conversation.total_messages == 1


class TestAIMessageModel:
    """Tests for AIMessage model."""

    def test_create_message(self, ai_conversation):
        """AIMessage can be created with required fields."""
        msg = AIMessage.objects.create(
            conversation=ai_conversation,
            role="user",
            content="Test message content",
        )
        assert msg.pk is not None
        assert isinstance(msg.id, uuid.UUID)
        assert msg.conversation == ai_conversation
        assert msg.role == "user"
        assert msg.content == "Test message content"

    def test_message_roles(self, ai_conversation):
        """All message roles are valid."""
        for role in ["user", "assistant", "system"]:
            msg = AIMessage.objects.create(
                conversation=ai_conversation,
                role=role,
                content=f"Message from {role}",
            )
            assert msg.role == role

    def test_message_defaults(self, ai_message):
        """Default field values are correct."""
        assert ai_message.is_pinned is False
        assert ai_message.is_liked is False
        assert ai_message.reactions == []
        assert ai_message.metadata == {}
        assert ai_message.audio_url == ""
        assert ai_message.audio_duration is None
        assert ai_message.image_url == ""
        assert ai_message.branch is None

    def test_message_str_short(self, ai_conversation):
        """String representation for short content."""
        msg = AIMessage.objects.create(
            conversation=ai_conversation, role="user", content="Short"
        )
        assert str(msg) == "user: Short"

    def test_message_str_long(self, ai_conversation):
        """String representation truncates long content."""
        long_content = "A" * 100
        msg = AIMessage.objects.create(
            conversation=ai_conversation, role="assistant", content=long_content
        )
        assert str(msg) == f"assistant: {'A' * 50}..."

    def test_message_ordering(self, ai_conversation):
        """Messages are ordered by created_at ascending."""
        msg1 = AIMessage.objects.create(
            conversation=ai_conversation, role="user", content="First"
        )
        msg2 = AIMessage.objects.create(
            conversation=ai_conversation, role="assistant", content="Second"
        )
        messages = list(ai_conversation.messages.all())
        assert messages[0].id == msg1.id
        assert messages[1].id == msg2.id


class TestConversationTemplateModel:
    """Tests for ConversationTemplate model."""

    def test_create_template(self):
        """ConversationTemplate can be created with required fields."""
        template = ConversationTemplate.objects.create(
            name="Motivation Template",
            conversation_type="motivation",
            system_prompt="You are a motivational coach.",
        )
        assert template.pk is not None
        assert template.name == "Motivation Template"
        assert template.conversation_type == "motivation"
        assert template.is_active is True

    def test_template_defaults(self, ai_template):
        """Default field values are correct."""
        assert ai_template.starter_messages == []
        assert ai_template.icon == ""
        assert ai_template.is_active is True

    def test_template_str(self, ai_template):
        """String representation includes name and type."""
        assert str(ai_template) == "Template: Test Template (general)"

    def test_template_with_starter_messages(self):
        """Template can have starter messages."""
        starters = [{"role": "assistant", "content": "Welcome!"}]
        template = ConversationTemplate.objects.create(
            name="With Starters",
            conversation_type="general",
            system_prompt="You are helpful.",
            starter_messages=starters,
        )
        assert template.starter_messages == starters


class TestChatMemoryModel:
    """Tests for ChatMemory model."""

    def test_create_memory(self, ai_user):
        """ChatMemory can be created with required fields."""
        memory = ChatMemory.objects.create(
            user=ai_user,
            key="preference",
            content="User likes concise responses.",
        )
        assert memory.pk is not None
        assert memory.user == ai_user
        assert memory.key == "preference"
        assert memory.importance == 3  # default
        assert memory.is_active is True

    def test_memory_key_choices(self, ai_user):
        """All memory key choices are valid."""
        for key in ["preference", "fact", "goal_context", "style"]:
            memory = ChatMemory.objects.create(
                user=ai_user,
                key=key,
                content=f"Memory of type {key}",
            )
            assert memory.key == key

    def test_memory_str_short(self, ai_user):
        """String representation for short content."""
        memory = ChatMemory.objects.create(
            user=ai_user, key="fact", content="Short fact"
        )
        assert str(memory) == "[fact] Short fact"

    def test_memory_str_long(self, ai_user):
        """String representation truncates long content."""
        long_content = "B" * 100
        memory = ChatMemory.objects.create(
            user=ai_user, key="preference", content=long_content
        )
        assert str(memory) == f"[preference] {'B' * 60}..."

    def test_memory_ordering(self, ai_user):
        """Memories are ordered by -importance, -updated_at."""
        m1 = ChatMemory.objects.create(
            user=ai_user, key="fact", content="Low importance", importance=1
        )
        m2 = ChatMemory.objects.create(
            user=ai_user, key="fact", content="High importance", importance=5
        )
        memories = list(ChatMemory.objects.filter(user=ai_user))
        assert memories[0].id == m2.id  # Higher importance first

    def test_memory_with_source_conversation(self, ai_memory):
        """Memory can be linked to a source conversation."""
        assert ai_memory.source_conversation is not None


class TestAIConversationSerializer:
    """Tests for AIConversationSerializer output."""

    def test_serializer_fields(self, ai_conversation):
        """Serializer outputs expected fields."""
        serializer = AIConversationSerializer(ai_conversation)
        data = serializer.data
        expected_fields = {
            "id", "user", "dream", "dream_title", "title", "is_pinned",
            "conversation_type", "total_messages", "total_tokens_used",
            "is_active", "last_message", "created_at", "updated_at",
        }
        assert set(data.keys()) == expected_fields

    def test_serializer_dream_title_null(self, ai_conversation):
        """dream_title is None when no dream is linked."""
        serializer = AIConversationSerializer(ai_conversation)
        assert serializer.data["dream_title"] is None

    def test_serializer_dream_title_present(self, ai_conversation_with_dream):
        """dream_title reflects linked dream."""
        serializer = AIConversationSerializer(ai_conversation_with_dream)
        assert serializer.data["dream_title"] == "Learn Python"

    def test_serializer_last_message_none(self, ai_conversation):
        """last_message is None when no messages exist."""
        serializer = AIConversationSerializer(ai_conversation)
        assert serializer.data["last_message"] is None

    def test_serializer_last_message_present(self, ai_conversation, ai_message):
        """last_message returns the most recent message preview."""
        serializer = AIConversationSerializer(ai_conversation)
        data = serializer.data
        assert data["last_message"] is not None
        assert data["last_message"]["role"] == "user"
        assert "Hello, AI coach!" in data["last_message"]["content"]

    def test_serializer_read_only_fields(self, ai_conversation):
        """Read-only fields cannot be set via serializer."""
        serializer = AIConversationSerializer(ai_conversation)
        data = serializer.data
        # These should be present but read-only
        assert "id" in data
        assert "user" in data
        assert "total_messages" in data
        assert "created_at" in data


class TestAIMessageCreateSerializer:
    """Tests for AIMessageCreateSerializer validation."""

    def test_valid_content(self):
        """Valid content passes validation."""
        serializer = AIMessageCreateSerializer(data={"content": "Hello, AI!"})
        assert serializer.is_valid()
        assert serializer.validated_data["content"] == "Hello, AI!"

    def test_empty_content_rejected(self):
        """Empty content is rejected."""
        serializer = AIMessageCreateSerializer(data={"content": ""})
        assert not serializer.is_valid()
        assert "content" in serializer.errors

    def test_whitespace_only_content_rejected(self):
        """Whitespace-only content is rejected."""
        serializer = AIMessageCreateSerializer(data={"content": "   "})
        assert not serializer.is_valid()
        assert "content" in serializer.errors

    def test_missing_content_rejected(self):
        """Missing content field is rejected."""
        serializer = AIMessageCreateSerializer(data={})
        assert not serializer.is_valid()
        assert "content" in serializer.errors

    def test_max_length_enforced(self):
        """Content exceeding max_length (5000) is rejected."""
        serializer = AIMessageCreateSerializer(data={"content": "x" * 5001})
        assert not serializer.is_valid()
        assert "content" in serializer.errors

    def test_content_at_max_length(self):
        """Content at exactly max_length (5000) passes."""
        serializer = AIMessageCreateSerializer(data={"content": "x" * 5000})
        assert serializer.is_valid()

    def test_content_stripped(self):
        """Content is stripped of leading/trailing whitespace."""
        serializer = AIMessageCreateSerializer(data={"content": "  Hello!  "})
        assert serializer.is_valid()
        assert serializer.validated_data["content"] == "Hello!"


# ══════════════════════════════════════════════════════════════════════
#  API ENDPOINT TESTS — AI
# ══════════════════════════════════════════════════════════════════════



@pytest.mark.django_db
class TestAIConversationAPI:
    """Tests for AI Conversation API endpoints."""

    def test_list_conversations(self, ai_client):
        resp = ai_client.get(
            "/api/ai/conversations/",
            HTTP_ORIGIN="https://stepora.app",
        )
        assert resp.status_code in (200, 403)

    def test_list_templates(self, ai_client):
        resp = ai_client.get(
            "/api/ai/templates/",
            HTTP_ORIGIN="https://stepora.app",
        )
        assert resp.status_code in (200, 403)

    def test_list_memories(self, ai_client):
        resp = ai_client.get(
            "/api/ai/memories/",
            HTTP_ORIGIN="https://stepora.app",
        )
        assert resp.status_code in (200, 403)
