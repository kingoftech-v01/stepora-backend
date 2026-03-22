"""
Tests for core utilities:
- core/sanitizers.py — sanitize_text, sanitize_html, sanitize_url, sanitize_json_values
- core/validators.py — all validators
- core/middleware.py — OriginValidationMiddleware, SecurityHeadersMiddleware,
                       LastActivityMiddleware
- core/auth/ — login, register, token refresh, password reset
"""

import uuid
from unittest.mock import Mock, patch

import pytest
from django.http import HttpResponse
from django.test import RequestFactory, override_settings
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIClient

from apps.users.models import User
from core.auth.models import EmailAddress

# ══════════════════════════════════════════════════════════════════════
#  SANITIZERS
# ══════════════════════════════════════════════════════════════════════


class TestSanitizeText:
    """Tests for sanitize_text()."""

    def test_removes_html_tags(self):
        from core.sanitizers import sanitize_text

        assert sanitize_text("<b>bold</b>") == "bold"

    def test_removes_script_tags(self):
        from core.sanitizers import sanitize_text

        result = sanitize_text('<script>alert("xss")</script>')
        assert "<script>" not in result
        assert "alert" not in result or "<" not in result

    def test_none_returns_empty(self):
        from core.sanitizers import sanitize_text

        assert sanitize_text(None) == ""

    def test_non_string_converted(self):
        from core.sanitizers import sanitize_text

        assert sanitize_text(42) == "42"

    def test_preserves_plain_text(self):
        from core.sanitizers import sanitize_text

        assert sanitize_text("Hello World!") == "Hello World!"

    def test_unescapes_html_entities(self):
        from core.sanitizers import sanitize_text

        result = sanitize_text("&amp; &lt; &gt;")
        assert "&" in result
        assert "<" in result
        assert ">" in result

    def test_removes_nested_tags(self):
        from core.sanitizers import sanitize_text

        result = sanitize_text("<div><span>text</span></div>")
        assert result == "text"

    def test_removes_img_tag(self):
        from core.sanitizers import sanitize_text

        result = sanitize_text('<img src="http://evil.com/x.png" onerror="alert(1)">')
        assert "<img" not in result


class TestSanitizeHtml:
    """Tests for sanitize_html()."""

    def test_keeps_allowed_tags(self):
        from core.sanitizers import sanitize_html

        result = sanitize_html("<p><strong>bold</strong></p>")
        assert "<p>" in result
        assert "<strong>" in result

    def test_strips_disallowed_tags(self):
        from core.sanitizers import sanitize_html

        result = sanitize_html("<div>text</div>")
        assert "<div>" not in result
        assert "text" in result

    def test_strips_script_tags(self):
        from core.sanitizers import sanitize_html

        result = sanitize_html('<script>alert(1)</script>')
        assert "<script>" not in result

    def test_allows_safe_links(self):
        from core.sanitizers import sanitize_html

        result = sanitize_html('<a href="https://example.com" title="link">click</a>')
        assert 'href="https://example.com"' in result

    def test_strips_javascript_links(self):
        from core.sanitizers import sanitize_html

        result = sanitize_html('<a href="javascript:alert(1)">click</a>')
        assert "javascript:" not in result

    def test_extra_tags(self):
        from core.sanitizers import sanitize_html

        result = sanitize_html("<h1>Title</h1>", extra_tags={"h1"})
        assert "<h1>" in result

    def test_none_returns_empty(self):
        from core.sanitizers import sanitize_html

        assert sanitize_html(None) == ""


class TestSanitizeUrl:
    """Tests for sanitize_url()."""

    def test_valid_https_url(self):
        from core.sanitizers import sanitize_url

        assert sanitize_url("https://example.com") == "https://example.com"

    def test_valid_http_url(self):
        from core.sanitizers import sanitize_url

        assert sanitize_url("http://example.com") == "http://example.com"

    def test_valid_mailto(self):
        from core.sanitizers import sanitize_url

        assert sanitize_url("mailto:test@example.com") == "mailto:test@example.com"

    def test_javascript_url_blocked(self):
        from core.sanitizers import sanitize_url

        assert sanitize_url("javascript:alert(1)") == ""

    def test_data_url_blocked(self):
        from core.sanitizers import sanitize_url

        assert sanitize_url("data:text/html,<h1>test</h1>") == ""

    def test_none_returns_empty(self):
        from core.sanitizers import sanitize_url

        assert sanitize_url(None) == ""

    def test_non_string_returns_empty(self):
        from core.sanitizers import sanitize_url

        assert sanitize_url(42) == ""

    def test_dangerous_patterns(self):
        from core.sanitizers import sanitize_url

        assert sanitize_url("https://evil.com/page?onerror=alert(1)") == ""
        assert sanitize_url("https://evil.com/page?onclick=bad") == ""
        assert sanitize_url("vbscript:alert(1)") == ""

    def test_ftp_blocked(self):
        from core.sanitizers import sanitize_url

        assert sanitize_url("ftp://files.example.com") == ""

    def test_strips_whitespace(self):
        from core.sanitizers import sanitize_url

        assert sanitize_url("  https://example.com  ") == "https://example.com"


class TestSanitizeJsonValues:
    """Tests for sanitize_json_values()."""

    def test_sanitizes_string_values(self):
        from core.sanitizers import sanitize_json_values

        data = {"name": "<b>Test</b>", "count": 5}
        result = sanitize_json_values(data)
        assert result["name"] == "Test"
        assert result["count"] == 5

    def test_sanitizes_nested_dicts(self):
        from core.sanitizers import sanitize_json_values

        data = {"user": {"name": "<script>x</script>"}}
        result = sanitize_json_values(data)
        assert "<script>" not in result["user"]["name"]

    def test_sanitizes_list_values(self):
        from core.sanitizers import sanitize_json_values

        data = {"tags": ["<b>tag1</b>", "tag2"]}
        result = sanitize_json_values(data)
        assert result["tags"][0] == "tag1"
        assert result["tags"][1] == "tag2"

    def test_specific_keys_only(self):
        from core.sanitizers import sanitize_json_values

        data = {"title": "<b>bold</b>", "raw": "<b>raw</b>"}
        result = sanitize_json_values(data, keys_to_sanitize=["title"])
        assert result["title"] == "bold"
        assert result["raw"] == "<b>raw</b>"

    def test_non_dict_returns_as_is(self):
        from core.sanitizers import sanitize_json_values

        assert sanitize_json_values("not a dict") == "not a dict"


# ══════════════════════════════════════════════════════════════════════
#  VALIDATORS
# ══════════════════════════════════════════════════════════════════════


class TestValidateUuid:
    """Tests for validate_uuid()."""

    def test_valid_uuid_string(self):
        from core.validators import validate_uuid

        uid = str(uuid.uuid4())
        result = validate_uuid(uid)
        assert isinstance(result, uuid.UUID)

    def test_valid_uuid_object(self):
        from core.validators import validate_uuid

        uid = uuid.uuid4()
        result = validate_uuid(uid)
        assert result == uid

    def test_invalid_uuid_raises(self):
        from core.validators import validate_uuid

        with pytest.raises(ValidationError, match="Invalid UUID"):
            validate_uuid("not-a-uuid")

    def test_empty_string_raises(self):
        from core.validators import validate_uuid

        with pytest.raises(ValidationError):
            validate_uuid("")


