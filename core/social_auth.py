"""
Social authentication views for Google and Apple Sign-In.
Uses dj-rest-auth social login views with allauth adapters.
"""

from dj_rest_auth.registration.views import SocialLoginView
from allauth.socialaccount.providers.google.views import GoogleOAuth2Adapter
from allauth.socialaccount.providers.apple.views import AppleOAuth2Adapter
from allauth.socialaccount.providers.oauth2.client import OAuth2Client
from drf_spectacular.utils import extend_schema


class GoogleLoginView(SocialLoginView):
    adapter_class = GoogleOAuth2Adapter
    client_class = OAuth2Client

    @extend_schema(
        summary='Google Sign-In',
        description='Authenticate using a Google OAuth2 access token. Returns an auth token.',
        tags=['Auth'],
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)


class AppleLoginView(SocialLoginView):
    adapter_class = AppleOAuth2Adapter
    client_class = OAuth2Client

    @extend_schema(
        summary='Apple Sign-In',
        description='Authenticate using an Apple OAuth2 authorization code. Returns an auth token.',
        tags=['Auth'],
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)
