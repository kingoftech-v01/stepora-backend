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
    ChallengeProgress,
    Circle,
    CircleCall,
    CircleChallenge,
    CircleInvitation,
    CircleMembership,
    CircleMessage,
    CirclePoll,
    CirclePost,
    PollOption,
    PollVote,
    PostReaction,
)


class CircleMemberSerializer(serializers.ModelSerializer):
    """
    Serializer for circle member display in member lists.

    Provides public user info: username, avatar, and role within the circle.
    """

    username = serializers.CharField(
        source="user.display_name", read_only=True, help_text="Member display name."
    )
    avatar = serializers.SerializerMethodField(help_text="Member avatar URL.")

    class Meta:
        model = CircleMembership
        fields = [
            "id",
            "user",
            "username",
            "avatar",
            "role",
            "joined_at",
        ]
        read_only_fields = fields
        extra_kwargs = {
            "id": {"help_text": "Unique identifier."},
            "user": {"help_text": "ID of the member user."},
            "joined_at": {"help_text": "Date and time the user joined the circle."},
        }

    def get_avatar(self, obj) -> str:
        return obj.user.get_effective_avatar_url()


class CircleChallengeSerializer(serializers.ModelSerializer):
    """
    Serializer for circle challenges.

    Includes challenge details, dates, status, participant count, challenge type,
    and target value.
    """

    participant_count = serializers.IntegerField(
        read_only=True,
        help_text="Number of participants in the challenge.",
    )
    start_date = serializers.DateTimeField(
        read_only=True, help_text="Challenge start date and time."
    )
    end_date = serializers.DateTimeField(
        read_only=True, help_text="Challenge end date and time."
    )
    has_joined = serializers.SerializerMethodField(
        help_text="Whether the current user has joined this challenge."
    )
    challenge_type = serializers.CharField(
        read_only=True, help_text="Type of challenge."
    )
    challenge_type_label = serializers.CharField(
        read_only=True,
        help_text="Human-readable challenge type label.",
    )
    target_value = serializers.IntegerField(
        read_only=True,
        help_text="Target value to complete the challenge.",
    )
    creator_name = serializers.SerializerMethodField(
        help_text="Display name of the challenge creator."
    )
    my_progress = serializers.SerializerMethodField(
        help_text="Current user total progress in this challenge."
    )

    class Meta:
        model = CircleChallenge
        fields = [
            "id",
            "title",
            "description",
            "challenge_type",
            "challenge_type_label",
            "target_value",
            "start_date",
            "end_date",
            "status",
            "participant_count",
            "has_joined",
            "creator_name",
            "my_progress",
            "created_at",
        ]
        read_only_fields = fields
        extra_kwargs = {
            "id": {"help_text": "Unique identifier."},
            "title": {"help_text": "Title of the challenge."},
            "description": {"help_text": "Description of the challenge."},
            "status": {"help_text": "Current status of the challenge."},
            "created_at": {"help_text": "Date and time the challenge was created."},
        }

    def get_has_joined(self, obj):
        request = self.context.get("request")
        if request and hasattr(request, "user") and request.user.is_authenticated:
            return obj.participants.filter(id=request.user.id).exists()
        return False

    def get_creator_name(self, obj):
        if obj.creator:
            return obj.creator.display_name or _("Anonymous")
        return None

    def get_my_progress(self, obj):
        request = self.context.get("request")
        if request and hasattr(request, "user") and request.user.is_authenticated:
            from django.db.models import Sum

            result = obj.progress_entries.filter(user=request.user).aggregate(
                total=Sum("progress_value")
            )
            return result["total"] or 0
        return 0


class CircleChallengeCreateSerializer(serializers.Serializer):
    """Serializer for creating a new challenge in a circle."""

    title = serializers.CharField(max_length=200, help_text="Title of the challenge.")
    description = serializers.CharField(
        max_length=5000,
        required=False,
        default="",
        help_text="Description of the challenge.",
    )
    challenge_type = serializers.ChoiceField(
        choices=["tasks_completed", "streak_days", "focus_minutes", "dreams_progress"],
        help_text="Type of challenge.",
    )
    target_value = serializers.IntegerField(
        min_value=1,
        help_text="Target value to complete the challenge.",
    )
    start_date = serializers.DateTimeField(
        help_text="When the challenge starts."
    )
    end_date = serializers.DateTimeField(
        help_text="When the challenge ends."
    )

    def validate_title(self, value):
        return sanitize_text(value)

    def validate_description(self, value):
        return sanitize_text(value)

    def validate(self, data):
        if data["end_date"] <= data["start_date"]:
            raise serializers.ValidationError(
                {"end_date": _("End date must be after start date.")}
            )
        return data


