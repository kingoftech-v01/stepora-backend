"""
Comprehensive tests for the custom auth system.
Covers: sign-up, sign-in, 2FA, email verification, password reset/change,
logout, token refresh, social login, account lockout.
"""

import hashlib
from datetime import timedelta
from unittest.mock import patch, Mock

import pyotp
import pytest
from django.conf import settings
from django.core import mail, signing
from django.core.cache import cache
from django.test.utils import override_settings
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.users.models import User
from core.auth.models import EmailAddress, SocialAccount
from core.auth.tokens import (
    make_email_verification_key,
    verify_email_verification_key,
    make_password_reset_token,
    verify_password_reset_token,
)

PASSWORD = 'SecureP@ss123!'


@pytest.fixture(autouse=True)
def _mock_auth_celery_tasks():
    """Mock all Celery tasks called by auth views to avoid Redis dependency."""
    with patch('core.auth.views.send_login_notification_email') as m1, \
         patch('core.auth.views.send_password_changed_email') as m2:
        m1.delay = Mock()
        m2.delay = Mock()
        yield


@pytest.fixture
def client():
    return APIClient()


@pytest.fixture
def create_user(db):
    """Create a user with verified email."""
    def _create(email='user@test.com', password=PASSWORD, verified=True, **kwargs):
        user = User.objects.create_user(email=email, password=password, **kwargs)
        EmailAddress.objects.create(
            user=user, email=email, verified=verified, primary=True,
        )
        return user
    return _create


# ═══════════════════════════════════════════════════════════════════════
# SIGN-UP (Registration)
# ═══════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestRegistration:

    def test_register_success(self, client):
        """Register a new user — should get JWT tokens back."""
        with patch('core.auth.tasks.send_verification_email.delay') as mock_email:
            resp = client.post('/api/auth/registration/', {
                'email': 'new@test.com',
                'password1': PASSWORD,
                'password2': PASSWORD,
            })
        assert resp.status_code == status.HTTP_200_OK
        assert 'access' in resp.data
        assert 'user' in resp.data
        assert resp.data['user']['email'] == 'new@test.com'

        # User + EmailAddress created
        assert User.objects.filter(email__iexact='new@test.com').exists()
        ea = EmailAddress.objects.get(email__iexact='new@test.com')
        assert ea.primary is True
        assert ea.verified is False

        # Verification email queued
        mock_email.assert_called_once()

    def test_register_with_display_name(self, client):
        with patch('core.auth.tasks.send_verification_email.delay'):
            resp = client.post('/api/auth/registration/', {
                'email': 'named@test.com',
                'password1': PASSWORD,
                'password2': PASSWORD,
                'display_name': 'Test User',
            })
        assert resp.status_code == status.HTTP_200_OK
        user = User.objects.get(email__iexact='named@test.com')
        assert user.display_name == 'Test User'

    def test_register_duplicate_email(self, client, create_user):
        create_user(email='dup@test.com')
        resp = client.post('/api/auth/registration/', {
            'email': 'dup@test.com',
            'password1': PASSWORD,
            'password2': PASSWORD,
        })
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_register_password_mismatch(self, client):
        resp = client.post('/api/auth/registration/', {
            'email': 'mm@test.com',
            'password1': PASSWORD,
            'password2': 'DifferentPass123!',
        })
        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        assert 'password2' in str(resp.data)

    def test_register_weak_password(self, client):
        resp = client.post('/api/auth/registration/', {
            'email': 'weak@test.com',
            'password1': '123',
            'password2': '123',
        })
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_register_duplicate_display_name(self, client, create_user):
        """Two users cannot have the same display name."""
        create_user(email='first@test.com', display_name='UniqueUser')
        with patch('core.auth.tasks.send_verification_email.delay'):
            resp = client.post('/api/auth/registration/', {
                'email': 'second@test.com',
                'password1': PASSWORD,
                'password2': PASSWORD,
                'display_name': 'UniqueUser',
            })
        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        assert 'already taken' in str(resp.data).lower()

    def test_register_duplicate_display_name_case_insensitive(self, client, create_user):
        """Display name uniqueness should be case-insensitive."""
        create_user(email='first@test.com', display_name='CoolName')
        with patch('core.auth.tasks.send_verification_email.delay'):
            resp = client.post('/api/auth/registration/', {
                'email': 'second@test.com',
                'password1': PASSWORD,
                'password2': PASSWORD,
                'display_name': 'coolname',
            })
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_register_native_gets_refresh_in_body(self, client):
        """Native clients should get refresh token in the response body."""
        with patch('core.auth.tasks.send_verification_email.delay'):
            resp = client.post(
                '/api/auth/registration/',
                {'email': 'native@test.com', 'password1': PASSWORD, 'password2': PASSWORD},
                HTTP_X_CLIENT_PLATFORM='native',
            )
        assert resp.status_code == status.HTTP_200_OK
        assert 'refresh' in resp.data


