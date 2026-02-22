"""
Serializers for the Circles system.

These serializers handle Dream Circle data including circle details,
memberships, posts, and challenges. They provide both list and detail
representations optimized for the mobile app's needs.
"""

from rest_framework import serializers

from .models import (
    Circle, CircleMembership, CirclePost, CircleChallenge,
    PostReaction, CircleInvitation, ChallengeProgress,
)


class CircleMemberSerializer(serializers.ModelSerializer):
    """
    Serializer for circle member display in member lists.

    Provides public user info: username, avatar, and role within the circle.
    """

    username = serializers.CharField(source='user.display_name', read_only=True)
    avatar = serializers.URLField(source='user.avatar_url', read_only=True)

    class Meta:
        model = CircleMembership
        fields = [
            'id',
            'user',
            'username',
            'avatar',
            'role',
            'joined_at',
        ]
        read_only_fields = fields


class CircleChallengeSerializer(serializers.ModelSerializer):
    """
    Serializer for circle challenges.

    Includes challenge details, dates, status, and participant count.
    Uses camelCase field names to match mobile app expectations.
    """

    participantCount = serializers.IntegerField(
        source='participant_count',
        read_only=True
    )
    startDate = serializers.DateTimeField(source='start_date', read_only=True)
    endDate = serializers.DateTimeField(source='end_date', read_only=True)

    class Meta:
        model = CircleChallenge
        fields = [
            'id',
            'title',
            'description',
            'startDate',
            'endDate',
            'status',
            'participantCount',
            'created_at',
        ]
        read_only_fields = fields


class CircleListSerializer(serializers.ModelSerializer):
    """
    Serializer for circle list display.

    Provides a lightweight representation of circles for the list view,
    including member count, member avatars, and basic info.
    """

    memberCount = serializers.IntegerField(source='member_count', read_only=True)
    maxMembers = serializers.IntegerField(source='max_members', read_only=True)
    memberAvatars = serializers.SerializerMethodField()
    creatorName = serializers.CharField(source='creator.display_name', read_only=True)
    isMember = serializers.SerializerMethodField()

    class Meta:
        model = Circle
        fields = [
            'id',
            'name',
            'description',
            'category',
            'is_public',
            'memberCount',
            'maxMembers',
            'memberAvatars',
            'creatorName',
            'isMember',
            'created_at',
        ]
        read_only_fields = fields

    def get_memberAvatars(self, obj):
        """Return avatar URLs of the first 5 members for preview display."""
        memberships = obj.memberships.select_related('user').order_by('joined_at')[:5]
        return [m.user.avatar_url for m in memberships if m.user.avatar_url]

    def get_isMember(self, obj):
        """Check if the requesting user is a member of this circle."""
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return False
        return obj.memberships.filter(user=request.user).exists()


class CircleDetailSerializer(serializers.ModelSerializer):
    """
    Serializer for circle detail display.

    Provides full circle information including member list, challenges,
    and whether the current user is a member.
    """

    memberCount = serializers.IntegerField(source='member_count', read_only=True)
    maxMembers = serializers.IntegerField(source='max_members', read_only=True)
    members = serializers.SerializerMethodField()
    challenges = serializers.SerializerMethodField()
    creatorName = serializers.CharField(source='creator.display_name', read_only=True)
    isMember = serializers.SerializerMethodField()

    class Meta:
        model = Circle
        fields = [
            'id',
            'name',
            'description',
            'category',
            'is_public',
            'creator',
            'creatorName',
            'memberCount',
            'maxMembers',
            'members',
            'challenges',
            'isMember',
            'created_at',
            'updated_at',
        ]
        read_only_fields = fields

    def get_members(self, obj):
        """Return all circle members with their roles."""
        memberships = obj.memberships.select_related('user').order_by('joined_at')
        return CircleMemberSerializer(memberships, many=True).data

    def get_challenges(self, obj):
        """Return active and upcoming challenges for this circle."""
        challenges = obj.challenges.filter(
            status__in=['upcoming', 'active']
        ).order_by('-start_date')
        return CircleChallengeSerializer(challenges, many=True).data

    def get_isMember(self, obj):
        """Check if the requesting user is a member of this circle."""
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return False
        return obj.memberships.filter(user=request.user).exists()


class CircleCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating a new circle.

    Accepts name, description, category, and visibility. The creator
    is set automatically from the request user.
    """

    # Accept camelCase from mobile
    isPublic = serializers.BooleanField(
        source='is_public',
        required=False,
        default=True
    )

    class Meta:
        model = Circle
        fields = [
            'name',
            'description',
            'category',
            'isPublic',
        ]

    def create(self, validated_data):
        """Create the circle and add the creator as an admin member."""
        user = self.context['request'].user
        validated_data['creator'] = user
        circle = super().create(validated_data)

        # Add creator as admin member
        CircleMembership.objects.create(
            circle=circle,
            user=user,
            role='admin'
        )
        return circle


class CirclePostSerializer(serializers.ModelSerializer):
    """
    Serializer for circle posts (feed items).

    Provides post content along with author display info for the feed view.
    """

    user = serializers.SerializerMethodField()
    createdAt = serializers.DateTimeField(source='created_at', read_only=True)
    reactions = serializers.SerializerMethodField()

    class Meta:
        model = CirclePost
        fields = [
            'id',
            'user',
            'content',
            'reactions',
            'createdAt',
        ]
        read_only_fields = ['id', 'user', 'reactions', 'createdAt']

    def get_user(self, obj):
        """Return author display info."""
        return {
            'id': str(obj.author.id),
            'username': obj.author.display_name or 'Anonymous',
            'avatar': obj.author.avatar_url or '',
        }

    def get_reactions(self, obj):
        """Return reaction counts grouped by type."""
        from django.db.models import Count
        counts = obj.reactions.values('reaction_type').annotate(
            count=Count('id')
        )
        return {item['reaction_type']: item['count'] for item in counts}


class CirclePostCreateSerializer(serializers.Serializer):
    """Serializer for creating a new post in a circle."""

    content = serializers.CharField(
        max_length=5000,
        help_text='The text content of the post.'
    )


class CircleUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating a circle (admin only)."""

    isPublic = serializers.BooleanField(
        source='is_public',
        required=False,
    )

    class Meta:
        model = Circle
        fields = [
            'name',
            'description',
            'category',
            'isPublic',
            'max_members',
        ]
        extra_kwargs = {
            'name': {'required': False},
            'description': {'required': False},
            'category': {'required': False},
            'max_members': {'required': False},
        }


class PostReactionSerializer(serializers.Serializer):
    """Serializer for reacting to a post."""

    reaction_type = serializers.ChoiceField(
        choices=['thumbs_up', 'fire', 'clap', 'heart'],
        help_text='Type of reaction.'
    )


class PostReactionDisplaySerializer(serializers.ModelSerializer):
    """Serializer for displaying reactions on a post."""

    username = serializers.CharField(source='user.display_name', read_only=True)

    class Meta:
        model = PostReaction
        fields = ['id', 'user', 'username', 'reaction_type', 'created_at']
        read_only_fields = fields


class CirclePostUpdateSerializer(serializers.Serializer):
    """Serializer for updating a circle post."""

    content = serializers.CharField(
        max_length=5000,
        help_text='The updated text content of the post.'
    )


class MemberRoleSerializer(serializers.Serializer):
    """Serializer for promoting/demoting a member."""

    role = serializers.ChoiceField(
        choices=['member', 'moderator'],
        help_text='New role for the member.'
    )


class CircleInvitationSerializer(serializers.ModelSerializer):
    """Serializer for circle invitations."""

    inviterName = serializers.CharField(source='inviter.display_name', read_only=True)
    inviteeName = serializers.SerializerMethodField()
    circleName = serializers.CharField(source='circle.name', read_only=True)
    isExpired = serializers.BooleanField(source='is_expired', read_only=True)

    class Meta:
        model = CircleInvitation
        fields = [
            'id', 'circle', 'circleName',
            'inviter', 'inviterName',
            'invitee', 'inviteeName',
            'invite_code', 'status', 'expires_at',
            'isExpired', 'created_at',
        ]
        read_only_fields = fields

    def get_inviteeName(self, obj):
        if obj.invitee:
            return obj.invitee.display_name or 'Anonymous'
        return None


class DirectInviteSerializer(serializers.Serializer):
    """Serializer for sending a direct invitation to a user."""

    user_id = serializers.UUIDField(help_text='UUID of the user to invite.')


class ChallengeProgressSerializer(serializers.ModelSerializer):
    """Serializer for challenge progress entries."""

    userName = serializers.SerializerMethodField()
    userAvatar = serializers.SerializerMethodField()

    class Meta:
        model = ChallengeProgress
        fields = [
            'id', 'challenge', 'user',
            'userName', 'userAvatar',
            'progress_value', 'notes',
            'created_at',
        ]
        read_only_fields = ['id', 'challenge', 'user', 'created_at']

    def get_userName(self, obj):
        return obj.user.display_name or 'Anonymous'

    def get_userAvatar(self, obj):
        return obj.user.avatar_url or ''


class ChallengeProgressCreateSerializer(serializers.Serializer):
    """Serializer for submitting challenge progress."""

    progress_value = serializers.FloatField(
        min_value=0,
        help_text='Numeric progress value.',
    )
    notes = serializers.CharField(
        max_length=2000,
        required=False,
        default='',
        help_text='Optional notes about this progress update.',
    )
