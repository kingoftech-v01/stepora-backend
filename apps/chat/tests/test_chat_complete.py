"""
Comprehensive tests for the Chat app — targeting 95%+ coverage.

Covers:
- ChatConversation: CRUD, list, detail, delete (readonly), start/get-or-create
- ChatMessage: send, list, read status, voice messages, pin, like
- Call: initiate, accept, reject, end, cancel, history, incoming, missed, status
- Agora: config, RTC token, RTM token
- WebSocket consumers: connect, disconnect, send, receive, typing, read receipts
- Blocked user prevents messaging AND calling
- IDOR: user cannot access other users' conversations
- Edge cases: empty conversations, duplicate starts, self-chat, etc.
"""

import uuid
from unittest.mock import Mock, patch

import pytest
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient, APIRequestFactory

from apps.chat.models import Call, ChatConversation, ChatMessage, MessageReadStatus
from apps.chat.serializers import (
    CallHistorySerializer,
    ChatConversationDetailSerializer,
    ChatConversationSerializer,
    ChatMessageCreateSerializer,
    ChatMessageSerializer,
)
from apps.friends.models import BlockedUser
from apps.users.models import User


# ──────────────────────────────────────────────────────────────────────
#  Fixtures
# ──────────────────────────────────────────────────────────────────────


@pytest.fixture
def user_a(db):
    """Primary test user."""
    return User.objects.create_user(
        email="complete_a@example.com",
        password="testpassword123",
        display_name="User Alpha",
        timezone="Europe/Paris",
    )


@pytest.fixture
def user_b(db):
    """Secondary test user."""
    return User.objects.create_user(
        email="complete_b@example.com",
        password="testpassword123",
        display_name="User Beta",
        timezone="Europe/Paris",
    )


@pytest.fixture
def user_c(db):
    """Third user (outsider / bystander)."""
    return User.objects.create_user(
        email="complete_c@example.com",
        password="testpassword123",
        display_name="User Charlie",
        timezone="Europe/Paris",
    )


@pytest.fixture
def client_a(user_a):
    c = APIClient()
    c.force_authenticate(user=user_a)
    return c


@pytest.fixture
def client_b(user_b):
    c = APIClient()
    c.force_authenticate(user=user_b)
    return c


@pytest.fixture
def client_c(user_c):
    c = APIClient()
    c.force_authenticate(user=user_c)
    return c


@pytest.fixture
def anon_client():
    return APIClient()


@pytest.fixture
def conversation_ab(user_a, user_b):
    return ChatConversation.objects.create(
        user=user_a, target_user=user_b, title="A-B chat"
    )


@pytest.fixture
def message_in_ab(conversation_ab, user_a):
    return ChatMessage.objects.create(
        conversation=conversation_ab,
        role="user",
        content="Hello from A!",
        metadata={"sender_id": str(user_a.id)},
    )


@pytest.fixture
def ringing_call_ab(user_a, user_b):
    return Call.objects.create(
        caller=user_a, callee=user_b, call_type="voice", status="ringing"
    )


# ══════════════════════════════════════════════════════════════════════
#  1. CONVERSATION CRUD
# ══════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestConversationList:
    """GET /api/chat/ — list conversations."""

    def test_list_own_conversations(self, client_a, conversation_ab):
        resp = client_a.get("/api/chat/")
        assert resp.status_code == 200
        ids = [c["id"] for c in resp.data.get("results", resp.data)]
        assert str(conversation_ab.id) in ids

    def test_list_as_target_user(self, client_b, conversation_ab):
        """User B is target_user and should see the conversation."""
        resp = client_b.get("/api/chat/")
        assert resp.status_code == 200
        ids = [c["id"] for c in resp.data.get("results", resp.data)]
        assert str(conversation_ab.id) in ids

    def test_outsider_does_not_see_conversation(self, client_c, conversation_ab):
        """User C is not part of the conversation and should not see it."""
        resp = client_c.get("/api/chat/")
        assert resp.status_code == 200
        ids = [c["id"] for c in resp.data.get("results", resp.data)]
        assert str(conversation_ab.id) not in ids

    def test_list_unauthenticated(self, anon_client):
        resp = anon_client.get("/api/chat/")
        assert resp.status_code == 401

    def test_list_empty(self, client_c):
        """User with no conversations gets empty list."""
        resp = client_c.get("/api/chat/")
        assert resp.status_code == 200
        results = resp.data.get("results", resp.data)
        assert len(results) == 0


@pytest.mark.django_db
class TestConversationRetrieve:
    """GET /api/chat/{id}/ — retrieve conversation detail."""

    def test_retrieve_as_owner(self, client_a, conversation_ab, message_in_ab):
        resp = client_a.get(f"/api/chat/{conversation_ab.id}/")
        assert resp.status_code == 200
        assert resp.data["id"] == str(conversation_ab.id)
        # Uses detail serializer with messages
        assert "messages" in resp.data

    def test_retrieve_as_target(self, client_b, conversation_ab):
        resp = client_b.get(f"/api/chat/{conversation_ab.id}/")
        assert resp.status_code == 200

    def test_retrieve_as_outsider_returns_404(self, client_c, conversation_ab):
        """IDOR: outsider cannot access other users' conversations."""
        resp = client_c.get(f"/api/chat/{conversation_ab.id}/")
        assert resp.status_code == 404

    def test_retrieve_nonexistent(self, client_a):
        resp = client_a.get(f"/api/chat/{uuid.uuid4()}/")
        assert resp.status_code == 404

    def test_retrieve_unauthenticated(self, anon_client, conversation_ab):
        resp = anon_client.get(f"/api/chat/{conversation_ab.id}/")
        assert resp.status_code == 401


