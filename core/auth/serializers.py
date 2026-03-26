"""
Authentication serializers — replaces dj-rest-auth serializers.
"""

import logging

from django.conf import settings
from django.contrib.auth import authenticate, get_user_model, password_validation
from django.core import signing
from django.db import DatabaseError
from rest_framework import serializers

from core.auth.models import EmailAddress
from core.auth.tokens import verify_email_verification_key, verify_password_reset_token

logger = logging.getLogger(__name__)
User = get_user_model()

_DP_AUTH = getattr(settings, "DP_AUTH", {})


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, style={"input_type": "password"})

    def validate(self, attrs):
        email = User.objects.normalize_email(attrs["email"])
        password = attrs["password"]

        user = authenticate(
            self.context.get("request"),
            email=email,
            password=password,
        )

        if not user:
            raise serializers.ValidationError(
                "Unable to log in with provided credentials.",
                code="invalid_credentials",
            )

        # Check email verification if mandatory
        verification = getattr(settings, "DP_AUTH", {}).get(
            "EMAIL_VERIFICATION", "mandatory"
        )
        if verification == "mandatory":
            has_verified = EmailAddress.objects.filter(
                user=user, email__iexact=user.email, verified=True
            ).exists()
            if not has_verified:
                raise serializers.ValidationError(
                    "E-mail is not verified.",
                    code="email_not_verified",
                )

        attrs["user"] = user
        return attrs


class RegisterSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password1 = serializers.CharField(write_only=True, style={"input_type": "password"})
    password2 = serializers.CharField(write_only=True, style={"input_type": "password"})
    display_name = serializers.CharField(max_length=255, required=False, default="")
    # COPPA/age verification (V-343): optional date_of_birth field.
    # If provided, user must be at least 13 years old.
    # If not provided, agreed_to_terms implicitly confirms 13+ (terms state age requirement).
    date_of_birth = serializers.DateField(
        required=False,
        help_text="Date of birth for age verification (COPPA: must be 13+).",
    )
    # GDPR consent recording (V-333): must accept terms to register.
    agreed_to_terms = serializers.BooleanField(
        default=True,
        help_text="User must agree to Terms of Service and Privacy Policy (confirms 13+ age).",
    )
    # Honeypot field for bot detection (V-1476).
    # Real users never see or fill this field. Bots that auto-fill all fields
    # will populate it, causing registration to be silently rejected.
    website = serializers.CharField(required=False, default="", allow_blank=True)

    def validate_email(self, value):
        email = User.objects.normalize_email(value)
        # Store whether email exists — handled in save() to avoid
        # account enumeration (same response regardless of existence).
        self._email_exists = User.objects.filter(email__iexact=email).exists()
        return email

    def validate_display_name(self, value):
        if value:
            from core.validators import validate_display_name

            return validate_display_name(value)
        return value

    def validate_agreed_to_terms(self, value):
        if not value:
            raise serializers.ValidationError(
                "You must agree to the Terms of Service and Privacy Policy to create an account."
            )
        return value

    def validate_date_of_birth(self, value):
        """COPPA compliance: reject users under 13."""
        if value:
            import datetime

            today = datetime.date.today()
            age = (
                today.year
                - value.year
                - ((today.month, today.day) < (value.month, value.day))
            )
            if age < 13:
                raise serializers.ValidationError(
                    "You must be at least 13 years old to create an account."
                )
        return value

    def validate(self, attrs):
        # Honeypot check: if the hidden field has a value, it is a bot.
        # Raise a generic error that looks like a normal validation failure
        # so the bot cannot distinguish it from a real error.
        if attrs.get("website"):
            logger.warning(
                "Bot registration blocked (honeypot triggered): email=%s",
                attrs.get("email", "unknown"),
            )
            raise serializers.ValidationError(
                "Unable to create account. Please try again later."
            )

        if attrs["password1"] != attrs["password2"]:
            raise serializers.ValidationError(
                {"password2": "The two password fields did not match."}
            )
        password_validation.validate_password(attrs["password1"])
        return attrs

    def save(self, request=None):
        from django.utils import timezone as tz

        email = self.validated_data["email"]
        password = self.validated_data["password1"]
        display_name = self.validated_data.get("display_name", "")
        date_of_birth = self.validated_data.get("date_of_birth")

        # Prevent account enumeration: if email already exists, silently
        # send a notification to the existing account and return None.
        # The view returns the same generic response in both cases.
        if getattr(self, "_email_exists", False):
            logger.info("Registration attempted with existing email (enumeration prevented)")
            return None

        extra_fields = {}
        if date_of_birth:
            extra_fields["date_of_birth"] = date_of_birth

        # Record consent timestamp and version (V-333 GDPR)
        extra_fields["consent_accepted_at"] = tz.now()
        extra_fields["consent_version"] = "2026-03-26"

        user = User.objects.create_user(
            email=email,
            password=password,
            display_name=display_name,
            **extra_fields,
        )

        verification = getattr(settings, "DP_AUTH", {}).get(
            "EMAIL_VERIFICATION", "mandatory"
        )

        email_addr = EmailAddress.objects.create(
            user=user,
            email=user.email,
            verified=(verification == "none"),
            primary=True,
        )

        # Send verification email async
        if verification != "none":
            from core.auth.tasks import send_verification_email

            send_verification_email.delay(str(user.id), email_addr.id)

        return user


class PasswordResetSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def save(self):
        email = User.objects.normalize_email(self.validated_data["email"])
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
    new_password1 = serializers.CharField(
        write_only=True, style={"input_type": "password"}
    )
    new_password2 = serializers.CharField(
        write_only=True, style={"input_type": "password"}
    )

    def validate(self, attrs):
        user, valid = verify_password_reset_token(attrs["uid"], attrs["token"])
        if not valid:
            raise serializers.ValidationError("Invalid or expired password reset link.")

        if attrs["new_password1"] != attrs["new_password2"]:
            raise serializers.ValidationError(
                {"new_password2": "The two password fields did not match."}
            )

        password_validation.validate_password(attrs["new_password1"], user)
        self._user = user
        return attrs

    def save(self):
        self._user.set_password(self.validated_data["new_password1"])
        self._user.save(update_fields=["password"])
        # Invalidate all existing refresh tokens so stolen tokens are revoked
        self._invalidate_user_tokens(self._user)
        return self._user

    @staticmethod
    def _invalidate_user_tokens(user):
        try:
            from rest_framework_simplejwt.token_blacklist.models import OutstandingToken

            OutstandingToken.objects.filter(user=user).delete()
        except ImportError:
            pass
        except DatabaseError:
            logger.error("Failed to invalidate tokens for user %s on password reset", user.id)


class PasswordChangeSerializer(serializers.Serializer):
    old_password = serializers.CharField(
        write_only=True, style={"input_type": "password"}
    )
    new_password1 = serializers.CharField(
        write_only=True, style={"input_type": "password"}
    )
    new_password2 = serializers.CharField(
        write_only=True, style={"input_type": "password"}
    )

    def validate_old_password(self, value):
        user = self.context["request"].user
        if not user.check_password(value):
            raise serializers.ValidationError("Invalid current password.")
        return value

    def validate(self, attrs):
        if attrs["new_password1"] != attrs["new_password2"]:
            raise serializers.ValidationError(
                {"new_password2": "The two password fields did not match."}
            )
        password_validation.validate_password(
            attrs["new_password1"], self.context["request"].user
        )
        return attrs

    def save(self):
        user = self.context["request"].user
        user.set_password(self.validated_data["new_password1"])
        user.save(update_fields=["password"])
        # Invalidate all existing refresh tokens so other sessions are revoked
        try:
            from rest_framework_simplejwt.token_blacklist.models import OutstandingToken

            OutstandingToken.objects.filter(user=user).delete()
        except ImportError:
            pass
        except DatabaseError:
            logger.error("Failed to invalidate tokens for user %s on password change", user.id)


class EmailVerificationSerializer(serializers.Serializer):
    key = serializers.CharField()

    def validate_key(self, value):
        try:
            email_address_id = verify_email_verification_key(value)
        except (signing.BadSignature, signing.SignatureExpired):
            raise serializers.ValidationError("Invalid or expired verification link.")

        try:
            self._email_address = EmailAddress.objects.select_related("user").get(
                pk=email_address_id,
            )
        except EmailAddress.DoesNotExist:
            raise serializers.ValidationError("Invalid verification link.")

        return value

    def save(self):
        self._email_address.verify()
        self._email_address.set_as_primary()


class ResendVerificationSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def save(self):
        email = User.objects.normalize_email(self.validated_data["email"])
        try:
            email_addr = EmailAddress.objects.select_related("user").get(
                email__iexact=email,
                verified=False,
            )
        except EmailAddress.DoesNotExist:
            # Silently return
            return

        from core.auth.tasks import send_verification_email

        send_verification_email.delay(str(email_addr.user_id), email_addr.id)
