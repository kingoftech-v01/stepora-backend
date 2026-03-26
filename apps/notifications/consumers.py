"""
WebSocket consumer for real-time notification delivery.
"""

import asyncio
import json
import logging
import time

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.core.cache import cache
from django.utils import timezone

from core.consumers import MAX_USER_WS_CONNECTIONS

logger = logging.getLogger(__name__)


class NotificationConsumer(AsyncWebsocketConsumer):
    """WebSocket consumer for real-time notifications."""

    # Rate limit: 20 messages per 60 seconds
    RATE_LIMIT_MSGS = 20
    RATE_LIMIT_WINDOW = 60

    async def connect(self):
        """Handle WebSocket connection."""
        self.user = self.scope["user"]
        self._authenticated = False
        self._message_timestamps = []
        self._conn_limit_registered = False

        self._auth_timeout = None

        if self.user.is_authenticated:
            # Authenticated via query string (deprecated) or middleware
            await self._setup_authenticated()
        elif self.scope.get("_allow_post_auth"):
            # Accept connection and wait for authenticate message
            await self.accept()
            # Close the connection if not authenticated within 10 seconds
            self._auth_timeout = asyncio.get_event_loop().call_later(
                10, lambda: asyncio.ensure_future(self._timeout_unauth())
            )
        else:
            await self.close(code=4003)
            return

    async def _timeout_unauth(self):
        """Close connection if still unauthenticated after timeout."""
        if not self._authenticated:
            await self.close(code=4003)

    async def _setup_authenticated(self):
        """Set up authenticated connection: join group, send unread count."""
        # Cancel the auth timeout since authentication succeeded
        if self._auth_timeout:
            self._auth_timeout.cancel()
            self._auth_timeout = None

        # Enforce per-user connection limit
        cache_key = f"ws:conn_count:{self.user.id}"
        try:
            current = cache.get(cache_key, 0)
            if current >= MAX_USER_WS_CONNECTIONS:
                logger.warning(
                    "WS connection limit reached for user %s (%d/%d)",
                    self.user.id, current, MAX_USER_WS_CONNECTIONS,
                )
                await self.close(code=4008)
                return
            cache.set(cache_key, current + 1, timeout=3600)
            self._conn_limit_registered = True
        except Exception:
            logger.debug("Connection limit check failed", exc_info=True)

        self._authenticated = True
        self.group_name = f"notifications_{self.user.id}"

        await self.channel_layer.group_add(self.group_name, self.channel_name)

        if self.scope.get("_allow_post_auth"):
            # Already accepted during connect for post-auth flow
            pass
        else:
            await self.accept()

        # Send connection confirmation with unread count
        unread = await self.get_unread_count()
        await self.send(
            text_data=json.dumps(
                {
                    "type": "connection",
                    "status": "connected",
                    "unread_count": unread,
                }
            )
        )

        self._heartbeat_task = asyncio.ensure_future(self._heartbeat_loop())

    async def _heartbeat_loop(self):
        """Send periodic pings to keep the connection alive."""
        try:
            while True:
                await asyncio.sleep(45)
                await self.send(text_data=json.dumps({"type": "ping"}))
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.warning(
                "Heartbeat loop error for user %s: %s", getattr(self, "user_id", "?"), e
            )

    async def disconnect(self, close_code):
        """Handle WebSocket disconnection."""
        if hasattr(self, "_auth_timeout") and self._auth_timeout:
            self._auth_timeout.cancel()
        if hasattr(self, "_heartbeat_task"):
            self._heartbeat_task.cancel()
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)
        # Release connection slot
        if getattr(self, "_conn_limit_registered", False):
            try:
                cache_key = f"ws:conn_count:{self.user.id}"
                current = cache.get(cache_key, 0)
                if current > 0:
                    cache.set(cache_key, current - 1, timeout=3600)
            except Exception:
                logger.debug("Connection slot release failed", exc_info=True)

    async def receive(self, text_data):
        """Handle incoming messages (authenticate, mark_read, mark_all_read)."""
        try:
            data = json.loads(text_data)
            action = data.get("type")

            # Post-connect authentication via message (preferred over query string)
            if action == "authenticate":
                if self._authenticated:
                    return  # Already authenticated, ignore
                token_key = data.get("token", "")
                from core.websocket_auth import get_user_from_token

                user = await get_user_from_token(token_key)
                if user.is_authenticated:
                    self.user = user
                    self.scope["user"] = user
                    await self._setup_authenticated()
                else:
                    await self.send(
                        text_data=json.dumps(
                            {
                                "type": "error",
                                "error": "Invalid token",
                            }
                        )
                    )
                    await self.close(code=4001)
                return

            # Reject non-auth messages if not yet authenticated
            if not self._authenticated:
                await self.send(
                    text_data=json.dumps(
                        {
                            "type": "error",
                            "error": 'Not authenticated. Send {"type": "authenticate", "token": "..."} first.',
                        }
                    )
                )
                return

            # Rate limit check
            if self._is_rate_limited():
                await self.send(
                    text_data=json.dumps(
                        {
                            "type": "error",
                            "error": "Rate limit exceeded. Please slow down.",
                        }
                    )
                )
                return

            if action == "mark_read":
                notification_id = data.get("notification_id")
                if notification_id:
                    await self.mark_notification_read(notification_id)
                    await self.send(
                        text_data=json.dumps(
                            {
                                "type": "marked_read",
                                "notification_id": notification_id,
                            }
                        )
                    )

            elif action == "mark_all_read":
                count = await self.mark_all_read()
                await self.send(
                    text_data=json.dumps(
                        {
                            "type": "all_marked_read",
                            "count": count,
                        }
                    )
                )

        except json.JSONDecodeError:
            await self.send(
                text_data=json.dumps(
                    {
                        "type": "error",
                        "error": "Invalid JSON",
                    }
                )
            )

    def _is_rate_limited(self):
        """Sliding window rate limit check."""
        now = time.time()
        self._message_timestamps = [
            t for t in self._message_timestamps if now - t < self.RATE_LIMIT_WINDOW
        ]
        if len(self._message_timestamps) >= self.RATE_LIMIT_MSGS:
            return True
        self._message_timestamps.append(now)
        return False

    async def send_notification(self, event):
        """Handler for channel layer group_send — pushes notification to client."""
        await self.send(
            text_data=json.dumps(
                {
                    "type": "notification",
                    "notification": event["notification"],
                }
            )
        )

    async def notification_message(self, event):
        """Handler for generic notification messages (e.g. call rejected)."""
        await self.send(
            text_data=json.dumps(
                {
                    "type": "notification_message",
                    "data": event.get("data", {}),
                }
            )
        )

    async def unread_count_update(self, event):
        """Handler to push updated unread count."""
        await self.send(
            text_data=json.dumps(
                {
                    "type": "unread_count",
                    "count": event["count"],
                }
            )
        )

    @database_sync_to_async
    def get_unread_count(self):
        from .models import Notification

        return Notification.objects.filter(
            user=self.user,
            status="sent",
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
        # Update unread notifications instead of deleting them so history is preserved
        from .models import Notification

        updated = Notification.objects.filter(
            user=self.user,
            read_at__isnull=True,
        ).update(read_at=timezone.now())
        return updated
