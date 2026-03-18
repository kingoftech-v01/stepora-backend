"""
Shared fixtures for AI app tests.
"""

from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.ai.models import AIConversation, AIMessage, ChatMemory, ConversationTemplate
from apps.dreams.models import Dream
from apps.subscriptions.models import Subscription, SubscriptionPlan
from apps.users.models import User


@pytest.fixture
def ai_user(db):
    """Create a premium test user for AI tests (AI features require premium)."""
    user = User.objects.create_user(
        email="ai_testuser@example.com",
        password="testpassword123",
        display_name="AI Test User",
        timezone="Europe/Paris",
    )
    plan = SubscriptionPlan.objects.get(slug="premium")
    Subscription.objects.update_or_create(
        user=user,
        defaults={
            "plan": plan,
            "status": "active",
            "current_period_start": timezone.now(),
            "current_period_end": timezone.now() + timedelta(days=30),
        },
    )
    return user


@pytest.fixture
def ai_user2(db):
    """Create a second test user for AI tests."""
    return User.objects.create_user(
        email="ai_testuser2@example.com",
        password="testpassword123",
        display_name="AI Test User 2",
        timezone="Europe/Paris",
    )


@pytest.fixture
def ai_client(ai_user):
    """Return an authenticated API client for AI tests."""
    client = APIClient()
    client.force_authenticate(user=ai_user)
    return client


@pytest.fixture
def ai_dream(db, ai_user):
    """Create a test dream for AI conversation linking."""
    return Dream.objects.create(
        user=ai_user,
        title="Learn Python",
        description="Master Python programming language",
        category="education",
        status="active",
    )


@pytest.fixture
def ai_conversation(db, ai_user):
    """Create a test AI conversation."""
    return AIConversation.objects.create(
        user=ai_user,
        conversation_type="general",
        title="Test Conversation",
    )


@pytest.fixture
def ai_conversation_with_dream(db, ai_user, ai_dream):
    """Create a test AI conversation linked to a dream."""
    return AIConversation.objects.create(
        user=ai_user,
        dream=ai_dream,
        conversation_type="planning",
        title="Planning Conversation",
    )


@pytest.fixture
def ai_message(db, ai_conversation):
    """Create a test AI message."""
    return AIMessage.objects.create(
        conversation=ai_conversation,
        role="user",
        content="Hello, AI coach!",
    )


@pytest.fixture
def ai_assistant_message(db, ai_conversation):
    """Create a test AI assistant message."""
    return AIMessage.objects.create(
        conversation=ai_conversation,
        role="assistant",
        content="Hello! How can I help you today?",
    )


@pytest.fixture
def ai_template(db):
    """Create a test conversation template."""
    return ConversationTemplate.objects.create(
        name="Test Template",
        conversation_type="general",
        system_prompt="You are a helpful AI coach.",
        description="A test template for unit tests.",
        is_active=True,
    )


@pytest.fixture
def ai_memory(db, ai_user, ai_conversation):
    """Create a test chat memory."""
    return ChatMemory.objects.create(
        user=ai_user,
        key="fact",
        content="User prefers morning routines.",
        source_conversation=ai_conversation,
        importance=3,
    )