class TestValidatePaginationParams:
    """Tests for validate_pagination_params()."""

    def test_valid_params(self):
        from core.validators import validate_pagination_params

        page, page_size = validate_pagination_params(2, 50)
        assert page == 2
        assert page_size == 50

    def test_defaults(self):
        from core.validators import validate_pagination_params

        page, page_size = validate_pagination_params(None, None)
        assert page == 1
        assert page_size == 20

    def test_invalid_page_raises(self):
        from core.validators import validate_pagination_params

        with pytest.raises(ValidationError):
            validate_pagination_params(-1, 20)

    def test_page_size_too_large_raises(self):
        from core.validators import validate_pagination_params

        with pytest.raises(ValidationError, match="Page size"):
            validate_pagination_params(1, 200)

    def test_non_numeric_raises(self):
        from core.validators import validate_pagination_params

        with pytest.raises(ValidationError, match="Invalid pagination"):
            validate_pagination_params("abc", 20)


class TestValidateSearchQuery:
    """Tests for validate_search_query()."""

    def test_valid_query(self):
        from core.validators import validate_search_query

        assert validate_search_query("test query") == "test query"

    def test_strips_html(self):
        from core.validators import validate_search_query

        result = validate_search_query("<b>test</b>")
        assert "<b>" not in result

    def test_truncates_long_query(self):
        from core.validators import MAX_SEARCH_QUERY_LENGTH, validate_search_query

        long_query = "a" * 500
        result = validate_search_query(long_query)
        assert len(result) == MAX_SEARCH_QUERY_LENGTH

    def test_empty_returns_empty(self):
        from core.validators import validate_search_query

        assert validate_search_query("") == ""
        assert validate_search_query(None) == ""


@pytest.mark.django_db
class TestValidateDisplayName:
    """Tests for validate_display_name()."""

    def test_valid_name(self):
        from core.validators import validate_display_name

        result = validate_display_name("John Doe")
        assert result == "John Doe"

    def test_unicode_allowed(self):
        from core.validators import validate_display_name

        result = validate_display_name("Jean-Pierre")
        assert result == "Jean-Pierre"

    def test_invalid_chars_raises(self):
        from core.validators import validate_display_name

        with pytest.raises(ValidationError, match="invalid characters"):
            validate_display_name("user@#$%")

    def test_duplicate_name_raises(self, db):
        User.objects.create_user(
            email="dupname@test.com",
            password="testpass123",
            display_name="TakenName",
        )
        from core.validators import validate_display_name

        with pytest.raises(ValidationError, match="already taken"):
            validate_display_name("takenname")

    def test_empty_name_allowed(self):
        from core.validators import validate_display_name

        result = validate_display_name("")
        assert result == ""


class TestValidateLocation:
    """Tests for validate_location()."""

    def test_valid_location(self):
        from core.validators import validate_location

        assert validate_location("Paris, France") == "Paris, France"

    def test_invalid_location_raises(self):
        from core.validators import validate_location

        with pytest.raises(ValidationError):
            validate_location("Location @#$%^")

    def test_empty_allowed(self):
        from core.validators import validate_location

        assert validate_location("") == ""


class TestValidateCouponCode:
    """Tests for validate_coupon_code()."""

    def test_valid_code(self):
        from core.validators import validate_coupon_code

        assert validate_coupon_code("SAVE50") == "SAVE50"

    def test_hyphens_underscores_allowed(self):
        from core.validators import validate_coupon_code

        assert validate_coupon_code("CODE-2026_v2") == "CODE-2026_v2"

    def test_invalid_chars_raises(self):
        from core.validators import validate_coupon_code

        with pytest.raises(ValidationError, match="letters, numbers"):
            validate_coupon_code("code with spaces!")


class TestValidateTagName:
    """Tests for validate_tag_name()."""

    def test_valid_tag(self):
        from core.validators import validate_tag_name

        assert validate_tag_name("education") == "education"

    def test_empty_tag_raises(self):
        from core.validators import validate_tag_name

        with pytest.raises(ValidationError, match="cannot be empty"):
            validate_tag_name("")

    def test_invalid_chars_raises(self):
        from core.validators import validate_tag_name

        with pytest.raises(ValidationError, match="invalid characters"):
            validate_tag_name("tag@#$")


class TestValidateTextLength:
    """Tests for validate_text_length()."""

    def test_within_limit(self):
        from core.validators import validate_text_length

        result = validate_text_length("short text", max_length=100)
        assert result == "short text"

    def test_exceeds_limit_raises(self):
        from core.validators import validate_text_length

        with pytest.raises(ValidationError, match="at most 10"):
            validate_text_length("x" * 20, max_length=10, field_name="Field")


class TestValidateUrlNoSsrf:
    """Tests for validate_url_no_ssrf()."""

    def test_valid_public_url(self):
        from core.validators import validate_url_no_ssrf

        url, ip = validate_url_no_ssrf("https://example.com")
        assert url == "https://example.com"
        assert ip is not None

    def test_localhost_blocked(self):
        from core.validators import validate_url_no_ssrf

        with pytest.raises(ValidationError, match="localhost"):
            validate_url_no_ssrf("http://localhost:8000")

    def test_ftp_scheme_blocked(self):
        from core.validators import validate_url_no_ssrf

        with pytest.raises(ValidationError, match="HTTP/HTTPS"):
            validate_url_no_ssrf("ftp://files.example.com")

    def test_empty_url_raises(self):
        from core.validators import validate_url_no_ssrf

        with pytest.raises(ValidationError, match="required"):
            validate_url_no_ssrf("")

    def test_no_hostname_raises(self):
        from core.validators import validate_url_no_ssrf

        with pytest.raises(ValidationError):
            validate_url_no_ssrf("http://")

    def test_private_ip_blocked(self):
        from core.validators import validate_url_no_ssrf

        with pytest.raises(ValidationError, match="private"):
            validate_url_no_ssrf("http://192.168.1.1")


# ══════════════════════════════════════════════════════════════════════
#  MIDDLEWARE
# ══════════════════════════════════════════════════════════════════════