class PollOptionSerializer(serializers.ModelSerializer):
    """
    Serializer for a single poll option.

    Includes the option text, vote count, and display order.
    """

    vote_count = serializers.IntegerField(
        read_only=True,
        help_text="Number of votes for this option.",
    )

    class Meta:
        model = PollOption
        fields = ["id", "text", "order", "vote_count"]
        read_only_fields = fields
        extra_kwargs = {
            "id": {"help_text": "Unique identifier."},
            "text": {"help_text": "Option text."},
            "order": {"help_text": "Display order."},
        }


class CirclePollSerializer(serializers.ModelSerializer):
    """
    Serializer for a poll attached to a circle post.

    Includes question, options with vote counts, total votes,
    the current user's voted option IDs, and whether the poll has ended.
    """

    options = PollOptionSerializer(
        many=True, read_only=True, help_text="List of poll options."
    )
    total_votes = serializers.IntegerField(
        read_only=True, help_text="Total number of votes."
    )
    allows_multiple = serializers.BooleanField(
        read_only=True,
        help_text="Whether multiple selections are allowed.",
    )
    ends_at = serializers.DateTimeField(
        read_only=True, help_text="Poll end time."
    )
    is_ended = serializers.BooleanField(
        read_only=True, help_text="Whether the poll has ended."
    )
    my_votes = serializers.SerializerMethodField(
        help_text="Option IDs the current user has voted for."
    )

    class Meta:
        model = CirclePoll
        fields = [
            "id",
            "question",
            "options",
            "allows_multiple",
            "ends_at",
            "is_ended",
            "total_votes",
            "my_votes",
        ]
        read_only_fields = fields
        extra_kwargs = {
            "id": {"help_text": "Unique identifier."},
            "question": {"help_text": "The poll question."},
        }

    def get_my_votes(self, obj) -> list:
        """Return list of option IDs the current user voted for."""
        request = self.context.get("request")
        if request and hasattr(request, "user") and request.user.is_authenticated:
            voted_option_ids = PollVote.objects.filter(
                option__poll=obj,
                user=request.user,
            ).values_list("option_id", flat=True)
            return [str(oid) for oid in voted_option_ids]
        return []


class PollOptionInputSerializer(serializers.Serializer):
    """Serializer for a single poll option in a create request."""

    text = serializers.CharField(max_length=200, help_text="Option text.")

    def validate_text(self, value):
        return sanitize_text(value)


class PollCreateSerializer(serializers.Serializer):
    """
    Serializer for creating a poll as part of a circle post.

    Accepts question, options (2-6), allows_multiple flag,
    and an optional end time.
    """

    question = serializers.CharField(max_length=300, help_text="The poll question.")
    options = PollOptionInputSerializer(many=True, help_text="List of options (2-6).")
    allows_multiple = serializers.BooleanField(
        required=False,
        default=False,
        help_text="Whether multiple selections are allowed.",
    )
    ends_at = serializers.DateTimeField(
        required=False,
        default=None,
        help_text="Optional end time for the poll.",
    )

    def validate_question(self, value):
        return sanitize_text(value)

    def validate_options(self, value):
        if len(value) < 2:
            raise serializers.ValidationError(_("A poll must have at least 2 options."))
        if len(value) > 6:
            raise serializers.ValidationError(_("A poll can have at most 6 options."))
        return value


class PollVoteInputSerializer(serializers.Serializer):
    """Serializer for voting on a poll."""

    option_ids = serializers.ListField(
        child=serializers.UUIDField(),
        min_length=1,
        help_text="List of option IDs to vote for.",
    )


