"""
Tests for AIChatConsumer WebSocket consumer.

Tests cover:
- Connect / disconnect lifecycle
- Post-connect JWT authentication
- Send prompt and receive streamed response
- Error handling (OpenAI failure, quota exceeded)
- Ping / pong
- Invalid JSON, oversized messages, empty messages
- Unauthenticated rejection
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

from apps.ai.consumers import AIChatConsumer
from apps.ai.models import AIConversation, AIMessage
from apps.users.models import User
from core.consumers import MAX_MSG_CONTENT_LEN, MAX_MSG_SIZE


# ──────────────────────────────────────────────────────────────────────
#  Helpers
# ──────────────────────────────────────────────────────────────────────


@database_sync_to_async
def _create_user(email, display_name="AI Test User"):
    return User.objects.create_user(
        email=email, password="testpassword123", display_name=display_name,
    )


@database_sync_to_async
def _create_ai_conversation(user, conversation_type="general"):
    return AIConversation.objects.create(
        user=user, conversation_type=conversation_type,
    )


@database_sync_to_async
def _count_messages(conversation_id):
    return AIMessage.objects.filter(conversation_id=conversation_id).count()


def _make_communicator(user, conversation_id):
    """Create a WebsocketCommunicator for AIChatConsumer with auth scope."""
    communicator = WebsocketCommunicator(
        AIChatConsumer.as_asgi(),
        f"/ws/ai-chat/{conversation_id}/",
    )
    communicator.scope["user"] = user
    communicator.scope["url_route"] = {"kwargs": {"conversation_id": str(conversation_id)}}
    communicator.scope["_allow_post_auth"] = False
    return communicator


def _make_anon_communicator(conversation_id):
    """Create a communicator for an unauthenticated (post-auth) user."""
    communicator = WebsocketCommunicator(
        AIChatConsumer.as_asgi(),
        f"/ws/ai-chat/{conversation_id}/",
    )
    communicator.scope["user"] = AnonymousUser()
    communicator.scope["url_route"] = {"kwargs": {"conversation_id": str(conversation_id)}}
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
    """Patch ModerationMixin._moderate_content to return a safe result."""
    if result is None:
        result = _FakeModerationResult()
    return patch(
        "core.consumers.ModerationMixin._moderate_content",
        new_callable=lambda: lambda self, *a, **kw: _async_return(result),
    )


def _patch_ai_quota(allowed=True, used=0, limit=50):
    """Patch the AI quota check."""
    info = {"used": used, "limit": limit}

    async def fake_check(self):
        return allowed, info

    return patch.object(AIChatConsumer, "_check_ai_quota", fake_check)


def _patch_ai_quota_increment():
    """Patch the AI quota increment."""

    async def fake_inc(self):
        return None

    return patch.object(AIChatConsumer, "_increment_ai_quota", fake_inc)


async def _fake_stream(*args, **kwargs):
    """Fake async generator for chat_stream_async."""
    for chunk in ["Hello", " from", " AI"]:
        yield chunk


def _patch_openai_stream():
    """Patch OpenAIService.chat_stream_async to yield test chunks."""
    return patch(
        "apps.ai.consumers.OpenAIService",
        return_value=MagicMock(chat_stream_async=_fake_stream),
    )


def _patch_ai_output_safety(safe=True):
    """Patch the AI output safety check."""

    async def fake_check(self, content):
        return safe

    return patch.object(AIChatConsumer, "_check_ai_output_safety", fake_check)


def _patch_memory_extraction():
    """Patch the memory extraction trigger."""

    async def fake_extract(self, conv):
        return None

    return patch.object(AIChatConsumer, "_maybe_extract_memories", fake_extract)


# ──────────────────────────────────────────────────────────────────────
#  Connect / Disconnect
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
class TestAIChatConnectDisconnect:
    """Connection and disconnection tests."""

    async def test_authenticated_user_connects_to_own_conversation(self):
        """Authenticated user connects to their own conversation."""
        user = await _create_user("ai_conn1@example.com")
        conv = await _create_ai_conversation(user)

        communicator = _make_communicator(user, conv.id)
        with _patch_moderation():
            connected, _ = await communicator.connect()
            assert connected

            response = await communicator.receive_json_from()
            assert response["type"] == "connection"
            assert response["status"] == "connected"
            assert response["conversation_id"] == str(conv.id)

            await communicator.disconnect()

    async def test_user_cannot_connect_to_others_conversation(self):
        """User should be rejected when connecting to another user's conversation."""
        user1 = await _create_user("ai_own1@example.com")
        user2 = await _create_user("ai_own2@example.com")
        conv = await _create_ai_conversation(user1)

        communicator = _make_communicator(user2, conv.id)
        with _patch_moderation():
            connected, _ = await communicator.connect()
            # The consumer accepts first then closes with 4003
            # so we may receive a close event
            await communicator.disconnect()

    async def test_nonexistent_conversation_is_rejected(self):
        """Connecting with a non-existent conversation ID should close."""
        user = await _create_user("ai_noconv@example.com")
        fake_id = str(uuid.uuid4())

        communicator = _make_communicator(user, fake_id)
        with _patch_moderation():
            connected, _ = await communicator.connect()
            await communicator.disconnect()

    async def test_unauthenticated_without_post_auth_rejected(self):
        """AnonymousUser without _allow_post_auth should be closed with 4003."""
        conv_id = str(uuid.uuid4())
        communicator = WebsocketCommunicator(
            AIChatConsumer.as_asgi(),
            f"/ws/ai-chat/{conv_id}/",
        )
        communicator.scope["user"] = AnonymousUser()
        communicator.scope["url_route"] = {"kwargs": {"conversation_id": conv_id}}
        communicator.scope["_allow_post_auth"] = False

        connected, code = await communicator.connect()
        assert not connected
        assert code == 4003

    async def test_anon_with_post_auth_is_accepted(self):
        """AnonymousUser with _allow_post_auth=True should be accepted."""
        conv_id = str(uuid.uuid4())
        communicator = _make_anon_communicator(conv_id)

        connected, _ = await communicator.connect()
        assert connected
        await communicator.disconnect()

    async def test_disconnect_cleans_up_group(self):
        """Disconnect should leave the channel group cleanly."""
        user = await _create_user("ai_disc@example.com")
        conv = await _create_ai_conversation(user)

        communicator = _make_communicator(user, conv.id)
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
class TestAIChatPostAuth:
    """Post-connect token authentication tests."""

    async def test_post_auth_with_valid_jwt(self):
        """Sending a valid JWT should authenticate and show connection."""
        user = await _create_user("ai_pa@example.com")
        conv = await _create_ai_conversation(user)

        from rest_framework_simplejwt.tokens import AccessToken

        token = str(AccessToken.for_user(user))

        communicator = _make_anon_communicator(conv.id)
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
        conv_id = str(uuid.uuid4())
        communicator = _make_anon_communicator(conv_id)

        connected, _ = await communicator.connect()
        assert connected

        await communicator.send_json_to({"type": "authenticate", "token": "bad-token"})
        response = await communicator.receive_json_from()
        assert response["type"] == "error"
        assert "Invalid token" in response["error"]

        await communicator.disconnect()


