"""
Serializers for the Social system.

These serializers handle friendships, follows, activity feeds, and
user search results. They provide data optimized for the mobile app's
social features.
"""

from django.utils.translation import gettext as _
from drf_spectacular.utils import extend_schema_serializer
from rest_framework import serializers

from apps.users.models import User
from core.sanitizers import sanitize_text

from .models import (
    ActivityFeedItem,
    DreamEncouragement,
    DreamPost,
    DreamPostComment,
    Friendship,
    PostReaction,
    SavedPost,
    SocialEvent,
    SocialEventRegistration,
    Story,
    StoryView,
)
from .validators import (
    validate_audio_upload,
    validate_event_cover_upload,
    validate_image_upload,
    validate_video_upload,
)


class UserPublicSerializer(serializers.ModelSerializer):
    """
    Public user profile serializer for social contexts.

    Exposes display name, avatar, level, and gamification stats
    but never private data like dreams or email.
    """

    username = serializers.CharField(
        source="display_name", read_only=True, help_text="Public display name."
    )
    avatar = serializers.URLField(
        source="avatar_url", read_only=True, help_text="Avatar image URL."
    )
    current_level = serializers.IntegerField(
        source="level", read_only=True, help_text="Current user level."
    )
    influence_score = serializers.IntegerField(
        source="xp", read_only=True, help_text="Total XP earned."
    )
    current_streak = serializers.IntegerField(
        source="streak_days", read_only=True, help_text="Current streak in days."
    )
    title = serializers.SerializerMethodField(
        help_text="Title based on level (e.g., Dreamer, Explorer)."
    )

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "avatar",
            "current_level",
            "influence_score",
            "current_streak",
            "title",
        ]
        read_only_fields = fields
        extra_kwargs = {
            "id": {"help_text": "Unique user identifier."},
        }

    def get_title(self, obj) -> str:
        """Generate a title based on the user's level."""
        level = obj.level
        if level >= 50:
            return "Legend"
        elif level >= 30:
            return "Master"
        elif level >= 20:
            return "Expert"
        elif level >= 10:
            return "Achiever"
        elif level >= 5:
            return "Explorer"
        return "Dreamer"


class FriendSerializer(serializers.Serializer):
    """
    Serializer for displaying a friend in the friends list.

    Combines user public data with friendship metadata.
    """

    id = serializers.UUIDField(help_text="User ID of the friend.")
    username = serializers.CharField(help_text="Display name of the friend.")
    avatar = serializers.URLField(
        allow_blank=True, help_text="Avatar URL of the friend."
    )
    title = serializers.CharField(help_text="Title based on level.")
    current_level = serializers.IntegerField(help_text="Current level.")
    influence_score = serializers.IntegerField(help_text="Influence score (XP).")
    current_streak = serializers.IntegerField(help_text="Current streak days.")


@extend_schema_serializer(component_name="PendingFriendRequest")
class FriendRequestSerializer(serializers.ModelSerializer):
    """
    Serializer for pending friend requests.

    Shows the sender's public info for incoming requests.
    """

    sender = serializers.SerializerMethodField(help_text="Sender public profile info.")

    class Meta:
        model = Friendship
        fields = [
            "id",
            "sender",
            "status",
            "created_at",
        ]
        read_only_fields = fields
        extra_kwargs = {
            "id": {"help_text": "Friend request identifier."},
            "status": {"help_text": "Request status (pending, accepted, rejected)."},
            "created_at": {"help_text": "When the request was sent."},
        }

    def get_sender(self, obj) -> dict:
        """Return the sender's public profile info."""
        user = obj.user1
        return {
            "id": str(user.id),
            "username": user.display_name or "Anonymous",
            "avatar": user.avatar_url or "",
            "current_level": user.level,
            "influence_score": user.xp,
        }


class UserSearchResultSerializer(serializers.Serializer):
    """
    Serializer for user search results.

    Includes public profile info plus friendship/follow status
    relative to the requesting user.
    """

    id = serializers.UUIDField(help_text="User ID.")
    username = serializers.CharField(help_text="Display name.")
    avatar = serializers.URLField(allow_blank=True, help_text="Avatar URL.")
    title = serializers.CharField(help_text="Title based on level.")
    influence_score = serializers.IntegerField(help_text="Influence score (XP).")
    current_level = serializers.IntegerField(help_text="Current level.")
    is_friend = serializers.BooleanField(help_text="Whether they are already a friend.")
    is_pending_request = serializers.BooleanField(
        help_text="Whether a friend request is pending.", default=False
    )
    is_following = serializers.BooleanField(
        help_text="Whether the current user follows them."
    )


