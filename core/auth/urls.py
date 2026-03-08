"""
URL patterns for the custom authentication system.
Replaces dj-rest-auth and allauth URL includes.
"""

from django.urls import path

from core.auth.views import (
    LoginView,
    TwoFactorChallengeView,
    RegisterView,
    LogoutView,
    PasswordResetView,
    PasswordResetValidateView,
    PasswordResetConfirmView,
    PasswordChangeView,
    VerifyEmailView,
    ResendVerificationView,
    TokenRefreshView,
    UserDetailsView,
    GoogleLoginView,
    AppleLoginView,
    AppleRedirectView,
)

urlpatterns = [
    # Core auth
    path('login/', LoginView.as_view(), name='rest_login'),
    path('logout/', LogoutView.as_view(), name='rest_logout'),
    path('2fa-challenge/', TwoFactorChallengeView.as_view(), name='2fa_challenge'),

    # Registration
    path('registration/', RegisterView.as_view(), name='rest_register'),

    # Password management
    path('password/reset/', PasswordResetView.as_view(), name='rest_password_reset'),
    path('password/reset/validate/', PasswordResetValidateView.as_view(), name='rest_password_reset_validate'),
    path('password/reset/confirm/', PasswordResetConfirmView.as_view(), name='rest_password_reset_confirm'),
    path('password/change/', PasswordChangeView.as_view(), name='rest_password_change'),

    # Email verification
    path('verify-email/', VerifyEmailView.as_view(), name='rest_verify_email'),
    path('resend-verification/', ResendVerificationView.as_view(), name='rest_resend_verification'),

    # Token refresh
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),

    # User details
    path('user/', UserDetailsView.as_view(), name='rest_user_details'),

    # Social login
    path('google/', GoogleLoginView.as_view(), name='google_login'),
    path('apple/', AppleLoginView.as_view(), name='apple_login'),
    path('apple/redirect/', AppleRedirectView.as_view(), name='apple_redirect'),
]