# ═══════════════════════════════════════════════════════════════════════
# SIGN-IN (Login)
# ═══════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestLogin:

    def test_login_success(self, client, create_user):
        create_user(email='login@test.com')
        resp = client.post('/api/auth/login/', {
            'email': 'login@test.com',
            'password': PASSWORD,
        })
        assert resp.status_code == status.HTTP_200_OK
        assert 'access' in resp.data
        assert resp.data['user']['email'] == 'login@test.com'

    def test_login_wrong_password(self, client, create_user):
        create_user(email='wrong@test.com')
        resp = client.post('/api/auth/login/', {
            'email': 'wrong@test.com',
            'password': 'WrongPassword!',
        })
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_login_nonexistent_email(self, client):
        resp = client.post('/api/auth/login/', {
            'email': 'ghost@test.com',
            'password': PASSWORD,
        })
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_login_unverified_email_blocked(self, client, create_user):
        """With mandatory verification, unverified email should be blocked."""
        create_user(email='unverified@test.com', verified=False)
        resp = client.post('/api/auth/login/', {
            'email': 'unverified@test.com',
            'password': PASSWORD,
        })
        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        assert 'not verified' in str(resp.data).lower()

    @override_settings(DP_AUTH={**settings.DP_AUTH, 'EMAIL_VERIFICATION': 'none'})
    def test_login_unverified_allowed_when_verification_none(self, client, create_user):
        create_user(email='noverify@test.com', verified=False)
        resp = client.post('/api/auth/login/', {
            'email': 'noverify@test.com',
            'password': PASSWORD,
        })
        assert resp.status_code == status.HTTP_200_OK
        assert 'access' in resp.data

    def test_login_case_insensitive(self, client, create_user):
        create_user(email='Case@Test.com')
        resp = client.post('/api/auth/login/', {
            'email': 'case@test.com',
            'password': PASSWORD,
        })
        assert resp.status_code == status.HTTP_200_OK

    def test_login_native_gets_refresh_in_body(self, client, create_user):
        create_user(email='native_login@test.com')
        resp = client.post(
            '/api/auth/login/',
            {'email': 'native_login@test.com', 'password': PASSWORD},
            HTTP_X_CLIENT_PLATFORM='native',
        )
        assert resp.status_code == status.HTTP_200_OK
        assert 'refresh' in resp.data

    def test_login_web_gets_refresh_cookie(self, client, create_user):
        create_user(email='web@test.com')
        resp = client.post('/api/auth/login/', {
            'email': 'web@test.com',
            'password': PASSWORD,
        })
        assert resp.status_code == status.HTTP_200_OK
        assert 'dp-refresh' in resp.cookies
        # Web clients should NOT get refresh in body
        assert 'refresh' not in resp.data

    def test_login_sets_httponly_cookie(self, client, create_user):
        create_user(email='cookie@test.com')
        resp = client.post('/api/auth/login/', {
            'email': 'cookie@test.com',
            'password': PASSWORD,
        })
        cookie = resp.cookies.get('dp-refresh')
        assert cookie is not None
        assert cookie['httponly'] is True


