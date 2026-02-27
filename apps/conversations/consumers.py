"""
WebSocket consumers for real-time chat.

Includes per-connection rate limiting, message size limits,
and optimized database queries.
"""

import json
import logging
import time
import asyncio
from collections import deque
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from asgiref.sync import sync_to_async

from django.db.models import F
from django.utils import timezone

from .models import Conversation, Message
from integrations.openai_service import OpenAIService
from core.exceptions import OpenAIError
from core.sanitizers import sanitize_text
from core.ai_usage import AIUsageTracker

logger = logging.getLogger(__name__)

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
        self._authenticated = False
        self._init_rate_limit()

        if self.user.is_authenticated:
            await self._setup_authenticated()
        elif self.scope.get('_allow_post_auth'):
            await self.accept()
        else:
            await self.close(code=4003)
            return

    async def _setup_authenticated(self):
        """Verify access and join room after authentication."""
        self._authenticated = True

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

        if self.scope.get('_allow_post_auth'):
            pass  # Already accepted
        else:
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
            logger.debug("Cleanup error during disconnect", exc_info=True)

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

        try:
            data = json.loads(text_data)
            message_type = data.get('type', 'message')

            # Post-connect authentication via message (preferred over query string)
            if message_type == 'authenticate':
                if self._authenticated:
                    return
                from core.websocket_auth import get_user_from_token
                user = await get_user_from_token(data.get('token', ''))
                if user.is_authenticated:
                    self.user = user
                    self.scope['user'] = user
                    await self._setup_authenticated()
                else:
                    await self.send_error('Invalid token')
                    await self.close(code=4001)
                return

            # Reject non-auth messages if not yet authenticated
            if not self._authenticated:
                await self.send_error('Not authenticated. Send {"type": "authenticate", "token": "..."} first.')
                return

            # Rate limit
            if self._is_rate_limited():
                await self.send_error('Rate limit exceeded. Please slow down.')
                return

            if message_type == 'message':
                await self.handle_message(data)
            elif message_type == 'function_call':
                await self.handle_explicit_function_call(data)
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

    async def handle_function_call(self, function_call, conversation):
        """Execute an AI function call and return the result."""
        from apps.dreams.models import Dream, Goal, Task

        name = function_call['name']
        args = function_call['arguments']
        user = self.scope['user']

        if name == 'create_task':
            # Find the active dream's first in-progress (or pending) goal
            goal = await database_sync_to_async(
                lambda: Goal.objects.filter(
                    dream__user=user, dream__status='active'
                ).exclude(status='completed').order_by('order').first()
            )()
            if not goal:
                return {'success': False, 'error': 'No active goal found'}
            next_order = await database_sync_to_async(goal.tasks.count)()
            task = await database_sync_to_async(
                lambda: Task.objects.create(
                    goal=goal,
                    title=args['title'],
                    description=args.get('description', ''),
                    duration_mins=args.get('duration_mins', 30),
                    order=next_order,
                )
            )()
            return {'success': True, 'task_id': str(task.id), 'title': task.title}

        elif name == 'complete_task':
            task = await database_sync_to_async(
                lambda: Task.objects.select_related('goal__dream__user').filter(
                    id=args['task_id'], goal__dream__user=user
                ).first()
            )()
            if not task:
                return {'success': False, 'error': 'Task not found'}
            # Use the model's complete() method for proper XP, streak, and progress updates
            await database_sync_to_async(task.complete)()
            return {'success': True, 'task_id': str(task.id)}

        elif name == 'create_goal':
            dream = await database_sync_to_async(
                lambda: Dream.objects.filter(id=args['dream_id'], user=user).first()
            )()
            if not dream:
                return {'success': False, 'error': 'Dream not found'}
            next_order = await database_sync_to_async(dream.goals.count)()
            goal = await database_sync_to_async(
                lambda: Goal.objects.create(
                    dream=dream,
                    title=args['title'],
                    description=args.get('description', ''),
                    order=args.get('order', next_order),
                )
            )()
            return {'success': True, 'goal_id': str(goal.id), 'title': goal.title}

        return {'success': False, 'error': f'Unknown function: {name}'}

    async def handle_explicit_function_call(self, data):
        """Handle explicit function call request from frontend."""
        conversation = await self._get_conversation()
        messages = await self.get_messages_for_api(conversation)

        ai_service = OpenAIService()

        # Add user instruction to trigger function calling
        instruction = data.get(
            'instruction',
            'Based on our conversation, please take the appropriate action.',
        )
        messages.append({'role': 'user', 'content': instruction})

        try:
            result = await database_sync_to_async(ai_service.chat)(
                messages=messages,
                conversation_type=conversation.conversation_type,
                functions=OpenAIService.FUNCTION_DEFINITIONS,
            )

            if result.get('function_call'):
                fc_result = await self.handle_function_call(
                    result['function_call'], conversation
                )

                await self.send(text_data=json.dumps({
                    'type': 'function_result',
                    'function_name': result['function_call']['name'],
                    'result': fc_result,
                    'ai_message': result.get('content', ''),
                }))

                # Save the AI message if there is one
                if result.get('content'):
                    await self.save_message('assistant', result['content'])
            else:
                # AI chose not to call a function, just send text
                if result.get('content'):
                    await self.save_message('assistant', result['content'])
                    await self.send(text_data=json.dumps({
                        'type': 'chat_message',
                        'message': {
                            'role': 'assistant',
                            'content': result['content'],
                        }
                    }))

        except Exception:
            logger.exception("Function call failed")
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Failed to process action request',
            }))

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