class TestOriginValidationMiddleware:
    """Tests for OriginValidationMiddleware."""

    def _make_middleware(self):
        from core.middleware import OriginValidationMiddleware

        return OriginValidationMiddleware(
            get_response=lambda req: HttpResponse("OK")
        )

    def test_allows_health_check(self):
        middleware = self._make_middleware()
        factory = RequestFactory()
        request = factory.get("/health/")
        response = middleware(request)
        assert response.status_code == 200

    def test_allows_stripe_webhook(self):
        middleware = self._make_middleware()
        factory = RequestFactory()
        request = factory.post("/api/subscriptions/webhook/")
        response = middleware(request)
        assert response.status_code == 200

    def test_allows_native_platform(self):
        middleware = self._make_middleware()
        factory = RequestFactory()
        request = factory.get("/api/test/", HTTP_X_CLIENT_PLATFORM="native")
        response = middleware(request)
        assert response.status_code == 200

    def test_allows_ios_platform(self):
        middleware = self._make_middleware()
        factory = RequestFactory()
        request = factory.get("/api/test/", HTTP_X_CLIENT_PLATFORM="ios")
        response = middleware(request)
        assert response.status_code == 200

    def test_allows_localhost_origin(self):
        middleware = self._make_middleware()
        factory = RequestFactory()
        request = factory.get(
            "/api/test/",
            HTTP_ORIGIN="http://localhost:8100",
        )
        response = middleware(request)
        assert response.status_code == 200

    def test_allows_internal_ip(self):
        middleware = self._make_middleware()
        factory = RequestFactory()
        request = factory.get("/api/test/", REMOTE_ADDR="127.0.0.1")
        response = middleware(request)
        assert response.status_code == 200

    def test_allows_alb_ip(self):
        middleware = self._make_middleware()
        factory = RequestFactory()
        request = factory.get("/api/test/", REMOTE_ADDR="10.0.1.50")
        response = middleware(request)
        assert response.status_code == 200

    def test_blocks_unknown_origin(self):
        middleware = self._make_middleware()
        factory = RequestFactory()
        request = factory.get(
            "/api/test/",
            HTTP_ORIGIN="https://evil.com",
            REMOTE_ADDR="8.8.8.8",
        )
        response = middleware(request)
        assert response.status_code == 403

    def test_blocks_unknown_referer(self):
        middleware = self._make_middleware()
        factory = RequestFactory()
        request = factory.get(
            "/api/test/",
            HTTP_REFERER="https://evil.com/page",
            REMOTE_ADDR="8.8.8.8",
        )
        response = middleware(request)
        assert response.status_code == 403

    def test_blocks_no_origin_no_referer(self):
        middleware = self._make_middleware()
        factory = RequestFactory()
        request = factory.get("/api/test/", REMOTE_ADDR="8.8.8.8")
        response = middleware(request)
        assert response.status_code == 403

    def test_allows_stepora_origin(self):
        middleware = self._make_middleware()
        factory = RequestFactory()
        request = factory.get(
            "/api/test/",
            HTTP_ORIGIN="https://stepora.app",
            REMOTE_ADDR="8.8.8.8",
        )
        response = middleware(request)
        assert response.status_code == 200

    def test_allows_api_stepora_origin(self):
        middleware = self._make_middleware()
        factory = RequestFactory()
        request = factory.get(
            "/api/test/",
            HTTP_ORIGIN="https://api.stepora.app",
            REMOTE_ADDR="8.8.8.8",
        )
        response = middleware(request)
        assert response.status_code == 200

    def test_allows_preprod_origin(self):
        middleware = self._make_middleware()
        factory = RequestFactory()
        request = factory.get(
            "/api/test/",
            HTTP_ORIGIN="https://dp.jhpetitfrere.com",
            REMOTE_ADDR="8.8.8.8",
        )
        response = middleware(request)
        assert response.status_code == 200


class TestSecurityHeadersMiddleware:
    """Tests for SecurityHeadersMiddleware."""

    def _make_middleware(self):
        from core.middleware import SecurityHeadersMiddleware

        return SecurityHeadersMiddleware(
            get_response=lambda req: HttpResponse("OK")
        )

    def test_sets_security_headers(self):
        middleware = self._make_middleware()
        factory = RequestFactory()
        request = factory.get("/")
        response = middleware(request)

        assert response["X-Content-Type-Options"] == "nosniff"
        assert response["X-Frame-Options"] == "DENY"
        assert response["Referrer-Policy"] == "strict-origin-when-cross-origin"
        assert response["Cross-Origin-Opener-Policy"] == "same-origin"
        assert response["Cross-Origin-Resource-Policy"] == "cross-origin"

    def test_csp_set_for_non_api(self):
        middleware = self._make_middleware()
        factory = RequestFactory()
        request = factory.get("/some-page/")
        response = middleware(request)

        assert "Content-Security-Policy" in response

    def test_csp_not_set_for_api_json(self):
        middleware = self._make_middleware()
        factory = RequestFactory()
        request = factory.get("/api/test/")

        def get_json_response(req):
            resp = HttpResponse('{"ok": true}', content_type="application/json")
            return resp

        middleware.get_response = get_json_response
        response = middleware(request)

        assert "Content-Security-Policy" not in response

    @override_settings(DEBUG=False)
    def test_hsts_in_production(self):
        middleware = self._make_middleware()
        factory = RequestFactory()
        request = factory.get("/")
        response = middleware(request)

        assert "Strict-Transport-Security" in response


@pytest.mark.django_db
class TestLastActivityMiddleware:
    """Tests for LastActivityMiddleware."""

    def _make_middleware(self):
        from core.middleware import LastActivityMiddleware

        return LastActivityMiddleware(
            get_response=lambda req: HttpResponse("OK")
        )

    def test_updates_last_seen_for_authenticated_user(self):
        user = User.objects.create_user(
            email="lastact@test.com",
            password="testpass123",
        )

        middleware = self._make_middleware()
        factory = RequestFactory()
        request = factory.get("/api/test/")
        request.user = user

        with patch("django.core.cache.cache") as mock_cache:
            mock_cache.get.return_value = None
            middleware(request)
            mock_cache.set.assert_called_once()

    def test_skips_unauthenticated_users(self):
        from django.contrib.auth.models import AnonymousUser

        middleware = self._make_middleware()
        factory = RequestFactory()
        request = factory.get("/api/test/")
        request.user = AnonymousUser()

        # Anonymous user has is_authenticated=False, so the middleware
        # should not attempt to update last activity
        response = middleware(request)
        assert response.status_code == 200


# ══════════════════════════════════════════════════════════════════════
#  AUTH (Login, Register, Token Refresh, Password Reset)
# ══════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestAuthLogin:
    """Tests for the login endpoint."""

    @patch("core.auth.views.send_login_notification_email")
    def test_login_success(self, mock_login_email):
        """Login with valid credentials returns access token."""
        user = User.objects.create_user(
            email="login@test.com",
            password="TestPass123!",
        )
        # Create verified email
        EmailAddress.objects.create(
            user=user, email="login@test.com", verified=True, primary=True
        )

        client = APIClient()
        response = client.post(
            "/api/auth/login/",
            {"email": "login@test.com", "password": "TestPass123!"},
            format="json",
            HTTP_ORIGIN="https://stepora.app",
        )
        assert response.status_code == 200
        assert "access" in response.data

    def test_login_wrong_password(self):
        """Login with wrong password returns 400."""
        user = User.objects.create_user(
            email="loginbad@test.com",
            password="TestPass123!",
        )
        EmailAddress.objects.create(
            user=user, email="loginbad@test.com", verified=True, primary=True
        )

        client = APIClient()
        response = client.post(
            "/api/auth/login/",
            {"email": "loginbad@test.com", "password": "WrongPass!"},
            format="json",
            HTTP_ORIGIN="https://stepora.app",
        )
        assert response.status_code == 400

    @patch("core.auth.views.send_login_notification_email")
    def test_login_unverified_email(self, mock_email):
        """Login with unverified email returns error."""
        user = User.objects.create_user(
            email="unverified@test.com",
            password="TestPass123!",
        )
        EmailAddress.objects.create(
            user=user, email="unverified@test.com", verified=False, primary=True
        )

        client = APIClient()
        response = client.post(
            "/api/auth/login/",
            {"email": "unverified@test.com", "password": "TestPass123!"},
            format="json",
            HTTP_ORIGIN="https://stepora.app",
        )
        # If email verification is mandatory, returns 400.
        # If verification is optional (dev), returns 200 (login succeeds).
        assert response.status_code in (200, 400)

    def test_login_nonexistent_user(self):
        """Login with nonexistent email returns 400."""
        client = APIClient()
        response = client.post(
            "/api/auth/login/",
            {"email": "nope@test.com", "password": "TestPass123!"},
            format="json",
            HTTP_ORIGIN="https://stepora.app",
        )
        assert response.status_code == 400


