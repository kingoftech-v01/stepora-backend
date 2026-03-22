"""
Unit tests for the Chat app.

Tests model creation, field defaults, serializer output, and validation.
"""

import uuid

import pytest

from apps.chat.models import Call, ChatConversation, ChatMessage, MessageReadStatus
from apps.chat.serializers import (
    ChatConversationSerializer,
    ChatMessageCreateSerializer,
)


class TestChatConversationModel:
    """Tests for ChatConversation model."""

    def test_create_conversation(self, chat_user, chat_user2):
        """ChatConversation can be created with user and target_user."""
        conv = ChatConversation.objects.create(
            user=chat_user,
            target_user=chat_user2,
        )
        assert conv.pk is not None
        assert isinstance(conv.id, uuid.UUID)
        assert conv.user == chat_user
        assert conv.target_user == chat_user2
        assert conv.is_active is True
        assert conv.total_messages == 0

    def test_create_conversation_without_target(self, chat_user):
        """ChatConversation can be created without a target_user."""
        conv = ChatConversation.objects.create(user=chat_user)
        assert conv.target_user is None
        assert conv.buddy_pairing is None

    def test_conversation_defaults(self, chat_conversation):
        """Default field values are correct."""
        assert chat_conversation.is_active is True
        assert chat_conversation.total_messages == 0
        assert chat_conversation.buddy_pairing is None

    def test_conversation_str(self, chat_conversation):
        """String representation includes user email."""
        assert chat_conversation.user.email in str(chat_conversation)

    def test_conversation_ordering(self, chat_user, chat_user2):
        """Conversations are ordered by -updated_at."""
        conv1 = ChatConversation.objects.create(
            user=chat_user, target_user=chat_user2
        )
        conv2 = ChatConversation.objects.create(
            user=chat_user, target_user=chat_user2
        )
        conversations = list(ChatConversation.objects.filter(user=chat_user))
        # conv2 created later, should be first
        assert conversations[0].id == conv2.id


class TestChatMessageModel:
    """Tests for ChatMessage model."""

    def test_create_message(self, chat_conversation, chat_user):
        """ChatMessage can be created with required fields."""
        msg = ChatMessage.objects.create(
            conversation=chat_conversation,
            role="user",
            content="Hello!",
            metadata={"sender_id": str(chat_user.id)},
        )
        assert msg.pk is not None
        assert isinstance(msg.id, uuid.UUID)
        assert msg.conversation == chat_conversation
        assert msg.role == "user"
        assert msg.content == "Hello!"
        assert msg.metadata["sender_id"] == str(chat_user.id)

    def test_message_with_sender_id_in_metadata(self, chat_conversation, chat_user):
        """Message metadata stores sender_id."""
        msg = ChatMessage.objects.create(
            conversation=chat_conversation,
            role="user",
            content="Test",
            metadata={"sender_id": str(chat_user.id)},
        )
        assert "sender_id" in msg.metadata
        assert msg.metadata["sender_id"] == str(chat_user.id)

    def test_message_defaults(self, chat_message):
        """Default field values are correct."""
        assert chat_message.is_pinned is False
        assert chat_message.is_liked is False
        assert chat_message.reactions == []
        assert chat_message.audio_url == ""
        assert chat_message.audio_duration is None
        assert chat_message.image_url == ""

    def test_message_str_short(self, chat_conversation):
        """String representation for short content."""
        msg = ChatMessage.objects.create(
            conversation=chat_conversation, role="user", content="Short"
        )
        assert str(msg) == "user: Short"

    def test_message_str_long(self, chat_conversation):
        """String representation truncates long content."""
        long_content = "C" * 100
        msg = ChatMessage.objects.create(
            conversation=chat_conversation, role="user", content=long_content
        )
        assert str(msg) == f"user: {'C' * 50}..."

    def test_message_ordering(self, chat_conversation):
        """Messages are ordered by created_at ascending."""
        msg1 = ChatMessage.objects.create(
            conversation=chat_conversation, role="user", content="First"
        )
        msg2 = ChatMessage.objects.create(
            conversation=chat_conversation, role="user", content="Second"
        )
        messages = list(chat_conversation.messages.all())
        assert messages[0].id == msg1.id
        assert messages[1].id == msg2.id

    def test_message_role_choices(self, chat_conversation):
        """Valid role choices are user and system."""
        for role in ["user", "system"]:
            msg = ChatMessage.objects.create(
                conversation=chat_conversation, role=role, content=f"From {role}"
            )
            assert msg.role == role


class TestMessageReadStatusModel:
    """Tests for MessageReadStatus model."""

    def test_create_read_status(self, chat_user, chat_conversation, chat_message):
        """MessageReadStatus can be created."""
        read_status = MessageReadStatus.objects.create(
            user=chat_user,
            conversation=chat_conversation,
            last_read_message=chat_message,
        )
        assert read_status.pk is not None
        assert read_status.user == chat_user
        assert read_status.conversation == chat_conversation
        assert read_status.last_read_message == chat_message

    def test_read_status_unique_constraint(self, chat_user, chat_conversation, chat_message):
        """Only one read status per user per conversation."""
        MessageReadStatus.objects.create(
            user=chat_user,
            conversation=chat_conversation,
            last_read_message=chat_message,
        )
        from django.db import IntegrityError

        with pytest.raises(IntegrityError):
            MessageReadStatus.objects.create(
                user=chat_user,
                conversation=chat_conversation,
                last_read_message=chat_message,
            )

    def test_read_status_str(self, chat_user, chat_conversation, chat_message):
        """String representation includes user and conversation info."""
        read_status = MessageReadStatus.objects.create(
            user=chat_user,
            conversation=chat_conversation,
            last_read_message=chat_message,
        )
        result = str(read_status)
        assert str(chat_message.id) in result