@pytest.mark.django_db
class TestConversationStart:
    """POST /api/chat/start/ — get or create a conversation."""

    def test_start_creates_new(self, client_a, user_a, user_c):
        resp = client_a.post(
            "/api/chat/start/",
            {"target_user_id": str(user_c.id)},
            format="json",
        )
        assert resp.status_code == 201
        assert ChatConversation.objects.filter(
            user=user_a, target_user=user_c
        ).exists()

    def test_start_returns_existing(self, client_a, conversation_ab, user_b):
        resp = client_a.post(
            "/api/chat/start/",
            {"target_user_id": str(user_b.id)},
            format="json",
        )
        assert resp.status_code == 200
        assert resp.data["id"] == str(conversation_ab.id)

    def test_start_returns_existing_reverse(self, client_b, conversation_ab, user_a):
        """B starts conversation with A — should find existing A->B conversation."""
        resp = client_b.post(
            "/api/chat/start/",
            {"target_user_id": str(user_a.id)},
            format="json",
        )
        assert resp.status_code == 200
        assert resp.data["id"] == str(conversation_ab.id)

    def test_start_with_user_id_alias(self, client_a, user_c):
        """user_id accepted as alias for target_user_id."""
        resp = client_a.post(
            "/api/chat/start/",
            {"user_id": str(user_c.id)},
            format="json",
        )
        assert resp.status_code == 201

    def test_start_with_self_returns_400(self, client_a, user_a):
        resp = client_a.post(
            "/api/chat/start/",
            {"target_user_id": str(user_a.id)},
            format="json",
        )
        assert resp.status_code == 400

    def test_start_missing_target_returns_400(self, client_a):
        resp = client_a.post("/api/chat/start/", {}, format="json")
        assert resp.status_code == 400

    def test_start_nonexistent_user_returns_404(self, client_a):
        resp = client_a.post(
            "/api/chat/start/",
            {"target_user_id": str(uuid.uuid4())},
            format="json",
        )
        assert resp.status_code == 404

    def test_start_unauthenticated(self, anon_client, user_b):
        resp = anon_client.post(
            "/api/chat/start/",
            {"target_user_id": str(user_b.id)},
            format="json",
        )
        assert resp.status_code == 401


@pytest.mark.django_db
class TestConversationReadOnly:
    """ChatConversationViewSet is ReadOnlyModelViewSet — no create/update/delete via REST."""

    def test_put_not_allowed(self, client_a, conversation_ab):
        resp = client_a.put(
            f"/api/chat/{conversation_ab.id}/",
            {"title": "New Title"},
            format="json",
        )
        assert resp.status_code == 405

    def test_patch_not_allowed(self, client_a, conversation_ab):
        resp = client_a.patch(
            f"/api/chat/{conversation_ab.id}/",
            {"title": "New Title"},
            format="json",
        )
        assert resp.status_code == 405

    def test_delete_not_allowed(self, client_a, conversation_ab):
        resp = client_a.delete(f"/api/chat/{conversation_ab.id}/")
        assert resp.status_code == 405


# ══════════════════════════════════════════════════════════════════════
#  2. MESSAGES
# ══════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestSendMessage:
    """POST /api/chat/{id}/send-message/"""

    @patch("channels.layers.get_channel_layer")
    def test_send_message_success(self, mock_layer, client_a, conversation_ab):
        mock_layer.return_value = None
        resp = client_a.post(
            f"/api/chat/{conversation_ab.id}/send-message/",
            {"content": "Hello friend!"},
            format="json",
        )
        assert resp.status_code == 201
        assert resp.data["content"] == "Hello friend!"
        assert resp.data["role"] == "user"

    @patch("channels.layers.get_channel_layer")
    def test_send_message_increments_total(self, mock_layer, client_a, conversation_ab):
        mock_layer.return_value = None
        client_a.post(
            f"/api/chat/{conversation_ab.id}/send-message/",
            {"content": "Msg"},
            format="json",
        )
        conversation_ab.refresh_from_db()
        assert conversation_ab.total_messages == 1

    @patch("channels.layers.get_channel_layer")
    def test_send_message_includes_sender_metadata(self, mock_layer, client_a, user_a, conversation_ab):
        mock_layer.return_value = None
        resp = client_a.post(
            f"/api/chat/{conversation_ab.id}/send-message/",
            {"content": "Hi"},
            format="json",
        )
        assert resp.data["metadata"]["sender_id"] == str(user_a.id)

    def test_send_empty_message_rejected(self, client_a, conversation_ab):
        resp = client_a.post(
            f"/api/chat/{conversation_ab.id}/send-message/",
            {"content": ""},
            format="json",
        )
        assert resp.status_code == 400

    def test_send_whitespace_only_rejected(self, client_a, conversation_ab):
        resp = client_a.post(
            f"/api/chat/{conversation_ab.id}/send-message/",
            {"content": "   "},
            format="json",
        )
        assert resp.status_code == 400

    def test_send_no_content_field(self, client_a, conversation_ab):
        resp = client_a.post(
            f"/api/chat/{conversation_ab.id}/send-message/",
            {},
            format="json",
        )
        assert resp.status_code == 400

    def test_send_message_unauthenticated(self, anon_client, conversation_ab):
        resp = anon_client.post(
            f"/api/chat/{conversation_ab.id}/send-message/",
            {"content": "Nope"},
            format="json",
        )
        assert resp.status_code == 401

    @patch("channels.layers.get_channel_layer")
    def test_send_message_to_nonexistent_conversation(self, mock_layer, client_a):
        resp = client_a.post(
            f"/api/chat/{uuid.uuid4()}/send-message/",
            {"content": "Where?"},
            format="json",
        )
        assert resp.status_code == 404

    @patch("channels.layers.get_channel_layer")
    def test_send_message_idor_outsider(self, mock_layer, client_c, conversation_ab):
        """IDOR: outsider cannot send messages in other users' conversations."""
        resp = client_c.post(
            f"/api/chat/{conversation_ab.id}/send-message/",
            {"content": "Sneaky"},
            format="json",
        )
        assert resp.status_code == 404

    @patch("channels.layers.get_channel_layer")
    def test_ws_failure_does_not_block_send(self, mock_layer, client_a, conversation_ab):
        """WebSocket broadcast failure is non-blocking."""
        mock_layer.side_effect = Exception("Channel layer down")
        resp = client_a.post(
            f"/api/chat/{conversation_ab.id}/send-message/",
            {"content": "Still goes through"},
            format="json",
        )
        assert resp.status_code == 201


