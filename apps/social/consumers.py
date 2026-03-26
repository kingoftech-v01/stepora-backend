"""
WebSocket consumer for real-time social feed updates.

Broadcasts events when:
- Someone the user follows creates a post
- Someone likes/comments on the user's post
- Someone follows/unfollows the user

Message types: new_post, post_liked, post_commented, follow_update
"""

import asyncio
import json
import logging
import time

from channels.generic.websocket import AsyncWebsocketConsumer
from channels.layers import get_channel_layer
from django.core.cache import cache

from core.consumers import MAX_USER_WS_CONNECTIONS

logger = logging.getLogger(__name__)


class SocialFeedConsumer(AsyncWebsocketConsumer):
    """WebSocket consumer for real-time social feed updates."""

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
            await self._setup_authenticated()
        elif self.scope.get("_allow_post_auth"):
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
        """Set up authenticated connection: join personal social group."""
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
        self.group_name = f"social_feed_{self.user.id}"

        await self.channel_layer.group_add(self.group_name, self.channel_name)

        if self.scope.get("_allow_post_auth"):
            pass  # Already accepted during connect for post-auth flow
        else:
            await self.accept()

        # Send connection confirmation
        await self.send(
            text_data=json.dumps(
                {
                    "type": "connection",
                    "status": "connected",
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
                "Heartbeat loop error for user %s: %s", getattr(self, "user", "?"), e
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
        """Handle incoming messages (authenticate only — this is a read-only consumer)."""
        try:
            data = json.loads(text_data)
            action = data.get("type")

            # Post-connect authentication via message (preferred over query string)
            if action == "authenticate":
                if self._authenticated:
                    return
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

            # Handle pong for heartbeat
            if action == "pong":
                return

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

    # ── Channel layer event handlers ──────────────────────────────────

    async def new_post(self, event):
        """Handler for new_post events — a followed user created a post."""
        await self.send(
            text_data=json.dumps(
                {
                    "type": "new_post",
                    "data": event.get("data", {}),
                }
            )
        )

    async def post_liked(self, event):
        """Handler for post_liked events — someone liked the user's post."""
        await self.send(
            text_data=json.dumps(
                {
                    "type": "post_liked",
                    "data": event.get("data", {}),
                }
            )
        )

    async def post_commented(self, event):
        """Handler for post_commented events — someone commented on the user's post."""
        await self.send(
            text_data=json.dumps(
                {
                    "type": "post_commented",
                    "data": event.get("data", {}),
                }
            )
        )

    async def follow_update(self, event):
        """Handler for follow_update events — someone followed/unfollowed the user."""
        await self.send(
            text_data=json.dumps(
                {
                    "type": "follow_update",
                    "data": event.get("data", {}),
                }
            )
        )


def broadcast_social_event(user_id, event_type, data):
    """
    Broadcast a social event to a user's social feed WebSocket group.

    This is a synchronous utility that can be called from views/signals.
    Uses async_to_sync to send via the channel layer.

    Args:
        user_id: UUID/str of the target user who should receive the event.
        event_type: One of 'new_post', 'post_liked', 'post_commented', 'follow_update'.
        data: Dict of event data to send to the client.
    """
    from asgiref.sync import async_to_sync

    channel_layer = get_channel_layer()
    group_name = f"social_feed_{user_id}"

    async_to_sync(channel_layer.group_send)(
        group_name,
        {
            "type": event_type,
            "data": data,
        },
    )


def broadcast_social_event_to_followers(author_user, event_type, data):
    """
    Broadcast a social event to all followers of the given user.

    Useful for broadcasting new_post events to everyone who follows the author.

    Args:
        author_user: The User instance whose followers should receive the event.
        event_type: Event type string (e.g., 'new_post').
        data: Dict of event data.
    """
    from apps.social.models import UserFollow

    follower_ids = UserFollow.objects.filter(following=author_user).values_list(
        "follower_id", flat=True
    )

    for follower_id in follower_ids:
        try:
            broadcast_social_event(follower_id, event_type, data)
        except Exception:
            logger.warning(
                "Failed to broadcast %s to follower %s",
                event_type,
                follower_id,
                exc_info=True,
            )
