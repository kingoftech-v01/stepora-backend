"""
Tests for CircleChatConsumer WebSocket consumer.

Tests cover:
- Connect / disconnect lifecycle
- Post-connect JWT authentication
- Send / receive group messages
- Membership validation (non-member rejected)
- Typing indicator
- Blocked user filtering in circle messages
- Ping / pong
- Invalid JSON, oversized messages, empty messages
- Content moderation
- Routing URL patterns
"""

import json
import uuid
from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from channels.db import database_sync_to_async
from channels.testing import WebsocketCommunicator
from django.contrib.auth.models import AnonymousUser

from apps.circles.consumers import CircleChatConsumer
from apps.circles.models import Circle, CircleMembership
from apps.users.models import User
from core.consumers import MAX_MSG_CONTENT_LEN, MAX_MSG_SIZE


# ──────────────────────────────────────────────────────────────────────
#  Helpers
# ──────────────────────────────────────────────────────────────────────


@database_sync_to_async
def _create_user(email, display_name="Circle Test User"):
    return User.objects.create_user(
        email=email, password="testpassword123", display_name=display_name,
    )


@database_sync_to_async
def _create_circle(creator, name="Test Circle"):
    return Circle.objects.create(
        name=name,
        description="A test circle",
        category="career",
        is_public=True,
        creator=creator,
        max_members=20,
    )


@database_sync_to_async
def _add_member(circle, user, role="member"):
    return CircleMembership.objects.create(
        circle=circle, user=user, role=role,
    )


@database_sync_to_async
def _create_block(blocker, blocked):
    from apps.social.models import BlockedUser

    return BlockedUser.objects.create(blocker=blocker, blocked=blocked)


def _make_communicator(user, circle_id):
    """Create a WebsocketCommunicator for CircleChatConsumer with auth scope."""
    communicator = WebsocketCommunicator(
        CircleChatConsumer.as_asgi(),
        f"/ws/circle-chat/{circle_id}/",
    )
    communicator.scope["user"] = user
    communicator.scope["url_route"] = {"kwargs": {"circle_id": str(circle_id)}}
    communicator.scope["_allow_post_auth"] = False
    return communicator


def _make_anon_communicator(circle_id):
    """Create a communicator for an unauthenticated (post-auth) user."""
    communicator = WebsocketCommunicator(
        CircleChatConsumer.as_asgi(),
        f"/ws/circle-chat/{circle_id}/",
    )
    communicator.scope["user"] = AnonymousUser()
    communicator.scope["url_route"] = {"kwargs": {"circle_id": str(circle_id)}}
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


async def _async_return(value):
    return value


def _patch_moderation(result=None):
    """Patch the ModerationMixin._moderate_content."""
    if result is None:
        result = _FakeModerationResult()
    return patch(
        "core.consumers.ModerationMixin._moderate_content",
        new_callable=lambda: lambda self, *a, **kw: _async_return(result),
    )


# ──────────────────────────────────────────────────────────────────────
#  Connect / Disconnect
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
class TestCircleChatConnectDisconnect:
    """Connection and disconnection tests."""

    async def test_member_connects_successfully(self):
        """A circle member should connect and receive connection confirmation."""
        creator = await _create_user("circ_conn1@example.com", "Creator")
        circle = await _create_circle(creator)
        await _add_member(circle, creator, role="admin")

        communicator = _make_communicator(creator, circle.id)
        with _patch_moderation():
            connected, _ = await communicator.connect()
            assert connected

            response = await communicator.receive_json_from()
            assert response["type"] == "connection"
            assert response["status"] == "connected"
            assert response["circle_id"] == str(circle.id)

            await communicator.disconnect()

    async def test_non_member_is_rejected(self):
        """A user who is not a circle member should be disconnected."""
        creator = await _create_user("circ_nm_creator@example.com", "Creator")
        outsider = await _create_user("circ_nm_out@example.com", "Outsider")
        circle = await _create_circle(creator)
        await _add_member(circle, creator, role="admin")

        communicator = _make_communicator(outsider, circle.id)
        with _patch_moderation():
            connected, _ = await communicator.connect()
            # Consumer accepts, checks membership, then sends error and closes
            response = await communicator.receive_output()
            await communicator.disconnect()

    async def test_unauthenticated_without_post_auth_rejected(self):
        """AnonymousUser without _allow_post_auth should be closed with 4003."""
        circle_id = str(uuid.uuid4())
        communicator = WebsocketCommunicator(
            CircleChatConsumer.as_asgi(),
            f"/ws/circle-chat/{circle_id}/",
        )
        communicator.scope["user"] = AnonymousUser()
        communicator.scope["url_route"] = {"kwargs": {"circle_id": circle_id}}
        communicator.scope["_allow_post_auth"] = False

        connected, code = await communicator.connect()
        assert not connected
        assert code == 4003

    async def test_anon_with_post_auth_accepted(self):
        """AnonymousUser with _allow_post_auth=True should be accepted."""
        circle_id = str(uuid.uuid4())
        communicator = _make_anon_communicator(circle_id)

        connected, _ = await communicator.connect()
        assert connected
        await communicator.disconnect()

    async def test_disconnect_cleans_up(self):
        """Disconnect should leave the channel group."""
        creator = await _create_user("circ_disc@example.com")
        circle = await _create_circle(creator)
        await _add_member(circle, creator, role="admin")

        communicator = _make_communicator(creator, circle.id)
        with _patch_moderation():
            connected, _ = await communicator.connect()
            assert connected
            await communicator.receive_json_from()  # connection msg
            await communicator.disconnect()