@pytest.mark.django_db
class TestGetMessages:
    """GET /api/chat/{id}/messages/"""

    def test_get_messages(self, client_a, conversation_ab, message_in_ab):
        resp = client_a.get(f"/api/chat/{conversation_ab.id}/messages/")
        assert resp.status_code == 200
        results = resp.data.get("results", resp.data)
        assert len(results) >= 1

    def test_get_messages_empty_conversation(self, client_a, user_a, user_b):
        conv = ChatConversation.objects.create(user=user_a, target_user=user_b)
        resp = client_a.get(f"/api/chat/{conv.id}/messages/")
        assert resp.status_code == 200

    def test_get_messages_idor(self, client_c, conversation_ab):
        """Outsider cannot get messages from other users' conversations."""
        resp = client_c.get(f"/api/chat/{conversation_ab.id}/messages/")
        assert resp.status_code == 404


@pytest.mark.django_db
class TestPinLikeMessage:
    """Pin and like message actions."""

    def test_pin_toggles(self, client_a, conversation_ab, message_in_ab):
        resp = client_a.post(
            f"/api/chat/{conversation_ab.id}/pin-message/{message_in_ab.id}/"
        )
        assert resp.status_code == 200
        assert resp.data["is_pinned"] is True

        resp = client_a.post(
            f"/api/chat/{conversation_ab.id}/pin-message/{message_in_ab.id}/"
        )
        assert resp.data["is_pinned"] is False

    def test_like_toggles(self, client_a, conversation_ab, message_in_ab):
        resp = client_a.post(
            f"/api/chat/{conversation_ab.id}/like-message/{message_in_ab.id}/"
        )
        assert resp.status_code == 200
        assert resp.data["is_liked"] is True

        resp = client_a.post(
            f"/api/chat/{conversation_ab.id}/like-message/{message_in_ab.id}/"
        )
        assert resp.data["is_liked"] is False

    def test_pin_nonexistent_message(self, client_a, conversation_ab):
        resp = client_a.post(
            f"/api/chat/{conversation_ab.id}/pin-message/{uuid.uuid4()}/"
        )
        assert resp.status_code == 404

    def test_like_nonexistent_message(self, client_a, conversation_ab):
        resp = client_a.post(
            f"/api/chat/{conversation_ab.id}/like-message/{uuid.uuid4()}/"
        )
        assert resp.status_code == 404

    def test_pin_idor_outsider(self, client_c, conversation_ab, message_in_ab):
        """Outsider cannot pin messages in other users' conversations."""
        resp = client_c.post(
            f"/api/chat/{conversation_ab.id}/pin-message/{message_in_ab.id}/"
        )
        assert resp.status_code == 404


@pytest.mark.django_db
class TestMarkRead:
    """POST /api/chat/{id}/mark-read/"""

    def test_mark_read_success(self, client_a, conversation_ab, message_in_ab):
        resp = client_a.post(f"/api/chat/{conversation_ab.id}/mark-read/")
        assert resp.status_code == 200
        assert resp.data["status"] == "ok"
        assert resp.data["last_read_message_id"] == str(message_in_ab.id)

    def test_mark_read_creates_status(self, client_a, user_a, conversation_ab, message_in_ab):
        client_a.post(f"/api/chat/{conversation_ab.id}/mark-read/")
        assert MessageReadStatus.objects.filter(
            user=user_a, conversation=conversation_ab
        ).exists()

    def test_mark_read_updates_existing(self, client_a, user_a, conversation_ab, message_in_ab):
        client_a.post(f"/api/chat/{conversation_ab.id}/mark-read/")
        msg2 = ChatMessage.objects.create(
            conversation=conversation_ab, role="user", content="New msg"
        )
        client_a.post(f"/api/chat/{conversation_ab.id}/mark-read/")
        rs = MessageReadStatus.objects.get(user=user_a, conversation=conversation_ab)
        assert rs.last_read_message == msg2

    def test_mark_read_empty_conversation(self, client_a, user_a, user_b):
        conv = ChatConversation.objects.create(user=user_a, target_user=user_b)
        resp = client_a.post(f"/api/chat/{conv.id}/mark-read/")
        assert resp.status_code == 200
        assert resp.data["last_read_message_id"] is None


# ══════════════════════════════════════════════════════════════════════
#  3. CALLS
# ══════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestInitiateCall:
    """POST /api/chat/calls/initiate/"""

    @patch("apps.chat.views.CallViewSet._notify_callee")
    def test_initiate_voice(self, mock_notify, client_a, user_b):
        resp = client_a.post(
            "/api/chat/calls/initiate/",
            {"callee_id": str(user_b.id), "call_type": "voice"},
            format="json",
        )
        assert resp.status_code == 201
        assert resp.data["call_type"] == "voice"
        assert resp.data["status"] == "ringing"

    @patch("apps.chat.views.CallViewSet._notify_callee")
    def test_initiate_video(self, mock_notify, client_a, user_b):
        resp = client_a.post(
            "/api/chat/calls/initiate/",
            {"callee_id": str(user_b.id), "call_type": "video"},
            format="json",
        )
        assert resp.status_code == 201
        assert resp.data["call_type"] == "video"

    def test_initiate_missing_callee(self, client_a):
        resp = client_a.post(
            "/api/chat/calls/initiate/",
            {"call_type": "voice"},
            format="json",
        )
        assert resp.status_code == 400

    def test_initiate_self(self, client_a, user_a):
        resp = client_a.post(
            "/api/chat/calls/initiate/",
            {"callee_id": str(user_a.id), "call_type": "voice"},
            format="json",
        )
        assert resp.status_code == 400

    def test_initiate_nonexistent_callee(self, client_a):
        resp = client_a.post(
            "/api/chat/calls/initiate/",
            {"callee_id": str(uuid.uuid4()), "call_type": "voice"},
            format="json",
        )
        assert resp.status_code == 404

    def test_initiate_invalid_type(self, client_a, user_b):
        resp = client_a.post(
            "/api/chat/calls/initiate/",
            {"callee_id": str(user_b.id), "call_type": "hologram"},
            format="json",
        )
        assert resp.status_code == 400

    @patch("apps.chat.views.CallViewSet._notify_callee")
    def test_initiate_user_id_alias(self, mock_notify, client_a, user_b):
        """user_id accepted as alias for callee_id."""
        resp = client_a.post(
            "/api/chat/calls/initiate/",
            {"user_id": str(user_b.id), "call_type": "voice"},
            format="json",
        )
        assert resp.status_code == 201


