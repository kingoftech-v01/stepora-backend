"""
Tests for integrations.google_calendar.GoogleCalendarService.

All Google API calls are mocked — no real API traffic.
"""

import uuid
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

import pytest
from django.core.cache import cache
from django.utils import timezone

from integrations.google_calendar import GoogleCalendarService

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_user(user_id=None, email="test@example.com"):
    """Build a mock User instance."""
    user = Mock()
    user.id = user_id or uuid.uuid4()
    user.email = email
    return user


def _make_integration(
    access_token="access-tok",
    refresh_token="refresh-tok",
    calendar_id="primary",
    sync_token="",
    token_expiry=None,
):
    """Build a mock GoogleCalendarIntegration model instance."""
    integration = Mock()
    integration.access_token = access_token
    integration.refresh_token = refresh_token
    integration.calendar_id = calendar_id
    integration.sync_token = sync_token
    integration.token_expiry = token_expiry or (timezone.now() + timedelta(hours=1))
    integration.user = _make_user()
    integration.last_sync_at = None
    integration.save = Mock()
    return integration


def _make_calendar_event(
    title="My Event",
    description="Event description",
    start_time=None,
    end_time=None,
    location="",
    google_event_id=None,
):
    """Build a mock CalendarEvent model instance."""
    event = Mock()
    event.title = title
    event.description = description
    event.start_time = start_time or timezone.now()
    event.end_time = end_time or (timezone.now() + timedelta(hours=1))
    event.location = location
    event.google_event_id = google_event_id
    event.save = Mock()
    return event


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_user():
    """Return a mock user for PKCE auth flow."""
    return _make_user()


@pytest.fixture
def service(mock_user):
    """Return a GoogleCalendarService instance with a user but no integration."""
    return GoogleCalendarService(user=mock_user)


@pytest.fixture
def service_no_user():
    """Return a GoogleCalendarService instance with no user or integration."""
    return GoogleCalendarService()


@pytest.fixture
def integration():
    """Return a mock integration with valid (non-expired) token."""
    return _make_integration()


@pytest.fixture
def service_with_integration(integration):
    """Return a GoogleCalendarService with a mock integration."""
    return GoogleCalendarService(user=integration.user, integration=integration)


# ===================================================================
# __init__()
# ===================================================================

class TestInit:

    def test_no_integration(self, service):
        assert service.integration is None
        assert service.user is not None

    def test_no_user(self, service_no_user):
        assert service_no_user.user is None
        assert service_no_user.integration is None

    def test_with_integration(self, service_with_integration):
        assert service_with_integration.integration is not None
        assert service_with_integration.integration.access_token == "access-tok"
        assert service_with_integration.user is not None


# ===================================================================
# get_auth_url()
# ===================================================================

class TestGetAuthUrl:

    @patch("google_auth_oauthlib.flow.Flow.from_client_config")
    def test_returns_auth_url(self, mock_from_config, service):
        mock_flow = Mock()
        mock_flow.authorization_url.return_value = (
            "https://accounts.google.com/auth?client_id=xxx",
            "state-value",
        )
        mock_from_config.return_value = mock_flow

        url = service.get_auth_url("https://example.com/callback")

        assert url == "https://accounts.google.com/auth?client_id=xxx"
        mock_from_config.assert_called_once()
        config = mock_from_config.call_args[0][0]
        assert "web" in config
        mock_flow.authorization_url.assert_called_once_with(
            access_type="offline",
            include_granted_scopes="true",
            prompt="consent",
        )

    @patch("google_auth_oauthlib.flow.Flow.from_client_config")
    def test_uses_correct_scopes(self, mock_from_config, service):
        mock_flow = Mock()
        mock_flow.authorization_url.return_value = ("url", "state")
        mock_from_config.return_value = mock_flow

        service.get_auth_url("https://example.com/callback")

        call_args = mock_from_config.call_args
        assert call_args[1]["scopes"] == ["https://www.googleapis.com/auth/calendar"]

    @patch("google_auth_oauthlib.flow.Flow.from_client_config")
    def test_uses_redirect_uri(self, mock_from_config, service):
        mock_flow = Mock()
        mock_flow.authorization_url.return_value = ("url", "state")
        mock_from_config.return_value = mock_flow

        service.get_auth_url("https://my-app.com/gcal/callback")

        call_args = mock_from_config.call_args
        assert call_args[1]["redirect_uri"] == "https://my-app.com/gcal/callback"

    @patch("google_auth_oauthlib.flow.Flow.from_client_config")
    def test_passes_pkce_code_verifier(self, mock_from_config, service):
        mock_flow = Mock()
        mock_flow.authorization_url.return_value = ("url", "state")
        mock_from_config.return_value = mock_flow

        service.get_auth_url("https://example.com/callback")

        call_kwargs = mock_from_config.call_args[1]
        assert "code_verifier" in call_kwargs
        assert call_kwargs["code_verifier"] is not None
        assert len(call_kwargs["code_verifier"]) >= 43
        assert call_kwargs["autogenerate_code_verifier"] is False

    @patch("google_auth_oauthlib.flow.Flow.from_client_config")
    def test_caches_code_verifier(self, mock_from_config, service):
        mock_flow = Mock()
        mock_flow.authorization_url.return_value = ("url", "state")
        mock_from_config.return_value = mock_flow

        service.get_auth_url("https://example.com/callback")

        cached = cache.get(service._cache_key())
        assert cached is not None
        assert cached == service._generate_code_verifier()