class CircleListSerializer(serializers.ModelSerializer):
    """
    Serializer for circle list display.

    Provides a lightweight representation of circles for the list view,
    including member count, member avatars, and basic info.
    """

    member_count = serializers.IntegerField(
        source="members_count",
        read_only=True,
        help_text="Total number of circle members.",
    )
    max_members = serializers.IntegerField(
        read_only=True,
        help_text="Maximum allowed members in the circle.",
    )
    member_avatars = serializers.SerializerMethodField(
        help_text="Avatar URLs of first 5 members."
    )
    creator_name = serializers.CharField(
        source="creator.display_name",
        read_only=True,
        help_text="Display name of the circle creator.",
    )
    is_member = serializers.SerializerMethodField(
        help_text="Whether the requesting user is a member."
    )

    class Meta:
        model = Circle
        fields = [
            "id",
            "name",
            "description",
            "category",
            "is_public",
            "member_count",
            "max_members",
            "member_avatars",
            "creator_name",
            "is_member",
            "created_at",
        ]
        read_only_fields = fields
        extra_kwargs = {
            "id": {"help_text": "Unique identifier."},
            "name": {"help_text": "Name of the circle."},
            "description": {"help_text": "Description of the circle."},
            "category": {"help_text": "Category of the circle."},
            "is_public": {"help_text": "Whether the circle is publicly visible."},
            "created_at": {"help_text": "Date and time the circle was created."},
        }

    def get_member_avatars(self, obj) -> list:
        """Return avatar URLs of the first 5 members for preview display."""
        memberships = obj.memberships.select_related("user").order_by("joined_at")[:5]
        return [
            url
            for m in memberships
            if (url := m.user.get_effective_avatar_url())
        ]

    def get_is_member(self, obj) -> bool:
        """Check if the requesting user is a member of this circle."""
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return False
        return obj.memberships.filter(user=request.user).exists()


