"""
Custom authentication views — replaces dj-rest-auth and allauth views.

Handles: login (with 2FA), registration, logout, password reset/change,
email verification, token refresh, social login (Google/Apple).

Native mobile apps send `X-Client-Platform: native` header to receive
the refresh token in the response body instead of an httpOnly cookie.
"""

import html
import json
import logging
import time
from datetime import timedelta

import pyotp
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core import signing
from django.core.cache import cache
from django.http import HttpResponse
from rest_framework import status as http_status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from core.auth.models import EmailAddress, SocialAccount
from core.auth.serializers import (
    EmailVerificationSerializer,
    LoginSerializer,
    PasswordChangeSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetSerializer,
    RegisterSerializer,
    ResendVerificationSerializer,
)
from core.auth.social import verify_apple_token, verify_google_token
from core.auth.tasks import send_login_notification_email, send_password_changed_email
from core.throttles import AuthRateThrottle

logger = logging.getLogger(__name__)
User = get_user_model()

_DP_AUTH = getattr(settings, "DP_AUTH", {})

# Account lockout settings
_MAX_FAILED_ATTEMPTS = 5
_LOCKOUT_SECONDS = 900  # 15 minutes

# 2FA challenge token settings
_TFA_CHALLENGE_MAX_AGE = 300  # 5 minutes
_TFA_CHALLENGE_SALT = "stepora-2fa-challenge"

# Allowed values for X-Client-Platform header
_NATIVE_PLATFORMS = frozenset(("native", "ios", "android", "capacitor"))

_COOKIE_NAME = _DP_AUTH.get("JWT_AUTH_REFRESH_COOKIE", "dp-refresh")
_COOKIE_DOMAIN = _DP_AUTH.get(
    "JWT_AUTH_COOKIE_DOMAIN"
)  # None = host-only (same-origin)
_COOKIE_PATH = _DP_AUTH.get("JWT_AUTH_COOKIE_PATH", "/api/auth/")
_COOKIE_SAMESITE = _DP_AUTH.get("JWT_AUTH_SAMESITE", "Lax")
_COOKIE_SECURE = _DP_AUTH.get("JWT_AUTH_SECURE", not settings.DEBUG)

# ── Helper functions ──────────────────────────────────────────────────


def _is_native_request(request):
    """Check if the request comes from a native mobile client."""
    platform = request.META.get("HTTP_X_CLIENT_PLATFORM", "").lower().strip()
    return platform in _NATIVE_PLATFORMS


def _get_client_ip(request):
    """Get the real client IP, respecting X-Forwarded-For behind a proxy."""
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if xff:
        return xff.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "")


def _lockout_key(identifier):
    return f"login_lockout:{identifier}"


def _fail_count_key(identifier):
    return f"login_fails:{identifier}"


def _create_challenge_token(user_id):
    """Create a short-lived signed token for the 2FA challenge."""
    return signing.dumps(
        {"uid": str(user_id), "t": int(time.time())},
        salt=_TFA_CHALLENGE_SALT,
    )


def _verify_challenge_token(token):
    """Verify and return user_id from a 2FA challenge token, or None."""
    try:
        data = signing.loads(
            token, salt=_TFA_CHALLENGE_SALT, max_age=_TFA_CHALLENGE_MAX_AGE
        )
        return data.get("uid")
    except (signing.BadSignature, signing.SignatureExpired):
        return None


