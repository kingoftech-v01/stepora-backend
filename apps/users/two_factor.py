"""
Two-Factor Authentication (TOTP) views for DreamPlanner.

Provides TOTP setup, verification, disable, and backup code management.
Uses pyotp for TOTP generation and verification.
"""

import pyotp
import secrets
import logging

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema, inline_serializer, OpenApiResponse
from rest_framework import serializers as drf_serializers

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


class TwoFactorSetupView(APIView):
    """Generate a TOTP secret and provisioning URI for setup."""

    permission_classes = [IsAuthenticated]

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
            issuer_name='DreamPlanner',
        )

        # Store secret temporarily in app_prefs (not yet verified)
        prefs = user.app_prefs or {}
        prefs['totp_pending_secret'] = secret
        user.app_prefs = prefs
        user.save(update_fields=['app_prefs'])

        return Response({
            'secret': secret,
            'provisioning_uri': provisioning_uri,
            'message': 'Scan the QR code with your authenticator app, then verify with a code.',
        })


class TwoFactorVerifyView(APIView):
    """Verify a TOTP code to complete 2FA setup or login verification."""

    permission_classes = [IsAuthenticated]

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

        # Check if we're completing setup (pending secret) or verifying login
        pending_secret = prefs.get('totp_pending_secret')
        active_secret = prefs.get('totp_secret')

        secret = pending_secret or active_secret

        if not secret:
            return Response(
                {'error': '2FA is not set up. Call setup first.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        totp = pyotp.TOTP(secret)
        if not totp.verify(code, valid_window=1):
            # Check backup codes
            backup_codes = prefs.get('totp_backup_codes', [])
            if code in backup_codes:
                backup_codes.remove(code)
                prefs['totp_backup_codes'] = backup_codes
                user.app_prefs = prefs
                user.save(update_fields=['app_prefs'])
                return Response({
                    'verified': True,
                    'method': 'backup_code',
                    'remaining_backup_codes': len(backup_codes),
                })

            return Response(
                {'error': 'Invalid verification code.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # If completing setup, activate the secret and generate backup codes
        if pending_secret:
            backup_codes = _generate_backup_codes()
            prefs['totp_secret'] = pending_secret
            prefs['totp_enabled'] = True
            prefs['totp_backup_codes'] = backup_codes
            prefs.pop('totp_pending_secret', None)
            user.app_prefs = prefs
            user.save(update_fields=['app_prefs'])

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

        prefs = user.app_prefs or {}
        prefs.pop('totp_secret', None)
        prefs.pop('totp_pending_secret', None)
        prefs.pop('totp_enabled', None)
        prefs.pop('totp_backup_codes', None)
        user.app_prefs = prefs
        user.save(update_fields=['app_prefs'])

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
        prefs = request.user.app_prefs or {}
        return Response({
            'two_factor_enabled': prefs.get('totp_enabled', False),
            'backup_codes_remaining': len(prefs.get('totp_backup_codes', [])),
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

        prefs = user.app_prefs or {}
        if not prefs.get('totp_enabled'):
            return Response(
                {'error': '2FA is not enabled.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        backup_codes = _generate_backup_codes()
        prefs['totp_backup_codes'] = backup_codes
        user.app_prefs = prefs
        user.save(update_fields=['app_prefs'])

        return Response({
            'backup_codes': backup_codes,
            'message': 'New backup codes generated. Previous codes are now invalid.',
        })
