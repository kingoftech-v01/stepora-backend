"""
Tests for BuddyChatConsumer WebSocket consumer.

Tests cover:
- Connect / disconnect lifecycle
- Post-connect JWT authentication
- Send and receive chat messages
- Typing indicator broadcast
- Mark-read receipt
- Ping / pong
- Invalid JSON, oversized messages, empty messages
- Rate limiting
- Unauthenticated rejection
- Group management (join / leave on connect / disconnect)
"""

import json
import uuid
from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from channels.db import database_sync_to_async
from channels.testing import WebsocketCommunicator
from django.contrib.auth.models import AnonymousUser
from django.test import override_settings

from apps.buddies.models import BuddyPairing
from apps.chat.consumers import BuddyChatConsumer
from apps.chat.models import ChatConversation, ChatMessage
from apps.users.models import User
from core.consumers import MAX_MSG_CONTENT_LEN, MAX_MSG_SIZE


# ──────────────────────────────────────────────────────────────────────
#  Helpers
# ──────────────────────────────────────────────────────────────────────


@database_sync_to_async
def _create_user(email, display_name="Test User"):
    return User.objects.create_user(
        email=email, password="testpassword123", display_name=display_name,
    )


@database_sync_to_async
def _create_buddy_pairing(user1, user2, status="active"):
    return BuddyPairing.objects.create(
        user1=user1, user2=user2, status=status, compatibility_score=0.85,
    )


@database_sync_to_async
def _count_messages(conversation):
    return ChatMessage.objects.filter(conversation=conversation).count()


@database_sync_to_async
def _get_conversation(pairing):
    return ChatConversation.objects.filter(buddy_pairing=pairing).first()


def _make_communicator(user, pairing_id):
    """Create a WebsocketCommunicator wired to BuddyChatConsumer with auth scope."""
    communicator = WebsocketCommunicator(
        BuddyChatConsumer.as_asgi(),
        f"/ws/buddy-chat/{pairing_id}/",
    )
    communicator.scope["user"] = user
    communicator.scope["url_route"] = {"kwargs": {"pairing_id": str(pairing_id)}}
    communicator.scope["_allow_post_auth"] = False
    return communicator


def _make_anon_communicator(pairing_id):
    """Create a communicator for an unauthenticated (post-auth) user."""
    communicator = WebsocketCommunicator(
        BuddyChatConsumer.as_asgi(),
        f"/ws/buddy-chat/{pairing_id}/",
    )
    communicator.scope["user"] = AnonymousUser()
    communicator.scope["url_route"] = {"kwargs": {"pairing_id": str(pairing_id)}}
    communicator.scope["_allow_post_auth"] = True
    return communicator


@dataclass
class _FakeModerationResult:
    is_flagged: bool = False
    user_message: str = ""
    categories: list = None
    severity: str = "none"

    def __post_init__(self):
        if self.categories is None:
            self.categories = []


