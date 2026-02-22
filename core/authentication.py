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


class CsrfExemptAPIMiddleware:
    """Skip CSRF checks for /api/ routes. Admin still uses CSRF."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path.startswith('/api/'):
            setattr(request, '_dont_enforce_csrf_checks', True)
        return self.get_response(request)