class TestCallModel:
    """Tests for Call model."""

    def test_create_call(self, chat_user, chat_user2):
        """Call can be created with required fields."""
        call = Call.objects.create(
            caller=chat_user,
            callee=chat_user2,
            call_type="voice",
            status="ringing",
        )
        assert call.pk is not None
        assert isinstance(call.id, uuid.UUID)
        assert call.caller == chat_user
        assert call.callee == chat_user2
        assert call.call_type == "voice"
        assert call.status == "ringing"

    def test_call_defaults(self, chat_call):
        """Default field values are correct."""
        assert chat_call.started_at is None
        assert chat_call.ended_at is None
        assert chat_call.duration_seconds == 0
        assert chat_call.buddy_pairing is None

    def test_call_type_choices(self, chat_user, chat_user2):
        """Both voice and video call types are valid."""
        for call_type in ["voice", "video"]:
            call = Call.objects.create(
                caller=chat_user,
                callee=chat_user2,
                call_type=call_type,
                status="ringing",
            )
            assert call.call_type == call_type

    def test_call_status_choices(self, chat_user, chat_user2):
        """All call status choices are valid."""
        valid_statuses = [
            "ringing", "accepted", "in_progress",
            "completed", "rejected", "missed", "cancelled",
        ]
        for call_status in valid_statuses:
            call = Call.objects.create(
                caller=chat_user,
                callee=chat_user2,
                call_type="voice",
                status=call_status,
            )
            assert call.status == call_status

    def test_call_str(self, chat_call):
        """String representation includes call type and users."""
        result = str(chat_call)
        assert "voice" in result
        assert "ringing" in result

    def test_call_ordering(self, chat_user, chat_user2):
        """Calls are ordered by -created_at."""
        call1 = Call.objects.create(
            caller=chat_user, callee=chat_user2,
            call_type="voice", status="completed"
        )
        call2 = Call.objects.create(
            caller=chat_user, callee=chat_user2,
            call_type="video", status="ringing"
        )
        calls = list(Call.objects.all())
        assert calls[0].id == call2.id  # More recent first


class TestChatConversationSerializerTargetUser:
    """Tests for ChatConversationSerializer target_user output."""

    def test_target_user_output(self, chat_conversation, chat_user):
        """Serializer returns target_user info."""
        from rest_framework.test import APIRequestFactory

        factory = APIRequestFactory()
        request = factory.get("/")
        request.user = chat_user
        serializer = ChatConversationSerializer(
            chat_conversation, context={"request": request}
        )
        data = serializer.data
        assert "target_user" in data
        # Since chat_user is the owner, target_user should be chat_user2
        assert data["target_user"] is not None

    def test_serializer_fields(self, chat_conversation, chat_user):
        """Serializer outputs expected fields."""
        from rest_framework.test import APIRequestFactory

        factory = APIRequestFactory()
        request = factory.get("/")
        request.user = chat_user
        serializer = ChatConversationSerializer(
            chat_conversation, context={"request": request}
        )
        data = serializer.data
        expected_fields = {
            "id", "user", "title", "total_messages", "is_active",
            "last_message", "unread_count", "target_user",
            "created_at", "updated_at",
        }
        assert set(data.keys()) == expected_fields


class TestChatMessageCreateSerializer:
    """Tests for ChatMessageCreateSerializer validation."""

    def test_valid_content(self):
        """Valid content passes validation."""
        serializer = ChatMessageCreateSerializer(data={"content": "Hello!"})
        assert serializer.is_valid()

    def test_empty_content_rejected(self):
        """Empty content is rejected."""
        serializer = ChatMessageCreateSerializer(data={"content": ""})
        assert not serializer.is_valid()
        assert "content" in serializer.errors

    def test_whitespace_only_rejected(self):
        """Whitespace-only content is rejected."""
        serializer = ChatMessageCreateSerializer(data={"content": "   "})
        assert not serializer.is_valid()
        assert "content" in serializer.errors

    def test_missing_content_rejected(self):
        """Missing content field is rejected."""
        serializer = ChatMessageCreateSerializer(data={})
        assert not serializer.is_valid()
        assert "content" in serializer.errors

    def test_max_length_enforced(self):
        """Content exceeding max_length (5000) is rejected."""
        serializer = ChatMessageCreateSerializer(data={"content": "x" * 5001})
        assert not serializer.is_valid()
        assert "content" in serializer.errors

    def test_content_stripped(self):
        """Content is stripped of leading/trailing whitespace."""
        serializer = ChatMessageCreateSerializer(data={"content": "  Hi there  "})
        assert serializer.is_valid()
        assert serializer.validated_data["content"] == "Hi there"


# ══════════════════════════════════════════════════════════════════════
#  API ENDPOINT TESTS — Chat
# ══════════════════════════════════════════════════════════════════════



@pytest.mark.django_db
class TestChatAPI:
    """Tests for Chat API endpoints."""

    def test_list_conversations(self, chat_client):
        resp = chat_client.get(
            "/api/chat/",
            HTTP_ORIGIN="https://stepora.app",
        )
        assert resp.status_code in (200, 403)

    def test_list_conversations_unauthenticated(self):
        from rest_framework.test import APIClient

        client = APIClient()
        resp = client.get(
            "/api/chat/",
            HTTP_ORIGIN="https://stepora.app",
        )
        assert resp.status_code == 401
