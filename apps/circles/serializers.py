"""
Serializers for the Circles system.

These serializers handle Dream Circle data including circle details,
memberships, posts, and challenges. They provide both list and detail
representations optimized for the mobile app's needs.
"""

from django.utils.translation import gettext as _
from rest_framework import serializers

from core.sanitizers import sanitize_text
from .models import (
    Circle, CircleMembership, CirclePost, CircleChallenge,
    PostReaction, CircleInvitation, ChallengeProgress,
    CircleMessage, CircleCall, CircleCallParticipant,
)


class CircleMemberSerializer(serializers.ModelSerializer):
    """
    Serializer for circle member display in member lists.

    Provides public user info: username, avatar, and role within the circle.
    """

    username = serializers.CharField(source='user.display_name', read_only=True, help_text='Member display name.')
    avatar = serializers.URLField(source='user.avatar_url', read_only=True, help_text='Member avatar URL.')

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
        extra_kwargs = {
            'id': {'help_text': 'Unique identifier.'},
            'user': {'help_text': 'ID of the member user.'},
            'joined_at': {'help_text': 'Date and time the user joined the circle.'},
        }


class CircleChallengeSerializer(serializers.ModelSerializer):
    """
    Serializer for circle challenges.

    Includes challenge details, dates, status, and participant count.
    Uses camelCase field names to match mobile app expectations.
    """

    participantCount = serializers.IntegerField(
        source='participant_count',
        read_only=True,
        help_text='Number of participants in the challenge.'
    )
    startDate = serializers.DateTimeField(source='start_date', read_only=True, help_text='Challenge start date and time.')
    endDate = serializers.DateTimeField(source='end_date', read_only=True, help_text='Challenge end date and time.')
    hasJoined = serializers.SerializerMethodField(help_text='Whether the current user has joined this challenge.')

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
            'hasJoined',
            'created_at',
        ]
        read_only_fields = fields
        extra_kwargs = {
            'id': {'help_text': 'Unique identifier.'},
            'title': {'help_text': 'Title of the challenge.'},
            'description': {'help_text': 'Description of the challenge.'},
            'status': {'help_text': 'Current status of the challenge.'},
            'created_at': {'help_text': 'Date and time the challenge was created.'},
        }

    def get_hasJoined(self, obj):
        request = self.context.get('request')
        if request and hasattr(request, 'user') and request.user.is_authenticated:
            return obj.participants.filter(id=request.user.id).exists()
        return False