class ActivityFeedItemSerializer(serializers.ModelSerializer):
    """
    Serializer for activity feed items.

    Provides activity data with the actor's public info for the social feed.
    """

    user = serializers.SerializerMethodField(help_text="Actor public profile info.")
    type = serializers.CharField(
        source="activity_type",
        help_text="Activity type (e.g., dream_completed, task_done).",
    )
    created_at = serializers.DateTimeField(
        read_only=True, help_text="When the activity occurred."
    )

    class Meta:
        model = ActivityFeedItem
        fields = [
            "id",
            "user",
            "type",
            "content",
            "created_at",
        ]
        read_only_fields = fields
        extra_kwargs = {
            "id": {"help_text": "Activity feed item identifier."},
            "content": {"help_text": "Activity description text."},
        }

    def get_user(self, obj) -> dict:
        """Return the actor's public profile info."""
        return {
            "id": str(obj.user.id),
            "username": obj.user.display_name or "Anonymous",
            "avatar": obj.user.avatar_url or "",
        }


class SendFriendRequestSerializer(serializers.Serializer):
    """Serializer for sending a friend request."""

    target_user_id = serializers.UUIDField(
        help_text="The UUID of the user to send a friend request to."
    )


class FollowUserSerializer(serializers.Serializer):
    """Serializer for following a user."""

    target_user_id = serializers.UUIDField(help_text="The UUID of the user to follow.")


class BlockUserSerializer(serializers.Serializer):
    """Serializer for blocking a user."""

    target_user_id = serializers.UUIDField(help_text="The UUID of the user to block.")
    reason = serializers.CharField(
        required=False, default="", help_text="Optional reason for blocking."
    )

    def validate_reason(self, value):
        return sanitize_text(value)


class ReportUserSerializer(serializers.Serializer):
    """Serializer for reporting a user."""

    target_user_id = serializers.UUIDField(help_text="The UUID of the user to report.")
    reason = serializers.CharField(
        help_text="Description of why the user is being reported."
    )
    category = serializers.ChoiceField(
        choices=["spam", "harassment", "inappropriate", "other"],
        default="other",
        help_text="Category of the report.",
    )

    def validate_reason(self, value):
        return sanitize_text(value)


class BlockedUserSerializer(serializers.Serializer):
    """Serializer for blocked user list items."""

    id = serializers.UUIDField(help_text="Block record ID.")
    user = serializers.SerializerMethodField(help_text="Blocked user public profile.")
    reason = serializers.CharField(help_text="Reason for blocking.")
    created_at = serializers.DateTimeField(help_text="When the block was created.")

    def get_user(self, obj) -> dict:
        blocked = obj.blocked
        return {
            "id": str(blocked.id),
            "username": blocked.display_name or "Anonymous",
            "avatar": blocked.avatar_url or "",
        }


# ── Dream Post serializers ────────────────────────────────────────────