# ===================================================================
# exchange_code()
# ===================================================================

class TestExchangeCode:

    @patch("google_auth_oauthlib.flow.Flow.from_client_config")
    def test_returns_tokens(self, mock_from_config, service):
        mock_creds = Mock()
        mock_creds.token = "new-access-token"
        mock_creds.refresh_token = "new-refresh-token"
        mock_creds.expiry = datetime(2026, 12, 31, 23, 59, 59)

        mock_flow = Mock()
        mock_flow.credentials = mock_creds
        mock_from_config.return_value = mock_flow

        result = service.exchange_code("auth-code-123", "https://example.com/callback")

        assert result["access_token"] == "new-access-token"
        assert result["refresh_token"] == "new-refresh-token"
        assert result["token_expiry"] == datetime(2026, 12, 31, 23, 59, 59)
        mock_flow.fetch_token.assert_called_once_with(code="auth-code-123")

    @patch("google_auth_oauthlib.flow.Flow.from_client_config")
    def test_uses_same_redirect_uri(self, mock_from_config, service):
        mock_flow = Mock()
        mock_flow.credentials = Mock(token="t", refresh_token="r", expiry=None)
        mock_from_config.return_value = mock_flow

        service.exchange_code("code", "https://my-app.com/callback")

        call_args = mock_from_config.call_args
        assert call_args[1]["redirect_uri"] == "https://my-app.com/callback"

    @patch("google_auth_oauthlib.flow.Flow.from_client_config")
    def test_passes_pkce_code_verifier(self, mock_from_config, service):
        mock_flow = Mock()
        mock_flow.credentials = Mock(token="t", refresh_token="r", expiry=None)
        mock_from_config.return_value = mock_flow

        service.exchange_code("code", "https://example.com/callback")

        call_kwargs = mock_from_config.call_args[1]
        assert "code_verifier" in call_kwargs
        assert call_kwargs["code_verifier"] is not None
        assert call_kwargs["autogenerate_code_verifier"] is False

    @patch("google_auth_oauthlib.flow.Flow.from_client_config")
    def test_uses_cached_verifier(self, mock_from_config, service):
        """exchange_code should use the Redis-cached verifier when available."""
        mock_flow = Mock()
        mock_flow.credentials = Mock(token="t", refresh_token="r", expiry=None)
        mock_from_config.return_value = mock_flow

        # Pre-populate cache (simulating get_auth_url having been called)
        cache.set(service._cache_key(), "cached-verifier-value", timeout=900)

        service.exchange_code("code", "https://example.com/callback")

        call_kwargs = mock_from_config.call_args[1]
        assert call_kwargs["code_verifier"] == "cached-verifier-value"

    @patch("google_auth_oauthlib.flow.Flow.from_client_config")
    def test_clears_cache_after_exchange(self, mock_from_config, service):
        """Cache key should be deleted after successful token exchange."""
        mock_flow = Mock()
        mock_flow.credentials = Mock(token="t", refresh_token="r", expiry=None)
        mock_from_config.return_value = mock_flow

        cache.set(service._cache_key(), "cached-verifier-value", timeout=900)
        service.exchange_code("code", "https://example.com/callback")

        assert cache.get(service._cache_key()) is None

    @patch("google_auth_oauthlib.flow.Flow.from_client_config")
    def test_deterministic_fallback_on_cache_miss(self, mock_from_config, service):
        """exchange_code should fall back to deterministic verifier if cache is empty."""
        mock_flow = Mock()
        mock_flow.credentials = Mock(token="t", refresh_token="r", expiry=None)
        mock_from_config.return_value = mock_flow

        # Ensure no cache entry exists
        cache.delete(service._cache_key())

        service.exchange_code("code", "https://example.com/callback")

        call_kwargs = mock_from_config.call_args[1]
        expected_verifier = service._generate_code_verifier()
        assert call_kwargs["code_verifier"] == expected_verifier


