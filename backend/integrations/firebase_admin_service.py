"""
Firebase Admin SDK initialization and utilities.
"""

import firebase_admin
from firebase_admin import credentials, auth as firebase_auth
from django.conf import settings
from core.exceptions import FirebaseError


def initialize_firebase():
    """Initialize Firebase Admin SDK."""
    if not firebase_admin._apps:
        try:
            cred = credentials.Certificate(settings.FIREBASE_CONFIG)
            firebase_admin.initialize_app(cred)
            print("Firebase Admin SDK initialized successfully")
        except Exception as e:
            print(f"Failed to initialize Firebase: {e}")
            raise FirebaseError(f"Firebase initialization failed: {str(e)}")


def verify_firebase_token(id_token):
    """
    Verify Firebase ID token.

    Args:
        id_token: Firebase ID token string

    Returns:
        Decoded token dictionary

    Raises:
        FirebaseError: If token is invalid
    """
    try:
        decoded_token = firebase_auth.verify_id_token(id_token)
        return decoded_token
    except firebase_auth.InvalidIdTokenError:
        raise FirebaseError("Invalid Firebase token")
    except firebase_auth.ExpiredIdTokenError:
        raise FirebaseError("Firebase token expired")
    except Exception as e:
        raise FirebaseError(f"Token verification failed: {str(e)}")


def get_user_by_email(email):
    """Get Firebase user by email."""
    try:
        user = firebase_auth.get_user_by_email(email)
        return user
    except firebase_auth.UserNotFoundError:
        return None
    except Exception as e:
        raise FirebaseError(f"Failed to get user: {str(e)}")


def create_custom_token(uid):
    """Create custom token for a user."""
    try:
        custom_token = firebase_auth.create_custom_token(uid)
        return custom_token
    except Exception as e:
        raise FirebaseError(f"Failed to create custom token: {str(e)}")


# Initialize Firebase on module import
try:
    initialize_firebase()
except Exception as e:
    print(f"Warning: Firebase initialization failed: {e}")