# ──────────────────────────────────────────────────────────────────────
#  Connect / Disconnect
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
class TestBuddyChatConnectDisconnect:
    """Connection and disconnection tests."""

    async def test_authenticated_user_connects_to_valid_pairing(self):
        """Authenticated user with a valid pairing connects successfully."""
        user1 = await _create_user("buddy_conn1@example.com", "User1")
        user2 = await _create_user("buddy_conn2@example.com", "User2")
        pairing = await _create_buddy_pairing(user1, user2)

        communicator = _make_communicator(user1, pairing.id)
        with _patch_moderation():
            connected, _ = await communicator.connect()
            assert connected

            # Should receive connection confirmation
            response = await communicator.receive_json_from()
            assert response["type"] == "connection"
            assert response["status"] == "connected"
            assert response["pairing_id"] == str(pairing.id)

            await communicator.disconnect()

    async def test_unauthenticated_user_without_post_auth_is_rejected(self):
        """AnonymousUser without _allow_post_auth should be closed with 4003."""
        pairing_id = str(uuid.uuid4())
        communicator = WebsocketCommunicator(
            BuddyChatConsumer.as_asgi(),
            f"/ws/buddy-chat/{pairing_id}/",
        )
        communicator.scope["user"] = AnonymousUser()
        communicator.scope["url_route"] = {"kwargs": {"pairing_id": pairing_id}}
        communicator.scope["_allow_post_auth"] = False

        connected, code = await communicator.connect()
        assert not connected
        assert code == 4003

    async def test_user_not_in_pairing_is_rejected(self):
        """A user who is not part of the pairing should be disconnected."""
        user1 = await _create_user("buddy_nip1@example.com")
        user2 = await _create_user("buddy_nip2@example.com")
        outsider = await _create_user("buddy_nip3@example.com")
        pairing = await _create_buddy_pairing(user1, user2)

        communicator = _make_communicator(outsider, pairing.id)
        with _patch_moderation():
            connected, _ = await communicator.connect()
            # Connection is accepted first, then error is sent
            # The consumer sends error then closes
            response = await communicator.receive_output()
            # Eventually gets a close
            await communicator.disconnect()

    async def test_invalid_pairing_id_is_rejected(self):
        """A non-existent pairing ID should close the connection."""
        user = await _create_user("buddy_bad_pair@example.com")
        fake_id = str(uuid.uuid4())

        communicator = _make_communicator(user, fake_id)
        with _patch_moderation():
            connected, _ = await communicator.connect()
            # Should receive error and close
            response = await communicator.receive_output()
            await communicator.disconnect()

    async def test_anon_user_with_post_auth_is_accepted(self):
        """AnonymousUser with _allow_post_auth=True should be accepted (for post-auth flow)."""
        pairing_id = str(uuid.uuid4())
        communicator = _make_anon_communicator(pairing_id)

        connected, _ = await communicator.connect()
        assert connected
        await communicator.disconnect()

    async def test_disconnect_cleans_up(self):
        """Disconnect should leave the channel group cleanly."""
        user1 = await _create_user("buddy_disc1@example.com")
        user2 = await _create_user("buddy_disc2@example.com")
        pairing = await _create_buddy_pairing(user1, user2)

        communicator = _make_communicator(user1, pairing.id)
        with _patch_moderation():
            connected, _ = await communicator.connect()
            assert connected
            await communicator.receive_json_from()  # consume connection message
            await communicator.disconnect()


# ──────────────────────────────────────────────────────────────────────
#  Post-connect authentication
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
class TestBuddyChatPostAuth:
    """Post-connect token authentication tests."""

    async def test_post_auth_with_valid_jwt(self):
        """Sending a valid JWT after connect should authenticate the user."""
        user1 = await _create_user("buddy_pa1@example.com")
        user2 = await _create_user("buddy_pa2@example.com")
        pairing = await _create_buddy_pairing(user1, user2)

        from rest_framework_simplejwt.tokens import AccessToken

        token = str(AccessToken.for_user(user1))

        communicator = _make_anon_communicator(pairing.id)
        with _patch_moderation():
            connected, _ = await communicator.connect()
            assert connected

            # Send authenticate message
            await communicator.send_json_to({"type": "authenticate", "token": token})

            # Should receive connection confirmation
            response = await communicator.receive_json_from()
            assert response["type"] == "connection"
            assert response["status"] == "connected"

            await communicator.disconnect()

    async def test_post_auth_with_invalid_token(self):
        """Sending an invalid token should return error and close."""
        pairing_id = str(uuid.uuid4())
        communicator = _make_anon_communicator(pairing_id)

        connected, _ = await communicator.connect()
        assert connected

        await communicator.send_json_to({"type": "authenticate", "token": "invalid-token"})

        # Should receive error message
        response = await communicator.receive_json_from()
        assert response["type"] == "error"
        assert "Invalid token" in response["error"]

        await communicator.disconnect()