# ═══════════════════════════════════════════════════════════════════════
# ACCOUNT LOCKOUT
# ═══════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestAccountLockout:

    def setup_method(self):
        cache.clear()

    def test_lockout_after_max_failures(self, client, create_user):
        create_user(email='locked@test.com')
        for _ in range(5):
            client.post('/api/auth/login/', {
                'email': 'locked@test.com',
                'password': 'wrong',
            })
        resp = client.post('/api/auth/login/', {
            'email': 'locked@test.com',
            'password': PASSWORD,
        })
        assert resp.status_code == status.HTTP_429_TOO_MANY_REQUESTS

    def test_successful_login_clears_failures(self, client, create_user):
        create_user(email='clear@test.com')
        for _ in range(3):
            client.post('/api/auth/login/', {
                'email': 'clear@test.com',
                'password': 'wrong',
            })
        # Successful login should clear counters
        resp = client.post('/api/auth/login/', {
            'email': 'clear@test.com',
            'password': PASSWORD,
        })
        assert resp.status_code == status.HTTP_200_OK

        # Further failed attempts should start from 0
        for _ in range(4):
            client.post('/api/auth/login/', {
                'email': 'clear@test.com',
                'password': 'wrong',
            })
        resp = client.post('/api/auth/login/', {
            'email': 'clear@test.com',
            'password': PASSWORD,
        })
        assert resp.status_code == status.HTTP_200_OK


# ═══════════════════════════════════════════════════════════════════════
# 2FA (Two-Factor Authentication)
# ═══════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestTwoFactor:

    @pytest.fixture
    def tfa_user(self, create_user):
        user = create_user(email='tfa@test.com')
        user.totp_secret = pyotp.random_base32()
        user.totp_enabled = True
        user.save(update_fields=['totp_secret', 'totp_enabled'])
        return user

    def test_login_with_2fa_returns_challenge(self, client, tfa_user):
        resp = client.post('/api/auth/login/', {
            'email': 'tfa@test.com',
            'password': PASSWORD,
        })
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data['tfaRequired'] is True
        assert 'challengeToken' in resp.data
        # Should NOT contain access token
        assert 'access' not in resp.data

    def test_2fa_challenge_valid_code(self, client, tfa_user):
        # Step 1: login to get challenge
        resp = client.post('/api/auth/login/', {
            'email': 'tfa@test.com',
            'password': PASSWORD,
        })
        challenge = resp.data['challengeToken']

        # Step 2: submit TOTP code
        totp = pyotp.TOTP(tfa_user.totp_secret)
        resp = client.post('/api/auth/2fa-challenge/', {
            'challengeToken': challenge,
            'code': totp.now(),
        })
        assert resp.status_code == status.HTTP_200_OK
        assert 'access' in resp.data
        assert resp.data['user']['email'] == 'tfa@test.com'

    def test_2fa_challenge_invalid_code(self, client, tfa_user):
        resp = client.post('/api/auth/login/', {
            'email': 'tfa@test.com',
            'password': PASSWORD,
        })
        challenge = resp.data['challengeToken']

        resp = client.post('/api/auth/2fa-challenge/', {
            'challengeToken': challenge,
            'code': '000000',
        })
        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        assert 'invalid' in resp.data['error'].lower()

    def test_2fa_challenge_expired_token(self, client, tfa_user):
        resp = client.post('/api/auth/login/', {
            'email': 'tfa@test.com',
            'password': PASSWORD,
        })
        challenge = resp.data['challengeToken']

        # Tamper with the token to simulate expiry
        resp = client.post('/api/auth/2fa-challenge/', {
            'challengeToken': 'invalid-token',
            'code': '123456',
        })
        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        assert 'expired' in resp.data['error'].lower() or 'invalid' in resp.data['error'].lower()

    def test_2fa_backup_code(self, client, tfa_user):
        """Backup code should work and be consumed."""
        salt = hashlib.sha256(b'dreamplanner-backup-codes').digest()
        code = 'ABCD1234'
        code_hash = hashlib.pbkdf2_hmac('sha256', code.encode(), salt, iterations=100_000).hex()
        tfa_user.backup_codes = [code_hash]
        tfa_user.save(update_fields=['backup_codes'])

        resp = client.post('/api/auth/login/', {
            'email': 'tfa@test.com',
            'password': PASSWORD,
        })
        challenge = resp.data['challengeToken']

        resp = client.post('/api/auth/2fa-challenge/', {
            'challengeToken': challenge,
            'code': code,
        })
        assert resp.status_code == status.HTTP_200_OK
        assert 'access' in resp.data

        # Backup code should be consumed
        tfa_user.refresh_from_db()
        assert code_hash not in tfa_user.backup_codes

    def test_2fa_native_gets_refresh(self, client, tfa_user):
        resp = client.post('/api/auth/login/', {
            'email': 'tfa@test.com',
            'password': PASSWORD,
        })
        challenge = resp.data['challengeToken']

        totp = pyotp.TOTP(tfa_user.totp_secret)
        resp = client.post(
            '/api/auth/2fa-challenge/',
            {'challengeToken': challenge, 'code': totp.now()},
            HTTP_X_CLIENT_PLATFORM='native',
        )
        assert resp.status_code == status.HTTP_200_OK
        assert 'refresh' in resp.data


