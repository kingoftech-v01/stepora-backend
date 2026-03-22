"""
Tests for core modules:
- core/storage.py     -- S3 storage backends and presigned URL generation
- core/pagination.py  -- DRF pagination classes
- core/exceptions.py  -- custom exception handler and exception classes
- core/sanitizers.py  -- XSS sanitization utilities
- core/audit.py       -- security audit logging
"""

import logging
from unittest.mock import Mock, patch

import pytest
from rest_framework.exceptions import (
    AuthenticationFailed,
    NotFound,
    PermissionDenied,
    Throttled,
)
from rest_framework.exceptions import (
    ValidationError as DRFValidationError,
)

# ── storage.py tests ────────────────────────────────────────────────────


class TestPresignedUrl:
    """Tests for presigned_url function."""

    def test_presigned_url_empty_file_field(self):
        """presigned_url returns empty string for empty/None file field."""
        from core.storage import presigned_url

        assert presigned_url(None) == ""
        assert presigned_url("") == ""

    @patch("core.storage._get_s3_client")
    def test_presigned_url_local_dev(self, mock_get_client):
        """presigned_url returns file.url when no bucket configured."""
        from core.storage import presigned_url

        mock_file = Mock()
        mock_file.__bool__ = Mock(return_value=True)
        mock_file.url = "/media/test/file.jpg"

        with patch("core.storage.settings") as mock_settings:
            mock_settings.AWS_STORAGE_BUCKET_NAME = None
            result = presigned_url(mock_file)
            assert result == "/media/test/file.jpg"

    @patch("core.storage._get_s3_client")
    def test_presigned_url_s3(self, mock_get_client):
        """presigned_url generates pre-signed URL when bucket is configured."""
        from core.storage import presigned_url

        mock_client = Mock()
        mock_client.generate_presigned_url.return_value = "https://s3.example.com/presigned"
        mock_get_client.return_value = mock_client

        mock_file = Mock()
        mock_file.__bool__ = Mock(return_value=True)
        mock_file.name = "avatars/test.jpg"

        with patch("core.storage.settings") as mock_settings:
            mock_settings.AWS_STORAGE_BUCKET_NAME = "my-bucket"
            mock_settings.AWS_MEDIA_LOCATION = "media"
            result = presigned_url(mock_file, expires_in=7200)

        assert result == "https://s3.example.com/presigned"
        mock_client.generate_presigned_url.assert_called_once_with(
            "get_object",
            Params={"Bucket": "my-bucket", "Key": "media/avatars/test.jpg"},
            ExpiresIn=7200,
        )


class TestReleasesStorage:
    """Tests for ReleasesStorage class."""

    @patch.dict("os.environ", {}, clear=False)
    def test_releases_storage_defaults(self):
        """ReleasesStorage uses default bucket and region."""
        from core.storage import ReleasesStorage

        # Just verify it can be instantiated without errors
        storage = ReleasesStorage()
        assert storage.bucket_name == "stepora-releases"
        assert storage.default_acl == "private"
        assert storage.querystring_auth is True

    @patch.dict(
        "os.environ",
        {
            "AWS_RELEASES_BUCKET": "custom-releases",
            "AWS_RELEASES_REGION": "us-east-1",
            "AWS_RELEASES_CUSTOM_DOMAIN": "cdn.example.com",
        },
    )
    def test_releases_storage_custom_env(self):
        """ReleasesStorage respects environment variables."""
        from core.storage import ReleasesStorage

        storage = ReleasesStorage()
        assert storage.bucket_name == "custom-releases"
        assert storage.custom_domain == "cdn.example.com"


class TestGetS3Client:
    """Tests for _get_s3_client singleton."""

    @patch("core.storage.boto3")
    def test_get_s3_client_creates_client(self, mock_boto3):
        """_get_s3_client creates boto3 S3 client on first call."""
        import core.storage

        # Reset the singleton
        core.storage._s3_client = None

        mock_boto3.client.return_value = Mock()
        client = core.storage._get_s3_client()
        assert client is not None
        mock_boto3.client.assert_called_once()

        # Reset after test
        core.storage._s3_client = None


