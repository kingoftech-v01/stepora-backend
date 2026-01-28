"""
Firebase authentication backend for Django and DRF.
"""

from django.contrib.auth.backends import BaseBackend
from rest_framework import authentication, exceptions
from firebase_admin import auth as firebase_auth
from apps.users.models import User


class FirebaseAuthenticationBackend(BaseBackend):
    """Django authentication backend using Firebase tokens."""

    def authenticate(self, request, firebase_token=None, **kwargs):
        """Authenticate user with Firebase token."""
        if not firebase_token:
            return None

        try:
            # Verify Firebase ID token
            decoded_token = firebase_auth.verify_id_token(firebase_token)
            firebase_uid = decoded_token['uid']
            email = decoded_token.get('email')

            if not email:
                return None

            # Get or create user
            user, created = User.objects.get_or_create(
                firebase_uid=firebase_uid,
                defaults={
                    'email': email,
                    'display_name': decoded_token.get('name', ''),
                }
            )

            return user

        except firebase_auth.InvalidIdTokenError:
            return None
        except firebase_auth.ExpiredIdTokenError:
            return None
        except Exception as e:
            print(f"Firebase authentication error: {e}")
            return None

    def get_user(self, user_id):
        """Get user by ID."""
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None


class FirebaseAuthentication(authentication.BaseAuthentication):
    """DRF authentication class for Firebase tokens."""

    def authenticate(self, request):
        """Authenticate the request and return a two-tuple of (user, token)."""
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')

        if not auth_header:
            return None

        # Extract token from "Bearer <token>"
        parts = auth_header.split()
        if len(parts) != 2 or parts[0].lower() != 'bearer':
            return None

        token = parts[1]

        try:
            # Verify token with Firebase
            decoded_token = firebase_auth.verify_id_token(token)
            firebase_uid = decoded_token['uid']

            # Get user from database
            try:
                user = User.objects.get(firebase_uid=firebase_uid)
            except User.DoesNotExist:
                # Auto-create user if doesn't exist
                email = decoded_token.get('email')
                if not email:
                    raise exceptions.AuthenticationFailed('No email in token')

                user = User.objects.create(
                    firebase_uid=firebase_uid,
                    email=email,
                    display_name=decoded_token.get('name', '')
                )

            # Update last activity
            user.update_activity()

            return (user, token)

        except firebase_auth.InvalidIdTokenError:
            raise exceptions.AuthenticationFailed('Invalid Firebase token')
        except firebase_auth.ExpiredIdTokenError:
            raise exceptions.AuthenticationFailed('Firebase token expired')
        except Exception as e:
            raise exceptions.AuthenticationFailed(f'Authentication failed: {str(e)}')

    def authenticate_header(self, request):
        """Return authentication header."""
        return 'Bearer'