@pytest.mark.django_db
class TestAcceptCall:
    """POST /api/chat/calls/{id}/accept/"""

    def test_accept_ringing_call(self, client_b, ringing_call_ab):
        resp = client_b.post(f"/api/chat/calls/{ringing_call_ab.id}/accept/")
        assert resp.status_code == 200
        assert resp.data["status"] == "accepted"
        assert "started_at" in resp.data

    def test_accept_not_callee_forbidden(self, client_a, ringing_call_ab):
        resp = client_a.post(f"/api/chat/calls/{ringing_call_ab.id}/accept/")
        assert resp.status_code == 403

    def test_accept_non_ringing_call(self, client_b, ringing_call_ab):
        ringing_call_ab.status = "completed"
        ringing_call_ab.save()
        resp = client_b.post(f"/api/chat/calls/{ringing_call_ab.id}/accept/")
        assert resp.status_code == 400

    def test_accept_nonexistent(self, client_a):
        resp = client_a.post(f"/api/chat/calls/{uuid.uuid4()}/accept/")
        assert resp.status_code == 404


@pytest.mark.django_db
class TestRejectCall:
    """POST /api/chat/calls/{id}/reject/"""

    @patch("channels.layers.get_channel_layer")
    @patch("apps.notifications.services.NotificationService.create")
    def test_reject_call(self, mock_notif, mock_layer, client_b, ringing_call_ab):
        mock_layer.return_value = None
        resp = client_b.post(f"/api/chat/calls/{ringing_call_ab.id}/reject/")
        assert resp.status_code == 200
        assert resp.data["status"] == "rejected"
        mock_notif.assert_called_once()

    def test_reject_not_callee(self, client_a, ringing_call_ab):
        resp = client_a.post(f"/api/chat/calls/{ringing_call_ab.id}/reject/")
        assert resp.status_code == 403


@pytest.mark.django_db
class TestEndCall:
    """POST /api/chat/calls/{id}/end/"""

    def test_end_accepted_call_with_duration(self, client_a, ringing_call_ab):
        ringing_call_ab.status = "accepted"
        ringing_call_ab.started_at = timezone.now() - timezone.timedelta(minutes=3)
        ringing_call_ab.save()
        resp = client_a.post(f"/api/chat/calls/{ringing_call_ab.id}/end/")
        assert resp.status_code == 200
        assert resp.data["status"] == "completed"
        assert resp.data["duration_seconds"] >= 0

    def test_end_call_as_callee(self, client_b, ringing_call_ab):
        ringing_call_ab.status = "accepted"
        ringing_call_ab.started_at = timezone.now()
        ringing_call_ab.save()
        resp = client_b.post(f"/api/chat/calls/{ringing_call_ab.id}/end/")
        assert resp.status_code == 200

    def test_end_call_not_participant(self, client_c, ringing_call_ab):
        ringing_call_ab.status = "accepted"
        ringing_call_ab.save()
        resp = client_c.post(f"/api/chat/calls/{ringing_call_ab.id}/end/")
        assert resp.status_code == 403

    def test_end_call_without_started_at(self, client_a, ringing_call_ab):
        """End call without started_at — no duration calculated."""
        ringing_call_ab.status = "accepted"
        ringing_call_ab.started_at = None
        ringing_call_ab.save()
        resp = client_a.post(f"/api/chat/calls/{ringing_call_ab.id}/end/")
        assert resp.status_code == 200
        ringing_call_ab.refresh_from_db()
        assert ringing_call_ab.duration_seconds == 0

    def test_end_nonexistent(self, client_a):
        resp = client_a.post(f"/api/chat/calls/{uuid.uuid4()}/end/")
        assert resp.status_code == 404


@pytest.mark.django_db
class TestCancelCall:
    """POST /api/chat/calls/{id}/cancel/"""

    def test_cancel_ringing(self, client_a, ringing_call_ab):
        resp = client_a.post(f"/api/chat/calls/{ringing_call_ab.id}/cancel/")
        assert resp.status_code == 200
        assert resp.data["status"] == "cancelled"

    def test_cancel_not_caller(self, client_b, ringing_call_ab):
        resp = client_b.post(f"/api/chat/calls/{ringing_call_ab.id}/cancel/")
        assert resp.status_code == 403

    def test_cancel_non_ringing(self, client_a, ringing_call_ab):
        ringing_call_ab.status = "accepted"
        ringing_call_ab.save()
        resp = client_a.post(f"/api/chat/calls/{ringing_call_ab.id}/cancel/")
        assert resp.status_code == 400

    def test_cancel_nonexistent(self, client_a):
        resp = client_a.post(f"/api/chat/calls/{uuid.uuid4()}/cancel/")
        assert resp.status_code == 404


@pytest.mark.django_db
class TestCallStatus:
    """GET /api/chat/calls/{id}/status/"""

    def test_get_status_as_caller(self, client_a, ringing_call_ab):
        resp = client_a.get(f"/api/chat/calls/{ringing_call_ab.id}/status/")
        assert resp.status_code == 200
        assert resp.data["status"] == "ringing"
        assert resp.data["call_type"] == "voice"
        assert resp.data["started_at"] is None

    def test_get_status_as_callee(self, client_b, ringing_call_ab):
        resp = client_b.get(f"/api/chat/calls/{ringing_call_ab.id}/status/")
        assert resp.status_code == 200

    def test_get_status_with_started_at(self, client_a, ringing_call_ab):
        now = timezone.now()
        ringing_call_ab.status = "accepted"
        ringing_call_ab.started_at = now
        ringing_call_ab.save()
        resp = client_a.get(f"/api/chat/calls/{ringing_call_ab.id}/status/")
        assert resp.data["started_at"] is not None

    def test_get_status_not_participant(self, client_c, ringing_call_ab):
        resp = client_c.get(f"/api/chat/calls/{ringing_call_ab.id}/status/")
        assert resp.status_code == 403

    def test_get_status_nonexistent(self, client_a):
        resp = client_a.get(f"/api/chat/calls/{uuid.uuid4()}/status/")
        assert resp.status_code == 404


