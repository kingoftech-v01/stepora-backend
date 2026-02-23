"""
Tests for conversations app.
"""

import pytest
from datetime import timedelta
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient
from unittest.mock import patch, Mock, AsyncMock
import json

from apps.users.models import User
from .models import Conversation, Message


@pytest.fixture
def user(db):
    """Override global user fixture to create a premium user for conversation tests."""
    return User.objects.create_user(
        email='testuser@example.com',
        password='testpassword123',
        display_name='Test User',
        timezone='Europe/Paris',
        subscription='premium',
        subscription_ends=timezone.now() + timedelta(days=30),
    )


@pytest.fixture
def authenticated_client(user):
    """Override global authenticated_client to use the premium user."""
    client = APIClient()
    client.force_authenticate(user=user)
    return client


class TestConversationModel:
    """Test Conversation model"""

    def test_create_conversation(self, db, conversation_data):
        """Test creating a conversation"""
        conversation = Conversation.objects.create(**conversation_data)

        assert conversation.user == conversation_data['user']
        assert conversation.conversation_type == 'general'
        assert conversation.is_active is True

    def test_conversation_str(self, conversation):
        """Test conversation string representation"""
        expected = f"{conversation.conversation_type} - {conversation.user.email}"
        assert str(conversation) == expected

    def test_get_messages_for_api(self, db, conversation):
        """Test getting messages formatted for API"""
        # Create some messages
        Message.objects.create(
            conversation=conversation,
            role='user',
            content='Hello'
        )
        Message.objects.create(
            conversation=conversation,
            role='assistant',
            content='Hi there!'
        )
        Message.objects.create(
            conversation=conversation,
            role='user',
            content='How are you?'
        )

        messages = conversation.get_messages_for_api(limit=2)

        # limit=2 returns the last 2 messages in chronological order
        assert len(messages) == 2
        assert messages[0]['role'] == 'assistant'
        assert messages[0]['content'] == 'Hi there!'
        assert messages[1]['role'] == 'user'
        assert messages[1]['content'] == 'How are you?'

    def test_add_message(self, conversation):
        """Test adding message to conversation"""
        message = conversation.add_message('user', 'Test message')

        assert message.conversation == conversation
        assert message.role == 'user'
        assert message.content == 'Test message'
        assert Message.objects.filter(conversation=conversation).count() == 1

    def test_add_message_updates_total(self, conversation):
        """Test that add_message increments total_messages"""
        conversation.add_message('user', 'First message')
        conversation.refresh_from_db()
        assert conversation.total_messages == 1

        conversation.add_message('assistant', 'Reply')
        conversation.refresh_from_db()
        assert conversation.total_messages == 2

    def test_add_message_tracks_tokens(self, conversation):
        """Test that add_message tracks token usage from metadata"""
        conversation.add_message('assistant', 'Response', metadata={'tokens_used': 50})
        conversation.refresh_from_db()
        assert conversation.total_tokens_used == 50


class TestMessageModel:
    """Test Message model"""

    def test_create_message(self, db, message_data):
        """Test creating a message"""
        message = Message.objects.create(**message_data)

        assert message.conversation == message_data['conversation']
        assert message.role == 'user'
        assert message.content == 'Hello, AI!'

    def test_message_ordering(self, db, conversation):
        """Test messages are ordered by creation time"""
        msg1 = Message.objects.create(conversation=conversation, role='user', content='First')
        msg2 = Message.objects.create(conversation=conversation, role='assistant', content='Second')
        msg3 = Message.objects.create(conversation=conversation, role='user', content='Third')

        messages = Message.objects.filter(conversation=conversation).order_by('created_at')
        assert list(messages) == [msg1, msg2, msg3]

    def test_message_metadata(self, db, conversation):
        """Test message with metadata"""
        metadata = {
            'tokens': 150,
            'model': 'gpt-4-turbo-preview',
            'finish_reason': 'stop'
        }

        message = Message.objects.create(
            conversation=conversation,
            role='assistant',
            content='Response with metadata',
            metadata=metadata
        )

        assert message.metadata['tokens'] == 150
        assert message.metadata['model'] == 'gpt-4-turbo-preview'

    def test_message_str(self, db, conversation):
        """Test message string representation"""
        message = Message.objects.create(
            conversation=conversation,
            role='user',
            content='Short message'
        )
        assert str(message) == 'user: Short message'

    def test_message_str_truncates_long_content(self, db, conversation):
        """Test message __str__ truncates long content"""
        long_content = 'A' * 100
        message = Message.objects.create(
            conversation=conversation,
            role='assistant',
            content=long_content
        )
        result = str(message)
        assert result.startswith('assistant: ')
        assert result.endswith('...')