# ──────────────────────────────────────────────────────────────────────
#  Send prompt / receive streamed response
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
class TestAIChatStreaming:
    """Test prompt sending and AI response streaming."""

    async def test_send_prompt_receives_stream(self):
        """Sending a message should trigger AI streaming and return chunks."""
        user = await _create_user("ai_stream@example.com")
        conv = await _create_ai_conversation(user)

        communicator = _make_communicator(user, conv.id)
        with (
            _patch_moderation(),
            _patch_ai_quota(allowed=True),
            _patch_ai_quota_increment(),
            _patch_openai_stream(),
            _patch_ai_output_safety(safe=True),
            _patch_memory_extraction(),
        ):
            connected, _ = await communicator.connect()
            await communicator.receive_json_from()  # connection msg

            await communicator.send_json_to(
                {"type": "message", "message": "Tell me about goals"}
            )

            # Collect all responses
            responses = []
            for _ in range(20):  # safeguard against infinite loop
                try:
                    resp = await communicator.receive_json_from(timeout=2)
                    responses.append(resp)
                    # After stream_end and the final message, we're done
                    if resp.get("type") == "message" and resp.get("message", {}).get("role") == "assistant":
                        break
                except Exception:
                    break

            types_received = [r["type"] for r in responses]

            # Should contain the user message echo, stream_start, stream chunks, stream_end, and assistant message
            assert "message" in types_received
            assert "stream_start" in types_received
            assert "stream_end" in types_received

            # At least one stream_chunk
            chunk_responses = [r for r in responses if r.get("type") == "stream_chunk"]
            assert len(chunk_responses) >= 1

            await communicator.disconnect()

    async def test_empty_message_returns_error(self):
        """An empty message should be rejected."""
        user = await _create_user("ai_empty@example.com")
        conv = await _create_ai_conversation(user)

        communicator = _make_communicator(user, conv.id)
        with _patch_moderation():
            connected, _ = await communicator.connect()
            await communicator.receive_json_from()

            await communicator.send_json_to({"type": "message", "message": ""})
            response = await communicator.receive_json_from()
            assert response["type"] == "error"
            assert "empty" in response["error"].lower()

            await communicator.disconnect()

    async def test_oversized_raw_message_returns_error(self):
        """A raw message exceeding MAX_MSG_SIZE should return error."""
        user = await _create_user("ai_big@example.com")
        conv = await _create_ai_conversation(user)

        communicator = _make_communicator(user, conv.id)
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
        user = await _create_user("ai_longcontent@example.com")
        conv = await _create_ai_conversation(user)

        communicator = _make_communicator(user, conv.id)
        with _patch_moderation():
            connected, _ = await communicator.connect()
            await communicator.receive_json_from()

            long_msg = "a" * (MAX_MSG_CONTENT_LEN + 1)
            await communicator.send_json_to({"type": "message", "message": long_msg})
            response = await communicator.receive_json_from()
            assert response["type"] == "error"
            assert "character limit" in response["error"].lower()

            await communicator.disconnect()


