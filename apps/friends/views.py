"""
Views for the Friends system.

Provides API endpoints for friendship management, follows, blocks,
and reports.
"""

import logging

from django.db.models import Q
from drf_spectacular.utils import extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.users.models import User

from .models import BlockedUser, Friendship, ReportedUser, UserFollow
from .serializers import (
    BlockedUserSerializer,
    BlockUserSerializer,
    FollowUserSerializer,
    FriendshipSerializer,
    ReportUserSerializer,
    SendFriendRequestSerializer,
)

logger = logging.getLogger(__name__)


class FriendshipViewSet(viewsets.GenericViewSet):
    """
    ViewSet for friendship management.

    Supports listing friends, viewing/sending/accepting/rejecting requests,
    removing friends, following/unfollowing, blocking/unblocking, and reporting.
    """

    permission_classes = [IsAuthenticated]
    serializer_class = FriendshipSerializer

    def get_queryset(self):
        return Friendship.objects.filter(
            Q(user1=self.request.user) | Q(user2=self.request.user)
        )

    @extend_schema(
        summary="List friends",
        tags=["Friends"],
        responses={200: dict},
    )
    @action(detail=False, methods=["get"])
    def friends(self, request):
        """List accepted friends."""
        user = request.user
        friendships = Friendship.objects.filter(
            Q(user1=user) | Q(user2=user), status="accepted"
        ).select_related("user1", "user2")

        friends = []
        for f in friendships:
            friend = f.user2 if f.user1 == user else f.user1
            friends.append(
                {
                    "id": str(friend.id),
                    "display_name": friend.display_name or "",
                    "email": friend.email,
                    "avatar_url": friend.get_effective_avatar_url(),
                    "level": friend.level,
                    "streak_days": friend.streak_days,
                    "friendship_id": str(f.id),
                    "since": f.updated_at,
                }
            )

        return Response({"friends": friends, "count": len(friends)})

    @extend_schema(
        summary="Send friend request",
        tags=["Friends"],
        request=SendFriendRequestSerializer,
        responses={201: FriendshipSerializer},
    )
    @action(detail=False, methods=["post"], url_path="request")
    def send_request(self, request):
        """Send a friend request."""
        serializer = SendFriendRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        target_id = serializer.validated_data["user_id"]

        if str(request.user.id) == str(target_id):
            return Response(
                {"error": "Cannot send friend request to yourself."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            target = User.objects.get(id=target_id)
        except User.DoesNotExist:
            return Response(
                {"error": "User not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Check if blocked
        if BlockedUser.is_blocked(request.user, target):
            return Response(
                {"error": "Cannot send request to this user."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Check existing friendship
        existing = Friendship.objects.filter(
            Q(user1=request.user, user2=target) | Q(user1=target, user2=request.user)
        ).first()

        if existing:
            if existing.status == "accepted":
                return Response(
                    {"error": "Already friends."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if existing.status == "pending":
                return Response(
                    {"error": "Friend request already pending."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        friendship = Friendship.objects.create(
            user1=request.user, user2=target, status="pending"
        )
        return Response(
            FriendshipSerializer(friendship).data,
            status=status.HTTP_201_CREATED,
        )

    @extend_schema(
        summary="Accept friend request",
        tags=["Friends"],
        responses={200: FriendshipSerializer},
    )
    @action(detail=True, methods=["post"], url_path="accept")
    def accept_request(self, request, pk=None):
        """Accept a pending friend request."""
        try:
            friendship = Friendship.objects.get(
                id=pk, user2=request.user, status="pending"
            )
        except Friendship.DoesNotExist:
            return Response(
                {"error": "Friend request not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        friendship.status = "accepted"
        friendship.save(update_fields=["status", "updated_at"])
        return Response(FriendshipSerializer(friendship).data)

    @extend_schema(
        summary="Reject friend request",
        tags=["Friends"],
        responses={200: dict},
    )
    @action(detail=True, methods=["post"], url_path="reject")
    def reject_request(self, request, pk=None):
        """Reject a pending friend request."""
        try:
            friendship = Friendship.objects.get(
                id=pk, user2=request.user, status="pending"
            )
        except Friendship.DoesNotExist:
            return Response(
                {"error": "Friend request not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        friendship.status = "rejected"
        friendship.save(update_fields=["status", "updated_at"])
        return Response({"message": "Friend request rejected."})

    @extend_schema(
        summary="Remove friend",
        tags=["Friends"],
        responses={200: dict},
    )
    @action(detail=False, methods=["delete"], url_path="remove/(?P<user_id>[^/.]+)")
    def remove_friend(self, request, user_id=None):
        """Remove a friend."""
        Friendship.objects.filter(
            Q(user1=request.user, user2_id=user_id)
            | Q(user1_id=user_id, user2=request.user),
            status="accepted",
        ).delete()
        return Response({"message": "Friend removed."})

    @extend_schema(
        summary="Pending friend requests",
        tags=["Friends"],
        responses={200: dict},
    )
    @action(detail=False, methods=["get"], url_path="requests/pending")
    def pending_requests(self, request):
        """List pending received friend requests."""
        requests_qs = Friendship.objects.filter(
            user2=request.user, status="pending"
        ).select_related("user1")

        results = [
            {
                "id": str(f.id),
                "user": {
                    "id": str(f.user1.id),
                    "display_name": f.user1.display_name or "",
                    "avatar_url": f.user1.get_effective_avatar_url(),
                    "level": f.user1.level,
                },
                "created_at": f.created_at,
            }
            for f in requests_qs
        ]

        return Response({"requests": results, "count": len(results)})

    @extend_schema(
        summary="Mutual friends",
        tags=["Friends"],
        responses={200: dict},
    )
    @action(detail=False, methods=["get"], url_path="mutual/(?P<user_id>[^/.]+)")
    def mutual_friends(self, request, user_id=None):
        """Get mutual friends with another user."""
        from .services import FriendshipService

        mutual = FriendshipService.mutual_friends(request.user.id, user_id)
        return Response({"mutual_friends": mutual, "count": len(mutual)})

    @extend_schema(
        summary="Follow a user",
        tags=["Friends"],
        request=FollowUserSerializer,
        responses={201: dict},
    )
    @action(detail=False, methods=["post"], url_path="follow")
    def follow(self, request):
        """Follow a user."""
        serializer = FollowUserSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        target_id = serializer.validated_data["user_id"]

        if str(request.user.id) == str(target_id):
            return Response(
                {"error": "Cannot follow yourself."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        UserFollow.objects.get_or_create(
            follower=request.user, following_id=target_id
        )
        return Response({"message": "Followed."}, status=status.HTTP_201_CREATED)

    @extend_schema(
        summary="Unfollow a user",
        tags=["Friends"],
        responses={200: dict},
    )
    @action(detail=False, methods=["delete"], url_path="unfollow/(?P<user_id>[^/.]+)")
    def unfollow(self, request, user_id=None):
        """Unfollow a user."""
        UserFollow.objects.filter(
            follower=request.user, following_id=user_id
        ).delete()
        return Response({"message": "Unfollowed."})

    @extend_schema(
        summary="Block a user",
        tags=["Friends"],
        request=BlockUserSerializer,
        responses={201: dict},
    )
    @action(detail=False, methods=["post"], url_path="block")
    def block(self, request):
        """Block a user."""
        serializer = BlockUserSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        target_id = serializer.validated_data["user_id"]

        BlockedUser.objects.get_or_create(
            blocker=request.user,
            blocked_id=target_id,
            defaults={"reason": serializer.validated_data.get("reason", "")},
        )

        # Also remove friendship and follows
        Friendship.objects.filter(
            Q(user1=request.user, user2_id=target_id)
            | Q(user1_id=target_id, user2=request.user)
        ).delete()
        UserFollow.objects.filter(
            Q(follower=request.user, following_id=target_id)
            | Q(follower_id=target_id, following=request.user)
        ).delete()

        return Response({"message": "User blocked."}, status=status.HTTP_201_CREATED)

    @extend_schema(
        summary="Unblock a user",
        tags=["Friends"],
        responses={200: dict},
    )
    @action(detail=False, methods=["delete"], url_path="unblock/(?P<user_id>[^/.]+)")
    def unblock(self, request, user_id=None):
        """Unblock a user."""
        BlockedUser.objects.filter(
            blocker=request.user, blocked_id=user_id
        ).delete()
        return Response({"message": "User unblocked."})

    @extend_schema(
        summary="List blocked users",
        tags=["Friends"],
        responses={200: BlockedUserSerializer(many=True)},
    )
    @action(detail=False, methods=["get"], url_path="blocked")
    def blocked_list(self, request):
        """List blocked users."""
        blocked = BlockedUser.objects.filter(
            blocker=request.user
        ).select_related("blocked")
        return Response(BlockedUserSerializer(blocked, many=True).data)

    @extend_schema(
        summary="Report a user",
        tags=["Friends"],
        request=ReportUserSerializer,
        responses={201: dict},
    )
    @action(detail=False, methods=["post"], url_path="report")
    def report(self, request):
        """Report a user."""
        serializer = ReportUserSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        ReportedUser.objects.create(
            reporter=request.user,
            reported_id=serializer.validated_data["user_id"],
            reason=serializer.validated_data["reason"],
            category=serializer.validated_data.get("category", "other"),
        )
        return Response({"message": "Report submitted."}, status=status.HTTP_201_CREATED)

    @extend_schema(
        summary="Social counts",
        tags=["Friends"],
        responses={200: dict},
    )
    @action(detail=False, methods=["get"], url_path="counts/(?P<user_id>[^/.]+)")
    def counts(self, request, user_id=None):
        """Get follower/following/friend counts for a user."""
        friends_count = Friendship.objects.filter(
            Q(user1_id=user_id) | Q(user2_id=user_id), status="accepted"
        ).count()
        followers_count = UserFollow.objects.filter(following_id=user_id).count()
        following_count = UserFollow.objects.filter(follower_id=user_id).count()

        return Response(
            {
                "friends": friends_count,
                "followers": followers_count,
                "following": following_count,
            }
        )