# ===================================================================
# _get_credentials()
# ===================================================================

class TestGetCredentials:

    @patch("google.oauth2.credentials.Credentials")
    def test_valid_token_not_refreshed(self, mock_creds_cls, service_with_integration):
        # Token is valid (expiry in the future — already set by fixture)
        mock_creds = Mock()
        mock_creds_cls.return_value = mock_creds

        result = service_with_integration._get_credentials()

        assert result == mock_creds
        mock_creds.refresh.assert_not_called()
        service_with_integration.integration.save.assert_not_called()

    @patch("google.auth.transport.requests.Request")
    @patch("google.oauth2.credentials.Credentials")
    def test_expired_token_refreshed(self, mock_creds_cls, mock_request_cls, service_with_integration):
        # Token expired
        service_with_integration.integration.token_expiry = timezone.now() - timedelta(hours=1)

        mock_creds = Mock()
        mock_creds.token = "refreshed-access-token"
        mock_creds.expiry = datetime(2026, 12, 31)
        mock_creds_cls.return_value = mock_creds

        result = service_with_integration._get_credentials()

        assert result == mock_creds
        mock_creds.refresh.assert_called_once()
        assert service_with_integration.integration.access_token == "refreshed-access-token"
        service_with_integration.integration.save.assert_called_once()


# ===================================================================
# _get_service()
# ===================================================================

class TestGetService:

    def test_builds_calendar_service(self, service_with_integration):
        import sys
        import types

        mock_discovery = types.ModuleType("googleapiclient.discovery")
        mock_build = Mock(return_value=Mock())
        mock_discovery.build = mock_build

        with patch.dict(sys.modules, {
            "googleapiclient": types.ModuleType("googleapiclient"),
            "googleapiclient.discovery": mock_discovery,
        }):
            with patch.object(service_with_integration, "_get_credentials") as mock_get_creds:
                mock_creds = Mock()
                mock_get_creds.return_value = mock_creds

                service_with_integration._get_service()

                mock_build.assert_called_once_with("calendar", "v3", credentials=mock_creds)


# ===================================================================
# push_event() — create new event
# ===================================================================

class TestPushEventCreate:

    def test_creates_new_event(self, service_with_integration):
        calendar_event = _make_calendar_event(google_event_id=None, location="Paris")

        mock_service = Mock()
        mock_insert = mock_service.events.return_value.insert.return_value
        mock_insert.execute.return_value = {"id": "google-event-id-123"}

        with patch.object(service_with_integration, "_get_service", return_value=mock_service):
            result = service_with_integration.push_event(calendar_event)

        assert result == "google-event-id-123"
        calendar_event.save.assert_called_once()
        assert calendar_event.google_event_id == "google-event-id-123"

        # Verify insert was called (not update)
        mock_service.events.return_value.insert.assert_called_once()
        call_kwargs = mock_service.events.return_value.insert.call_args[1]
        assert call_kwargs["calendarId"] == "primary"
        assert call_kwargs["body"]["summary"] == "My Event"
        assert call_kwargs["body"]["location"] == "Paris"

    def test_creates_event_without_location(self, service_with_integration):
        calendar_event = _make_calendar_event(google_event_id=None, location="")

        mock_service = Mock()
        mock_insert = mock_service.events.return_value.insert.return_value
        mock_insert.execute.return_value = {"id": "new-id"}

        with patch.object(service_with_integration, "_get_service", return_value=mock_service):
            service_with_integration.push_event(calendar_event)

        call_kwargs = mock_service.events.return_value.insert.call_args[1]
        assert "location" not in call_kwargs["body"]


# ===================================================================
# push_event() — update existing event
# ===================================================================

