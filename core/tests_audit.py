"""
Tests for security audit logging.
"""

import pytest
import logging
from unittest.mock import Mock, patch, call
from django.test import RequestFactory

from .audit import (
    _get_client_ip,
    log_auth_failure,
    log_auth_success,
    log_permission_denied,
    log_data_export,
    log_account_change,
    log_webhook_event,
    log_suspicious_input,
)


class TestGetClientIp:
    """Tests for _get_client_ip helper."""

    def setup_method(self):
        self.factory = RequestFactory()

    def test_direct_ip(self):
        request = self.factory.get('/api/test/')
        ip = _get_client_ip(request)
        assert ip == '127.0.0.1'

    def test_x_forwarded_for_single(self):
        request = self.factory.get('/api/test/', HTTP_X_FORWARDED_FOR='203.0.113.1')
        ip = _get_client_ip(request)
        assert ip == '203.0.113.1'

    def test_x_forwarded_for_multiple(self):
        request = self.factory.get(
            '/api/test/',
            HTTP_X_FORWARDED_FOR='203.0.113.1, 70.41.3.18, 150.172.238.178'
        )
        ip = _get_client_ip(request)
        assert ip == '203.0.113.1'

    def test_x_forwarded_for_with_spaces(self):
        request = self.factory.get(
            '/api/test/',
            HTTP_X_FORWARDED_FOR='  203.0.113.1  , 70.41.3.18'
        )
        ip = _get_client_ip(request)
        assert ip == '203.0.113.1'

    def test_no_remote_addr(self):
        request = self.factory.get('/api/test/')
        request.META.pop('REMOTE_ADDR', None)
        ip = _get_client_ip(request)
        assert ip == 'unknown'


class TestLogAuthFailure:
    """Tests for log_auth_failure."""

    @patch('core.audit.security_logger')
    def test_logs_warning(self, mock_logger):
        factory = RequestFactory()
        request = factory.get('/api/auth/login/')
        log_auth_failure(request, 'invalid_credentials')
        mock_logger.warning.assert_called_once()
        args = mock_logger.warning.call_args
        assert 'AUTH_FAILURE' in args[0][0]
        assert 'invalid_credentials' in str(args)

    @patch('core.audit.security_logger')
    def test_includes_ip(self, mock_logger):
        factory = RequestFactory()
        request = factory.get('/api/auth/login/', HTTP_X_FORWARDED_FOR='10.0.0.1')
        log_auth_failure(request, 'expired_token')
        args = mock_logger.warning.call_args
        assert '10.0.0.1' in str(args)


class TestLogAuthSuccess:
    """Tests for log_auth_success."""

    @patch('core.audit.security_logger')
    def test_logs_info(self, mock_logger, user):
        factory = RequestFactory()
        request = factory.get('/api/auth/login/')
        log_auth_success(request, user)
        mock_logger.info.assert_called_once()
        args = mock_logger.info.call_args
        assert 'AUTH_SUCCESS' in args[0][0]
        assert user.email in str(args)


class TestLogPermissionDenied:
    """Tests for log_permission_denied."""

    @patch('core.audit.security_logger')
    def test_logs_warning(self, mock_logger, user):
        factory = RequestFactory()
        request = factory.get('/api/conversations/')
        request.user = user
        log_permission_denied(request, 'CanUseAI', 'ConversationViewSet')
        mock_logger.warning.assert_called_once()
        args = mock_logger.warning.call_args
        assert 'PERMISSION_DENIED' in args[0][0]
        assert 'CanUseAI' in str(args)

    @patch('core.audit.security_logger')
    def test_handles_anonymous_user(self, mock_logger):
        factory = RequestFactory()
        request = factory.get('/api/test/')
        request.user = Mock(spec=[])
        log_permission_denied(request, 'IsAuthenticated', 'TestView')
        mock_logger.warning.assert_called_once()
        assert 'anonymous' in str(mock_logger.warning.call_args)


class TestLogDataExport:
    """Tests for log_data_export."""

    @patch('core.audit.security_logger')
    def test_logs_info(self, mock_logger, user):
        log_data_export(user)
        mock_logger.info.assert_called_once()
        args = mock_logger.info.call_args
        assert 'DATA_EXPORT' in args[0][0]
        assert user.email in str(args)
        assert 'full' in str(args)

    @patch('core.audit.security_logger')
    def test_custom_export_type(self, mock_logger, user):
        log_data_export(user, export_type='partial')
        assert 'partial' in str(mock_logger.info.call_args)


class TestLogAccountChange:
    """Tests for log_account_change."""

    @patch('core.audit.security_logger')
    def test_logs_password_change(self, mock_logger, user):
        log_account_change(user, 'password_change')
        mock_logger.info.assert_called_once()
        assert 'ACCOUNT_CHANGE' in str(mock_logger.info.call_args)
        assert 'password_change' in str(mock_logger.info.call_args)

    @patch('core.audit.security_logger')
    def test_logs_account_deletion(self, mock_logger, user):
        log_account_change(user, 'account_deletion')
        assert 'account_deletion' in str(mock_logger.info.call_args)

    @patch('core.audit.security_logger')
    def test_logs_with_details(self, mock_logger, user):
        log_account_change(user, 'email_change', details='old@test.com -> new@test.com')
        assert 'old@test.com -> new@test.com' in str(mock_logger.info.call_args)


class TestLogWebhookEvent:
    """Tests for log_webhook_event."""

    @patch('core.audit.security_logger')
    def test_logs_processed_event(self, mock_logger):
        log_webhook_event('invoice.paid', 'evt_123', 'processed')
        mock_logger.info.assert_called_once()
        args_str = str(mock_logger.info.call_args)
        assert 'WEBHOOK' in args_str
        assert 'invoice.paid' in args_str
        assert 'evt_123' in args_str
        assert 'processed' in args_str

    @patch('core.audit.security_logger')
    def test_logs_failed_event(self, mock_logger):
        log_webhook_event('unknown', 'unknown', 'signature_failed')
        assert 'signature_failed' in str(mock_logger.info.call_args)

    @patch('core.audit.security_logger')
    def test_logs_with_details(self, mock_logger):
        log_webhook_event('checkout.complete', 'evt_456', 'processed', details='sub_id=sub_xyz')
        assert 'sub_id=sub_xyz' in str(mock_logger.info.call_args)


class TestLogSuspiciousInput:
    """Tests for log_suspicious_input."""

    @patch('core.audit.security_logger')
    def test_logs_warning(self, mock_logger, user):
        factory = RequestFactory()
        request = factory.get('/api/test/')
        request.user = user
        log_suspicious_input(request, 'bio', '<script>alert("xss")</script>')
        mock_logger.warning.assert_called_once()
        args_str = str(mock_logger.warning.call_args)
        assert 'SUSPICIOUS_INPUT' in args_str
        assert 'bio' in args_str

    @patch('core.audit.security_logger')
    def test_truncates_long_values(self, mock_logger):
        factory = RequestFactory()
        request = factory.get('/api/test/')
        request.user = Mock(id='user-123')
        long_value = 'x' * 500
        log_suspicious_input(request, 'description', long_value)
        mock_logger.warning.assert_called_once()
        assert 'SUSPICIOUS_INPUT' in str(mock_logger.warning.call_args)

    @patch('core.audit.security_logger')
    def test_handles_anonymous_user(self, mock_logger):
        factory = RequestFactory()
        request = factory.get('/api/test/')
        request.user = Mock(spec=[])
        log_suspicious_input(request, 'name', '<b>test</b>')
        assert 'anonymous' in str(mock_logger.warning.call_args)