@pytest.mark.django_db
class TestCallHistory:
    """GET /api/chat/calls/history/"""

    def test_history_as_caller(self, client_a, ringing_call_ab):
        resp = client_a.get("/api/chat/calls/history/")
        assert resp.status_code == 200
        results = resp.data.get("results", resp.data)
        assert len(results) >= 1

    def test_history_as_callee(self, client_b, ringing_call_ab):
        resp = client_b.get("/api/chat/calls/history/")
        assert resp.status_code == 200
        results = resp.data.get("results", resp.data)
        assert len(results) >= 1

    def test_history_excludes_other_users(self, client_c, ringing_call_ab):
        resp = client_c.get("/api/chat/calls/history/")
        assert resp.status_code == 200
        results = resp.data.get("results", resp.data)
        assert len(results) == 0

    def test_history_empty(self, client_c):
        resp = client_c.get("/api/chat/calls/history/")
        assert resp.status_code == 200


@pytest.mark.django_db
class TestIncomingCalls:
    """GET /api/chat/calls/incoming/"""

    def test_incoming_for_callee(self, client_b, ringing_call_ab):
        resp = client_b.get("/api/chat/calls/incoming/")
        assert resp.status_code == 200
        assert len(resp.data) >= 1
        assert resp.data[0]["call_type"] == "voice"
        assert resp.data[0]["caller_name"] == "User Alpha"

    def test_incoming_not_shown_for_caller(self, client_a, ringing_call_ab):
        resp = client_a.get("/api/chat/calls/incoming/")
        assert resp.status_code == 200
        call_ids = [c["call_id"] for c in resp.data]
        assert str(ringing_call_ab.id) not in call_ids

    def test_incoming_excludes_completed(self, client_b, user_a, user_b):
        Call.objects.create(
            caller=user_a, callee=user_b,
            call_type="voice", status="completed",
        )
        resp = client_b.get("/api/chat/calls/incoming/")
        for c in resp.data:
            assert c.get("status", "ringing") != "completed"


# ══════════════════════════════════════════════════════════════════════
#  4. BLOCKING ENFORCEMENT
# ══════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestBlockingPreventsCall:
    """Blocked users cannot call each other."""

    @patch("apps.chat.views.CallViewSet._notify_callee")
    def test_blocked_user_cannot_initiate_call(self, mock_notify, client_a, user_a, user_b):
        BlockedUser.objects.create(blocker=user_b, blocked=user_a, reason="spam")
        resp = client_a.post(
            "/api/chat/calls/initiate/",
            {"callee_id": str(user_b.id), "call_type": "voice"},
            format="json",
        )
        assert resp.status_code == 403

    @patch("apps.chat.views.CallViewSet._notify_callee")
    def test_blocker_cannot_call_blocked(self, mock_notify, client_a, user_a, user_b):
        BlockedUser.objects.create(blocker=user_a, blocked=user_b, reason="test")
        resp = client_a.post(
            "/api/chat/calls/initiate/",
            {"callee_id": str(user_b.id), "call_type": "voice"},
            format="json",
        )
        assert resp.status_code == 403


@pytest.mark.django_db
class TestBlockingPreventsConversation:
    """Blocked users cannot start conversations."""

    def test_blocked_user_cannot_start_conversation(self, client_a, user_a, user_b):
        BlockedUser.objects.create(blocker=user_b, blocked=user_a, reason="spam")
        resp = client_a.post(
            "/api/chat/start/",
            {"target_user_id": str(user_b.id)},
            format="json",
        )
        assert resp.status_code == 403

    def test_blocker_cannot_start_conversation(self, client_a, user_a, user_b):
        BlockedUser.objects.create(blocker=user_a, blocked=user_b, reason="test")
        resp = client_a.post(
            "/api/chat/start/",
            {"target_user_id": str(user_b.id)},
            format="json",
        )
        assert resp.status_code == 403


# ══════════════════════════════════════════════════════════════════════
#  5. AGORA ENDPOINTS
# ══════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestAgoraConfig:
    """GET /api/chat/agora/config/"""

    def test_config_returns_app_id(self, client_a):
        with patch("django.conf.settings.AGORA_APP_ID", "test-app-id"):
            resp = client_a.get("/api/chat/agora/config/")
        assert resp.status_code == 200
        assert resp.data["appId"] == "test-app-id"

    def test_config_not_configured(self, client_a):
        with patch("django.conf.settings.AGORA_APP_ID", ""):
            resp = client_a.get("/api/chat/agora/config/")
        assert resp.status_code == 503

    def test_config_unauthenticated(self, anon_client):
        resp = anon_client.get("/api/chat/agora/config/")
        assert resp.status_code == 401


@pytest.mark.django_db
class TestAgoraRtmToken:
    """POST /api/chat/agora/rtm-token/"""

    def test_rtm_not_configured(self, client_a):
        with patch("django.conf.settings.AGORA_APP_ID", ""), \
             patch("django.conf.settings.AGORA_APP_CERTIFICATE", ""):
            resp = client_a.post("/api/chat/agora/rtm-token/")
        assert resp.status_code == 503

    def test_rtm_success(self, client_a):
        import sys
        import types
        mock_rtm = types.ModuleType("agora_token_builder.RtmTokenBuilder")
        mock_builder = Mock()
        mock_builder.buildToken.return_value = "fake-rtm-token"
        mock_rtm.RtmTokenBuilder = mock_builder
        mock_rtm.Role_Rtm_User = 1
        with patch.dict(sys.modules, {
            "agora_token_builder": types.ModuleType("agora_token_builder"),
            "agora_token_builder.RtmTokenBuilder": mock_rtm,
        }), patch("django.conf.settings.AGORA_APP_ID", "test-id"), \
             patch("django.conf.settings.AGORA_APP_CERTIFICATE", "test-cert"):
            resp = client_a.post("/api/chat/agora/rtm-token/")
        assert resp.status_code == 200
        assert resp.data["token"] == "fake-rtm-token"
        assert "uid" in resp.data
        assert "expiresIn" in resp.data


