"""
Views for the Social system.

Provides API endpoints for friendships, follows, activity feeds,
and user search. All endpoints require authentication.
"""

import logging
from datetime import timedelta

from django.db.models import Count, Exists, F, OuterRef, Q, Subquery
from django.utils import timezone
from django.utils.translation import gettext as _
from drf_spectacular.utils import (
    OpenApiParameter,
    OpenApiResponse,
    extend_schema,
    inline_serializer,
)
from rest_framework import generics
from rest_framework import serializers as drf_serializers
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.users.models import User
from core.permissions import CanUseSocialFeed

from .models import (
    ActivityComment,
    ActivityFeedItem,
    ActivityLike,
    BlockedUser,
    DreamEncouragement,
    DreamPost,
    DreamPostComment,
    DreamPostLike,
    Friendship,
    PostReaction,
    RecentSearch,
    ReportedUser,
    SavedPost,
    SocialEvent,
    SocialEventRegistration,
    Story,
    StoryView,
    UserFollow,
)
from .serializers import (
    ActivityFeedItemSerializer,
    BlockedUserSerializer,
    BlockUserSerializer,
    DreamEncouragementSerializer,
    DreamPostCommentSerializer,
    DreamPostCreateSerializer,
    DreamPostSerializer,
    FollowUserSerializer,
    FriendRequestSerializer,
    FriendSerializer,
    ReportUserSerializer,
    SendFriendRequestSerializer,
    SocialEventCreateSerializer,
    SocialEventRegistrationSerializer,
    SocialEventSerializer,
    StoryCreateSerializer,
    StorySerializer,
    UserSearchResultSerializer,
)

logger = logging.getLogger(__name__)