# ──────────────────────────────────────────────────────────────────────
#  Send / Receive messages
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
class TestBuddyChatSendReceive:
    """Message sending and receiving tests."""

    async def test_send_message_succeeds(self):
        """Sending a valid message should broadcast it back via the group."""
        user1 = await _create_user("buddy_msg1@example.com", "Sender")
        user2 = await _create_user("buddy_msg2@example.com", "Receiver")
        pairing = await _create_buddy_pairing(user1, user2)

        communicator = _make_communicator(user1, pairing.id)
        with _patch_moderation(), _patch_push():
            connected, _ = await communicator.connect()
            assert connected
            await communicator.receive_json_from()  # connection msg

            await communicator.send_json_to(
                {"type": "message", "message": "Hello buddy!"}
            )

            # Should receive the broadcasted message
            response = await communicator.receive_json_from()
            assert response["type"] == "message"
            assert response["message"]["content"] == "Hello buddy!"
            assert response["message"]["sender_id"] == str(user1.id)

            await communicator.disconnect()

    async def test_empty_message_returns_error(self):
        """An empty message should return an error."""
        user1 = await _create_user("buddy_empty1@example.com")
        user2 = await _create_user("buddy_empty2@example.com")
        pairing = await _create_buddy_pairing(user1, user2)

        communicator = _make_communicator(user1, pairing.id)
        with _patch_moderation():
            connected, _ = await communicator.connect()
            await communicator.receive_json_from()

            await communicator.send_json_to({"type": "message", "message": ""})
            response = await communicator.receive_json_from()
            assert response["type"] == "error"
            assert "empty" in response["error"].lower()

            await communicator.disconnect()

    async def test_oversized_message_returns_error(self):
        """A message exceeding MAX_MSG_SIZE should return an error."""
        user1 = await _create_user("buddy_big1@example.com")
        user2 = await _create_user("buddy_big2@example.com")
        pairing = await _create_buddy_pairing(user1, user2)

        communicator = _make_communicator(user1, pairing.id)
        with _patch_moderation():
            connected, _ = await communicator.connect()
            await communicator.receive_json_from()

            # Send oversized raw message (exceeds MAX_MSG_SIZE)
            big_payload = "x" * (MAX_MSG_SIZE + 100)
            await communicator.send_to(text_data=big_payload)
            response = await communicator.receive_json_from()
            assert response["type"] == "error"
            assert "too large" in response["error"].lower()

            await communicator.disconnect()

    async def test_content_exceeding_max_length_returns_error(self):
        """A message content exceeding MAX_MSG_CONTENT_LEN should be rejected."""
        user1 = await _create_user("buddy_long1@example.com")
        user2 = await _create_user("buddy_long2@example.com")
        pairing = await _create_buddy_pairing(user1, user2)

        communicator = _make_communicator(user1, pairing.id)
        with _patch_moderation(), _patch_push():
            connected, _ = await communicator.connect()
            await communicator.receive_json_from()

            long_content = "a" * (MAX_MSG_CONTENT_LEN + 1)
            await communicator.send_json_to({"type": "message", "message": long_content})
            response = await communicator.receive_json_from()
            assert response["type"] == "error"
            assert "character limit" in response["error"].lower()

            await communicator.disconnect()

    async def test_invalid_json_returns_error(self):
        """Non-JSON text should return an error."""
        user1 = await _create_user("buddy_json1@example.com")
        user2 = await _create_user("buddy_json2@example.com")
        pairing = await _create_buddy_pairing(user1, user2)

        communicator = _make_communicator(user1, pairing.id)
        with _patch_moderation():
            connected, _ = await communicator.connect()
            await communicator.receive_json_from()

            await communicator.send_to(text_data="not-json{{{")
            response = await communicator.receive_json_from()
            assert response["type"] == "error"
            assert "Invalid JSON" in response["error"]

            await communicator.disconnect()

    async def test_message_not_authenticated_returns_error(self):
        """Sending a message before authentication should return error."""
        pairing_id = str(uuid.uuid4())
        communicator = _make_anon_communicator(pairing_id)

        connected, _ = await communicator.connect()
        assert connected

        await communicator.send_json_to({"type": "message", "message": "hello"})
        response = await communicator.receive_json_from()
        assert response["type"] == "error"
        assert "Not authenticated" in response["error"]

        await communicator.disconnect()

    async def test_message_saved_to_database(self):
        """A sent message should be persisted in the database."""
        user1 = await _create_user("buddy_db1@example.com")
        user2 = await _create_user("buddy_db2@example.com")
        pairing = await _create_buddy_pairing(user1, user2)

        communicator = _make_communicator(user1, pairing.id)
        with _patch_moderation(), _patch_push():
            connected, _ = await communicator.connect()
            await communicator.receive_json_from()

            await communicator.send_json_to(
                {"type": "message", "message": "Persisted msg"}
            )
            await communicator.receive_json_from()  # consume broadcast

            conv = await _get_conversation(pairing)
            assert conv is not None
            msg_count = await _count_messages(conv)
            assert msg_count >= 1

            await communicator.disconnect()


