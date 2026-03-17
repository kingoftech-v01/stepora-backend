"""
Views for the Ads app.

Provides a single config endpoint that returns active ad placements
and whether the requesting user should see ads. Premium and Pro users
always receive an empty configuration.
"""

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import AdPlacement
from .serializers import AdConfigSerializer


class AdConfigView(APIView):
    """
    GET /api/v1/ads/config/

    Returns ad configuration for the authenticated user.
    Free-tier users receive active placements; premium/pro users
    get should_show_ads=False and an empty placement list.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        plan = user.get_active_plan()

        # Premium and Pro users never see ads
        should_show_ads = True
        if plan and not plan.has_ads:
            should_show_ads = False

        # Also check the user.subscription field as a fallback
        if user.subscription in ("premium", "pro"):
            should_show_ads = False

        placements = []
        if should_show_ads:
            placements = list(
                AdPlacement.objects.filter(is_active=True).order_by(
                    "-priority", "name"
                )
            )

        serializer = AdConfigSerializer(
            {
                "should_show_ads": should_show_ads,
                "placements": placements,
            }
        )
        return Response(serializer.data, status=status.HTTP_200_OK)
