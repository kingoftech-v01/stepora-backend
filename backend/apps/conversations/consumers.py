"""
WebSocket consumers for real-time chat.
"""

import json
import asyncio
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from asgiref.sync import sync_to_async

from .models import Conversation, Message
from integrations.openai_service import OpenAIService
from core.exceptions import OpenAIError


class ChatConsumer(AsyncWebsocketConsumer):
    """WebSocket consumer for real-time chat conversations."""

    async def connect(self):
        """Handle WebSocket connection."""
        self.conversation_id = self.scope['url_route']['kwargs']['conversation_id']
        self.room_group_name = f'conversation_{self.conversation_id}'
        self.user = self.scope['user']

        # Verify user has access to conversation
        has_access = await self.check_conversation_access()
        if not has_access:
            await self.close(code=4003)  # Forbidden
            return

        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        await self.accept()

        # Send connection confirmation
        await self.send(text_data=json.dumps({
            'type': 'connection',
            'status': 'connected',
            'conversation_id': self.conversation_id
        }))

    async def disconnect(self, close_code):
        """Handle WebSocket disconnection."""
        # Leave room group
        if hasattr(self, 'room_group_name'):
            await self.channel_layer.group_discard(
                self.room_group_name,
                self.channel_name
            )

    async def receive(self, text_data):
        """Receive message from WebSocket."""
        try:
            data = json.loads(text_data)
            message_type = data.get('type', 'message')

            if message_type == 'message':
                await self.handle_message(data)
            elif message_type == 'typing':
                await self.handle_typing(data)

        except json.JSONDecodeError:
            await self.send_error('Invalid JSON')
        except Exception as e:
            await self.send_error(f'Error: {str(e)}')

    async def handle_message(self, data):
        """Handle incoming chat message."""
        message_content = data.get('message', '').strip()

        if not message_content:
            await self.send_error('Message cannot be empty')
            return

        # Save user message
        user_message = await self.save_message('user', message_content)

        # Broadcast user message to room
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'chat_message',
                'message': {
                    'id': str(user_message.id),
                    'role': 'user',
                    'content': message_content,
                    'created_at': user_message.created_at.isoformat()
                }
            }
        )

        # Get AI response with streaming
        await self.get_ai_response_stream(message_content)

    async def handle_typing(self, data):
        """Handle typing indicator."""
        is_typing = data.get('is_typing', False)

        # Broadcast typing status to room
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'typing_status',
                'user_id': str(self.user.id),
                'is_typing': is_typing
            }
        )

    async def get_ai_response_stream(self, user_message):
        """Get AI response with streaming."""
        try:
            # Get conversation and messages
            conversation = await self.get_conversation()
            messages = await self.get_messages_for_api(conversation)

            # Initialize AI service
            ai_service = OpenAIService()

            # Send streaming start indicator
            await self.send(text_data=json.dumps({
                'type': 'stream_start'
            }))

            # Stream AI response
            full_response = ""
            async for chunk in ai_service.chat_stream_async(
                messages=messages,
                conversation_type=conversation.conversation_type
            ):
                full_response += chunk

                # Send chunk to client
                await self.send(text_data=json.dumps({
                    'type': 'stream_chunk',
                    'chunk': chunk
                }))

            # Send streaming end indicator
            await self.send(text_data=json.dumps({
                'type': 'stream_end'
            }))

            # Save complete AI response
            assistant_message = await self.save_message('assistant', full_response)

            # Broadcast complete message to room
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'chat_message',
                    'message': {
                        'id': str(assistant_message.id),
                        'role': 'assistant',
                        'content': full_response,
                        'created_at': assistant_message.created_at.isoformat()
                    }
                }
            )

        except OpenAIError as e:
            await self.send_error(f'AI Error: {str(e)}')
        except Exception as e:
            await self.send_error(f'Unexpected error: {str(e)}')

    async def chat_message(self, event):
        """Send message to WebSocket."""
        await self.send(text_data=json.dumps({
            'type': 'message',
            'message': event['message']
        }))

    async def typing_status(self, event):
        """Send typing status to WebSocket."""
        # Don't send typing status to the user who is typing
        if str(event['user_id']) != str(self.user.id):
            await self.send(text_data=json.dumps({
                'type': 'typing',
                'user_id': event['user_id'],
                'is_typing': event['is_typing']
            }))

    async def send_error(self, error_message):
        """Send error message to client."""
        await self.send(text_data=json.dumps({
            'type': 'error',
            'error': error_message
        }))

    @database_sync_to_async
    def check_conversation_access(self):
        """Check if user has access to conversation."""
        try:
            conversation = Conversation.objects.get(id=self.conversation_id)
            return conversation.user == self.user
        except Conversation.DoesNotExist:
            return False

    @database_sync_to_async
    def get_conversation(self):
        """Get conversation object."""
        return Conversation.objects.get(id=self.conversation_id)

    @database_sync_to_async
    def get_messages_for_api(self, conversation):
        """Get recent messages for API."""
        return conversation.get_messages_for_api(limit=20)

    @database_sync_to_async
    def save_message(self, role, content):
        """Save message to database."""
        conversation = Conversation.objects.get(id=self.conversation_id)
        return conversation.add_message(role, content)


