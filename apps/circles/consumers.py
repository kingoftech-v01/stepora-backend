"""
WebSocket consumer for circle group chat.

Messages are persisted to CircleMessage model.
Block filtering: messages from blocked senders are silently dropped.
"""

import json
import logging

from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async

from core.consumers import (
    RateLimitMixin,
    AuthenticatedConsumerMixin,
    BlockingMixin,
    ModerationMixin,
    MAX_MSG_SIZE,
    MAX_MSG_CONTENT_LEN,
)
from core.sanitizers import sanitize_text

logger = logging.getLogger(__name__)


class CircleChatConsumer(
    RateLimitMixin,
    AuthenticatedConsumerMixin,
    BlockingMixin,
    ModerationMixin,
    AsyncWebsocketConsumer,
):
    """
    WebSocket consumer for circle group messaging.

    URL: ws/circle-chat/<circle_id>/
    Group name: circle_chat_{circle_id}
    Rate limit: 20 msgs / 60s (lower for group chat)
    """

    rate_limit_msgs = 20
    rate_limit_window = 60

    async def connect(self):
        self.circle_id = self.scope['url_route']['kwargs']['circle_id']
        self.room_group_name = f'circle_chat_{self.circle_id}'
        self._circle_cache = None
        self._blocked_user_ids = set()
        self._init_rate_limit()
        await self._init_auth()

        if self.user.is_authenticated:
            await self._setup_authenticated()
        elif self.scope.get('_allow_post_auth'):
            await self.accept()
        else:
            await self.close(code=4003)

    async def _setup_authenticated_inner(self):
        """Verify membership and join group."""
        is_member = await self._verify_membership()
        if not is_member:
            await self.send_error('You must be a member of this circle')
            await self.close(code=4003)
            return

        # Load blocked user IDs for filtering incoming group messages
        self._blocked_user_ids = await self._get_blocked_user_ids()

        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name,
        )

        await self.send(text_data=json.dumps({
            'type': 'connection',
            'status': 'connected',
            'circle_id': self.circle_id,
        }))

    async def disconnect(self, close_code):
        await self._cancel_heartbeat()
        if hasattr(self, 'room_group_name'):
            await self.channel_layer.group_discard(
                self.room_group_name,
                self.channel_name,
            )

    async def receive(self, text_data):
        if len(text_data) > MAX_MSG_SIZE:
            await self.send_error('Message too large')
            return

        try:
            data = json.loads(text_data)
            message_type = data.get('type', 'message')

            if message_type == 'authenticate':
                await self._handle_authenticate_message(data)
                return

            if not self._authenticated:
                await self.send_error(
                    'Not authenticated. Send {"type": "authenticate", "token": "..."} first.'
                )
                return

            if message_type == 'message':
                await self._handle_chat_message(data)
            elif message_type == 'typing':
                await self._handle_typing(data)
            elif message_type == 'ping':
                await self.send(text_data=json.dumps({'type': 'pong'}))

        except json.JSONDecodeError:
            await self.send_error('Invalid JSON')
        except Exception as e:
            logger.exception("CircleChatConsumer error")
            await self.send_error(f'Error: {str(e)}')

    async def _handle_chat_message(self, data):
        content = data.get('message', '').strip()

        if not content:
            await self.send_error('Message cannot be empty')
            return

        if len(content) > MAX_MSG_CONTENT_LEN:
            await self.send_error(
                f'Message exceeds {MAX_MSG_CONTENT_LEN} character limit'
            )
            return

        if self._is_rate_limited():
            await self.send_error('Rate limit exceeded. Please slow down.')
            return

        # Moderate
        mod_result = await self._moderate_content(content)
        if mod_result.is_flagged:
            await self.send(text_data=json.dumps({
                'type': 'moderation',
                'message': mod_result.user_message,
            }))
            return

        # Sanitize
        content = sanitize_text(content)

        # Save message
        message = await self._save_message(content)

        # Broadcast to group
        sender_name = self.user.display_name or 'Anonymous'
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'circle_message',
                'message': {
                    'id': str(message.id),
                    'sender_id': str(self.user.id),
                    'sender_name': sender_name,
                    'sender_avatar': self.user.avatar_url or '',
                    'content': content,
                    'created_at': message.created_at.isoformat(),
                },
            },
        )

    async def _handle_typing(self, data):
        is_typing = data.get('is_typing', False)
        sender_name = self.user.display_name or 'Anonymous'
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'typing_status',
                'user_id': str(self.user.id),
                'user_name': sender_name,
                'is_typing': is_typing,
            },
        )

    # ── Channel layer handlers ────────────────────────────────────────

    async def circle_message(self, event):
        """Handle incoming circle message — filter blocked senders."""
        sender_id = event['message'].get('sender_id', '')
        if sender_id in self._blocked_user_ids:
            return  # Silently drop
        await self.send(text_data=json.dumps({
            'type': 'message',
            'message': event['message'],
        }))

    async def typing_status(self, event):
        if str(event['user_id']) != str(self.user.id):
            sender_id = event.get('user_id', '')
            if sender_id in self._blocked_user_ids:
                return
            await self.send(text_data=json.dumps({
                'type': 'typing',
                'user_id': event['user_id'],
                'user_name': event.get('user_name', ''),
                'is_typing': event['is_typing'],
            }))

    async def call_started(self, event):
        """Notify about a circle call starting."""
        await self.send(text_data=json.dumps({
            'type': 'call_started',
            'call': event['call'],
        }))

    # ── Database methods ──────────────────────────────────────────────

    @database_sync_to_async
    def _verify_membership(self):
        from .models import CircleMembership
        return CircleMembership.objects.filter(
            circle_id=self.circle_id, user=self.user
        ).exists()

    @database_sync_to_async
    def _get_blocked_user_ids(self):
        """Get set of user ID strings that the current user has blocked or is blocked by."""
        from apps.social.models import BlockedUser
        from django.db.models import Q
        blocked_qs = BlockedUser.objects.filter(
            Q(blocker=self.user) | Q(blocked=self.user)
        ).values_list('blocker_id', 'blocked_id')
        ids = set()
        for blocker_id, blocked_id in blocked_qs:
            if blocker_id != self.user.id:
                ids.add(str(blocker_id))
            if blocked_id != self.user.id:
                ids.add(str(blocked_id))
        return ids

    @database_sync_to_async
    def _save_message(self, content):
        from .models import CircleMessage
        return CircleMessage.objects.create(
            circle_id=self.circle_id,
            sender=self.user,
            content=content,
        )