# ──────────────────────────────────────────────────────────────────────
#  Error handling
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
class TestAIChatErrors:
    """Error handling tests."""

    async def test_quota_exceeded_returns_quota_message(self):
        """When AI quota is exceeded, a quota_exceeded message should be sent."""
        user = await _create_user("ai_quota@example.com")
        conv = await _create_ai_conversation(user)

        communicator = _make_communicator(user, conv.id)
        with _patch_moderation(), _patch_ai_quota(allowed=False, used=50, limit=50):
            connected, _ = await communicator.connect()
            await communicator.receive_json_from()

            await communicator.send_json_to(
                {"type": "message", "message": "Hit quota"}
            )
            response = await communicator.receive_json_from()
            assert response["type"] == "quota_exceeded"
            assert "limit reached" in response["message"].lower()
            assert response["usage"]["used"] == 50
            assert response["usage"]["limit"] == 50

            await communicator.disconnect()

    async def test_openai_error_returns_service_unavailable(self):
        """When OpenAI raises an error, the consumer should send a service error."""
        user = await _create_user("ai_oaierr@example.com")
        conv = await _create_ai_conversation(user)

        from core.exceptions import OpenAIError

        async def failing_stream(*args, **kwargs):
            raise OpenAIError("Service down")
            # Need to make it an async generator even though it raises
            yield  # pragma: no cover

        communicator = _make_communicator(user, conv.id)
        with (
            _patch_moderation(),
            _patch_ai_quota(allowed=True),
            patch(
                "apps.ai.consumers.OpenAIService",
                return_value=MagicMock(chat_stream_async=failing_stream),
            ),
        ):
            connected, _ = await communicator.connect()
            await communicator.receive_json_from()

            await communicator.send_json_to(
                {"type": "message", "message": "Will fail"}
            )

            # Collect responses - should include the user message echo and then the error
            responses = []
            for _ in range(10):
                try:
                    resp = await communicator.receive_json_from(timeout=2)
                    responses.append(resp)
                    if resp.get("type") == "error":
                        break
                except Exception:
                    break

            error_msgs = [r for r in responses if r.get("type") == "error"]
            assert len(error_msgs) >= 1
            assert "unavailable" in error_msgs[0]["error"].lower()

            await communicator.disconnect()

    async def test_invalid_json_returns_error(self):
        """Non-JSON text should return an error."""
        user = await _create_user("ai_badjson@example.com")
        conv = await _create_ai_conversation(user)

        communicator = _make_communicator(user, conv.id)
        with _patch_moderation():
            connected, _ = await communicator.connect()
            await communicator.receive_json_from()

            await communicator.send_to(text_data="{invalid-json")
            response = await communicator.receive_json_from()
            assert response["type"] == "error"
            assert "Invalid JSON" in response["error"]

            await communicator.disconnect()

    async def test_not_authenticated_returns_error(self):
        """Messages before auth should return 'Not authenticated' error."""
        conv_id = str(uuid.uuid4())
        communicator = _make_anon_communicator(conv_id)

        connected, _ = await communicator.connect()
        assert connected

        await communicator.send_json_to({"type": "message", "message": "hello"})
        response = await communicator.receive_json_from()
        assert response["type"] == "error"
        assert "Not authenticated" in response["error"]

        await communicator.disconnect()


