"""
Social authentication views for Google and Apple Sign-In.
Uses dj-rest-auth social login views with allauth adapters.
"""

from dj_rest_auth.registration.views import SocialLoginView
from allauth.socialaccount.providers.google.views import GoogleOAuth2Adapter
from allauth.socialaccount.providers.apple.views import AppleOAuth2Adapter
from allauth.socialaccount.providers.oauth2.client import OAuth2Client


class GoogleLoginView(SocialLoginView):
    adapter_class = GoogleOAuth2Adapter
    client_class = OAuth2Client


class AppleLoginView(SocialLoginView):
    adapter_class = AppleOAuth2Adapter
    client_class = OAuth2Client
