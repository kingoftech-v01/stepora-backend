"""
Agora.io token generation endpoints for RTM (messaging) and RTC (voice/video).
"""

import time

from django.conf import settings
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def agora_config(request):
    """Return the Agora App ID (public, no certificate)."""
    app_id = getattr(settings, 'AGORA_APP_ID', '')
    if not app_id:
        return Response(
            {'detail': 'Agora is not configured.'},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
    return Response({'appId': app_id})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def agora_rtm_token(request):
    """Generate an Agora RTM token for the authenticated user (24h TTL)."""
    from agora_token_builder.RtmTokenBuilder import RtmTokenBuilder, Role_Rtm_User

    app_id = getattr(settings, 'AGORA_APP_ID', '')
    app_cert = getattr(settings, 'AGORA_APP_CERTIFICATE', '')
    if not app_id or not app_cert:
        return Response(
            {'detail': 'Agora is not configured.'},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    user_account = str(request.user.id)
    expiration_seconds = 86400  # 24 hours

    token = RtmTokenBuilder.buildToken(
        app_id,
        app_cert,
        user_account,
        Role_Rtm_User,
        expiration_seconds,
    )

    return Response({
        'token': token,
        'uid': user_account,
        'expiresIn': expiration_seconds,
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def agora_rtc_token(request):
    """Generate an Agora RTC token for a channel (1h TTL)."""
    from agora_token_builder.RtcTokenBuilder import RtcTokenBuilder, Role_Publisher

    app_id = getattr(settings, 'AGORA_APP_ID', '')
    app_cert = getattr(settings, 'AGORA_APP_CERTIFICATE', '')
    if not app_id or not app_cert:
        return Response(
            {'detail': 'Agora is not configured.'},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    channel_name = (request.data.get('channelName') or request.data.get('channel_name') or '').strip()
    if not channel_name:
        return Response(
            {'detail': 'channelName is required.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    uid = str(request.user.id)
    expiration_seconds = 3600  # 1 hour
    current_timestamp = int(time.time())
    privilege_expired_ts = current_timestamp + expiration_seconds

    token = RtcTokenBuilder.buildTokenWithAccount(
        app_id,
        app_cert,
        channel_name,
        uid,
        Role_Publisher,
        privilege_expired_ts,
    )

    return Response({
        'token': token,
        'uid': uid,
        'channelName': channel_name,
        'expiresIn': expiration_seconds,
    })