# ── pagination.py tests ─────────────────────────────────────────────────


class TestStandardLimitOffsetPagination:
    """Tests for StandardLimitOffsetPagination."""

    def test_default_limit(self):
        """Default limit is 20."""
        from core.pagination import StandardLimitOffsetPagination

        paginator = StandardLimitOffsetPagination()
        assert paginator.default_limit == 20

    def test_max_limit(self):
        """Max limit is 100."""
        from core.pagination import StandardLimitOffsetPagination

        paginator = StandardLimitOffsetPagination()
        assert paginator.max_limit == 100


class TestLargeLimitOffsetPagination:
    """Tests for LargeLimitOffsetPagination."""

    def test_default_limit(self):
        """Default limit is 50."""
        from core.pagination import LargeLimitOffsetPagination

        paginator = LargeLimitOffsetPagination()
        assert paginator.default_limit == 50

    def test_max_limit(self):
        """Max limit is 200."""
        from core.pagination import LargeLimitOffsetPagination

        paginator = LargeLimitOffsetPagination()
        assert paginator.max_limit == 200


class TestStandardResultsSetPagination:
    """Tests for StandardResultsSetPagination."""

    def test_page_size(self):
        """Default page size is 20."""
        from core.pagination import StandardResultsSetPagination

        paginator = StandardResultsSetPagination()
        assert paginator.page_size == 20

    def test_max_page_size(self):
        """Max page size is 100."""
        from core.pagination import StandardResultsSetPagination

        paginator = StandardResultsSetPagination()
        assert paginator.max_page_size == 100

    def test_page_size_query_param(self):
        """page_size query parameter is 'page_size'."""
        from core.pagination import StandardResultsSetPagination

        paginator = StandardResultsSetPagination()
        assert paginator.page_size_query_param == "page_size"

    def test_get_paginated_response_structure(self):
        """get_paginated_response returns correct structure with pagination metadata."""
        from core.pagination import StandardResultsSetPagination

        paginator = StandardResultsSetPagination()

        # Mock the paginator's page object
        mock_page = Mock()
        mock_page.paginator.count = 100
        mock_page.paginator.num_pages = 5
        mock_page.number = 2
        mock_page.has_next.return_value = True
        mock_page.has_previous.return_value = True
        mock_page.next_page_number.return_value = 3
        mock_page.previous_page_number.return_value = 1

        paginator.page = mock_page
        paginator.request = Mock()
        paginator.request.build_absolute_uri = Mock(
            return_value="http://test.com/api/items/?page=2"
        )

        response = paginator.get_paginated_response([{"id": 1}])
        data = response.data

        assert "pagination" in data
        assert "results" in data
        assert data["pagination"]["count"] == 100
        assert data["pagination"]["total_pages"] == 5
        assert data["pagination"]["current_page"] == 2
        assert data["pagination"]["page_size"] == 20


class TestLargeResultsSetPagination:
    """Tests for LargeResultsSetPagination."""

    def test_page_size(self):
        """Default page size is 50."""
        from core.pagination import LargeResultsSetPagination

        paginator = LargeResultsSetPagination()
        assert paginator.page_size == 50

    def test_max_page_size(self):
        """Max page size is 200."""
        from core.pagination import LargeResultsSetPagination

        paginator = LargeResultsSetPagination()
        assert paginator.max_page_size == 200


# ── exceptions.py tests ─────────────────────────────────────────────────


