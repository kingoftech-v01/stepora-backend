"""
Tests for security features: sanitization and WebSocket authentication.
"""

import pytest
from unittest.mock import patch, Mock, AsyncMock
from django.contrib.auth.models import AnonymousUser

from .sanitizers import (
    sanitize_text,
    sanitize_html,
    sanitize_url,
    sanitize_json_values
)
from .websocket_auth import (
    get_user_from_firebase_token,
    FirebaseWebSocketMiddleware,
    FirebaseWebSocketAuthMiddleware
)


class TestSanitizeText:
    """Tests for sanitize_text function."""

    def test_removes_script_tags(self):
        """Test that script tags are removed."""
        text = '<script>alert("xss")</script>Hello'
        result = sanitize_text(text)
        assert '<script>' not in result
        assert 'alert' not in result
        assert 'Hello' in result

    def test_removes_html_tags(self):
        """Test that all HTML tags are removed."""
        text = '<p>Hello</p><div>World</div>'
        result = sanitize_text(text)
        assert '<p>' not in result
        assert '</p>' not in result
        assert 'Hello' in result
        assert 'World' in result

    def test_handles_none(self):
        """Test that None returns empty string."""
        result = sanitize_text(None)
        assert result == ''

    def test_handles_non_string(self):
        """Test that non-string values are converted."""
        result = sanitize_text(123)
        assert result == '123'

    def test_preserves_normal_text(self):
        """Test that normal text is preserved."""
        text = 'Hello World! This is a test.'
        result = sanitize_text(text)
        assert result == text

    def test_removes_nested_tags(self):
        """Test nested tags are removed."""
        text = '<div><p><span>Text</span></p></div>'
        result = sanitize_text(text)
        assert 'Text' in result
        assert '<' not in result

    def test_handles_malformed_html(self):
        """Test malformed HTML is handled."""
        text = '<p>Unclosed tag'
        result = sanitize_text(text)
        assert '<p>' not in result
        assert 'Unclosed tag' in result


class TestSanitizeHtml:
    """Tests for sanitize_html function."""

    def test_allows_safe_tags(self):
        """Test that safe tags are preserved."""
        text = '<p>Hello</p><strong>World</strong>'
        result = sanitize_html(text)
        assert '<p>' in result
        assert '<strong>' in result

    def test_removes_script_tags(self):
        """Test that script tags are removed."""
        text = '<p>Safe</p><script>evil()</script>'
        result = sanitize_html(text)
        assert '<p>' in result
        assert '<script>' not in result

    def test_removes_onclick_handlers(self):
        """Test that event handlers are removed."""
        text = '<a href="#" onclick="evil()">Link</a>'
        result = sanitize_html(text)
        assert 'onclick' not in result

    def test_allows_safe_links(self):
        """Test that safe links are preserved."""
        text = '<a href="https://example.com">Link</a>'
        result = sanitize_html(text)
        assert 'href="https://example.com"' in result

    def test_removes_javascript_links(self):
        """Test that javascript: URLs are removed."""
        text = '<a href="javascript:alert(1)">Link</a>'
        result = sanitize_html(text)
        assert 'javascript:' not in result


class TestSanitizeUrl:
    """Tests for sanitize_url function."""

    def test_allows_https(self):
        """Test HTTPS URLs are allowed."""
        url = 'https://example.com/path'
        result = sanitize_url(url)
        assert result == url

    def test_allows_http(self):
        """Test HTTP URLs are allowed."""
        url = 'http://example.com/path'
        result = sanitize_url(url)
        assert result == url

    def test_allows_mailto(self):
        """Test mailto URLs are allowed."""
        url = 'mailto:test@example.com'
        result = sanitize_url(url)
        assert result == url

    def test_blocks_javascript(self):
        """Test javascript: URLs are blocked."""
        url = 'javascript:alert(1)'
        result = sanitize_url(url)
        assert result == ''

    def test_blocks_data(self):
        """Test data: URLs are blocked."""
        url = 'data:text/html,<script>alert(1)</script>'
        result = sanitize_url(url)
        assert result == ''

    def test_handles_none(self):
        """Test None returns empty string."""
        result = sanitize_url(None)
        assert result == ''

    def test_handles_non_string(self):
        """Test non-string returns empty string."""
        result = sanitize_url(123)
        assert result == ''

    def test_blocks_onclick_in_url(self):
        """Test onclick in URL is blocked."""
        url = 'https://example.com?onclick=alert(1)'
        result = sanitize_url(url)
        assert result == ''


