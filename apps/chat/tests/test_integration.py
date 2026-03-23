"""
Integration tests for the Chat app.

Tests API endpoints via the DRF test client.
"""

import uuid
from unittest.mock import patch

from rest_framework import status

from apps.chat.models import Call, ChatConversation, ChatMessage, MessageReadStatus


class TestListChatConversations:
    """Tests for GET /api/chat/"""

    def test_list_conversations(self, chat_client, chat_conversation):
        """Authenticated user can list their chat conversations."""
        response = chat_client.get("/api/chat/")
        assert response.status_code == status.HTTP_200_OK
        data = response.data
        results = data.get("results", data)
        assert len(results) >= 1

    def test_list_conversations_unauthenticated(self):
        """Unauthenticated request returns 401."""
        from rest_framework.test import APIClient

        client = APIClient()
        response = client.get("/api/chat/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_list_includes_conversations_as_target(
        self, chat_client2, chat_conversation
    ):
        """User sees conversations where they are the target_user."""
        response = chat_client2.get("/api/chat/")
        assert response.status_code == status.HTTP_200_OK
        results = response.data.get("results", response.data)
        conv_ids = [c["id"] for c in results]
        assert str(chat_conversation.id) in conv_ids


class TestSendFriendMessage:
    """Tests for POST /api/chat/{id}/send-message/"""

    @patch("channels.layers.get_channel_layer")
    def test_send_message(self, mock_channel_layer, chat_client, chat_conversation):
        """Send a message in a chat conversation."""
        mock_channel_layer.return_value = None  # Suppress WebSocket
        response = chat_client.post(
            f"/api/chat/{chat_conversation.id}/send-message/",
            {"content": "Hello friend!"},
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["content"] == "Hello friend!"
        assert response.data["role"] == "user"

    @patch("channels.layers.get_channel_layer")
    def test_send_message_increments_total(
        self, mock_channel_layer, chat_client, chat_conversation
    ):
        """Sending a message increments total_messages."""
        mock_channel_layer.return_value = None
        chat_client.post(
            f"/api/chat/{chat_conversation.id}/send-message/",
            {"content": "Message 1"},
            format="json",
        )
        chat_conversation.refresh_from_db()
        assert chat_conversation.total_messages == 1

    def test_send_empty_message_rejected(self, chat_client, chat_conversation):
        """Empty message content is rejected."""
        response = chat_client.post(
            f"/api/chat/{chat_conversation.id}/send-message/",
            {"content": ""},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_send_message_unauthenticated(self, chat_conversation):
        """Unauthenticated request returns 401."""
        from rest_framework.test import APIClient

        client = APIClient()
        response = client.post(
            f"/api/chat/{chat_conversation.id}/send-message/",
            {"content": "Hello"},
            format="json",
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestGetMessages:
    """Tests for GET /api/chat/{id}/messages/"""

    def test_get_messages(self, chat_client, chat_conversation, chat_message):
        """Get messages for a conversation."""
        response = chat_client.get(f"/api/chat/{chat_conversation.id}/messages/")
        assert response.status_code == status.HTTP_200_OK
        data = response.data
        results = data.get("results", data)
        assert len(results) >= 1

    def test_get_messages_empty(self, chat_client, chat_user, chat_user2):
        """Get messages for a conversation with no messages."""
        conv = ChatConversation.objects.create(user=chat_user, target_user=chat_user2)
        response = chat_client.get(f"/api/chat/{conv.id}/messages/")
        assert response.status_code == status.HTTP_200_OK


class TestPinLikeMessage:
    """Tests for pin and like message endpoints."""

    def test_pin_message(self, chat_client, chat_conversation, chat_message):
        """Pin a message toggles is_pinned."""
        response = chat_client.post(
            f"/api/chat/{chat_conversation.id}/pin-message/{chat_message.id}/"
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["is_pinned"] is True

        # Toggle back
        response = chat_client.post(
            f"/api/chat/{chat_conversation.id}/pin-message/{chat_message.id}/"
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["is_pinned"] is False

    def test_like_message(self, chat_client, chat_conversation, chat_message):
        """Like a message toggles is_liked."""
        response = chat_client.post(
            f"/api/chat/{chat_conversation.id}/like-message/{chat_message.id}/"
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["is_liked"] is True

        # Toggle back
        response = chat_client.post(
            f"/api/chat/{chat_conversation.id}/like-message/{chat_message.id}/"
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["is_liked"] is False

    def test_pin_nonexistent_message(self, chat_client, chat_conversation):
        """Pinning a non-existent message returns 404."""
        fake_id = uuid.uuid4()
        response = chat_client.post(
            f"/api/chat/{chat_conversation.id}/pin-message/{fake_id}/"
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_like_nonexistent_message(self, chat_client, chat_conversation):
        """Liking a non-existent message returns 404."""
        fake_id = uuid.uuid4()
        response = chat_client.post(
            f"/api/chat/{chat_conversation.id}/like-message/{fake_id}/"
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestMarkRead:
    """Tests for POST /api/chat/{id}/mark-read/"""

    def test_mark_read(self, chat_client, chat_conversation, chat_message):
        """Mark a conversation as read."""
        response = chat_client.post(f"/api/chat/{chat_conversation.id}/mark-read/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["status"] == "ok"
        assert response.data["last_read_message_id"] == str(chat_message.id)

    def test_mark_read_creates_status(
        self, chat_client, chat_user, chat_conversation, chat_message
    ):
        """mark-read creates a MessageReadStatus record."""
        chat_client.post(f"/api/chat/{chat_conversation.id}/mark-read/")
        assert MessageReadStatus.objects.filter(
            user=chat_user, conversation=chat_conversation
        ).exists()

    def test_mark_read_updates_existing(
        self, chat_client, chat_user, chat_conversation, chat_message
    ):
        """mark-read updates existing read status."""
        chat_client.post(f"/api/chat/{chat_conversation.id}/mark-read/")
        # Add another message
        msg2 = ChatMessage.objects.create(
            conversation=chat_conversation, role="user", content="New message"
        )
        chat_client.post(f"/api/chat/{chat_conversation.id}/mark-read/")
        read_status = MessageReadStatus.objects.get(
            user=chat_user, conversation=chat_conversation
        )
        assert read_status.last_read_message == msg2


class TestInitiateCall:
    """Tests for POST /api/chat/calls/initiate/"""

    @patch("apps.chat.views.CallViewSet._notify_callee")
    def test_initiate_voice_call(self, mock_notify, chat_client, chat_user2):
        """Initiate a voice call."""
        response = chat_client.post(
            "/api/chat/calls/initiate/",
            {"callee_id": str(chat_user2.id), "call_type": "voice"},
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["call_type"] == "voice"
        assert response.data["status"] == "ringing"
        assert response.data["callee_id"] == str(chat_user2.id)

    @patch("apps.chat.views.CallViewSet._notify_callee")
    def test_initiate_video_call(self, mock_notify, chat_client, chat_user2):
        """Initiate a video call."""
        response = chat_client.post(
            "/api/chat/calls/initiate/",
            {"callee_id": str(chat_user2.id), "call_type": "video"},
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["call_type"] == "video"

    def test_initiate_call_missing_callee(self, chat_client):
        """Initiating without callee_id returns 400."""
        response = chat_client.post(
            "/api/chat/calls/initiate/",
            {"call_type": "voice"},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_initiate_call_self(self, chat_client, chat_user):
        """Cannot call yourself."""
        response = chat_client.post(
            "/api/chat/calls/initiate/",
            {"callee_id": str(chat_user.id), "call_type": "voice"},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_initiate_call_invalid_callee(self, chat_client):
        """Calling a non-existent user returns 404."""
        response = chat_client.post(
            "/api/chat/calls/initiate/",
            {"callee_id": str(uuid.uuid4()), "call_type": "voice"},
            format="json",
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_initiate_call_invalid_type(self, chat_client, chat_user2):
        """Invalid call_type returns 400."""
        response = chat_client.post(
            "/api/chat/calls/initiate/",
            {"callee_id": str(chat_user2.id), "call_type": "invalid"},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST


class TestAcceptRejectCall:
    """Tests for accept and reject call endpoints."""

    def test_accept_call(self, chat_client2, chat_call):
        """Callee can accept a ringing call."""
        response = chat_client2.post(f"/api/chat/calls/{chat_call.id}/accept/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["status"] == "accepted"
        assert "started_at" in response.data

    def test_accept_call_not_callee(self, chat_client, chat_call):
        """Non-callee cannot accept the call."""
        response = chat_client.post(f"/api/chat/calls/{chat_call.id}/accept/")
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_accept_non_ringing_call(self, chat_client2, chat_call):
        """Cannot accept a call that is not ringing."""
        chat_call.status = "completed"
        chat_call.save()
        response = chat_client2.post(f"/api/chat/calls/{chat_call.id}/accept/")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    @patch("apps.chat.views.CallViewSet._notify_callee")
    def test_reject_call(self, mock_notify, chat_client2, chat_call):
        """Callee can reject a call."""
        with patch("apps.notifications.services.NotificationService.create"):
            response = chat_client2.post(f"/api/chat/calls/{chat_call.id}/reject/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["status"] == "rejected"

    def test_reject_call_not_callee(self, chat_client, chat_call):
        """Non-callee cannot reject the call."""
        response = chat_client.post(f"/api/chat/calls/{chat_call.id}/reject/")
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_accept_nonexistent_call(self, chat_client):
        """Accepting a non-existent call returns 404."""
        response = chat_client.post(f"/api/chat/calls/{uuid.uuid4()}/accept/")
        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestCallHistory:
    """Tests for GET /api/chat/calls/history/"""

    def test_call_history(self, chat_client, chat_call):
        """User can see their call history."""
        response = chat_client.get("/api/chat/calls/history/")
        assert response.status_code == status.HTTP_200_OK
        data = response.data
        results = data.get("results", data)
        assert len(results) >= 1

    def test_call_history_includes_both_roles(self, chat_client2, chat_call):
        """Callee also sees calls in their history."""
        response = chat_client2.get("/api/chat/calls/history/")
        assert response.status_code == status.HTTP_200_OK
        data = response.data
        results = data.get("results", data)
        assert len(results) >= 1

    def test_call_history_excludes_other_users(self, chat_user3, chat_call):
        """Third user does not see other users' calls."""
        from rest_framework.test import APIClient

        client = APIClient()
        client.force_authenticate(user=chat_user3)
        response = client.get("/api/chat/calls/history/")
        assert response.status_code == status.HTTP_200_OK
        data = response.data
        results = data.get("results", data)
        assert len(results) == 0


class TestIncomingCalls:
    """Tests for GET /api/chat/calls/incoming/"""

    def test_incoming_calls(self, chat_client2, chat_call):
        """Callee sees ringing calls in incoming."""
        response = chat_client2.get("/api/chat/calls/incoming/")
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) >= 1
        assert response.data[0]["call_type"] == "voice"

    def test_incoming_calls_excludes_completed(
        self, chat_client2, chat_user, chat_user2
    ):
        """Completed calls are not shown in incoming."""
        Call.objects.create(
            caller=chat_user,
            callee=chat_user2,
            call_type="voice",
            status="completed",
        )
        response = chat_client2.get("/api/chat/calls/incoming/")
        assert response.status_code == status.HTTP_200_OK
        # Filter to only check for completed calls
        for call_data in response.data:
            assert call_data.get("status", "ringing") != "completed"

    def test_incoming_calls_caller_sees_none(self, chat_client, chat_call):
        """Caller does not see their own calls in incoming."""
        response = chat_client.get("/api/chat/calls/incoming/")
        assert response.status_code == status.HTTP_200_OK
        # Caller should not see calls where they are the caller
        call_ids = [c.get("call_id") for c in response.data]
        assert str(chat_call.id) not in call_ids


# ──────────────────────────────────────────────────────────────────────
#  Start (get-or-create) conversation
# ──────────────────────────────────────────────────────────────────────


class TestStartConversation:
    """Tests for POST /api/chat/start/"""

    def test_start_creates_new_conversation(self, chat_client, chat_user, chat_user3):
        """Starting a conversation with a new user creates one."""
        response = chat_client.post(
            "/api/chat/start/",
            {"target_user_id": str(chat_user3.id)},
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert ChatConversation.objects.filter(
            user=chat_user, target_user=chat_user3
        ).exists()

    def test_start_returns_existing_conversation(
        self, chat_client, chat_conversation, chat_user2
    ):
        """Starting a conversation with a user who already has one returns existing."""
        response = chat_client.post(
            "/api/chat/start/",
            {"target_user_id": str(chat_user2.id)},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["id"] == str(chat_conversation.id)

    def test_start_missing_target(self, chat_client):
        """Starting without target_user_id returns 400."""
        response = chat_client.post(
            "/api/chat/start/",
            {},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_start_with_self(self, chat_client, chat_user):
        """Cannot start a conversation with yourself."""
        response = chat_client.post(
            "/api/chat/start/",
            {"target_user_id": str(chat_user.id)},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_start_nonexistent_user(self, chat_client):
        """Starting with a non-existent user returns 404."""
        response = chat_client.post(
            "/api/chat/start/",
            {"target_user_id": str(uuid.uuid4())},
            format="json",
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_start_unauthenticated(self, chat_user2):
        """Unauthenticated request returns 401."""
        from rest_framework.test import APIClient

        client = APIClient()
        response = client.post(
            "/api/chat/start/",
            {"target_user_id": str(chat_user2.id)},
            format="json",
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


# ──────────────────────────────────────────────────────────────────────
#  Send Voice Message
# ──────────────────────────────────────────────────────────────────────


class TestSendVoiceMessage:
    """Tests for POST /api/chat/{id}/send-message/ with voice-like content."""

    @patch("channels.layers.get_channel_layer")
    def test_send_long_message(
        self, mock_channel_layer, chat_client, chat_conversation
    ):
        """Send a long text message."""
        mock_channel_layer.return_value = None
        long_content = "A" * 500
        response = chat_client.post(
            f"/api/chat/{chat_conversation.id}/send-message/",
            {"content": long_content},
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["content"] == long_content


# ──────────────────────────────────────────────────────────────────────
#  End Call & Cancel Call
# ──────────────────────────────────────────────────────────────────────


class TestEndCall:
    """Tests for POST /api/chat/calls/{id}/end/"""

    def test_end_accepted_call(self, chat_client, chat_call):
        """Caller can end an accepted call."""
        from django.utils import timezone as tz

        chat_call.status = "accepted"
        chat_call.started_at = tz.now()
        chat_call.save()

        response = chat_client.post(f"/api/chat/calls/{chat_call.id}/end/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["status"] == "completed"

    def test_end_call_as_callee(self, chat_client2, chat_call):
        """Callee can also end a call."""
        from django.utils import timezone as tz

        chat_call.status = "accepted"
        chat_call.started_at = tz.now()
        chat_call.save()

        response = chat_client2.post(f"/api/chat/calls/{chat_call.id}/end/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["status"] == "completed"

    def test_end_call_not_participant(self, chat_user3, chat_call):
        """Non-participant cannot end a call."""
        from rest_framework.test import APIClient

        client = APIClient()
        client.force_authenticate(user=chat_user3)

        chat_call.status = "accepted"
        chat_call.save()

        response = client.post(f"/api/chat/calls/{chat_call.id}/end/")
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_end_nonexistent_call(self, chat_client):
        """Ending a non-existent call returns 404."""
        response = chat_client.post(f"/api/chat/calls/{uuid.uuid4()}/end/")
        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestCancelCall:
    """Tests for POST /api/chat/calls/{id}/cancel/"""

    def test_cancel_ringing_call(self, chat_client, chat_call):
        """Caller can cancel a ringing call."""
        response = chat_client.post(f"/api/chat/calls/{chat_call.id}/cancel/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["status"] == "cancelled"

    def test_cancel_call_not_caller(self, chat_client2, chat_call):
        """Callee cannot cancel a call."""
        response = chat_client2.post(f"/api/chat/calls/{chat_call.id}/cancel/")
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_cancel_non_ringing_call(self, chat_client, chat_call):
        """Cannot cancel a call that is not ringing."""
        chat_call.status = "accepted"
        chat_call.save()
        response = chat_client.post(f"/api/chat/calls/{chat_call.id}/cancel/")
        assert response.status_code == status.HTTP_400_BAD_REQUEST


class TestCallStatus:
    """Tests for GET /api/chat/calls/{id}/status/"""

    def test_get_call_status(self, chat_client, chat_call):
        """Participant can get call status."""
        response = chat_client.get(f"/api/chat/calls/{chat_call.id}/status/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["status"] == "ringing"
        assert response.data["call_type"] == "voice"

    def test_get_call_status_callee(self, chat_client2, chat_call):
        """Callee can also get call status."""
        response = chat_client2.get(f"/api/chat/calls/{chat_call.id}/status/")
        assert response.status_code == status.HTTP_200_OK

    def test_get_call_status_non_participant(self, chat_user3, chat_call):
        """Non-participant cannot see call status."""
        from rest_framework.test import APIClient

        client = APIClient()
        client.force_authenticate(user=chat_user3)
        response = client.get(f"/api/chat/calls/{chat_call.id}/status/")
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_get_call_status_not_found(self, chat_client):
        """Non-existent call returns 404."""
        response = chat_client.get(f"/api/chat/calls/{uuid.uuid4()}/status/")
        assert response.status_code == status.HTTP_404_NOT_FOUND


# ──────────────────────────────────────────────────────────────────────
#  Retrieve conversation detail
# ──────────────────────────────────────────────────────────────────────


class TestRetrieveConversation:
    """Tests for GET /api/chat/{id}/"""

    def test_retrieve_conversation(self, chat_client, chat_conversation):
        """Get a specific conversation with messages."""
        response = chat_client.get(f"/api/chat/{chat_conversation.id}/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["id"] == str(chat_conversation.id)

    def test_retrieve_nonexistent(self, chat_client):
        """Non-existent conversation returns 404."""
        response = chat_client.get(f"/api/chat/{uuid.uuid4()}/")
        assert response.status_code == status.HTTP_404_NOT_FOUND