class TestExtractMessage:
    """Tests for _extract_message helper."""

    def test_string_detail(self):
        """String detail returns as-is."""
        from core.exceptions import _extract_message

        assert _extract_message("An error occurred") == "An error occurred"

    def test_list_detail(self):
        """List detail returns first item."""
        from core.exceptions import _extract_message

        assert _extract_message(["Error 1", "Error 2"]) == "Error 1"

    def test_empty_list(self):
        """Empty list returns 'Unknown error'."""
        from core.exceptions import _extract_message

        assert _extract_message([]) == "Unknown error"

    def test_dict_with_non_field_errors(self):
        """Dict with non_field_errors returns first non-field error."""
        from core.exceptions import _extract_message

        detail = {
            "non_field_errors": ["Credentials invalid"],
            "email": ["Email required"],
        }
        assert _extract_message(detail) == "Credentials invalid"

    def test_dict_field_error(self):
        """Dict without non_field_errors returns first field error."""
        from core.exceptions import _extract_message

        detail = {"email": ["Email is required"]}
        assert _extract_message(detail) == "Email is required"

    def test_dict_non_list_field_error(self):
        """Dict with non-list field value returns it as string."""
        from core.exceptions import _extract_message

        detail = {"email": "Email is required"}
        assert _extract_message(detail) == "Email is required"


class TestCustomExceptionHandler:
    """Tests for custom_exception_handler."""

    def _make_context(self, view=None):
        """Create a mock context dict for the exception handler."""
        return {"view": view, "request": Mock()}

    def test_returns_none_for_unhandled(self):
        """Returns None for exceptions DRF does not handle."""
        from core.exceptions import custom_exception_handler

        result = custom_exception_handler(ValueError("oops"), self._make_context())
        assert result is None

    def test_validation_error_format(self):
        """ValidationError returns structured error response."""
        from core.exceptions import custom_exception_handler

        exc = DRFValidationError({"email": ["This field is required."]})
        response = custom_exception_handler(exc, self._make_context())
        assert response is not None
        assert response.status_code == 400
        assert "error" in response.data
        assert "code" in response.data
        assert "status_code" in response.data

    def test_field_errors_included(self):
        """Field errors are included in response data."""
        from core.exceptions import custom_exception_handler

        exc = DRFValidationError({
            "email": ["This field is required."],
            "password": ["Too short."],
        })
        response = custom_exception_handler(exc, self._make_context())
        assert "field_errors" in response.data
        assert "email" in response.data["field_errors"]
        assert "password" in response.data["field_errors"]

    def test_non_field_errors_not_in_field_errors(self):
        """non_field_errors are not included in field_errors dict."""
        from core.exceptions import custom_exception_handler

        exc = DRFValidationError({
            "non_field_errors": ["Invalid credentials."],
            "email": ["Required"],
        })
        response = custom_exception_handler(exc, self._make_context())
        assert "non_field_errors" not in response.data.get("field_errors", {})

    def test_not_found_error(self):
        """NotFound returns 404 with correct format."""
        from core.exceptions import custom_exception_handler

        exc = NotFound("Object not found")
        response = custom_exception_handler(exc, self._make_context())
        assert response.status_code == 404
        assert "error" in response.data

    def test_authentication_failed(self):
        """AuthenticationFailed returns 401."""
        from core.exceptions import custom_exception_handler

        exc = AuthenticationFailed("Invalid token")
        response = custom_exception_handler(exc, self._make_context())
        assert response.status_code == 401

    def test_permission_denied(self):
        """PermissionDenied returns 403."""
        from core.exceptions import custom_exception_handler

        exc = PermissionDenied("Not allowed")
        response = custom_exception_handler(exc, self._make_context())
        assert response.status_code == 403

    def test_throttled(self):
        """Throttled returns 429."""
        from core.exceptions import custom_exception_handler

        exc = Throttled(wait=60)
        response = custom_exception_handler(exc, self._make_context())
        assert response.status_code == 429

    def test_subscription_required_enrichment(self):
        """403 with subscription_required code includes tier info."""
        from core.exceptions import custom_exception_handler

        exc = PermissionDenied("Subscription required")
        exc.default_code = "subscription_required"
        exc.detail = Mock()
        exc.detail.code = "subscription_required"
        exc.detail.__str__ = Mock(return_value="Subscription required")

        # Put required_tier on the exception itself
        exc.required_tier = "premium"
        exc.feature_name = "ai_coaching"

        response = custom_exception_handler(exc, self._make_context())
        assert response.status_code == 403
        assert response.data.get("required_tier") == "premium"
        assert response.data.get("feature_name") == "ai_coaching"