class DreamPostSerializer(serializers.ModelSerializer):
    """Full dream post representation for the feed."""

    user = serializers.SerializerMethodField()
    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)
    likes_count = serializers.IntegerField(read_only=True)
    comments_count = serializers.IntegerField(read_only=True)
    shares_count = serializers.IntegerField(read_only=True)
    saves_count = serializers.IntegerField(read_only=True)
    has_liked = serializers.SerializerMethodField()
    has_saved = serializers.SerializerMethodField()
    has_encouraged = serializers.SerializerMethodField()
    encouragement_summary = serializers.SerializerMethodField()
    user_reaction = serializers.SerializerMethodField()
    reaction_counts = serializers.SerializerMethodField()
    gofundme_url = serializers.URLField(read_only=True)
    image_url = serializers.SerializerMethodField()
    video_url = serializers.SerializerMethodField()
    audio_url = serializers.SerializerMethodField()
    media_type = serializers.CharField(read_only=True)
    post_type = serializers.CharField(read_only=True)
    dream_title = serializers.SerializerMethodField()
    linked_achievement = serializers.SerializerMethodField()
    event_detail = serializers.SerializerMethodField()

    class Meta:
        model = DreamPost
        fields = [
            "id",
            "user",
            "dream",
            "dream_title",
            "content",
            "image_url",
            "video_url",
            "audio_url",
            "media_type",
            "post_type",
            "gofundme_url",
            "visibility",
            "likes_count",
            "comments_count",
            "shares_count",
            "saves_count",
            "is_pinned",
            "has_liked",
            "has_saved",
            "has_encouraged",
            "encouragement_summary",
            "user_reaction",
            "reaction_counts",
            "linked_achievement",
            "event_detail",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_user(self, obj) -> dict:
        request = self.context.get("request")
        is_following = False
        if request and request.user.is_authenticated and obj.user_id != request.user.id:
            if hasattr(obj, "_user_is_following"):
                is_following = obj._user_is_following
            else:
                from apps.social.models import UserFollow

                is_following = UserFollow.objects.filter(
                    follower=request.user,
                    following_id=obj.user_id,
                ).exists()
        return {
            "id": str(obj.user.id),
            "username": obj.user.display_name or "Anonymous",
            "avatar": obj.user.avatar_url or "",
            "level": obj.user.level,
            "is_following": is_following,
        }

    def get_has_liked(self, obj) -> bool:
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return False
        if hasattr(obj, "_user_has_liked"):
            return obj._user_has_liked
        return obj.likes.filter(user=request.user).exists()

    def get_has_saved(self, obj) -> bool:
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return False
        if hasattr(obj, "_user_has_saved"):
            return obj._user_has_saved
        return SavedPost.objects.filter(post=obj, user=request.user).exists()

    def get_has_encouraged(self, obj) -> bool:
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return False
        if hasattr(obj, "_user_has_encouraged"):
            return obj._user_has_encouraged
        return obj.encouragements.filter(user=request.user).exists()

    def get_encouragement_summary(self, obj) -> dict:
        from django.db.models import Count

        counts = obj.encouragements.values("encouragement_type").annotate(
            count=Count("id")
        )
        return {item["encouragement_type"]: item["count"] for item in counts}

    def get_user_reaction(self, obj):
        """Return the current user's reaction type on this post, or None."""
        if hasattr(obj, "_user_reaction_type"):
            return obj._user_reaction_type
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return None
        reaction = (
            PostReaction.objects.filter(
                post=obj,
                user=request.user,
            )
            .values_list("reaction_type", flat=True)
            .first()
        )
        return reaction

    def get_reaction_counts(self, obj) -> dict:
        """Return a dict of reaction_type -> count for this post."""
        from django.db.models import Count

        counts = obj.reactions.values("reaction_type").annotate(count=Count("id"))
        return {item["reaction_type"]: item["count"] for item in counts}

    def _absolute_url(self, relative_url):
        """Convert a relative media URL to an absolute URL."""
        request = self.context.get("request")
        if request:
            return request.build_absolute_uri(relative_url)
        return relative_url

    def get_image_url(self, obj) -> str:
        if obj.image_url:
            return obj.image_url
        if obj.image_file:
            return self._absolute_url(obj.image_file.url)
        return ""

    def get_video_url(self, obj) -> str:
        if obj.video_file:
            return self._absolute_url(obj.video_file.url)
        return ""

    def get_audio_url(self, obj) -> str:
        if obj.audio_file:
            return self._absolute_url(obj.audio_file.url)
        return ""

    def get_dream_title(self, obj) -> str:
        if obj.dream:
            return obj.dream.title
        return ""

    def get_linked_achievement(self, obj) -> dict:
        if obj.post_type not in ("achievement", "milestone"):
            return None
        result = {"type": obj.post_type}
        if obj.linked_goal:
            result["goal_title"] = obj.linked_goal.title
        if obj.linked_milestone:
            result["milestone_title"] = obj.linked_milestone.title
        if obj.linked_task:
            result["task_title"] = obj.linked_task.title
        if obj.dream:
            result["dream_title"] = obj.dream.title
        return result

    def get_event_detail(self, obj) -> dict:
        if obj.post_type != "event":
            return None
        events = obj.social_event.all()
        if not events:
            return None
        event = events[0]
        request = self.context.get("request")
        is_registered = False
        if request and request.user.is_authenticated:
            is_registered = event.registrations.filter(
                user=request.user, status="registered"
            ).exists()
        return {
            "id": str(event.id),
            "title": event.title,
            "description": event.description,
            "event_type": event.event_type,
            "location": event.location,
            "meeting_link": event.meeting_link,
            "start_time": event.start_time.isoformat(),
            "end_time": event.end_time.isoformat(),
            "max_participants": event.max_participants,
            "participants_count": event.participants_count,
            "status": event.status,
            "is_registered": is_registered,
        }


class DreamPostCreateSerializer(serializers.Serializer):
    """Serializer for creating a dream post with optional media and event."""

    content = serializers.CharField(max_length=5000)
    dream_id = serializers.UUIDField(required=False, allow_null=True)
    gofundme_url = serializers.URLField(required=False, default="")
    visibility = serializers.ChoiceField(
        choices=["public", "followers", "private"],
        default="public",
    )
    image_url = serializers.URLField(required=False, default="")

    # Media uploads
    image_file = serializers.ImageField(required=False, allow_null=True)
    video_file = serializers.FileField(required=False, allow_null=True)
    audio_file = serializers.FileField(required=False, allow_null=True)

    # Post type & achievement linking
    post_type = serializers.ChoiceField(
        choices=["regular", "achievement", "milestone", "event"],
        default="regular",
    )
    linked_goal_id = serializers.UUIDField(required=False, allow_null=True)
    linked_milestone_id = serializers.UUIDField(required=False, allow_null=True)
    linked_task_id = serializers.UUIDField(required=False, allow_null=True)

    # Event fields (only when post_type = 'event')
    event_title = serializers.CharField(max_length=255, required=False)
    event_description = serializers.CharField(
        max_length=5000, required=False, default=""
    )
    event_type = serializers.ChoiceField(
        choices=["virtual", "physical", "challenge"],
        required=False,
    )
    event_location = serializers.CharField(max_length=500, required=False, default="")
    event_meeting_link = serializers.URLField(required=False, default="")
    event_start_time = serializers.DateTimeField(required=False)
    event_end_time = serializers.DateTimeField(required=False)
    event_max_participants = serializers.IntegerField(
        required=False,
        allow_null=True,
        min_value=1,
    )
    event_cover_image = serializers.ImageField(required=False, allow_null=True)
    event_challenge_description = serializers.CharField(
        max_length=5000,
        required=False,
        default="",
    )

    def validate_content(self, value):
        return sanitize_text(value)

    def validate_gofundme_url(self, value):
        if value:
            from core.sanitizers import sanitize_url

            return sanitize_url(value)
        return value

    def validate_image_file(self, value):
        if value:
            validate_image_upload(value)
        return value

    def validate_video_file(self, value):
        if value:
            validate_video_upload(value)
        return value

    def validate_audio_file(self, value):
        if value:
            validate_audio_upload(value)
        return value

    def validate_event_cover_image(self, value):
        if value:
            validate_event_cover_upload(value)
        return value

    def validate_event_meeting_link(self, value):
        if value:
            from core.sanitizers import sanitize_url

            return sanitize_url(value)
        return value

    def validate(self, data):
        # Ensure only one media type
        media_count = sum(
            1
            for f in [
                data.get("image_file"),
                data.get("video_file"),
                data.get("audio_file"),
            ]
            if f
        )
        if data.get("image_url") and media_count > 0:
            raise serializers.ValidationError(
                _("Cannot provide both image_url and an uploaded file.")
            )
        if media_count > 1:
            raise serializers.ValidationError(
                _(
                    "Only one media file (image, video, or audio) can be uploaded per post."
                )
            )

        # Validate event fields when post_type is 'event'
        if data.get("post_type") == "event":
            if not data.get("event_title"):
                raise serializers.ValidationError(
                    {"event_title": _("Event title is required for event posts.")}
                )
            if not data.get("event_type"):
                raise serializers.ValidationError(
                    {"event_type": _("Event type is required for event posts.")}
                )
            if not data.get("event_start_time") or not data.get("event_end_time"):
                raise serializers.ValidationError(
                    _("Event start and end times are required.")
                )
            if data["event_end_time"] <= data["event_start_time"]:
                raise serializers.ValidationError(
                    _("Event end time must be after start time.")
                )
            # Virtual events need a link
            if data["event_type"] == "virtual" and not data.get("event_meeting_link"):
                raise serializers.ValidationError(
                    {
                        "event_meeting_link": _(
                            "Meeting link is required for virtual events."
                        )
                    }
                )

        return data


class DreamPostCommentSerializer(serializers.ModelSerializer):
    """Comment on a dream post."""

    user = serializers.SerializerMethodField()
    created_at = serializers.DateTimeField(read_only=True)
    replies = serializers.SerializerMethodField()

    class Meta:
        model = DreamPostComment
        fields = ["id", "user", "content", "parent", "replies", "created_at"]
        read_only_fields = ["id", "user", "replies", "created_at"]

    def get_user(self, obj) -> dict:
        return {
            "id": str(obj.user.id),
            "username": obj.user.display_name or "Anonymous",
            "avatar": obj.user.avatar_url or "",
        }

    def get_replies(self, obj) -> list:
        if obj.replies.exists():
            return DreamPostCommentSerializer(
                obj.replies.select_related("user").order_by("created_at")[:10],
                many=True,
                context=self.context,
            ).data
        return []


class DreamEncouragementSerializer(serializers.ModelSerializer):
    """Encouragement on a dream post."""

    user = serializers.SerializerMethodField()
    encouragement_type = serializers.CharField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)

    class Meta:
        model = DreamEncouragement
        fields = ["id", "user", "encouragement_type", "message", "created_at"]
        read_only_fields = fields

    def get_user(self, obj) -> dict:
        return {
            "id": str(obj.user.id),
            "username": obj.user.display_name or "Anonymous",
            "avatar": obj.user.avatar_url or "",
        }


