"""
WebSocket consumers for real-time chat.

Includes per-connection rate limiting, message size limits,
and optimized database queries.
"""

import json
import time
import asyncio
from collections import deque
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from asgiref.sync import sync_to_async

from django.db.models import F
from django.utils import timezone

from .models import Conversation, Message, Call
from integrations.openai_service import OpenAIService
from core.exceptions import OpenAIError
from core.sanitizers import sanitize_text
from core.ai_usage import AIUsageTracker

# ── Rate-limiting / size constants ────────────────────────────────
MAX_MSG_SIZE = 8192           # Max WebSocket frame size in bytes
MAX_MSG_CONTENT_LEN = 5000   # Max user message content length (chars)
RATE_LIMIT_MSGS = 30         # Messages allowed per window
RATE_LIMIT_WINDOW = 60       # Window in seconds
HEARTBEAT_TIMEOUT = 90       # Close if no activity in 90s


class _RateLimitMixin:
    """Simple sliding-window rate limiter per WebSocket connection."""

    def _init_rate_limit(self):
        self._msg_timestamps = deque(maxlen=RATE_LIMIT_MSGS)

    def _is_rate_limited(self):
        now = time.monotonic()
        cutoff = now - RATE_LIMIT_WINDOW
        while self._msg_timestamps and self._msg_timestamps[0] < cutoff:
            self._msg_timestamps.popleft()
        if len(self._msg_timestamps) >= RATE_LIMIT_MSGS:
            return True
        self._msg_timestamps.append(now)
        return False


class ChatConsumer(_RateLimitMixin, AsyncWebsocketConsumer):
    """WebSocket consumer for real-time chat conversations."""

    async def connect(self):
        """Handle WebSocket connection."""
        self.conversation_id = self.scope['url_route']['kwargs']['conversation_id']
        self.room_group_name = f'conversation_{self.conversation_id}'
        self.user = self.scope['user']
        self._conversation_cache = None
        self._init_rate_limit()

        # Verify user has access — cache conversation for later use
        conversation = await self._load_and_verify_conversation()
        if not conversation:
            await self.close(code=4003)
            return

        self._conversation_cache = conversation

        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        await self.accept()

        await self.send(text_data=json.dumps({
            'type': 'connection',
            'status': 'connected',
            'conversation_id': self.conversation_id
        }))

        self._heartbeat_task = asyncio.ensure_future(self._heartbeat_loop())

    async def _heartbeat_loop(self):
        """Send periodic pings to keep the connection alive."""
        try:
            while True:
                await asyncio.sleep(45)
                await self.send(text_data=json.dumps({'type': 'ping'}))
        except asyncio.CancelledError:
            pass
        except Exception:
            pass

    async def disconnect(self, close_code):
        """Handle WebSocket disconnection."""
        if hasattr(self, '_heartbeat_task'):
            self._heartbeat_task.cancel()
        if hasattr(self, 'room_group_name'):
            await self.channel_layer.group_discard(
                self.room_group_name,
                self.channel_name
            )

    async def receive(self, text_data):
        """Receive message from WebSocket."""
        # Size guard
        if len(text_data) > MAX_MSG_SIZE:
            await self.send_error('Message too large')
            return

        # Rate limit
        if self._is_rate_limited():
            await self.send_error('Rate limit exceeded. Please slow down.')
            return

        try:
            data = json.loads(text_data)
            message_type = data.get('type', 'message')

            if message_type == 'message':
                await self.handle_message(data)
            elif message_type == 'typing':
                await self.handle_typing(data)
            elif message_type == 'ping':
                await self.send(text_data=json.dumps({'type': 'pong'}))

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

        if len(message_content) > MAX_MSG_CONTENT_LEN:
            await self.send_error(f'Message exceeds {MAX_MSG_CONTENT_LEN} character limit')
            return

        # Content moderation check BEFORE saving or calling AI
        mod_result = await self._moderate_message(message_content)
        if mod_result.is_flagged:
            await self.send(text_data=json.dumps({
                'type': 'moderation',
                'message': mod_result.user_message,
            }))
            return

        # Check AI daily quota BEFORE saving or calling AI
        allowed, info = await self._check_ai_quota()
        if not allowed:
            await self.send(text_data=json.dumps({
                'type': 'quota_exceeded',
                'message': f"Daily AI chat limit reached ({info['used']}/{info['limit']}). Resets at midnight.",
                'usage': info,
            }))
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
            # Use cached conversation, refresh for latest messages
            conversation = await self._get_conversation()
            messages = await self.get_messages_for_api(conversation)

            ai_service = OpenAIService()

            await self.send(text_data=json.dumps({
                'type': 'stream_start'
            }))

            MAX_STREAM_LEN = 10000
            chunks = []
            total_len = 0
            async for chunk in ai_service.chat_stream_async(
                messages=messages,
                conversation_type=conversation.conversation_type
            ):
                chunks.append(chunk)
                total_len += len(chunk)

                if total_len > MAX_STREAM_LEN:
                    break

                await self.send(text_data=json.dumps({
                    'type': 'stream_chunk',
                    'chunk': chunk
                }))

            full_response = ''.join(chunks)[:MAX_STREAM_LEN]

            full_response = sanitize_text(full_response)

            output_safe = await self._check_ai_output_safety(full_response)
            if not output_safe:
                full_response = (
                    "I apologize, but I need to rephrase my response. "
                    "Could you tell me more about what specific aspect of your dream you'd like help with?"
                )

            await self.send(text_data=json.dumps({
                'type': 'stream_end'
            }))

            await self._increment_ai_quota()

            assistant_message = await self.save_message('assistant', full_response)

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

    # ── Database methods (N+1 optimized) ──────────────────────────

    @database_sync_to_async
    def _load_and_verify_conversation(self):
        """Load conversation with select_related and verify access — single query."""
        try:
            conversation = Conversation.objects.select_related(
                'user', 'dream'
            ).get(id=self.conversation_id)
            if conversation.user_id != self.user.id:
                return None
            return conversation
        except Conversation.DoesNotExist:
            return None

    @database_sync_to_async
    def _get_conversation(self):
        """Return cached conversation or refresh with select_related."""
        if self._conversation_cache:
            return self._conversation_cache
        return Conversation.objects.select_related('user', 'dream').get(
            id=self.conversation_id
        )

    @database_sync_to_async
    def get_messages_for_api(self, conversation):
        """Get recent messages for API."""
        return conversation.get_messages_for_api(limit=20)

    @database_sync_to_async
    def _moderate_message(self, content):
        """Run content moderation on a message."""
        from core.moderation import ContentModerationService
        return ContentModerationService().moderate_text(content, context='chat')

    @database_sync_to_async
    def _check_ai_output_safety(self, content):
        """Check if AI output is safe."""
        from core.ai_validators import validate_ai_output_safety
        is_safe, _ = validate_ai_output_safety(content)
        return is_safe

    @database_sync_to_async
    def save_message(self, role, content):
        """Save message to database using F() expression to avoid reloading conversation."""
        message = Message.objects.create(
            conversation_id=self.conversation_id, role=role, content=content
        )
        Conversation.objects.filter(id=self.conversation_id).update(
            total_messages=F('total_messages') + 1,
            updated_at=timezone.now(),
        )
        return message

    @database_sync_to_async
    def _check_ai_quota(self):
        """Check if user has remaining AI chat quota."""
        tracker = AIUsageTracker()
        return tracker.check_quota(self.user, 'ai_chat')

    @database_sync_to_async
    def _increment_ai_quota(self):
        """Increment AI chat usage counter."""
        tracker = AIUsageTracker()
        return tracker.increment(self.user, 'ai_chat')