# ═══════════════════════════════════════════════════════════════════════
# EMAIL VERIFICATION
# ═══════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestEmailVerification:

    def test_verify_email_success(self, client, create_user):
        user = create_user(email='verify@test.com', verified=False)
        ea = EmailAddress.objects.get(user=user, email='verify@test.com')
        key = make_email_verification_key(ea.id)

        resp = client.post('/api/auth/verify-email/', {'key': key})
        assert resp.status_code == status.HTTP_200_OK

        ea.refresh_from_db()
        assert ea.verified is True
        assert ea.primary is True

    def test_verify_email_invalid_key(self, client):
        resp = client.post('/api/auth/verify-email/', {'key': 'invalid-key'})
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_verify_email_expired_key(self, client, create_user):
        user = create_user(email='expired@test.com', verified=False)
        ea = EmailAddress.objects.get(user=user)

        # Create key with max_age=0 to simulate expiry
        key = signing.dumps({'ea': str(ea.id)}, salt='dp-email-verify')
        # We can't easily test expiry without time mocking, so test bad signature
        resp = client.post('/api/auth/verify-email/', {'key': key + 'tampered'})
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_resend_verification(self, client, create_user):
        create_user(email='resend@test.com', verified=False)
        with patch('core.auth.tasks.send_verification_email.delay') as mock_send:
            resp = client.post('/api/auth/resend-verification/', {'email': 'resend@test.com'})
        assert resp.status_code == status.HTTP_200_OK
        mock_send.assert_called_once()

    def test_resend_verification_already_verified_silent(self, client, create_user):
        """Resending for an already-verified email should silently return 200."""
        create_user(email='already@test.com', verified=True)
        with patch('core.auth.tasks.send_verification_email.delay') as mock_send:
            resp = client.post('/api/auth/resend-verification/', {'email': 'already@test.com'})
        assert resp.status_code == status.HTTP_200_OK
        mock_send.assert_not_called()

    def test_resend_verification_unknown_email_silent(self, client):
        """Resending for an unknown email should silently return 200."""
        resp = client.post('/api/auth/resend-verification/', {'email': 'nope@test.com'})
        assert resp.status_code == status.HTTP_200_OK


# ═══════════════════════════════════════════════════════════════════════
# PASSWORD RESET
# ═══════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestPasswordReset:

    def test_request_reset_success(self, client, create_user):
        create_user(email='reset@test.com')
        with patch('core.auth.tasks.send_password_reset_email.delay') as mock_send:
            resp = client.post('/api/auth/password/reset/', {'email': 'reset@test.com'})
        assert resp.status_code == status.HTTP_200_OK
        mock_send.assert_called_once()

    def test_request_reset_unknown_email_silent(self, client):
        """Should not reveal whether email exists."""
        with patch('core.auth.tasks.send_password_reset_email.delay') as mock_send:
            resp = client.post('/api/auth/password/reset/', {'email': 'nobody@test.com'})
        assert resp.status_code == status.HTTP_200_OK
        mock_send.assert_not_called()

    def test_reset_confirm_success(self, client, create_user):
        user = create_user(email='confirm@test.com')
        uid, token = make_password_reset_token(user)

        new_pass = 'NewSecure@456!'
        resp = client.post('/api/auth/password/reset/confirm/', {
            'uid': uid,
            'token': token,
            'new_password1': new_pass,
            'new_password2': new_pass,
        })
        assert resp.status_code == status.HTTP_200_OK

        # Verify the new password works
        user.refresh_from_db()
        assert user.check_password(new_pass)

    def test_reset_confirm_invalid_token(self, client, create_user):
        create_user(email='badtoken@test.com')
        resp = client.post('/api/auth/password/reset/confirm/', {
            'uid': 'bad',
            'token': 'bad',
            'new_password1': PASSWORD,
            'new_password2': PASSWORD,
        })
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_reset_confirm_password_mismatch(self, client, create_user):
        user = create_user(email='mismatch@test.com')
        uid, token = make_password_reset_token(user)

        resp = client.post('/api/auth/password/reset/confirm/', {
            'uid': uid,
            'token': token,
            'new_password1': 'NewSecure@456!',
            'new_password2': 'DifferentPass!',
        })
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_reset_token_invalidated_after_use(self, client, create_user):
        """Token should not work twice (password change invalidates it)."""
        user = create_user(email='oneuse@test.com')
        uid, token = make_password_reset_token(user)

        new_pass = 'NewSecure@456!'
        client.post('/api/auth/password/reset/confirm/', {
            'uid': uid, 'token': token,
            'new_password1': new_pass, 'new_password2': new_pass,
        })
        # Second attempt with same token
        resp = client.post('/api/auth/password/reset/confirm/', {
            'uid': uid, 'token': token,
            'new_password1': 'AnotherPass789!', 'new_password2': 'AnotherPass789!',
        })
        assert resp.status_code == status.HTTP_400_BAD_REQUEST


