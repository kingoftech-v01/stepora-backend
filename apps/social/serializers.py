"""
Serializers for the Social system.

These serializers handle friendships, follows, activity feeds, and
user search results. They provide data optimized for the mobile app's
social features.
"""

from rest_framework import serializers
from drf_spectacular.utils import extend_schema_serializer

from core.sanitizers import sanitize_text
from apps.users.models import User
from .models import (
    Friendship, UserFollow, ActivityFeedItem,
    DreamPost, DreamPostLike, DreamPostComment, DreamEncouragement,
)


class UserPublicSerializer(serializers.ModelSerializer):
    """
    Public user profile serializer for social contexts.

    Exposes display name, avatar, level, and gamification stats
    but never private data like dreams or email.
    """

    username = serializers.CharField(source='display_name', read_only=True, help_text='Public display name.')
    avatar = serializers.URLField(source='avatar_url', read_only=True, help_text='Avatar image URL.')
    currentLevel = serializers.IntegerField(source='level', read_only=True, help_text='Current user level.')
    influenceScore = serializers.IntegerField(source='xp', read_only=True, help_text='Total XP earned.')
    currentStreak = serializers.IntegerField(source='streak_days', read_only=True, help_text='Current streak in days.')
    title = serializers.SerializerMethodField(help_text='Title based on level (e.g., Dreamer, Explorer).')

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
        extra_kwargs = {
            'id': {'help_text': 'Unique user identifier.'},
        }

    def get_title(self, obj) -> str:
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


@extend_schema_serializer(component_name='PendingFriendRequest')
class FriendRequestSerializer(serializers.ModelSerializer):
    """
    Serializer for pending friend requests.

    Shows the sender's public info for incoming requests.
    """

    sender = serializers.SerializerMethodField(help_text='Sender public profile info.')

    class Meta:
        model = Friendship
        fields = [
            'id',
            'sender',
            'status',
            'created_at',
        ]
        read_only_fields = fields
        extra_kwargs = {
            'id': {'help_text': 'Friend request identifier.'},
            'status': {'help_text': 'Request status (pending, accepted, rejected).'},
            'created_at': {'help_text': 'When the request was sent.'},
        }

    def get_sender(self, obj) -> dict:
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

    user = serializers.SerializerMethodField(help_text='Actor public profile info.')
    type = serializers.CharField(source='activity_type', help_text='Activity type (e.g., dream_completed, task_done).')
    createdAt = serializers.DateTimeField(source='created_at', read_only=True, help_text='When the activity occurred.')

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
        extra_kwargs = {
            'id': {'help_text': 'Activity feed item identifier.'},
            'content': {'help_text': 'Activity description text.'},
        }

    def get_user(self, obj) -> dict:
        """Return the actor's public profile info."""
        return {
            'id': str(obj.user.id),
            'username': obj.user.display_name or 'Anonymous',
            'avatar': obj.user.avatar_url or '',
        }


class SendFriendRequestSerializer(serializers.Serializer):
    """Serializer for sending a friend request."""

    target_user_id = serializers.UUIDField(
        help_text='The UUID of the user to send a friend request to.'
    )


class FollowUserSerializer(serializers.Serializer):
    """Serializer for following a user."""

    target_user_id = serializers.UUIDField(
        help_text='The UUID of the user to follow.'
    )


class BlockUserSerializer(serializers.Serializer):
    """Serializer for blocking a user."""

    target_user_id = serializers.UUIDField(
        help_text='The UUID of the user to block.'
    )
    reason = serializers.CharField(
        required=False,
        default='',
        help_text='Optional reason for blocking.'
    )

    def validate_reason(self, value):
        return sanitize_text(value)


