"""
WebSocket consumer for real-time notification delivery.
"""

import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async


class NotificationConsumer(AsyncWebsocketConsumer):
    """WebSocket consumer for real-time notifications."""

    async def connect(self):
        """Handle WebSocket connection."""
        self.user = self.scope['user']

        if not self.user.is_authenticated:
            await self.close(code=4003)
            return

        self.group_name = f'notifications_{self.user.id}'

        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )

        await self.accept()

        # Send connection confirmation with unread count
        unread = await self.get_unread_count()
        await self.send(text_data=json.dumps({
            'type': 'connection',
            'status': 'connected',
            'unread_count': unread,
        }))

    async def disconnect(self, close_code):
        """Handle WebSocket disconnection."""
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(
                self.group_name,
                self.channel_name
            )

    async def receive(self, text_data):
        """Handle incoming messages (mark_read, mark_all_read)."""
        try:
            data = json.loads(text_data)
            action = data.get('type')

            if action == 'mark_read':
                notification_id = data.get('notification_id')
                if notification_id:
                    await self.mark_notification_read(notification_id)
                    await self.send(text_data=json.dumps({
                        'type': 'marked_read',
                        'notification_id': notification_id,
                    }))

            elif action == 'mark_all_read':
                count = await self.mark_all_read()
                await self.send(text_data=json.dumps({
                    'type': 'all_marked_read',
                    'count': count,
                }))

        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'error': 'Invalid JSON',
            }))

    async def send_notification(self, event):
        """Handler for channel layer group_send — pushes notification to client."""
        await self.send(text_data=json.dumps({
            'type': 'notification',
            'notification': event['notification'],
        }))

    async def unread_count_update(self, event):
        """Handler to push updated unread count."""
        await self.send(text_data=json.dumps({
            'type': 'unread_count',
            'count': event['count'],
        }))

    @database_sync_to_async
    def get_unread_count(self):
        from .models import Notification
        return Notification.objects.filter(
            user=self.user,
            status='sent',
            read_at__isnull=True,
        ).count()

    @database_sync_to_async
    def mark_notification_read(self, notification_id):
        from .models import Notification
        try:
            notification = Notification.objects.get(
                id=notification_id,
                user=self.user,
            )
            notification.mark_read()
        except Notification.DoesNotExist:
            pass

    @database_sync_to_async
    def mark_all_read(self):
        from .models import Notification
        from django.utils import timezone
        return Notification.objects.filter(
            user=self.user,
            read_at__isnull=True,
        ).update(read_at=timezone.now())