class TestConversationViewSet:
    """Test Conversation API endpoints"""

    def test_list_conversations(self, authenticated_client, user):
        """Test GET /api/conversations/"""
        # Create conversations
        Conversation.objects.create(user=user, conversation_type='general')
        Conversation.objects.create(user=user, conversation_type='dream_creation')

        response = authenticated_client.get('/api/conversations/')

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['results']) == 2

    def test_create_conversation(self, authenticated_client, user):
        """Test POST /api/conversations/ with general type (no dream required)."""
        data = {
            'conversation_type': 'general',
        }

        response = authenticated_client.post('/api/conversations/', data, format='json')

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['conversation_type'] == 'general'
        assert Conversation.objects.filter(user=user, conversation_type='general').exists()

    def test_create_planning_conversation_requires_dream(self, authenticated_client, user):
        """Test POST /api/conversations/ with planning type requires dream."""
        data = {
            'conversation_type': 'planning',
        }

        response = authenticated_client.post('/api/conversations/', data, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_get_conversation_detail(self, authenticated_client, conversation):
        """Test GET /api/conversations/{id}/"""
        response = authenticated_client.get(f'/api/conversations/{conversation.id}/')

        assert response.status_code == status.HTTP_200_OK
        assert response.data['id'] == str(conversation.id)

    def test_list_messages(self, authenticated_client, conversation):
        """Test GET /api/conversations/{id}/messages/"""
        # Create messages
        Message.objects.create(conversation=conversation, role='user', content='Message 1')
        Message.objects.create(conversation=conversation, role='assistant', content='Message 2')

        response = authenticated_client.get(f'/api/conversations/{conversation.id}/messages/')

        assert response.status_code == status.HTTP_200_OK
        # The messages action uses paginate_queryset, so results are paginated
        assert len(response.data['results']) == 2

    def test_send_message(self, authenticated_client, conversation, mock_openai):
        """Test POST /api/conversations/{id}/send_message/"""
        data = {
            'content': 'Hello, AI assistant!'
        }

        with patch('apps.conversations.views.OpenAIService') as mock_service, \
             patch('apps.conversations.views.validate_chat_response') as mock_validate:
            mock_validate.return_value = Mock(content='AI response', tokens_used=50)
            mock_service.return_value.chat.return_value = {'content': 'AI response'}

            response = authenticated_client.post(
                f'/api/conversations/{conversation.id}/send_message/',
                data,
                format='json'
            )

            assert response.status_code == status.HTTP_200_OK
            assert Message.objects.filter(conversation=conversation, role='user').exists()
            assert Message.objects.filter(conversation=conversation, role='assistant').exists()

    def test_cannot_access_other_user_conversation(self, db, authenticated_client, user_data):
        """Test user cannot access another user's conversation"""
        from apps.users.models import User

        other_user = User.objects.create(
            email=f'other_{user_data["email"]}'
        )
        other_conversation = Conversation.objects.create(
            user=other_user,
            conversation_type='general'
        )

        response = authenticated_client.get(f'/api/conversations/{other_conversation.id}/')
        assert response.status_code == status.HTTP_404_NOT_FOUND


# WebSocket tests are skipped because they require pytest-asyncio and channels
# test layer configuration. They also depend on the conversation fixture which
# now works correctly after the conftest fix.
@pytest.mark.skip(reason="Requires async test infrastructure (channels test layer)")
@pytest.mark.asyncio
class TestChatConsumer:
    """Test WebSocket ChatConsumer"""

    async def test_connect_authenticated(self, db, user, conversation):
        """Test WebSocket connection with authentication"""
        from channels.testing import WebsocketCommunicator
        from config.asgi import application

        communicator = WebsocketCommunicator(
            application,
            f'/ws/conversations/{conversation.id}/'
        )
        communicator.scope['user'] = user

        connected, _ = await communicator.connect()
        assert connected

        # Should receive connection confirmation
        response = await communicator.receive_json_from()
        assert response['type'] == 'connection'
        assert response['status'] == 'connected'

        await communicator.disconnect()

    async def test_connect_unauthorized(self, db, conversation):
        """Test WebSocket connection without authentication"""
        from channels.testing import WebsocketCommunicator
        from config.asgi import application
        from django.contrib.auth.models import AnonymousUser

        communicator = WebsocketCommunicator(
            application,
            f'/ws/conversations/{conversation.id}/'
        )
        communicator.scope['user'] = AnonymousUser()

        connected, close_code = await communicator.connect()

        # Should be rejected
        if connected:
            await communicator.disconnect()

        # Connection should fail or close with forbidden code
        assert close_code == 4003 or not connected

    async def test_send_message(self, db, user, conversation):
        """Test sending message via WebSocket"""
        from channels.testing import WebsocketCommunicator
        from config.asgi import application

        communicator = WebsocketCommunicator(
            application,
            f'/ws/conversations/{conversation.id}/'
        )
        communicator.scope['user'] = user

        await communicator.connect()
        await communicator.receive_json_from()  # Connection confirmation

        # Send message
        with patch('apps.conversations.consumers.OpenAIService') as mock_service:
            # Mock async streaming response
            async def mock_stream():
                for chunk in ['Hello', ' ', 'from', ' ', 'AI']:
                    yield chunk

            mock_service.return_value.chat_stream_async.return_value = mock_stream()

            await communicator.send_json_to({
                'type': 'message',
                'message': 'Hello AI'
            })

            # Should receive user message broadcast
            response1 = await communicator.receive_json_from()
            assert response1['type'] == 'message'
            assert response1['message']['role'] == 'user'

            # Should receive stream start
            response2 = await communicator.receive_json_from()
            assert response2['type'] == 'stream_start'

            # Should receive stream chunks
            chunks = []
            for _ in range(5):  # 5 chunks
                chunk_response = await communicator.receive_json_from()
                if chunk_response['type'] == 'stream_chunk':
                    chunks.append(chunk_response['chunk'])

            assert len(chunks) == 5

            # Should receive stream end
            end_response = await communicator.receive_json_from()
            assert end_response['type'] == 'stream_end'

            # Should receive complete assistant message
            final_response = await communicator.receive_json_from()
            assert final_response['type'] == 'message'
            assert final_response['message']['role'] == 'assistant'

        await communicator.disconnect()

    async def test_typing_indicator(self, db, user, conversation):
        """Test typing indicator via WebSocket"""
        from channels.testing import WebsocketCommunicator
        from config.asgi import application

        communicator = WebsocketCommunicator(
            application,
            f'/ws/conversations/{conversation.id}/'
        )
        communicator.scope['user'] = user

        await communicator.connect()
        await communicator.receive_json_from()  # Connection confirmation

        # Send typing status
        await communicator.send_json_to({
            'type': 'typing',
            'is_typing': True
        })

        # Note: We won't receive our own typing status
        # In a multi-user scenario, other users in the room would receive it

        await communicator.disconnect()

    async def test_error_handling(self, db, user, conversation):
        """Test error handling in WebSocket"""
        from channels.testing import WebsocketCommunicator
        from config.asgi import application

        communicator = WebsocketCommunicator(
            application,
            f'/ws/conversations/{conversation.id}/'
        )
        communicator.scope['user'] = user

        await communicator.connect()
        await communicator.receive_json_from()  # Connection confirmation

        # Send invalid JSON
        await communicator.send_to(text_data='invalid json')

        # Should receive error message
        response = await communicator.receive_json_from()
        assert response['type'] == 'error'

        await communicator.disconnect()

    async def test_empty_message_rejected(self, db, user, conversation):
        """Test empty message is rejected"""
        from channels.testing import WebsocketCommunicator
        from config.asgi import application

        communicator = WebsocketCommunicator(
            application,
            f'/ws/conversations/{conversation.id}/'
        )
        communicator.scope['user'] = user

        await communicator.connect()
        await communicator.receive_json_from()  # Connection confirmation

        # Send empty message
        await communicator.send_json_to({
            'type': 'message',
            'message': '   '  # Whitespace only
        })

        # Should receive error
        response = await communicator.receive_json_from()
        assert response['type'] == 'error'

        await communicator.disconnect()


class TestConversationTypes:
    """Test different conversation types"""

    def test_general_conversation(self, db, user):
        """Test general conversation type"""
        conversation = Conversation.objects.create(
            user=user,
            conversation_type='general',
        )

        assert conversation.conversation_type == 'general'

    def test_dream_creation_conversation(self, db, user):
        """Test dream creation conversation type"""
        conversation = Conversation.objects.create(
            user=user,
            conversation_type='dream_creation',
        )

        assert conversation.conversation_type == 'dream_creation'

    def test_planning_conversation(self, db, user, dream):
        """Test planning conversation type with linked dream"""
        conversation = Conversation.objects.create(
            user=user,
            conversation_type='planning',
            dream=dream,
        )

        assert conversation.conversation_type == 'planning'
        assert conversation.dream == dream

    def test_motivation_conversation(self, db, user):
        """Test motivation conversation type"""
        conversation = Conversation.objects.create(
            user=user,
            conversation_type='motivation'
        )

        assert conversation.conversation_type == 'motivation'

    def test_all_conversation_types_valid(self, db, user):
        """Test that all defined conversation types can be created"""
        valid_types = [choice[0] for choice in Conversation.TYPE_CHOICES]
        for conv_type in valid_types:
            conversation = Conversation.objects.create(
                user=user,
                conversation_type=conv_type,
            )
            assert conversation.conversation_type == conv_type