class BuddyChatConsumer(_RateLimitMixin, AsyncWebsocketConsumer):
    """WebSocket consumer for buddy-to-buddy real-time chat (no AI response)."""

    async def connect(self):
        """Handle WebSocket connection."""
        self.conversation_id = self.scope['url_route']['kwargs']['conversation_id']
        self.room_group_name = f'buddy_chat_{self.conversation_id}'
        self.user = self.scope['user']
        self._init_rate_limit()

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

        self._heartbeat_task = asyncio.ensure_future(self._heartbeat_loop())

    async def _heartbeat_loop(self):
        """Send periodic pings to keep the connection alive."""
        try:
            while True:
                await asyncio.sleep(45)
                await self.send(text_data=json.dumps({'type': 'ping'}))
        except asyncio.CancelledError:
            pass
        except Exception:
            pass

    async def disconnect(self, close_code):
        """Handle WebSocket disconnection."""
        if hasattr(self, '_heartbeat_task'):
            self._heartbeat_task.cancel()
        if hasattr(self, 'room_group_name'):
            await self.channel_layer.group_discard(
                self.room_group_name,
                self.channel_name
            )

    async def receive(self, text_data):
        """Receive message from WebSocket."""
        # Size guard
        if len(text_data) > MAX_MSG_SIZE:
            await self.send_error('Message too large')
            return

        # Rate limit
        if self._is_rate_limited():
            await self.send_error('Rate limit exceeded. Please slow down.')
            return

        try:
            data = json.loads(text_data)
            message_type = data.get('type', 'message')

            if message_type == 'message':
                await self.handle_buddy_message(data)
            elif message_type == 'typing':
                await self.handle_typing(data)
            elif message_type == 'ping':
                await self.send(text_data=json.dumps({'type': 'pong'}))

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

        if len(content) > MAX_MSG_CONTENT_LEN:
            await self.send_error(f'Message exceeds {MAX_MSG_CONTENT_LEN} character limit')
            return

        # Content moderation for buddy messages
        mod_result = await self._moderate_buddy_message(content)
        if mod_result.is_flagged:
            await self.send(text_data=json.dumps({
                'type': 'moderation',
                'message': mod_result.user_message,
            }))
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
            conversation = Conversation.objects.select_related(
                'buddy_pairing', 'buddy_pairing__user1', 'buddy_pairing__user2'
            ).get(
                id=self.conversation_id,
                conversation_type='buddy_chat',
            )
            if not conversation.buddy_pairing:
                return False
            pairing = conversation.buddy_pairing
            return self.user.id in (pairing.user1_id, pairing.user2_id)
        except Conversation.DoesNotExist:
            return False

    @database_sync_to_async
    def _moderate_buddy_message(self, content):
        """Run content moderation on a buddy message."""
        from core.moderation import ContentModerationService
        return ContentModerationService().moderate_text(content, context='chat')

    @database_sync_to_async
    def save_buddy_message(self, content):
        """Save a buddy chat message using F() expression to avoid reloading conversation."""
        message = Message.objects.create(
            conversation_id=self.conversation_id,
            role='user',
            content=content,
            metadata={'sender_id': str(self.user.id)},
        )
        Conversation.objects.filter(id=self.conversation_id).update(
            total_messages=F('total_messages') + 1,
            updated_at=timezone.now(),
        )
        return message

    @database_sync_to_async
    def get_display_name(self):
        """Return display name of the connected user."""
        return self.user.display_name or self.user.email


