"""
WebSocket consumer for buddy-to-buddy chat.

Uses Django Channels for reliable message persistence instead of Agora RTM.
Messages are saved to Conversation/Message models (conversation_type='buddy_chat').
"""

import json
import logging

from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async

from django.db.models import F, Q
from django.utils import timezone

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


class BuddyChatConsumer(
    RateLimitMixin,
    AuthenticatedConsumerMixin,
    BlockingMixin,
    ModerationMixin,
    AsyncWebsocketConsumer,
):
    """
    WebSocket consumer for buddy-to-buddy messaging.

    URL: ws/buddy-chat/<pairing_id>/
    Group name: buddy_chat_{pairing_id}
    Rate limit: 30 msgs / 60s
    """

    rate_limit_msgs = 30
    rate_limit_window = 60

    async def connect(self):
        self.pairing_id = self.scope['url_route']['kwargs']['pairing_id']
        self.room_group_name = f'buddy_chat_{self.pairing_id}'
        self._pairing_cache = None
        self._conversation_cache = None
        self._partner = None
        self._init_rate_limit()
        await self._init_auth()

        if self.user.is_authenticated:
            await self._setup_authenticated()
        elif self.scope.get('_allow_post_auth'):
            await self.accept()
        else:
            await self.close(code=4003)

    async def _setup_authenticated_inner(self):
        """Verify buddy pairing, check blocks, join group."""
        pairing = await self._load_and_verify_pairing()
        if not pairing:
            await self.send_error('Invalid pairing or not a participant')
            await self.close(code=4003)
            return

        self._pairing_cache = pairing

        # Determine partner
        self._partner = await self._get_partner(pairing)

        # Block check
        if await self._is_blocked(self.user, self._partner):
            await self.send_error('Cannot chat with this user')
            await self.close(code=4003)
            return

        # Find or create the buddy_chat conversation
        self._conversation_cache = await self._get_or_create_conversation(pairing)

        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name,
        )

        await self.send(text_data=json.dumps({
            'type': 'connection',
            'status': 'connected',
            'pairing_id': self.pairing_id,
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
            elif message_type == 'mark_read':
                await self._handle_mark_read()
            elif message_type == 'ping':
                await self.send(text_data=json.dumps({'type': 'pong'}))

        except json.JSONDecodeError:
            await self.send_error('Invalid JSON')
        except Exception:
            logger.exception("BuddyChatConsumer error")
            await self.send_error('An unexpected error occurred')

    async def _handle_chat_message(self, data):
        """Validate, moderate, save, broadcast, and push-notify."""
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

        # Re-check block before each send
        if await self._is_blocked(self.user, self._partner):
            await self.send_error('Cannot send messages to this user')
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
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'chat_message',
                'message': {
                    'id': str(message.id),
                    'sender_id': str(self.user.id),
                    'content': content,
                    'created_at': message.created_at.isoformat(),
                },
            },
        )

        # Push notification to partner
        await self._send_push_notification(content)

    async def _handle_typing(self, data):
        is_typing = data.get('is_typing', False)
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'typing_status',
                'user_id': str(self.user.id),
                'is_typing': is_typing,
            },
        )

    async def _handle_mark_read(self):
        await self._mark_conversation_read()
        await self.send(text_data=json.dumps({
            'type': 'marked_read',
            'pairing_id': self.pairing_id,
        }))

    # ── Channel layer handlers ────────────────────────────────────────

    async def chat_message(self, event):
        await self.send(text_data=json.dumps({
            'type': 'message',
            'message': event['message'],
        }))

    async def typing_status(self, event):
        if str(event['user_id']) != str(self.user.id):
            await self.send(text_data=json.dumps({
                'type': 'typing',
                'user_id': event['user_id'],
                'is_typing': event['is_typing'],
            }))

    async def call_started(self, event):
        """Notify about an incoming buddy call."""
        await self.send(text_data=json.dumps({
            'type': 'call_started',
            'call': event['call'],
        }))

    # ── Database methods ──────────────────────────────────────────────

    @database_sync_to_async
    def _load_and_verify_pairing(self):
        from apps.buddies.models import BuddyPairing
        try:
            pairing = BuddyPairing.objects.select_related(
                'user1', 'user2'
            ).get(id=self.pairing_id, status='active')
            if self.user not in (pairing.user1, pairing.user2):
                return None
            return pairing
        except BuddyPairing.DoesNotExist:
            return None

    @database_sync_to_async
    def _get_partner(self, pairing):
        return pairing.user2 if pairing.user1_id == self.user.id else pairing.user1

    @database_sync_to_async
    def _get_or_create_conversation(self, pairing):
        from apps.conversations.models import Conversation
        conversation = Conversation.objects.filter(
            conversation_type='buddy_chat',
            buddy_pairing=pairing,
        ).first()
        if not conversation:
            conversation = Conversation.objects.create(
                user=pairing.user1,
                conversation_type='buddy_chat',
                buddy_pairing=pairing,
                title=f'Buddy Chat',
            )
        return conversation

    @database_sync_to_async
    def _save_message(self, content):
        from apps.conversations.models import Conversation, Message
        message = Message.objects.create(
            conversation=self._conversation_cache,
            role='user',
            content=content,
            metadata={'sender_id': str(self.user.id)},
        )
        Conversation.objects.filter(id=self._conversation_cache.id).update(
            total_messages=F('total_messages') + 1,
            updated_at=timezone.now(),
        )
        return message

    @database_sync_to_async
    def _mark_conversation_read(self):
        from apps.conversations.models import MessageReadStatus, Message
        last_msg = Message.objects.filter(
            conversation=self._conversation_cache
        ).order_by('-created_at').first()
        if last_msg:
            MessageReadStatus.objects.update_or_create(
                user=self.user,
                conversation=self._conversation_cache,
                defaults={'last_read_message': last_msg},
            )

    @database_sync_to_async
    def _send_push_notification(self, content):
        """Send FCM push to partner if they're not connected."""
        try:
            from apps.notifications.fcm_service import FCMService
            from apps.notifications.models import UserDevice

            devices = UserDevice.objects.filter(
                user=self._partner, is_active=True
            )
            tokens = [d.fcm_token for d in devices if d.fcm_token]
            if not tokens:
                return

            sender_name = self.user.display_name or self.user.username or 'Your buddy'
            preview = content[:100] + '...' if len(content) > 100 else content

            fcm = FCMService()
            for token in tokens:
                try:
                    fcm.send_to_token(
                        token=token,
                        title=f'Message from {sender_name}',
                        body=preview,
                        data={
                            'type': 'buddy_message',
                            'pairing_id': self.pairing_id,
                            'sender_id': str(self.user.id),
                        },
                    )
                except Exception:
                    logger.debug("FCM send failed", exc_info=True)
        except Exception:
            logger.debug("Push notification failed", exc_info=True)