# ── Social Event serializers ─────────────────────────────────────────


class SocialEventSerializer(serializers.ModelSerializer):
    """Full social event representation."""

    creator = serializers.SerializerMethodField()
    created_at = serializers.DateTimeField(read_only=True)
    start_time = serializers.DateTimeField(read_only=True)
    end_time = serializers.DateTimeField(read_only=True)
    event_type = serializers.CharField(read_only=True)
    meeting_link = serializers.URLField(read_only=True)
    max_participants = serializers.IntegerField(read_only=True)
    participants_count = serializers.IntegerField(read_only=True)
    cover_image_url = serializers.SerializerMethodField()
    challenge_description = serializers.CharField(read_only=True)
    is_registered = serializers.SerializerMethodField()
    dream_title = serializers.SerializerMethodField()
    post_id = serializers.SerializerMethodField()

    class Meta:
        model = SocialEvent
        fields = [
            "id",
            "creator",
            "post_id",
            "title",
            "description",
            "cover_image_url",
            "event_type",
            "location",
            "meeting_link",
            "start_time",
            "end_time",
            "challenge_description",
            "max_participants",
            "participants_count",
            "status",
            "is_registered",
            "dream_title",
            "created_at",
        ]
        read_only_fields = fields

    def get_creator(self, obj) -> dict:
        return {
            "id": str(obj.creator.id),
            "username": obj.creator.display_name or "Anonymous",
            "avatar": obj.creator.avatar_url or "",
            "level": obj.creator.level,
        }

    def get_cover_image_url(self, obj) -> str:
        if obj.cover_image:
            return obj.cover_image.url
        return ""

    def get_is_registered(self, obj) -> bool:
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return False
        if hasattr(obj, "_user_is_registered"):
            return obj._user_is_registered
        return obj.registrations.filter(user=request.user, status="registered").exists()

    def get_dream_title(self, obj) -> str:
        if obj.dream:
            return obj.dream.title
        return ""

    def get_post_id(self, obj) -> str:
        if obj.post_id:
            return str(obj.post_id)
        return ""


