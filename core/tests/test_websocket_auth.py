"""
Tests for core.websocket_auth — JWT / DRF-Token WebSocket authentication.

Covers:
- get_user_from_token (JWT valid, invalid, expired; DRF Token valid, expired, inactive)
- TokenWebSocketMiddleware (query-string token, missing token, _allow_post_auth flag)
- TokenWebSocketAuthMiddleware (alternative wrapper)
- TokenAuthMiddlewareStack convenience function
"""

from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser

from apps.users.models import User
from core.websocket_auth import (
    TokenAuthMiddlewareStack,
    TokenWebSocketAuthMiddleware,
    TokenWebSocketMiddleware,
    get_user_from_token,
)

# ──────────────────────────────────────────────────────────────────────
#  get_user_from_token
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestGetUserFromToken:
    """Test the get_user_from_token async helper."""

    @pytest.mark.asyncio
    async def test_empty_token_returns_anonymous(self):
        """Empty or None token should return AnonymousUser."""
        user = await get_user_from_token("")
        assert isinstance(user, AnonymousUser)
        assert not user.is_authenticated

    @pytest.mark.asyncio
    async def test_none_token_returns_anonymous(self):
        """None token should return AnonymousUser."""
        user = await get_user_from_token(None)
        assert isinstance(user, AnonymousUser)

    @pytest.mark.asyncio
    async def test_garbage_token_returns_anonymous(self):
        """A random garbage string should return AnonymousUser."""
        user = await get_user_from_token("totally-invalid-token-xyz")
        assert isinstance(user, AnonymousUser)

    @pytest.mark.asyncio
    async def test_valid_jwt_returns_user(self):
        """A valid JWT access token should return the corresponding user."""
        u = await _create_user("ws_jwt@example.com")
        from rest_framework_simplejwt.tokens import AccessToken

        token = str(AccessToken.for_user(u))
        result = await get_user_from_token(token)
        assert result.is_authenticated
        assert result.id == u.id

    @pytest.mark.asyncio
    async def test_expired_jwt_returns_anonymous(self):
        """An expired JWT should return AnonymousUser."""
        u = await _create_user("ws_exp_jwt@example.com")
        from rest_framework_simplejwt.tokens import AccessToken

        token = AccessToken.for_user(u)
        # Force the token to be expired
        token.set_exp(lifetime=-timedelta(days=1))
        result = await get_user_from_token(str(token))
        assert isinstance(result, AnonymousUser)

    @pytest.mark.asyncio
    async def test_jwt_for_inactive_user_returns_anonymous(self):
        """A JWT for an inactive user should return AnonymousUser."""
        u = await _create_user("ws_inactive@example.com")
        from rest_framework_simplejwt.tokens import AccessToken

        token = str(AccessToken.for_user(u))
        # Deactivate the user
        from channels.db import database_sync_to_async

        @database_sync_to_async
        def deactivate():
            u.is_active = False
            u.save(update_fields=["is_active"])

        await deactivate()
        result = await get_user_from_token(token)
        assert isinstance(result, AnonymousUser)

    @pytest.mark.asyncio
    async def test_jwt_for_nonexistent_user_returns_anonymous(self):
        """A JWT referencing a deleted user should return AnonymousUser."""
        u = await _create_user("ws_deleted@example.com")
        from rest_framework_simplejwt.tokens import AccessToken

        token = str(AccessToken.for_user(u))
        from channels.db import database_sync_to_async

        await database_sync_to_async(u.delete)()
        result = await get_user_from_token(token)
        assert isinstance(result, AnonymousUser)