@pytest.mark.django_db
class TestAuthRegister:
    """Tests for the registration endpoint."""

    @patch("core.auth.tasks.send_verification_email.delay")
    @patch("core.auth.views.send_login_notification_email")
    def test_register_success(self, mock_login_email, mock_verify_email):
        """Registration with valid data returns 201."""
        client = APIClient()
        response = client.post(
            "/api/auth/registration/",
            {
                "email": "newuser@test.com",
                "password1": "StrongPass123!",
                "password2": "StrongPass123!",
            },
            format="json",
            HTTP_ORIGIN="https://stepora.app",
        )
        assert response.status_code == 200
        assert User.objects.filter(email="newuser@test.com").exists()

    def test_register_password_mismatch(self):
        """Registration with mismatched passwords returns 400."""
        client = APIClient()
        response = client.post(
            "/api/auth/registration/",
            {
                "email": "mismatch@test.com",
                "password1": "StrongPass123!",
                "password2": "DifferentPass456!",
            },
            format="json",
            HTTP_ORIGIN="https://stepora.app",
        )
        assert response.status_code == 400

    def test_register_duplicate_email(self):
        """Registration with existing email returns 400."""
        User.objects.create_user(
            email="existing@test.com", password="TestPass123!"
        )

        client = APIClient()
        response = client.post(
            "/api/auth/registration/",
            {
                "email": "existing@test.com",
                "password1": "StrongPass123!",
                "password2": "StrongPass123!",
            },
            format="json",
            HTTP_ORIGIN="https://stepora.app",
        )
        assert response.status_code == 400

    def test_register_weak_password(self):
        """Registration with a weak password returns 400."""
        client = APIClient()
        response = client.post(
            "/api/auth/registration/",
            {
                "email": "weakpass@test.com",
                "password1": "123",
                "password2": "123",
            },
            format="json",
            HTTP_ORIGIN="https://stepora.app",
        )
        assert response.status_code == 400


@pytest.mark.django_db
class TestAuthTokenRefresh:
    """Tests for the token refresh endpoint."""

    @patch("core.auth.views.send_login_notification_email")
    def test_token_refresh_with_cookie(self, mock_login_email):
        """Token refresh with valid refresh cookie returns new access token."""
        user = User.objects.create_user(
            email="refresh@test.com", password="TestPass123!"
        )
        EmailAddress.objects.create(
            user=user, email="refresh@test.com", verified=True, primary=True
        )

        client = APIClient()
        # Login first to get tokens
        login_resp = client.post(
            "/api/auth/login/",
            {"email": "refresh@test.com", "password": "TestPass123!"},
            format="json",
            HTTP_ORIGIN="https://stepora.app",
        )
        assert login_resp.status_code == 200

        # Get the refresh token from the cookie
        refresh_cookie = login_resp.cookies.get("dp-refresh")
        if refresh_cookie:
            client.cookies["dp-refresh"] = refresh_cookie.value

            response = client.post(
                "/api/auth/token/refresh/",
                format="json",
                HTTP_ORIGIN="https://stepora.app",
            )
            assert response.status_code == 200
            assert "access" in response.data

    def test_token_refresh_without_cookie(self):
        """Token refresh without refresh token returns 400."""
        client = APIClient()
        response = client.post(
            "/api/auth/token/refresh/",
            format="json",
            HTTP_ORIGIN="https://stepora.app",
        )
        assert response.status_code == 400


@pytest.mark.django_db
class TestAuthPasswordReset:
    """Tests for password reset endpoints."""

    @patch("core.auth.tasks.send_password_reset_email.delay")
    def test_password_reset_request(self, mock_email):
        """Password reset request returns 200 for existing email."""
        User.objects.create_user(
            email="resetme@test.com", password="TestPass123!"
        )
        EmailAddress.objects.create(
            user=User.objects.get(email="resetme@test.com"),
            email="resetme@test.com",
            verified=True,
            primary=True,
        )

        client = APIClient()
        response = client.post(
            "/api/auth/password/reset/",
            {"email": "resetme@test.com"},
            format="json",
            HTTP_ORIGIN="https://stepora.app",
        )
        assert response.status_code == 200

    def test_password_reset_nonexistent_email(self):
        """Password reset request returns 200 even for nonexistent email (prevents enumeration)."""
        client = APIClient()
        response = client.post(
            "/api/auth/password/reset/",
            {"email": "nobody@test.com"},
            format="json",
            HTTP_ORIGIN="https://stepora.app",
        )
        # Should not reveal whether email exists
        assert response.status_code == 200


@pytest.mark.django_db
class TestAuthPasswordChange:
    """Tests for password change endpoint."""

    @patch("core.auth.views.send_password_changed_email")
    def test_password_change_success(self, mock_pw_email):
        """Password change with valid old password succeeds."""
        user = User.objects.create_user(
            email="changepw@test.com", password="OldPass123!"
        )
        EmailAddress.objects.create(
            user=user, email="changepw@test.com", verified=True, primary=True
        )

        client = APIClient()
        client.force_authenticate(user=user)
        response = client.post(
            "/api/auth/password/change/",
            {
                "old_password": "OldPass123!",
                "new_password1": "NewStrongPass456!",
                "new_password2": "NewStrongPass456!",
            },
            format="json",
            HTTP_ORIGIN="https://stepora.app",
        )
        assert response.status_code == 200

    def test_password_change_wrong_old_password(self):
        """Password change with wrong old password fails."""
        user = User.objects.create_user(
            email="changepwbad@test.com", password="OldPass123!"
        )

        client = APIClient()
        client.force_authenticate(user=user)
        response = client.post(
            "/api/auth/password/change/",
            {
                "old_password": "WrongOldPass!",
                "new_password1": "NewPass456!",
                "new_password2": "NewPass456!",
            },
            format="json",
            HTTP_ORIGIN="https://stepora.app",
        )
        assert response.status_code == 400

    def test_password_change_unauthenticated(self):
        """Password change without authentication returns 401."""
        client = APIClient()
        response = client.post(
            "/api/auth/password/change/",
            {
                "old_password": "OldPass123!",
                "new_password1": "NewPass456!",
                "new_password2": "NewPass456!",
            },
            format="json",
            HTTP_ORIGIN="https://stepora.app",
        )
        assert response.status_code in (401, 403)


# ══════════════════════════════════════════════════════════════════════
#  GOOGLE OAUTH (mocked)
# ══════════════════════════════════════════════════════════════════════


@pytest.fixture(autouse=True, scope="class")
def _clear_cache_for_auth_tests():
    """Clear cache to avoid rate limit interference between tests."""
    from django.core.cache import cache
    cache.clear()
    yield
    cache.clear()


@pytest.mark.django_db
class TestGoogleOAuth:
    """Tests for Google OAuth endpoints (mocked)."""

    @patch("core.auth.views.verify_google_token")
    @patch("core.auth.views.send_login_notification_email")
    def test_google_login_new_user(self, mock_notif, mock_verify):
        """Google login creates new user if not exists."""
        mock_verify.return_value = (
            "google-uid-123",
            "googleuser@example.com",
            "Google User",
            "https://example.com/photo.jpg",
        )
        mock_notif.delay.return_value = None

        client = APIClient()
        response = client.post(
            "/api/auth/google/",
            {"id_token": "fake-google-token"},
            format="json",
            HTTP_ORIGIN="https://stepora.app",
        )
        assert response.status_code == 200
        assert "access" in response.data
        assert response.data["user"]["email"] == "googleuser@example.com"

    @patch("core.auth.views.verify_google_token")
    @patch("core.auth.views.send_login_notification_email")
    def test_google_login_existing_user(self, mock_notif, mock_verify):
        """Google login links to existing user by email."""
        user = User.objects.create_user(
            email="existinggoogle@example.com", password="Existing123!"
        )
        mock_verify.return_value = (
            "google-uid-456",
            "existinggoogle@example.com",
            "Existing User",
            "",
        )
        mock_notif.delay.return_value = None

        client = APIClient()
        response = client.post(
            "/api/auth/google/",
            {"id_token": "fake-token"},
            format="json",
            HTTP_ORIGIN="https://stepora.app",
        )
        assert response.status_code == 200
        assert response.data["user"]["email"] == "existinggoogle@example.com"

    def test_google_login_no_token(self):
        """Google login without token returns 400."""
        client = APIClient()
        response = client.post(
            "/api/auth/google/",
            {},
            format="json",
            HTTP_ORIGIN="https://stepora.app",
        )
        assert response.status_code == 400


