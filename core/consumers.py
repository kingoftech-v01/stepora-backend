"""
Shared WebSocket consumer mixins for Stepora.

Provides reusable building blocks for all WebSocket consumers:
- RateLimitMixin: per-connection sliding-window rate limiter
- ConnectionLimitMixin: per-user concurrent connection limiter (Redis-backed)
- AuthenticatedConsumerMixin: post-connect token auth, heartbeat, error helper
- BlockingMixin: check BlockedUser between two users
- ModerationMixin: content moderation via ContentModerationService
"""

import asyncio
import json
import logging
import time
from collections import deque

from channels.db import database_sync_to_async
from django.core.cache import cache

logger = logging.getLogger(__name__)

# ── Default constants (consumers can override) ──────────────────────
MAX_MSG_SIZE = 8192
MAX_MSG_CONTENT_LEN = 5000
DEFAULT_RATE_LIMIT_MSGS = 30
DEFAULT_RATE_LIMIT_WINDOW = 60
HEARTBEAT_INTERVAL = 45
MAX_USER_WS_CONNECTIONS = 5  # Max concurrent WS connections per user


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


class ConnectionLimitMixin:
    """
    Per-user concurrent WebSocket connection limiter (Redis-backed).

    Tracks active connections per user in the Django cache (Redis).
    Rejects new connections that exceed MAX_USER_WS_CONNECTIONS.
    """

    max_user_connections = MAX_USER_WS_CONNECTIONS

    def _conn_limit_cache_key(self, user_id):
        return f"ws:conn_count:{user_id}"

    async def _check_connection_limit(self):
        """
        Increment the user's connection count. Returns True if allowed,
        False if the limit is exceeded (connection should be rejected).
        """
        user_id = str(self.user.id)
        cache_key = self._conn_limit_cache_key(user_id)

        try:
            current = cache.get(cache_key, 0)
            if current >= self.max_user_connections:
                logger.warning(
                    "WS connection limit reached for user %s (%d/%d)",
                    user_id,
                    current,
                    self.max_user_connections,
                )
                return False
            # Increment with a TTL of 1 hour (connections should disconnect
            # and decrement, but TTL acts as a safety net against leaks)
            cache.set(cache_key, current + 1, timeout=3600)
            self._conn_limit_registered = True
            return True
        except Exception:
            # If cache is unavailable, allow the connection (fail open for availability)
            logger.debug("Connection limit check failed — allowing connection", exc_info=True)
            return True

    async def _release_connection_slot(self):
        """Decrement the user's connection count on disconnect."""
        if not getattr(self, "_conn_limit_registered", False):
            return
        try:
            user_id = str(self.user.id)
            cache_key = self._conn_limit_cache_key(user_id)
            current = cache.get(cache_key, 0)
            if current > 0:
                cache.set(cache_key, current - 1, timeout=3600)
        except Exception:
            logger.debug("Connection slot release failed", exc_info=True)


class AuthenticatedConsumerMixin:
    """
    Post-connect token authentication, heartbeat loop, and error helper.

    Subclasses must implement ``_setup_authenticated_inner()`` which is called
    after the user is verified and the connection is accepted.
    """

    async def _init_auth(self):
        """Call from connect(). Sets up auth state."""
        self.user = self.scope["user"]
        self._authenticated = False
        self._auth_timeout = None

    async def _handle_auth_connect(self):
        """Handle the auth flow on connect. Returns True if connected."""
        if self.user.is_authenticated:
            await self._setup_authenticated()
            return True
        elif self.scope.get("_allow_post_auth"):
            await self.accept()
            # Close the connection if not authenticated within 10 seconds
            self._auth_timeout = asyncio.get_event_loop().call_later(
                10, lambda: asyncio.ensure_future(self._timeout_unauth())
            )
            return True
        else:
            await self.close(code=4003)
            return False

    async def _timeout_unauth(self):
        """Close connection if still unauthenticated after timeout."""
        if not self._authenticated:
            await self.close(code=4003)

    async def _setup_authenticated(self):
        """Verify access and join room after authentication."""
        # Cancel the auth timeout since authentication succeeded
        if self._auth_timeout:
            self._auth_timeout.cancel()
            self._auth_timeout = None

        # Enforce per-user connection limit (if mixin is present)
        if hasattr(self, "_check_connection_limit"):
            allowed = await self._check_connection_limit()
            if not allowed:
                await self.send(
                    text_data=json.dumps(
                        {
                            "type": "error",
                            "error": "Too many active connections. Please close other tabs.",
                        }
                    )
                ) if self.scope.get("_allow_post_auth") else None
                await self.close(code=4008)
                return

        self._authenticated = True

        if self.scope.get("_allow_post_auth"):
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
                await self.send(text_data=json.dumps({"type": "ping"}))
        except asyncio.CancelledError:
            pass
        except Exception:
            logger.debug("Heartbeat error", exc_info=True)

    async def _cancel_heartbeat(self):
        if hasattr(self, "_auth_timeout") and self._auth_timeout:
            self._auth_timeout.cancel()
        if hasattr(self, "_heartbeat_task"):
            self._heartbeat_task.cancel()
        # Release connection slot (if ConnectionLimitMixin is present)
        if hasattr(self, "_release_connection_slot"):
            await self._release_connection_slot()

    async def _handle_authenticate_message(self, data):
        """Process a {"type": "authenticate", "token": "..."} message."""
        if self._authenticated:
            return
        from core.websocket_auth import get_user_from_token

        user = await get_user_from_token(data.get("token", ""))
        if user.is_authenticated:
            self.user = user
            self.scope["user"] = user
            await self._setup_authenticated()
        else:
            await self.send_error("Invalid token")
            await self.close(code=4001)

    async def send_error(self, error_message):
        """Send error message to client."""
        await self.send(
            text_data=json.dumps(
                {
                    "type": "error",
                    "error": error_message,
                }
            )
        )


class BlockingMixin:
    """Check BlockedUser between two users."""

    @database_sync_to_async
    def _is_blocked(self, user_a, user_b):
        from apps.social.models import BlockedUser

        return BlockedUser.is_blocked(user_a, user_b)


class ModerationMixin:
    """Content moderation via ContentModerationService."""

    @database_sync_to_async
    def _moderate_content(self, content, context="chat"):
        from core.moderation import ContentModerationService

        return ContentModerationService().moderate_text(content, context=context)