class CircleListSerializer(serializers.ModelSerializer):
    """
    Serializer for circle list display.

    Provides a lightweight representation of circles for the list view,
    including member count, member avatars, and basic info.
    """

    memberCount = serializers.IntegerField(source='member_count', read_only=True, help_text='Total number of circle members.')
    maxMembers = serializers.IntegerField(source='max_members', read_only=True, help_text='Maximum allowed members in the circle.')
    memberAvatars = serializers.SerializerMethodField(help_text='Avatar URLs of first 5 members.')
    creatorName = serializers.CharField(source='creator.display_name', read_only=True, help_text='Display name of the circle creator.')
    isMember = serializers.SerializerMethodField(help_text='Whether the requesting user is a member.')

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
        extra_kwargs = {
            'id': {'help_text': 'Unique identifier.'},
            'name': {'help_text': 'Name of the circle.'},
            'description': {'help_text': 'Description of the circle.'},
            'category': {'help_text': 'Category of the circle.'},
            'is_public': {'help_text': 'Whether the circle is publicly visible.'},
            'created_at': {'help_text': 'Date and time the circle was created.'},
        }

    def get_memberAvatars(self, obj) -> list:
        """Return avatar URLs of the first 5 members for preview display."""
        memberships = obj.memberships.select_related('user').order_by('joined_at')[:5]
        return [m.user.avatar_url for m in memberships if m.user.avatar_url]

    def get_isMember(self, obj) -> bool:
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

    memberCount = serializers.IntegerField(source='member_count', read_only=True, help_text='Total number of circle members.')
    maxMembers = serializers.IntegerField(source='max_members', read_only=True, help_text='Maximum allowed members in the circle.')
    members = serializers.SerializerMethodField(help_text='List of all circle members.')
    challenges = serializers.SerializerMethodField(help_text='Active and upcoming circle challenges.')
    creatorName = serializers.CharField(source='creator.display_name', read_only=True, help_text='Display name of the circle creator.')
    isMember = serializers.SerializerMethodField(help_text='Whether the requesting user is a member.')

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
        extra_kwargs = {
            'id': {'help_text': 'Unique identifier.'},
            'name': {'help_text': 'Name of the circle.'},
            'description': {'help_text': 'Description of the circle.'},
            'category': {'help_text': 'Category of the circle.'},
            'is_public': {'help_text': 'Whether the circle is publicly visible.'},
            'creator': {'help_text': 'ID of the circle creator.'},
            'created_at': {'help_text': 'Date and time the circle was created.'},
            'updated_at': {'help_text': 'Date and time the circle was last updated.'},
        }

    def get_members(self, obj) -> list:
        """Return all circle members with their roles."""
        memberships = obj.memberships.select_related('user').order_by('joined_at')
        return CircleMemberSerializer(memberships, many=True).data

    def get_challenges(self, obj) -> list:
        """Return active and upcoming challenges for this circle."""
        challenges = obj.challenges.filter(
            status__in=['upcoming', 'active']
        ).order_by('-start_date')
        return CircleChallengeSerializer(challenges, many=True).data

    def get_isMember(self, obj) -> bool:
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
        default=True,
        help_text='Whether the circle is publicly visible.'
    )

    class Meta:
        model = Circle
        fields = [
            'name',
            'description',
            'category',
            'isPublic',
        ]
        extra_kwargs = {
            'name': {'help_text': 'Name of the circle.'},
            'description': {'help_text': 'Description of the circle.'},
            'category': {'help_text': 'Category of the circle.'},
        }

    def validate_name(self, value):
        return sanitize_text(value)

    def validate_description(self, value):
        return sanitize_text(value)

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

    user = serializers.SerializerMethodField(help_text='Author display info including id, username, and avatar.')
    createdAt = serializers.DateTimeField(source='created_at', read_only=True, help_text='Date and time the post was created.')
    reactions = serializers.SerializerMethodField(help_text='Reaction counts grouped by type.')

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
        extra_kwargs = {
            'id': {'help_text': 'Unique identifier.'},
        }

    def get_user(self, obj) -> dict:
        """Return author display info."""
        return {
            'id': str(obj.author.id),
            'username': obj.author.display_name or _('Anonymous'),
            'avatar': obj.author.avatar_url or '',
        }

    def get_reactions(self, obj) -> dict:
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

    def validate_content(self, value):
        return sanitize_text(value)


class CircleUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating a circle (admin only)."""

    isPublic = serializers.BooleanField(
        source='is_public',
        required=False,
        help_text='Whether the circle is publicly visible.'
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
            'name': {'required': False, 'help_text': 'Name of the circle.'},
            'description': {'required': False, 'help_text': 'Description of the circle.'},
            'category': {'required': False, 'help_text': 'Category of the circle.'},
            'max_members': {'required': False, 'help_text': 'Maximum allowed members in the circle.'},
        }

    def validate_name(self, value):
        return sanitize_text(value)

    def validate_description(self, value):
        return sanitize_text(value)


class PostReactionSerializer(serializers.Serializer):
    """Serializer for reacting to a post."""

    reaction_type = serializers.ChoiceField(
        choices=['thumbs_up', 'fire', 'clap', 'heart'],
        help_text='Type of reaction.'
    )


class PostReactionDisplaySerializer(serializers.ModelSerializer):
    """Serializer for displaying reactions on a post."""

    username = serializers.CharField(source='user.display_name', read_only=True, help_text='Display name of the reacting user.')

    class Meta:
        model = PostReaction
        fields = ['id', 'user', 'username', 'reaction_type', 'created_at']
        read_only_fields = fields
        extra_kwargs = {
            'id': {'help_text': 'Unique identifier.'},
            'user': {'help_text': 'ID of the reacting user.'},
            'created_at': {'help_text': 'Date and time the reaction was created.'},
        }


class CirclePostUpdateSerializer(serializers.Serializer):
    """Serializer for updating a circle post."""

    content = serializers.CharField(
        max_length=5000,
        help_text='The updated text content of the post.'
    )

    def validate_content(self, value):
        return sanitize_text(value)


class MemberRoleSerializer(serializers.Serializer):
    """Serializer for promoting/demoting a member."""

    role = serializers.ChoiceField(
        choices=['member', 'moderator'],
        help_text='New role for the member.'
    )


class CircleInvitationSerializer(serializers.ModelSerializer):
    """Serializer for circle invitations."""

    inviterName = serializers.CharField(source='inviter.display_name', read_only=True, help_text='Display name of the inviter.')
    inviteeName = serializers.SerializerMethodField(help_text='Display name of the invitee.')
    circleName = serializers.CharField(source='circle.name', read_only=True, help_text='Name of the circle being invited to.')
    isExpired = serializers.BooleanField(source='is_expired', read_only=True, help_text='Whether the invitation has expired.')

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
        extra_kwargs = {
            'id': {'help_text': 'Unique identifier.'},
            'circle': {'help_text': 'ID of the circle.'},
            'inviter': {'help_text': 'ID of the user who sent the invitation.'},
            'invitee': {'help_text': 'ID of the invited user.'},
            'invite_code': {'help_text': 'Unique invitation code.'},
            'status': {'help_text': 'Current status of the invitation.'},
            'expires_at': {'help_text': 'Expiration date and time of the invitation.'},
            'created_at': {'help_text': 'Date and time the invitation was created.'},
        }

    def get_inviteeName(self, obj) -> str:
        if obj.invitee:
            return obj.invitee.display_name or _('Anonymous')
        return None


class DirectInviteSerializer(serializers.Serializer):
    """Serializer for sending a direct invitation to a user."""

    user_id = serializers.UUIDField(help_text='UUID of the user to invite.')


class ChallengeProgressSerializer(serializers.ModelSerializer):
    """Serializer for challenge progress entries."""

    userName = serializers.SerializerMethodField(help_text='Display name of the user.')
    userAvatar = serializers.SerializerMethodField(help_text='Avatar URL of the user.')

    class Meta:
        model = ChallengeProgress
        fields = [
            'id', 'challenge', 'user',
            'userName', 'userAvatar',
            'progress_value', 'notes',
            'created_at',
        ]
        read_only_fields = ['id', 'challenge', 'user', 'created_at']
        extra_kwargs = {
            'id': {'help_text': 'Unique identifier.'},
            'challenge': {'help_text': 'ID of the associated challenge.'},
            'user': {'help_text': 'ID of the user tracking progress.'},
            'created_at': {'help_text': 'Date and time the progress was recorded.'},
        }

    def get_userName(self, obj) -> str:
        return obj.user.display_name or _('Anonymous')

    def get_userAvatar(self, obj) -> str:
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

    def validate_notes(self, value):
        return sanitize_text(value)


class CircleMessageSerializer(serializers.ModelSerializer):
    """Serializer for circle chat messages."""

    senderName = serializers.CharField(source='sender.display_name', read_only=True)
    senderAvatar = serializers.URLField(source='sender.avatar_url', read_only=True)
    createdAt = serializers.DateTimeField(source='created_at', read_only=True)

    class Meta:
        model = CircleMessage
        fields = [
            'id', 'circle', 'sender', 'senderName', 'senderAvatar',
            'content', 'metadata', 'createdAt',
        ]
        read_only_fields = ['id', 'circle', 'sender', 'senderName', 'senderAvatar', 'createdAt']


class CircleCallSerializer(serializers.ModelSerializer):
    """Serializer for circle group calls."""

    initiatorName = serializers.CharField(source='initiator.display_name', read_only=True)
    participantCount = serializers.SerializerMethodField()
    startedAt = serializers.DateTimeField(source='started_at', read_only=True)
    endedAt = serializers.DateTimeField(source='ended_at', read_only=True)
    callType = serializers.CharField(source='call_type', read_only=True)
    agoraChannel = serializers.CharField(source='agora_channel', read_only=True)

    class Meta:
        model = CircleCall
        fields = [
            'id', 'circle', 'initiator', 'initiatorName',
            'callType', 'status', 'agoraChannel',
            'startedAt', 'endedAt', 'duration_seconds',
            'max_participants', 'participantCount',
        ]
        read_only_fields = fields

    def get_participantCount(self, obj) -> int:
        return obj.participants.filter(left_at__isnull=True).count()