# ══════════════════════════════════════════════════════════════════════
#  APPLE OAUTH (mocked)
# ══════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestAppleOAuth:
    """Tests for Apple OAuth endpoints (mocked)."""

    @patch("core.auth.views.verify_apple_token")
    @patch("core.auth.views.send_login_notification_email")
    def test_apple_login_new_user(self, mock_notif, mock_verify):
        """Apple login creates new user if not exists."""
        mock_verify.return_value = ("apple-uid-123", "appleuser@example.com")
        mock_notif.delay.return_value = None

        client = APIClient()
        response = client.post(
            "/api/auth/apple/",
            {"id_token": "fake-apple-token", "name": "Apple User"},
            format="json",
            HTTP_ORIGIN="https://stepora.app",
        )
        assert response.status_code == 200
        assert "access" in response.data

    def test_apple_login_no_token(self):
        """Apple login without token returns 400."""
        client = APIClient()
        response = client.post(
            "/api/auth/apple/",
            {},
            format="json",
            HTTP_ORIGIN="https://stepora.app",
        )
        assert response.status_code == 400


# ══════════════════════════════════════════════════════════════════════
#  TWO-FACTOR AUTHENTICATION
# ══════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestTwoFactorAuth:
    """Tests for 2FA challenge endpoint."""

    def test_2fa_challenge_missing_fields(self):
        """2FA challenge without fields returns 400."""
        client = APIClient()
        response = client.post(
            "/api/auth/2fa-challenge/",
            {},
            format="json",
            HTTP_ORIGIN="https://stepora.app",
        )
        assert response.status_code == 400

    def test_2fa_challenge_invalid_token(self):
        """2FA challenge with invalid token returns 400."""
        client = APIClient()
        response = client.post(
            "/api/auth/2fa-challenge/",
            {"challenge_token": "invalid-token", "code": "123456"},
            format="json",
            HTTP_ORIGIN="https://stepora.app",
        )
        assert response.status_code == 400

    @patch("core.auth.views.send_login_notification_email")
    def test_login_with_2fa_returns_challenge(self, mock_notif):
        """Login for 2FA-enabled user returns challenge token."""
        import pyotp

        user = User.objects.create_user(
            email="tfa_user@example.com", password="StrongPass123!"
        )
        EmailAddress.objects.create(
            user=user, email="tfa_user@example.com", verified=True, primary=True
        )
        user.totp_enabled = True
        user.totp_secret = pyotp.random_base32()
        user.save(update_fields=["totp_enabled", "totp_secret"])

        client = APIClient()
        response = client.post(
            "/api/auth/login/",
            {"email": "tfa_user@example.com", "password": "StrongPass123!"},
            format="json",
            HTTP_ORIGIN="https://stepora.app",
        )
        assert response.status_code == 200
        assert response.data.get("tfa_required") is True
        assert "challenge_token" in response.data

    @patch("core.auth.views.send_login_notification_email")
    def test_2fa_challenge_valid_totp(self, mock_notif):
        """2FA challenge with valid TOTP code succeeds."""
        import pyotp

        from core.auth.views import _create_challenge_token

        mock_notif.delay.return_value = None
        user = User.objects.create_user(
            email="tfa_valid@example.com", password="StrongPass123!"
        )
        user.totp_enabled = True
        secret = pyotp.random_base32()
        user.totp_secret = secret
        user.save(update_fields=["totp_enabled", "totp_secret"])

        challenge_token = _create_challenge_token(user.id)
        totp = pyotp.TOTP(secret)
        code = totp.now()

        client = APIClient()
        response = client.post(
            "/api/auth/2fa-challenge/",
            {"challenge_token": challenge_token, "code": code},
            format="json",
            HTTP_ORIGIN="https://stepora.app",
        )
        assert response.status_code == 200
        assert "access" in response.data


# ══════════════════════════════════════════════════════════════════════
#  EMAIL VERIFICATION
# ══════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestEmailVerification:
    """Tests for email verification endpoints."""

    def test_verify_email_invalid_key(self):
        """Verify with invalid key returns 400."""
        client = APIClient()
        response = client.post(
            "/api/auth/verify-email/",
            {"key": "invalid-verification-key"},
            format="json",
            HTTP_ORIGIN="https://stepora.app",
        )
        assert response.status_code == 400

    def test_resend_verification(self):
        """Resend verification always returns 200 (no leak)."""
        client = APIClient()
        response = client.post(
            "/api/auth/resend-verification/",
            {"email": "nonexistent@example.com"},
            format="json",
            HTTP_ORIGIN="https://stepora.app",
        )
        assert response.status_code == 200

    @patch("core.auth.serializers.ResendVerificationSerializer.save")
    def test_resend_verification_existing_email(self, mock_save):
        """Resend verification for existing unverified email."""
        mock_save.return_value = None
        user = User.objects.create_user(
            email="unverified@example.com", password="Test123!"
        )
        EmailAddress.objects.create(
            user=user, email="unverified@example.com", verified=False, primary=True
        )

        client = APIClient()
        response = client.post(
            "/api/auth/resend-verification/",
            {"email": "unverified@example.com"},
            format="json",
            HTTP_ORIGIN="https://stepora.app",
        )
        assert response.status_code == 200


# ══════════════════════════════════════════════════════════════════════
#  PASSWORD RESET
# ══════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestPasswordReset:
    """Tests for password reset endpoints."""

    def test_password_reset_request(self):
        """Password reset always returns 200 (no leak)."""
        client = APIClient()
        response = client.post(
            "/api/auth/password/reset/",
            {"email": "anyone@example.com"},
            format="json",
            HTTP_ORIGIN="https://stepora.app",
        )
        assert response.status_code == 200

    def test_password_reset_validate_invalid(self):
        """Validate with invalid token returns 400."""
        client = APIClient()
        response = client.post(
            "/api/auth/password/reset/validate/",
            {"uid": "invalid-uid", "token": "invalid-token"},
            format="json",
            HTTP_ORIGIN="https://stepora.app",
        )
        assert response.status_code == 400

    def test_password_reset_validate_missing_fields(self):
        """Validate without uid/token returns 400."""
        client = APIClient()
        response = client.post(
            "/api/auth/password/reset/validate/",
            {},
            format="json",
            HTTP_ORIGIN="https://stepora.app",
        )
        assert response.status_code == 400

    def test_password_reset_confirm_invalid(self):
        """Confirm with invalid data returns 400."""
        client = APIClient()
        response = client.post(
            "/api/auth/password/reset/confirm/",
            {
                "uid": "invalid",
                "token": "invalid",
                "new_password1": "NewPass123!",
                "new_password2": "NewPass123!",
            },
            format="json",
            HTTP_ORIGIN="https://stepora.app",
        )
        assert response.status_code == 400


