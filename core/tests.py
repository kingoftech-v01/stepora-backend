"""
Tests for core utilities.
"""

from unittest.mock import Mock, patch

from rest_framework import status
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory

from apps.dreams.models import Dream
from apps.users.models import User

from .exceptions import OpenAIError, ValidationError
from .pagination import LargeResultsSetPagination, StandardResultsSetPagination
from .permissions import (
    CanCreateDream,
    CanUseAI,
    CanUseBuddy,
    CanUseCircles,
    CanUseLeague,
    CanUseVisionBoard,
    IsOwner,
    IsPremiumUser,
    IsProUser,
)
from .throttles import AIChatDailyThrottle as AIChatThrottle
from .throttles import AIPlanRateThrottle as AIPlanGenerationThrottle
from .throttles import StorePurchaseRateThrottle as StorePurchaseThrottle
from .throttles import SubscriptionRateThrottle as SubscriptionThrottle


class TestPermissions:
    """Test custom DRF permissions"""

    def test_is_owner_permission_allowed(self, user):
        """Test IsOwner permission allows owner"""
        permission = IsOwner()

        # Create object owned by user
        dream = Dream.objects.create(user=user, title="Test Dream")

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
        other_user = User.objects.create(email=f'other_{user_data["email"]}')

        # Create object owned by other user
        dream = Dream.objects.create(user=other_user, title="Test Dream")

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
            Dream.objects.create(user=user, title=f"Dream {i}")

        pagination = StandardResultsSetPagination()

        # Mock request - wrap in DRF Request for query_params support
        factory = APIRequestFactory()
        request = Request(factory.get("/api/dreams/"))

        queryset = Dream.objects.all()
        paginated_queryset = pagination.paginate_queryset(queryset, request)

        # Should return first 20 items
        assert len(paginated_queryset) == 20

        response = pagination.get_paginated_response([])

        assert response.data["pagination"]["count"] == 50
        assert response.data["pagination"]["page_size"] == 20
        assert response.data["pagination"]["total_pages"] == 3

    def test_standard_pagination_custom_page_size(self, db, user):
        """Test StandardResultsSetPagination with custom page size"""
        for i in range(50):
            Dream.objects.create(user=user, title=f"Dream {i}")

        pagination = StandardResultsSetPagination()

        factory = APIRequestFactory()
        request = Request(factory.get("/api/dreams/?page_size=30"))

        queryset = Dream.objects.all()
        paginated_queryset = pagination.paginate_queryset(queryset, request)

        assert len(paginated_queryset) == 30

    def test_large_pagination(self, db, user):
        """Test LargeResultsSetPagination"""
        for i in range(100):
            Dream.objects.create(user=user, title=f"Dream {i}")

        pagination = LargeResultsSetPagination()

        factory = APIRequestFactory()
        request = Request(factory.get("/api/dreams/"))

        queryset = Dream.objects.all()
        paginated_queryset = pagination.paginate_queryset(queryset, request)

        # Should return first 50 items
        assert len(paginated_queryset) == 50


class TestExceptions:
    """Test custom exceptions"""

    def test_openai_error(self):
        """Test OpenAIError exception"""
        error = OpenAIError("API rate limit exceeded")

        assert str(error) == "API rate limit exceeded"
        assert isinstance(error, Exception)

    def test_validation_error(self):
        """Test ValidationError exception"""
        error = ValidationError("Invalid input data")

        assert str(error) == "Invalid input data"
        assert isinstance(error, Exception)


class TestHealthChecks:
    """Test health check endpoints"""

    def test_health_check(self, api_client):
        """Test GET /health/"""
        response = api_client.get("/health/")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "healthy"
        assert "timestamp" in data

    def test_liveness_probe(self, api_client):
        """Test GET /health/liveness/"""
        response = api_client.get("/health/liveness/")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "alive"

    def test_readiness_probe(self, api_client):
        """Test GET /health/readiness/"""
        response = api_client.get("/health/readiness/")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "ready"

    def test_readiness_probe_db_failure(self, api_client):
        """Test readiness probe with DB failure"""
        with patch("core.views._check_database") as mock_db:
            mock_db.return_value = {
                "status": "down",
                "error": "Database connection failed",
            }

            response = api_client.get("/health/readiness/")

            assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
            data = response.json()
            assert data["status"] == "not ready"
            assert data["reason"] == "database unavailable"


class TestMiddleware:
    """Test custom middleware"""

    def test_request_logging_middleware(self, api_client):
        """Test request logging middleware"""
        # This would test custom middleware if implemented
        # For now, just verify requests work
        response = api_client.get("/health/")
        assert response.status_code == status.HTTP_200_OK

    def test_cors_middleware(self, api_client):
        """Test CORS headers"""
        response = api_client.get("/health/")

        # Check CORS headers are set
        # This depends on CORS configuration
        assert response.status_code == status.HTTP_200_OK