class CircleDetailSerializer(serializers.ModelSerializer):
    """
    Serializer for circle detail display.

    Provides full circle information including member list, challenges,
    and whether the current user is a member.
    """

    member_count = serializers.IntegerField(
        source="members_count",
        read_only=True,
        help_text="Total number of circle members.",
    )
    max_members = serializers.IntegerField(
        read_only=True,
        help_text="Maximum allowed members in the circle.",
    )
    members = serializers.SerializerMethodField(help_text="List of all circle members.")
    challenges = serializers.SerializerMethodField(
        help_text="Active and upcoming circle challenges."
    )
    creator_name = serializers.CharField(
        source="creator.display_name",
        read_only=True,
        help_text="Display name of the circle creator.",
    )
    is_member = serializers.SerializerMethodField(
        help_text="Whether the requesting user is a member."
    )

    class Meta:
        model = Circle
        fields = [
            "id",
            "name",
            "description",
            "category",
            "is_public",
            "creator",
            "creator_name",
            "member_count",
            "max_members",
            "members",
            "challenges",
            "is_member",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields
        extra_kwargs = {
            "id": {"help_text": "Unique identifier."},
            "name": {"help_text": "Name of the circle."},
            "description": {"help_text": "Description of the circle."},
            "category": {"help_text": "Category of the circle."},
            "is_public": {"help_text": "Whether the circle is publicly visible."},
            "creator": {"help_text": "ID of the circle creator."},
            "created_at": {"help_text": "Date and time the circle was created."},
            "updated_at": {"help_text": "Date and time the circle was last updated."},
        }

    def get_members(self, obj) -> list:
        """Return all circle members with their roles."""
        memberships = obj.memberships.select_related("user").order_by("joined_at")
        return CircleMemberSerializer(memberships, many=True).data

    def get_challenges(self, obj) -> list:
        """Return active and upcoming challenges for this circle."""
        challenges = obj.challenges.filter(status__in=["upcoming", "active"]).order_by(
            "-start_date"
        )
        return CircleChallengeSerializer(challenges, many=True).data

    def get_is_member(self, obj) -> bool:
        """Check if the requesting user is a member of this circle."""
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return False
        return obj.memberships.filter(user=request.user).exists()


class CircleCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating a new circle.

    Accepts name, description, category, and visibility. The creator
    is set automatically from the request user.
    """

    is_public = serializers.BooleanField(
        required=False,
        default=True,
        help_text="Whether the circle is publicly visible.",
    )

    class Meta:
        model = Circle
        fields = [
            "name",
            "description",
            "category",
            "is_public",
        ]
        extra_kwargs = {
            "name": {"help_text": "Name of the circle."},
            "description": {"help_text": "Description of the circle."},
            "category": {"help_text": "Category of the circle."},
        }

    def validate_name(self, value):
        return sanitize_text(value)

    def validate_description(self, value):
        return sanitize_text(value)

    def create(self, validated_data):
        """Create the circle and add the creator as an admin member."""
        user = self.context["request"].user
        validated_data["creator"] = user
        circle = super().create(validated_data)

        # Add creator as admin member
        CircleMembership.objects.create(circle=circle, user=user, role="admin")
        return circle


class CirclePostSerializer(serializers.ModelSerializer):
    """
    Serializer for circle posts (feed items).

    Provides post content along with author display info for the feed view.
    Includes poll data when the post has an attached poll.
    """

    user = serializers.SerializerMethodField(
        help_text="Author display info including id, username, and avatar."
    )
    created_at = serializers.DateTimeField(
        read_only=True,
        help_text="Date and time the post was created.",
    )
    reactions = serializers.SerializerMethodField(
        help_text="Reaction counts grouped by type."
    )
    poll = serializers.SerializerMethodField(
        help_text="Poll data if the post has a poll attached."
    )

    class Meta:
        model = CirclePost
        fields = [
            "id",
            "user",
            "content",
            "reactions",
            "poll",
            "created_at",
        ]
        read_only_fields = ["id", "user", "reactions", "poll", "created_at"]
        extra_kwargs = {
            "id": {"help_text": "Unique identifier."},
        }

    def get_user(self, obj) -> dict:
        """Return author display info."""
        return {
            "id": str(obj.author.id),
            "username": obj.author.display_name or _("Anonymous"),
            "avatar": obj.author.get_effective_avatar_url(),
        }

    def get_reactions(self, obj) -> dict:
        """Return reaction counts grouped by type."""
        from django.db.models import Count

        counts = obj.reactions.values("reaction_type").annotate(count=Count("id"))
        return {item["reaction_type"]: item["count"] for item in counts}

    def get_poll(self, obj):
        """Return poll data if the post has a poll, otherwise None."""
        try:
            poll = obj.poll
        except CirclePoll.DoesNotExist:
            return None
        return CirclePollSerializer(poll, context=self.context).data


class CirclePostCreateSerializer(serializers.Serializer):
    """Serializer for creating a new post in a circle, optionally with a poll."""

    content = serializers.CharField(
        max_length=5000, help_text="The text content of the post."
    )
    poll = PollCreateSerializer(
        required=False,
        default=None,
        help_text="Optional poll to attach to the post.",
    )

    def validate_content(self, value):
        return sanitize_text(value)


class CircleUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating a circle (admin only)."""

    is_public = serializers.BooleanField(
        required=False,
        help_text="Whether the circle is publicly visible.",
    )

    class Meta:
        model = Circle
        fields = [
            "name",
            "description",
            "category",
            "is_public",
            "max_members",
        ]
        extra_kwargs = {
            "name": {"required": False, "help_text": "Name of the circle."},
            "description": {
                "required": False,
                "help_text": "Description of the circle.",
            },
            "category": {"required": False, "help_text": "Category of the circle."},
            "max_members": {
                "required": False,
                "help_text": "Maximum allowed members in the circle.",
            },
        }

    def validate_name(self, value):
        return sanitize_text(value)

    def validate_description(self, value):
        return sanitize_text(value)


class PostReactionSerializer(serializers.Serializer):
    """Serializer for reacting to a post."""

    reaction_type = serializers.ChoiceField(
        choices=["thumbs_up", "fire", "clap", "heart"], help_text="Type of reaction."
    )


class PostReactionDisplaySerializer(serializers.ModelSerializer):
    """Serializer for displaying reactions on a post."""

    username = serializers.CharField(
        source="user.display_name",
        read_only=True,
        help_text="Display name of the reacting user.",
    )

    class Meta:
        model = PostReaction
        fields = ["id", "user", "username", "reaction_type", "created_at"]
        read_only_fields = fields
        extra_kwargs = {
            "id": {"help_text": "Unique identifier."},
            "user": {"help_text": "ID of the reacting user."},
            "created_at": {"help_text": "Date and time the reaction was created."},
        }


class CirclePostUpdateSerializer(serializers.Serializer):
    """Serializer for updating a circle post."""

    content = serializers.CharField(
        max_length=5000, help_text="The updated text content of the post."
    )

    def validate_content(self, value):
        return sanitize_text(value)


class MemberRoleSerializer(serializers.Serializer):
    """Serializer for promoting/demoting a member."""

    role = serializers.ChoiceField(
        choices=["member", "moderator"], help_text="New role for the member."
    )


class CircleInvitationSerializer(serializers.ModelSerializer):
    """Serializer for circle invitations."""

    inviter_name = serializers.CharField(
        source="inviter.display_name",
        read_only=True,
        help_text="Display name of the inviter.",
    )
    invitee_name = serializers.SerializerMethodField(
        help_text="Display name of the invitee."
    )
    circle_name = serializers.CharField(
        source="circle.name",
        read_only=True,
        help_text="Name of the circle being invited to.",
    )
    is_expired = serializers.BooleanField(
        read_only=True,
        help_text="Whether the invitation has expired.",
    )

    class Meta:
        model = CircleInvitation
        fields = [
            "id",
            "circle",
            "circle_name",
            "inviter",
            "inviter_name",
            "invitee",
            "invitee_name",
            "invite_code",
            "status",
            "expires_at",
            "is_expired",
            "created_at",
        ]
        read_only_fields = fields
        extra_kwargs = {
            "id": {"help_text": "Unique identifier."},
            "circle": {"help_text": "ID of the circle."},
            "inviter": {"help_text": "ID of the user who sent the invitation."},
            "invitee": {"help_text": "ID of the invited user."},
            "invite_code": {"help_text": "Unique invitation code."},
            "status": {"help_text": "Current status of the invitation."},
            "expires_at": {"help_text": "Expiration date and time of the invitation."},
            "created_at": {"help_text": "Date and time the invitation was created."},
        }

    def get_invitee_name(self, obj) -> str:
        if obj.invitee:
            return obj.invitee.display_name or _("Anonymous")
        return None


class DirectInviteSerializer(serializers.Serializer):
    """Serializer for sending a direct invitation to a user."""

    user_id = serializers.UUIDField(help_text="UUID of the user to invite.")


class ChallengeProgressSerializer(serializers.ModelSerializer):
    """Serializer for challenge progress entries."""

    user_name = serializers.SerializerMethodField(help_text="Display name of the user.")
    user_avatar = serializers.SerializerMethodField(help_text="Avatar URL of the user.")

    class Meta:
        model = ChallengeProgress
        fields = [
            "id",
            "challenge",
            "user",
            "user_name",
            "user_avatar",
            "progress_value",
            "notes",
            "created_at",
        ]
        read_only_fields = ["id", "challenge", "user", "created_at"]
        extra_kwargs = {
            "id": {"help_text": "Unique identifier."},
            "challenge": {"help_text": "ID of the associated challenge."},
            "user": {"help_text": "ID of the user tracking progress."},
            "created_at": {"help_text": "Date and time the progress was recorded."},
        }

    def get_user_name(self, obj) -> str:
        return obj.user.display_name or _("Anonymous")

    def get_user_avatar(self, obj) -> str:
        return obj.user.get_effective_avatar_url()


class ChallengeProgressCreateSerializer(serializers.Serializer):
    """Serializer for submitting challenge progress."""

    progress_value = serializers.FloatField(
        min_value=0,
        help_text="Numeric progress value.",
    )
    notes = serializers.CharField(
        max_length=2000,
        required=False,
        default="",
        help_text="Optional notes about this progress update.",
    )

    def validate_notes(self, value):
        return sanitize_text(value)


class CircleMessageSerializer(serializers.ModelSerializer):
    """Serializer for circle chat messages."""

    sender_name = serializers.CharField(source="sender.display_name", read_only=True)
    sender_avatar = serializers.SerializerMethodField()
    created_at = serializers.DateTimeField(read_only=True)

    class Meta:
        model = CircleMessage
        fields = [
            "id",
            "circle",
            "sender",
            "sender_name",
            "sender_avatar",
            "content",
            "metadata",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "circle",
            "sender",
            "sender_name",
            "sender_avatar",
            "created_at",
        ]

    def get_sender_avatar(self, obj) -> str:
        return obj.sender.get_effective_avatar_url()


class CircleCallSerializer(serializers.ModelSerializer):
    """Serializer for circle group calls."""

    initiator_name = serializers.CharField(
        source="initiator.display_name", read_only=True
    )
    participant_count = serializers.SerializerMethodField()
    started_at = serializers.DateTimeField(read_only=True)
    ended_at = serializers.DateTimeField(read_only=True)
    call_type = serializers.CharField(read_only=True)
    agora_channel = serializers.CharField(read_only=True)

    class Meta:
        model = CircleCall
        fields = [
            "id",
            "circle",
            "initiator",
            "initiator_name",
            "call_type",
            "status",
            "agora_channel",
            "started_at",
            "ended_at",
            "duration_seconds",
            "max_participants",
            "participant_count",
        ]
        read_only_fields = fields

    def get_participant_count(self, obj) -> int:
        return obj.participants.filter(left_at__isnull=True).count()