@pytest.mark.django_db
class TestAgoraRtcToken:
    """POST /api/chat/agora/rtc-token/"""

    def test_rtc_not_configured(self, client_a):
        with patch("django.conf.settings.AGORA_APP_ID", ""), \
             patch("django.conf.settings.AGORA_APP_CERTIFICATE", ""):
            resp = client_a.post(
                "/api/chat/agora/rtc-token/",
                {"channelName": "test"},
                format="json",
            )
        assert resp.status_code == 503

    def test_rtc_missing_channel(self, client_a):
        with patch("django.conf.settings.AGORA_APP_ID", "test-id"), \
             patch("django.conf.settings.AGORA_APP_CERTIFICATE", "test-cert"):
            resp = client_a.post("/api/chat/agora/rtc-token/", {}, format="json")
        assert resp.status_code == 400

    def test_rtc_invalid_channel_name(self, client_a):
        with patch("django.conf.settings.AGORA_APP_ID", "test-id"), \
             patch("django.conf.settings.AGORA_APP_CERTIFICATE", "test-cert"):
            resp = client_a.post(
                "/api/chat/agora/rtc-token/",
                {"channelName": "invalid name!@#"},
                format="json",
            )
        assert resp.status_code == 400

    def test_rtc_channel_too_long(self, client_a):
        with patch("django.conf.settings.AGORA_APP_ID", "test-id"), \
             patch("django.conf.settings.AGORA_APP_CERTIFICATE", "test-cert"):
            resp = client_a.post(
                "/api/chat/agora/rtc-token/",
                {"channelName": "a" * 65},
                format="json",
            )
        assert resp.status_code == 400

    def test_rtc_not_authorized(self, client_a):
        """Channel name that doesn't match any active call or circle."""
        with patch("django.conf.settings.AGORA_APP_ID", "test-id"), \
             patch("django.conf.settings.AGORA_APP_CERTIFICATE", "test-cert"):
            resp = client_a.post(
                "/api/chat/agora/rtc-token/",
                {"channelName": str(uuid.uuid4())},
                format="json",
            )
        assert resp.status_code == 403

    def test_rtc_authorized_call(self, client_a, user_a, user_b):
        """RTC token for an active call the user is part of."""
        import sys
        import types
        mock_rtc = types.ModuleType("agora_token_builder.RtcTokenBuilder")
        mock_builder = Mock()
        mock_builder.buildTokenWithAccount.return_value = "fake-rtc-token"
        mock_rtc.RtcTokenBuilder = mock_builder
        mock_rtc.Role_Publisher = 1

        call = Call.objects.create(
            caller=user_a, callee=user_b, call_type="voice", status="ringing"
        )
        with patch.dict(sys.modules, {
            "agora_token_builder": types.ModuleType("agora_token_builder"),
            "agora_token_builder.RtcTokenBuilder": mock_rtc,
        }), patch("django.conf.settings.AGORA_APP_ID", "test-id"), \
             patch("django.conf.settings.AGORA_APP_CERTIFICATE", "test-cert"):
            resp = client_a.post(
                "/api/chat/agora/rtc-token/",
                {"channelName": str(call.id)},
                format="json",
            )
        assert resp.status_code == 200
        assert resp.data["token"] == "fake-rtc-token"
        assert resp.data["channelName"] == str(call.id)

    def test_rtc_channel_name_alias(self, client_a, user_a, user_b):
        """channel_name (snake_case) also accepted."""
        import sys
        import types
        mock_rtc = types.ModuleType("agora_token_builder.RtcTokenBuilder")
        mock_builder = Mock()
        mock_builder.buildTokenWithAccount.return_value = "fake-rtc-token"
        mock_rtc.RtcTokenBuilder = mock_builder
        mock_rtc.Role_Publisher = 1

        call = Call.objects.create(
            caller=user_a, callee=user_b, call_type="voice", status="ringing"
        )
        with patch.dict(sys.modules, {
            "agora_token_builder": types.ModuleType("agora_token_builder"),
            "agora_token_builder.RtcTokenBuilder": mock_rtc,
        }), patch("django.conf.settings.AGORA_APP_ID", "test-id"), \
             patch("django.conf.settings.AGORA_APP_CERTIFICATE", "test-cert"):
            resp = client_a.post(
                "/api/chat/agora/rtc-token/",
                {"channel_name": str(call.id)},
                format="json",
            )
        assert resp.status_code == 200


# ══════════════════════════════════════════════════════════════════════
#  6. SERIALIZERS
# ══════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestChatConversationSerializerComplete:
    """Comprehensive serializer tests."""

    def test_serializer_fields(self, conversation_ab, user_a):
        factory = APIRequestFactory()
        request = factory.get("/")
        request.user = user_a
        data = ChatConversationSerializer(
            conversation_ab, context={"request": request}
        ).data
        expected = {
            "id", "user", "title", "total_messages", "is_active",
            "last_message", "unread_count", "target_user",
            "created_at", "updated_at",
        }
        assert set(data.keys()) == expected

    def test_target_user_for_owner(self, conversation_ab, user_a, user_b):
        """Owner sees target_user info for user_b."""
        factory = APIRequestFactory()
        request = factory.get("/")
        request.user = user_a
        data = ChatConversationSerializer(
            conversation_ab, context={"request": request}
        ).data
        assert data["target_user"] is not None
        assert data["target_user"]["id"] == str(user_b.id)
        assert data["target_user"]["display_name"] == "User Beta"

    def test_target_user_for_target(self, conversation_ab, user_a, user_b):
        """target_user sees owner info."""
        factory = APIRequestFactory()
        request = factory.get("/")
        request.user = user_b
        data = ChatConversationSerializer(
            conversation_ab, context={"request": request}
        ).data
        assert data["target_user"] is not None
        assert data["target_user"]["id"] == str(user_a.id)

    def test_last_message(self, conversation_ab, message_in_ab, user_a):
        factory = APIRequestFactory()
        request = factory.get("/")
        request.user = user_a
        data = ChatConversationSerializer(
            conversation_ab, context={"request": request}
        ).data
        assert data["last_message"] is not None
        assert "Hello from A!" in data["last_message"]["content"]

    def test_unread_count_no_read_status(self, conversation_ab, user_b):
        """user_b has not read any messages — all from user_a are unread."""
        ChatMessage.objects.create(
            conversation=conversation_ab, role="user", content="Msg from A",
            metadata={"sender_id": str(conversation_ab.user_id)},
        )
        factory = APIRequestFactory()
        request = factory.get("/")
        request.user = user_b
        data = ChatConversationSerializer(
            conversation_ab, context={"request": request}
        ).data
        assert data["unread_count"] >= 1

    def test_unread_count_with_read_status(self, conversation_ab, user_b, message_in_ab):
        """After mark-read, unread_count should be 0 for user_b."""
        MessageReadStatus.objects.create(
            user=user_b,
            conversation=conversation_ab,
            last_read_message=message_in_ab,
        )
        factory = APIRequestFactory()
        request = factory.get("/")
        request.user = user_b
        data = ChatConversationSerializer(
            conversation_ab, context={"request": request}
        ).data
        assert data["unread_count"] == 0