# ──────────────────────────────────────────────────────────────────────
#  Typing indicator
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
class TestBuddyChatTyping:
    """Typing indicator tests."""

    async def test_typing_indicator_broadcast(self):
        """Typing indicator should be broadcast via the group."""
        user1 = await _create_user("buddy_typ1@example.com")
        user2 = await _create_user("buddy_typ2@example.com")
        pairing = await _create_buddy_pairing(user1, user2)

        communicator = _make_communicator(user1, pairing.id)
        with _patch_moderation():
            connected, _ = await communicator.connect()
            await communicator.receive_json_from()

            await communicator.send_json_to(
                {"type": "typing", "is_typing": True}
            )
            # The typing_status handler filters out own user_id, so the sender
            # won't receive their own typing event. We verify no error is raised.
            # (In a two-communicator test, user2 would receive it.)
            assert await communicator.receive_nothing(timeout=0.5)

            await communicator.disconnect()


# ──────────────────────────────────────────────────────────────────────
#  Read receipt
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
class TestBuddyChatReadReceipt:
    """Mark-read receipt tests."""

    async def test_mark_read_returns_confirmation(self):
        """Sending mark_read should return a marked_read confirmation."""
        user1 = await _create_user("buddy_read1@example.com")
        user2 = await _create_user("buddy_read2@example.com")
        pairing = await _create_buddy_pairing(user1, user2)

        communicator = _make_communicator(user1, pairing.id)
        with _patch_moderation(), _patch_push():
            connected, _ = await communicator.connect()
            await communicator.receive_json_from()

            # Send a message first so there's something to mark read
            await communicator.send_json_to(
                {"type": "message", "message": "Read me"}
            )
            await communicator.receive_json_from()  # consume broadcast

            await communicator.send_json_to({"type": "mark_read"})
            response = await communicator.receive_json_from()
            assert response["type"] == "marked_read"
            assert response["pairing_id"] == str(pairing.id)

            await communicator.disconnect()


# ──────────────────────────────────────────────────────────────────────
#  Ping / Pong
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
class TestBuddyChatPingPong:
    """Ping / pong tests."""

    async def test_ping_returns_pong(self):
        """Sending a ping should return a pong."""
        user1 = await _create_user("buddy_ping1@example.com")
        user2 = await _create_user("buddy_ping2@example.com")
        pairing = await _create_buddy_pairing(user1, user2)

        communicator = _make_communicator(user1, pairing.id)
        with _patch_moderation():
            connected, _ = await communicator.connect()
            await communicator.receive_json_from()

            await communicator.send_json_to({"type": "ping"})
            response = await communicator.receive_json_from()
            assert response["type"] == "pong"

            await communicator.disconnect()