# ──────────────────────────────────────────────────────────────────────
#  TokenWebSocketMiddleware
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestTokenWebSocketMiddleware:
    """Test the BaseMiddleware-based TokenWebSocketMiddleware."""

    @pytest.mark.asyncio
    async def test_no_token_sets_anonymous_and_allows_post_auth(self):
        """Without a query-string token, user is anon and _allow_post_auth is True."""
        inner_app = AsyncMock()
        middleware = TokenWebSocketMiddleware(inner_app)

        scope = {
            "type": "websocket",
            "query_string": b"",
        }
        receive = AsyncMock()
        send = AsyncMock()

        await middleware(scope, receive, send)
        assert isinstance(scope["user"], AnonymousUser)
        assert scope["_allow_post_auth"] is True

    @pytest.mark.asyncio
    async def test_valid_jwt_token_in_query_string(self):
        """A valid JWT in the query string should set the user and disable post-auth."""
        u = await _create_user("ws_mw_jwt@example.com")
        from rest_framework_simplejwt.tokens import AccessToken

        token = str(AccessToken.for_user(u))

        inner_app = AsyncMock()
        middleware = TokenWebSocketMiddleware(inner_app)

        scope = {
            "type": "websocket",
            "query_string": f"token={token}".encode(),
        }
        receive = AsyncMock()
        send = AsyncMock()

        await middleware(scope, receive, send)
        assert scope["user"].is_authenticated
        assert scope["user"].id == u.id
        assert scope["_allow_post_auth"] is False

    @pytest.mark.asyncio
    async def test_invalid_token_in_query_string_sets_anonymous(self):
        """An invalid token in query string should set AnonymousUser."""
        inner_app = AsyncMock()
        middleware = TokenWebSocketMiddleware(inner_app)

        scope = {
            "type": "websocket",
            "query_string": b"token=bad-token-value",
        }
        receive = AsyncMock()
        send = AsyncMock()

        await middleware(scope, receive, send)
        assert isinstance(scope["user"], AnonymousUser)
        # When a token IS provided (even invalid), _allow_post_auth is False
        assert scope["_allow_post_auth"] is False


# ──────────────────────────────────────────────────────────────────────
#  TokenWebSocketAuthMiddleware (alternative wrapper)
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestTokenWebSocketAuthMiddleware:
    """Test the alternative (non-BaseMiddleware) auth middleware."""

    @pytest.mark.asyncio
    async def test_non_websocket_scope_passes_through(self):
        """Non-websocket scopes should pass through to the inner app."""
        inner_app = AsyncMock()
        middleware = TokenWebSocketAuthMiddleware(inner_app)

        scope = {"type": "http"}
        receive = AsyncMock()
        send = AsyncMock()

        await middleware(scope, receive, send)
        inner_app.assert_awaited_once_with(scope, receive, send)
        assert "user" not in scope

    @pytest.mark.asyncio
    async def test_websocket_scope_without_token(self):
        """WebSocket scope without token sets anon user and _allow_post_auth."""
        inner_app = AsyncMock()
        middleware = TokenWebSocketAuthMiddleware(inner_app)

        scope = {"type": "websocket", "query_string": b""}
        receive = AsyncMock()
        send = AsyncMock()

        await middleware(scope, receive, send)
        assert isinstance(scope["user"], AnonymousUser)
        assert scope["_allow_post_auth"] is True

    @pytest.mark.asyncio
    async def test_websocket_scope_with_valid_token(self):
        """WebSocket scope with valid token sets authenticated user."""
        u = await _create_user("ws_alt_mw@example.com")
        from rest_framework_simplejwt.tokens import AccessToken

        token = str(AccessToken.for_user(u))

        inner_app = AsyncMock()
        middleware = TokenWebSocketAuthMiddleware(inner_app)

        scope = {"type": "websocket", "query_string": f"token={token}".encode()}
        receive = AsyncMock()
        send = AsyncMock()

        await middleware(scope, receive, send)
        assert scope["user"].id == u.id
        assert scope["_allow_post_auth"] is False


# ──────────────────────────────────────────────────────────────────────
#  TokenAuthMiddlewareStack
# ──────────────────────────────────────────────────────────────────────


class TestTokenAuthMiddlewareStack:
    """Test the convenience wrapper function."""

    def test_returns_middleware_instance(self):
        """TokenAuthMiddlewareStack should return a TokenWebSocketAuthMiddleware."""
        inner = MagicMock()
        result = TokenAuthMiddlewareStack(inner)
        assert isinstance(result, TokenWebSocketAuthMiddleware)

    def test_wraps_inner_app(self):
        """The returned middleware should wrap the provided inner app."""
        inner = MagicMock()
        result = TokenAuthMiddlewareStack(inner)
        assert result.app is inner


# ──────────────────────────────────────────────────────────────────────
#  Helpers
# ──────────────────────────────────────────────────────────────────────


@database_sync_to_async
def _create_user(email):
    return User.objects.create_user(
        email=email,
        password="testpassword123",
        display_name="WS Auth Test User",
    )