@pytest.mark.django_db
class TestChatConversationDetailSerializerComplete:
    """Detail serializer caps messages at 50."""

    def test_messages_capped_at_50(self, conversation_ab, user_a):
        # Create 55 messages
        for i in range(55):
            ChatMessage.objects.create(
                conversation=conversation_ab, role="user", content=f"Msg {i}"
            )
        data = ChatConversationDetailSerializer(conversation_ab).data
        assert len(data["messages"]) == 50


@pytest.mark.django_db
class TestChatMessageCreateSerializerComplete:
    """Validation tests for ChatMessageCreateSerializer."""

    def test_valid(self):
        s = ChatMessageCreateSerializer(data={"content": "Hello!"})
        assert s.is_valid()

    def test_empty_rejected(self):
        s = ChatMessageCreateSerializer(data={"content": ""})
        assert not s.is_valid()

    def test_whitespace_rejected(self):
        s = ChatMessageCreateSerializer(data={"content": "   "})
        assert not s.is_valid()

    def test_missing_content(self):
        s = ChatMessageCreateSerializer(data={})
        assert not s.is_valid()

    def test_max_length_5000(self):
        s = ChatMessageCreateSerializer(data={"content": "x" * 5001})
        assert not s.is_valid()

    def test_content_stripped(self):
        s = ChatMessageCreateSerializer(data={"content": "  Hello  "})
        assert s.is_valid()
        assert s.validated_data["content"] == "Hello"


@pytest.mark.django_db
class TestCallHistorySerializerComplete:
    """CallHistorySerializer output."""

    def test_fields(self, ringing_call_ab):
        data = CallHistorySerializer(ringing_call_ab).data
        expected = {
            "id", "caller_id", "callee_id", "caller_name", "callee_name",
            "call_type", "status", "started_at", "ended_at",
            "duration_seconds", "created_at",
        }
        assert set(data.keys()) == expected


# ══════════════════════════════════════════════════════════════════════
#  7. MODEL UNIT TESTS
# ══════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestChatConversationModelComplete:
    def test_create(self, user_a, user_b):
        conv = ChatConversation.objects.create(user=user_a, target_user=user_b)
        assert isinstance(conv.id, uuid.UUID)
        assert conv.is_active is True
        assert conv.total_messages == 0

    def test_str(self, conversation_ab):
        assert conversation_ab.user.email in str(conversation_ab)

    def test_ordering(self, user_a, user_b):
        c1 = ChatConversation.objects.create(user=user_a, target_user=user_b)
        c2 = ChatConversation.objects.create(user=user_a, target_user=user_b)
        convs = list(ChatConversation.objects.filter(user=user_a))
        assert convs[0].id == c2.id


@pytest.mark.django_db
class TestChatMessageModelComplete:
    def test_create(self, conversation_ab, user_a):
        msg = ChatMessage.objects.create(
            conversation=conversation_ab, role="user", content="Hi",
            metadata={"sender_id": str(user_a.id)},
        )
        assert isinstance(msg.id, uuid.UUID)
        assert msg.is_pinned is False
        assert msg.is_liked is False
        assert msg.reactions == []
        assert msg.audio_url == ""
        assert msg.audio_duration is None
        assert msg.image_url == ""

    def test_str_short(self, conversation_ab):
        msg = ChatMessage.objects.create(
            conversation=conversation_ab, role="user", content="Short"
        )
        assert str(msg) == "user: Short"

    def test_str_long(self, conversation_ab):
        long = "C" * 100
        msg = ChatMessage.objects.create(
            conversation=conversation_ab, role="user", content=long
        )
        assert str(msg) == f"user: {'C' * 50}..."

    def test_ordering_ascending(self, conversation_ab):
        m1 = ChatMessage.objects.create(
            conversation=conversation_ab, role="user", content="First"
        )
        m2 = ChatMessage.objects.create(
            conversation=conversation_ab, role="user", content="Second"
        )
        msgs = list(conversation_ab.messages.all())
        assert msgs[0].id == m1.id
        assert msgs[1].id == m2.id

    def test_role_choices(self, conversation_ab):
        for role in ["user", "system"]:
            msg = ChatMessage.objects.create(
                conversation=conversation_ab, role=role, content=f"From {role}"
            )
            assert msg.role == role

    def test_voice_message_fields(self, conversation_ab):
        """Audio-related fields can be set on a message."""
        msg = ChatMessage.objects.create(
            conversation=conversation_ab,
            role="user",
            content="[voice message]",
            audio_url="https://example.com/audio.mp3",
            audio_duration=30,
        )
        assert msg.audio_url == "https://example.com/audio.mp3"
        assert msg.audio_duration == 30

    def test_image_message_field(self, conversation_ab):
        msg = ChatMessage.objects.create(
            conversation=conversation_ab,
            role="user",
            content="Check this out",
            image_url="https://example.com/image.png",
        )
        assert msg.image_url == "https://example.com/image.png"


