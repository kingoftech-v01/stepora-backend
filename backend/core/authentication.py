"""
Token authentication backend for Django and DRF.
Uses django-allauth and DRF Token authentication.
"""

from rest_framework.authentication import TokenAuthentication


class BearerTokenAuthentication(TokenAuthentication):
    """DRF Token authentication that accepts 'Bearer' keyword in addition to 'Token'."""

    keyword = 'Token'

    def authenticate(self, request):
        """Try both 'Token' and 'Bearer' prefixes."""
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')

        if auth_header.startswith('Bearer '):
            request.META['HTTP_AUTHORIZATION'] = 'Token ' + auth_header[7:]

        return super().authenticate(request)
