"""
Custom authentication backend that authenticates by email.
Replaces allauth.account.auth_backends.AuthenticationBackend.
"""

from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend

User = get_user_model()


class EmailAuthBackend(ModelBackend):
    """Authenticate users by email + password (case-insensitive)."""

    def authenticate(self, request, email=None, password=None, username=None, **kwargs):
        # Accept 'username' kwarg for compatibility with Django internals
        email = email or username
        if not email or not password:
            return None

        email = User.objects.normalize_email(email)
        try:
            user = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            # Run the default password hasher to avoid timing attacks
            User().set_password(password)
            return None

        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