def _issue_jwt_response(user, request):
    """
    Issue JWT tokens for a user.

    Returns a Response with:
    - access token in body
    - refresh token as httpOnly cookie (web) or in body (native)
    """
    refresh = RefreshToken.for_user(user)
    data = {
        "access": str(refresh.access_token),
        "user": {
            "id": str(user.id),
            "email": user.email,
            "display_name": getattr(user, "display_name", ""),
        },
    }

    response = Response(data, status=http_status.HTTP_200_OK)

    # Set refresh token as httpOnly cookie
    cookie_max_age = int(
        settings.SIMPLE_JWT.get(
            "REFRESH_TOKEN_LIFETIME", timedelta(days=7)
        ).total_seconds()
    )
    response.set_cookie(
        _COOKIE_NAME,
        str(refresh),
        max_age=cookie_max_age,
        httponly=True,
        samesite=_COOKIE_SAMESITE,
        secure=_COOKIE_SECURE,
        path=_COOKIE_PATH,
        domain=_COOKIE_DOMAIN,
    )

    # For native clients, also inject refresh token into body
    if _is_native_request(request):
        data["refresh"] = str(refresh)
        response.data = data
        response.content = json.dumps(data).encode("utf-8")

    return response


def _check_lockout(request):
    """
    Check if the request is locked out due to too many failed attempts.
    Returns (identifiers, lockout_response_or_None).
    """
    ip = _get_client_ip(request)
    email = (request.data.get("email") or "").lower().strip()
    identifiers = [f"ip:{ip}"]
    if email:
        identifiers.append(f"email:{email}")

    for ident in identifiers:
        if cache.get(_lockout_key(ident)):
            return identifiers, Response(
                {"detail": "Too many failed login attempts. Please try again later."},
                status=http_status.HTTP_429_TOO_MANY_REQUESTS,
            )
    return identifiers, None


def _record_failed_login(identifiers):
    """Record a failed login attempt and trigger lockout if threshold reached."""
    for ident in identifiers:
        key = _fail_count_key(ident)
        try:
            fails = cache.incr(key)
        except ValueError:
            cache.set(key, 1, timeout=_LOCKOUT_SECONDS)
            fails = 1
        if fails >= _MAX_FAILED_ATTEMPTS:
            cache.set(_lockout_key(ident), True, timeout=_LOCKOUT_SECONDS)
            logger.warning(
                "Account lockout triggered for %s after %d failures", ident, fails
            )


def _clear_failed_login(identifiers):
    """Clear failed login counters after a successful login."""
    for ident in identifiers:
        cache.delete(_fail_count_key(ident))
        cache.delete(_lockout_key(ident))


# ── Views ─────────────────────────────────────────────────────────────


class LoginView(APIView):
    """
    Email + password login with account lockout and 2FA support.

    If 2FA is enabled, returns {tfaRequired: true, challengeToken: ...}
    instead of JWT tokens. Client must then call /auth/2fa-challenge/.
    """

    permission_classes = [AllowAny]
    throttle_classes = [AuthRateThrottle]

    def post(self, request):
        identifiers, lockout_response = _check_lockout(request)
        if lockout_response:
            return lockout_response

        serializer = LoginSerializer(data=request.data, context={"request": request})
        if not serializer.is_valid():
            _record_failed_login(identifiers)
            return Response(serializer.errors, status=http_status.HTTP_400_BAD_REQUEST)

        user = serializer.validated_data["user"]
        _clear_failed_login(identifiers)

        # Check 2FA
        if getattr(user, "totp_enabled", False):
            challenge_token = _create_challenge_token(user.id)
            return Response(
                {
                    "tfa_required": True,
                    "challenge_token": challenge_token,
                },
                status=http_status.HTTP_200_OK,
            )

        # Send login notification
        send_login_notification_email.delay(
            str(user.id),
            ip_address=_get_client_ip(request),
            user_agent=request.META.get("HTTP_USER_AGENT", ""),
        )

        return _issue_jwt_response(user, request)


