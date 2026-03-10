"""
WebSocket consumer for real-time league leaderboard updates.

Broadcasts events when:
- A user's XP changes (ranking change)
- League standings are updated

Message types: ranking_update, xp_change
"""

import asyncio
import json
import logging
import time

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.layers import get_channel_layer

logger = logging.getLogger(__name__)


class LeagueLeaderboardConsumer(AsyncWebsocketConsumer):
    """WebSocket consumer for real-time league leaderboard updates."""

    # Rate limit: 20 messages per 60 seconds
    RATE_LIMIT_MSGS = 20
    RATE_LIMIT_WINDOW = 60

    async def connect(self):
        """Handle WebSocket connection."""
        self.user = self.scope["user"]
        self._authenticated = False
        self._message_timestamps = []
        self._league_group = None

        if self.user.is_authenticated:
            await self._setup_authenticated()
        elif self.scope.get("_allow_post_auth"):
            await self.accept()
        else:
            await self.close(code=4003)
            return

    async def _setup_authenticated(self):
        """Set up authenticated connection: join league tier group."""
        self._authenticated = True

        # Determine the user's current league tier
        tier = await self._get_user_league_tier()
        self._league_group = f"league_{tier}" if tier else "league_bronze"

        await self.channel_layer.group_add(self._league_group, self.channel_name)

        # Also join a personal group for user-specific XP updates
        self._personal_group = f"league_user_{self.user.id}"
        await self.channel_layer.group_add(self._personal_group, self.channel_name)

        if self.scope.get("_allow_post_auth"):
            pass  # Already accepted during connect for post-auth flow
        else:
            await self.accept()

        # Send connection confirmation with current league tier
        await self.send(
            text_data=json.dumps(
                {
                    "type": "connection",
                    "status": "connected",
                    "league_tier": tier or "bronze",
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
        if hasattr(self, "_heartbeat_task"):
            self._heartbeat_task.cancel()
        if self._league_group:
            await self.channel_layer.group_discard(
                self._league_group, self.channel_name
            )
        if hasattr(self, "_personal_group"):
            await self.channel_layer.group_discard(
                self._personal_group, self.channel_name
            )

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

    @database_sync_to_async
    def _get_user_league_tier(self):
        """Get the user's current league tier string."""
        from .services import LeagueService

        league = LeagueService.get_user_league(self.user)
        return league.tier if league else None

    # ── Channel layer event handlers ──────────────────────────────────

    async def ranking_update(self, event):
        """Handler for ranking_update events — league standings changed."""
        await self.send(
            text_data=json.dumps(
                {
                    "type": "ranking_update",
                    "data": event.get("data", {}),
                }
            )
        )

    async def xp_change(self, event):
        """Handler for xp_change events — a user's XP changed."""
        await self.send(
            text_data=json.dumps(
                {
                    "type": "xp_change",
                    "data": event.get("data", {}),
                }
            )
        )


def broadcast_league_update(league_tier, data, event_type="ranking_update"):
    """
    Broadcast a league update to all users in a given league tier.

    This is a synchronous utility that can be called from views/signals.

    Args:
        league_tier: The league tier string (e.g., 'gold', 'bronze').
        data: Dict of event data to send to connected clients.
        event_type: One of 'ranking_update', 'xp_change'. Defaults to 'ranking_update'.
    """
    from asgiref.sync import async_to_sync

    channel_layer = get_channel_layer()
    group_name = f"league_{league_tier}"

    async_to_sync(channel_layer.group_send)(
        group_name,
        {
            "type": event_type,
            "data": data,
        },
    )


def broadcast_xp_change(user_id, data):
    """
    Broadcast an XP change event to a specific user's personal league group.

    Args:
        user_id: UUID/str of the user whose XP changed.
        data: Dict of event data (xp, level, league_tier, rank, etc.).
    """
    from asgiref.sync import async_to_sync

    channel_layer = get_channel_layer()
    group_name = f"league_user_{user_id}"

    async_to_sync(channel_layer.group_send)(
        group_name,
        {
            "type": "xp_change",
            "data": data,
        },
    )
