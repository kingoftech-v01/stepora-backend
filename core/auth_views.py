"""
Custom authentication views for native mobile app support.

Problem: dj-rest-auth with JWT_AUTH_HTTPONLY=True stores the refresh token
in an httpOnly cookie. This is secure for web browsers, but native mobile
apps (Capacitor/Cordova) cannot access httpOnly cookies.

Solution: Native clients send `X-Client-Platform: native` header. When
this header is present, the refresh token is extracted from the Set-Cookie
header and injected into the JSON response body so the native app can
store it securely in Capacitor Preferences (encrypted device storage).

Web clients continue to use httpOnly cookies as before.

2FA flow:
  1. Client posts email + password to /auth/login/
  2. If credentials are valid AND user.totp_enabled:
     - No JWT tokens are issued
     - A short-lived signed challenge_token is returned with tfaRequired=True
  3. Client posts challenge_token + TOTP code to /auth/2fa-challenge/
  4. If valid, full JWT tokens are issued
"""

import json
import logging
import time

import pyotp
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core import signing
from django.core.cache import cache
from rest_framework import status as http_status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from dj_rest_auth.views import LoginView
from dj_rest_auth.registration.views import RegisterView
from rest_framework_simplejwt.tokens import RefreshToken

from core.throttles import AuthRateThrottle

logger = logging.getLogger(__name__)
User = get_user_model()

# Account lockout settings
_MAX_FAILED_ATTEMPTS = 5
_LOCKOUT_SECONDS = 900  # 15 minutes

# 2FA challenge token settings
_TFA_CHALLENGE_MAX_AGE = 300  # 5 minutes
_TFA_CHALLENGE_SALT = 'dreamplanner-2fa-challenge'

# Allowed values for X-Client-Platform header
_NATIVE_PLATFORMS = frozenset(('native', 'ios', 'android', 'capacitor'))

_COOKIE_NAME = settings.REST_AUTH.get('JWT_AUTH_REFRESH_COOKIE', 'dp-refresh')


def _is_native_request(request):
    """Check if the request comes from a native mobile client."""
    platform = request.META.get('HTTP_X_CLIENT_PLATFORM', '').lower().strip()
    return platform in _NATIVE_PLATFORMS


def _inject_refresh_token(response):
    """Extract refresh token from Set-Cookie and add it to response body."""
    refresh_token = ''
    if hasattr(response, 'cookies') and _COOKIE_NAME in response.cookies:
        refresh_token = response.cookies[_COOKIE_NAME].value

    if refresh_token and hasattr(response, 'data'):
        response.data['refresh'] = refresh_token
        # Re-serialize the response content with the injected token
        response.content = json.dumps(response.data).encode('utf-8')

    return response


def _get_client_ip(request):
    """Get the real client IP, respecting X-Forwarded-For behind a proxy."""
    xff = request.META.get('HTTP_X_FORWARDED_FOR')
    if xff:
        return xff.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', '')


def _lockout_key(identifier):
    return f'login_lockout:{identifier}'


def _fail_count_key(identifier):
    return f'login_fails:{identifier}'


def _create_challenge_token(user_id):
    """Create a short-lived signed token for the 2FA challenge."""
    return signing.dumps(
        {'uid': str(user_id), 't': int(time.time())},
        salt=_TFA_CHALLENGE_SALT,
    )


def _verify_challenge_token(token):
    """Verify and return user_id from a 2FA challenge token, or None."""
    try:
        data = signing.loads(token, salt=_TFA_CHALLENGE_SALT, max_age=_TFA_CHALLENGE_MAX_AGE)
        return data.get('uid')
    except (signing.BadSignature, signing.SignatureExpired):
        return None


class NativeAwareLoginView(LoginView):
    """
    Login view that returns refresh token in body for native clients.
    Web clients get the standard httpOnly cookie behavior.
    Includes AuthRateThrottle, account lockout, and 2FA enforcement.
    """
    throttle_classes = [AuthRateThrottle]

    def post(self, request, *args, **kwargs):
        # Check lockout by IP
        ip = _get_client_ip(request)
        email = (request.data.get('email') or request.data.get('username') or '').lower().strip()
        identifiers = [f'ip:{ip}']
        if email:
            identifiers.append(f'email:{email}')

        for ident in identifiers:
            if cache.get(_lockout_key(ident)):
                return Response(
                    {'detail': 'Too many failed login attempts. Please try again later.'},
                    status=http_status.HTTP_429_TOO_MANY_REQUESTS,
                )

        # Let dj-rest-auth validate credentials (this issues JWT tokens on success)
        response = super().post(request, *args, **kwargs)

        if response.status_code == 200:
            # Credentials valid — clear failure counters
            for ident in identifiers:
                cache.delete(_fail_count_key(ident))
                cache.delete(_lockout_key(ident))

            # Check if user has 2FA enabled
            user = self.user if hasattr(self, 'user') else None
            if user is None and email:
                try:
                    user = User.objects.get(email__iexact=email)
                except User.DoesNotExist:
                    user = None

            if user and getattr(user, 'totp_enabled', False):
                # 2FA required — do NOT return tokens.
                # Strip cookies (refresh token) and return a challenge token instead.
                challenge_token = _create_challenge_token(user.id)
                tfa_response = Response({
                    'tfaRequired': True,
                    'challengeToken': challenge_token,
                }, status=http_status.HTTP_200_OK)
                # Clear any JWT cookies that were set by the parent LoginView
                tfa_response.delete_cookie(_COOKIE_NAME)
                return tfa_response

            # No 2FA — normal flow
            if _is_native_request(request):
                _inject_refresh_token(response)

        elif response.status_code == 400:
            # Failed login — increment counters
            for ident in identifiers:
                key = _fail_count_key(ident)
                try:
                    fails = cache.incr(key)
                except ValueError:
                    cache.set(key, 1, timeout=_LOCKOUT_SECONDS)
                    fails = 1
                if fails >= _MAX_FAILED_ATTEMPTS:
                    cache.set(_lockout_key(ident), True, timeout=_LOCKOUT_SECONDS)
                    logger.warning('Account lockout triggered for %s after %d failures', ident, fails)

        return response


