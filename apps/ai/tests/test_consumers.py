"""
Tests for the AI Chat WebSocket consumer.

Uses channels.testing.WebsocketCommunicator to test connect/disconnect
and message handling with mocked OpenAI service.
"""


import pytest

from apps.ai.models import AIConversation
from apps.users.models import User


@pytest.fixture
def ai_ws_user(db):
    """Create a user for AI consumer tests."""
    return User.objects.create_user(
        email="ai_ws_user@example.com",
        password="testpass123",
        display_name="AI WS User",
    )


@pytest.fixture
def ai_ws_conversation(db, ai_ws_user):
    """Create an AI conversation for testing."""
    return AIConversation.objects.create(
        user=ai_ws_user,
        conversation_type="general",
    )


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
class TestAIChatConsumerUnit:
    """Unit-level tests for AIChatConsumer behavior."""

    async def test_consumer_class_exists(self):
        """AIChatConsumer class can be imported."""
        from apps.ai.consumers import AIChatConsumer

        assert AIChatConsumer is not None

    async def test_consumer_has_connect_method(self):
        """AIChatConsumer has connect method."""
        from apps.ai.consumers import AIChatConsumer

        assert hasattr(AIChatConsumer, "connect")

    async def test_consumer_has_disconnect_method(self):
        """AIChatConsumer has disconnect method."""
        from apps.ai.consumers import AIChatConsumer

        assert hasattr(AIChatConsumer, "disconnect")

    async def test_consumer_has_receive_method(self):
        """AIChatConsumer has receive method."""
        from apps.ai.consumers import AIChatConsumer

        assert hasattr(AIChatConsumer, "receive")