class TestCustomExceptions:
    """Tests for custom exception classes."""

    def test_openai_error(self):
        """OpenAIError can be raised and caught."""
        from core.exceptions import OpenAIError

        with pytest.raises(OpenAIError):
            raise OpenAIError("API call failed")

    def test_validation_error(self):
        """ValidationError can be raised and caught."""
        from core.exceptions import ValidationError

        with pytest.raises(ValidationError):
            raise ValidationError("Invalid data")

    def test_notification_error(self):
        """NotificationError can be raised and caught."""
        from core.exceptions import NotificationError

        with pytest.raises(NotificationError):
            raise NotificationError("Failed to send")


# ── sanitizers.py tests ─────────────────────────────────────────────────


class TestSanitizeText:
    """Tests for sanitize_text function."""

    def test_none_input(self):
        """None returns empty string."""
        from core.sanitizers import sanitize_text

        assert sanitize_text(None) == ""

    def test_plain_text_unchanged(self):
        """Plain text passes through unchanged."""
        from core.sanitizers import sanitize_text

        assert sanitize_text("Hello World") == "Hello World"

    def test_strips_html_tags(self):
        """HTML tags are removed."""
        from core.sanitizers import sanitize_text

        result = sanitize_text("<b>Bold</b> text")
        assert "<b>" not in result
        assert "Bold" in result

    def test_strips_script_tags(self):
        """Script tags and their content are removed entirely by nh3."""
        from core.sanitizers import sanitize_text

        result = sanitize_text('<script>alert("xss")</script>')
        assert "<script>" not in result
        # nh3 removes script content entirely (not just tags)
        assert result == ""

    def test_strips_script_but_keeps_surrounding_text(self):
        """Script tags removed but surrounding text preserved."""
        from core.sanitizers import sanitize_text

        result = sanitize_text('Hello <script>alert(1)</script> World')
        assert "<script>" not in result
        assert "Hello" in result
        assert "World" in result

    def test_non_string_input(self):
        """Non-string input is converted to string first."""
        from core.sanitizers import sanitize_text

        result = sanitize_text(12345)
        assert result == "12345"

    def test_html_entities_unescaped(self):
        """HTML entities are unescaped after sanitization."""
        from core.sanitizers import sanitize_text

        result = sanitize_text("&amp; &lt; &gt;")
        assert "&" in result


class TestSanitizeHtml:
    """Tests for sanitize_html function."""

    def test_none_input(self):
        """None returns empty string."""
        from core.sanitizers import sanitize_html

        assert sanitize_html(None) == ""

    def test_allowed_tags_kept(self):
        """Allowed tags (p, strong, em, etc.) are preserved."""
        from core.sanitizers import sanitize_html

        result = sanitize_html("<p><strong>Hello</strong></p>")
        assert "<p>" in result
        assert "<strong>" in result

    def test_disallowed_tags_stripped(self):
        """Disallowed tags (script, div, etc.) are removed."""
        from core.sanitizers import sanitize_html

        result = sanitize_html("<div>Content</div>")
        assert "<div>" not in result
        assert "Content" in result

        # Script tags and content are entirely removed by nh3
        result2 = sanitize_html('<script>alert("x")</script>Safe')
        assert "<script>" not in result2
        assert "Safe" in result2

    def test_extra_tags(self):
        """Extra tags parameter allows additional tags."""
        from core.sanitizers import sanitize_html

        result = sanitize_html("<h1>Title</h1>", extra_tags={"h1"})
        assert "<h1>" in result

    def test_non_string_input(self):
        """Non-string input is converted to string."""
        from core.sanitizers import sanitize_html

        result = sanitize_html(42)
        assert result == "42"

    def test_links_with_allowed_schemes(self):
        """Links with http/https schemes are kept."""
        from core.sanitizers import sanitize_html

        result = sanitize_html('<a href="https://example.com">Link</a>')
        assert "https://example.com" in result
        assert "<a" in result


