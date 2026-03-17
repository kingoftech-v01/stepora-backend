"""Serializers for the Ads app."""

from rest_framework import serializers

from .models import AdPlacement


class AdPlacementSerializer(serializers.ModelSerializer):
    """Serializes an AdPlacement for the config endpoint."""

    class Meta:
        model = AdPlacement
        fields = [
            "id",
            "name",
            "display_name",
            "ad_type",
            "is_active",
            "frequency",
            "priority",
        ]
        read_only_fields = fields


class AdConfigSerializer(serializers.Serializer):
    """
    Top-level response for the ad config endpoint.

    Returns the user's ad eligibility flag and active placements.
    Premium/Pro users receive should_show_ads=False with an empty list.
    """

    should_show_ads = serializers.BooleanField()
    placements = AdPlacementSerializer(many=True)
