"""
Shared WebSocket consumer mixins for DreamPlanner.

Provides reusable building blocks for all WebSocket consumers:
- RateLimitMixin: per-connection sliding-window rate limiter
- AuthenticatedConsumerMixin: post-connect token auth, heartbeat, error helper
- BlockingMixin: check BlockedUser between two users
- ModerationMixin: content moderation via ContentModerationService
"""

import json
import time
import asyncio
import logging
from collections import deque

from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async

logger = logging.getLogger(__name__)

# ── Default constants (consumers can override) ──────────────────────
MAX_MSG_SIZE = 8192
MAX_MSG_CONTENT_LEN = 5000
DEFAULT_RATE_LIMIT_MSGS = 30
DEFAULT_RATE_LIMIT_WINDOW = 60
HEARTBEAT_INTERVAL = 45


class RateLimitMixin:
    """Sliding-window rate limiter per WebSocket connection."""

    rate_limit_msgs = DEFAULT_RATE_LIMIT_MSGS
    rate_limit_window = DEFAULT_RATE_LIMIT_WINDOW

    def _init_rate_limit(self):
        self._msg_timestamps = deque(maxlen=self.rate_limit_msgs)

    def _is_rate_limited(self):
        now = time.monotonic()
        cutoff = now - self.rate_limit_window
        while self._msg_timestamps and self._msg_timestamps[0] < cutoff:
            self._msg_timestamps.popleft()
        if len(self._msg_timestamps) >= self.rate_limit_msgs:
            return True
        self._msg_timestamps.append(now)
        return False


class AuthenticatedConsumerMixin:
    """
    Post-connect token authentication, heartbeat loop, and error helper.

    Subclasses must implement ``_setup_authenticated_inner()`` which is called
    after the user is verified and the connection is accepted.
    """

    async def _init_auth(self):
        """Call from connect(). Sets up auth state."""
        self.user = self.scope['user']
        self._authenticated = False

    async def _handle_auth_connect(self):
        """Handle the auth flow on connect. Returns True if connected."""
        if self.user.is_authenticated:
            await self._setup_authenticated()
            return True
        elif self.scope.get('_allow_post_auth'):
            await self.accept()
            return True
        else:
            await self.close(code=4003)
            return False

    async def _setup_authenticated(self):
        """Verify access and join room after authentication."""
        self._authenticated = True

        if self.scope.get('_allow_post_auth'):
            pass  # Already accepted
        else:
            await self.accept()

        await self._setup_authenticated_inner()

        self._heartbeat_task = asyncio.ensure_future(self._heartbeat_loop())

    async def _setup_authenticated_inner(self):
        """Override in subclass: join groups, send confirmation, etc."""
        raise NotImplementedError

    async def _heartbeat_loop(self):
        try:
            while True:
                await asyncio.sleep(HEARTBEAT_INTERVAL)
                await self.send(text_data=json.dumps({'type': 'ping'}))
        except asyncio.CancelledError:
            pass
        except Exception:
            logger.debug("Heartbeat error", exc_info=True)

    async def _cancel_heartbeat(self):
        if hasattr(self, '_heartbeat_task'):
            self._heartbeat_task.cancel()

    async def _handle_authenticate_message(self, data):
        """Process a {"type": "authenticate", "token": "..."} message."""
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

    async def send_error(self, error_message):
        """Send error message to client."""
        await self.send(text_data=json.dumps({
            'type': 'error',
            'error': error_message,
        }))


class BlockingMixin:
    """Check BlockedUser between two users."""

    @database_sync_to_async
    def _is_blocked(self, user_a, user_b):
        from apps.social.models import BlockedUser
        return BlockedUser.is_blocked(user_a, user_b)


class ModerationMixin:
    """Content moderation via ContentModerationService."""

    @database_sync_to_async
    def _moderate_content(self, content, context='chat'):
        from core.moderation import ContentModerationService
        return ContentModerationService().moderate_text(content, context=context)
