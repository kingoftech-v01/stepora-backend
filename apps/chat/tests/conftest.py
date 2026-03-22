"""
Shared fixtures for Chat app tests.
"""

import pytest
from rest_framework.test import APIClient

from apps.chat.models import Call, ChatConversation, ChatMessage
from apps.users.models import User


@pytest.fixture
def chat_user(db):
    """Create a test user for chat tests."""
    return User.objects.create_user(
        email="chat_user@example.com",
        password="testpassword123",
        display_name="Chat User",
        timezone="Europe/Paris",
    )


@pytest.fixture
def chat_user2(db):
    """Create a second test user for chat tests."""
    return User.objects.create_user(
        email="chat_user2@example.com",
        password="testpassword123",
        display_name="Chat User 2",
        timezone="Europe/Paris",
    )


@pytest.fixture
def chat_user3(db):
    """Create a third test user for chat tests."""
    return User.objects.create_user(
        email="chat_user3@example.com",
        password="testpassword123",
        display_name="Chat User 3",
        timezone="Europe/Paris",
    )


@pytest.fixture
def chat_client(chat_user):
    """Return an authenticated API client for chat tests."""
    client = APIClient()
    client.force_authenticate(user=chat_user)
    return client


@pytest.fixture
def chat_client2(chat_user2):
    """Return an authenticated API client for the second chat user."""
    client = APIClient()
    client.force_authenticate(user=chat_user2)
    return client


@pytest.fixture
def chat_conversation(db, chat_user, chat_user2):
    """Create a test chat conversation between two users."""
    return ChatConversation.objects.create(
        user=chat_user,
        target_user=chat_user2,
        title="Test Chat",
    )


@pytest.fixture
def chat_message(db, chat_conversation, chat_user):
    """Create a test chat message."""
    return ChatMessage.objects.create(
        conversation=chat_conversation,
        role="user",
        content="Hello from chat!",
        metadata={"sender_id": str(chat_user.id)},
    )


@pytest.fixture
def chat_call(db, chat_user, chat_user2):
    """Create a test call between two users."""
    return Call.objects.create(
        caller=chat_user,
        callee=chat_user2,
        call_type="voice",
        status="ringing",
    )