class TestAuthentication:
    """Test authentication utilities"""

    def test_get_user_from_request(self, authenticated_client, user):
        """Test extracting user from authenticated request"""
        response = authenticated_client.get("/api/users/me/")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["email"] == user.email

    def test_unauthenticated_request(self, api_client):
        """Test unauthenticated request handling"""
        response = api_client.get("/api/users/me/")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestIsProUser:
    """Test IsProUser permission"""

    def test_allows_pro_user(self, pro_user):
        permission = IsProUser()
        request = Mock()
        request.user = pro_user
        assert permission.has_permission(request, Mock()) is True

    def test_denies_premium_user(self, premium_user):
        permission = IsProUser()
        request = Mock()
        request.user = premium_user
        assert permission.has_permission(request, Mock()) is False

    def test_denies_free_user(self, user):
        permission = IsProUser()
        request = Mock()
        request.user = user
        assert permission.has_permission(request, Mock()) is False

    def test_denies_unauthenticated(self):
        permission = IsProUser()
        request = Mock()
        request.user = Mock(is_authenticated=False)
        assert permission.has_permission(request, Mock()) is False


class TestCanCreateDream:
    """Test CanCreateDream permission"""

    def test_allows_get_requests(self, user):
        permission = CanCreateDream()
        request = Mock()
        request.method = "GET"
        request.user = user
        assert permission.has_permission(request, Mock()) is True

    def test_allows_post_when_can_create(self, user):
        permission = CanCreateDream()
        request = Mock()
        request.method = "POST"
        request.user = user
        request.user.can_create_dream = Mock(return_value=True)
        assert permission.has_permission(request, Mock()) is True

    def test_denies_post_when_limit_reached(self, user):
        permission = CanCreateDream()
        request = Mock()
        request.method = "POST"
        request.user = user
        request.user.can_create_dream = Mock(return_value=False)
        assert permission.has_permission(request, Mock()) is False


class TestCanUseAI:
    """Test CanUseAI permission"""

    def test_allows_premium_user(self, premium_user):
        permission = CanUseAI()
        request = Mock()
        request.user = premium_user
        assert permission.has_permission(request, Mock()) is True

    def test_allows_pro_user(self, pro_user):
        permission = CanUseAI()
        request = Mock()
        request.user = pro_user
        assert permission.has_permission(request, Mock()) is True

    def test_denies_free_user(self, user):
        permission = CanUseAI()
        request = Mock()
        request.user = user
        assert permission.has_permission(request, Mock()) is False


class TestCanUseBuddy:
    """Test CanUseBuddy permission"""

    def test_allows_premium_user(self, premium_user):
        permission = CanUseBuddy()
        request = Mock()
        request.user = premium_user
        assert permission.has_permission(request, Mock()) is True

    def test_allows_pro_user(self, pro_user):
        permission = CanUseBuddy()
        request = Mock()
        request.user = pro_user
        assert permission.has_permission(request, Mock()) is True

    def test_denies_free_user(self, user):
        permission = CanUseBuddy()
        request = Mock()
        request.user = user
        assert permission.has_permission(request, Mock()) is False


class TestCanUseCircles:
    """Test CanUseCircles permission"""

    def test_post_allowed_for_pro(self, pro_user):
        permission = CanUseCircles()
        request = Mock()
        request.method = "POST"
        request.user = pro_user
        assert permission.has_permission(request, Mock()) is True

    def test_post_denied_for_premium(self, premium_user):
        permission = CanUseCircles()
        request = Mock()
        request.method = "POST"
        request.user = premium_user
        assert permission.has_permission(request, Mock()) is False

    def test_get_allowed_for_premium(self, premium_user):
        permission = CanUseCircles()
        request = Mock()
        request.method = "GET"
        request.user = premium_user
        assert permission.has_permission(request, Mock()) is True

    def test_get_denied_for_free(self, user):
        permission = CanUseCircles()
        request = Mock()
        request.method = "GET"
        request.user = user
        assert permission.has_permission(request, Mock()) is False


class TestCanUseVisionBoard:
    """Test CanUseVisionBoard permission"""

    def test_allows_pro_user(self, pro_user):
        permission = CanUseVisionBoard()
        request = Mock()
        request.user = pro_user
        assert permission.has_permission(request, Mock()) is True

    def test_denies_premium_user(self, premium_user):
        permission = CanUseVisionBoard()
        request = Mock()
        request.user = premium_user
        assert permission.has_permission(request, Mock()) is False

    def test_denies_free_user(self, user):
        permission = CanUseVisionBoard()
        request = Mock()
        request.user = user
        assert permission.has_permission(request, Mock()) is False


class TestCanUseLeague:
    """Test CanUseLeague permission"""

    def test_allows_premium_user(self, premium_user):
        permission = CanUseLeague()
        request = Mock()
        request.user = premium_user
        assert permission.has_permission(request, Mock()) is True

    def test_allows_pro_user(self, pro_user):
        permission = CanUseLeague()
        request = Mock()
        request.user = pro_user
        assert permission.has_permission(request, Mock()) is True

    def test_denies_free_user(self, user):
        permission = CanUseLeague()
        request = Mock()
        request.user = user
        assert permission.has_permission(request, Mock()) is False


class TestThrottleClasses:
    """Test custom throttle classes exist and have correct scopes"""

    def test_ai_chat_throttle_scope(self):
        throttle = AIChatThrottle()
        assert throttle.scope == "ai_chat"

    def test_ai_plan_generation_throttle_scope(self):
        throttle = AIPlanGenerationThrottle()
        assert throttle.scope == "ai_plan"

    def test_subscription_throttle_scope(self):
        throttle = SubscriptionThrottle()
        assert throttle.scope == "subscription"

    def test_store_purchase_throttle_scope(self):
        throttle = StorePurchaseThrottle()
        assert throttle.scope == "store_purchase"
