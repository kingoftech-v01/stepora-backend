"""
Custom serializers for dj-rest-auth.
"""

from dj_rest_auth.registration.serializers import RegisterSerializer as DefaultRegisterSerializer
from rest_framework import serializers
from apps.users.models import User


class RegisterSerializer(DefaultRegisterSerializer):
    """Custom registration serializer for email-only auth (no username)."""

    username = None
    display_name = serializers.CharField(max_length=255, required=False, default='')

    def validate_email(self, email):
        email = super().validate_email(email)
        if User.objects.filter(email__iexact=email).exists():
            raise serializers.ValidationError(
                'An account with this email already exists.'
            )
        return email

    def get_cleaned_data(self):
        return {
            'email': self.validated_data.get('email', ''),
            'password1': self.validated_data.get('password1', ''),
        }

    def save(self, request):
        user = super().save(request)
        display_name = self.validated_data.get('display_name', '')
        if display_name:
            user.display_name = display_name
            user.save(update_fields=['display_name'])
        return user
