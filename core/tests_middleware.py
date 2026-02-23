"""
Tests for SecurityHeadersMiddleware and LastActivityMiddleware.
"""

import pytest
import time
from unittest.mock import patch, Mock, MagicMock
from django.test import RequestFactory, override_settings
from django.http import HttpResponse
from rest_framework.test import APIClient

from .middleware import SecurityHeadersMiddleware, LastActivityMiddleware
from .authentication import CsrfExemptAPIMiddleware


class TestSecurityHeadersMiddleware:
    """Tests for the SecurityHeadersMiddleware."""

    def setup_method(self):
        self.factory = RequestFactory()
        self.get_response = Mock(return_value=HttpResponse('OK'))
        self.middleware = SecurityHeadersMiddleware(self.get_response)

    def test_csp_header_present(self):
        request = self.factory.get('/api/test/')
        response = self.middleware(request)
        assert 'Content-Security-Policy' in response

    def test_csp_default_value(self):
        request = self.factory.get('/api/test/')
        response = self.middleware(request)
        csp = response['Content-Security-Policy']
        assert "default-src 'self'" in csp
        assert "script-src 'self'" in csp
        assert "frame-ancestors 'none'" in csp

    @override_settings(CSP_POLICY="default-src 'none'")
    def test_csp_custom_value(self):
        request = self.factory.get('/api/test/')
        response = self.middleware(request)
        assert response['Content-Security-Policy'] == "default-src 'none'"

    def test_referrer_policy_present(self):
        request = self.factory.get('/api/test/')
        response = self.middleware(request)
        assert response['Referrer-Policy'] == 'strict-origin-when-cross-origin'

    def test_permissions_policy_present(self):
        request = self.factory.get('/api/test/')
        response = self.middleware(request)
        policy = response['Permissions-Policy']
        assert 'geolocation=()' in policy
        assert 'microphone=()' in policy
        assert 'camera=()' in policy
        assert 'payment=()' in policy

    def test_x_content_type_options(self):
        request = self.factory.get('/api/test/')
        response = self.middleware(request)
        assert response['X-Content-Type-Options'] == 'nosniff'

    def test_x_frame_options_deny(self):
        request = self.factory.get('/api/test/')
        response = self.middleware(request)
        assert response['X-Frame-Options'] == 'DENY'

    def test_coop_header(self):
        request = self.factory.get('/api/test/')
        response = self.middleware(request)
        assert response['Cross-Origin-Opener-Policy'] == 'same-origin'

    def test_corp_header(self):
        request = self.factory.get('/api/test/')
        response = self.middleware(request)
        assert response['Cross-Origin-Resource-Policy'] == 'same-origin'

    def test_headers_on_api_endpoint(self, api_client):
        response = api_client.get('/health/')
        assert response['Content-Security-Policy'] is not None
        assert response['Referrer-Policy'] is not None
        assert response['X-Frame-Options'] == 'DENY'

    def test_headers_on_all_status_codes(self):
        error_response = HttpResponse('Error', status=500)
        self.get_response.return_value = error_response
        request = self.factory.get('/api/test/')
        response = self.middleware(request)
        assert response['Content-Security-Policy'] is not None
        assert response.status_code == 500

    def test_headers_on_post_request(self):
        request = self.factory.post('/api/test/')
        response = self.middleware(request)
        assert 'Content-Security-Policy' in response

    def test_headers_on_non_api_path(self):
        request = self.factory.get('/admin/')
        response = self.middleware(request)
        assert 'Content-Security-Policy' in response


class TestLastActivityMiddleware:
    """Tests for the LastActivityMiddleware."""

    def setup_method(self):
        self.get_response = Mock(return_value=HttpResponse('OK'))
        self.middleware = LastActivityMiddleware(self.get_response)
        self.factory = RequestFactory()

    def test_updates_authenticated_user(self, user):
        request = self.factory.get('/api/test/')
        request.user = user

        self.middleware(request)

        user.refresh_from_db()
        assert user.is_online is True
        assert user.last_seen is not None

    def test_skips_unauthenticated_request(self):
        request = self.factory.get('/api/test/')
        request.user = Mock(is_authenticated=False)

        response = self.middleware(request)
        assert response.status_code == 200

    def test_throttles_updates(self, user):
        request = self.factory.get('/api/test/')
        request.user = user

        # First call updates
        self.middleware(request)

        # Second call within 60 seconds should be throttled
        with patch('apps.users.models.User.objects') as mock_objects:
            self.middleware(request)
            mock_objects.filter.assert_not_called()

    def test_updates_after_throttle_window(self, user):
        request = self.factory.get('/api/test/')
        request.user = user

        # First call
        self.middleware(request)

        # Simulate time passing beyond throttle window
        self.middleware._cache[user.id] = time.time() - 61

        with patch('apps.users.models.User.objects.filter') as mock_filter:
            mock_filter.return_value = Mock(update=Mock())
            self.middleware(request)
            mock_filter.assert_called_once()

    def test_handles_db_error_gracefully(self, user):
        request = self.factory.get('/api/test/')
        request.user = user

        # Reset cache to force update
        self.middleware._cache.clear()

        with patch('apps.users.models.User.objects.filter') as mock_filter:
            mock_filter.side_effect = Exception('DB error')
            # Should not raise
            response = self.middleware(request)
            assert response.status_code == 200

    def test_passes_request_to_get_response(self):
        request = self.factory.get('/api/test/')
        request.user = Mock(is_authenticated=False)

        self.middleware(request)
        self.get_response.assert_called_once_with(request)


class TestCsrfExemptAPIMiddleware:
    """Tests for CsrfExemptAPIMiddleware."""

    def setup_method(self):
        self.get_response = Mock(return_value=HttpResponse('OK'))
        self.middleware = CsrfExemptAPIMiddleware(self.get_response)
        self.factory = RequestFactory()

    def test_api_with_token_exempts_csrf(self):
        request = self.factory.get('/api/test/')
        request.META['HTTP_AUTHORIZATION'] = 'Token abc123'

        self.middleware(request)
        assert getattr(request, '_dont_enforce_csrf_checks', False) is True

    def test_api_with_bearer_exempts_csrf(self):
        request = self.factory.get('/api/test/')
        request.META['HTTP_AUTHORIZATION'] = 'Bearer abc123'

        self.middleware(request)
        assert getattr(request, '_dont_enforce_csrf_checks', False) is True

    def test_api_without_token_no_csrf_exempt(self):
        request = self.factory.get('/api/test/')

        self.middleware(request)
        assert getattr(request, '_dont_enforce_csrf_checks', False) is False

    def test_non_api_path_no_csrf_exempt(self):
        request = self.factory.get('/admin/')
        request.META['HTTP_AUTHORIZATION'] = 'Token abc123'

        self.middleware(request)
        assert getattr(request, '_dont_enforce_csrf_checks', False) is False

    def test_api_with_invalid_prefix_no_exempt(self):
        request = self.factory.get('/api/test/')
        request.META['HTTP_AUTHORIZATION'] = 'Basic abc123'

        self.middleware(request)
        assert getattr(request, '_dont_enforce_csrf_checks', False) is False

    def test_passes_response_through(self):
        request = self.factory.get('/api/test/')
        response = self.middleware(request)
        assert response.status_code == 200
        self.get_response.assert_called_once_with(request)