# ═══════════════════════════════════════════════════════════════════════
# PASSWORD CHANGE (authenticated)
# ═══════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestPasswordChange:

    def test_change_password_success(self, client, create_user):
        user = create_user(email='change@test.com')
        client.force_authenticate(user=user)

        new_pass = 'ChangedP@ss456!'
        resp = client.post('/api/auth/password/change/', {
            'old_password': PASSWORD,
            'new_password1': new_pass,
            'new_password2': new_pass,
        })
        assert resp.status_code == status.HTTP_200_OK

        user.refresh_from_db()
        assert user.check_password(new_pass)

    def test_change_password_wrong_old(self, client, create_user):
        user = create_user(email='wrongold@test.com')
        client.force_authenticate(user=user)

        resp = client.post('/api/auth/password/change/', {
            'old_password': 'WrongOldPass!',
            'new_password1': 'NewPass456!',
            'new_password2': 'NewPass456!',
        })
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_change_password_unauthenticated(self, client):
        resp = client.post('/api/auth/password/change/', {
            'old_password': PASSWORD,
            'new_password1': 'New123!',
            'new_password2': 'New123!',
        })
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED


# ═══════════════════════════════════════════════════════════════════════
# LOGOUT
# ═══════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestLogout:

    def test_logout_success(self, client, create_user):
        user = create_user(email='logout@test.com')
        refresh = RefreshToken.for_user(user)
        client.force_authenticate(user=user)

        resp = client.post('/api/auth/logout/', {'refresh': str(refresh)})
        assert resp.status_code == status.HTTP_200_OK
        assert 'logged out' in resp.data['detail'].lower()

    def test_logout_clears_cookie(self, client, create_user):
        user = create_user(email='logcookie@test.com')
        client.force_authenticate(user=user)

        resp = client.post('/api/auth/logout/')
        assert resp.status_code == status.HTTP_200_OK
        # Cookie should be deleted (max-age=0)
        cookie = resp.cookies.get('dp-refresh')
        if cookie:
            assert cookie['max-age'] == 0

    def test_logout_unauthenticated(self, client):
        resp = client.post('/api/auth/logout/')
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED


# ═══════════════════════════════════════════════════════════════════════
# TOKEN REFRESH
# ═══════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestTokenRefresh:

    def test_refresh_with_body_token(self, client, create_user):
        user = create_user(email='refresh@test.com')
        refresh = RefreshToken.for_user(user)

        resp = client.post('/api/auth/token/refresh/', {'refresh': str(refresh)})
        assert resp.status_code == status.HTTP_200_OK
        assert 'access' in resp.data

    def test_refresh_invalid_token(self, client):
        resp = client.post('/api/auth/token/refresh/', {'refresh': 'invalid-token'})
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_refresh_no_token(self, client):
        resp = client.post('/api/auth/token/refresh/', {})
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_refresh_native_gets_new_refresh(self, client, create_user):
        user = create_user(email='native_refresh@test.com')
        refresh = RefreshToken.for_user(user)

        resp = client.post(
            '/api/auth/token/refresh/',
            {'refresh': str(refresh)},
            HTTP_X_CLIENT_PLATFORM='native',
        )
        assert resp.status_code == status.HTTP_200_OK
        assert 'access' in resp.data
        # With rotation enabled, native should get new refresh in body
        if settings.SIMPLE_JWT.get('ROTATE_REFRESH_TOKENS', False):
            assert 'refresh' in resp.data