class TestSanitizeUrl:
    """Tests for sanitize_url function."""

    def test_none_input(self):
        """None returns empty string."""
        from core.sanitizers import sanitize_url

        assert sanitize_url(None) == ""

    def test_non_string_input(self):
        """Non-string returns empty string."""
        from core.sanitizers import sanitize_url

        assert sanitize_url(12345) == ""

    def test_valid_https_url(self):
        """Valid HTTPS URL passes through."""
        from core.sanitizers import sanitize_url

        assert sanitize_url("https://example.com") == "https://example.com"

    def test_valid_http_url(self):
        """Valid HTTP URL passes through."""
        from core.sanitizers import sanitize_url

        assert sanitize_url("http://example.com") == "http://example.com"

    def test_valid_mailto(self):
        """Mailto URL passes through."""
        from core.sanitizers import sanitize_url

        assert sanitize_url("mailto:test@example.com") == "mailto:test@example.com"

    def test_javascript_protocol_blocked(self):
        """JavaScript protocol is blocked."""
        from core.sanitizers import sanitize_url

        assert sanitize_url("javascript:alert(1)") == ""

    def test_data_protocol_blocked(self):
        """Data protocol is blocked."""
        from core.sanitizers import sanitize_url

        assert sanitize_url("data:text/html,<script>alert(1)</script>") == ""

    def test_vbscript_blocked(self):
        """VBScript protocol is blocked."""
        from core.sanitizers import sanitize_url

        assert sanitize_url("vbscript:MsgBox(1)") == ""

    def test_event_handlers_blocked(self):
        """URLs with event handlers are blocked."""
        from core.sanitizers import sanitize_url

        assert sanitize_url("https://example.com/onerror=alert(1)") == ""
        assert sanitize_url("https://example.com/onclick=alert(1)") == ""

    def test_script_tag_in_url_blocked(self):
        """URLs with script tags are blocked."""
        from core.sanitizers import sanitize_url

        assert sanitize_url("https://example.com/<script>x</script>") == ""

    def test_ftp_protocol_blocked(self):
        """FTP protocol is blocked (only http/https/mailto allowed)."""
        from core.sanitizers import sanitize_url

        assert sanitize_url("ftp://example.com/file") == ""

    def test_whitespace_stripped(self):
        """Leading/trailing whitespace is stripped."""
        from core.sanitizers import sanitize_url

        assert sanitize_url("  https://example.com  ") == "https://example.com"


class TestSanitizeJsonValues:
    """Tests for sanitize_json_values function."""

    def test_non_dict_input(self):
        """Non-dict input returns as-is."""
        from core.sanitizers import sanitize_json_values

        assert sanitize_json_values("string") == "string"
        assert sanitize_json_values(123) == 123

    def test_sanitizes_string_values(self):
        """String values are sanitized."""
        from core.sanitizers import sanitize_json_values

        data = {"title": "<b>Bold</b> text", "count": 5}
        result = sanitize_json_values(data)
        assert "<b>" not in result["title"]
        assert "Bold" in result["title"]
        assert result["count"] == 5

    def test_recursive_dict(self):
        """Nested dicts are sanitized recursively."""
        from core.sanitizers import sanitize_json_values

        data = {"nested": {"title": "<script>x</script>Hello"}}
        result = sanitize_json_values(data)
        assert "<script>" not in result["nested"]["title"]
        assert "Hello" in result["nested"]["title"]

    def test_list_values(self):
        """List values are sanitized."""
        from core.sanitizers import sanitize_json_values

        data = {"items": ["<b>item1</b>", "<i>item2</i>"]}
        result = sanitize_json_values(data)
        assert "<b>" not in result["items"][0]
        assert "<i>" not in result["items"][1]

    def test_keys_to_sanitize_filter(self):
        """Only specified keys are sanitized when keys_to_sanitize is set."""
        from core.sanitizers import sanitize_json_values

        data = {"title": "<b>Bold</b>", "raw": "<b>Keep</b>"}
        result = sanitize_json_values(data, keys_to_sanitize=["title"])
        assert "<b>" not in result["title"]
        assert "<b>" in result["raw"]

    def test_list_with_dicts(self):
        """Lists containing dicts are sanitized recursively."""
        from core.sanitizers import sanitize_json_values

        data = {"items": [{"name": "<script>x</script>safe"}, {"name": "clean"}]}
        result = sanitize_json_values(data)
        assert "<script>" not in result["items"][0]["name"]
        assert result["items"][1]["name"] == "clean"

    def test_non_string_list_items_preserved(self):
        """Non-string list items are preserved."""
        from core.sanitizers import sanitize_json_values

        data = {"items": [1, 2.5, True, None]}
        result = sanitize_json_values(data)
        assert result["items"] == [1, 2.5, True, None]