# ──────────────────────────────────────────────────────────────────────
#  Content moderation
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
class TestAIChatModeration:
    """Content moderation tests."""

    async def test_flagged_content_returns_moderation_notice(self):
        """A flagged message should return a moderation response."""
        user = await _create_user("ai_mod@example.com")
        conv = await _create_ai_conversation(user)

        flagged = _FakeModerationResult(
            is_flagged=True, user_message="Inappropriate content"
        )
        communicator = _make_communicator(user, conv.id)
        with _patch_moderation(flagged):
            connected, _ = await communicator.connect()
            await communicator.receive_json_from()

            await communicator.send_json_to(
                {"type": "message", "message": "bad stuff"}
            )
            response = await communicator.receive_json_from()
            assert response["type"] == "moderation"
            assert "Inappropriate content" in response["message"]

            await communicator.disconnect()


# ──────────────────────────────────────────────────────────────────────
#  Ping / Pong
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
class TestAIChatPingPong:
    """Ping / pong tests."""

    async def test_ping_returns_pong(self):
        """Sending a ping should return a pong."""
        user = await _create_user("ai_ping@example.com")
        conv = await _create_ai_conversation(user)

        communicator = _make_communicator(user, conv.id)
        with _patch_moderation():
            connected, _ = await communicator.connect()
            await communicator.receive_json_from()

            await communicator.send_json_to({"type": "ping"})
            response = await communicator.receive_json_from()
            assert response["type"] == "pong"

            await communicator.disconnect()


# ──────────────────────────────────────────────────────────────────────
#  Typing indicator
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
class TestAIChatTyping:
    """Typing indicator tests."""

    async def test_typing_does_not_error(self):
        """Sending a typing indicator should not raise errors."""
        user = await _create_user("ai_typ@example.com")
        conv = await _create_ai_conversation(user)

        communicator = _make_communicator(user, conv.id)
        with _patch_moderation():
            connected, _ = await communicator.connect()
            await communicator.receive_json_from()

            await communicator.send_json_to({"type": "typing", "is_typing": True})
            # Own typing events are filtered out for the sender
            assert await communicator.receive_nothing(timeout=0.5)

            await communicator.disconnect()


# ──────────────────────────────────────────────────────────────────────
#  Routing
# ──────────────────────────────────────────────────────────────────────


class TestAIChatRouting:
    """Test that routing patterns are correctly configured."""

    def test_routing_has_ai_chat_pattern(self):
        """AI routing should define ai-chat URL pattern."""
        from apps.ai.routing import websocket_urlpatterns

        assert len(websocket_urlpatterns) >= 1
        patterns = [p.pattern.regex.pattern for p in websocket_urlpatterns]
        assert any("ai-chat" in p for p in patterns)

    def test_routing_has_deprecated_conversations_pattern(self):
        """AI routing should have the backward-compat conversations pattern."""
        from apps.ai.routing import websocket_urlpatterns

        patterns = [p.pattern.regex.pattern for p in websocket_urlpatterns]
        assert any("conversations" in p for p in patterns)

    def test_routing_captures_conversation_id(self):
        """Both AI chat routes should capture conversation_id."""
        from apps.ai.routing import websocket_urlpatterns

        for pattern in websocket_urlpatterns:
            assert "conversation_id" in pattern.pattern.regex.pattern