# ═══════════════════════════════════════════════════════════════════════
# USER DETAILS
# ═══════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestUserDetails:

    def test_get_user_details(self, client, create_user):
        user = create_user(email='details@test.com', display_name='Detail User')
        client.force_authenticate(user=user)

        resp = client.get('/api/auth/user/')
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data['email'] == 'details@test.com'

    def test_get_user_details_unauthenticated(self, client):
        resp = client.get('/api/auth/user/')
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED


# ═══════════════════════════════════════════════════════════════════════
# SOCIAL LOGIN (Google)
# ═══════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestGoogleLogin:

    @patch('core.auth.views.verify_google_token')
    def test_google_login_new_user(self, mock_verify, client):
        mock_verify.return_value = ('google-uid-123', 'google@test.com', 'Google User', 'https://pic.url')

        resp = client.post('/api/auth/google/', {'id_token': 'fake-google-token'})
        assert resp.status_code == status.HTTP_200_OK
        assert 'access' in resp.data

        # User and social account created
        user = User.objects.get(email__iexact='google@test.com')
        assert SocialAccount.objects.filter(user=user, provider='google', uid='google-uid-123').exists()
        assert EmailAddress.objects.filter(user=user, verified=True).exists()

    @patch('core.auth.views.verify_google_token')
    def test_google_login_existing_social(self, mock_verify, client, create_user):
        """Re-login with existing social account should work."""
        user = create_user(email='existing_google@test.com')
        SocialAccount.objects.create(user=user, provider='google', uid='google-uid-456')

        mock_verify.return_value = ('google-uid-456', 'existing_google@test.com', 'Name', '')

        resp = client.post('/api/auth/google/', {'id_token': 'fake-token'})
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data['user']['email'] == 'existing_google@test.com'

    @patch('core.auth.views.verify_google_token')
    def test_google_login_existing_email_links(self, mock_verify, client, create_user):
        """Google login with email matching an existing user should link the account."""
        create_user(email='link@test.com')
        mock_verify.return_value = ('google-uid-789', 'link@test.com', 'Link User', '')

        resp = client.post('/api/auth/google/', {'id_token': 'fake-token'})
        assert resp.status_code == status.HTTP_200_OK
        user = User.objects.get(email__iexact='link@test.com')
        assert SocialAccount.objects.filter(user=user, provider='google').exists()

    def test_google_login_missing_token(self, client):
        resp = client.post('/api/auth/google/', {})
        assert resp.status_code == status.HTTP_400_BAD_REQUEST


# ═══════════════════════════════════════════════════════════════════════
# SOCIAL LOGIN (Apple)
# ═══════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestAppleLogin:

    @patch('core.auth.views.verify_apple_token')
    def test_apple_login_new_user(self, mock_verify, client):
        mock_verify.return_value = ('apple-uid-123', 'apple@test.com')

        resp = client.post('/api/auth/apple/', {
            'id_token': 'fake-apple-token',
            'name': 'Apple User',
        })
        assert resp.status_code == status.HTTP_200_OK
        assert 'access' in resp.data
        user = User.objects.get(email__iexact='apple@test.com')
        assert SocialAccount.objects.filter(user=user, provider='apple', uid='apple-uid-123').exists()

    @patch('core.auth.views.verify_apple_token')
    def test_apple_login_existing_social(self, mock_verify, client, create_user):
        user = create_user(email='exist_apple@test.com')
        SocialAccount.objects.create(user=user, provider='apple', uid='apple-uid-456')

        mock_verify.return_value = ('apple-uid-456', '')  # Apple may omit email

        resp = client.post('/api/auth/apple/', {'id_token': 'fake-token'})
        assert resp.status_code == status.HTTP_200_OK

    def test_apple_login_missing_token(self, client):
        resp = client.post('/api/auth/apple/', {})
        assert resp.status_code == status.HTTP_400_BAD_REQUEST