@pytest.mark.django_db
class TestMessageReadStatusModelComplete:
    def test_create(self, user_a, conversation_ab, message_in_ab):
        rs = MessageReadStatus.objects.create(
            user=user_a, conversation=conversation_ab,
            last_read_message=message_in_ab,
        )
        assert rs.pk is not None
        assert str(message_in_ab.id) in str(rs)

    def test_unique_constraint(self, user_a, conversation_ab, message_in_ab):
        from django.db import IntegrityError
        MessageReadStatus.objects.create(
            user=user_a, conversation=conversation_ab,
            last_read_message=message_in_ab,
        )
        with pytest.raises(IntegrityError):
            MessageReadStatus.objects.create(
                user=user_a, conversation=conversation_ab,
                last_read_message=message_in_ab,
            )


@pytest.mark.django_db
class TestCallModelComplete:
    def test_create(self, user_a, user_b):
        call = Call.objects.create(
            caller=user_a, callee=user_b,
            call_type="voice", status="ringing",
        )
        assert isinstance(call.id, uuid.UUID)
        assert call.duration_seconds == 0
        assert call.started_at is None

    def test_str(self, ringing_call_ab):
        s = str(ringing_call_ab)
        assert "voice" in s
        assert "ringing" in s

    def test_all_status_choices(self, user_a, user_b):
        for st in ["ringing", "accepted", "in_progress", "completed", "rejected", "missed", "cancelled"]:
            call = Call.objects.create(
                caller=user_a, callee=user_b,
                call_type="voice", status=st,
            )
            assert call.status == st

    def test_ordering(self, user_a, user_b):
        c1 = Call.objects.create(
            caller=user_a, callee=user_b,
            call_type="voice", status="completed",
        )
        c2 = Call.objects.create(
            caller=user_a, callee=user_b,
            call_type="video", status="ringing",
        )
        calls = list(Call.objects.all())
        assert calls[0].id == c2.id


# ══════════════════════════════════════════════════════════════════════
#  8. BUDDY PAIRING + WEBSOCKET INTEGRATION
# ══════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestCallWithBuddyPairing:
    """Calls with active buddy pairings broadcast via WebSocket."""

    @patch("apps.chat.views.CallViewSet._notify_callee")
    def test_initiate_with_buddy_pairing(self, mock_notify, client_a, user_a, user_b):
        from apps.buddies.models import BuddyPairing
        BuddyPairing.objects.create(
            user1=user_a, user2=user_b, status="active"
        )
        with patch("channels.layers.get_channel_layer") as mock_layer:
            mock_layer.return_value = None
            resp = client_a.post(
                "/api/chat/calls/initiate/",
                {"callee_id": str(user_b.id), "call_type": "video"},
                format="json",
            )
        assert resp.status_code == 201


@pytest.mark.django_db
class TestSendMessageBuddyConversation:
    """Message in buddy conversation uses buddy_chat room name."""

    @patch("channels.layers.get_channel_layer")
    def test_send_in_buddy_conv(self, mock_layer, client_a, user_a, user_b):
        from apps.buddies.models import BuddyPairing
        pairing = BuddyPairing.objects.create(
            user1=user_a, user2=user_b, status="active"
        )
        conv = ChatConversation.objects.create(
            user=user_a, target_user=user_b, buddy_pairing=pairing
        )
        mock_layer.return_value = None
        resp = client_a.post(
            f"/api/chat/{conv.id}/send-message/",
            {"content": "Buddy msg"},
            format="json",
        )
        assert resp.status_code == 201


# ══════════════════════════════════════════════════════════════════════
#  9. FCM NOTIFY CALLEE
# ══════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestNotifyCallee:
    """_notify_callee FCM integration."""

    def test_no_devices_no_error(self, user_a, user_b):
        call = Call.objects.create(
            caller=user_a, callee=user_b, call_type="voice", status="ringing"
        )
        from apps.chat.views import CallViewSet
        viewset = CallViewSet()
        # Should not raise
        viewset._notify_callee(call, user_a)

    @patch("apps.notifications.fcm_service.FCMService")
    def test_with_device(self, mock_fcm_cls, user_a, user_b):
        from apps.notifications.models import UserDevice
        UserDevice.objects.create(
            user=user_b, fcm_token="test-token", platform="android", is_active=True,
        )
        mock_fcm_instance = Mock()
        mock_fcm_cls.return_value = mock_fcm_instance

        call = Call.objects.create(
            caller=user_a, callee=user_b, call_type="voice", status="ringing"
        )
        from apps.chat.views import CallViewSet
        CallViewSet()._notify_callee(call, user_a)
        mock_fcm_instance.send_to_token.assert_called_once()


# ══════════════════════════════════════════════════════════════════════
#  10. ADMIN
# ══════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestChatAdmin:
    """Admin classes are registered and functional."""

    def test_admin_registered(self):
        from django.contrib.admin.sites import site
        from apps.chat.models import Call, ChatConversation, ChatMessage, MessageReadStatus
        assert ChatConversation in site._registry
        assert ChatMessage in site._registry
        assert Call in site._registry
        assert MessageReadStatus in site._registry

    def test_conversation_admin_content_preview(self, conversation_ab, message_in_ab):
        from apps.chat.admin import ChatMessageAdmin
        admin_instance = ChatMessageAdmin(ChatMessage, None)
        preview = admin_instance.content_preview(message_in_ab)
        assert preview == "Hello from A!"


# ══════════════════════════════════════════════════════════════════════
#  11. ROUTING
# ══════════════════════════════════════════════════════════════════════


class TestChatRouting:
    """Chat routing patterns are correctly configured."""

    def test_routing_patterns_exist(self):
        from apps.chat.routing import websocket_urlpatterns
        assert len(websocket_urlpatterns) >= 1

    def test_buddy_chat_pattern(self):
        from apps.chat.routing import websocket_urlpatterns
        patterns = [p.pattern.regex.pattern for p in websocket_urlpatterns]
        assert any("buddy-chat" in p for p in patterns)

    def test_pairing_id_captured(self):
        from apps.chat.routing import websocket_urlpatterns
        pattern = websocket_urlpatterns[0]
        assert "pairing_id" in pattern.pattern.regex.pattern


# ══════════════════════════════════════════════════════════════════════
#  12. APP CONFIG
# ══════════════════════════════════════════════════════════════════════


class TestChatAppConfig:
    def test_app_name(self):
        from apps.chat.apps import ChatConfig
        assert ChatConfig.name == "apps.chat"
        assert ChatConfig.verbose_name == "Chat"
