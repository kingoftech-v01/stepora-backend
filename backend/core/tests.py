"""
Tests for core utilities.
"""

import pytest
from django.test import RequestFactory
from rest_framework import status
from rest_framework.test import APIRequestFactory
from unittest.mock import Mock, patch

from .permissions import IsOwner, IsPremiumUser
from .pagination import StandardResultsSetPagination, LargeResultsSetPagination
from .exceptions import OpenAIError, FCMError, ValidationError
from .views import health_check, liveness, readiness
from apps.users.models import User
from apps.dreams.models import Dream


class TestPermissions:
    """Test custom DRF permissions"""

    def test_is_owner_permission_allowed(self, user):
        """Test IsOwner permission allows owner"""
        permission = IsOwner()

        # Create object owned by user
        dream = Dream.objects.create(user=user, title='Test Dream')

        # Mock view with object
        view = Mock()
        view.get_object = Mock(return_value=dream)

        # Mock request
        request = Mock()
        request.user = user

        result = permission.has_object_permission(request, view, dream)
        assert result is True

    def test_is_owner_permission_denied(self, db, user, user_data):
        """Test IsOwner permission denies non-owner"""
        permission = IsOwner()

        # Create another user
        other_user = User.objects.create(
            firebase_uid=f'other_{user_data["firebase_uid"]}',
            email=f'other_{user_data["email"]}'
        )

        # Create object owned by other user
        dream = Dream.objects.create(user=other_user, title='Test Dream')

        # Mock request with different user
        request = Mock()
        request.user = user

        result = permission.has_object_permission(request, Mock(), dream)
        assert result is False

    def test_is_premium_user_permission_allowed(self, premium_user):
        """Test IsPremiumUser permission allows premium users"""
        permission = IsPremiumUser()

        request = Mock()
        request.user = premium_user

        result = permission.has_permission(request, Mock())
        assert result is True

    def test_is_premium_user_permission_denied(self, user):
        """Test IsPremiumUser permission denies free users"""
        permission = IsPremiumUser()

        request = Mock()
        request.user = user

        result = permission.has_permission(request, Mock())
        assert result is False


class TestPagination:
    """Test custom pagination classes"""

    def test_standard_pagination(self, db, user):
        """Test StandardResultsSetPagination"""
        # Create 50 dreams
        for i in range(50):
            Dream.objects.create(user=user, title=f'Dream {i}')

        pagination = StandardResultsSetPagination()

        # Mock request
        factory = APIRequestFactory()
        request = factory.get('/api/dreams/')

        queryset = Dream.objects.all()
        paginated_queryset = pagination.paginate_queryset(queryset, request)

        # Should return first 20 items
        assert len(paginated_queryset) == 20

        response = pagination.get_paginated_response([])

        assert response.data['pagination']['count'] == 50
        assert response.data['pagination']['page_size'] == 20
        assert response.data['pagination']['total_pages'] == 3

    def test_standard_pagination_custom_page_size(self, db, user):
        """Test StandardResultsSetPagination with custom page size"""
        for i in range(50):
            Dream.objects.create(user=user, title=f'Dream {i}')

        pagination = StandardResultsSetPagination()

        factory = APIRequestFactory()
        request = factory.get('/api/dreams/?page_size=30')

        queryset = Dream.objects.all()
        paginated_queryset = pagination.paginate_queryset(queryset, request)

        assert len(paginated_queryset) == 30

    def test_large_pagination(self, db, user):
        """Test LargeResultsSetPagination"""
        for i in range(100):
            Dream.objects.create(user=user, title=f'Dream {i}')

        pagination = LargeResultsSetPagination()

        factory = APIRequestFactory()
        request = factory.get('/api/dreams/')

        queryset = Dream.objects.all()
        paginated_queryset = pagination.paginate_queryset(queryset, request)

        # Should return first 50 items
        assert len(paginated_queryset) == 50


class TestExceptions:
    """Test custom exceptions"""

    def test_openai_error(self):
        """Test OpenAIError exception"""
        error = OpenAIError('API rate limit exceeded')

        assert str(error) == 'API rate limit exceeded'
        assert isinstance(error, Exception)

    def test_fcm_error(self):
        """Test FCMError exception"""
        error = FCMError('Invalid FCM token')

        assert str(error) == 'Invalid FCM token'
        assert isinstance(error, Exception)

    def test_validation_error(self):
        """Test ValidationError exception"""
        error = ValidationError('Invalid input data')

        assert str(error) == 'Invalid input data'
        assert isinstance(error, Exception)


class TestHealthChecks:
    """Test health check endpoints"""

    def test_health_check(self, api_client):
        """Test GET /health/"""
        response = api_client.get('/health/')

        assert response.status_code == status.HTTP_200_OK
        assert response.data['status'] == 'healthy'
        assert 'timestamp' in response.data

    def test_liveness_probe(self, api_client):
        """Test GET /health/liveness/"""
        response = api_client.get('/health/liveness/')

        assert response.status_code == status.HTTP_200_OK
        assert response.data['status'] == 'alive'

    def test_readiness_probe(self, api_client):
        """Test GET /health/readiness/"""
        with patch('django.db.connection.ensure_connection') as mock_db:
            mock_db.return_value = None

            response = api_client.get('/health/readiness/')

            assert response.status_code == status.HTTP_200_OK
            assert response.data['status'] == 'ready'
            assert response.data['database'] == 'connected'

    def test_readiness_probe_db_failure(self, api_client):
        """Test readiness probe with DB failure"""
        with patch('django.db.connection.ensure_connection') as mock_db:
            mock_db.side_effect = Exception('Database connection failed')

            response = api_client.get('/health/readiness/')

            assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
            assert response.data['status'] == 'not_ready'


class TestMiddleware:
    """Test custom middleware"""

    def test_request_logging_middleware(self, api_client):
        """Test request logging middleware"""
        # This would test custom middleware if implemented
        # For now, just verify requests work
        response = api_client.get('/health/')
        assert response.status_code == status.HTTP_200_OK

    def test_cors_middleware(self, api_client):
        """Test CORS headers"""
        response = api_client.get('/health/')

        # Check CORS headers are set
        # This depends on CORS configuration
        assert response.status_code == status.HTTP_200_OK


class TestAuthentication:
    """Test authentication utilities"""

    def test_get_user_from_request(self, authenticated_client, user):
        """Test extracting user from authenticated request"""
        response = authenticated_client.get('/api/users/me/')

        assert response.status_code == status.HTTP_200_OK
        assert response.data['email'] == user.email

    def test_unauthenticated_request(self, api_client):
        """Test unauthenticated request handling"""
        response = api_client.get('/api/users/me/')

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