class TestSanitizeJsonValues:
    """Tests for sanitize_json_values function."""

    def test_sanitizes_string_values(self):
        """Test string values are sanitized."""
        data = {'name': '<script>evil()</script>John'}
        result = sanitize_json_values(data)
        assert '<script>' not in result['name']
        assert 'John' in result['name']

    def test_preserves_non_string_values(self):
        """Test non-string values are preserved."""
        data = {'count': 42, 'active': True}
        result = sanitize_json_values(data)
        assert result['count'] == 42
        assert result['active'] is True

    def test_handles_nested_dicts(self):
        """Test nested dictionaries are sanitized."""
        data = {
            'user': {
                'name': '<b>John</b>'
            }
        }
        result = sanitize_json_values(data)
        assert '<b>' not in result['user']['name']
        assert 'John' in result['user']['name']

    def test_handles_lists(self):
        """Test lists are sanitized."""
        data = {
            'tags': ['<script>a</script>', 'safe']
        }
        result = sanitize_json_values(data)
        assert '<script>' not in result['tags'][0]
        assert result['tags'][1] == 'safe'

    def test_specific_keys_only(self):
        """Test sanitizing specific keys only."""
        data = {
            'name': '<b>Bold</b>',
            'code': '<code>keep</code>'
        }
        result = sanitize_json_values(data, keys_to_sanitize=['name'])
        assert '<b>' not in result['name']
        assert '<code>' in result['code']


class TestWebSocketAuth:
    """Tests for WebSocket authentication."""

    @pytest.mark.asyncio
    async def test_get_user_anonymous_when_no_token(self, db):
        """Test returns AnonymousUser when no token provided."""
        user = await get_user_from_firebase_token(None)
        assert isinstance(user, AnonymousUser)

    @pytest.mark.asyncio
    async def test_get_user_anonymous_when_empty_token(self, db):
        """Test returns AnonymousUser when empty token."""
        user = await get_user_from_firebase_token('')
        assert isinstance(user, AnonymousUser)

    @pytest.mark.asyncio
    @patch('core.websocket_auth.firebase_auth')
    async def test_get_user_success(self, mock_firebase, db):
        """Test successful user retrieval."""
        from apps.users.models import User

        # Create test user
        test_user = User.objects.create(
            firebase_uid='test-firebase-uid',
            email='test@test.com'
        )

        # Mock Firebase verification
        mock_firebase.verify_id_token.return_value = {
            'uid': 'test-firebase-uid',
            'email': 'test@test.com'
        }

        user = await get_user_from_firebase_token('valid-token')

        assert user.firebase_uid == 'test-firebase-uid'
        assert user.email == 'test@test.com'

    @pytest.mark.asyncio
    @patch('core.websocket_auth.firebase_auth')
    async def test_get_user_invalid_token(self, mock_firebase, db):
        """Test returns AnonymousUser for invalid token."""
        from firebase_admin.auth import InvalidIdTokenError

        mock_firebase.verify_id_token.side_effect = InvalidIdTokenError('Invalid')
        mock_firebase.InvalidIdTokenError = InvalidIdTokenError

        user = await get_user_from_firebase_token('invalid-token')
        assert isinstance(user, AnonymousUser)

    @pytest.mark.asyncio
    @patch('core.websocket_auth.firebase_auth')
    async def test_get_user_expired_token(self, mock_firebase, db):
        """Test returns AnonymousUser for expired token."""
        from firebase_admin.auth import ExpiredIdTokenError

        mock_firebase.verify_id_token.side_effect = ExpiredIdTokenError('Expired', 'cause')
        mock_firebase.ExpiredIdTokenError = ExpiredIdTokenError

        user = await get_user_from_firebase_token('expired-token')
        assert isinstance(user, AnonymousUser)

    @pytest.mark.asyncio
    @patch('core.websocket_auth.firebase_auth')
    async def test_creates_user_if_not_exists(self, mock_firebase, db):
        """Test creates user if doesn't exist."""
        from apps.users.models import User

        mock_firebase.verify_id_token.return_value = {
            'uid': 'new-firebase-uid',
            'email': 'new@test.com',
            'name': 'New User'
        }

        user = await get_user_from_firebase_token('valid-token')

        assert user.firebase_uid == 'new-firebase-uid'
        assert user.email == 'new@test.com'
        assert User.objects.filter(firebase_uid='new-firebase-uid').exists()


class TestFirebaseWebSocketMiddleware:
    """Tests for Firebase WebSocket Middleware."""

    @pytest.mark.asyncio
    async def test_extracts_token_from_query_string(self, db):
        """Test token extraction from query string."""
        middleware = FirebaseWebSocketMiddleware(inner=AsyncMock())

        scope = {
            'type': 'websocket',
            'query_string': b'token=test-token',
        }

        with patch('core.websocket_auth.get_user_from_firebase_token') as mock_get_user:
            mock_get_user.return_value = AnonymousUser()
            await middleware(scope, AsyncMock(), AsyncMock())
            mock_get_user.assert_called_once_with('test-token')

    @pytest.mark.asyncio
    async def test_handles_empty_query_string(self, db):
        """Test handling empty query string."""
        middleware = FirebaseWebSocketMiddleware(inner=AsyncMock())

        scope = {
            'type': 'websocket',
            'query_string': b'',
        }

        with patch('core.websocket_auth.get_user_from_firebase_token') as mock_get_user:
            mock_get_user.return_value = AnonymousUser()
            await middleware(scope, AsyncMock(), AsyncMock())
            mock_get_user.assert_called_once_with(None)
