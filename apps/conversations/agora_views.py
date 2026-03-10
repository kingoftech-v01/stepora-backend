"""
Agora.io token generation endpoints for RTM (messaging) and RTC (voice/video).
"""

import time

from django.conf import settings
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def agora_config(request):
    """Return the Agora App ID (public, no certificate)."""
    app_id = getattr(settings, "AGORA_APP_ID", "")
    if not app_id:
        return Response(
            {"detail": "Agora is not configured."},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
    return Response({"appId": app_id})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def agora_rtm_token(request):
    """Generate an Agora RTM token for the authenticated user (24h TTL)."""
    from agora_token_builder.RtmTokenBuilder import Role_Rtm_User, RtmTokenBuilder

    app_id = getattr(settings, "AGORA_APP_ID", "")
    app_cert = getattr(settings, "AGORA_APP_CERTIFICATE", "")
    if not app_id or not app_cert:
        return Response(
            {"detail": "Agora is not configured."},
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

    return Response(
        {
            "token": token,
            "uid": user_account,
            "expiresIn": expiration_seconds,
        }
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def agora_rtc_token(request):
    """Generate an Agora RTC token for a channel (1h TTL)."""
    from agora_token_builder.RtcTokenBuilder import Role_Publisher, RtcTokenBuilder

    app_id = getattr(settings, "AGORA_APP_ID", "")
    app_cert = getattr(settings, "AGORA_APP_CERTIFICATE", "")
    if not app_id or not app_cert:
        return Response(
            {"detail": "Agora is not configured."},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    import re

    channel_name = (
        request.data.get("channelName") or request.data.get("channel_name") or ""
    ).strip()
    if not channel_name:
        return Response(
            {"detail": "channelName is required."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    # Validate channel name: alphanumeric, hyphens, underscores only, max 64 chars
    if len(channel_name) > 64 or not re.match(r"^[a-zA-Z0-9_-]+$", channel_name):
        return Response(
            {
                "detail": "Invalid channelName. Use alphanumeric, hyphens, underscores only (max 64 chars)."
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Verify the user is an authorized participant for this channel
    from django.db.models import Q

    from apps.conversations.models import Call

    authorized = False

    # Check 1:1 calls — channel name is the call UUID
    if Call.objects.filter(
        Q(id=channel_name),
        Q(caller=request.user) | Q(callee=request.user),
        status__in=["ringing", "accepted", "in_progress"],
    ).exists():
        authorized = True

    if not authorized:
        # Check circle calls
        from apps.circles.models import CircleCall, CircleMembership

        circle_call = (
            CircleCall.objects.filter(
                Q(id=channel_name) | Q(agora_channel=channel_name),
                status="active",
            )
            .select_related("circle")
            .first()
        )
        if (
            circle_call
            and CircleMembership.objects.filter(
                circle=circle_call.circle,
                user=request.user,
            ).exists()
        ):
            authorized = True

    if not authorized:
        return Response(
            {"detail": "Not authorized for this channel."},
            status=status.HTTP_403_FORBIDDEN,
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

    return Response(
        {
            "token": token,
            "uid": uid,
            "channelName": channel_name,
            "expiresIn": expiration_seconds,
        }
    )