class TwoFactorChallengeView(APIView):
    """
    Complete 2FA login with TOTP code or backup code.

    Accepts challengeToken (from login) + code.
    If valid, issues JWT access + refresh tokens.
    """

    permission_classes = [AllowAny]
    throttle_classes = [AuthRateThrottle]

    def post(self, request):
        challenge_token = request.data.get("challenge_token", "").strip()
        code = request.data.get("code", "").strip()

        if not challenge_token or not code:
            return Response(
                {"error": "Challenge token and verification code are required."},
                status=http_status.HTTP_400_BAD_REQUEST,
            )

        user_id = _verify_challenge_token(challenge_token)
        if not user_id:
            return Response(
                {"error": "Invalid or expired challenge. Please log in again."},
                status=http_status.HTTP_400_BAD_REQUEST,
            )

        try:
            user = User.objects.get(id=user_id, is_active=True)
        except User.DoesNotExist:
            return Response(
                {"error": "Invalid challenge."},
                status=http_status.HTTP_400_BAD_REQUEST,
            )

        if not user.totp_enabled or not user.totp_secret:
            return Response(
                {"error": "2FA is not enabled for this account."},
                status=http_status.HTTP_400_BAD_REQUEST,
            )

        # Verify TOTP code
        totp = pyotp.TOTP(user.totp_secret)
        verified = totp.verify(code, valid_window=1)

        # If TOTP failed, try backup codes
        if not verified:
            from apps.users.two_factor import _hash_code

            stored_hashes = user.backup_codes or []
            code_hash = _hash_code(code.upper())
            if code_hash in stored_hashes:
                stored_hashes.remove(code_hash)
                user.backup_codes = stored_hashes
                user.save(update_fields=["backup_codes"])
                verified = True

        if not verified:
            return Response(
                {"error": "Invalid verification code."},
                status=http_status.HTTP_400_BAD_REQUEST,
            )

        # Send login notification
        send_login_notification_email.delay(
            str(user.id),
            ip_address=_get_client_ip(request),
            user_agent=request.META.get("HTTP_USER_AGENT", ""),
        )

        return _issue_jwt_response(user, request)


class RegisterView(APIView):
    """
    User registration with email + password.
    Issues JWT tokens and sends verification email.
    """

    permission_classes = [AllowAny]
    throttle_classes = [AuthRateThrottle]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=http_status.HTTP_400_BAD_REQUEST)

        user = serializer.save(request=request)
        return _issue_jwt_response(user, request)


class LogoutView(APIView):
    """
    Logout by blacklisting the refresh token and clearing the cookie.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        # Try to get refresh token from body or cookie
        refresh_token = request.data.get("refresh", "")
        if not refresh_token:
            refresh_token = request.COOKIES.get(_COOKIE_NAME, "")

        if refresh_token:
            try:
                token = RefreshToken(refresh_token)
                token.blacklist()
            except TokenError:
                pass  # Token already expired or blacklisted

        response = Response(
            {"detail": "Successfully logged out."}, status=http_status.HTTP_200_OK
        )
        # Delete refresh cookie with exact same attributes it was created with
        response.set_cookie(
            _COOKIE_NAME,
            "",
            max_age=0,
            httponly=True,
            secure=_COOKIE_SECURE,
            samesite=_COOKIE_SAMESITE,
            path=_COOKIE_PATH,
            domain=_COOKIE_DOMAIN,
        )
        return response


class PasswordResetView(APIView):
    """
    Request a password reset email.
    Always returns 200 to avoid leaking whether an account exists.
    """

    permission_classes = [AllowAny]
    throttle_classes = [AuthRateThrottle]

    def post(self, request):
        serializer = PasswordResetSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
        return Response(
            {
                "detail": "If an account exists with this email, a password reset link has been sent."
            },
            status=http_status.HTTP_200_OK,
        )


class PasswordResetValidateView(APIView):
    """
    Validate a password reset token without consuming it.
    Returns 200 if valid, 400 if invalid/expired.
    """

    permission_classes = [AllowAny]
    throttle_classes = [AuthRateThrottle]

    def post(self, request):
        from core.auth.tokens import verify_password_reset_token

        uid = request.data.get("uid", "")
        token = request.data.get("token", "")
        if not uid or not token:
            return Response(
                {"valid": False, "detail": "uid and token are required."},
                status=http_status.HTTP_400_BAD_REQUEST,
            )
        user, valid = verify_password_reset_token(uid, token)
        if valid:
            return Response({"valid": True}, status=http_status.HTTP_200_OK)
        return Response(
            {"valid": False, "detail": "Invalid or expired reset link."},
            status=http_status.HTTP_400_BAD_REQUEST,
        )


class PasswordResetConfirmView(APIView):
    """
    Confirm a password reset with uid, token, and new password.
    """

    permission_classes = [AllowAny]
    throttle_classes = [AuthRateThrottle]

    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=http_status.HTTP_400_BAD_REQUEST)
        user = serializer.save()
        send_password_changed_email.delay(str(user.id))
        return Response(
            {"detail": "Password has been reset successfully."},
            status=http_status.HTTP_200_OK,
        )


class PasswordChangeView(APIView):
    """
    Change password for authenticated user.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = PasswordChangeSerializer(
            data=request.data, context={"request": request}
        )
        if not serializer.is_valid():
            return Response(serializer.errors, status=http_status.HTTP_400_BAD_REQUEST)
        serializer.save()
        send_password_changed_email.delay(str(request.user.id))
        return Response(
            {"detail": "Password has been changed successfully."},
            status=http_status.HTTP_200_OK,
        )