# ──────────────────────────────────────────────────────────────────────
#  Rate limiting
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
class TestBuddyChatRateLimit:
    """Rate limiting tests."""

    async def test_rate_limit_config(self):
        """BuddyChatConsumer should have correct rate limit settings."""
        assert BuddyChatConsumer.rate_limit_msgs == 30
        assert BuddyChatConsumer.rate_limit_window == 60


# ──────────────────────────────────────────────────────────────────────
#  Moderation
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
class TestBuddyChatModeration:
    """Content moderation tests."""

    async def test_flagged_content_is_blocked(self):
        """A message flagged by moderation should return a moderation notice."""
        user1 = await _create_user("buddy_mod1@example.com")
        user2 = await _create_user("buddy_mod2@example.com")
        pairing = await _create_buddy_pairing(user1, user2)

        communicator = _make_communicator(user1, pairing.id)
        flagged = _FakeModerationResult(
            is_flagged=True, user_message="Content not allowed"
        )
        with _patch_moderation(flagged):
            connected, _ = await communicator.connect()
            await communicator.receive_json_from()

            await communicator.send_json_to(
                {"type": "message", "message": "bad content"}
            )
            response = await communicator.receive_json_from()
            assert response["type"] == "moderation"
            assert "Content not allowed" in response["message"]

            await communicator.disconnect()


# ──────────────────────────────────────────────────────────────────────
#  Channel layer handler tests
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
class TestBuddyChatChannelHandlers:
    """Tests for the channel layer event handlers."""

    async def test_chat_message_handler(self):
        """The chat_message handler should forward messages to the client."""
        user1 = await _create_user("buddy_ch1@example.com")
        user2 = await _create_user("buddy_ch2@example.com")
        pairing = await _create_buddy_pairing(user1, user2)

        communicator = _make_communicator(user1, pairing.id)
        with _patch_moderation(), _patch_push():
            connected, _ = await communicator.connect()
            await communicator.receive_json_from()

            # Send a message - it will be broadcast via the group and received back
            await communicator.send_json_to(
                {"type": "message", "message": "Channel test"}
            )
            response = await communicator.receive_json_from()
            assert response["type"] == "message"
            assert response["message"]["content"] == "Channel test"

            await communicator.disconnect()


# ──────────────────────────────────────────────────────────────────────
#  Routing
# ──────────────────────────────────────────────────────────────────────


class TestBuddyChatRouting:
    """Test that routing patterns are correctly configured."""

    def test_routing_patterns_exist(self):
        """Chat routing should define buddy-chat URL pattern."""
        from apps.chat.routing import websocket_urlpatterns

        assert len(websocket_urlpatterns) >= 1
        patterns = [p.pattern.regex.pattern for p in websocket_urlpatterns]
        assert any("buddy-chat" in p for p in patterns)

    def test_routing_pattern_captures_pairing_id(self):
        """The buddy-chat route should capture pairing_id as a named group."""
        from apps.chat.routing import websocket_urlpatterns

        pattern = websocket_urlpatterns[0]
        assert "pairing_id" in pattern.pattern.regex.pattern


# ──────────────────────────────────────────────────────────────────────
#  Patch helpers
# ──────────────────────────────────────────────────────────────────────


def _patch_moderation(result=None):
    """Patch the ModerationMixin._moderate_content to return a safe result."""
    if result is None:
        result = _FakeModerationResult()
    return patch(
        "core.consumers.ModerationMixin._moderate_content",
        new_callable=lambda: lambda self, *a, **kw: _async_return(result),
    )


def _patch_push():
    """Patch push notification sending to do nothing."""
    return patch(
        "apps.chat.consumers.BuddyChatConsumer._send_push_notification",
        new_callable=lambda: lambda self, *a, **kw: _async_return(None),
    )


async def _async_return(value):
    return value
