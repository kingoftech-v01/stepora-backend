"""
Serializers for the Circles system.

These serializers handle Dream Circle data including circle details,
memberships, posts, and challenges. They provide both list and detail
representations optimized for the mobile app's needs.
"""

from rest_framework import serializers

from .models import Circle, CircleMembership, CirclePost, CircleChallenge


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

    class Meta:
        model = CirclePost
        fields = [
            'id',
            'user',
            'content',
            'createdAt',
        ]
        read_only_fields = ['id', 'user', 'createdAt']

    def get_user(self, obj):
        """Return author display info."""
        return {
            'id': str(obj.author.id),
            'username': obj.author.display_name or 'Anonymous',
            'avatar': obj.author.avatar_url or '',
        }


class CirclePostCreateSerializer(serializers.Serializer):
    """Serializer for creating a new post in a circle."""

    content = serializers.CharField(
        max_length=5000,
        help_text='The text content of the post.'
    )