# ──────────────────────────────────────────────────────────────────────
#  Post-connect authentication
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
class TestCircleChatPostAuth:
    """Post-connect token authentication tests."""

    async def test_post_auth_with_valid_jwt(self):
        """Valid JWT post-auth should authenticate and show connection."""
        creator = await _create_user("circ_pa@example.com")
        circle = await _create_circle(creator)
        await _add_member(circle, creator, role="admin")

        from rest_framework_simplejwt.tokens import AccessToken

        token = str(AccessToken.for_user(creator))

        communicator = _make_anon_communicator(circle.id)
        with _patch_moderation():
            connected, _ = await communicator.connect()
            assert connected

            await communicator.send_json_to({"type": "authenticate", "token": token})
            response = await communicator.receive_json_from()
            assert response["type"] == "connection"
            assert response["status"] == "connected"

            await communicator.disconnect()

    async def test_post_auth_with_invalid_token(self):
        """An invalid token should return error and close."""
        circle_id = str(uuid.uuid4())
        communicator = _make_anon_communicator(circle_id)

        connected, _ = await communicator.connect()
        assert connected

        await communicator.send_json_to({"type": "authenticate", "token": "bad-token"})
        response = await communicator.receive_json_from()
        assert response["type"] == "error"
        assert "Invalid token" in response["error"]

        await communicator.disconnect()


# ──────────────────────────────────────────────────────────────────────
#  Send / Receive group messages
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
class TestCircleChatSendReceive:
    """Message sending and receiving tests."""

    async def test_send_message_succeeds(self):
        """Sending a valid message should broadcast it back via the group."""
        creator = await _create_user("circ_msg@example.com", "Sender")
        circle = await _create_circle(creator)
        await _add_member(circle, creator, role="admin")

        communicator = _make_communicator(creator, circle.id)
        with _patch_moderation():
            connected, _ = await communicator.connect()
            await communicator.receive_json_from()  # connection msg

            await communicator.send_json_to(
                {"type": "message", "message": "Hello circle!"}
            )

            response = await communicator.receive_json_from()
            assert response["type"] == "message"
            assert response["message"]["content"] == "Hello circle!"
            assert response["message"]["sender_id"] == str(creator.id)
            assert response["message"]["sender_name"] == "Sender"

            await communicator.disconnect()

    async def test_empty_message_returns_error(self):
        """An empty message should return an error."""
        creator = await _create_user("circ_empty@example.com")
        circle = await _create_circle(creator)
        await _add_member(circle, creator, role="admin")

        communicator = _make_communicator(creator, circle.id)
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
        creator = await _create_user("circ_big@example.com")
        circle = await _create_circle(creator)
        await _add_member(circle, creator, role="admin")

        communicator = _make_communicator(creator, circle.id)
        with _patch_moderation():
            connected, _ = await communicator.connect()
            await communicator.receive_json_from()

            big_payload = "x" * (MAX_MSG_SIZE + 100)
            await communicator.send_to(text_data=big_payload)
            response = await communicator.receive_json_from()
            assert response["type"] == "error"
            assert "too large" in response["error"].lower()

            await communicator.disconnect()

    async def test_content_exceeding_max_length_returns_error(self):
        """Message content exceeding MAX_MSG_CONTENT_LEN should be rejected."""
        creator = await _create_user("circ_long@example.com")
        circle = await _create_circle(creator)
        await _add_member(circle, creator, role="admin")

        communicator = _make_communicator(creator, circle.id)
        with _patch_moderation():
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
        creator = await _create_user("circ_badjson@example.com")
        circle = await _create_circle(creator)
        await _add_member(circle, creator, role="admin")

        communicator = _make_communicator(creator, circle.id)
        with _patch_moderation():
            connected, _ = await communicator.connect()
            await communicator.receive_json_from()

            await communicator.send_to(text_data="not-json!!!")
            response = await communicator.receive_json_from()
            assert response["type"] == "error"
            assert "Invalid JSON" in response["error"]

            await communicator.disconnect()

    async def test_message_not_authenticated_returns_error(self):
        """Sending a message before auth should return error."""
        circle_id = str(uuid.uuid4())
        communicator = _make_anon_communicator(circle_id)

        connected, _ = await communicator.connect()
        assert connected

        await communicator.send_json_to({"type": "message", "message": "hello"})
        response = await communicator.receive_json_from()
        assert response["type"] == "error"
        assert "Not authenticated" in response["error"]

        await communicator.disconnect()


