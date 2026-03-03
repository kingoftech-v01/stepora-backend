"""
Social authentication views for Google and Apple Sign-In.
Uses dj-rest-auth social login views with allauth adapters.

Includes AppleRedirectView for native OAuth form_post callback:
Apple sends code + id_token via form_post to /api/auth/apple/redirect/.
The view authenticates the user and redirects back to the native app
via a deep link with the JWT token.
"""

import html
import json as json_mod
import logging

from django.conf import settings
from django.http import HttpResponse
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView
from dj_rest_auth.registration.views import SocialLoginView
from allauth.socialaccount.providers.google.views import GoogleOAuth2Adapter
from allauth.socialaccount.providers.apple.views import AppleOAuth2Adapter
from allauth.socialaccount.providers.oauth2.client import OAuth2Client
from drf_spectacular.utils import extend_schema

logger = logging.getLogger(__name__)


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


class AppleRedirectView(APIView):
    """
    Handle Apple OAuth2 form_post callback for native apps.

    Apple sends POST with: code, id_token, state (native redirect URI).
    This view authenticates via AppleLoginView, then redirects the native
    app back with a deep link containing the auth token.
    """

    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(
        summary='Apple OAuth redirect callback',
        description=(
            'Receives Apple OAuth form_post with code and id_token. '
            'Authenticates the user and redirects back to the native app.'
        ),
        tags=['Auth'],
    )
    def post(self, request):
        code = request.POST.get('code', '')
        id_token = request.POST.get('id_token', '')
        raw_state = request.POST.get('state', '')  # Native deep link URI

        # Validate state against allowed deep link schemes to prevent open redirect
        ALLOWED_DEEP_LINK_PREFIXES = ('com.dreamplanner.app://',)
        state = ''
        if raw_state and any(raw_state.startswith(p) for p in ALLOWED_DEEP_LINK_PREFIXES):
            state = raw_state

        if not code and not id_token:
            return HttpResponse('Missing authorization code or id_token.', status=400)

        # Authenticate via Apple — use the id_token with the Apple adapter
        from rest_framework.test import APIRequestFactory
        factory = APIRequestFactory()
        internal_request = factory.post(
            '/api/auth/apple/',
            data={'code': code, 'id_token': id_token},
            format='json',
        )
        internal_request.META.update(request.META)

        apple_view = AppleLoginView.as_view()
        response = apple_view(internal_request)
        response.render()

        if response.status_code == 200:
            import json
            data = json.loads(response.content)
            access_token = data.get('access', data.get('key', ''))

            # Build the deep link back to native app
            if state and access_token:
                deep_link = state + '?token=' + access_token
            elif access_token:
                deep_link = 'com.dreamplanner.app://auth/callback?token=' + access_token
            else:
                deep_link = 'com.dreamplanner.app://auth/callback?error=no_token'
        else:
            deep_link = state + '?error=auth_failed' if state else 'com.dreamplanner.app://auth/callback?error=auth_failed'

        # Redirect via an HTML page (form_post response must be HTML)
        deep_link_js = json_mod.dumps(deep_link)
        deep_link_html = html.escape(deep_link)
        page = (
            '<!DOCTYPE html><html><head><meta charset="utf-8">'
            '<title>Redirecting...</title></head><body>'
            '<p>Redirecting to DreamPlanner...</p>'
            '<p><a href="' + deep_link_html + '">Click here if not redirected.</a></p>'
            '<script>window.location.href = ' + deep_link_js + ';</script>'
            '</body></html>'
        )
        return HttpResponse(page, content_type='text/html')