class VerifyEmailView(APIView):
    """
    Verify an email address using the signed key from the verification email.
    """

    permission_classes = [AllowAny]

    def post(self, request):
        serializer = EmailVerificationSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=http_status.HTTP_400_BAD_REQUEST)
        serializer.save()
        return Response(
            {"detail": "Email address has been verified."},
            status=http_status.HTTP_200_OK,
        )


class ResendVerificationView(APIView):
    """
    Resend the email verification link.
    Always returns 200 to avoid leaking account information.
    """

    permission_classes = [AllowAny]
    throttle_classes = [AuthRateThrottle]

    def post(self, request):
        serializer = ResendVerificationSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
        return Response(
            {
                "detail": "If an unverified email exists, a verification link has been sent."
            },
            status=http_status.HTTP_200_OK,
        )


class TokenRefreshView(APIView):
    """
    Refresh JWT tokens.

    Web clients: reads refresh token from httpOnly cookie, returns new access token.
    Native clients: reads refresh token from body, returns new access + refresh tokens.
    """

    permission_classes = [AllowAny]

    def post(self, request):
        # Native clients send refresh token in body
        refresh_str = request.data.get("refresh", "")
        if not refresh_str:
            # Web clients: refresh token is in httpOnly cookie
            refresh_str = request.COOKIES.get(_COOKIE_NAME, "")

        if not refresh_str:
            return Response(
                {"detail": "No refresh token provided."},
                status=http_status.HTTP_400_BAD_REQUEST,
            )

        try:
            return self._do_refresh(request, refresh_str)
        except TokenError:
            return Response(
                {"detail": "Token is invalid or expired."},
                status=http_status.HTTP_401_UNAUTHORIZED,
            )

    def _do_refresh(self, request, refresh_str):
        old_refresh = RefreshToken(refresh_str)  # raises TokenError if invalid

        # Get new access token
        data = {
            "access": str(old_refresh.access_token),
        }

        response = Response(data, status=http_status.HTTP_200_OK)

        # Rotate refresh token if configured
        if settings.SIMPLE_JWT.get("ROTATE_REFRESH_TOKENS", False):
            try:
                if settings.SIMPLE_JWT.get("BLACKLIST_AFTER_ROTATION", False):
                    old_refresh.blacklist()
            except AttributeError:
                pass

            new_refresh = RefreshToken.for_user(
                User.objects.get(pk=old_refresh.payload.get("user_id"))
            )

            # Set new refresh cookie
            cookie_max_age = int(
                settings.SIMPLE_JWT.get(
                    "REFRESH_TOKEN_LIFETIME", timedelta(days=7)
                ).total_seconds()
            )
            response.set_cookie(
                _COOKIE_NAME,
                str(new_refresh),
                max_age=cookie_max_age,
                httponly=True,
                samesite=_COOKIE_SAMESITE,
                secure=_COOKIE_SECURE,
                path=_COOKIE_PATH,
                domain=_COOKIE_DOMAIN,
            )

            if _is_native_request(request):
                data["refresh"] = str(new_refresh)
                response.data = data
                response.content = json.dumps(data).encode("utf-8")
        else:
            # No rotation — re-set the same cookie
            cookie_max_age = int(
                settings.SIMPLE_JWT.get(
                    "REFRESH_TOKEN_LIFETIME", timedelta(days=7)
                ).total_seconds()
            )
            response.set_cookie(
                _COOKIE_NAME,
                refresh_str,
                max_age=cookie_max_age,
                httponly=True,
                samesite=_COOKIE_SAMESITE,
                secure=_COOKIE_SECURE,
                path=_COOKIE_PATH,
                domain=_COOKIE_DOMAIN,
            )

        return response


