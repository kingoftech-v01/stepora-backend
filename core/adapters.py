"""
Custom allauth adapter for DreamPlanner.

Overrides email confirmation and password reset URLs to point to the
frontend app instead of the default backend URLs.
"""

from allauth.account.adapter import DefaultAccountAdapter
from django.conf import settings


class DreamPlannerAccountAdapter(DefaultAccountAdapter):

    def get_email_confirmation_url(self, request, emailconfirmation):
        """
        Return a frontend URL for email confirmation instead of the
        default backend URL.
        """
        return f"{settings.FRONTEND_URL}/verify-email/{emailconfirmation.key}"

    def get_reset_password_from_key_url(self, key):
        """
        Return a frontend URL for password reset instead of the
        default backend URL.
        """
        return f"{settings.FRONTEND_URL}/reset-password/{key}"