class TestPushEventUpdate:

    def test_updates_existing_event(self, service_with_integration):
        calendar_event = _make_calendar_event(google_event_id="existing-id-456")

        mock_service = Mock()
        mock_update = mock_service.events.return_value.update.return_value
        mock_update.execute.return_value = {"id": "existing-id-456"}

        with patch.object(service_with_integration, "_get_service", return_value=mock_service):
            result = service_with_integration.push_event(calendar_event)

        assert result == "existing-id-456"
        # Should NOT save google_event_id for updates
        calendar_event.save.assert_not_called()

        # Verify update was called (not insert)
        mock_service.events.return_value.update.assert_called_once()
        call_kwargs = mock_service.events.return_value.update.call_args[1]
        assert call_kwargs["eventId"] == "existing-id-456"


# ===================================================================
# delete_event()
# ===================================================================

class TestDeleteEvent:

    def test_deletes_event(self, service_with_integration):
        mock_service = Mock()

        with patch.object(service_with_integration, "_get_service", return_value=mock_service):
            service_with_integration.delete_event("event-to-delete-789")

        mock_service.events.return_value.delete.assert_called_once()
        call_kwargs = mock_service.events.return_value.delete.call_args[1]
        assert call_kwargs["eventId"] == "event-to-delete-789"
        assert call_kwargs["calendarId"] == "primary"


# ===================================================================
# pull_events() — first sync (no sync token)
# ===================================================================

class TestPullEventsFirstSync:

    def test_first_sync_without_sync_token(self, service_with_integration):
        service_with_integration.integration.sync_token = ""

        mock_service = Mock()
        mock_list = mock_service.events.return_value.list.return_value
        mock_list.execute.return_value = {
            "items": [
                {"id": "ev1", "summary": "Event 1"},
                {"id": "ev2", "summary": "Event 2"},
            ],
            "nextSyncToken": "new-sync-token-abc",
        }

        with patch.object(service_with_integration, "_get_service", return_value=mock_service):
            events = service_with_integration.pull_events()

        assert len(events) == 2
        assert events[0]["id"] == "ev1"

        # Verify sync token was saved
        assert service_with_integration.integration.sync_token == "new-sync-token-abc"
        service_with_integration.integration.save.assert_called()

        # Verify timeMin/timeMax were used (first sync)
        call_kwargs = mock_service.events.return_value.list.call_args[1]
        assert "timeMin" in call_kwargs
        assert "timeMax" in call_kwargs


# ===================================================================
# pull_events() — incremental sync (with sync token)
# ===================================================================

class TestPullEventsIncrementalSync:

    def test_incremental_sync_with_sync_token(self, service_with_integration):
        service_with_integration.integration.sync_token = "existing-sync-token"

        mock_service = Mock()
        mock_list = mock_service.events.return_value.list.return_value
        mock_list.execute.return_value = {
            "items": [{"id": "ev3", "summary": "Updated Event"}],
            "nextSyncToken": "updated-sync-token",
        }

        with patch.object(service_with_integration, "_get_service", return_value=mock_service):
            events = service_with_integration.pull_events()

        assert len(events) == 1
        assert events[0]["summary"] == "Updated Event"

        # Verify syncToken was used (incremental sync)
        call_kwargs = mock_service.events.return_value.list.call_args[1]
        assert call_kwargs["syncToken"] == "existing-sync-token"
        assert "timeMin" not in call_kwargs


# ===================================================================
# pull_events() — pagination
# ===================================================================

class TestPullEventsPagination:

    def test_handles_pagination(self, service_with_integration):
        service_with_integration.integration.sync_token = ""

        mock_service = Mock()

        # Page 1: has nextPageToken
        page1 = {
            "items": [{"id": "ev1"}],
            "nextPageToken": "page-2-token",
        }
        # Page 2: has nextSyncToken (end)
        page2 = {
            "items": [{"id": "ev2"}],
            "nextSyncToken": "final-sync-token",
        }

        mock_list = mock_service.events.return_value.list.return_value
        mock_list.execute.side_effect = [page1, page2]

        with patch.object(service_with_integration, "_get_service", return_value=mock_service):
            events = service_with_integration.pull_events()

        assert len(events) == 2
        assert service_with_integration.integration.sync_token == "final-sync-token"


# ===================================================================
# pull_events() — full sync required error
# ===================================================================