class BuddyChatConsumer(AsyncWebsocketConsumer):
    """WebSocket consumer for buddy-to-buddy real-time chat (no AI response)."""

    async def connect(self):
        """Handle WebSocket connection."""
        self.conversation_id = self.scope['url_route']['kwargs']['conversation_id']
        self.room_group_name = f'buddy_chat_{self.conversation_id}'
        self.user = self.scope['user']

        # Verify user is part of this buddy conversation
        has_access = await self.check_buddy_access()
        if not has_access:
            await self.close(code=4003)
            return

        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        await self.accept()

        await self.send(text_data=json.dumps({
            'type': 'connection',
            'status': 'connected',
            'conversation_id': self.conversation_id,
            'user_id': str(self.user.id),
            'display_name': await self.get_display_name(),
        }))

    async def disconnect(self, close_code):
        """Handle WebSocket disconnection."""
        if hasattr(self, 'room_group_name'):
            await self.channel_layer.group_discard(
                self.room_group_name,
                self.channel_name
            )

    async def receive(self, text_data):
        """Receive message from WebSocket."""
        try:
            data = json.loads(text_data)
            message_type = data.get('type', 'message')

            if message_type == 'message':
                await self.handle_buddy_message(data)
            elif message_type == 'typing':
                await self.handle_typing(data)

        except json.JSONDecodeError:
            await self.send_error('Invalid JSON')
        except Exception as e:
            await self.send_error(f'Error: {str(e)}')

    async def handle_buddy_message(self, data):
        """Handle incoming buddy chat message — no AI response."""
        content = data.get('message', '').strip()
        if not content:
            await self.send_error('Message cannot be empty')
            return

        message = await self.save_buddy_message(content)

        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'chat_message',
                'message': {
                    'id': str(message.id),
                    'role': 'user',
                    'content': content,
                    'sender_id': str(self.user.id),
                    'sender_name': await self.get_display_name(),
                    'created_at': message.created_at.isoformat(),
                }
            }
        )

    async def handle_typing(self, data):
        """Handle typing indicator."""
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'typing_status',
                'user_id': str(self.user.id),
                'is_typing': data.get('is_typing', False),
            }
        )

    async def chat_message(self, event):
        """Send message to WebSocket."""
        await self.send(text_data=json.dumps({
            'type': 'message',
            'message': event['message'],
        }))

    async def typing_status(self, event):
        """Send typing status to WebSocket (exclude self)."""
        if str(event['user_id']) != str(self.user.id):
            await self.send(text_data=json.dumps({
                'type': 'typing',
                'user_id': event['user_id'],
                'is_typing': event['is_typing'],
            }))

    async def send_error(self, error_message):
        """Send error message to client."""
        await self.send(text_data=json.dumps({
            'type': 'error',
            'error': error_message,
        }))

    @database_sync_to_async
    def check_buddy_access(self):
        """Check that user is part of this buddy conversation."""
        try:
            conversation = Conversation.objects.select_related('buddy_pairing').get(
                id=self.conversation_id,
                conversation_type='buddy_chat',
            )
            if not conversation.buddy_pairing:
                return False
            pairing = conversation.buddy_pairing
            return self.user in (pairing.user1, pairing.user2)
        except Conversation.DoesNotExist:
            return False

    @database_sync_to_async
    def save_buddy_message(self, content):
        """Save a buddy chat message."""
        conversation = Conversation.objects.get(id=self.conversation_id)
        return conversation.add_message(
            'user',
            content,
            metadata={'sender_id': str(self.user.id)},
        )

    @database_sync_to_async
    def get_display_name(self):
        """Return display name of the connected user."""
        return self.user.display_name or self.user.email