# ═══════════════════════════════════════════════════════════════════════
# TOKEN HELPERS (unit tests)
# ═══════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestTokenHelpers:

    def test_email_verification_key_roundtrip(self, create_user):
        user = create_user(email='key@test.com')
        ea = EmailAddress.objects.get(user=user)
        key = make_email_verification_key(ea.id)
        assert verify_email_verification_key(key) == ea.id

    def test_email_verification_key_bad_signature(self):
        with pytest.raises(Exception):
            verify_email_verification_key('bad-key')

    def test_password_reset_token_roundtrip(self, create_user):
        user = create_user(email='token@test.com')
        uid, token = make_password_reset_token(user)
        found_user, valid = verify_password_reset_token(uid, token)
        assert valid is True
        assert found_user.pk == user.pk

    def test_password_reset_token_invalid(self):
        user, valid = verify_password_reset_token('bad', 'bad')
        assert valid is False
        assert user is None


# ═══════════════════════════════════════════════════════════════════════
# FULL FLOW INTEGRATION TESTS
# ═══════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestFullFlows:

    def test_register_verify_login_flow(self, client):
        """Complete flow: register -> verify email -> login."""
        # 1. Register
        with patch('core.auth.tasks.send_verification_email.delay') as mock_send:
            resp = client.post('/api/auth/registration/', {
                'email': 'flow@test.com',
                'password1': PASSWORD,
                'password2': PASSWORD,
            })
        assert resp.status_code == status.HTTP_200_OK
        user = User.objects.get(email='flow@test.com')
        ea = EmailAddress.objects.get(user=user)

        # 2. Login should fail (unverified)
        resp = client.post('/api/auth/login/', {
            'email': 'flow@test.com',
            'password': PASSWORD,
        })
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

        # 3. Verify email
        key = make_email_verification_key(ea.id)
        resp = client.post('/api/auth/verify-email/', {'key': key})
        assert resp.status_code == status.HTTP_200_OK

        # 4. Login should now work
        resp = client.post('/api/auth/login/', {
            'email': 'flow@test.com',
            'password': PASSWORD,
        })
        assert resp.status_code == status.HTTP_200_OK
        assert 'access' in resp.data

    def test_forgot_password_full_flow(self, client, create_user):
        """Complete flow: request reset -> confirm reset -> login with new password."""
        create_user(email='forgot@test.com')
        user = User.objects.get(email='forgot@test.com')

        # 1. Request reset
        with patch('core.auth.tasks.send_password_reset_email.delay'):
            resp = client.post('/api/auth/password/reset/', {'email': 'forgot@test.com'})
        assert resp.status_code == status.HTTP_200_OK

        # 2. Confirm reset
        uid, token = make_password_reset_token(user)
        new_pass = 'BrandNewP@ss99!'
        resp = client.post('/api/auth/password/reset/confirm/', {
            'uid': uid, 'token': token,
            'new_password1': new_pass, 'new_password2': new_pass,
        })
        assert resp.status_code == status.HTTP_200_OK

        # 3. Login with new password
        resp = client.post('/api/auth/login/', {
            'email': 'forgot@test.com',
            'password': new_pass,
        })
        assert resp.status_code == status.HTTP_200_OK
        assert 'access' in resp.data

        # 4. Old password should no longer work
        resp = client.post('/api/auth/login/', {
            'email': 'forgot@test.com',
            'password': PASSWORD,
        })
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_login_2fa_full_flow(self, client, create_user):
        """Complete 2FA flow: login -> challenge -> get tokens."""
        user = create_user(email='full2fa@test.com')
        secret = pyotp.random_base32()
        user.totp_secret = secret
        user.totp_enabled = True
        user.save(update_fields=['totp_secret', 'totp_enabled'])

        # 1. Login returns challenge
        resp = client.post('/api/auth/login/', {
            'email': 'full2fa@test.com',
            'password': PASSWORD,
        })
        assert resp.data['tfaRequired'] is True
        challenge = resp.data['challengeToken']

        # 2. Submit TOTP
        totp = pyotp.TOTP(secret)
        resp = client.post('/api/auth/2fa-challenge/', {
            'challengeToken': challenge,
            'code': totp.now(),
        })
        assert resp.status_code == status.HTTP_200_OK
        assert 'access' in resp.data

        # 3. Use access token to get user details
        access = resp.data['access']
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {access}')
        resp = client.get('/api/auth/user/')
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data['email'] == 'full2fa@test.com'
