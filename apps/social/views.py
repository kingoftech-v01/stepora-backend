"""
Views for the Social system.

Provides API endpoints for friendships, follows, activity feeds,
and user search. All endpoints require authentication.
"""

from rest_framework import viewsets, status, generics
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Q
from core.permissions import CanUseSocialFeed
from drf_spectacular.utils import (
    extend_schema,
    extend_schema_view,
    OpenApiParameter,
    OpenApiResponse,
)

from apps.users.models import User
from rest_framework.views import APIView
from rest_framework import serializers as drf_serializers
from drf_spectacular.utils import inline_serializer

import logging
from django.db.models import F, Exists, OuterRef

from .models import (
    Friendship, UserFollow, ActivityFeedItem, ActivityLike,
    ActivityComment, BlockedUser, ReportedUser, RecentSearch,
    DreamPost, DreamPostLike, DreamPostComment, DreamEncouragement,
)
from .serializers import (
    FriendSerializer,
    FriendRequestSerializer,
    UserSearchResultSerializer,
    ActivityFeedItemSerializer,
    SendFriendRequestSerializer,
    FollowUserSerializer,
    UserPublicSerializer,
    BlockUserSerializer,
    ReportUserSerializer,
    BlockedUserSerializer,
    DreamPostSerializer,
    DreamPostCreateSerializer,
    DreamPostCommentSerializer,
    DreamEncouragementSerializer,
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
            title = 'Legend'
        elif level >= 30:
            title = 'Master'
        elif level >= 20:
            title = 'Expert'
        elif level >= 10:
            title = 'Achiever'
        elif level >= 5:
            title = 'Explorer'
        else:
            title = 'Dreamer'

        return {
            'id': user.id,
            'username': user.display_name or 'Anonymous',
            'avatar': user.avatar_url or '',
            'title': title,
            'currentLevel': user.level,
            'influenceScore': user.xp,
            'currentStreak': user.streak_days,
        }

    @extend_schema(
        summary="List friends",
        description="Retrieve the current user's accepted friends.",
        responses={200: FriendSerializer(many=True)},
        tags=["Social"],
    )
    @action(detail=False, methods=['get'], url_path='friends')
    def list_friends(self, request):
        """
        List all accepted friends of the current user.

        Returns public profile info for each friend including
        username, avatar, level, and influence score.
        """
        friendships = Friendship.objects.filter(
            Q(user1=request.user) | Q(user2=request.user),
            status='accepted'
        ).select_related('user1', 'user2')

        friends = []
        for friendship in friendships:
            friend_user = friendship.user2 if friendship.user1_id == request.user.id else friendship.user1
            friends.append(self._get_friend_data(friend_user))

        serializer = FriendSerializer(friends, many=True)
        return Response(serializer.data)

    @extend_schema(
        summary="Pending friend requests",
        description="Retrieve pending friend requests sent to the current user.",
        responses={200: FriendRequestSerializer(many=True)},
        tags=["Social"],
    )
    @action(detail=False, methods=['get'], url_path='friends/requests/pending')
    def pending_requests(self, request):
        """
        List pending friend requests received by the current user.

        Returns the sender's public info for each pending request.
        """
        requests_qs = Friendship.objects.filter(
            user2=request.user,
            status='pending'
        ).select_related('user1').order_by('-created_at')

        serializer = FriendRequestSerializer(requests_qs, many=True)
        return Response(serializer.data)

    @extend_schema(
        summary="Send friend request",
        description="Send a friend request to another user.",
        request=SendFriendRequestSerializer,
        responses={
            201: OpenApiResponse(description="Friend request sent."),
            400: OpenApiResponse(description="Cannot send request (already friends, self-request, etc.)."),
            404: OpenApiResponse(description="Resource not found."),
        },
        tags=["Social"],
    )
    @action(detail=False, methods=['post'], url_path='friends/request')
    def send_request(self, request):
        """
        Send a friend request.

        Creates a pending friendship between the current user and the
        target user. Fails if a friendship already exists or if the
        user tries to befriend themselves.
        """
        serializer = SendFriendRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        target_user_id = serializer.validated_data['target_user_id']

        # Cannot befriend yourself
        if target_user_id == request.user.id:
            return Response(
                {'error': 'You cannot send a friend request to yourself.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Check target exists
        try:
            target_user = User.objects.get(id=target_user_id)
        except User.DoesNotExist:
            return Response(
                {'error': 'User not found.'},
                status=status.HTTP_404_NOT_FOUND
            )

        # Check if either user has blocked the other
        if BlockedUser.objects.filter(
            Q(blocker=request.user, blocked=target_user) |
            Q(blocker=target_user, blocked=request.user)
        ).exists():
            return Response(
                {'error': 'Cannot send friend request to this user.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Check for existing friendship in either direction
        existing = Friendship.objects.filter(
            Q(user1=request.user, user2=target_user) |
            Q(user1=target_user, user2=request.user)
        ).first()

        if existing:
            if existing.status == 'accepted':
                return Response(
                    {'error': 'You are already friends with this user.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            elif existing.status == 'pending':
                return Response(
                    {'error': 'A friend request is already pending.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            elif existing.status == 'rejected':
                # Allow re-sending after rejection
                existing.status = 'pending'
                existing.user1 = request.user
                existing.user2 = target_user
                existing.save(update_fields=['status', 'user1', 'user2', 'updated_at'])
                return Response(
                    {'message': 'Friend request sent.'},
                    status=status.HTTP_201_CREATED
                )

        Friendship.objects.create(
            user1=request.user,
            user2=target_user,
            status='pending'
        )

        return Response(
            {'message': 'Friend request sent.'},
            status=status.HTTP_201_CREATED
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
    @action(detail=False, methods=['post'], url_path=r'friends/accept/(?P<request_id>[0-9a-f-]+)')
    def accept_request(self, request, request_id=None):
        """
        Accept a pending friend request.

        Changes the friendship status from 'pending' to 'accepted'.
        Only the recipient (user2) can accept.
        """
        try:
            friendship = Friendship.objects.get(
                id=request_id,
                user2=request.user,
                status='pending'
            )
        except Friendship.DoesNotExist:
            return Response(
                {'error': 'Friend request not found.'},
                status=status.HTTP_404_NOT_FOUND
            )

        friendship.status = 'accepted'
        friendship.save(update_fields=['status', 'updated_at'])

        return Response({'message': 'Friend request accepted.'})

    @extend_schema(
        summary="Reject friend request",
        description="Reject a pending friend request.",
        responses={
            200: OpenApiResponse(description="Friend request rejected."),
            404: OpenApiResponse(description="Request not found."),
        },
        tags=["Social"],
    )
    @action(detail=False, methods=['post'], url_path=r'friends/reject/(?P<request_id>[0-9a-f-]+)')
    def reject_request(self, request, request_id=None):
        """
        Reject a pending friend request.

        Changes the friendship status from 'pending' to 'rejected'.
        Only the recipient (user2) can reject.
        """
        try:
            friendship = Friendship.objects.get(
                id=request_id,
                user2=request.user,
                status='pending'
            )
        except Friendship.DoesNotExist:
            return Response(
                {'error': 'Friend request not found.'},
                status=status.HTTP_404_NOT_FOUND
            )

        friendship.status = 'rejected'
        friendship.save(update_fields=['status', 'updated_at'])

        return Response({'message': 'Friend request rejected.'})

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
    @action(detail=False, methods=['post'], url_path='follow')
    def follow_user(self, request):
        """
        Follow another user.

        Creates a unidirectional follow relationship. The followed user's
        public activity will appear in the follower's feed.
        """
        serializer = FollowUserSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        target_user_id = serializer.validated_data['target_user_id']

        if target_user_id == request.user.id:
            return Response(
                {'error': 'You cannot follow yourself.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            target_user = User.objects.get(id=target_user_id)
        except User.DoesNotExist:
            return Response(
                {'error': 'User not found.'},
                status=status.HTTP_404_NOT_FOUND
            )

        # Check if either user has blocked the other
        if BlockedUser.objects.filter(
            Q(blocker=request.user, blocked=target_user) |
            Q(blocker=target_user, blocked=request.user)
        ).exists():
            return Response(
                {'error': 'Cannot follow this user.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if UserFollow.objects.filter(follower=request.user, following=target_user).exists():
            return Response(
                {'error': 'You are already following this user.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        UserFollow.objects.create(
            follower=request.user,
            following=target_user
        )

        return Response(
            {'message': f'Now following {target_user.display_name or "user"}.'},
            status=status.HTTP_201_CREATED
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
    @action(detail=False, methods=['delete'], url_path=r'unfollow/(?P<user_id>[0-9a-f-]+)')
    def unfollow_user(self, request, user_id=None):
        """Remove a follow relationship with the given user."""
        deleted_count, _ = UserFollow.objects.filter(
            follower=request.user,
            following_id=user_id
        ).delete()

        if deleted_count == 0:
            return Response(
                {'error': 'You are not following this user.'},
                status=status.HTTP_404_NOT_FOUND
            )

        return Response({'message': 'Successfully unfollowed.'})

    @extend_schema(
        summary="Remove friend",
        description="Remove an existing friendship.",
        responses={
            200: OpenApiResponse(description="Friend removed."),
            404: OpenApiResponse(description="Friendship not found."),
        },
        tags=["Social"],
    )
    @action(detail=False, methods=['delete'], url_path=r'friends/remove/(?P<user_id>[0-9a-f-]+)')
    def remove_friend(self, request, user_id=None):
        """Remove a friendship with the given user."""
        friendship = Friendship.objects.filter(
            Q(user1=request.user, user2_id=user_id) |
            Q(user1_id=user_id, user2=request.user),
            status='accepted'
        ).first()

        if not friendship:
            return Response(
                {'error': 'Friendship not found.'},
                status=status.HTTP_404_NOT_FOUND
            )

        friendship.delete()
        return Response({'message': 'Friend removed.'})

    @extend_schema(
        summary="Sent friend requests",
        description="Retrieve friend requests sent by the current user.",
        responses={200: FriendRequestSerializer(many=True)},
        tags=["Social"],
    )
    @action(detail=False, methods=['get'], url_path='friends/requests/sent')
    def sent_requests(self, request):
        """List pending friend requests sent by the current user."""
        requests_qs = Friendship.objects.filter(
            user1=request.user,
            status='pending'
        ).select_related('user2').order_by('-created_at')

        # Reuse FriendRequestSerializer but the "sender" here is the receiver
        data = []
        for fr in requests_qs:
            receiver = fr.user2
            data.append({
                'id': fr.id,
                'receiver': {
                    'id': str(receiver.id),
                    'username': receiver.display_name or 'Anonymous',
                    'avatar': receiver.avatar_url or '',
                    'currentLevel': receiver.level,
                    'influenceScore': receiver.xp,
                },
                'status': fr.status,
                'created_at': fr.created_at,
            })

        return Response(data)

    @extend_schema(
        summary="Block a user",
        description="Block another user. Removes existing friendships and follows.",
        request=BlockUserSerializer,
        responses={
            201: OpenApiResponse(description="User blocked."),
            400: OpenApiResponse(description="Cannot block yourself or already blocked."),
            404: OpenApiResponse(description="Resource not found."),
        },
        tags=["Social"],
    )
    @action(detail=False, methods=['post'], url_path='block')
    def block_user(self, request):
        """
        Block a user. Also removes any existing friendship and follow
        relationships in both directions.
        """
        serializer = BlockUserSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        target_user_id = serializer.validated_data['target_user_id']
        reason = serializer.validated_data.get('reason', '')

        if target_user_id == request.user.id:
            return Response(
                {'error': 'You cannot block yourself.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            target_user = User.objects.get(id=target_user_id)
        except User.DoesNotExist:
            return Response(
                {'error': 'User not found.'},
                status=status.HTTP_404_NOT_FOUND
            )

        if BlockedUser.objects.filter(blocker=request.user, blocked=target_user).exists():
            return Response(
                {'error': 'User is already blocked.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        BlockedUser.objects.create(
            blocker=request.user,
            blocked=target_user,
            reason=reason,
        )

        # Remove any existing friendships
        Friendship.objects.filter(
            Q(user1=request.user, user2=target_user) |
            Q(user1=target_user, user2=request.user)
        ).delete()

        # Remove follows in both directions
        UserFollow.objects.filter(
            Q(follower=request.user, following=target_user) |
            Q(follower=target_user, following=request.user)
        ).delete()

        return Response(
            {'message': 'User blocked.'},
            status=status.HTTP_201_CREATED
        )

    @extend_schema(
        summary="Unblock a user",
        description="Unblock a previously blocked user.",
        responses={
            200: OpenApiResponse(description="User unblocked."),
            404: OpenApiResponse(description="Block not found."),
        },
        tags=["Social"],
    )
    @action(detail=False, methods=['delete'], url_path=r'unblock/(?P<user_id>[0-9a-f-]+)')
    def unblock_user(self, request, user_id=None):
        """Remove a block on the given user."""
        deleted_count, _ = BlockedUser.objects.filter(
            blocker=request.user,
            blocked_id=user_id
        ).delete()

        if deleted_count == 0:
            return Response(
                {'error': 'Block not found.'},
                status=status.HTTP_404_NOT_FOUND
            )

        return Response({'message': 'User unblocked.'})

    @extend_schema(
        summary="List blocked users",
        description="Get list of users blocked by the current user.",
        responses={200: BlockedUserSerializer(many=True)},
        tags=["Social"],
    )
    @action(detail=False, methods=['get'], url_path='blocked')
    def list_blocked(self, request):
        """List all users blocked by the current user."""
        blocked = BlockedUser.objects.filter(
            blocker=request.user
        ).select_related('blocked').order_by('-created_at')

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
    @action(detail=False, methods=['post'], url_path='report')
    def report_user(self, request):
        """Submit a user report for moderation."""
        serializer = ReportUserSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        target_user_id = serializer.validated_data['target_user_id']

        if target_user_id == request.user.id:
            return Response(
                {'error': 'You cannot report yourself.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            target_user = User.objects.get(id=target_user_id)
        except User.DoesNotExist:
            return Response(
                {'error': 'User not found.'},
                status=status.HTTP_404_NOT_FOUND
            )

        ReportedUser.objects.create(
            reporter=request.user,
            reported=target_user,
            reason=serializer.validated_data['reason'],
            category=serializer.validated_data.get('category', 'other'),
        )

        return Response(
            {'message': 'Report submitted. Thank you for helping keep our community safe.'},
            status=status.HTTP_201_CREATED
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
    @action(detail=False, methods=['get'], url_path=r'friends/mutual/(?P<user_id>[0-9a-f-]+)')
    def mutual_friends(self, request, user_id=None):
        """Get friends that the current user and target user have in common."""
        try:
            target_user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response(
                {'error': 'User not found.'},
                status=status.HTTP_404_NOT_FOUND
            )

        # Get current user's friend IDs
        my_friend_ids = set()
        my_friendships = Friendship.objects.filter(
            Q(user1=request.user) | Q(user2=request.user),
            status='accepted'
        )
        for f in my_friendships:
            my_friend_ids.add(f.user2_id if f.user1_id == request.user.id else f.user1_id)

        # Get target user's friend IDs
        their_friend_ids = set()
        their_friendships = Friendship.objects.filter(
            Q(user1=target_user) | Q(user2=target_user),
            status='accepted'
        )
        for f in their_friendships:
            their_friend_ids.add(f.user2_id if f.user1_id == target_user.id else f.user1_id)

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
    @action(detail=False, methods=['delete'], url_path=r'friends/cancel/(?P<request_id>[0-9a-f-]+)')
    def cancel_request(self, request, request_id=None):
        """Cancel a pending friend request sent by the current user."""
        try:
            friendship = Friendship.objects.get(
                id=request_id,
                user1=request.user,
                status='pending'
            )
        except Friendship.DoesNotExist:
            return Response(
                {'error': 'Friend request not found.'},
                status=status.HTTP_404_NOT_FOUND
            )

        friendship.delete()
        return Response({'message': 'Friend request cancelled.'})

    @extend_schema(
        summary="Online friends",
        description="Get friends who are currently online or recently active.",
        responses={200: FriendSerializer(many=True)},
        tags=["Social"],
    )
    @action(detail=False, methods=['get'], url_path='friends/online')
    def online_friends(self, request):
        """Get friends who are online or were active in the last 5 minutes."""
        from datetime import timedelta
        from django.utils import timezone as tz

        friendships = Friendship.objects.filter(
            Q(user1=request.user) | Q(user2=request.user),
            status='accepted'
        ).select_related('user1', 'user2')

        threshold = tz.now() - timedelta(minutes=5)
        online = []
        for friendship in friendships:
            friend_user = friendship.user2 if friendship.user1_id == request.user.id else friendship.user1
            if friend_user.is_online or (friend_user.last_seen and friend_user.last_seen >= threshold):
                data = self._get_friend_data(friend_user)
                data['is_online'] = friend_user.is_online
                data['last_seen'] = friend_user.last_seen
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
    @action(detail=False, methods=['get'], url_path=r'counts/(?P<user_id>[0-9a-f-]+)')
    def social_counts(self, request, user_id=None):
        """Get follower count, following count, and friend count for a user."""
        try:
            target_user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response(
                {'error': 'User not found.'},
                status=status.HTTP_404_NOT_FOUND
            )

        follower_count = UserFollow.objects.filter(following=target_user).count()
        following_count = UserFollow.objects.filter(follower=target_user).count()
        friend_count = Friendship.objects.filter(
            Q(user1=target_user) | Q(user2=target_user),
            status='accepted'
        ).count()

        return Response({
            'follower_count': follower_count,
            'following_count': following_count,
            'friend_count': friend_count,
        })


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
        if getattr(self, 'swagger_fake_view', False):
            return ActivityFeedItem.objects.none()

        user = self.request.user

        # Free users only see encouragements received
        if user.subscription == 'free':
            return ActivityFeedItem.objects.filter(
                Q(user=user),
                activity_type='encouragement',
            ).select_related('user').order_by('-created_at')

        # Get friend IDs (accepted friendships) — 2 queries instead of loading all objects
        friend_ids = set(
            Friendship.objects.filter(user1=user, status='accepted').values_list('user2_id', flat=True)
        ) | set(
            Friendship.objects.filter(user2=user, status='accepted').values_list('user1_id', flat=True)
        )

        # Get followed user IDs
        followed_ids = set(
            UserFollow.objects.filter(
                follower=user
            ).values_list('following_id', flat=True)
        )

        # Exclude blocked users (both directions)
        blocked_by_user = set(
            BlockedUser.objects.filter(blocker=user).values_list('blocked_id', flat=True)
        )
        blocked_user_by = set(
            BlockedUser.objects.filter(blocked=user).values_list('blocker_id', flat=True)
        )
        excluded_ids = blocked_by_user | blocked_user_by

        # Combine friends and followed users
        all_ids = (friend_ids | followed_ids) - excluded_ids
        all_ids.add(user.id)  # Include own activity

        qs = ActivityFeedItem.objects.filter(
            user_id__in=all_ids
        ).select_related('user').order_by('-created_at')

        # Apply optional filters
        activity_type = self.request.query_params.get('activity_type')
        if activity_type:
            qs = qs.filter(activity_type=activity_type)

        created_after = self.request.query_params.get('created_after')
        if created_after:
            qs = qs.filter(created_at__gte=created_after)

        created_before = self.request.query_params.get('created_before')
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
            OpenApiParameter(name='activity_type', type=str, location=OpenApiParameter.QUERY, required=False,
                             description='Filter by activity type (e.g. task_completed, dream_completed).'),
            OpenApiParameter(name='created_after', type=str, location=OpenApiParameter.QUERY, required=False,
                             description='Filter activities created after this datetime (ISO 8601).'),
            OpenApiParameter(name='created_before', type=str, location=OpenApiParameter.QUERY, required=False,
                             description='Filter activities created before this datetime (ISO 8601).'),
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
            response.data['activities'] = response.data.pop('results')
            return response

        serializer = self.get_serializer(queryset, many=True)
        return Response({'activities': serializer.data})


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
                name='q',
                type=str,
                location=OpenApiParameter.QUERY,
                description='Search query (minimum 2 characters).',
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
        query = request.query_params.get('q', '').strip()
        if len(query) < 2:
            return Response({'count': 0, 'next': None, 'previous': None, 'results': []})

        # Get blocked user IDs (both directions)
        blocked_ids = set()
        blocks = BlockedUser.objects.filter(
            Q(blocker=request.user) | Q(blocked=request.user)
        ).values_list('blocker_id', 'blocked_id')
        for blocker_id, blocked_id in blocks:
            blocked_ids.add(blocker_id)
            blocked_ids.add(blocked_id)
        blocked_ids.discard(request.user.id)

        # Elasticsearch-backed search (display_name is encrypted, can't use DB icontains)
        from apps.search.services import SearchService
        matching_user_ids = SearchService.search_users(query)

        users_qs = User.objects.filter(
            id__in=matching_user_ids,
            is_active=True
        ).exclude(
            id=request.user.id
        ).exclude(
            id__in=blocked_ids
        )

        # Paginate the queryset (respects ?limit= and ?offset=)
        page = self.paginate_queryset(users_qs)
        users_page = page if page is not None else users_qs[:20]

        # Pre-fetch friendship and follow status — 2 queries instead of loading all objects
        friend_ids = set(
            Friendship.objects.filter(user1=request.user, status='accepted').values_list('user2_id', flat=True)
        ) | set(
            Friendship.objects.filter(user2=request.user, status='accepted').values_list('user1_id', flat=True)
        )

        following_ids = set(
            UserFollow.objects.filter(
                follower=request.user
            ).values_list('following_id', flat=True)
        )

        results = []
        for user in users_page:
            level = user.level
            if level >= 50:
                title = 'Legend'
            elif level >= 30:
                title = 'Master'
            elif level >= 20:
                title = 'Expert'
            elif level >= 10:
                title = 'Achiever'
            elif level >= 5:
                title = 'Explorer'
            else:
                title = 'Dreamer'

            results.append({
                'id': user.id,
                'username': user.display_name or 'Anonymous',
                'avatar': user.avatar_url or '',
                'title': title,
                'influenceScore': user.xp,
                'currentLevel': user.level,
                'isFriend': user.id in friend_ids,
                'isFollowing': user.id in following_ids,
            })

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
            UserFollow.objects.filter(follower=user).values_list('following_id', flat=True)
        )
        friend_ids = set(
            Friendship.objects.filter(user1=user, status='accepted').values_list('user2_id', flat=True)
        ) | set(
            Friendship.objects.filter(user2=user, status='accepted').values_list('user1_id', flat=True)
        )

        # Get blocked IDs
        blocked_ids = set(
            BlockedUser.objects.filter(blocker=user).values_list('blocked_id', flat=True)
        ) | set(
            BlockedUser.objects.filter(blocked=user).values_list('blocker_id', flat=True)
        )

        exclude_ids = following_ids | friend_ids | blocked_ids | {user.id}

        # Strategy 1: Users in shared circles
        from apps.circles.models import CircleMembership
        user_circle_ids = CircleMembership.objects.filter(
            user=user
        ).values_list('circle_id', flat=True)

        circle_user_ids = set(
            CircleMembership.objects.filter(
                circle_id__in=user_circle_ids
            ).exclude(
                user_id__in=exclude_ids
            ).values_list('user_id', flat=True)
        )

        # Strategy 2: Friends of friends (mutual friends) — single batch query
        limited_friend_ids = list(friend_ids)[:20]
        fof_friendships = Friendship.objects.filter(
            Q(user1_id__in=limited_friend_ids) | Q(user2_id__in=limited_friend_ids),
            status='accepted'
        )
        fof_ids = set()
        for f in fof_friendships:
            for uid in (f.user1_id, f.user2_id):
                if uid not in exclude_ids:
                    fof_ids.add(uid)

        # Strategy 3: Users with similar dream categories
        from apps.dreams.models import Dream
        user_categories = set(
            Dream.objects.filter(
                user=user, status='active'
            ).values_list('category', flat=True)
        )
        similar_category_ids = set()
        if user_categories:
            similar_category_ids = set(
                Dream.objects.filter(
                    category__in=user_categories, status='active'
                ).exclude(
                    user_id__in=exclude_ids
                ).values_list('user_id', flat=True)[:50]
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
                title = 'Legend'
            elif level >= 30:
                title = 'Master'
            elif level >= 20:
                title = 'Expert'
            elif level >= 10:
                title = 'Achiever'
            elif level >= 5:
                title = 'Explorer'
            else:
                title = 'Dreamer'

            results.append({
                'id': u.id,
                'username': u.display_name or 'Anonymous',
                'avatar': u.avatar_url or '',
                'title': title,
                'influenceScore': u.xp,
                'currentLevel': u.level,
                'isFriend': False,
                'isFollowing': False,
            })

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
                name='FeedLikeResponse',
                fields={
                    'liked': drf_serializers.BooleanField(),
                    'like_count': drf_serializers.IntegerField(),
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
                {'error': 'Activity not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        like, created = ActivityLike.objects.get_or_create(
            user=request.user, activity=activity,
        )

        if not created:
            # Already liked — toggle off
            like.delete()
            liked = False
        else:
            liked = True

        like_count = ActivityLike.objects.filter(activity=activity).count()
        return Response({'liked': liked, 'like_count': like_count})


class FeedCommentView(APIView):
    """Add a comment to an activity feed item."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Comment on a feed activity",
        description="Add a comment to an activity feed item.",
        tags=["Social"],
        request=inline_serializer(
            name='FeedCommentRequest',
            fields={'text': drf_serializers.CharField()},
        ),
        responses={
            201: inline_serializer(
                name='FeedCommentResponse',
                fields={
                    'id': drf_serializers.UUIDField(),
                    'text': drf_serializers.CharField(),
                    'user': drf_serializers.DictField(),
                    'created_at': drf_serializers.DateTimeField(),
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
                {'error': 'Activity not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        text = request.data.get('text', '').strip()
        if not text:
            return Response(
                {'error': 'text is required.'},
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
                'id': comment.id,
                'text': comment.text,
                'user': {
                    'id': str(request.user.id),
                    'username': request.user.display_name or 'Anonymous',
                    'avatar': request.user.avatar_url or '',
                },
                'created_at': comment.created_at,
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
    @action(detail=False, methods=['get'], url_path='list')
    def list_searches(self, request):
        """Return up to 20 recent searches."""
        searches = RecentSearch.objects.filter(user=request.user)[:20]
        data = [
            {
                'id': str(s.id),
                'query': s.query,
                'search_type': s.search_type,
                'created_at': s.created_at,
            }
            for s in searches
        ]
        return Response(data)

    @extend_schema(
        summary="Record a search",
        description="Record a recent search query.",
        tags=["Social"],
    )
    @action(detail=False, methods=['post'], url_path='add')
    def add_search(self, request):
        """Record a search query."""
        query = request.data.get('query', '').strip()
        search_type = request.data.get('search_type', 'all')
        if not query:
            return Response({'error': 'query is required.'}, status=status.HTTP_400_BAD_REQUEST)

        # Avoid duplicates — delete older same query
        RecentSearch.objects.filter(user=request.user, query=query).delete()
        RecentSearch.objects.create(user=request.user, query=query, search_type=search_type)

        # Keep only 20 most recent
        old_ids = RecentSearch.objects.filter(
            user=request.user
        ).order_by('-created_at').values_list('id', flat=True)[20:]
        RecentSearch.objects.filter(id__in=list(old_ids)).delete()

        return Response({'message': 'Search recorded.'}, status=status.HTTP_201_CREATED)

    @extend_schema(
        summary="Clear recent searches",
        description="Delete all recent searches for the current user.",
        tags=["Social"],
    )
    @action(detail=False, methods=['delete'], url_path='clear')
    def clear_searches(self, request):
        """Clear all recent searches."""
        RecentSearch.objects.filter(user=request.user).delete()
        return Response({'message': 'Recent searches cleared.'})

    @extend_schema(
        summary="Remove a recent search",
        description="Delete a single recent search by its ID.",
        tags=["Social"],
        responses={
            200: OpenApiResponse(description="Search removed."),
            404: OpenApiResponse(description="Search not found."),
        },
    )
    @action(detail=False, methods=['delete'], url_path=r'(?P<pk>[0-9a-f-]+)/remove')
    def remove_search(self, request, pk=None):
        """Delete a single recent search by ID."""
        try:
            search = RecentSearch.objects.get(id=pk, user=request.user)
        except RecentSearch.DoesNotExist:
            return Response(
                {'error': 'Search not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        search.delete()
        return Response({'message': 'Search removed.'})


class DreamPostViewSet(viewsets.ModelViewSet):
    """
    Social dream posts: feed, CRUD, like, comment, encourage, share.

    All endpoints live under /api/social/posts/.
    The main social feed is at /api/social/posts/feed/.
    """

    permission_classes = [IsAuthenticated]
    serializer_class = DreamPostSerializer

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return DreamPost.objects.none()
        return DreamPost.objects.select_related('user', 'dream').order_by('-created_at')

    def get_serializer_class(self):
        if self.action == 'create':
            return DreamPostCreateSerializer
        return DreamPostSerializer

    def create(self, request, *args, **kwargs):
        """Create a new dream post."""
        serializer = DreamPostCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        # Validate dream ownership if provided
        dream = None
        dream_id = data.get('dream_id')
        if dream_id:
            from apps.dreams.models import Dream
            try:
                dream = Dream.objects.get(id=dream_id, user=request.user)
            except Dream.DoesNotExist:
                return Response(
                    {'error': 'Dream not found.'},
                    status=status.HTTP_404_NOT_FOUND,
                )

        post = DreamPost.objects.create(
            user=request.user,
            dream=dream,
            content=data['content'],
            image_url=data.get('image_url', ''),
            gofundme_url=data.get('gofundme_url', ''),
            visibility=data.get('visibility', 'public'),
        )

        return Response(
            DreamPostSerializer(post, context={'request': request}).data,
            status=status.HTTP_201_CREATED,
        )

    def update(self, request, *args, **kwargs):
        """Edit own post."""
        post = self.get_object()
        if post.user != request.user:
            return Response(
                {'error': 'You can only edit your own posts.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        content = request.data.get('content')
        if content:
            from core.sanitizers import sanitize_text
            post.content = sanitize_text(content)

        gofundme_url = request.data.get('gofundme_url')
        if gofundme_url is not None:
            from core.sanitizers import sanitize_url
            post.gofundme_url = sanitize_url(gofundme_url)

        visibility = request.data.get('visibility')
        if visibility in ('public', 'followers', 'private'):
            post.visibility = visibility

        post.save()
        return Response(
            DreamPostSerializer(post, context={'request': request}).data,
        )

    def partial_update(self, request, *args, **kwargs):
        return self.update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        """Delete own post."""
        post = self.get_object()
        if post.user != request.user:
            return Response(
                {'error': 'You can only delete your own posts.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        post.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(
        summary="Social feed",
        description="Main social feed: posts from followed users + public, excluding blocked users.",
        responses={200: DreamPostSerializer(many=True)},
        tags=["Social Feed"],
    )
    @action(detail=False, methods=['get'])
    def feed(self, request):
        """Main social feed."""
        user = request.user

        # Get followed user IDs
        followed_ids = set(
            UserFollow.objects.filter(follower=user).values_list('following_id', flat=True)
        )

        # Get blocked user IDs (both directions)
        blocked_ids = set()
        blocked_qs = BlockedUser.objects.filter(
            Q(blocker=user) | Q(blocked=user)
        ).values_list('blocker_id', 'blocked_id')
        for blocker_id, blocked_id in blocked_qs:
            if blocker_id != user.id:
                blocked_ids.add(blocker_id)
            if blocked_id != user.id:
                blocked_ids.add(blocked_id)

        # Posts from followed users OR public posts, excluding blocked
        posts = DreamPost.objects.filter(
            Q(user_id__in=followed_ids) | Q(visibility='public')
        ).exclude(
            user_id__in=blocked_ids,
        ).select_related('user', 'dream').order_by('-created_at')

        # Annotate with user_has_liked and user_has_encouraged
        posts = posts.annotate(
            _user_has_liked=Exists(
                DreamPostLike.objects.filter(post=OuterRef('pk'), user=user)
            ),
            _user_has_encouraged=Exists(
                DreamEncouragement.objects.filter(post=OuterRef('pk'), user=user)
            ),
        )

        page = self.paginate_queryset(posts)
        if page is not None:
            serializer = DreamPostSerializer(page, many=True, context={'request': request})
            return self.get_paginated_response(serializer.data)

        serializer = DreamPostSerializer(posts[:50], many=True, context={'request': request})
        return Response(serializer.data)

    @extend_schema(
        summary="Like/unlike a post",
        description="Toggle like on a dream post.",
        tags=["Social Feed"],
        responses={200: dict},
    )
    @action(detail=True, methods=['post'])
    def like(self, request, pk=None):
        """Toggle like on a post."""
        post = self.get_object()
        like, created = DreamPostLike.objects.get_or_create(
            post=post, user=request.user,
        )

        if created:
            DreamPost.objects.filter(id=post.id).update(
                likes_count=F('likes_count') + 1
            )
            # Create notification
            self._notify_post_owner(
                post, request.user,
                title=f"{request.user.display_name or 'Someone'} liked your dream post",
            )
            return Response({'liked': True, 'likes_count': post.likes_count + 1})
        else:
            like.delete()
            DreamPost.objects.filter(id=post.id).update(
                likes_count=F('likes_count') - 1
            )
            return Response({'liked': False, 'likes_count': max(0, post.likes_count - 1)})

    @extend_schema(
        summary="Comment on a post",
        description="Add a comment to a dream post.",
        tags=["Social Feed"],
        responses={201: DreamPostCommentSerializer},
    )
    @action(detail=True, methods=['post'])
    def comment(self, request, pk=None):
        """Add a comment to a post."""
        post = self.get_object()
        content = request.data.get('content', '').strip()
        if not content:
            return Response(
                {'error': 'content is required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        from core.sanitizers import sanitize_text
        content = sanitize_text(content)

        parent_id = request.data.get('parent_id')
        parent = None
        if parent_id:
            try:
                parent = DreamPostComment.objects.get(id=parent_id, post=post)
            except DreamPostComment.DoesNotExist:
                return Response(
                    {'error': 'Parent comment not found.'},
                    status=status.HTTP_404_NOT_FOUND,
                )

        comment = DreamPostComment.objects.create(
            post=post,
            user=request.user,
            content=content,
            parent=parent,
        )

        DreamPost.objects.filter(id=post.id).update(
            comments_count=F('comments_count') + 1
        )

        self._notify_post_owner(
            post, request.user,
            title=f"{request.user.display_name or 'Someone'} commented on your post",
        )

        return Response(
            DreamPostCommentSerializer(comment, context={'request': request}).data,
            status=status.HTTP_201_CREATED,
        )

    @extend_schema(
        summary="List comments on a post",
        description="Get paginated comments for a dream post.",
        tags=["Social Feed"],
        responses={200: DreamPostCommentSerializer(many=True)},
    )
    @action(detail=True, methods=['get'])
    def comments(self, request, pk=None):
        """List comments on a post."""
        post = self.get_object()
        # Get top-level comments (replies are nested in serializer)
        qs = DreamPostComment.objects.filter(
            post=post, parent__isnull=True,
        ).select_related('user').order_by('-created_at')

        page = self.paginate_queryset(qs)
        if page is not None:
            serializer = DreamPostCommentSerializer(
                page, many=True, context={'request': request}
            )
            return self.get_paginated_response(serializer.data)

        serializer = DreamPostCommentSerializer(
            qs, many=True, context={'request': request}
        )
        return Response(serializer.data)

    @extend_schema(
        summary="Encourage a post",
        description="Send encouragement with a type (you_got_this, keep_going, etc).",
        tags=["Social Feed"],
        responses={201: DreamEncouragementSerializer},
    )
    @action(detail=True, methods=['post'])
    def encourage(self, request, pk=None):
        """Send encouragement to a post."""
        post = self.get_object()
        encouragement_type = request.data.get('encouragement_type', 'you_got_this')
        message = request.data.get('message', '')

        valid_types = [t[0] for t in DreamEncouragement.ENCOURAGEMENT_TYPES]
        if encouragement_type not in valid_types:
            return Response(
                {'error': f'encouragement_type must be one of: {", ".join(valid_types)}'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if message:
            from core.sanitizers import sanitize_text
            message = sanitize_text(message)

        encouragement, created = DreamEncouragement.objects.update_or_create(
            post=post,
            user=request.user,
            defaults={
                'encouragement_type': encouragement_type,
                'message': message,
            },
        )

        if created:
            type_display = dict(DreamEncouragement.ENCOURAGEMENT_TYPES).get(
                encouragement_type, encouragement_type
            )
            self._notify_post_owner(
                post, request.user,
                title=f"{request.user.display_name or 'Someone'} encouraged you: {type_display}",
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
    @action(detail=True, methods=['post'])
    def share(self, request, pk=None):
        """Share/repost to own followers."""
        original_post = self.get_object()
        content = request.data.get('content', '')
        if content:
            from core.sanitizers import sanitize_text
            content = sanitize_text(content)

        share_content = content or f'Shared: {original_post.content[:200]}'

        new_post = DreamPost.objects.create(
            user=request.user,
            dream=original_post.dream,
            content=share_content,
            image_url=original_post.image_url,
            gofundme_url=original_post.gofundme_url,
            visibility='public',
        )

        DreamPost.objects.filter(id=original_post.id).update(
            shares_count=F('shares_count') + 1
        )

        return Response(
            DreamPostSerializer(new_post, context={'request': request}).data,
            status=status.HTTP_201_CREATED,
        )

    @extend_schema(
        summary="User's posts",
        description="Get posts by a specific user.",
        tags=["Social Feed"],
        responses={200: DreamPostSerializer(many=True)},
    )
    @action(detail=False, methods=['get'], url_path=r'user/(?P<user_id>[0-9a-f-]+)')
    def user_posts(self, request, user_id=None):
        """Get posts by a specific user."""
        try:
            target_user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response(
                {'error': 'User not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Check if blocked
        if BlockedUser.is_blocked(request.user, target_user):
            return Response(
                {'error': 'Cannot view this user.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Determine visibility
        is_following = UserFollow.objects.filter(
            follower=request.user, following=target_user
        ).exists()

        posts = DreamPost.objects.filter(user=target_user)
        if target_user != request.user:
            if is_following:
                posts = posts.filter(visibility__in=['public', 'followers'])
            else:
                posts = posts.filter(visibility='public')

        posts = posts.select_related('user', 'dream').order_by('-created_at')

        page = self.paginate_queryset(posts)
        if page is not None:
            serializer = DreamPostSerializer(
                page, many=True, context={'request': request}
            )
            return self.get_paginated_response(serializer.data)

        serializer = DreamPostSerializer(
            posts, many=True, context={'request': request}
        )
        return Response(serializer.data)

    def _notify_post_owner(self, post, actor, title):
        """Create a notification for the post owner."""
        if post.user == actor:
            return  # Don't notify yourself
        try:
            from apps.notifications.models import Notification
            from django.utils import timezone
            Notification.objects.create(
                user=post.user,
                notification_type='social',
                title=title,
                body='',
                scheduled_for=timezone.now(),
                data={
                    'post_id': str(post.id),
                    'actor_id': str(actor.id),
                    'type': 'social',
                },
            )
        except Exception:
            logger.debug("Failed to create social notification", exc_info=True)