class CallSignalingConsumer(_RateLimitMixin, AsyncWebsocketConsumer):
    """
    WebSocket consumer for WebRTC call signaling.

    Relays SDP offers/answers and ICE candidates between caller and callee.
    Endpoint: ws/call/<call_id>/
    """

    async def connect(self):
        self.call_id = self.scope['url_route']['kwargs']['call_id']
        self.room_group_name = f'call_{self.call_id}'
        self.user = self.scope['user']
        self._init_rate_limit()

        # Verify user is caller or callee
        has_access = await self.check_call_access()
        if not has_access:
            await self.close(code=4003)
            return

        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        await self.accept()

        # Build ICE servers list (STUN + optional TURN)
        ice_servers = [
            {'urls': 'stun:stun.l.google.com:19302'},
            {'urls': 'stun:stun1.l.google.com:19302'},
        ]
        from django.conf import settings
        if getattr(settings, 'TURN_SERVER_URL', ''):
            ice_servers.append({
                'urls': settings.TURN_SERVER_URL,
                'username': getattr(settings, 'TURN_SERVER_USERNAME', ''),
                'credential': getattr(settings, 'TURN_SERVER_CREDENTIAL', ''),
            })

        await self.send(text_data=json.dumps({
            'type': 'connection',
            'status': 'connected',
            'callId': self.call_id,
            'userId': str(self.user.id),
            'iceServers': ice_servers,
        }))

    async def disconnect(self, close_code):
        if hasattr(self, 'room_group_name'):
            await self.channel_layer.group_discard(
                self.room_group_name,
                self.channel_name
            )

    async def receive(self, text_data):
        # Size guard — signaling messages should be small (< 64KB)
        if len(text_data) > 65536:
            await self.send(text_data=json.dumps({
                'type': 'error', 'error': 'Message too large',
            }))
            return

        # Rate limit
        if self._is_rate_limited():
            return

        try:
            data = json.loads(text_data)
            msg_type = data.get('type', '')

            if msg_type in ('offer', 'answer', 'ice_candidate', 'call_end'):
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        'type': 'relay_signal',
                        'sender_channel': self.channel_name,
                        'payload': data,
                    }
                )
            elif msg_type == 'ping':
                await self.send(text_data=json.dumps({'type': 'pong'}))

        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({
                'type': 'error', 'error': 'Invalid JSON',
            }))

    async def relay_signal(self, event):
        """Forward signaling data to the other peer (skip sender)."""
        if event['sender_channel'] != self.channel_name:
            await self.send(text_data=json.dumps(event['payload']))

    @database_sync_to_async
    def check_call_access(self):
        """Verify user is caller or callee of this call."""
        try:
            call = Call.objects.select_related('caller', 'callee').get(id=self.call_id)
            return self.user.id in (call.caller_id, call.callee_id)
        except Call.DoesNotExist:
            return False