class TwoFactorChallengeView(APIView):
    """
    Unauthenticated endpoint for completing 2FA login.

    Accepts a challenge_token (from login) + TOTP code or backup code.
    If valid, issues JWT access + refresh tokens.
    """
    permission_classes = [AllowAny]
    throttle_classes = [AuthRateThrottle]

    def post(self, request):
        challenge_token = request.data.get('challengeToken', '').strip()
        code = request.data.get('code', '').strip()

        if not challenge_token or not code:
            return Response(
                {'error': 'Challenge token and verification code are required.'},
                status=http_status.HTTP_400_BAD_REQUEST,
            )

        # Verify challenge token
        user_id = _verify_challenge_token(challenge_token)
        if not user_id:
            return Response(
                {'error': 'Invalid or expired challenge. Please log in again.'},
                status=http_status.HTTP_400_BAD_REQUEST,
            )

        try:
            user = User.objects.get(id=user_id, is_active=True)
        except User.DoesNotExist:
            return Response(
                {'error': 'Invalid challenge.'},
                status=http_status.HTTP_400_BAD_REQUEST,
            )

        if not user.totp_enabled or not user.totp_secret:
            return Response(
                {'error': '2FA is not enabled for this account.'},
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
                user.save(update_fields=['backup_codes'])
                verified = True

        if not verified:
            return Response(
                {'error': 'Invalid verification code.'},
                status=http_status.HTTP_400_BAD_REQUEST,
            )

        # 2FA verified — issue JWT tokens
        refresh = RefreshToken.for_user(user)
        data = {
            'access': str(refresh.access_token),
            'user': {'id': str(user.id), 'email': user.email},
        }

        # Native clients need the refresh token in the body (can't read httpOnly cookies).
        # Web clients get it as an httpOnly cookie only — never in the body.
        if _is_native_request(request):
            data['refresh'] = str(refresh)

        response = Response(data, status=http_status.HTTP_200_OK)

        # Set refresh token as httpOnly cookie (same as dj-rest-auth behavior)
        from datetime import timedelta
        cookie_max_age = int(timedelta(days=7).total_seconds())
        response.set_cookie(
            _COOKIE_NAME,
            str(refresh),
            max_age=cookie_max_age,
            httponly=True,
            samesite=settings.REST_AUTH.get('JWT_AUTH_SAMESITE', 'Lax'),
            secure=settings.REST_AUTH.get('JWT_AUTH_SECURE', not settings.DEBUG),
            path=settings.REST_AUTH.get('JWT_AUTH_COOKIE_PATH', '/'),
        )

        return response


class VerifyEmailView(APIView):
    """
    Verify an email confirmation key sent by allauth.

    The frontend SPA receives the key from the confirmation URL
    (e.g. /verify-email?key=abc123) and posts it here to confirm
    the email address.
    """
    permission_classes = [AllowAny]
    throttle_classes = [AuthRateThrottle]

    def _verify_key(self, request, key):
        """Core verification logic shared by GET and POST."""
        if not key:
            return Response(
                {'detail': 'Confirmation key is required.'},
                status=http_status.HTTP_400_BAD_REQUEST,
            )

        from allauth.account.models import EmailConfirmationHMAC, EmailConfirmation

        # Try HMAC-based key first (allauth >= 0.53)
        emailconfirmation = EmailConfirmationHMAC.from_key(key)
        if not emailconfirmation:
            # Fallback to DB-based key
            try:
                emailconfirmation = EmailConfirmation.objects.get(key=key)
            except EmailConfirmation.DoesNotExist:
                return Response(
                    {'detail': 'Invalid or expired confirmation link. Please request a new one.'},
                    status=http_status.HTTP_400_BAD_REQUEST,
                )

        # Confirm the email (idempotent if already verified)
        if not emailconfirmation.email_address.verified:
            emailconfirmation.confirm(request)

        return Response({'detail': 'Email verified successfully.'})

    def post(self, request):
        key = (request.data.get('key') or '').strip()
        return self._verify_key(request, key)

    def get(self, request):
        """Support GET for convenience — direct clicks from email."""
        key = request.query_params.get('key', '').strip()
        return self._verify_key(request, key)


class ResendVerificationView(APIView):
    """
    Resend email verification to the authenticated user's primary email.

    No email parameter accepted — uses the email from the JWT token.
    This prevents users from triggering resends for other accounts.
    """
    throttle_classes = [AuthRateThrottle]

    def post(self, request):
        from allauth.account.models import EmailAddress
        ea = EmailAddress.objects.filter(
            user=request.user, primary=True, verified=False,
        ).first()
        if ea:
            ea.send_confirmation(request)
        # Always return OK to avoid leaking whether the email exists
        return Response({'detail': 'ok'})


class NativeAwareRegisterView(RegisterView):
    """
    Registration view that returns refresh token in body for native clients.
    Web clients get the standard httpOnly cookie behavior.
    """
    throttle_classes = [AuthRateThrottle]

    def create(self, request, *args, **kwargs):
        response = super().create(request, *args, **kwargs)
        if _is_native_request(request) and response.status_code in (200, 201):
            _inject_refresh_token(response)
        return response