class TestCreateSanitizingSerializerMixin:
    """Tests for create_sanitizing_serializer_mixin factory."""

    def test_creates_mixin_class(self):
        """Factory returns a class with to_internal_value method."""
        from core.sanitizers import create_sanitizing_serializer_mixin

        Mixin = create_sanitizing_serializer_mixin(["title", "description"])
        assert hasattr(Mixin, "to_internal_value")


# ── audit.py tests ──────────────────────────────────────────────────────


class TestAuditGetClientIp:
    """Tests for _get_client_ip helper."""

    def test_xff_header(self):
        """Extracts IP from X-Forwarded-For header."""
        from core.audit import _get_client_ip

        request = Mock()
        request.META = {"HTTP_X_FORWARDED_FOR": "1.2.3.4, 5.6.7.8"}
        assert _get_client_ip(request) == "1.2.3.4"

    def test_remote_addr(self):
        """Falls back to REMOTE_ADDR when no XFF header."""
        from core.audit import _get_client_ip

        request = Mock()
        request.META = {"REMOTE_ADDR": "10.0.0.1"}
        assert _get_client_ip(request) == "10.0.0.1"

    def test_no_ip_info(self):
        """Returns 'unknown' when no IP info available."""
        from core.audit import _get_client_ip

        request = Mock()
        request.META = {}
        assert _get_client_ip(request) == "unknown"