class ReportUserSerializer(serializers.Serializer):
    """Serializer for reporting a user."""

    target_user_id = serializers.UUIDField(
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

    def validate_reason(self, value):
        return sanitize_text(value)


class BlockedUserSerializer(serializers.Serializer):
    """Serializer for blocked user list items."""

    id = serializers.UUIDField(help_text='Block record ID.')
    user = serializers.SerializerMethodField(help_text='Blocked user public profile.')
    reason = serializers.CharField(help_text='Reason for blocking.')
    created_at = serializers.DateTimeField(help_text='When the block was created.')

    def get_user(self, obj) -> dict:
        blocked = obj.blocked
        return {
            'id': str(blocked.id),
            'username': blocked.display_name or 'Anonymous',
            'avatar': blocked.avatar_url or '',
        }


# ── Dream Post serializers ────────────────────────────────────────────


class DreamPostSerializer(serializers.ModelSerializer):
    """Full dream post representation for the feed."""

    user = serializers.SerializerMethodField()
    createdAt = serializers.DateTimeField(source='created_at', read_only=True)
    updatedAt = serializers.DateTimeField(source='updated_at', read_only=True)
    likesCount = serializers.IntegerField(source='likes_count', read_only=True)
    commentsCount = serializers.IntegerField(source='comments_count', read_only=True)
    sharesCount = serializers.IntegerField(source='shares_count', read_only=True)
    hasLiked = serializers.SerializerMethodField()
    hasEncouraged = serializers.SerializerMethodField()
    encouragementSummary = serializers.SerializerMethodField()
    gofundmeUrl = serializers.URLField(source='gofundme_url', read_only=True)
    imageUrl = serializers.SerializerMethodField()
    dreamTitle = serializers.SerializerMethodField()

    class Meta:
        model = DreamPost
        fields = [
            'id', 'user', 'dream', 'dreamTitle',
            'content', 'imageUrl', 'gofundmeUrl',
            'visibility', 'likesCount', 'commentsCount', 'sharesCount',
            'is_pinned', 'hasLiked', 'hasEncouraged', 'encouragementSummary',
            'createdAt', 'updatedAt',
        ]
        read_only_fields = fields

    def get_user(self, obj) -> dict:
        return {
            'id': str(obj.user.id),
            'username': obj.user.display_name or 'Anonymous',
            'avatar': obj.user.avatar_url or '',
            'level': obj.user.level,
        }

    def get_hasLiked(self, obj) -> bool:
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return False
        if hasattr(obj, '_user_has_liked'):
            return obj._user_has_liked
        return obj.likes.filter(user=request.user).exists()

    def get_hasEncouraged(self, obj) -> bool:
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return False
        if hasattr(obj, '_user_has_encouraged'):
            return obj._user_has_encouraged
        return obj.encouragements.filter(user=request.user).exists()

    def get_encouragementSummary(self, obj) -> dict:
        from django.db.models import Count
        counts = obj.encouragements.values('encouragement_type').annotate(
            count=Count('id')
        )
        return {item['encouragement_type']: item['count'] for item in counts}

    def get_imageUrl(self, obj) -> str:
        if obj.image_url:
            return obj.image_url
        if obj.image_file:
            return obj.image_file.url
        return ''

    def get_dreamTitle(self, obj) -> str:
        if obj.dream:
            return obj.dream.title
        return ''


class DreamPostCreateSerializer(serializers.Serializer):
    """Serializer for creating a dream post."""

    content = serializers.CharField(max_length=5000)
    dream_id = serializers.UUIDField(required=False, allow_null=True)
    gofundme_url = serializers.URLField(required=False, default='')
    visibility = serializers.ChoiceField(
        choices=['public', 'followers', 'private'],
        default='public',
    )
    image_url = serializers.URLField(required=False, default='')

    def validate_content(self, value):
        return sanitize_text(value)

    def validate_gofundme_url(self, value):
        if value:
            from core.sanitizers import sanitize_url
            return sanitize_url(value)
        return value


class DreamPostCommentSerializer(serializers.ModelSerializer):
    """Comment on a dream post."""

    user = serializers.SerializerMethodField()
    createdAt = serializers.DateTimeField(source='created_at', read_only=True)
    replies = serializers.SerializerMethodField()

    class Meta:
        model = DreamPostComment
        fields = ['id', 'user', 'content', 'parent', 'replies', 'createdAt']
        read_only_fields = ['id', 'user', 'replies', 'createdAt']

    def get_user(self, obj) -> dict:
        return {
            'id': str(obj.user.id),
            'username': obj.user.display_name or 'Anonymous',
            'avatar': obj.user.avatar_url or '',
        }

    def get_replies(self, obj) -> list:
        if obj.replies.exists():
            return DreamPostCommentSerializer(
                obj.replies.select_related('user').order_by('created_at')[:10],
                many=True,
                context=self.context,
            ).data
        return []


class DreamEncouragementSerializer(serializers.ModelSerializer):
    """Encouragement on a dream post."""

    user = serializers.SerializerMethodField()
    encouragementType = serializers.CharField(source='encouragement_type', read_only=True)
    createdAt = serializers.DateTimeField(source='created_at', read_only=True)

    class Meta:
        model = DreamEncouragement
        fields = ['id', 'user', 'encouragementType', 'message', 'createdAt']
        read_only_fields = fields

    def get_user(self, obj) -> dict:
        return {
            'id': str(obj.user.id),
            'username': obj.user.display_name or 'Anonymous',
            'avatar': obj.user.avatar_url or '',
        }