class SocialEventCreateSerializer(serializers.Serializer):
    """Serializer for creating a social event standalone (without post)."""

    title = serializers.CharField(max_length=255)
    description = serializers.CharField(max_length=5000, required=False, default="")
    event_type = serializers.ChoiceField(choices=["virtual", "physical", "challenge"])
    location = serializers.CharField(max_length=500, required=False, default="")
    meeting_link = serializers.URLField(required=False, default="")
    start_time = serializers.DateTimeField()
    end_time = serializers.DateTimeField()
    max_participants = serializers.IntegerField(
        required=False,
        allow_null=True,
        min_value=1,
    )
    dream_id = serializers.UUIDField(required=False, allow_null=True)
    cover_image = serializers.ImageField(required=False, allow_null=True)
    challenge_description = serializers.CharField(
        max_length=5000,
        required=False,
        default="",
    )

    def validate_title(self, value):
        return sanitize_text(value)

    def validate_description(self, value):
        return sanitize_text(value)

    def validate_challenge_description(self, value):
        return sanitize_text(value)

    def validate_meeting_link(self, value):
        if value:
            from core.sanitizers import sanitize_url

            return sanitize_url(value)
        return value

    def validate_cover_image(self, value):
        if value:
            validate_event_cover_upload(value)
        return value

    def validate(self, data):
        if data["end_time"] <= data["start_time"]:
            raise serializers.ValidationError(
                "Event end time must be after start time."
            )
        if data["event_type"] == "virtual" and not data.get("meeting_link"):
            raise serializers.ValidationError(
                {"meeting_link": _("Meeting link is required for virtual events.")}
            )
        return data