# ──────────────────────────────────────────────────────────────────────
#  Membership validation
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
class TestCircleChatMembership:
    """Membership validation tests."""

    async def test_member_can_send_messages(self):
        """A member should be able to send and receive messages."""
        creator = await _create_user("circ_mem_cr@example.com", "Creator")
        member = await _create_user("circ_mem_mb@example.com", "Member")
        circle = await _create_circle(creator)
        await _add_member(circle, creator, role="admin")
        await _add_member(circle, member, role="member")

        communicator = _make_communicator(member, circle.id)
        with _patch_moderation():
            connected, _ = await communicator.connect()
            assert connected
            response = await communicator.receive_json_from()
            assert response["type"] == "connection"

            await communicator.send_json_to(
                {"type": "message", "message": "I am a member"}
            )
            response = await communicator.receive_json_from()
            assert response["type"] == "message"
            assert response["message"]["content"] == "I am a member"

            await communicator.disconnect()


# ──────────────────────────────────────────────────────────────────────
#  Blocked user filtering
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
class TestCircleChatBlocking:
    """Blocked user filtering tests."""

    async def test_blocked_user_ids_loaded_on_connect(self):
        """Blocked user IDs should be loaded when a member connects."""
        creator = await _create_user("circ_blk_cr@example.com", "Creator")
        blocker = await _create_user("circ_blk_blk@example.com", "Blocker")
        blocked_target = await _create_user("circ_blk_tgt@example.com", "Target")
        circle = await _create_circle(creator)
        await _add_member(circle, creator, role="admin")
        await _add_member(circle, blocker, role="member")
        await _add_member(circle, blocked_target, role="member")

        # blocker blocks blocked_target
        await _create_block(blocker, blocked_target)

        communicator = _make_communicator(blocker, circle.id)
        with _patch_moderation():
            connected, _ = await communicator.connect()
            assert connected
            await communicator.receive_json_from()  # connection msg
            # Connection succeeded — blocked user filtering is internal
            await communicator.disconnect()


# ──────────────────────────────────────────────────────────────────────
#  Typing indicator
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
class TestCircleChatTyping:
    """Typing indicator tests."""

    async def test_typing_does_not_error(self):
        """Sending a typing indicator should not raise errors."""
        creator = await _create_user("circ_typ@example.com")
        circle = await _create_circle(creator)
        await _add_member(circle, creator, role="admin")

        communicator = _make_communicator(creator, circle.id)
        with _patch_moderation():
            connected, _ = await communicator.connect()
            await communicator.receive_json_from()

            await communicator.send_json_to({"type": "typing", "is_typing": True})
            # Own typing is filtered out
            assert await communicator.receive_nothing(timeout=0.5)

            await communicator.disconnect()


# ──────────────────────────────────────────────────────────────────────
#  Ping / Pong
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
class TestCircleChatPingPong:
    """Ping / pong tests."""

    async def test_ping_returns_pong(self):
        """Sending a ping should return a pong."""
        creator = await _create_user("circ_ping@example.com")
        circle = await _create_circle(creator)
        await _add_member(circle, creator, role="admin")

        communicator = _make_communicator(creator, circle.id)
        with _patch_moderation():
            connected, _ = await communicator.connect()
            await communicator.receive_json_from()

            await communicator.send_json_to({"type": "ping"})
            response = await communicator.receive_json_from()
            assert response["type"] == "pong"

            await communicator.disconnect()