class FriendshipViewSet(viewsets.GenericViewSet):
    """
    ViewSet for friendship management.

    Supports listing friends, viewing/sending/accepting/rejecting requests,
    and following users.
    """

    queryset = Friendship.objects.none()
    permission_classes = [IsAuthenticated]
    serializer_class = FriendSerializer

    def _get_friend_data(self, user):
        """Build friend data dict from a User object."""
        level = user.level
        if level >= 50:
            title = "Legend"
        elif level >= 30:
            title = "Master"
        elif level >= 20:
            title = "Expert"
        elif level >= 10:
            title = "Achiever"
        elif level >= 5:
            title = "Explorer"
        else:
            title = "Dreamer"

        return {
            "id": user.id,
            "username": user.display_name or "Anonymous",
            "avatar": user.get_effective_avatar_url(),
            "title": title,
            "current_level": user.level,
            "influence_score": user.xp,
            "current_streak": user.streak_days,
        }

    @extend_schema(
        summary="List friends",
        description="Retrieve the current user's accepted friends.",
        responses={200: FriendSerializer(many=True)},
        tags=["Social"],
    )
    @action(detail=False, methods=["get"], url_path="friends")
    def list_friends(self, request):
        """
        List all accepted friends of the current user.

        Returns public profile info for each friend including
        username, avatar, level, and influence score.
        """
        friendships = Friendship.objects.filter(
            Q(user1=request.user) | Q(user2=request.user), status="accepted"
        ).select_related("user1", "user2")

        friends = []
        for friendship in friendships:
            friend_user = (
                friendship.user2
                if friendship.user1_id == request.user.id
                else friendship.user1
            )
            friends.append(self._get_friend_data(friend_user))

        serializer = FriendSerializer(friends, many=True)
        return Response(serializer.data)

    @extend_schema(
        summary="Pending friend requests",
        description="Retrieve pending friend requests sent to the current user.",
        responses={200: FriendRequestSerializer(many=True)},
        tags=["Social"],
    )
    @action(detail=False, methods=["get"], url_path="friends/requests/pending")
    def pending_requests(self, request):
        """
        List pending friend requests received by the current user.

        Returns the sender's public info for each pending request.
        """
        requests_qs = (
            Friendship.objects.filter(user2=request.user, status="pending")
            .select_related("user1")
            .order_by("-created_at")
        )

        serializer = FriendRequestSerializer(requests_qs, many=True)
        return Response(serializer.data)

    @extend_schema(
        summary="Send friend request",
        description="Send a friend request to another user.",
        request=SendFriendRequestSerializer,
        responses={
            201: OpenApiResponse(description="Friend request sent."),
            400: OpenApiResponse(
                description="Cannot send request (already friends, self-request, etc.)."
            ),
            404: OpenApiResponse(description="Resource not found."),
        },
        tags=["Social"],
    )
    @action(detail=False, methods=["post"], url_path="friends/request")
    def send_request(self, request):
        """
        Send a friend request.

        Creates a pending friendship between the current user and the
        target user. Fails if a friendship already exists or if the
        user tries to befriend themselves.
        """
        serializer = SendFriendRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        target_user_id = serializer.validated_data["target_user_id"]

        # Cannot befriend yourself
        if target_user_id == request.user.id:
            return Response(
                {"error": _("You cannot send a friend request to yourself.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Check target exists
        try:
            target_user = User.objects.get(id=target_user_id)
        except User.DoesNotExist:
            return Response(
                {"error": _("User not found.")}, status=status.HTTP_404_NOT_FOUND
            )

        # Check if either user has blocked the other
        if BlockedUser.objects.filter(
            Q(blocker=request.user, blocked=target_user)
            | Q(blocker=target_user, blocked=request.user)
        ).exists():
            return Response(
                {"error": _("Cannot send friend request to this user.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Check for existing friendship in either direction
        existing = Friendship.objects.filter(
            Q(user1=request.user, user2=target_user)
            | Q(user1=target_user, user2=request.user)
        ).first()

        if existing:
            if existing.status == "accepted":
                return Response(
                    {"error": _("You are already friends with this user.")},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            elif existing.status == "pending":
                return Response(
                    {"error": _("A friend request is already pending.")},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            elif existing.status == "rejected":
                # Allow re-sending after rejection
                existing.status = "pending"
                existing.user1 = request.user
                existing.user2 = target_user
                existing.save(update_fields=["status", "user1", "user2", "updated_at"])
                return Response(
                    {"message": _("Friend request sent.")},
                    status=status.HTTP_201_CREATED,
                )

        Friendship.objects.create(
            user1=request.user, user2=target_user, status="pending"
        )

        # Send push notification to the recipient
        try:
            from apps.notifications.models import Notification

            Notification.objects.create(
                user=target_user,
                notification_type="buddy",
                title=_("New Friend Request"),
                body=_("%(name)s sent you a friend request.")
                % {"name": request.user.display_name or "Someone"},
                data={"screen": "friends", "user_id": str(request.user.id)},
            )
        except Exception:
            pass

        return Response(
            {"message": _("Friend request sent.")}, status=status.HTTP_201_CREATED
        )

    @extend_schema(
        summary="Accept friend request",
        description="Accept a pending friend request.",
        responses={
            200: OpenApiResponse(description="Friend request accepted."),
            404: OpenApiResponse(description="Request not found."),
        },
        tags=["Social"],
    )
    @action(
        detail=False,
        methods=["post"],
        url_path=r"friends/accept/(?P<request_id>[0-9a-f-]+)",
    )
    def accept_request(self, request, request_id=None):
        """
        Accept a pending friend request.

        Changes the friendship status from 'pending' to 'accepted'.
        Only the recipient (user2) can accept.
        """
        try:
            friendship = Friendship.objects.get(
                id=request_id, user2=request.user, status="pending"
            )
        except Friendship.DoesNotExist:
            return Response(
                {"error": _("Friend request not found.")},
                status=status.HTTP_404_NOT_FOUND,
            )

        friendship.status = "accepted"
        friendship.save(update_fields=["status", "updated_at"])

        # Notify the sender that their request was accepted
        try:
            from apps.notifications.models import Notification

            Notification.objects.create(
                user=friendship.user1,
                notification_type="buddy",
                title=_("Friend Request Accepted"),
                body=_("%(name)s accepted your friend request!")
                % {"name": request.user.display_name or "Someone"},
                data={"screen": "friends", "user_id": str(request.user.id)},
            )
        except Exception:
            pass

        return Response({"message": _("Friend request accepted.")})

    @extend_schema(
        summary="Reject friend request",
        description="Reject a pending friend request.",
        responses={
            200: OpenApiResponse(description="Friend request rejected."),
            404: OpenApiResponse(description="Request not found."),
        },
        tags=["Social"],
    )
    @action(
        detail=False,
        methods=["post"],
        url_path=r"friends/reject/(?P<request_id>[0-9a-f-]+)",
    )
    def reject_request(self, request, request_id=None):
        """
        Reject a pending friend request.

        Changes the friendship status from 'pending' to 'rejected'.
        Only the recipient (user2) can reject.
        """
        try:
            friendship = Friendship.objects.get(
                id=request_id, user2=request.user, status="pending"
            )
        except Friendship.DoesNotExist:
            return Response(
                {"error": _("Friend request not found.")},
                status=status.HTTP_404_NOT_FOUND,
            )

        friendship.status = "rejected"
        friendship.save(update_fields=["status", "updated_at"])

        return Response({"message": _("Friend request rejected.")})

    @extend_schema(
        summary="Follow a user",
        description="Follow another user to see their activity in your feed.",
        request=FollowUserSerializer,
        responses={
            201: OpenApiResponse(description="Successfully followed the user."),
            400: OpenApiResponse(description="Already following or invalid target."),
            404: OpenApiResponse(description="Resource not found."),
        },
        tags=["Social"],
    )
    @action(detail=False, methods=["post"], url_path="follow")
    def follow_user(self, request):
        """
        Follow another user.

        Creates a unidirectional follow relationship. The followed user's
        public activity will appear in the follower's feed.
        """
        serializer = FollowUserSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        target_user_id = serializer.validated_data["target_user_id"]

        if target_user_id == request.user.id:
            return Response(
                {"error": _("You cannot follow yourself.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            target_user = User.objects.get(id=target_user_id)
        except User.DoesNotExist:
            return Response(
                {"error": _("User not found.")}, status=status.HTTP_404_NOT_FOUND
            )

        # Check if either user has blocked the other
        if BlockedUser.objects.filter(
            Q(blocker=request.user, blocked=target_user)
            | Q(blocker=target_user, blocked=request.user)
        ).exists():
            return Response(
                {"error": _("Cannot follow this user.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if UserFollow.objects.filter(
            follower=request.user, following=target_user
        ).exists():
            return Response(
                {"error": _("You are already following this user.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        UserFollow.objects.create(follower=request.user, following=target_user)

        return Response(
            {
                "message": _("Now following %(name)s.")
                % {"name": target_user.display_name or _("user")}
            },
            status=status.HTTP_201_CREATED,
        )

    @extend_schema(
        summary="Unfollow a user",
        description="Stop following another user.",
        responses={
            200: OpenApiResponse(description="Successfully unfollowed."),
            404: OpenApiResponse(description="Follow relationship not found."),
        },
        tags=["Social"],
    )
    @action(
        detail=False, methods=["delete"], url_path=r"unfollow/(?P<user_id>[0-9a-f-]+)"
    )
    def unfollow_user(self, request, user_id=None):
        """Remove a follow relationship with the given user."""
        deleted_count, _detail = UserFollow.objects.filter(
            follower=request.user, following_id=user_id
        ).delete()

        if deleted_count == 0:
            return Response(
                {"error": _("You are not following this user.")},
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response({"message": _("Successfully unfollowed.")})

    @extend_schema(
        summary="Remove friend",
        description="Remove an existing friendship.",
        responses={
            200: OpenApiResponse(description="Friend removed."),
            404: OpenApiResponse(description="Friendship not found."),
        },
        tags=["Social"],
    )
    @action(
        detail=False,
        methods=["delete"],
        url_path=r"friends/remove/(?P<user_id>[0-9a-f-]+)",
    )
    def remove_friend(self, request, user_id=None):
        """Remove a friendship with the given user."""
        friendship = Friendship.objects.filter(
            Q(user1=request.user, user2_id=user_id)
            | Q(user1_id=user_id, user2=request.user),
            status="accepted",
        ).first()

        if not friendship:
            return Response(
                {"error": _("Friendship not found.")}, status=status.HTTP_404_NOT_FOUND
            )

        friendship.delete()
        return Response({"message": _("Friend removed.")})

    @extend_schema(
        summary="Sent friend requests",
        description="Retrieve friend requests sent by the current user.",
        responses={200: FriendRequestSerializer(many=True)},
        tags=["Social"],
    )
    @action(detail=False, methods=["get"], url_path="friends/requests/sent")
    def sent_requests(self, request):
        """List pending friend requests sent by the current user."""
        requests_qs = (
            Friendship.objects.filter(user1=request.user, status="pending")
            .select_related("user2")
            .order_by("-created_at")
        )

        # Reuse FriendRequestSerializer but the "sender" here is the receiver
        data = []
        for fr in requests_qs:
            receiver = fr.user2
            data.append(
                {
                    "id": fr.id,
                    "receiver": {
                        "id": str(receiver.id),
                        "username": receiver.display_name or "Anonymous",
                        "avatar": receiver.get_effective_avatar_url(),
                        "current_level": receiver.level,
                        "influence_score": receiver.xp,
                    },
                    "status": fr.status,
                    "created_at": fr.created_at,
                }
            )

        return Response(data)

    @extend_schema(
        summary="Block a user",
        description="Block another user. Removes existing friendships and follows.",
        request=BlockUserSerializer,
        responses={
            201: OpenApiResponse(description="User blocked."),
            400: OpenApiResponse(
                description="Cannot block yourself or already blocked."
            ),
            404: OpenApiResponse(description="Resource not found."),
        },
        tags=["Social"],
    )
    @action(detail=False, methods=["post"], url_path="block")
    def block_user(self, request):
        """
        Block a user. Also removes any existing friendship and follow
        relationships in both directions.
        """
        serializer = BlockUserSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        target_user_id = serializer.validated_data["target_user_id"]
        reason = serializer.validated_data.get("reason", "")

        if target_user_id == request.user.id:
            return Response(
                {"error": _("You cannot block yourself.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            target_user = User.objects.get(id=target_user_id)
        except User.DoesNotExist:
            return Response(
                {"error": _("User not found.")}, status=status.HTTP_404_NOT_FOUND
            )

        if BlockedUser.objects.filter(
            blocker=request.user, blocked=target_user
        ).exists():
            return Response(
                {"error": _("User is already blocked.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        BlockedUser.objects.create(
            blocker=request.user,
            blocked=target_user,
            reason=reason,
        )

        # Remove any existing friendships
        Friendship.objects.filter(
            Q(user1=request.user, user2=target_user)
            | Q(user1=target_user, user2=request.user)
        ).delete()

        # Remove follows in both directions
        UserFollow.objects.filter(
            Q(follower=request.user, following=target_user)
            | Q(follower=target_user, following=request.user)
        ).delete()

        return Response({"message": _("User blocked.")}, status=status.HTTP_201_CREATED)

    @extend_schema(
        summary="Unblock a user",
        description="Unblock a previously blocked user.",
        responses={
            200: OpenApiResponse(description="User unblocked."),
            404: OpenApiResponse(description="Block not found."),
        },
        tags=["Social"],
    )
    @action(
        detail=False, methods=["delete"], url_path=r"unblock/(?P<user_id>[0-9a-f-]+)"
    )
    def unblock_user(self, request, user_id=None):
        """Remove a block on the given user."""
        deleted_count, _detail = BlockedUser.objects.filter(
            blocker=request.user, blocked_id=user_id
        ).delete()

        if deleted_count == 0:
            return Response(
                {"error": _("Block not found.")}, status=status.HTTP_404_NOT_FOUND
            )

        return Response({"message": _("User unblocked.")})

    @extend_schema(
        summary="List blocked users",
        description="Get list of users blocked by the current user.",
        responses={200: BlockedUserSerializer(many=True)},
        tags=["Social"],
    )
    @action(detail=False, methods=["get"], url_path="blocked")
    def list_blocked(self, request):
        """List all users blocked by the current user."""
        blocked = (
            BlockedUser.objects.filter(blocker=request.user)
            .select_related("blocked")
            .order_by("-created_at")
        )

        serializer = BlockedUserSerializer(blocked, many=True)
        return Response(serializer.data)

    @extend_schema(
        summary="Report a user",
        description="Report a user for moderation review.",
        request=ReportUserSerializer,
        responses={
            201: OpenApiResponse(description="Report submitted."),
            400: OpenApiResponse(description="Cannot report yourself."),
            404: OpenApiResponse(description="Resource not found."),
        },
        tags=["Social"],
    )
    @action(detail=False, methods=["post"], url_path="report")
    def report_user(self, request):
        """Submit a user report for moderation."""
        serializer = ReportUserSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        target_user_id = serializer.validated_data["target_user_id"]

        if target_user_id == request.user.id:
            return Response(
                {"error": _("You cannot report yourself.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            target_user = User.objects.get(id=target_user_id)
        except User.DoesNotExist:
            return Response(
                {"error": _("User not found.")}, status=status.HTTP_404_NOT_FOUND
            )

        ReportedUser.objects.create(
            reporter=request.user,
            reported=target_user,
            reason=serializer.validated_data["reason"],
            category=serializer.validated_data.get("category", "other"),
        )

        return Response(
            {
                "message": _(
                    "Report submitted. Thank you for helping keep our community safe."
                )
            },
            status=status.HTTP_201_CREATED,
        )

    @extend_schema(
        summary="Mutual friends",
        description="Get mutual friends between the current user and another user.",
        responses={
            200: FriendSerializer(many=True),
            404: OpenApiResponse(description="Resource not found."),
        },
        tags=["Social"],
    )
    @action(
        detail=False,
        methods=["get"],
        url_path=r"friends/mutual/(?P<user_id>[0-9a-f-]+)",
    )
    def mutual_friends(self, request, user_id=None):
        """Get friends that the current user and target user have in common."""
        try:
            target_user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response(
                {"error": _("User not found.")}, status=status.HTTP_404_NOT_FOUND
            )

        # Get current user's friend IDs
        my_friend_ids = set()
        my_friendships = Friendship.objects.filter(
            Q(user1=request.user) | Q(user2=request.user), status="accepted"
        )
        for f in my_friendships:
            my_friend_ids.add(
                f.user2_id if f.user1_id == request.user.id else f.user1_id
            )

        # Get target user's friend IDs
        their_friend_ids = set()
        their_friendships = Friendship.objects.filter(
            Q(user1=target_user) | Q(user2=target_user), status="accepted"
        )
        for f in their_friendships:
            their_friend_ids.add(
                f.user2_id if f.user1_id == target_user.id else f.user1_id
            )

        # Intersection
        mutual_ids = my_friend_ids & their_friend_ids
        mutual_users = User.objects.filter(id__in=mutual_ids)

        friends = [self._get_friend_data(u) for u in mutual_users]
        serializer = FriendSerializer(friends, many=True)
        return Response(serializer.data)

    @extend_schema(
        summary="Cancel friend request",
        description="Cancel a pending friend request sent by the current user.",
        responses={
            200: OpenApiResponse(description="Friend request cancelled."),
            404: OpenApiResponse(description="Request not found."),
        },
        tags=["Social"],
    )
    @action(
        detail=False,
        methods=["delete"],
        url_path=r"friends/cancel/(?P<request_id>[0-9a-f-]+)",
    )
    def cancel_request(self, request, request_id=None):
        """Cancel a pending friend request sent by the current user."""
        try:
            friendship = Friendship.objects.get(
                id=request_id, user1=request.user, status="pending"
            )
        except Friendship.DoesNotExist:
            return Response(
                {"error": _("Friend request not found.")},
                status=status.HTTP_404_NOT_FOUND,
            )

        friendship.delete()
        return Response({"message": _("Friend request cancelled.")})

    @extend_schema(
        summary="Online friends",
        description="Get friends who are currently online or recently active.",
        responses={200: FriendSerializer(many=True)},
        tags=["Social"],
    )
    @action(detail=False, methods=["get"], url_path="friends/online")
    def online_friends(self, request):
        """Get friends who are online or were active in the last 5 minutes."""
        from datetime import timedelta

        from django.utils import timezone as tz

        friendships = Friendship.objects.filter(
            Q(user1=request.user) | Q(user2=request.user), status="accepted"
        ).select_related("user1", "user2")

        threshold = tz.now() - timedelta(minutes=5)
        online = []
        for friendship in friendships:
            friend_user = (
                friendship.user2
                if friendship.user1_id == request.user.id
                else friendship.user1
            )
            if friend_user.is_online or (
                friend_user.last_seen and friend_user.last_seen >= threshold
            ):
                data = self._get_friend_data(friend_user)
                data["is_online"] = friend_user.is_online
                data["last_seen"] = friend_user.last_seen
                online.append(data)

        return Response(online)

    @extend_schema(
        summary="Follower and following counts",
        description="Get follower and following counts for a user.",
        tags=["Social"],
        responses={
            200: OpenApiResponse(description="Counts returned."),
            404: OpenApiResponse(description="Resource not found."),
        },
    )
    @action(detail=False, methods=["get"], url_path=r"counts/(?P<user_id>[0-9a-f-]+)")
    def social_counts(self, request, user_id=None):
        """Get follower count, following count, and friend count for a user."""
        try:
            target_user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response(
                {"error": _("User not found.")}, status=status.HTTP_404_NOT_FOUND
            )

        # Return 404 if blocked in either direction
        if BlockedUser.objects.filter(
            Q(blocker=request.user, blocked=target_user)
            | Q(blocker=target_user, blocked=request.user)
        ).exists():
            return Response(
                {"error": _("User not found.")},
                status=status.HTTP_404_NOT_FOUND,
            )

        follower_count = UserFollow.objects.filter(following=target_user).count()
        following_count = UserFollow.objects.filter(follower=target_user).count()
        friend_count = Friendship.objects.filter(
            Q(user1=target_user) | Q(user2=target_user), status="accepted"
        ).count()

        return Response(
            {
                "follower_count": follower_count,
                "following_count": following_count,
                "friend_count": friend_count,
            }
        )


class ActivityFeedView(generics.ListAPIView):
    """
    View for retrieving the friends activity feed.

    Shows activity items from the user's friends and followed users,
    ordered by most recent first.
    Free users only see encouragement-type activities.
    """

    permission_classes = [IsAuthenticated]
    serializer_class = ActivityFeedItemSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return ActivityFeedItem.objects.none()

        user = self.request.user

        # Free users only see encouragements received
        if user.subscription == "free":
            return (
                ActivityFeedItem.objects.filter(
                    Q(user=user),
                    activity_type="encouragement",
                )
                .select_related("user")
                .order_by("-created_at")
            )

        # Get friend IDs (accepted friendships) — 2 queries instead of loading all objects
        friend_ids = set(
            Friendship.objects.filter(user1=user, status="accepted").values_list(
                "user2_id", flat=True
            )
        ) | set(
            Friendship.objects.filter(user2=user, status="accepted").values_list(
                "user1_id", flat=True
            )
        )

        # Get followed user IDs
        followed_ids = set(
            UserFollow.objects.filter(follower=user).values_list(
                "following_id", flat=True
            )
        )

        # Exclude blocked users (both directions)
        blocked_by_user = set(
            BlockedUser.objects.filter(blocker=user).values_list(
                "blocked_id", flat=True
            )
        )
        blocked_user_by = set(
            BlockedUser.objects.filter(blocked=user).values_list(
                "blocker_id", flat=True
            )
        )
        excluded_ids = blocked_by_user | blocked_user_by

        # Combine friends and followed users
        all_ids = (friend_ids | followed_ids) - excluded_ids
        all_ids.add(user.id)  # Include own activity

        qs = (
            ActivityFeedItem.objects.filter(user_id__in=all_ids)
            .select_related("user")
            .order_by("-created_at")
        )

        # Exclude activity items that reference private dreams from other users
        dream_types = {"task_completed", "dream_completed", "milestone_reached"}
        from apps.dreams.models import Dream

        private_dream_ids = set(
            Dream.objects.filter(
                is_public=False,
                user_id__in=all_ids,
            )
            .exclude(
                user=user,
            )
            .values_list("id", flat=True)
        )
        if private_dream_ids:
            pass

            # Exclude items from other users whose content references a private dream
            private_id_strs = {str(did) for did in private_dream_ids}
            # Filter in Python for JSON content — can't do JSON lookup efficiently in all DBs
            qs_ids_to_exclude = []
            for item in (
                qs.filter(activity_type__in=dream_types)
                .exclude(user=user)
                .only("id", "content", "data")
            ):
                dream_id_str = (item.content or {}).get("dream_id") or (
                    item.data or {}
                ).get("dream_id", "")
                if dream_id_str and str(dream_id_str) in private_id_strs:
                    qs_ids_to_exclude.append(item.id)
            if qs_ids_to_exclude:
                qs = qs.exclude(id__in=qs_ids_to_exclude)

        # Apply optional filters
        activity_type = self.request.query_params.get("activity_type")
        if activity_type:
            qs = qs.filter(activity_type=activity_type)

        created_after = self.request.query_params.get("created_after")
        if created_after:
            qs = qs.filter(created_at__gte=created_after)

        created_before = self.request.query_params.get("created_before")
        if created_before:
            qs = qs.filter(created_at__lte=created_before)

        return qs

    @extend_schema(
        summary="Friends activity feed",
        description=(
            "Retrieve activity feed from friends and followed users. "
            "Shows recent activities like task completions, dream achievements, and milestones. "
            "Supports filtering by activity_type, created_after, and created_before query params."
        ),
        parameters=[
            OpenApiParameter(
                name="activity_type",
                type=str,
                location=OpenApiParameter.QUERY,
                required=False,
                description="Filter by activity type (e.g. task_completed, dream_completed).",
            ),
            OpenApiParameter(
                name="created_after",
                type=str,
                location=OpenApiParameter.QUERY,
                required=False,
                description="Filter activities created after this datetime (ISO 8601).",
            ),
            OpenApiParameter(
                name="created_before",
                type=str,
                location=OpenApiParameter.QUERY,
                required=False,
                description="Filter activities created before this datetime (ISO 8601).",
            ),
        ],
        tags=["Social"],
    )
    def list(self, request, *args, **kwargs):
        """Return the activity feed for the current user's social circle."""
        queryset = self.get_queryset()

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            response = self.get_paginated_response(serializer.data)
            response.data["activities"] = response.data.pop("results")
            return response

        serializer = self.get_serializer(queryset, many=True)
        return Response({"activities": serializer.data})


class UserSearchView(generics.ListAPIView):
    """
    View for searching users by display name or email.

    Returns matching users with their friendship/follow status
    relative to the requesting user.
    """

    queryset = User.objects.none()
    permission_classes = [IsAuthenticated]
    serializer_class = UserSearchResultSerializer

    @extend_schema(
        summary="Search users",
        description="Search for users by display name. Returns matching users with friendship/follow status.",
        parameters=[
            OpenApiParameter(
                name="q",
                type=str,
                location=OpenApiParameter.QUERY,
                description="Search query (minimum 2 characters).",
                required=True,
            ),
        ],
        tags=["Social"],
    )
    def list(self, request, *args, **kwargs):
        """
        Search for users by display name.

        Returns matching users with isFriend and isFollowing flags.
        Excludes the current user from results.
        Paginated via LimitOffsetPagination (default).
        """
        query = request.query_params.get("q", "").strip()
        if len(query) < 2:
            return Response({"count": 0, "next": None, "previous": None, "results": []})

        # Get blocked user IDs (both directions)
        blocked_ids = set()
        blocks = BlockedUser.objects.filter(
            Q(blocker=request.user) | Q(blocked=request.user)
        ).values_list("blocker_id", "blocked_id")
        for blocker_id, blocked_id in blocks:
            blocked_ids.add(blocker_id)
            blocked_ids.add(blocked_id)
        blocked_ids.discard(request.user.id)

        # Elasticsearch-backed search (display_name is encrypted, can't use DB icontains)
        from apps.search.services import SearchService

        matching_user_ids = SearchService.search_users(query)

        users_qs = (
            User.objects.filter(id__in=matching_user_ids, is_active=True)
            .exclude(id=request.user.id)
            .exclude(id__in=blocked_ids)
        )

        # Paginate the queryset (respects ?limit= and ?offset=)
        page = self.paginate_queryset(users_qs)
        users_page = page if page is not None else users_qs[:20]

        # Pre-fetch friendship and follow status — 3 queries instead of loading all objects
        friend_ids = set(
            Friendship.objects.filter(
                user1=request.user, status="accepted"
            ).values_list("user2_id", flat=True)
        ) | set(
            Friendship.objects.filter(
                user2=request.user, status="accepted"
            ).values_list("user1_id", flat=True)
        )

        pending_ids = set(
            Friendship.objects.filter(user1=request.user, status="pending").values_list(
                "user2_id", flat=True
            )
        ) | set(
            Friendship.objects.filter(user2=request.user, status="pending").values_list(
                "user1_id", flat=True
            )
        )

        following_ids = set(
            UserFollow.objects.filter(follower=request.user).values_list(
                "following_id", flat=True
            )
        )

        results = []
        for user in users_page:
            level = user.level
            if level >= 50:
                title = "Legend"
            elif level >= 30:
                title = "Master"
            elif level >= 20:
                title = "Expert"
            elif level >= 10:
                title = "Achiever"
            elif level >= 5:
                title = "Explorer"
            else:
                title = "Dreamer"

            results.append(
                {
                    "id": user.id,
                    "username": user.display_name or "Anonymous",
                    "avatar": user.get_effective_avatar_url(),
                    "title": title,
                    "influence_score": user.xp,
                    "current_level": user.level,
                    "is_friend": user.id in friend_ids,
                    "is_pending_request": user.id in pending_ids,
                    "is_following": user.id in following_ids,
                }
            )

        serializer = UserSearchResultSerializer(results, many=True)
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)


class FollowSuggestionsView(generics.ListAPIView):
    """
    View for suggesting users to follow. Requires premium+ subscription.

    Suggestions are based on:
    - Users in shared circles
    - Mutual friends
    - Users with similar dream categories
    """

    queryset = User.objects.none()
    permission_classes = [IsAuthenticated, CanUseSocialFeed]
    serializer_class = UserSearchResultSerializer
    pagination_class = None  # bounded by scoring algorithm (top 20)

    @extend_schema(
        summary="Follow suggestions",
        description=(
            "Get suggested users to follow based on shared circles, "
            "mutual friends, and similar dream categories."
        ),
        tags=["Social"],
        responses={
            200: UserSearchResultSerializer(many=True),
            403: OpenApiResponse(description="Subscription required."),
        },
    )
    def list(self, request, *args, **kwargs):
        user = request.user

        # Get IDs the user already follows or is friends with
        following_ids = set(
            UserFollow.objects.filter(follower=user).values_list(
                "following_id", flat=True
            )
        )
        friend_ids = set(
            Friendship.objects.filter(user1=user, status="accepted").values_list(
                "user2_id", flat=True
            )
        ) | set(
            Friendship.objects.filter(user2=user, status="accepted").values_list(
                "user1_id", flat=True
            )
        )

        # Get blocked IDs
        blocked_ids = set(
            BlockedUser.objects.filter(blocker=user).values_list(
                "blocked_id", flat=True
            )
        ) | set(
            BlockedUser.objects.filter(blocked=user).values_list(
                "blocker_id", flat=True
            )
        )

        exclude_ids = following_ids | friend_ids | blocked_ids | {user.id}

        # Strategy 1: Users in shared circles
        from apps.circles.models import CircleMembership

        user_circle_ids = CircleMembership.objects.filter(user=user).values_list(
            "circle_id", flat=True
        )

        circle_user_ids = set(
            CircleMembership.objects.filter(circle_id__in=user_circle_ids)
            .exclude(user_id__in=exclude_ids)
            .values_list("user_id", flat=True)
        )

        # Strategy 2: Friends of friends (mutual friends) — single batch query
        limited_friend_ids = list(friend_ids)[:20]
        fof_friendships = Friendship.objects.filter(
            Q(user1_id__in=limited_friend_ids) | Q(user2_id__in=limited_friend_ids),
            status="accepted",
        )
        fof_ids = set()
        for f in fof_friendships:
            for uid in (f.user1_id, f.user2_id):
                if uid not in exclude_ids:
                    fof_ids.add(uid)

        # Strategy 3: Users with similar dream categories
        from apps.dreams.models import Dream

        user_categories = set(
            Dream.objects.filter(user=user, status="active").values_list(
                "category", flat=True
            )
        )
        similar_category_ids = set()
        if user_categories:
            similar_category_ids = set(
                Dream.objects.filter(category__in=user_categories, status="active")
                .exclude(user_id__in=exclude_ids)
                .values_list("user_id", flat=True)[:50]
            )

        # Combine and rank (circle members > fof > similar categories)
        from collections import Counter

        score = Counter()
        for uid in circle_user_ids:
            score[uid] += 3
        for uid in fof_ids:
            score[uid] += 2
        for uid in similar_category_ids:
            score[uid] += 1

        # Get top 20 suggestions
        top_ids = [uid for uid, _ in score.most_common(20)]
        suggested_users = User.objects.filter(id__in=top_ids, is_active=True)

        # Build ordered list
        user_map = {u.id: u for u in suggested_users}
        results = []
        for uid in top_ids:
            u = user_map.get(uid)
            if not u:
                continue
            level = u.level
            if level >= 50:
                title = "Legend"
            elif level >= 30:
                title = "Master"
            elif level >= 20:
                title = "Expert"
            elif level >= 10:
                title = "Achiever"
            elif level >= 5:
                title = "Explorer"
            else:
                title = "Dreamer"

            # Check pending status for suggestions
            is_pending = Friendship.objects.filter(
                Q(user1=user, user2=u) | Q(user1=u, user2=user), status="pending"
            ).exists()

            results.append(
                {
                    "id": u.id,
                    "username": u.display_name or "Anonymous",
                    "avatar": u.get_effective_avatar_url(),
                    "title": title,
                    "influence_score": u.xp,
                    "current_level": u.level,
                    "is_friend": False,
                    "is_pending_request": is_pending,
                    "is_following": False,
                }
            )

        serializer = UserSearchResultSerializer(results, many=True)
        return Response(serializer.data)


class FeedLikeView(APIView):
    """Toggle a like on an activity feed item."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Like a feed activity",
        description="Toggle a like on an activity feed item. If already liked, the like is removed.",
        tags=["Social"],
        request=None,
        responses={
            200: inline_serializer(
                name="FeedLikeResponse",
                fields={
                    "liked": drf_serializers.BooleanField(),
                    "like_count": drf_serializers.IntegerField(),
                },
            ),
            404: OpenApiResponse(description="Activity not found."),
        },
    )
    def post(self, request, activity_id):
        try:
            activity = ActivityFeedItem.objects.get(id=activity_id)
        except ActivityFeedItem.DoesNotExist:
            return Response(
                {"error": _("Activity not found.")},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Check block status — blocked users should not interact
        if BlockedUser.objects.filter(
            Q(blocker=request.user, blocked=activity.user)
            | Q(blocker=activity.user, blocked=request.user)
        ).exists():
            return Response(
                {"error": _("Activity not found.")},
                status=status.HTTP_404_NOT_FOUND,
            )

        like, created = ActivityLike.objects.get_or_create(
            user=request.user,
            activity=activity,
        )

        if not created:
            # Already liked — toggle off
            like.delete()
            liked = False
        else:
            liked = True

        like_count = ActivityLike.objects.filter(activity=activity).count()
        return Response({"liked": liked, "like_count": like_count})


class FeedCommentView(APIView):
    """Add a comment to an activity feed item."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Comment on a feed activity",
        description="Add a comment to an activity feed item.",
        tags=["Social"],
        request=inline_serializer(
            name="FeedCommentRequest",
            fields={"text": drf_serializers.CharField()},
        ),
        responses={
            201: inline_serializer(
                name="FeedCommentResponse",
                fields={
                    "id": drf_serializers.UUIDField(),
                    "text": drf_serializers.CharField(),
                    "user": drf_serializers.DictField(),
                    "created_at": drf_serializers.DateTimeField(),
                },
            ),
            400: OpenApiResponse(description="Text is required."),
            404: OpenApiResponse(description="Activity not found."),
        },
    )
    def post(self, request, activity_id):
        from core.sanitizers import sanitize_text

        try:
            activity = ActivityFeedItem.objects.get(id=activity_id)
        except ActivityFeedItem.DoesNotExist:
            return Response(
                {"error": _("Activity not found.")},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Check block status — blocked users should not interact
        if BlockedUser.objects.filter(
            Q(blocker=request.user, blocked=activity.user)
            | Q(blocker=activity.user, blocked=request.user)
        ).exists():
            return Response(
                {"error": _("Activity not found.")},
                status=status.HTTP_404_NOT_FOUND,
            )

        text = request.data.get("text", "").strip()
        if not text:
            return Response(
                {"error": _("text is required.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        text = sanitize_text(text)

        comment = ActivityComment.objects.create(
            user=request.user,
            activity=activity,
            text=text,
        )

        return Response(
            {
                "id": comment.id,
                "text": comment.text,
                "user": {
                    "id": str(request.user.id),
                    "username": request.user.display_name or "Anonymous",
                    "avatar": request.user.get_effective_avatar_url(),
                },
                "created_at": comment.created_at,
            },
            status=status.HTTP_201_CREATED,
        )


class RecentSearchViewSet(viewsets.GenericViewSet):
    """CRUD for recent search queries."""

    queryset = RecentSearch.objects.none()
    permission_classes = [IsAuthenticated]
    serializer_class = UserSearchResultSerializer

    @extend_schema(
        summary="List recent searches",
        description="Get the user's recent search queries.",
        tags=["Social"],
    )
    @action(detail=False, methods=["get"], url_path="list")
    def list_searches(self, request):
        """Return up to 20 recent searches."""
        searches = RecentSearch.objects.filter(user=request.user)[:20]
        data = [
            {
                "id": str(s.id),
                "query": s.query,
                "search_type": s.search_type,
                "created_at": s.created_at,
            }
            for s in searches
        ]
        return Response(data)

    @extend_schema(
        summary="Record a search",
        description="Record a recent search query.",
        tags=["Social"],
    )
    @action(detail=False, methods=["post"], url_path="add")
    def add_search(self, request):
        """Record a search query."""
        query = request.data.get("query", "").strip()
        search_type = request.data.get("search_type", "all")
        if not query:
            return Response(
                {"error": _("query is required.")}, status=status.HTTP_400_BAD_REQUEST
            )

        # Avoid duplicates — delete older same query
        RecentSearch.objects.filter(user=request.user, query=query).delete()
        RecentSearch.objects.create(
            user=request.user, query=query, search_type=search_type
        )

        # Keep only 20 most recent
        old_ids = (
            RecentSearch.objects.filter(user=request.user)
            .order_by("-created_at")
            .values_list("id", flat=True)[20:]
        )
        RecentSearch.objects.filter(id__in=list(old_ids)).delete()

        return Response(
            {"message": _("Search recorded.")}, status=status.HTTP_201_CREATED
        )

    @extend_schema(
        summary="Clear recent searches",
        description="Delete all recent searches for the current user.",
        tags=["Social"],
    )
    @action(detail=False, methods=["delete"], url_path="clear")
    def clear_searches(self, request):
        """Clear all recent searches."""
        RecentSearch.objects.filter(user=request.user).delete()
        return Response({"message": _("Recent searches cleared.")})

    @extend_schema(
        summary="Remove a recent search",
        description="Delete a single recent search by its ID.",
        tags=["Social"],
        responses={
            200: OpenApiResponse(description="Search removed."),
            404: OpenApiResponse(description="Search not found."),
        },
    )
    @action(detail=False, methods=["delete"], url_path=r"(?P<pk>[0-9a-f-]+)/remove")
    def remove_search(self, request, pk=None):
        """Delete a single recent search by ID."""
        try:
            search = RecentSearch.objects.get(id=pk, user=request.user)
        except RecentSearch.DoesNotExist:
            return Response(
                {"error": _("Search not found.")},
                status=status.HTTP_404_NOT_FOUND,
            )

        search.delete()
        return Response({"message": _("Search removed.")})


class DreamPostViewSet(viewsets.ModelViewSet):
    """
    Social dream posts: feed, CRUD, like, comment, encourage, share.

    All endpoints live under /api/social/posts/.
    The main social feed is at /api/social/posts/feed/.
    """

    permission_classes = [IsAuthenticated]
    serializer_class = DreamPostSerializer

    def _get_blocked_ids(self, user):
        """Get set of user IDs blocked in either direction."""
        blocked_ids = set()
        blocked_qs = BlockedUser.objects.filter(
            Q(blocker=user) | Q(blocked=user)
        ).values_list("blocker_id", "blocked_id")
        for blocker_id, blocked_id in blocked_qs:
            if blocker_id != user.id:
                blocked_ids.add(blocker_id)
            if blocked_id != user.id:
                blocked_ids.add(blocked_id)
        return blocked_ids

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return DreamPost.objects.none()
        user = self.request.user
        blocked_ids = self._get_blocked_ids(user)

        # Get followed user IDs for followers-only visibility
        followed_ids = set(
            UserFollow.objects.filter(follower=user).values_list(
                "following_id", flat=True
            )
        )

        # User can see: own posts, public posts, followers-only posts from people they follow
        return (
            DreamPost.objects.filter(
                Q(user=user)
                | Q(visibility="public")
                | Q(visibility="followers", user_id__in=followed_ids)
            )
            .exclude(
                user_id__in=blocked_ids,
            )
            .exclude(
                # Hide posts linked to dreams that are no longer public
                Q(dream__isnull=False)
                & Q(dream__is_public=False)
                & ~Q(user=user)
            )
            .select_related("user", "dream")
            .order_by("-created_at")
        )

    def get_serializer_class(self):
        if self.action == "create":
            return DreamPostCreateSerializer
        return DreamPostSerializer

    def create(self, request, *args, **kwargs):
        """Create a new dream post with optional media and event."""
        serializer = DreamPostCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        # Validate dream ownership and public status if provided
        dream = None
        dream_id = data.get("dream_id")
        if dream_id:
            from apps.dreams.models import Dream

            try:
                dream = Dream.objects.get(id=dream_id, user=request.user)
            except Dream.DoesNotExist:
                return Response(
                    {"error": _("Dream not found.")},
                    status=status.HTTP_404_NOT_FOUND,
                )
            if not dream.is_public:
                return Response(
                    {
                        "error": _("Dream must be public to be shared in a post."),
                        "code": "dream_not_public",
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # Validate linked achievement items
        linked_goal = None
        linked_milestone = None
        linked_task = None
        if data.get("linked_goal_id"):
            from apps.dreams.models import Goal

            try:
                linked_goal = Goal.objects.get(
                    id=data["linked_goal_id"],
                    dream__user=request.user,
                )
            except Goal.DoesNotExist:
                return Response(
                    {"error": _("Goal not found.")},
                    status=status.HTTP_404_NOT_FOUND,
                )
        if data.get("linked_milestone_id"):
            from apps.dreams.models import DreamMilestone

            try:
                linked_milestone = DreamMilestone.objects.get(
                    id=data["linked_milestone_id"],
                    dream__user=request.user,
                )
            except DreamMilestone.DoesNotExist:
                return Response(
                    {"error": _("Milestone not found.")},
                    status=status.HTTP_404_NOT_FOUND,
                )
        if data.get("linked_task_id"):
            from apps.dreams.models import Task

            try:
                linked_task = Task.objects.get(
                    id=data["linked_task_id"],
                    dream__user=request.user,
                )
            except Task.DoesNotExist:
                return Response(
                    {"error": _("Task not found.")},
                    status=status.HTTP_404_NOT_FOUND,
                )

        # Determine media type
        media_type = "none"
        if data.get("image_file") or data.get("image_url"):
            media_type = "image"
        elif data.get("video_file"):
            media_type = "video"
        elif data.get("audio_file"):
            media_type = "audio"

        post = DreamPost.objects.create(
            user=request.user,
            dream=dream,
            content=data["content"],
            image_url=data.get("image_url", ""),
            image_file=data.get("image_file") or "",
            video_file=data.get("video_file") or "",
            audio_file=data.get("audio_file") or "",
            media_type=media_type,
            post_type=data.get("post_type", "regular"),
            linked_goal=linked_goal,
            linked_milestone=linked_milestone,
            linked_task=linked_task,
            gofundme_url=data.get("gofundme_url", ""),
            visibility=data.get("visibility", "public"),
        )

        # Create linked event if post_type is 'event'
        if data.get("post_type") == "event":
            SocialEvent.objects.create(
                creator=request.user,
                post=post,
                title=data["event_title"],
                description=data.get("event_description", ""),
                event_type=data["event_type"],
                location=data.get("event_location", ""),
                meeting_link=data.get("event_meeting_link", ""),
                start_time=data["event_start_time"],
                end_time=data["event_end_time"],
                max_participants=data.get("event_max_participants"),
                cover_image=data.get("event_cover_image") or "",
                challenge_description=data.get("event_challenge_description", ""),
                dream=dream,
            )

        return Response(
            DreamPostSerializer(post, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )

    def perform_update(self, serializer):
        """Verify ownership before updating."""
        instance = serializer.instance if hasattr(serializer, "instance") else self.get_object()
        if instance.user != self.request.user:
            raise PermissionDenied(_("You can only edit your own posts."))

    def update(self, request, *args, **kwargs):
        """Edit own post. Only content, visibility, post_type, gofundme_url are editable."""
        post = self.get_object()
        if post.user != request.user:
            raise PermissionDenied(_("You can only edit your own posts."))

        from core.sanitizers import sanitize_text

        content = request.data.get("content")
        if content:
            post.content = sanitize_text(content)

        gofundme_url = request.data.get("gofundme_url")
        if gofundme_url is not None:
            from core.sanitizers import sanitize_url

            post.gofundme_url = sanitize_url(gofundme_url)

        visibility = request.data.get("visibility")
        if visibility in ("public", "followers", "private"):
            post.visibility = visibility

        post_type = request.data.get("post_type")
        if post_type in ("regular", "achievement", "milestone", "event"):
            post.post_type = post_type

        post.save()
        return Response(
            DreamPostSerializer(post, context={"request": request}).data,
        )

    def partial_update(self, request, *args, **kwargs):
        return self.update(request, *args, **kwargs)

    def perform_destroy(self, instance):
        """Verify ownership before deleting."""
        if instance.user != self.request.user:
            raise PermissionDenied(_("You can only delete your own posts."))
        instance.delete()

    def destroy(self, request, *args, **kwargs):
        """Delete own post."""
        post = self.get_object()
        if post.user != request.user:
            raise PermissionDenied(_("You can only delete your own posts."))
        post.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(
        summary="Social feed",
        description=(
            "Main social feed with tiered algorithm: "
            "Tier 1 (friends), Tier 2 (friends-of-friends), "
            "Tier 3 (follows + trending). Excludes blocked users and own posts."
        ),
        responses={200: DreamPostSerializer(many=True)},
        tags=["Social Feed"],
    )
    @action(detail=False, methods=["get"])
    def feed(self, request):
        """
        Main social feed with 3-tier algorithm.

        Tier 1 — Friends (highest priority):
          Posts from accepted friends, all visibility except 'private'.

        Tier 2 — Friends of friends (2nd degree):
          Public posts only. Capped at 500 2nd-degree user IDs.

        Tier 3 — Follows + Trending:
          Public posts from followed users (not in T1/T2) +
          high-engagement public posts from last 7 days.

        Interleave: ~8 T1, ~4 T2, ~3 T3 per page of 15.
        Always exclude: blocked users, own posts, private posts from non-owners.
        """
        user = request.user
        PAGE_SIZE = 15

        # ── Blocked users ──────────────────────────────────────────
        blocked_ids = self._get_blocked_ids(user)

        # ── Tier 1: Friends ────────────────────────────────────────
        friend_ids = set(
            Friendship.objects.filter(
                user1=user, status="accepted"
            ).values_list("user2_id", flat=True)
        ) | set(
            Friendship.objects.filter(
                user2=user, status="accepted"
            ).values_list("user1_id", flat=True)
        )
        friend_ids -= blocked_ids

        # ── Tier 2: Friends of friends ─────────────────────────────
        # Get friends of T1 users, excluding self, T1, and blocked
        fof_ids = set()
        if friend_ids:
            fof_from_user1 = set(
                Friendship.objects.filter(
                    user1_id__in=friend_ids, status="accepted"
                ).values_list("user2_id", flat=True)
            )
            fof_from_user2 = set(
                Friendship.objects.filter(
                    user2_id__in=friend_ids, status="accepted"
                ).values_list("user1_id", flat=True)
            )
            fof_ids = (fof_from_user1 | fof_from_user2) - friend_ids - blocked_ids - {user.id}
            # Cap at 500 IDs
            if len(fof_ids) > 500:
                fof_ids = set(list(fof_ids)[:500])

        # ── Tier 3: Follows (excluding T1 and T2) ─────────────────
        followed_ids = set(
            UserFollow.objects.filter(follower=user).values_list(
                "following_id", flat=True
            )
        )
        t3_follow_ids = followed_ids - friend_ids - fof_ids - blocked_ids - {user.id}

        # ── Common annotations ─────────────────────────────────────
        def _annotate_posts(qs):
            return qs.annotate(
                _user_has_liked=Exists(
                    DreamPostLike.objects.filter(post=OuterRef("pk"), user=user)
                ),
                _user_has_saved=Exists(
                    SavedPost.objects.filter(post=OuterRef("pk"), user=user)
                ),
                _user_has_encouraged=Exists(
                    DreamEncouragement.objects.filter(post=OuterRef("pk"), user=user)
                ),
                _user_reaction_type=Subquery(
                    PostReaction.objects.filter(
                        post=OuterRef("pk"),
                        user=user,
                    ).values("reaction_type")[:1]
                ),
                _user_is_following=Exists(
                    UserFollow.objects.filter(
                        follower=user, following_id=OuterRef("user_id")
                    )
                ),
            )

        # ── Base exclusions (always) ───────────────────────────────
        base_exclude = blocked_ids | {user.id}

        # ── Build tier querysets ───────────────────────────────────
        # T1: friends, all visibility except private
        t1_qs = DreamPost.objects.none()
        if friend_ids:
            t1_qs = (
                DreamPost.objects.filter(user_id__in=friend_ids)
                .exclude(visibility="private")
                .exclude(user_id__in=base_exclude)
                .select_related("user", "dream")
                .order_by("-created_at")
            )

        # T2: friends-of-friends, public only
        t2_qs = DreamPost.objects.none()
        if fof_ids:
            t2_qs = (
                DreamPost.objects.filter(user_id__in=fof_ids, visibility="public")
                .exclude(user_id__in=base_exclude)
                .select_related("user", "dream")
                .order_by("-created_at")
            )

        # T3: followed users (not in T1/T2) + trending public posts from last 7 days
        t3_follow_qs = DreamPost.objects.none()
        if t3_follow_ids:
            t3_follow_qs = (
                DreamPost.objects.filter(user_id__in=t3_follow_ids, visibility="public")
                .exclude(user_id__in=base_exclude)
                .select_related("user", "dream")
                .order_by("-created_at")
            )

        seven_days_ago = timezone.now() - timedelta(days=7)
        all_known_ids = friend_ids | fof_ids | t3_follow_ids | base_exclude
        t3_trending_qs = (
            DreamPost.objects.filter(
                visibility="public",
                created_at__gte=seven_days_ago,
            )
            .exclude(user_id__in=all_known_ids)
            .select_related("user", "dream")
            .order_by("-likes_count", "-comments_count", "-created_at")
        )

        # ── Fetch and interleave ───────────────────────────────────
        # Target distribution per page: ~8 T1, ~4 T2, ~3 T3
        t1_target = 8
        t2_target = 4
        t3_target = 3

        t1_posts = list(_annotate_posts(t1_qs[:t1_target * 2]))
        t2_posts = list(_annotate_posts(t2_qs[:t2_target * 2]))
        t3_follow_posts = list(_annotate_posts(t3_follow_qs[:t3_target * 2]))
        t3_trending_posts = list(_annotate_posts(t3_trending_qs[:t3_target * 2]))

        # Take up to targets from each tier
        t1_take = t1_posts[:t1_target]
        t2_take = t2_posts[:t2_target]
        t3_take = t3_follow_posts[:t3_target]

        # Fill remaining from trending if follows didn't provide enough
        t3_remaining = t3_target - len(t3_take)
        if t3_remaining > 0:
            # Avoid duplicates
            t3_take_ids = {p.id for p in t3_take}
            for tp in t3_trending_posts:
                if tp.id not in t3_take_ids:
                    t3_take.append(tp)
                    t3_take_ids.add(tp.id)
                    if len(t3_take) >= t3_target:
                        break

        # Fill shortfalls: if any tier is short, fill from others
        total_collected = len(t1_take) + len(t2_take) + len(t3_take)
        deficit = PAGE_SIZE - total_collected

        if deficit > 0:
            # Collect remaining posts from all tiers
            used_ids = {p.id for p in t1_take} | {p.id for p in t2_take} | {p.id for p in t3_take}
            fill_pool = []
            for pool in [t1_posts, t2_posts, t3_follow_posts, t3_trending_posts]:
                for p in pool:
                    if p.id not in used_ids:
                        fill_pool.append(p)
                        used_ids.add(p.id)
            t3_take.extend(fill_pool[:deficit])

        # ── Interleave: T1, T1, T2, T1, T3, T1, T2, T1, ... ──────
        merged = []
        t1_iter = iter(t1_take)
        t2_iter = iter(t2_take)
        t3_iter = iter(t3_take)

        # Pattern per 15: T1 T1 T2 T1 T1 T3 T1 T1 T2 T1 T3 T1 T2 T1 T3
        pattern = [1, 1, 2, 1, 1, 3, 1, 1, 2, 1, 3, 1, 2, 1, 3]
        iters = {1: t1_iter, 2: t2_iter, 3: t3_iter}
        fallback_order = {1: [2, 3], 2: [1, 3], 3: [2, 1]}

        seen_ids = set()
        for tier_num in pattern:
            added = False
            # Try primary tier first, then fallbacks
            for try_tier in [tier_num] + fallback_order[tier_num]:
                post = next(iters[try_tier], None)
                if post and post.id not in seen_ids:
                    merged.append(post)
                    seen_ids.add(post.id)
                    added = True
                    break
            if not added:
                # All tiers exhausted for this slot
                continue

        # ── Serialize and return ───────────────────────────────────
        serializer = DreamPostSerializer(
            merged, many=True, context={"request": request}
        )
        return Response(serializer.data)

    @extend_schema(
        summary="Like/unlike a post",
        description="Toggle like on a dream post.",
        tags=["Social Feed"],
        responses={200: dict},
    )
    @action(detail=True, methods=["post"])
    def like(self, request, pk=None):
        """Toggle like on a post."""
        post = self.get_object()
        like, created = DreamPostLike.objects.get_or_create(
            post=post,
            user=request.user,
        )

        if created:
            DreamPost.objects.filter(id=post.id).update(
                likes_count=F("likes_count") + 1
            )
            # Create notification
            self._notify_post_owner(
                post,
                request.user,
                title=_("%(name)s liked your dream post")
                % {"name": request.user.display_name or _("Someone")},
            )
            return Response({"liked": True, "likes_count": post.likes_count + 1})
        else:
            like.delete()
            DreamPost.objects.filter(id=post.id).update(
                likes_count=F("likes_count") - 1
            )
            return Response(
                {"liked": False, "likes_count": max(0, post.likes_count - 1)}
            )

    @extend_schema(
        summary="React to a post",
        description="Toggle an emoji reaction on a dream post. Same reaction removes it, different reaction changes it.",
        tags=["Social Feed"],
        responses={200: dict},
    )
    @action(detail=True, methods=["post"])
    def react(self, request, pk=None):
        """Toggle emoji reaction on a post."""
        post = self.get_object()
        reaction_type = request.data.get("reaction_type", "like")

        valid_types = [t[0] for t in PostReaction.REACTION_TYPES]
        if reaction_type not in valid_types:
            return Response(
                {
                    "error": _("reaction_type must be one of: %(types)s")
                    % {"types": ", ".join(valid_types)}
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        existing = PostReaction.objects.filter(user=request.user, post=post).first()
        if existing:
            if existing.reaction_type == reaction_type:
                existing.delete()
                counts = (
                    PostReaction.objects.filter(post=post)
                    .values("reaction_type")
                    .annotate(count=Count("id"))
                )
                return Response(
                    {
                        "reacted": False,
                        "reaction_type": None,
                        "counts": {c["reaction_type"]: c["count"] for c in counts},
                    }
                )
            existing.reaction_type = reaction_type
            existing.save()
        else:
            PostReaction.objects.create(
                user=request.user,
                post=post,
                reaction_type=reaction_type,
            )
            self._notify_post_owner(
                post,
                request.user,
                title=_("%(name)s reacted to your dream post")
                % {
                    "name": request.user.display_name or _("Someone"),
                },
            )

        counts = (
            PostReaction.objects.filter(post=post)
            .values("reaction_type")
            .annotate(count=Count("id"))
        )
        return Response(
            {
                "reacted": True,
                "reaction_type": reaction_type,
                "counts": {c["reaction_type"]: c["count"] for c in counts},
            }
        )

    @extend_schema(
        summary="Comment on a post",
        description="Add a comment to a dream post.",
        tags=["Social Feed"],
        responses={201: DreamPostCommentSerializer},
    )
    @action(detail=True, methods=["post"])
    def comment(self, request, pk=None):
        """Add a comment to a post."""
        post = self.get_object()
        content = request.data.get("content", "").strip()
        if not content:
            return Response(
                {"error": _("content is required.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        from core.sanitizers import sanitize_text

        content = sanitize_text(content)

        parent_id = request.data.get("parent_id")
        parent = None
        if parent_id:
            try:
                parent = DreamPostComment.objects.get(id=parent_id, post=post)
            except DreamPostComment.DoesNotExist:
                return Response(
                    {"error": _("Parent comment not found.")},
                    status=status.HTTP_404_NOT_FOUND,
                )

        comment = DreamPostComment.objects.create(
            post=post,
            user=request.user,
            content=content,
            parent=parent,
        )

        DreamPost.objects.filter(id=post.id).update(
            comments_count=F("comments_count") + 1
        )

        self._notify_post_owner(
            post,
            request.user,
            title=_("%(name)s commented on your post")
            % {"name": request.user.display_name or _("Someone")},
        )

        return Response(
            DreamPostCommentSerializer(comment, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )

    @extend_schema(
        summary="List comments on a post",
        description="Get paginated comments for a dream post.",
        tags=["Social Feed"],
        responses={200: DreamPostCommentSerializer(many=True)},
    )
    @action(detail=True, methods=["get"])
    def comments(self, request, pk=None):
        """List comments on a post."""
        post = self.get_object()
        # Get top-level comments (replies are nested in serializer)
        qs = (
            DreamPostComment.objects.filter(
                post=post,
                parent__isnull=True,
            )
            .select_related("user")
            .order_by("-created_at")
        )

        page = self.paginate_queryset(qs)
        if page is not None:
            serializer = DreamPostCommentSerializer(
                page, many=True, context={"request": request}
            )
            return self.get_paginated_response(serializer.data)

        serializer = DreamPostCommentSerializer(
            qs, many=True, context={"request": request}
        )
        return Response(serializer.data)

    @extend_schema(
        summary="Encourage a post",
        description="Send encouragement with a type (you_got_this, keep_going, etc).",
        tags=["Social Feed"],
        responses={201: DreamEncouragementSerializer},
    )
    @action(detail=True, methods=["post"])
    def encourage(self, request, pk=None):
        """Send encouragement to a post."""
        post = self.get_object()
        encouragement_type = request.data.get("encouragement_type", "you_got_this")
        message = request.data.get("message", "")

        valid_types = [t[0] for t in DreamEncouragement.ENCOURAGEMENT_TYPES]
        if encouragement_type not in valid_types:
            return Response(
                {
                    "error": _("encouragement_type must be one of: %(types)s")
                    % {"types": ", ".join(valid_types)}
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if message:
            from core.sanitizers import sanitize_text

            message = sanitize_text(message)

        encouragement, created = DreamEncouragement.objects.update_or_create(
            post=post,
            user=request.user,
            defaults={
                "encouragement_type": encouragement_type,
                "message": message,
            },
        )

        if created:
            type_display = dict(DreamEncouragement.ENCOURAGEMENT_TYPES).get(
                encouragement_type, encouragement_type
            )
            self._notify_post_owner(
                post,
                request.user,
                title=_("%(name)s encouraged you: %(type)s")
                % {
                    "name": request.user.display_name or _("Someone"),
                    "type": type_display,
                },
            )

        return Response(
            DreamEncouragementSerializer(encouragement).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    @extend_schema(
        summary="Share/repost a dream post",
        description="Share a post to your own followers by creating a new post referencing the original.",
        tags=["Social Feed"],
        responses={201: DreamPostSerializer},
    )
    @action(detail=True, methods=["post"])
    def share(self, request, pk=None):
        """Share/repost to own followers."""
        original_post = self.get_object()
        content = request.data.get("content", "")
        if content:
            from core.sanitizers import sanitize_text

            content = sanitize_text(content)

        share_content = content or f"Shared: {original_post.content[:200]}"

        new_post = DreamPost.objects.create(
            user=request.user,
            dream=original_post.dream,
            content=share_content,
            image_url=original_post.image_url,
            gofundme_url=original_post.gofundme_url,
            visibility="public",
        )

        DreamPost.objects.filter(id=original_post.id).update(
            shares_count=F("shares_count") + 1
        )

        return Response(
            DreamPostSerializer(new_post, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )

    @extend_schema(
        summary="User's posts",
        description="Get posts by a specific user.",
        tags=["Social Feed"],
        responses={200: DreamPostSerializer(many=True)},
    )
    @action(detail=False, methods=["get"], url_path=r"user/(?P<user_id>[0-9a-f-]+)")
    def user_posts(self, request, user_id=None):
        """Get posts by a specific user."""
        try:
            target_user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response(
                {"error": _("User not found.")},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Check if blocked
        if BlockedUser.is_blocked(request.user, target_user):
            return Response(
                {"error": _("Cannot view this user.")},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Determine visibility
        is_following = UserFollow.objects.filter(
            follower=request.user, following=target_user
        ).exists()

        posts = DreamPost.objects.filter(user=target_user)
        if target_user != request.user:
            if is_following:
                posts = posts.filter(visibility__in=["public", "followers"])
            else:
                posts = posts.filter(visibility="public")

        posts = posts.select_related("user", "dream").order_by("-created_at")

        page = self.paginate_queryset(posts)
        if page is not None:
            serializer = DreamPostSerializer(
                page, many=True, context={"request": request}
            )
            return self.get_paginated_response(serializer.data)

        serializer = DreamPostSerializer(posts, many=True, context={"request": request})
        return Response(serializer.data)

    @extend_schema(
        summary="Save/unsave a post",
        description="Toggle bookmark on a dream post.",
        tags=["Social Feed"],
        responses={200: dict},
    )
    @action(detail=True, methods=["post"])
    def save(self, request, pk=None):
        """Toggle bookmark/save on a post."""
        post = self.get_object()
        existing = SavedPost.objects.filter(user=request.user, post=post).first()
        if existing:
            existing.delete()
            DreamPost.objects.filter(id=post.id).update(
                saves_count=F("saves_count") - 1
            )
            return Response(
                {"saved": False, "saves_count": max(0, post.saves_count - 1)}
            )
        else:
            SavedPost.objects.create(user=request.user, post=post)
            DreamPost.objects.filter(id=post.id).update(
                saves_count=F("saves_count") + 1
            )
            return Response({"saved": True, "saves_count": post.saves_count + 1})

    @extend_schema(
        summary="List saved posts",
        description="Return all posts bookmarked by the current user.",
        tags=["Social Feed"],
        responses={200: DreamPostSerializer(many=True)},
    )
    @action(detail=False, methods=["get"])
    def saved(self, request):
        """List all posts saved/bookmarked by the current user."""
        saved_post_ids = (
            SavedPost.objects.filter(
                user=request.user,
            )
            .order_by("-created_at")
            .values_list("post_id", flat=True)
        )
        saved_posts = (
            DreamPost.objects.filter(
                id__in=saved_post_ids,
            )
            .select_related("user", "dream")
            .order_by("-created_at")
        )
        page = self.paginate_queryset(saved_posts)
        if page is not None:
            serializer = DreamPostSerializer(
                page, many=True, context={"request": request}
            )
            return self.get_paginated_response(serializer.data)
        serializer = DreamPostSerializer(
            saved_posts, many=True, context={"request": request}
        )
        return Response(serializer.data)

    def _notify_post_owner(self, post, actor, title):
        """Create a notification for the post owner."""
        if post.user == actor:
            return  # Don't notify yourself
        try:
            from django.utils import timezone

            from apps.notifications.models import Notification

            Notification.objects.create(
                user=post.user,
                notification_type="social",
                title=title,
                body="",
                scheduled_for=timezone.now(),
                data={
                    "post_id": str(post.id),
                    "actor_id": str(actor.id),
                    "type": "social",
                },
            )
        except Exception:
            logger.debug("Failed to create social notification", exc_info=True)


class SocialEventViewSet(viewsets.ModelViewSet):
    """
    Social events: CRUD, register/unregister, participants.

    All endpoints live under /api/social/events/.
    """

    permission_classes = [IsAuthenticated]
    serializer_class = SocialEventSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return SocialEvent.objects.none()
        user = self.request.user
        # Exclude events from blocked users
        blocked_ids = set()
        blocked_qs = BlockedUser.objects.filter(
            Q(blocker=user) | Q(blocked=user)
        ).values_list("blocker_id", "blocked_id")
        for blocker_id, blocked_id in blocked_qs:
            if blocker_id != user.id:
                blocked_ids.add(blocker_id)
            if blocked_id != user.id:
                blocked_ids.add(blocked_id)
        return (
            SocialEvent.objects.exclude(
                creator_id__in=blocked_ids,
            )
            .select_related(
                "creator",
                "dream",
                "post",
            )
            .order_by("-created_at")
        )

    def retrieve(self, request, *args, **kwargs):
        """Retrieve event — strip meeting_link for non-participants."""
        event = self.get_object()
        data = SocialEventSerializer(event, context={"request": request}).data
        # Only show meeting_link to creator or registered participants
        is_participant = (
            event.creator == request.user
            or SocialEventRegistration.objects.filter(
                event=event,
                user=request.user,
                status="registered",
            ).exists()
        )
        if not is_participant:
            data.pop("meeting_link", None)
        return Response(data)

    def get_serializer_class(self):
        if self.action == "create":
            return SocialEventCreateSerializer
        return SocialEventSerializer

    @extend_schema(
        summary="Create event",
        description="Create a standalone social event (not linked to a post).",
        tags=["Social Events"],
        responses={201: SocialEventSerializer},
    )
    def create(self, request, *args, **kwargs):
        """Create a new social event."""
        serializer = SocialEventCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        dream = None
        if data.get("dream_id"):
            from apps.dreams.models import Dream

            try:
                dream = Dream.objects.get(id=data["dream_id"], user=request.user)
            except Dream.DoesNotExist:
                return Response(
                    {"error": _("Dream not found.")},
                    status=status.HTTP_404_NOT_FOUND,
                )

        event = SocialEvent.objects.create(
            creator=request.user,
            title=data["title"],
            description=data.get("description", ""),
            event_type=data["event_type"],
            location=data.get("location", ""),
            meeting_link=data.get("meeting_link", ""),
            start_time=data["start_time"],
            end_time=data["end_time"],
            max_participants=data.get("max_participants"),
            cover_image=data.get("cover_image") or "",
            challenge_description=data.get("challenge_description", ""),
            dream=dream,
        )

        return Response(
            SocialEventSerializer(event, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )

    def update(self, request, *args, **kwargs):
        """Edit own event."""
        event = self.get_object()
        if event.creator != request.user:
            return Response(
                {"error": _("You can only edit your own events.")},
                status=status.HTTP_403_FORBIDDEN,
            )

        from core.sanitizers import sanitize_text

        for field in ("title", "description", "challenge_description"):
            val = request.data.get(field)
            if val is not None:
                setattr(event, field, sanitize_text(val))

        for field in (
            "location",
            "meeting_link",
            "start_time",
            "end_time",
            "max_participants",
            "event_type",
            "status",
        ):
            val = request.data.get(field)
            if val is not None:
                setattr(event, field, val)

        event.save()
        return Response(
            SocialEventSerializer(event, context={"request": request}).data,
        )

    def partial_update(self, request, *args, **kwargs):
        return self.update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        """Cancel own event (soft delete)."""
        event = self.get_object()
        if event.creator != request.user:
            return Response(
                {"error": _("You can only cancel your own events.")},
                status=status.HTTP_403_FORBIDDEN,
            )
        event.status = "cancelled"
        event.save(update_fields=["status", "updated_at"])
        return Response(
            SocialEventSerializer(event, context={"request": request}).data,
        )

    @extend_schema(
        summary="Register for event",
        description="Register the current user for a social event.",
        tags=["Social Events"],
        responses={200: dict},
    )
    @action(detail=True, methods=["post"])
    def register(self, request, pk=None):
        """Register for an event."""
        event = self.get_object()

        if event.status in ("cancelled", "completed"):
            return Response(
                {"error": _("Cannot register for a cancelled or completed event.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Atomic capacity check
        from django.db import transaction

        with transaction.atomic():
            locked_event = SocialEvent.objects.select_for_update().get(id=event.id)
            if (
                locked_event.max_participants is not None
                and locked_event.participants_count >= locked_event.max_participants
            ):
                return Response(
                    {"error": _("Event is full.")},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            reg, created = SocialEventRegistration.objects.get_or_create(
                event=locked_event,
                user=request.user,
                defaults={"status": "registered"},
            )
            if not created and reg.status == "cancelled":
                reg.status = "registered"
                reg.save(update_fields=["status"])
                created = True  # treat as new registration

            if created:
                SocialEvent.objects.filter(id=event.id).update(
                    participants_count=F("participants_count") + 1
                )

        return Response(
            {
                "registered": True,
                "participants_count": locked_event.participants_count
                + (1 if created else 0),
            }
        )

    @extend_schema(
        summary="Unregister from event",
        description="Cancel registration for a social event.",
        tags=["Social Events"],
        responses={200: dict},
    )
    @action(detail=True, methods=["post"])
    def unregister(self, request, pk=None):
        """Cancel registration for an event."""
        event = self.get_object()

        try:
            reg = SocialEventRegistration.objects.get(
                event=event,
                user=request.user,
                status="registered",
            )
        except SocialEventRegistration.DoesNotExist:
            return Response(
                {"error": _("Not registered for this event.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        reg.status = "cancelled"
        reg.save(update_fields=["status"])
        SocialEvent.objects.filter(id=event.id).update(
            participants_count=F("participants_count") - 1
        )

        return Response(
            {
                "registered": False,
                "participants_count": max(0, event.participants_count - 1),
            }
        )

    @extend_schema(
        summary="Event participants",
        description="List registered participants for an event.",
        tags=["Social Events"],
        responses={200: SocialEventRegistrationSerializer(many=True)},
    )
    @action(detail=True, methods=["get"])
    def participants(self, request, pk=None):
        """List participants of an event."""
        event = self.get_object()
        regs = (
            SocialEventRegistration.objects.filter(
                event=event,
                status="registered",
            )
            .select_related("user")
            .order_by("-registered_at")
        )

        page = self.paginate_queryset(regs)
        if page is not None:
            serializer = SocialEventRegistrationSerializer(
                page,
                many=True,
                context={"request": request},
            )
            return self.get_paginated_response(serializer.data)

        serializer = SocialEventRegistrationSerializer(
            regs,
            many=True,
            context={"request": request},
        )
        return Response(serializer.data)

    @extend_schema(
        summary="Events feed",
        description="Upcoming events for the social feed.",
        tags=["Social Events"],
        responses={200: SocialEventSerializer(many=True)},
    )
    @action(detail=False, methods=["get"])
    def feed(self, request):
        """Get upcoming events for the feed."""
        from django.utils import timezone

        events = (
            SocialEvent.objects.filter(
                status__in=["upcoming", "active"],
                end_time__gte=timezone.now(),
            )
            .select_related("creator", "dream", "post")
            .order_by("start_time")
        )

        page = self.paginate_queryset(events)
        if page is not None:
            serializer = SocialEventSerializer(
                page,
                many=True,
                context={"request": request},
            )
            return self.get_paginated_response(serializer.data)

        serializer = SocialEventSerializer(
            events[:50],
            many=True,
            context={"request": request},
        )
        return Response(serializer.data)


# ═══════════════════════════════════════════════════════════════════
#  Stories — ephemeral media posts (24h)
# ═══════════════════════════════════════════════════════════════════


class StoryViewSet(viewsets.ModelViewSet):
    """
    ViewSet for stories (ephemeral 24h media posts).

    create   — upload a story (image or video + optional caption)
    destroy  — delete own story
    feed     — GET stories feed grouped by user
    my_stories — GET current user's active stories
    view     — POST mark a story as viewed
    viewers  — GET list of viewers for own story
    """

    permission_classes = [IsAuthenticated]
    serializer_class = StorySerializer

    def get_serializer_class(self):
        if self.action == "create":
            return StoryCreateSerializer
        return StorySerializer

    def get_queryset(self):
        from django.utils import timezone

        user = self.request.user
        now = timezone.now()

        # Build visible user set (friends + followed + self)
        friend_ids = set(
            Friendship.objects.filter(
                Q(user1=user, status="accepted") | Q(user2=user, status="accepted")
            )
            .values_list("user1_id", "user2_id")
            .distinct()
        )
        flat_friend_ids = set()
        for pair in friend_ids:
            flat_friend_ids.update(pair)
        flat_friend_ids.discard(user.id)

        followed_ids = set(
            UserFollow.objects.filter(follower=user).values_list(
                "following_id", flat=True
            )
        )

        # Blocked users (both directions)
        blocked_ids = set()
        blocked_qs = BlockedUser.objects.filter(
            Q(blocker=user) | Q(blocked=user)
        ).values_list("blocker_id", "blocked_id")
        for pair in blocked_qs:
            blocked_ids.update(pair)
        blocked_ids.discard(user.id)

        visible_user_ids = (flat_friend_ids | followed_ids | {user.id}) - blocked_ids

        return (
            Story.objects.filter(
                user_id__in=visible_user_ids,
                expires_at__gt=now,
            )
            .select_related("user")
            .order_by("-created_at")
        )

    def create(self, request, *args, **kwargs):
        """Create a new story."""
        from datetime import timedelta

        from django.utils import timezone

        from core.sanitizers import sanitize_text

        serializer = StoryCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        now = timezone.now()
        story = Story(
            user=request.user,
            caption=sanitize_text(data.get("caption", ""), 280),
            expires_at=now + timedelta(hours=24),
        )

        if data.get("image_file"):
            story.image_file = data["image_file"]
            story.media_type = "image"
        elif data.get("video_file"):
            story.video_file = data["video_file"]
            story.media_type = "video"

        story.save()

        return Response(
            StorySerializer(story, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )

    def destroy(self, request, *args, **kwargs):
        """Delete own story."""
        story = self.get_object()
        if story.user != request.user:
            return Response(
                {"error": _("You can only delete your own stories.")},
                status=status.HTTP_403_FORBIDDEN,
            )
        story.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=["get"])
    def feed(self, request):
        """
        Get stories feed grouped by user.
        Returns friends' and followed users' active stories, grouped by user.
        Current user's stories are included first.
        """
        from collections import OrderedDict

        from django.utils import timezone

        user = request.user
        now = timezone.now()

        # Get friend and followed user IDs
        friend_ids = set(
            Friendship.objects.filter(
                Q(user1=user, status="accepted") | Q(user2=user, status="accepted")
            )
            .values_list("user1_id", "user2_id")
            .distinct()
        )
        # Flatten tuples and remove self
        flat_friend_ids = set()
        for pair in friend_ids:
            flat_friend_ids.update(pair)
        flat_friend_ids.discard(user.id)

        followed_ids = set(
            UserFollow.objects.filter(follower=user).values_list(
                "following_id", flat=True
            )
        )

        # Blocked users (both directions)
        blocked_ids = set()
        blocked_qs = BlockedUser.objects.filter(
            Q(blocker=user) | Q(blocked=user)
        ).values_list("blocker_id", "blocked_id")
        for pair in blocked_qs:
            blocked_ids.update(pair)
        blocked_ids.discard(user.id)

        # All relevant user IDs (friends + followed + self)
        relevant_ids = (flat_friend_ids | followed_ids | {user.id}) - blocked_ids

        # Active stories from relevant users
        stories = (
            Story.objects.filter(
                user_id__in=relevant_ids,
                expires_at__gt=now,
            )
            .select_related("user")
            .annotate(
                _user_has_viewed=Exists(
                    StoryView.objects.filter(story=OuterRef("pk"), user=user)
                ),
            )
            .order_by("user_id", "-created_at")
        )

        # Group by user
        groups = OrderedDict()
        for story in stories:
            uid = str(story.user_id)
            if uid not in groups:
                groups[uid] = {
                    "user": {
                        "id": uid,
                        "username": story.user.display_name or "Anonymous",
                        "display_name": story.user.display_name or "Anonymous",
                        "avatar": story.user.get_effective_avatar_url(),
                    },
                    "stories": [],
                    "has_unviewed": False,
                }
            groups[uid]["stories"].append(story)
            if not story._user_has_viewed:
                groups[uid]["has_unviewed"] = True

        # Sort: current user first, then unviewed, then viewed
        my_uid = str(user.id)
        result = []
        if my_uid in groups:
            my_group = groups.pop(my_uid)
            my_group["stories"] = StorySerializer(
                my_group["stories"],
                many=True,
                context={"request": request},
            ).data
            result.append(my_group)

        # Unviewed first
        unviewed = []
        viewed = []
        for uid, group in groups.items():
            group["stories"] = StorySerializer(
                group["stories"],
                many=True,
                context={"request": request},
            ).data
            if group["has_unviewed"]:
                unviewed.append(group)
            else:
                viewed.append(group)

        result.extend(unviewed)
        result.extend(viewed)

        return Response(result)

    @action(detail=False, methods=["get"], url_path="my_stories")
    def my_stories(self, request):
        """Get current user's active stories."""
        from django.utils import timezone

        stories = Story.objects.filter(
            user=request.user,
            expires_at__gt=timezone.now(),
        ).order_by("-created_at")
        serializer = StorySerializer(stories, many=True, context={"request": request})
        return Response(serializer.data)

    @action(detail=True, methods=["post"], url_path="view")
    def mark_viewed(self, request, pk=None):
        """Mark a story as viewed."""
        story = self.get_object()
        if story.user == request.user:
            return Response({"status": "own_story"})

        _, created = StoryView.objects.get_or_create(
            story=story,
            user=request.user,
        )
        if created:
            Story.objects.filter(id=story.id).update(
                view_count=F("view_count") + 1,
            )
        return Response({"status": "viewed"})

    @action(detail=True, methods=["get"])
    def viewers(self, request, pk=None):
        """Get list of viewers for own story."""
        story = self.get_object()
        if story.user != request.user:
            return Response(
                {"error": _("You can only see viewers of your own stories.")},
                status=status.HTTP_403_FORBIDDEN,
            )
        views = (
            StoryView.objects.filter(story=story)
            .select_related("user")
            .order_by("-viewed_at")
        )
        result = []
        for v in views:
            result.append(
                {
                    "id": str(v.user.id),
                    "username": v.user.display_name or "Anonymous",
                    "avatar": v.user.get_effective_avatar_url(),
                    "viewed_at": v.viewed_at.isoformat(),
                }
            )
        return Response(result)


# ═══════════════════════════════════════════════════════════════════
#  Friend Suggestions — smart recommendation engine
# ═══════════════════════════════════════════════════════════════════


class FriendSuggestionsView(APIView):
    """
    Smart friend suggestion engine.

    Scores potential friends based on:
    - Mutual friends (40%)
    - Similar dream categories (30%)
    - Activity level & XP proximity (15%)
    - Shared circle membership (15%)

    Results are cached for 1 hour per user and returned as
    a ranked list of the top 10 candidates.
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Friend suggestions",
        description=(
            "Get smart friend suggestions scored by mutual friends, "
            "shared dream categories, activity level, and shared circles."
        ),
        tags=["Social"],
        responses={200: OpenApiResponse(description="List of friend suggestions.")},
    )
    def get(self, request):
        from collections import Counter, defaultdict
        from datetime import timedelta

        from django.core.cache import cache

        from apps.circles.models import Circle, CircleMembership
        from apps.dreams.models import Dream

        user = request.user
        cache_key = f"friend_suggestions_{user.id}"

        # Check cache first
        cached = cache.get(cache_key)
        if cached is not None:
            return Response(cached)

        # ── Build exclusion set ──────────────────────────────────
        # Already friends (accepted)
        friend_ids = set(
            Friendship.objects.filter(user1=user, status="accepted").values_list(
                "user2_id", flat=True
            )
        ) | set(
            Friendship.objects.filter(user2=user, status="accepted").values_list(
                "user1_id", flat=True
            )
        )

        # Pending requests (sent or received)
        pending_ids = set(
            Friendship.objects.filter(
                Q(user1=user) | Q(user2=user), status="pending"
            ).values_list("user1_id", flat=True)
        ) | set(
            Friendship.objects.filter(
                Q(user1=user) | Q(user2=user), status="pending"
            ).values_list("user2_id", flat=True)
        )

        # Blocked users (either direction)
        blocked_ids = set(
            BlockedUser.objects.filter(blocker=user).values_list(
                "blocked_id", flat=True
            )
        ) | set(
            BlockedUser.objects.filter(blocked=user).values_list(
                "blocker_id", flat=True
            )
        )

        exclude_ids = friend_ids | pending_ids | blocked_ids | {user.id}

        # ── 1. Mutual friends (weight: 0.40) ────────────────────
        # Find friends-of-friends
        limited_friend_ids = list(friend_ids)[:50]
        fof_friendships = Friendship.objects.filter(
            Q(user1_id__in=limited_friend_ids) | Q(user2_id__in=limited_friend_ids),
            status="accepted",
        ).values_list("user1_id", "user2_id")

        mutual_count = Counter()
        for u1, u2 in fof_friendships:
            for uid in (u1, u2):
                if uid not in exclude_ids and uid not in limited_friend_ids:
                    mutual_count[uid] += 1

        # ── 2. Similar dream categories (weight: 0.30) ──────────
        user_categories = set(
            Dream.objects.filter(user=user, status="active").values_list(
                "category", flat=True
            )
        )

        category_overlap = Counter()
        user_shared_cats = defaultdict(set)
        if user_categories:
            cat_dreams = (
                Dream.objects.filter(category__in=user_categories, status="active")
                .exclude(user_id__in=exclude_ids)
                .values_list("user_id", "category")
            )

            for uid, cat in cat_dreams:
                category_overlap[uid] += 1
                user_shared_cats[uid].add(cat)

        # ── 3. Activity level & XP proximity (weight: 0.15) ─────
        seven_days_ago = timezone.now() - timedelta(days=7)
        active_user_ids = set(
            User.objects.filter(
                last_activity__gte=seven_days_ago,
                is_active=True,
            )
            .exclude(id__in=exclude_ids)
            .values_list("id", flat=True)[:200]
        )

        # ── 4. Shared circles (weight: 0.15) ────────────────────
        user_circle_ids = list(
            CircleMembership.objects.filter(user=user).values_list(
                "circle_id", flat=True
            )
        )

        circle_members = Counter()
        user_shared_circles = defaultdict(list)
        if user_circle_ids:
            circle_name_map = dict(
                Circle.objects.filter(id__in=user_circle_ids).values_list("id", "name")
            )
            memberships = (
                CircleMembership.objects.filter(circle_id__in=user_circle_ids)
                .exclude(user_id__in=exclude_ids)
                .values_list("user_id", "circle_id")
            )

            for uid, cid in memberships:
                circle_members[uid] += 1
                cname = circle_name_map.get(cid, "")
                if cname:
                    user_shared_circles[uid].append(cname)

        # ── Combine scores ───────────────────────────────────────
        all_candidate_ids = (
            set(mutual_count.keys())
            | set(category_overlap.keys())
            | active_user_ids
            | set(circle_members.keys())
        )

        # Normalize helpers
        max_mutual = max(mutual_count.values()) if mutual_count else 1
        max_cat = max(category_overlap.values()) if category_overlap else 1
        max_circle = max(circle_members.values()) if circle_members else 1

        scored = {}
        for uid in all_candidate_ids:
            # Mutual friends score (40%)
            mutual_raw = mutual_count.get(uid, 0)
            s_mutual = (mutual_raw / max_mutual) * 0.40 if max_mutual else 0

            # Category overlap score (30%)
            cat_raw = category_overlap.get(uid, 0)
            s_cat = (cat_raw / max_cat) * 0.30 if max_cat else 0

            # Activity score (15%) — binary: active in last 7 days
            s_activity = 0.15 if uid in active_user_ids else 0

            # Circle score (15%)
            circle_raw = circle_members.get(uid, 0)
            s_circle = (circle_raw / max_circle) * 0.15 if max_circle else 0

            scored[uid] = s_mutual + s_cat + s_activity + s_circle

        # Sort by score descending, take top 10
        top_ids = sorted(scored, key=scored.get, reverse=True)[:10]

        if not top_ids:
            cache.set(cache_key, [], 3600)
            return Response([])

        # ── Build response ───────────────────────────────────────
        suggested_users = User.objects.filter(id__in=top_ids, is_active=True)
        user_map = {u.id: u for u in suggested_users}

        results = []
        for uid in top_ids:
            u = user_map.get(uid)
            if not u:
                continue

            score = round(scored[uid], 2)
            m_count = mutual_count.get(uid, 0)
            shared_cats = sorted(user_shared_cats.get(uid, set()))
            shared_circs = user_shared_circles.get(uid, [])

            # Build reasons list
            reasons = []
            if m_count > 0:
                reasons.append(f'{m_count} mutual friend{"s" if m_count != 1 else ""}')
            if shared_cats:
                cat_labels = {
                    "health": "Health",
                    "career": "Career",
                    "relationships": "Relationships",
                    "personal": "Personal Growth",
                    "finance": "Finance",
                    "hobbies": "Hobbies",
                    "education": "Education",
                    "creative": "Creative",
                    "social": "Social",
                    "travel": "Travel",
                }
                cat_names = [cat_labels.get(c, c.title()) for c in shared_cats[:3]]
                reasons.append(f'Both pursuing {" & ".join(cat_names)} goals')
            if shared_circs:
                reasons.append(f"Same circle: {shared_circs[0]}")
            if uid in active_user_ids:
                reasons.append("Active this week")

            # Level title
            level = u.level
            if level >= 50:
                title = "Legend"
            elif level >= 30:
                title = "Master"
            elif level >= 20:
                title = "Expert"
            elif level >= 10:
                title = "Achiever"
            elif level >= 5:
                title = "Explorer"
            else:
                title = "Dreamer"

            results.append(
                {
                    "user": {
                        "id": str(u.id),
                        "display_name": u.display_name or "Anonymous",
                        "avatar": u.get_effective_avatar_url(),
                        "level": u.level,
                        "title": title,
                    },
                    "score": score,
                    "reasons": reasons,
                    "mutual_friend_count": m_count,
                    "shared_categories": shared_cats,
                }
            )

        cache.set(cache_key, results, 3600)
        return Response(results)
