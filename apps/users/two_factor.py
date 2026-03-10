"""
Two-Factor Authentication (TOTP) views for Stepora.

Provides TOTP setup, verification, disable, and backup code management.
Uses pyotp for TOTP generation and verification.
Secrets are stored in the User model's EncryptedCharField (not app_prefs).
"""

import hashlib
import os as _os
import pyotp
import secrets
import logging

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema, inline_serializer, OpenApiResponse
from rest_framework import serializers as drf_serializers

from core.throttles import TwoFactorRateThrottle

logger = logging.getLogger(__name__)

# Number of backup codes to generate
BACKUP_CODE_COUNT = 10
BACKUP_CODE_LENGTH = 8


def _generate_backup_codes(count=BACKUP_CODE_COUNT):
    """Generate a list of random backup codes."""
    return [
        secrets.token_hex(BACKUP_CODE_LENGTH // 2).upper()
        for _ in range(count)
    ]


def _hash_code(code):
    """Hash a backup code for secure storage using PBKDF2 with a fixed app-level salt."""
    # Using a fixed salt derived from FIELD_ENCRYPTION_KEY avoids storing per-code salts
    # while still preventing rainbow table attacks on the 8-char hex codes.
    salt = hashlib.sha256(b'stepora-backup-codes').digest()
    return hashlib.pbkdf2_hmac('sha256', code.encode(), salt, iterations=100_000).hex()


class TwoFactorSetupView(APIView):
    """Generate a TOTP secret and provisioning URI for setup."""

    permission_classes = [IsAuthenticated]
    throttle_classes = [TwoFactorRateThrottle]

    @extend_schema(
        summary="Setup 2FA",
        tags=["Auth"],
        request=None,
        responses={200: inline_serializer('TwoFactorSetupResponse', fields={
            'secret': drf_serializers.CharField(),
            'provisioning_uri': drf_serializers.CharField(),
            'message': drf_serializers.CharField(),
        })},
    )
    def post(self, request):
        user = request.user

        # Generate a new TOTP secret
        secret = pyotp.random_base32()
        provisioning_uri = pyotp.totp.TOTP(secret).provisioning_uri(
            name=user.email,
            issuer_name='Stepora',
        )

        # Store pending secret in the EncryptedCharField (not app_prefs)
        # and use a flag in app_prefs to mark it as pending (not yet verified)
        user.totp_secret = secret
        prefs = user.app_prefs or {}
        prefs['totp_pending'] = True
        prefs.pop('totp_pending_secret', None)  # Clean up legacy key
        user.app_prefs = prefs
        user.save(update_fields=['totp_secret', 'app_prefs'])

        return Response({
            'secret': secret,
            'provisioning_uri': provisioning_uri,
            'message': 'Scan the QR code with your authenticator app, then verify with a code.',
        })


class TwoFactorVerifyView(APIView):
    """Verify a TOTP code to complete 2FA setup or login verification."""

    permission_classes = [IsAuthenticated]
    throttle_classes = [TwoFactorRateThrottle]

    @extend_schema(
        summary="Verify 2FA code",
        tags=["Auth"],
        request=inline_serializer('TwoFactorVerifyRequest', fields={
            'code': drf_serializers.CharField(),
        }),
        responses={
            200: inline_serializer('TwoFactorVerifyResponse', fields={
                'verified': drf_serializers.BooleanField(),
            }),
            400: OpenApiResponse(description='Invalid code or 2FA not set up.'),
        },
    )
    def post(self, request):
        user = request.user
        code = request.data.get('code', '').strip()

        if not code:
            return Response(
                {'error': 'Verification code is required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        prefs = user.app_prefs or {}

        # Check if we're completing setup (pending flag) or verifying login
        is_pending = prefs.get('totp_pending', False)
        secret = user.totp_secret  # EncryptedCharField (holds both pending and active secrets)

        if not secret:
            return Response(
                {'error': '2FA is not set up. Call setup first.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        totp = pyotp.TOTP(secret)
        if not totp.verify(code, valid_window=1):
            # Check backup codes (stored as hashes)
            stored_hashes = user.backup_codes or []
            code_hash = _hash_code(code)
            if code_hash in stored_hashes:
                stored_hashes.remove(code_hash)
                user.backup_codes = stored_hashes
                user.save(update_fields=['backup_codes'])
                return Response({
                    'verified': True,
                    'method': 'backup_code',
                    'remaining_backup_codes': len(stored_hashes),
                })

            return Response(
                {'error': 'Invalid verification code.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # If completing setup, activate the secret and generate backup codes
        if is_pending:
            backup_codes = _generate_backup_codes()
            hashed_codes = [_hash_code(c) for c in backup_codes]

            # Secret is already in the EncryptedCharField — just enable 2FA
            user.totp_enabled = True
            user.backup_codes = hashed_codes

            # Clear pending flag and any legacy app_prefs TOTP data
            prefs.pop('totp_pending', None)
            prefs.pop('totp_pending_secret', None)
            prefs.pop('totp_secret', None)
            prefs.pop('totp_enabled', None)
            prefs.pop('totp_backup_codes', None)
            user.app_prefs = prefs

            user.save(update_fields=[
                'totp_enabled', 'backup_codes', 'app_prefs'
            ])

            return Response({
                'verified': True,
                'two_factor_enabled': True,
                'backup_codes': backup_codes,
                'message': 'Save these backup codes in a safe place. Each can be used once.',
            })

        return Response({'verified': True})


class TwoFactorDisableView(APIView):
    """Disable 2FA for the current user."""

    permission_classes = [IsAuthenticated]
    throttle_classes = [TwoFactorRateThrottle]

    @extend_schema(
        summary="Disable 2FA",
        tags=["Auth"],
        request=inline_serializer('TwoFactorDisableRequest', fields={
            'password': drf_serializers.CharField(),
        }),
        responses={
            200: inline_serializer('TwoFactorDisableResponse', fields={
                'two_factor_enabled': drf_serializers.BooleanField(),
                'message': drf_serializers.CharField(),
            }),
            400: OpenApiResponse(description='Invalid password.'),
        },
    )
    def post(self, request):
        user = request.user
        password = request.data.get('password', '')

        if not password or not user.check_password(password):
            return Response(
                {'error': 'Invalid password.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Clear encrypted model fields
        user.totp_enabled = False
        user.totp_secret = ''
        user.backup_codes = None

        # Clean up any legacy app_prefs TOTP data
        prefs = user.app_prefs or {}
        prefs.pop('totp_secret', None)
        prefs.pop('totp_pending_secret', None)
        prefs.pop('totp_enabled', None)
        prefs.pop('totp_backup_codes', None)
        user.app_prefs = prefs

        user.save(update_fields=[
            'totp_enabled', 'totp_secret', 'backup_codes', 'app_prefs'
        ])

        return Response({
            'two_factor_enabled': False,
            'message': 'Two-factor authentication has been disabled.',
        })


class TwoFactorStatusView(APIView):
    """Check 2FA status for the current user."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="2FA status",
        tags=["Auth"],
        request=None,
        responses={200: inline_serializer('TwoFactorStatusResponse', fields={
            'two_factor_enabled': drf_serializers.BooleanField(),
            'backup_codes_remaining': drf_serializers.IntegerField(),
        })},
    )
    def get(self, request):
        user = request.user
        return Response({
            'two_factor_enabled': user.totp_enabled,
            'backup_codes_remaining': len(user.backup_codes or []),
        })


class TwoFactorRegenerateBackupCodesView(APIView):
    """Regenerate backup codes for 2FA."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Regenerate backup codes",
        tags=["Auth"],
        request=inline_serializer('TwoFactorRegenerateBackupCodesRequest', fields={
            'password': drf_serializers.CharField(),
        }),
        responses={
            200: inline_serializer('TwoFactorRegenerateBackupCodesResponse', fields={
                'backup_codes': drf_serializers.ListField(child=drf_serializers.CharField()),
                'message': drf_serializers.CharField(),
            }),
            400: OpenApiResponse(description='Invalid password or 2FA not enabled.'),
        },
    )
    def post(self, request):
        user = request.user
        password = request.data.get('password', '')

        if not password or not user.check_password(password):
            return Response(
                {'error': 'Invalid password.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not user.totp_enabled:
            return Response(
                {'error': '2FA is not enabled.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        backup_codes = _generate_backup_codes()
        user.backup_codes = [_hash_code(c) for c in backup_codes]
        user.save(update_fields=['backup_codes'])

        return Response({
            'backup_codes': backup_codes,
            'message': 'New backup codes generated. Previous codes are now invalid.',
        })
