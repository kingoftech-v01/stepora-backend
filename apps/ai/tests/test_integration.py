"""
Integration tests for the AI Coaching app.

Tests API endpoints via the DRF test client.
"""

import pytest
from django.urls import reverse
from rest_framework import status

from apps.ai.models import AIConversation, AIMessage


class TestListAIConversations:
    """Tests for GET /api/ai/conversations/"""

    def test_list_conversations_authenticated(self, ai_client, ai_conversation):
        """Authenticated user can list their AI conversations."""
        response = ai_client.get("/api/ai/conversations/")
        assert response.status_code == status.HTTP_200_OK
        data = response.data
        # Response may be paginated
        results = data.get("results", data)
        assert len(results) >= 1
        conv_ids = [c["id"] for c in results]
        assert str(ai_conversation.id) in conv_ids

    def test_list_conversations_unauthenticated(self):
        """Unauthenticated request returns 401."""
        from rest_framework.test import APIClient

        client = APIClient()
        response = client.get("/api/ai/conversations/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_list_conversations_only_own(self, ai_client, ai_user2, ai_conversation):
        """User only sees their own conversations, not other users'."""
        # Create a conversation for another user
        other_conv = AIConversation.objects.create(
            user=ai_user2,
            conversation_type="general",
        )
        response = ai_client.get("/api/ai/conversations/")
        results = response.data.get("results", response.data)
        conv_ids = [c["id"] for c in results]
        assert str(other_conv.id) not in conv_ids

    def test_list_conversations_filter_by_type(self, ai_client, ai_user):
        """Conversations can be filtered by conversation_type."""
        AIConversation.objects.create(user=ai_user, conversation_type="motivation")
        AIConversation.objects.create(user=ai_user, conversation_type="general")
        response = ai_client.get("/api/ai/conversations/?conversation_type=motivation")
        assert response.status_code == status.HTTP_200_OK
        results = response.data.get("results", response.data)
        for conv in results:
            assert conv["conversation_type"] == "motivation"


class TestCreateAIConversation:
    """Tests for POST /api/ai/conversations/"""

    def test_create_general_conversation(self, ai_client):
        """Create a general AI conversation without a dream."""
        response = ai_client.post(
            "/api/ai/conversations/",
            {"conversation_type": "general"},
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["conversation_type"] == "general"
        assert response.data["id"] is not None

    def test_create_planning_conversation_with_dream(self, ai_client, ai_dream):
        """Create a planning conversation linked to a dream."""
        response = ai_client.post(
            "/api/ai/conversations/",
            {
                "conversation_type": "planning",
                "dream": str(ai_dream.id),
            },
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["conversation_type"] == "planning"
        assert str(response.data["dream"]) == str(ai_dream.id)

    def test_create_planning_without_dream_rejected(self, ai_client):
        """Planning conversation without a dream is rejected."""
        response = ai_client.post(
            "/api/ai/conversations/",
            {"conversation_type": "planning"},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_create_conversation_unauthenticated(self):
        """Unauthenticated request returns 401."""
        from rest_framework.test import APIClient

        client = APIClient()
        response = client.post(
            "/api/ai/conversations/",
            {"conversation_type": "general"},
            format="json",
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_create_conversation_with_title(self, ai_client):
        """Conversation can be created with an optional title."""
        response = ai_client.post(
            "/api/ai/conversations/",
            {"conversation_type": "general", "title": "My Chat"},
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["title"] == "My Chat"


class TestGetAIConversationDetail:
    """Tests for GET /api/ai/conversations/{id}/"""

    def test_get_conversation_detail(self, ai_client, ai_conversation, ai_message):
        """Retrieve a conversation with messages."""
        response = ai_client.get(f"/api/ai/conversations/{ai_conversation.id}/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["id"] == str(ai_conversation.id)
        assert "messages" in response.data
        assert len(response.data["messages"]) >= 1

    def test_get_conversation_not_found(self, ai_client):
        """Non-existent conversation returns 404."""
        import uuid

        fake_id = uuid.uuid4()
        response = ai_client.get(f"/api/ai/conversations/{fake_id}/")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_get_other_user_conversation(self, ai_client, ai_user2):
        """Cannot retrieve another user's conversation."""
        other_conv = AIConversation.objects.create(
            user=ai_user2,
            conversation_type="general",
        )
        response = ai_client.get(f"/api/ai/conversations/{other_conv.id}/")
        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestGetAIMessages:
    """Tests for getting messages within a conversation."""

    def test_get_messages_via_detail(self, ai_client, ai_conversation):
        """Conversation detail includes messages."""
        # Add a few messages
        ai_conversation.add_message("user", "Hello!")
        ai_conversation.add_message("assistant", "Hi there!")
        response = ai_client.get(f"/api/ai/conversations/{ai_conversation.id}/")
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["messages"]) == 2
        # Messages should be in chronological order
        assert response.data["messages"][0]["role"] == "user"
        assert response.data["messages"][1]["role"] == "assistant"

    def test_messages_limited_to_50(self, ai_client, ai_conversation):
        """Detail serializer limits messages to 50."""
        for i in range(55):
            AIMessage.objects.create(
                conversation=ai_conversation,
                role="user" if i % 2 == 0 else "assistant",
                content=f"Message {i}",
            )
        response = ai_client.get(f"/api/ai/conversations/{ai_conversation.id}/")
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["messages"]) == 50


class TestAIConversationUpdate:
    """Tests for PATCH/PUT /api/ai/conversations/{id}/"""

    def test_update_conversation_title(self, ai_client, ai_conversation):
        """Owner can update conversation title."""
        response = ai_client.patch(
            f"/api/ai/conversations/{ai_conversation.id}/",
            {"title": "Updated Title"},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["title"] == "Updated Title"

    def test_pin_conversation(self, ai_client, ai_conversation):
        """Owner can pin a conversation."""
        response = ai_client.patch(
            f"/api/ai/conversations/{ai_conversation.id}/",
            {"is_pinned": True},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["is_pinned"] is True


class TestAIConversationDelete:
    """Tests for DELETE /api/ai/conversations/{id}/"""

    def test_delete_conversation(self, ai_client, ai_user):
        """Owner can delete their conversation."""
        conv = AIConversation.objects.create(
            user=ai_user, conversation_type="general"
        )
        response = ai_client.delete(f"/api/ai/conversations/{conv.id}/")
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not AIConversation.objects.filter(id=conv.id).exists()

    def test_delete_other_user_conversation(self, ai_client, ai_user2):
        """Cannot delete another user's conversation."""
        other_conv = AIConversation.objects.create(
            user=ai_user2, conversation_type="general"
        )
        response = ai_client.delete(f"/api/ai/conversations/{other_conv.id}/")
        # Should be 404 since queryset is filtered by user
        assert response.status_code == status.HTTP_404_NOT_FOUND
