"""
Serializers for the Social system.

These serializers handle friendships, follows, activity feeds, and
user search results. They provide data optimized for the mobile app's
social features.
"""

from rest_framework import serializers

from apps.users.models import User
from .models import Friendship, UserFollow, ActivityFeedItem


class UserPublicSerializer(serializers.ModelSerializer):
    """
    Public user profile serializer for social contexts.

    Exposes display name, avatar, level, and gamification stats
    but never private data like dreams or email.
    """

    username = serializers.CharField(source='display_name', read_only=True)
    avatar = serializers.URLField(source='avatar_url', read_only=True)
    currentLevel = serializers.IntegerField(source='level', read_only=True)
    influenceScore = serializers.IntegerField(source='xp', read_only=True)
    currentStreak = serializers.IntegerField(source='streak_days', read_only=True)
    title = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id',
            'username',
            'avatar',
            'currentLevel',
            'influenceScore',
            'currentStreak',
            'title',
        ]
        read_only_fields = fields

    def get_title(self, obj):
        """Generate a title based on the user's level."""
        level = obj.level
        if level >= 50:
            return 'Legend'
        elif level >= 30:
            return 'Master'
        elif level >= 20:
            return 'Expert'
        elif level >= 10:
            return 'Achiever'
        elif level >= 5:
            return 'Explorer'
        return 'Dreamer'


class FriendSerializer(serializers.Serializer):
    """
    Serializer for displaying a friend in the friends list.

    Combines user public data with friendship metadata.
    """

    id = serializers.UUIDField(help_text='User ID of the friend.')
    username = serializers.CharField(help_text='Display name of the friend.')
    avatar = serializers.URLField(
        allow_blank=True,
        help_text='Avatar URL of the friend.'
    )
    title = serializers.CharField(help_text='Title based on level.')
    currentLevel = serializers.IntegerField(help_text='Current level.')
    influenceScore = serializers.IntegerField(help_text='Influence score (XP).')
    currentStreak = serializers.IntegerField(help_text='Current streak days.')


class FriendRequestSerializer(serializers.ModelSerializer):
    """
    Serializer for pending friend requests.

    Shows the sender's public info for incoming requests.
    """

    sender = serializers.SerializerMethodField()

    class Meta:
        model = Friendship
        fields = [
            'id',
            'sender',
            'status',
            'created_at',
        ]
        read_only_fields = fields

    def get_sender(self, obj):
        """Return the sender's public profile info."""
        user = obj.user1
        return {
            'id': str(user.id),
            'username': user.display_name or 'Anonymous',
            'avatar': user.avatar_url or '',
            'currentLevel': user.level,
            'influenceScore': user.xp,
        }


class UserSearchResultSerializer(serializers.Serializer):
    """
    Serializer for user search results.

    Includes public profile info plus friendship/follow status
    relative to the requesting user.
    """

    id = serializers.UUIDField(help_text='User ID.')
    username = serializers.CharField(help_text='Display name.')
    avatar = serializers.URLField(allow_blank=True, help_text='Avatar URL.')
    title = serializers.CharField(help_text='Title based on level.')
    influenceScore = serializers.IntegerField(help_text='Influence score (XP).')
    currentLevel = serializers.IntegerField(help_text='Current level.')
    isFriend = serializers.BooleanField(help_text='Whether they are already a friend.')
    isFollowing = serializers.BooleanField(help_text='Whether the current user follows them.')


class ActivityFeedItemSerializer(serializers.ModelSerializer):
    """
    Serializer for activity feed items.

    Provides activity data with the actor's public info for the social feed.
    Uses camelCase field names to match mobile app expectations.
    """

    user = serializers.SerializerMethodField()
    type = serializers.CharField(source='activity_type')
    createdAt = serializers.DateTimeField(source='created_at', read_only=True)

    class Meta:
        model = ActivityFeedItem
        fields = [
            'id',
            'user',
            'type',
            'content',
            'createdAt',
        ]
        read_only_fields = fields

    def get_user(self, obj):
        """Return the actor's public profile info."""
        return {
            'id': str(obj.user.id),
            'username': obj.user.display_name or 'Anonymous',
            'avatar': obj.user.avatar_url or '',
        }


class SendFriendRequestSerializer(serializers.Serializer):
    """Serializer for sending a friend request."""

    targetUserId = serializers.UUIDField(
        help_text='The UUID of the user to send a friend request to.'
    )


class FollowUserSerializer(serializers.Serializer):
    """Serializer for following a user."""

    targetUserId = serializers.UUIDField(
        help_text='The UUID of the user to follow.'
    )


class BlockUserSerializer(serializers.Serializer):
    """Serializer for blocking a user."""

    targetUserId = serializers.UUIDField(
        help_text='The UUID of the user to block.'
    )
    reason = serializers.CharField(
        required=False,
        default='',
        help_text='Optional reason for blocking.'
    )


class ReportUserSerializer(serializers.Serializer):
    """Serializer for reporting a user."""

    targetUserId = serializers.UUIDField(
        help_text='The UUID of the user to report.'
    )
    reason = serializers.CharField(
        help_text='Description of why the user is being reported.'
    )
    category = serializers.ChoiceField(
        choices=['spam', 'harassment', 'inappropriate', 'other'],
        default='other',
        help_text='Category of the report.'
    )


class BlockedUserSerializer(serializers.Serializer):
    """Serializer for blocked user list items."""

    id = serializers.UUIDField(help_text='Block record ID.')
    user = serializers.SerializerMethodField()
    reason = serializers.CharField(help_text='Reason for blocking.')
    created_at = serializers.DateTimeField(help_text='When the block was created.')

    def get_user(self, obj):
        blocked = obj.blocked
        return {
            'id': str(blocked.id),
            'username': blocked.display_name or 'Anonymous',
            'avatar': blocked.avatar_url or '',
        }