class UserDetailsView(APIView):
    """
    Get the authenticated user's details.
    Replaces dj-rest-auth's UserDetailsView.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        from apps.users.serializers import UserSerializer

        serializer = UserSerializer(user, context={"request": request})
        return Response(serializer.data)

    def put(self, request):
        user = request.user
        from apps.users.serializers import UserSerializer

        serializer = UserSerializer(
            user, data=request.data, context={"request": request}
        )
        if not serializer.is_valid():
            return Response(serializer.errors, status=http_status.HTTP_400_BAD_REQUEST)
        serializer.save()
        return Response(serializer.data)

    def patch(self, request):
        user = request.user
        from apps.users.serializers import UserSerializer

        serializer = UserSerializer(
            user, data=request.data, partial=True, context={"request": request}
        )
        if not serializer.is_valid():
            return Response(serializer.errors, status=http_status.HTTP_400_BAD_REQUEST)
        serializer.save()
        return Response(serializer.data)


# ── Social Login Views ────────────────────────────────────────────────


class GoogleLoginView(APIView):
    """
    Google Sign-In using ID token verification.
    Accepts {id_token: "..."} in the request body.
    """

    permission_classes = [AllowAny]
    throttle_classes = [AuthRateThrottle]

    def post(self, request):
        id_token_str = request.data.get("id_token", "") or request.data.get(
            "access_token", ""
        )
        if not id_token_str:
            return Response(
                {"error": "id_token is required."},
                status=http_status.HTTP_400_BAD_REQUEST,
            )

        uid, email, name, picture = verify_google_token(id_token_str)

        user = self._get_or_create_user(uid, email, name, picture)
        send_login_notification_email.delay(
            str(user.id),
            ip_address=_get_client_ip(request),
            user_agent=request.META.get("HTTP_USER_AGENT", ""),
        )
        return _issue_jwt_response(user, request)

    def _get_or_create_user(self, uid, email, name, picture):
        """Find or create a user from Google credentials."""
        # Check if social account already exists
        try:
            social = SocialAccount.objects.select_related("user").get(
                provider="google",
                uid=uid,
            )
            social.extra_data = {"name": name, "picture": picture, "email": email}
            social.save(update_fields=["extra_data", "last_login"])
            return social.user
        except SocialAccount.DoesNotExist:
            pass

        # Check if a user with this email already exists
        try:
            user = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            user = User.objects.create_user(
                email=email,
                display_name=name or "",
            )
            # Mark email as verified (Google verified it)
            EmailAddress.objects.create(
                user=user,
                email=email,
                verified=True,
                primary=True,
            )

        # Create social account link
        SocialAccount.objects.create(
            user=user,
            provider="google",
            uid=uid,
            extra_data={"name": name, "picture": picture, "email": email},
        )

        return user


class AppleLoginView(APIView):
    """
    Apple Sign-In using ID token verification.
    Accepts {id_token: "...", name: "..."} in the request body.
    """

    permission_classes = [AllowAny]
    throttle_classes = [AuthRateThrottle]

    def post(self, request):
        id_token_str = request.data.get("id_token", "") or request.data.get("code", "")
        if not id_token_str:
            return Response(
                {"error": "id_token is required."},
                status=http_status.HTTP_400_BAD_REQUEST,
            )

        uid, email = verify_apple_token(id_token_str)

        # Apple may omit email on subsequent logins
        name = request.data.get("name", "")

        user = self._get_or_create_user(uid, email, name)
        send_login_notification_email.delay(
            str(user.id),
            ip_address=_get_client_ip(request),
            user_agent=request.META.get("HTTP_USER_AGENT", ""),
        )
        return _issue_jwt_response(user, request)

    def _get_or_create_user(self, uid, email, name):
        """Find or create a user from Apple credentials."""
        # Check if social account already exists
        try:
            social = SocialAccount.objects.select_related("user").get(
                provider="apple",
                uid=uid,
            )
            social.save(update_fields=["last_login"])
            return social.user
        except SocialAccount.DoesNotExist:
            pass

        if not email:
            from rest_framework import serializers

            raise serializers.ValidationError(
                "Apple did not provide an email. This may happen on subsequent logins. "
                "Please use the original Apple Sign-In method."
            )

        # Check if a user with this email already exists
        try:
            user = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            user = User.objects.create_user(
                email=email,
                display_name=name or "",
            )
            EmailAddress.objects.create(
                user=user,
                email=email,
                verified=True,
                primary=True,
            )

        SocialAccount.objects.create(
            user=user,
            provider="apple",
            uid=uid,
            extra_data={"email": email, "name": name},
        )

        return user


class AppleRedirectView(APIView):
    """
    Handle Apple OAuth2 form_post callback for native apps.

    Apple sends POST with: code, id_token, state (native redirect URI).
    This view authenticates via Apple token verification, then redirects
    the native app back with a deep link containing the JWT token.
    """

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        id_token_str = request.POST.get("id_token", "")
        raw_state = request.POST.get("state", "")

        # Validate state against allowed deep link schemes to prevent open redirect
        ALLOWED_DEEP_LINK_PREFIXES = ("com.stepora.app://",)
        state = ""
        if raw_state and any(
            raw_state.startswith(p) for p in ALLOWED_DEEP_LINK_PREFIXES
        ):
            state = raw_state

        if not id_token_str:
            return HttpResponse("Missing id_token.", status=400)

        try:
            uid, email = verify_apple_token(id_token_str)
            name = request.POST.get("name", "")

            # Get or create user
            apple_view = AppleLoginView()
            user = apple_view._get_or_create_user(uid, email, name)

            # Issue JWT
            refresh = RefreshToken.for_user(user)
            access_token = str(refresh.access_token)

            if state and access_token:
                deep_link = state + "?token=" + access_token
            elif access_token:
                deep_link = "com.stepora.app://auth/callback?token=" + access_token
            else:
                deep_link = "com.stepora.app://auth/callback?error=no_token"

        except Exception:
            deep_link = (
                state + "?error=auth_failed"
                if state
                else "com.stepora.app://auth/callback?error=auth_failed"
            )

        # Redirect via HTML page (form_post response must be HTML)
        deep_link_js = json.dumps(deep_link)
        deep_link_html = html.escape(deep_link)
        page = (
            '<!DOCTYPE html><html><head><meta charset="utf-8">'
            "<title>Redirecting...</title></head><body>"
            "<p>Redirecting to Stepora...</p>"
            '<p><a href="' + deep_link_html + '">Click here if not redirected.</a></p>'
            "<script>window.location.href = " + deep_link_js + ";</script>"
            "</body></html>"
        )
        return HttpResponse(page, content_type="text/html")