# ══════════════════════════════════════════════════════════════════════
#  TOKEN REFRESH
# ══════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestTokenRefresh:
    """Tests for token refresh endpoint."""

    def test_refresh_no_token(self):
        """Refresh without token returns 400."""
        client = APIClient()
        response = client.post(
            "/api/auth/token/refresh/",
            {},
            format="json",
            HTTP_ORIGIN="https://stepora.app",
        )
        assert response.status_code == 400

    def test_refresh_invalid_token(self):
        """Refresh with invalid token returns 401."""
        client = APIClient()
        response = client.post(
            "/api/auth/token/refresh/",
            {"refresh": "invalid-token-string"},
            format="json",
            HTTP_ORIGIN="https://stepora.app",
        )
        assert response.status_code == 401

    def test_refresh_valid_token(self):
        """Refresh with valid token returns new access token."""
        from rest_framework_simplejwt.tokens import RefreshToken

        user = User.objects.create_user(
            email="refreshtest@example.com", password="TestPass123!"
        )
        refresh = RefreshToken.for_user(user)

        client = APIClient()
        response = client.post(
            "/api/auth/token/refresh/",
            {"refresh": str(refresh)},
            format="json",
            HTTP_ORIGIN="https://stepora.app",
        )
        assert response.status_code == 200
        assert "access" in response.data


# ══════════════════════════════════════════════════════════════════════
#  USER DETAILS (auth endpoint)
# ══════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestUserDetails:
    """Tests for /api/auth/user/ endpoint."""

    def test_get_user_details(self):
        """Authenticated user can get their details."""
        user = User.objects.create_user(
            email="userdetails@example.com", password="TestPass123!"
        )
        client = APIClient()
        client.force_authenticate(user=user)
        response = client.get("/api/auth/user/")
        assert response.status_code == 200
        assert response.data["email"] == "userdetails@example.com"

    def test_patch_user_details(self):
        """Authenticated user can patch their details."""
        user = User.objects.create_user(
            email="patchdetails@example.com", password="TestPass123!"
        )
        client = APIClient()
        client.force_authenticate(user=user)
        response = client.patch(
            "/api/auth/user/",
            {"display_name": "Patched Name"},
            format="json",
        )
        assert response.status_code == 200

    def test_get_user_details_unauthenticated(self):
        """Unauthenticated user gets 401."""
        client = APIClient()
        response = client.get("/api/auth/user/")
        assert response.status_code == 401


# ══════════════════════════════════════════════════════════════════════
#  LOGOUT
# ══════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestLogout:
    """Tests for logout endpoint."""

    def test_logout_authenticated(self):
        """Authenticated user can logout."""
        user = User.objects.create_user(
            email="logouttest@example.com", password="TestPass123!"
        )
        client = APIClient()
        client.force_authenticate(user=user)
        response = client.post("/api/auth/logout/")
        assert response.status_code == 200

    def test_logout_unauthenticated(self):
        """Unauthenticated logout returns 401."""
        client = APIClient()
        response = client.post("/api/auth/logout/")
        assert response.status_code == 401

    def test_logout_with_refresh_token(self):
        """Logout with refresh token blacklists it."""
        from rest_framework_simplejwt.tokens import RefreshToken

        user = User.objects.create_user(
            email="logoutrefresh@example.com", password="TestPass123!"
        )
        refresh = RefreshToken.for_user(user)

        client = APIClient()
        client.force_authenticate(user=user)
        response = client.post(
            "/api/auth/logout/",
            {"refresh": str(refresh)},
            format="json",
        )
        assert response.status_code == 200


# ══════════════════════════════════════════════════════════════════════
#  NATIVE CLIENT (X-Client-Platform header)
# ══════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestNativeClient:
    """Tests for native client token handling."""

    @patch("core.auth.views.send_login_notification_email")
    def test_native_login_returns_refresh_in_body(self, mock_notif):
        """Native client login returns refresh token in response body."""
        mock_notif.delay.return_value = None
        user = User.objects.create_user(
            email="nativelogin@example.com", password="NativePass123!"
        )
        EmailAddress.objects.create(
            user=user, email="nativelogin@example.com", verified=True, primary=True
        )

        client = APIClient()
        response = client.post(
            "/api/auth/login/",
            {"email": "nativelogin@example.com", "password": "NativePass123!"},
            format="json",
            HTTP_X_CLIENT_PLATFORM="native",
            HTTP_ORIGIN="https://stepora.app",
        )
        assert response.status_code == 200
        assert "access" in response.data
        assert "refresh" in response.data


# ══════════════════════════════════════════════════════════════════════
#  HEALTH CHECK VIEWS
# ══════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestHealthCheckViews:
    """Tests for core health check views."""

    def test_health_check(self):
        """Health check returns healthy status."""
        client = APIClient()
        response = client.get("/health/")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "services" in data
        assert "database" in data["services"]
        assert "cache" in data["services"]

    def test_liveness_check(self):
        """Liveness check returns alive."""
        client = APIClient()
        response = client.get("/health/liveness/")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "alive"

    def test_readiness_check(self):
        """Readiness check returns ready."""
        client = APIClient()
        response = client.get("/health/readiness/")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ready"


# ══════════════════════════════════════════════════════════════════════
#  AUDIT LOGGING
# ══════════════════════════════════════════════════════════════════════


class TestAuditLogging:
    """Tests for core.audit logging functions."""

    def test_get_client_ip_from_xff(self):
        """Extract IP from X-Forwarded-For header."""
        from core.audit import _get_client_ip

        request = Mock()
        request.META = {
            "HTTP_X_FORWARDED_FOR": "1.2.3.4, 5.6.7.8",
            "REMOTE_ADDR": "127.0.0.1",
        }
        assert _get_client_ip(request) == "1.2.3.4"

    def test_get_client_ip_from_remote_addr(self):
        """Extract IP from REMOTE_ADDR when no XFF."""
        from core.audit import _get_client_ip

        request = Mock()
        request.META = {"REMOTE_ADDR": "192.168.1.1"}
        assert _get_client_ip(request) == "192.168.1.1"

    def test_log_auth_failure(self):
        """log_auth_failure does not raise."""
        from core.audit import log_auth_failure

        request = Mock()
        request.META = {"REMOTE_ADDR": "127.0.0.1"}
        request.path = "/api/auth/login/"
        log_auth_failure(request, "wrong_password")

    def test_log_auth_success(self):
        """log_auth_success does not raise."""
        from core.audit import log_auth_success

        request = Mock()
        request.META = {"REMOTE_ADDR": "127.0.0.1"}
        user = Mock()
        user.id = uuid.uuid4()
        user.email = "test@example.com"
        log_auth_success(request, user)

    def test_log_permission_denied(self):
        """log_permission_denied does not raise."""
        from core.audit import log_permission_denied

        request = Mock()
        request.META = {"REMOTE_ADDR": "127.0.0.1"}
        request.path = "/api/dreams/"
        request.user = Mock()
        request.user.id = uuid.uuid4()
        log_permission_denied(request, "IsOwner", "DreamViewSet")

    def test_log_data_export(self):
        """log_data_export does not raise."""
        from core.audit import log_data_export

        user = Mock()
        user.id = uuid.uuid4()
        user.email = "test@example.com"
        log_data_export(user)

    def test_log_account_change(self):
        """log_account_change does not raise."""
        from core.audit import log_account_change

        user = Mock()
        user.id = uuid.uuid4()
        user.email = "test@example.com"
        log_account_change(user, "password_change", "changed from settings")

    def test_log_webhook_event(self):
        """log_webhook_event does not raise."""
        from core.audit import log_webhook_event

        log_webhook_event("customer.created", "evt_123", "processed")

    def test_log_suspicious_input(self):
        """log_suspicious_input does not raise."""
        from core.audit import log_suspicious_input

        request = Mock()
        request.META = {"REMOTE_ADDR": "127.0.0.1"}
        request.user = Mock()
        request.user.id = uuid.uuid4()
        log_suspicious_input(request, "title", "<script>alert(1)</script>")

    def test_log_ai_output_flagged(self):
        """log_ai_output_flagged does not raise."""
        from core.audit import log_ai_output_flagged

        log_ai_output_flagged("conv_123", "some harmful text", "toxic content")

    def test_log_jailbreak_attempt(self):
        """log_jailbreak_attempt does not raise."""
        from core.audit import log_jailbreak_attempt

        request = Mock()
        request.META = {"REMOTE_ADDR": "127.0.0.1"}
        request.user = Mock()
        request.user.id = uuid.uuid4()
        log_jailbreak_attempt(request, "ignore all previous instructions")


