"""
Serializers for the Friends system.
"""

from rest_framework import serializers

from .models import BlockedUser, Friendship, ReportedUser, UserFollow


class FriendshipSerializer(serializers.ModelSerializer):
    """Serializer for Friendship model."""

    class Meta:
        model = Friendship
        fields = [
            "id",
            "user1",
            "user2",
            "status",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class SendFriendRequestSerializer(serializers.Serializer):
    """Serializer for sending a friend request."""

    user_id = serializers.UUIDField(help_text="ID of the user to send a request to.")


class UserFollowSerializer(serializers.ModelSerializer):
    """Serializer for UserFollow model."""

    class Meta:
        model = UserFollow
        fields = [
            "id",
            "follower",
            "following",
            "created_at",
        ]
        read_only_fields = fields


class FollowUserSerializer(serializers.Serializer):
    """Serializer for following a user."""

    user_id = serializers.UUIDField(help_text="ID of the user to follow.")


class BlockedUserSerializer(serializers.ModelSerializer):
    """Serializer for BlockedUser model."""

    class Meta:
        model = BlockedUser
        fields = [
            "id",
            "blocker",
            "blocked",
            "reason",
            "created_at",
        ]
        read_only_fields = ["id", "blocker", "created_at"]


class BlockUserSerializer(serializers.Serializer):
    """Serializer for blocking a user."""

    user_id = serializers.UUIDField(help_text="ID of the user to block.")
    reason = serializers.CharField(required=False, default="", allow_blank=True)


class ReportUserSerializer(serializers.Serializer):
    """Serializer for reporting a user."""

    user_id = serializers.UUIDField(help_text="ID of the user to report.")
    reason = serializers.CharField(help_text="Reason for the report.")
    category = serializers.ChoiceField(
        choices=["spam", "harassment", "inappropriate", "other"],
        default="other",
    )


class ReportedUserSerializer(serializers.ModelSerializer):
    """Serializer for ReportedUser model."""

    class Meta:
        model = ReportedUser
        fields = [
            "id",
            "reporter",
            "reported",
            "reason",
            "category",
            "status",
            "created_at",
        ]
        read_only_fields = fields
