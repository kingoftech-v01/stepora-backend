"""
Custom serializers for dj-rest-auth.
"""

from dj_rest_auth.registration.serializers import RegisterSerializer as DefaultRegisterSerializer
from rest_framework import serializers


class RegisterSerializer(DefaultRegisterSerializer):
    """Custom registration serializer for email-only auth (no username)."""

    username = None

    def get_cleaned_data(self):
        return {
            'email': self.validated_data.get('email', ''),
            'password1': self.validated_data.get('password1', ''),
        }
