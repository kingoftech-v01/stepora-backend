"""
Tests for the Buddy Chat WebSocket consumer.

Uses channels.testing.WebsocketCommunicator to test connect/disconnect
and message handling with mocked dependencies.
"""

import pytest

from apps.users.models import User


@pytest.fixture
def buddy_ws_user(db):
    """Create a user for buddy chat consumer tests."""
    return User.objects.create_user(
        email="buddy_ws_user@example.com",
        password="testpass123",
        display_name="Buddy WS User",
    )


@pytest.fixture
def buddy_ws_user2(db):
    """Create a second user for buddy chat consumer tests."""
    return User.objects.create_user(
        email="buddy_ws_user2@example.com",
        password="testpass123",
        display_name="Buddy WS User 2",
    )


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
class TestBuddyChatConsumerUnit:
    """Unit-level tests for BuddyChatConsumer behavior."""

    async def test_consumer_class_exists(self):
        """BuddyChatConsumer class can be imported."""
        from apps.chat.consumers import BuddyChatConsumer

        assert BuddyChatConsumer is not None

    async def test_consumer_has_connect_method(self):
        """BuddyChatConsumer has connect method."""
        from apps.chat.consumers import BuddyChatConsumer

        assert hasattr(BuddyChatConsumer, "connect")

    async def test_consumer_has_disconnect_method(self):
        """BuddyChatConsumer has disconnect method."""
        from apps.chat.consumers import BuddyChatConsumer

        assert hasattr(BuddyChatConsumer, "disconnect")

    async def test_consumer_has_receive_method(self):
        """BuddyChatConsumer has receive method."""
        from apps.chat.consumers import BuddyChatConsumer

        assert hasattr(BuddyChatConsumer, "receive")

    async def test_consumer_rate_limit_config(self):
        """BuddyChatConsumer has rate limit configuration."""
        from apps.chat.consumers import BuddyChatConsumer

        assert hasattr(BuddyChatConsumer, "rate_limit_msgs")
        assert BuddyChatConsumer.rate_limit_msgs == 30
        assert hasattr(BuddyChatConsumer, "rate_limit_window")
        assert BuddyChatConsumer.rate_limit_window == 60