class TestAuditLogFunctions:
    """Tests for audit logging functions.

    The 'security' logger may have propagate=False in some settings configs,
    so we temporarily force propagate=True during tests to allow caplog capture.
    """

    @pytest.fixture(autouse=True)
    def _enable_security_logger_propagation(self):
        """Ensure security logger propagates so caplog can capture."""
        logger = logging.getLogger("security")
        old_propagate = logger.propagate
        old_level = logger.level
        logger.propagate = True
        logger.setLevel(logging.DEBUG)
        yield
        logger.propagate = old_propagate
        logger.setLevel(old_level)

    def _make_request(self, path="/test/", ip="1.2.3.4"):
        """Create a mock request with standard META."""
        request = Mock()
        request.META = {"HTTP_X_FORWARDED_FOR": ip}
        request.path = path
        request.user = Mock()
        request.user.id = "user-123"
        return request

    def _make_user(self, user_id="user-456", email="user@test.com"):
        """Create a mock user."""
        user = Mock()
        user.id = user_id
        user.email = email
        return user

    def test_log_auth_failure(self, caplog):
        """log_auth_failure logs at WARNING level."""
        from core.audit import log_auth_failure

        request = self._make_request()
        with caplog.at_level(logging.DEBUG, logger="security"):
            log_auth_failure(request, "bad_password")
        assert "AUTH_FAILURE" in caplog.text
        assert "1.2.3.4" in caplog.text

    def test_log_auth_success(self, caplog):
        """log_auth_success logs at INFO level."""
        from core.audit import log_auth_success

        request = self._make_request()
        user = self._make_user()
        with caplog.at_level(logging.DEBUG, logger="security"):
            log_auth_success(request, user)
        assert "AUTH_SUCCESS" in caplog.text

    def test_log_permission_denied(self, caplog):
        """log_permission_denied logs at WARNING level."""
        from core.audit import log_permission_denied

        request = self._make_request()
        with caplog.at_level(logging.DEBUG, logger="security"):
            log_permission_denied(request, "IsAuthenticated", "UserViewSet")
        assert "PERMISSION_DENIED" in caplog.text

    def test_log_data_export(self, caplog):
        """log_data_export logs at INFO level."""
        from core.audit import log_data_export

        user = self._make_user()
        with caplog.at_level(logging.DEBUG, logger="security"):
            log_data_export(user, "full")
        assert "DATA_EXPORT" in caplog.text

    def test_log_account_change(self, caplog):
        """log_account_change logs at INFO level."""
        from core.audit import log_account_change

        user = self._make_user()
        with caplog.at_level(logging.DEBUG, logger="security"):
            log_account_change(user, "password_change", "via settings")
        assert "ACCOUNT_CHANGE" in caplog.text
        assert "password_change" in caplog.text

    def test_log_webhook_event(self, caplog):
        """log_webhook_event logs at INFO level."""
        from core.audit import log_webhook_event

        with caplog.at_level(logging.DEBUG, logger="security"):
            log_webhook_event("invoice.paid", "evt_123", "processed")
        assert "WEBHOOK" in caplog.text
        assert "invoice.paid" in caplog.text

    def test_log_suspicious_input(self, caplog):
        """log_suspicious_input logs at WARNING level with truncated value."""
        from core.audit import log_suspicious_input

        request = self._make_request()
        with caplog.at_level(logging.DEBUG, logger="security"):
            log_suspicious_input(request, "title", "<script>alert(1)</script>")
        assert "SUSPICIOUS_INPUT" in caplog.text
        assert "title" in caplog.text

    def test_log_ai_output_flagged(self, caplog):
        """log_ai_output_flagged logs at WARNING level."""
        from core.audit import log_ai_output_flagged

        with caplog.at_level(logging.DEBUG, logger="security"):
            log_ai_output_flagged("conv-123", "dangerous content preview", "safety_check")
        assert "AI_OUTPUT_FLAGGED" in caplog.text

    def test_log_jailbreak_attempt(self, caplog):
        """log_jailbreak_attempt logs at CRITICAL level."""
        from core.audit import log_jailbreak_attempt

        request = self._make_request()
        with caplog.at_level(logging.DEBUG, logger="security"):
            log_jailbreak_attempt(request, "Ignore all instructions")
        assert "JAILBREAK_ATTEMPT" in caplog.text

    def test_log_content_moderation(self, caplog):
        """log_content_moderation logs at WARNING level."""
        from core.audit import log_content_moderation

        request = self._make_request()
        mock_result = Mock()
        mock_result.detection_source = "ai"
        mock_result.categories = ["hate", "violence"]
        mock_result.severity = "high"

        with caplog.at_level(logging.DEBUG, logger="security"):
            log_content_moderation(request, "offensive text", mock_result, "post_create")
        assert "CONTENT_MODERATION" in caplog.text

    def test_anonymous_user_handling(self, caplog):
        """Audit functions handle anonymous users (no .id attribute)."""
        from core.audit import log_suspicious_input

        request = Mock()
        request.META = {"REMOTE_ADDR": "10.0.0.1"}
        request.user = Mock(spec=[])  # No .id attribute

        with caplog.at_level(logging.DEBUG, logger="security"):
            log_suspicious_input(request, "field", "value")
        assert "SUSPICIOUS_INPUT" in caplog.text
        assert "anonymous" in caplog.text