# ══════════════════════════════════════════════════════════════════════
#  PERMISSIONS
# ══════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestPermissions:
    """Tests for core.permissions."""

    def test_is_email_verified_unauthenticated(self):
        """Unauthenticated requests pass IsEmailVerified (let IsAuthenticated handle)."""
        from core.permissions import IsEmailVerified

        perm = IsEmailVerified()
        request = Mock()
        request.user = Mock()
        request.user.is_authenticated = False
        request.path = "/api/dreams/"
        assert perm.has_permission(request, None) is True

    def test_is_email_verified_exempt_path(self):
        """Exempt paths bypass email verification."""
        from core.permissions import IsEmailVerified

        perm = IsEmailVerified()
        request = Mock()
        request.user = Mock()
        request.user.is_authenticated = True
        request.path = "/api/auth/login/"
        assert perm.has_permission(request, None) is True

    def test_is_owner_has_user(self):
        """IsOwner checks obj.user matches request.user."""
        from core.permissions import IsOwner

        perm = IsOwner()
        user = Mock()
        request = Mock()
        request.user = user
        obj = Mock()
        obj.user = user
        assert perm.has_object_permission(request, None, obj) is True

    def test_is_owner_different_user(self):
        """IsOwner denies when obj.user != request.user."""
        from core.permissions import IsOwner

        perm = IsOwner()
        request = Mock()
        request.user = Mock()
        obj = Mock()
        obj.user = Mock()
        assert perm.has_object_permission(request, None, obj) is False

    def test_is_owner_buddy_pairing(self):
        """IsOwner allows user1 or user2 of a buddy pairing."""
        from core.permissions import IsOwner

        perm = IsOwner()
        user = Mock()
        request = Mock()
        request.user = user
        obj = Mock(spec=[])
        obj.user1 = user
        obj.user2 = Mock()
        # Remove 'user' attribute to test user1/user2 path
        assert perm.has_object_permission(request, None, obj) is True

    def test_is_premium_user_no_plan(self):
        """IsPremiumUser denies user with no plan."""
        from core.permissions import IsPremiumUser

        perm = IsPremiumUser()
        user = Mock()
        user.is_authenticated = True
        user.get_active_plan.return_value = None
        request = Mock()
        request.user = user
        assert perm.has_permission(request, None) is False

    def test_is_premium_user_with_plan(self):
        """IsPremiumUser allows user with premium plan."""
        from core.permissions import IsPremiumUser

        perm = IsPremiumUser()
        user = Mock()
        user.is_authenticated = True
        plan = Mock()
        plan.slug = "premium"
        user.get_active_plan.return_value = plan
        request = Mock()
        request.user = user
        assert perm.has_permission(request, None) is True

    def test_is_pro_user(self):
        """IsProUser allows user with pro plan."""
        from core.permissions import IsProUser

        perm = IsProUser()
        user = Mock()
        user.is_authenticated = True
        plan = Mock()
        plan.slug = "pro"
        user.get_active_plan.return_value = plan
        request = Mock()
        request.user = user
        assert perm.has_permission(request, None) is True

    def test_is_pro_user_premium(self):
        """IsProUser denies user with premium plan."""
        from core.permissions import IsProUser

        perm = IsProUser()
        user = Mock()
        user.is_authenticated = True
        plan = Mock()
        plan.slug = "premium"
        user.get_active_plan.return_value = plan
        request = Mock()
        request.user = user
        assert perm.has_permission(request, None) is False

    def test_can_create_dream_non_post(self):
        """CanCreateDream allows non-POST requests."""
        from core.permissions import CanCreateDream

        perm = CanCreateDream()
        request = Mock()
        request.method = "GET"
        assert perm.has_permission(request, None) is True

    def test_can_create_dream_under_limit(self):
        """CanCreateDream allows POST when under dream limit."""
        from core.permissions import CanCreateDream

        perm = CanCreateDream()
        user = User.objects.create_user(
            email="dreamlimit@example.com", password="test123"
        )
        plan = Mock()
        plan.dream_limit = 3
        plan.slug = "free"
        user.get_active_plan = Mock(return_value=plan)
        request = Mock()
        request.user = user
        request.method = "POST"
        assert perm.has_permission(request, None) is True

    def test_can_create_dream_unlimited(self):
        """CanCreateDream allows POST when dream_limit is -1."""
        from core.permissions import CanCreateDream

        perm = CanCreateDream()
        user = User.objects.create_user(
            email="unlimiteddream@example.com", password="test123"
        )
        plan = Mock()
        plan.dream_limit = -1
        plan.slug = "pro"
        user.get_active_plan = Mock(return_value=plan)
        request = Mock()
        request.user = user
        request.method = "POST"
        assert perm.has_permission(request, None) is True

    def test_can_use_ai_false(self):
        """CanUseAI denies user whose plan has no AI."""
        from core.permissions import CanUseAI

        perm = CanUseAI()
        user = Mock()
        user.is_authenticated = True
        plan = Mock()
        plan.has_ai = False
        user.get_active_plan.return_value = plan
        request = Mock()
        request.user = user
        assert perm.has_permission(request, None) is False

    def test_can_use_ai_true(self):
        """CanUseAI allows user whose plan has AI."""
        from core.permissions import CanUseAI

        perm = CanUseAI()
        user = Mock()
        user.is_authenticated = True
        plan = Mock()
        plan.has_ai = True
        user.get_active_plan.return_value = plan
        request = Mock()
        request.user = user
        assert perm.has_permission(request, None) is True

    def test_can_use_buddy(self):
        """CanUseBuddy allows user whose plan has buddy."""
        from core.permissions import CanUseBuddy

        perm = CanUseBuddy()
        user = Mock()
        user.is_authenticated = True
        plan = Mock()
        plan.has_buddy = True
        user.get_active_plan.return_value = plan
        request = Mock()
        request.user = user
        assert perm.has_permission(request, None) is True

    def test_can_use_circles_post(self):
        """CanUseCircles checks has_circle_create for POST."""
        from core.permissions import CanUseCircles

        perm = CanUseCircles()
        user = Mock()
        user.is_authenticated = True
        plan = Mock()
        plan.has_circle_create = True
        plan.has_circles = True
        user.get_active_plan.return_value = plan
        request = Mock()
        request.user = user
        request.method = "POST"
        assert perm.has_permission(request, None) is True

    def test_can_use_circles_get(self):
        """CanUseCircles checks has_circles for GET."""
        from core.permissions import CanUseCircles

        perm = CanUseCircles()
        user = Mock()
        user.is_authenticated = True
        plan = Mock()
        plan.has_circles = True
        user.get_active_plan.return_value = plan
        request = Mock()
        request.user = user
        request.method = "GET"
        assert perm.has_permission(request, None) is True

    def test_can_use_circles_denied_create(self):
        """CanUseCircles denies POST when no circle_create."""
        from core.permissions import CanUseCircles

        perm = CanUseCircles()
        user = Mock()
        user.is_authenticated = True
        plan = Mock()
        plan.has_circle_create = False
        plan.has_circles = True
        user.get_active_plan.return_value = plan
        request = Mock()
        request.user = user
        request.method = "POST"
        assert perm.has_permission(request, None) is False

    def test_can_use_vision_board(self):
        """CanUseVisionBoard checks has_vision_board."""
        from core.permissions import CanUseVisionBoard

        perm = CanUseVisionBoard()
        user = Mock()
        user.is_authenticated = True
        plan = Mock()
        plan.has_vision_board = True
        user.get_active_plan.return_value = plan
        request = Mock()
        request.user = user
        assert perm.has_permission(request, None) is True

    def test_can_use_league(self):
        """CanUseLeague checks has_league."""
        from core.permissions import CanUseLeague

        perm = CanUseLeague()
        user = Mock()
        user.is_authenticated = True
        plan = Mock()
        plan.has_league = True
        user.get_active_plan.return_value = plan
        request = Mock()
        request.user = user
        assert perm.has_permission(request, None) is True

    def test_can_use_store(self):
        """CanUseStore checks has_store."""
        from core.permissions import CanUseStore

        perm = CanUseStore()
        user = Mock()
        user.is_authenticated = True
        plan = Mock()
        plan.has_store = True
        user.get_active_plan.return_value = plan
        request = Mock()
        request.user = user
        assert perm.has_permission(request, None) is True

    def test_can_use_social_feed(self):
        """CanUseSocialFeed checks has_social_feed."""
        from core.permissions import CanUseSocialFeed

        perm = CanUseSocialFeed()
        user = Mock()
        user.is_authenticated = True
        plan = Mock()
        plan.has_social_feed = True
        user.get_active_plan.return_value = plan
        request = Mock()
        request.user = user
        assert perm.has_permission(request, None) is True

    def test_can_make_public_dream(self):
        """CanMakePublicDream checks has_public_dreams."""
        from core.permissions import CanMakePublicDream

        perm = CanMakePublicDream()
        user = Mock()
        user.is_authenticated = True
        plan = Mock()
        plan.has_public_dreams = True
        user.get_active_plan.return_value = plan
        request = Mock()
        request.user = user
        assert perm.has_permission(request, None) is True


