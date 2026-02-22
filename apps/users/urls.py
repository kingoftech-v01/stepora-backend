"""
URLs for Users app.
"""

from django.urls import path, include
from django.http import JsonResponse
from rest_framework.routers import SimpleRouter
from .views import UserViewSet
from .models import EmailChangeRequest
from .two_factor import (
    TwoFactorSetupView, TwoFactorVerifyView, TwoFactorDisableView,
    TwoFactorStatusView, TwoFactorRegenerateBackupCodesView,
)


def verify_email_change(request, token):
    """Verify email change via token link."""
    try:
        ecr = EmailChangeRequest.objects.get(token=token, is_verified=False)
    except EmailChangeRequest.DoesNotExist:
        return JsonResponse({'error': 'Invalid or expired token.'}, status=400)

    if ecr.is_expired:
        ecr.delete()
        return JsonResponse({'error': 'Token has expired.'}, status=400)

    # Apply email change
    user = ecr.user
    user.email = ecr.new_email
    user.save(update_fields=['email'])

    ecr.is_verified = True
    ecr.save(update_fields=['is_verified'])

    return JsonResponse({'message': 'Email successfully changed.'})


router = SimpleRouter()
router.register(r'', UserViewSet, basename='user')

urlpatterns = [
    path('verify-email/<str:token>/', verify_email_change, name='verify-email-change'),
    # Two-Factor Authentication
    path('2fa/setup/', TwoFactorSetupView.as_view(), name='2fa-setup'),
    path('2fa/verify/', TwoFactorVerifyView.as_view(), name='2fa-verify'),
    path('2fa/disable/', TwoFactorDisableView.as_view(), name='2fa-disable'),
    path('2fa/status/', TwoFactorStatusView.as_view(), name='2fa-status'),
    path('2fa/backup-codes/', TwoFactorRegenerateBackupCodesView.as_view(), name='2fa-backup-codes'),
    path('', include(router.urls)),
]
