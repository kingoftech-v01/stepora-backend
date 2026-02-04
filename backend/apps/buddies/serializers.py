"""
Serializers for the Buddies system.

These serializers handle buddy pairing data, progress comparisons,
and match results for the DreamBuddyScreen in the mobile app.
"""

from rest_framework import serializers

from .models import BuddyPairing, BuddyEncouragement


class BuddyPartnerSerializer(serializers.Serializer):
    """
    Serializer for a buddy partner's public profile.

    Shows the partner's display info, level, streak, and influence
    for the buddy detail view.
    """

    id = serializers.UUIDField(help_text='Partner user ID.')
    username = serializers.CharField(help_text='Partner display name.')
    avatar = serializers.URLField(allow_blank=True, help_text='Partner avatar URL.')
    title = serializers.CharField(help_text='Partner title based on level.')
    currentLevel = serializers.IntegerField(help_text='Partner current level.')
    influenceScore = serializers.IntegerField(help_text='Partner influence (XP).')
    currentStreak = serializers.IntegerField(help_text='Partner streak days.')


class BuddyPairingSerializer(serializers.Serializer):
    """
    Serializer for the current buddy pairing detail.

    Returns the pairing info along with the partner's public profile
    and recent activity stats.
    """

    id = serializers.UUIDField(help_text='Pairing ID.')
    partner = BuddyPartnerSerializer(help_text='Partner profile info.')
    compatibilityScore = serializers.FloatField(help_text='Compatibility score 0-1.')
    status = serializers.CharField(help_text='Pairing status.')
    recentActivity = serializers.IntegerField(help_text='Partner tasks this week.')
    createdAt = serializers.DateTimeField(help_text='When the pairing was created.')


class BuddyProgressSerializer(serializers.Serializer):
    """
    Serializer for buddy progress comparison.

    Shows side-by-side stats for both buddies including streak,
    tasks completed this week, and influence score.
    """

    user = serializers.DictField(help_text='Current user progress stats.')
    partner = serializers.DictField(help_text='Partner progress stats.')


class BuddyMatchSerializer(serializers.Serializer):
    """
    Serializer for a potential buddy match result.

    Returned from the find-match endpoint with the matched user's
    info and compatibility score.
    """

    userId = serializers.UUIDField(help_text='Matched user ID.')
    username = serializers.CharField(help_text='Matched user display name.')
    avatar = serializers.URLField(allow_blank=True, help_text='Matched user avatar.')
    compatibilityScore = serializers.FloatField(help_text='Compatibility score 0-1.')
    sharedInterests = serializers.ListField(
        child=serializers.CharField(),
        help_text='List of shared interest categories.'
    )


class BuddyPairRequestSerializer(serializers.Serializer):
    """Serializer for pairing with a specific user."""

    partnerId = serializers.UUIDField(
        help_text='The UUID of the user to pair with.'
    )


class BuddyEncourageSerializer(serializers.Serializer):
    """Serializer for sending encouragement to a buddy."""

    message = serializers.CharField(
        required=False,
        default='',
        max_length=1000,
        help_text='Optional motivational message.'
    )
