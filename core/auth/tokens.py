"""
HMAC token helpers for email verification and password reset.

Email verification uses django.core.signing (stateless, self-expiring HMAC).
Password reset uses Django's built-in PasswordResetTokenGenerator (HMAC).
Both approaches are the same as allauth's internals — no database rows needed.
"""

import logging

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.core import signing
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode

logger = logging.getLogger(__name__)

User = get_user_model()

_EMAIL_VERIFY_SALT = 'dp-email-verify'
_EMAIL_VERIFY_MAX_AGE = getattr(settings, 'DP_AUTH', {}).get(
    'VERIFICATION_KEY_MAX_AGE', 60 * 60 * 24 * 3  # 3 days
)

_PASSWORD_RESET_MAX_AGE = getattr(settings, 'DP_AUTH', {}).get(
    'PASSWORD_RESET_MAX_AGE', 60 * 60  # 1 hour
)

_password_reset_generator = PasswordResetTokenGenerator()


# ── Email verification ─────────────────────────────────────────────

def make_email_verification_key(email_address_id):
    """Create a stateless HMAC key for verifying an email address."""
    return signing.dumps(
        {'ea': str(email_address_id)},
        salt=_EMAIL_VERIFY_SALT,
    )


def verify_email_verification_key(key):
    """
    Verify an email verification key.
    Returns the email_address_id on success, raises on failure.
    """
    data = signing.loads(
        key,
        salt=_EMAIL_VERIFY_SALT,
        max_age=_EMAIL_VERIFY_MAX_AGE,
    )
    return int(data['ea'])


# ── Password reset ─────────────────────────────────────────────────

def make_password_reset_token(user):
    """
    Generate a (uid, token) pair for password reset.
    uid is base64-encoded user PK; token is HMAC-signed.
    """
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = _password_reset_generator.make_token(user)
    return uid, token


def verify_password_reset_token(uidb64, token):
    """
    Verify a password reset token.
    Returns (user, True) on success or (None, False) on failure.
    """
    try:
        user_id = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=user_id)
    except (ValueError, TypeError, User.DoesNotExist, OverflowError):
        return None, False

    if _password_reset_generator.check_token(user, token):
        return user, True

    return None, False
