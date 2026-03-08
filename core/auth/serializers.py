"""
Authentication serializers — replaces dj-rest-auth serializers.
"""

import logging

from django.conf import settings
from django.contrib.auth import authenticate, get_user_model, password_validation
from django.core import signing
from rest_framework import serializers

from core.auth.models import EmailAddress
from core.auth.tokens import verify_email_verification_key, verify_password_reset_token

logger = logging.getLogger(__name__)
User = get_user_model()

_DP_AUTH = getattr(settings, 'DP_AUTH', {})


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, style={'input_type': 'password'})

    def validate(self, attrs):
        email = User.objects.normalize_email(attrs['email'])
        password = attrs['password']

        user = authenticate(
            self.context.get('request'),
            email=email,
            password=password,
        )

        if not user:
            raise serializers.ValidationError(
                'Unable to log in with provided credentials.',
                code='invalid_credentials',
            )

        # Check email verification if mandatory
        verification = getattr(settings, 'DP_AUTH', {}).get('EMAIL_VERIFICATION', 'mandatory')
        if verification == 'mandatory':
            has_verified = EmailAddress.objects.filter(
                user=user, email__iexact=user.email, verified=True
            ).exists()
            if not has_verified:
                raise serializers.ValidationError(
                    'E-mail is not verified.',
                    code='email_not_verified',
                )

        attrs['user'] = user
        return attrs


class RegisterSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password1 = serializers.CharField(write_only=True, style={'input_type': 'password'})
    password2 = serializers.CharField(write_only=True, style={'input_type': 'password'})
    display_name = serializers.CharField(max_length=255, required=False, default='')

    def validate_email(self, value):
        email = User.objects.normalize_email(value)
        if User.objects.filter(email__iexact=email).exists():
            raise serializers.ValidationError('An account with this email already exists.')
        return email

    def validate_display_name(self, value):
        if value:
            from core.validators import validate_display_name
            return validate_display_name(value)
        return value

    def validate(self, attrs):
        if attrs['password1'] != attrs['password2']:
            raise serializers.ValidationError(
                {'password2': 'The two password fields did not match.'}
            )
        password_validation.validate_password(attrs['password1'])
        return attrs

    def save(self, request=None):
        email = self.validated_data['email']
        password = self.validated_data['password1']
        display_name = self.validated_data.get('display_name', '')

        user = User.objects.create_user(
            email=email,
            password=password,
            display_name=display_name,
        )

        verification = getattr(settings, 'DP_AUTH', {}).get('EMAIL_VERIFICATION', 'mandatory')

        email_addr = EmailAddress.objects.create(
            user=user,
            email=user.email,
            verified=(verification == 'none'),
            primary=True,
        )

        # Send verification email async
        if verification != 'none':
            from core.auth.tasks import send_verification_email
            send_verification_email.delay(str(user.id), email_addr.id)

        return user


class PasswordResetSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def save(self):
        email = User.objects.normalize_email(self.validated_data['email'])
        try:
            user = User.objects.get(email__iexact=email, is_active=True)
        except User.DoesNotExist:
            # Silently return — do not reveal whether account exists
            return

        from core.auth.tasks import send_password_reset_email
        send_password_reset_email.delay(str(user.id))


class PasswordResetConfirmSerializer(serializers.Serializer):
    uid = serializers.CharField()
    token = serializers.CharField()
    new_password1 = serializers.CharField(write_only=True, style={'input_type': 'password'})
    new_password2 = serializers.CharField(write_only=True, style={'input_type': 'password'})

    def validate(self, attrs):
        user, valid = verify_password_reset_token(attrs['uid'], attrs['token'])
        if not valid:
            raise serializers.ValidationError(
                'Invalid or expired password reset link.'
            )

        if attrs['new_password1'] != attrs['new_password2']:
            raise serializers.ValidationError(
                {'new_password2': 'The two password fields did not match.'}
            )

        password_validation.validate_password(attrs['new_password1'], user)
        self._user = user
        return attrs

    def save(self):
        self._user.set_password(self.validated_data['new_password1'])
        self._user.save(update_fields=['password'])


class PasswordChangeSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True, style={'input_type': 'password'})
    new_password1 = serializers.CharField(write_only=True, style={'input_type': 'password'})
    new_password2 = serializers.CharField(write_only=True, style={'input_type': 'password'})

    def validate_old_password(self, value):
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError('Invalid current password.')
        return value

    def validate(self, attrs):
        if attrs['new_password1'] != attrs['new_password2']:
            raise serializers.ValidationError(
                {'new_password2': 'The two password fields did not match.'}
            )
        password_validation.validate_password(
            attrs['new_password1'], self.context['request'].user
        )
        return attrs

    def save(self):
        user = self.context['request'].user
        user.set_password(self.validated_data['new_password1'])
        user.save(update_fields=['password'])


class EmailVerificationSerializer(serializers.Serializer):
    key = serializers.CharField()

    def validate_key(self, value):
        try:
            email_address_id = verify_email_verification_key(value)
        except (signing.BadSignature, signing.SignatureExpired):
            raise serializers.ValidationError('Invalid or expired verification link.')

        try:
            self._email_address = EmailAddress.objects.select_related('user').get(
                pk=email_address_id,
            )
        except EmailAddress.DoesNotExist:
            raise serializers.ValidationError('Invalid verification link.')

        return value

    def save(self):
        self._email_address.verify()
        self._email_address.set_as_primary()


class ResendVerificationSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def save(self):
        email = User.objects.normalize_email(self.validated_data['email'])
        try:
            email_addr = EmailAddress.objects.select_related('user').get(
                email__iexact=email,
                verified=False,
            )
        except EmailAddress.DoesNotExist:
            # Silently return
            return

        from core.auth.tasks import send_verification_email
        send_verification_email.delay(str(email_addr.user_id), email_addr.id)