class TestPullEventsFullSyncRequired:

    def test_full_sync_on_410_error(self, service_with_integration):
        service_with_integration.integration.sync_token = "stale-token"

        mock_service = Mock()

        # First call: raises 410 error (sync token stale)
        # Second call (after sync token cleared): returns events normally
        call_count = [0]

        def list_side_effect(**kwargs):
            mock_result = Mock()
            call_count[0] += 1
            if call_count[0] == 1 and "syncToken" in kwargs:
                raise Exception("410 fullSyncRequired")
            mock_result.execute.return_value = {
                "items": [{"id": "ev-fresh"}],
                "nextSyncToken": "fresh-token",
            }
            return mock_result

        mock_service.events.return_value.list = list_side_effect

        with patch.object(service_with_integration, "_get_service", return_value=mock_service):
            events = service_with_integration.pull_events()

        assert len(events) == 1
        assert service_with_integration.integration.sync_token == "fresh-token"

    def test_non_410_error_raises(self, service_with_integration):
        service_with_integration.integration.sync_token = ""

        mock_service = Mock()
        mock_list = mock_service.events.return_value.list.return_value
        mock_list.execute.side_effect = Exception("Some other API error")

        with patch.object(service_with_integration, "_get_service", return_value=mock_service):
            with pytest.raises(Exception, match="Some other API error"):
                service_with_integration.pull_events()


# ===================================================================
# pull_events() — empty result
# ===================================================================

class TestPullEventsEmpty:

    def test_empty_events(self, service_with_integration):
        service_with_integration.integration.sync_token = "tok"

        mock_service = Mock()
        mock_list = mock_service.events.return_value.list.return_value
        mock_list.execute.return_value = {
            "items": [],
            "nextSyncToken": "same-token",
        }

        with patch.object(service_with_integration, "_get_service", return_value=mock_service):
            events = service_with_integration.pull_events()

        assert events == []
        assert service_with_integration.integration.sync_token == "same-token"


# ===================================================================
# SCOPES
# ===================================================================

class TestScopes:

    def test_scopes_defined(self, service):
        assert service.SCOPES == ["https://www.googleapis.com/auth/calendar"]


# ===================================================================
# PKCE code_verifier generation and caching
# ===================================================================

class TestPKCECodeVerifier:

    def test_deterministic_is_consistent(self, service):
        """Same user always generates the same code_verifier."""
        v1 = service._generate_code_verifier()
        v2 = service._generate_code_verifier()
        assert v1 == v2

    def test_different_users_different_verifiers(self):
        """Each user gets a unique code_verifier."""
        user1 = _make_user(email="user1@test.com")
        user2 = _make_user(email="user2@test.com")
        s1 = GoogleCalendarService(user=user1)
        s2 = GoogleCalendarService(user=user2)
        assert s1._generate_code_verifier() != s2._generate_code_verifier()

    def test_verifier_meets_pkce_length_requirements(self, service):
        """PKCE spec requires 43-128 characters."""
        verifier = service._generate_code_verifier()
        assert 43 <= len(verifier) <= 128

    def test_verifier_uses_base64url_charset(self, service):
        """Verifier should only contain base64url-safe characters."""
        import re
        verifier = service._generate_code_verifier()
        assert re.match(r'^[A-Za-z0-9_-]+$', verifier)

    def test_raises_without_user(self, service_no_user):
        """_generate_code_verifier requires a user."""
        with pytest.raises(ValueError, match="User required"):
            service_no_user._generate_code_verifier()

    def test_cache_key_includes_user_id(self, service):
        """Cache key should be unique per user."""
        key = service._cache_key()
        assert str(service.user.id) in key

    @patch("google_auth_oauthlib.flow.Flow.from_client_config")
    def test_full_auth_then_exchange_flow(self, mock_from_config, service):
        """End-to-end: get_auth_url caches verifier, exchange_code uses it."""
        # Setup mock for get_auth_url
        mock_flow_auth = Mock()
        mock_flow_auth.authorization_url.return_value = ("url", "state")

        # Setup mock for exchange_code
        mock_flow_exchange = Mock()
        mock_flow_exchange.credentials = Mock(
            token="t", refresh_token="r", expiry=None
        )

        mock_from_config.side_effect = [mock_flow_auth, mock_flow_exchange]

        # Step 1: get auth URL (caches verifier)
        service.get_auth_url("https://example.com/callback")

        # Verify verifier is cached
        cached_verifier = cache.get(service._cache_key())
        assert cached_verifier is not None

        # Step 2: exchange code (uses cached verifier)
        service.exchange_code("code", "https://example.com/callback")

        # Both calls should use the same verifier
        auth_kwargs = mock_from_config.call_args_list[0][1]
        exchange_kwargs = mock_from_config.call_args_list[1][1]
        assert auth_kwargs["code_verifier"] == exchange_kwargs["code_verifier"]

        # Cache should be cleared after exchange
        assert cache.get(service._cache_key()) is None