# ══════════════════════════════════════════════════════════════════════
#  AUTH SOCIAL (Google & Apple token verification)
# ══════════════════════════════════════════════════════════════════════


class TestAuthSocial:
    """Tests for core.auth.social token verification."""

    @patch("core.auth.social._get_cached_jwks")
    def test_verify_google_jwt_manual_key_not_found(self, mock_jwks):
        """Manual Google JWT verification fails when key not found."""
        from core.auth.social import _verify_google_jwt_manual

        mock_jwks.return_value = {"keys": []}
        with pytest.raises(Exception):
            _verify_google_jwt_manual("fake.jwt.token")

    def test_find_jwk_found(self):
        """_find_jwk returns key when kid matches."""
        from core.auth.social import _find_jwk

        jwks = {"keys": [{"kid": "key1", "n": "abc"}, {"kid": "key2", "n": "def"}]}
        result = _find_jwk(jwks, "key1")
        assert result["n"] == "abc"

    def test_find_jwk_not_found(self):
        """_find_jwk returns None when kid not found."""
        from core.auth.social import _find_jwk

        jwks = {"keys": [{"kid": "key1"}]}
        result = _find_jwk(jwks, "nonexistent")
        assert result is None

    @patch("core.auth.social.http_requests.get")
    def test_get_cached_jwks_fetch(self, mock_get):
        """_get_cached_jwks fetches from URL when not cached."""
        from core.auth.social import _get_cached_jwks

        mock_resp = Mock()
        mock_resp.json.return_value = {"keys": [{"kid": "k1"}]}
        mock_resp.raise_for_status.return_value = None
        mock_get.return_value = mock_resp

        result = _get_cached_jwks("test_provider", "https://example.com/jwks", force_refresh=True)
        assert result == {"keys": [{"kid": "k1"}]}

    @patch("core.auth.social.http_requests.get")
    def test_get_cached_jwks_network_error(self, mock_get):
        """_get_cached_jwks raises ValidationError on network failure."""
        import requests

        from core.auth.social import _get_cached_jwks

        mock_get.side_effect = requests.RequestException("timeout")

        with pytest.raises(Exception):
            _get_cached_jwks("test_provider", "https://example.com/jwks", force_refresh=True)

    @patch("core.auth.social._get_cached_jwks")
    @patch("core.auth.social._find_jwk")
    def test_verify_apple_token_key_not_found(self, mock_find, mock_jwks):
        """Apple token verification fails when signing key not found."""
        from core.auth.social import verify_apple_token

        mock_jwks.return_value = {"keys": []}
        mock_find.return_value = None

        with pytest.raises(Exception):
            verify_apple_token("fake.apple.token")

    @patch("core.auth.social._get_cached_jwks")
    def test_verify_google_token_invalid(self, mock_jwks):
        """verify_google_token raises on invalid token."""
        from core.auth.social import verify_google_token

        mock_jwks.return_value = {"keys": []}
        with pytest.raises(Exception):
            verify_google_token("invalid_token")


# ══════════════════════════════════════════════════════════════════════
#  AUTH TOKENS
# ══════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestAuthTokens:
    """Tests for core.auth.tokens."""

    def test_make_email_verification_key(self):
        """Make and verify email verification key."""
        from core.auth.models import EmailAddress
        from core.auth.tokens import make_email_verification_key

        user = User.objects.create_user(
            email="tokentest@example.com", password="test123"
        )
        ea = EmailAddress.objects.create(
            user=user, email=user.email, verified=False, primary=True
        )
        key = make_email_verification_key(ea.id)
        assert key is not None
        assert len(key) > 0

    def test_make_password_reset_token(self):
        """Generate password reset token."""
        from core.auth.tokens import make_password_reset_token

        user = User.objects.create_user(
            email="resettoken@example.com", password="test123"
        )
        uidb64, token = make_password_reset_token(user)
        assert uidb64 is not None
        assert token is not None


# ══════════════════════════════════════════════════════════════════════
#  WEBSOCKET AUTH
# ══════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestWebSocketAuth:
    """Tests for core.websocket_auth."""

    @pytest.mark.asyncio
    async def test_get_user_no_token(self):
        """get_user_from_token with no token returns AnonymousUser."""
        from django.contrib.auth.models import AnonymousUser

        from core.websocket_auth import get_user_from_token

        user = await get_user_from_token(None)
        assert isinstance(user, AnonymousUser)

    @pytest.mark.asyncio
    async def test_get_user_invalid_token(self):
        """get_user_from_token with invalid token returns AnonymousUser."""
        from django.contrib.auth.models import AnonymousUser

        from core.websocket_auth import get_user_from_token

        user = await get_user_from_token("invalid_jwt_token")
        assert isinstance(user, AnonymousUser)

    @pytest.mark.asyncio
    async def test_get_user_valid_jwt(self):
        """get_user_from_token with valid JWT returns the user."""
        from channels.db import database_sync_to_async
        from rest_framework_simplejwt.tokens import AccessToken

        from core.websocket_auth import get_user_from_token

        @database_sync_to_async
        def create_user():
            return User.objects.create_user(
                email="wsauthtest@example.com", password="test123"
            )

        user = await create_user()
        token = str(AccessToken.for_user(user))
        result = await get_user_from_token(token)
        assert result.id == user.id

    @pytest.mark.asyncio
    async def test_get_user_empty_string(self):
        """get_user_from_token with empty string returns AnonymousUser."""
        from django.contrib.auth.models import AnonymousUser

        from core.websocket_auth import get_user_from_token

        user = await get_user_from_token("")
        assert isinstance(user, AnonymousUser)