class SocialEventRegistrationSerializer(serializers.ModelSerializer):
    """Registration record for a social event."""

    user = serializers.SerializerMethodField()
    registered_at = serializers.DateTimeField(read_only=True)

    class Meta:
        model = SocialEventRegistration
        fields = ["id", "user", "status", "registered_at"]
        read_only_fields = fields

    def get_user(self, obj) -> dict:
        return {
            "id": str(obj.user.id),
            "username": obj.user.display_name or "Anonymous",
            "avatar": obj.user.avatar_url or "",
            "level": obj.user.level,
        }


# ═══════════════════════════════════════════════════════════════════
#  Story Serializers
# ═══════════════════════════════════════════════════════════════════


class StorySerializer(serializers.ModelSerializer):
    """Read serializer for a single story."""

    user = serializers.SerializerMethodField()
    image_url = serializers.SerializerMethodField()
    video_url = serializers.SerializerMethodField()
    media_type = serializers.CharField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)
    expires_at = serializers.DateTimeField(read_only=True)
    view_count = serializers.IntegerField(read_only=True)
    has_viewed = serializers.SerializerMethodField()

    class Meta:
        model = Story
        fields = [
            "id",
            "user",
            "image_url",
            "video_url",
            "media_type",
            "caption",
            "created_at",
            "expires_at",
            "view_count",
            "has_viewed",
        ]
        read_only_fields = fields

    def get_user(self, obj) -> dict:
        return {
            "id": str(obj.user.id),
            "username": obj.user.display_name or "Anonymous",
            "display_name": obj.user.display_name or "Anonymous",
            "avatar": obj.user.avatar_url or "",
        }

    def _absolute_url(self, relative_url):
        request = self.context.get("request")
        if request:
            return request.build_absolute_uri(relative_url)
        return relative_url

    def get_image_url(self, obj) -> str:
        if obj.image_file:
            return self._absolute_url(obj.image_file.url)
        return ""

    def get_video_url(self, obj) -> str:
        if obj.video_file:
            return self._absolute_url(obj.video_file.url)
        return ""

    def get_has_viewed(self, obj) -> bool:
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return False
        if hasattr(obj, "_user_has_viewed"):
            return obj._user_has_viewed
        return StoryView.objects.filter(story=obj, user=request.user).exists()


class StoryCreateSerializer(serializers.Serializer):
    """Write serializer for creating a story."""

    image_file = serializers.ImageField(required=False, allow_null=True)
    video_file = serializers.FileField(required=False, allow_null=True)
    caption = serializers.CharField(max_length=280, required=False, default="")

    def validate(self, data):
        has_image = bool(data.get("image_file"))
        has_video = bool(data.get("video_file"))
        if not has_image and not has_video:
            raise serializers.ValidationError(_("A story requires an image or video."))
        if has_image and has_video:
            raise serializers.ValidationError(_("Only one media file per story."))
        if has_image:
            validate_image_upload(data["image_file"])
        if has_video:
            validate_video_upload(data["video_file"])
        return data


class StoryFeedGroupSerializer(serializers.Serializer):
    """Groups stories by user for the feed."""

    user = serializers.DictField()
    stories = StorySerializer(many=True)
    has_unviewed = serializers.BooleanField()