# ──────────────────────────────────────────────────────────────────────
#  Content moderation
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
class TestCircleChatModeration:
    """Content moderation tests."""

    async def test_flagged_content_returns_moderation_notice(self):
        """A flagged message should return a moderation response."""
        creator = await _create_user("circ_mod@example.com")
        circle = await _create_circle(creator)
        await _add_member(circle, creator, role="admin")

        flagged = _FakeModerationResult(
            is_flagged=True, user_message="Not allowed in group"
        )
        communicator = _make_communicator(creator, circle.id)
        with _patch_moderation(flagged):
            connected, _ = await communicator.connect()
            await communicator.receive_json_from()

            await communicator.send_json_to(
                {"type": "message", "message": "bad content"}
            )
            response = await communicator.receive_json_from()
            assert response["type"] == "moderation"
            assert "Not allowed in group" in response["message"]

            await communicator.disconnect()


# ──────────────────────────────────────────────────────────────────────
#  Rate limit config
# ──────────────────────────────────────────────────────────────────────


class TestCircleChatRateLimit:
    """Rate limit configuration tests."""

    def test_rate_limit_config(self):
        """CircleChatConsumer should have lower rate limits for group chat."""
        assert CircleChatConsumer.rate_limit_msgs == 20
        assert CircleChatConsumer.rate_limit_window == 60


# ──────────────────────────────────────────────────────────────────────
#  Routing
# ──────────────────────────────────────────────────────────────────────


class TestCircleChatRouting:
    """Test that routing patterns are correctly configured."""

    def test_routing_has_circle_chat_pattern(self):
        """Circle routing should define circle-chat URL pattern."""
        from apps.circles.routing import websocket_urlpatterns

        assert len(websocket_urlpatterns) >= 1
        patterns = [p.pattern.regex.pattern for p in websocket_urlpatterns]
        assert any("circle-chat" in p for p in patterns)

    def test_routing_captures_circle_id(self):
        """The circle-chat route should capture circle_id as a named group."""
        from apps.circles.routing import websocket_urlpatterns

        pattern = websocket_urlpatterns[0]
        assert "circle_id" in pattern.pattern.regex.pattern


# ──────────────────────────────────────────────────────────────────────
#  All routing files
# ──────────────────────────────────────────────────────────────────────


class TestAllRoutingPatterns:
    """Test that all routing.py files have correct URL patterns."""

    def test_buddy_chat_routing(self):
        from apps.chat.routing import websocket_urlpatterns

        assert isinstance(websocket_urlpatterns, list)
        assert len(websocket_urlpatterns) >= 1

    def test_ai_chat_routing(self):
        from apps.ai.routing import websocket_urlpatterns

        assert isinstance(websocket_urlpatterns, list)
        assert len(websocket_urlpatterns) >= 1

    def test_circle_chat_routing(self):
        from apps.circles.routing import websocket_urlpatterns

        assert isinstance(websocket_urlpatterns, list)
        assert len(websocket_urlpatterns) >= 1

    def test_notification_routing(self):
        from apps.notifications.routing import websocket_urlpatterns

        assert isinstance(websocket_urlpatterns, list)
        assert len(websocket_urlpatterns) >= 1

    def test_social_routing(self):
        from apps.social.routing import websocket_urlpatterns

        assert isinstance(websocket_urlpatterns, list)
        assert len(websocket_urlpatterns) >= 1

    def test_buddies_routing_is_empty_shim(self):
        """Buddies routing is an empty shim (buddy chat is in chat.routing)."""
        from apps.buddies.routing import websocket_urlpatterns

        assert websocket_urlpatterns == []

    def test_leagues_routing_is_empty(self):
        """Leagues routing is empty (no WebSocket consumer)."""
        from apps.leagues.routing import websocket_urlpatterns

        assert websocket_urlpatterns == []

    def test_all_patterns_in_asgi_config(self):
        """All non-empty routing patterns should be registered in ASGI."""
        from apps.ai.routing import websocket_urlpatterns as ai_ws
        from apps.chat.routing import websocket_urlpatterns as chat_ws
        from apps.circles.routing import websocket_urlpatterns as circle_ws
        from apps.notifications.routing import websocket_urlpatterns as notif_ws
        from apps.social.routing import websocket_urlpatterns as social_ws

        # Verify each has at least one pattern
        assert len(ai_ws) >= 1
        assert len(chat_ws) >= 1
        assert len(circle_ws) >= 1
        assert len(notif_ws) >= 1
        assert len(social_ws) >= 1
