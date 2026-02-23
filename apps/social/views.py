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
from .models import Friendship, UserFollow, ActivityFeedItem, BlockedUser, ReportedUser, RecentSearch
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
)


class FriendshipViewSet(viewsets.GenericViewSet):
    """
    ViewSet for friendship management.

    Supports listing friends, viewing/sending/accepting/rejecting requests,
    and following users.
    """

    permission_classes = [IsAuthenticated]

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
        return Response({'friends': serializer.data})

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
        return Response({'requests': serializer.data})

    @extend_schema(
        summary="Send friend request",
        description="Send a friend request to another user.",
        request=SendFriendRequestSerializer,
        responses={
            201: OpenApiResponse(description="Friend request sent."),
            400: OpenApiResponse(description="Cannot send request (already friends, self-request, etc.)."),
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

        target_user_id = serializer.validated_data['targetUserId']

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

        target_user_id = serializer.validated_data['targetUserId']

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

        return Response({'requests': data})

    @extend_schema(
        summary="Block a user",
        description="Block another user. Removes existing friendships and follows.",
        request=BlockUserSerializer,
        responses={
            201: OpenApiResponse(description="User blocked."),
            400: OpenApiResponse(description="Cannot block yourself or already blocked."),
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

        target_user_id = serializer.validated_data['targetUserId']
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
        return Response({'blocked_users': serializer.data})

    @extend_schema(
        summary="Report a user",
        description="Report a user for moderation review.",
        request=ReportUserSerializer,
        responses={
            201: OpenApiResponse(description="Report submitted."),
            400: OpenApiResponse(description="Cannot report yourself."),
        },
        tags=["Social"],
    )
    @action(detail=False, methods=['post'], url_path='report')
    def report_user(self, request):
        """Submit a user report for moderation."""
        serializer = ReportUserSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        target_user_id = serializer.validated_data['targetUserId']

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
        responses={200: FriendSerializer(many=True)},
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
        return Response({'friends': serializer.data, 'count': len(friends)})

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

        return Response({'friends': online, 'count': len(online)})

    @extend_schema(
        summary="Follower and following counts",
        description="Get follower and following counts for a user.",
        tags=["Social"],
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
        user = self.request.user

        # Free users only see encouragements received
        if user.subscription == 'free':
            return ActivityFeedItem.objects.filter(
                Q(user=user),
                activity_type='encouragement',
            ).select_related('user').order_by('-created_at')

        # Get friend IDs (accepted friendships)
        friend_ids = set()
        friendships = Friendship.objects.filter(
            Q(user1=user) | Q(user2=user),
            status='accepted'
        )
        for f in friendships:
            if f.user1_id == user.id:
                friend_ids.add(f.user2_id)
            else:
                friend_ids.add(f.user1_id)

        # Get followed user IDs
        followed_ids = set(
            UserFollow.objects.filter(
                follower=user
            ).values_list('following_id', flat=True)
        )

        # Exclude blocked users (both directions)
        blocked_ids = set(
            BlockedUser.objects.filter(
                Q(blocker=user) | Q(blocked=user)
            ).values_list('blocker_id', 'blocked_id')
            .distinct()
        )
        excluded_ids = set()
        for blocker_id, blocked_id in blocked_ids:
            excluded_ids.add(blocker_id)
            excluded_ids.add(blocked_id)
        excluded_ids.discard(user.id)

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
        """
        query = request.query_params.get('q', '').strip()
        if len(query) < 2:
            return Response({'users': []})

        # Get blocked user IDs (both directions)
        blocked_ids = set()
        blocks = BlockedUser.objects.filter(
            Q(blocker=request.user) | Q(blocked=request.user)
        ).values_list('blocker_id', 'blocked_id')
        for blocker_id, blocked_id in blocks:
            blocked_ids.add(blocker_id)
            blocked_ids.add(blocked_id)
        blocked_ids.discard(request.user.id)

        # Security: search by display_name only — never expose email in search
        users = User.objects.filter(
            display_name__icontains=query,
            is_active=True
        ).exclude(
            id=request.user.id
        ).exclude(
            id__in=blocked_ids
        ).order_by('display_name')[:20]

        # Pre-fetch friendship and follow status
        friend_ids = set()
        friendships = Friendship.objects.filter(
            Q(user1=request.user) | Q(user2=request.user),
            status='accepted'
        )
        for f in friendships:
            if f.user1_id == request.user.id:
                friend_ids.add(f.user2_id)
            else:
                friend_ids.add(f.user1_id)

        following_ids = set(
            UserFollow.objects.filter(
                follower=request.user
            ).values_list('following_id', flat=True)
        )

        results = []
        for user in users:
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
        return Response({'users': serializer.data})


class FollowSuggestionsView(generics.ListAPIView):
    """
    View for suggesting users to follow. Requires premium+ subscription.

    Suggestions are based on:
    - Users in shared circles
    - Mutual friends
    - Users with similar dream categories
    """

    permission_classes = [IsAuthenticated, CanUseSocialFeed]
    serializer_class = UserSearchResultSerializer

    @extend_schema(
        summary="Follow suggestions",
        description=(
            "Get suggested users to follow based on shared circles, "
            "mutual friends, and similar dream categories."
        ),
        tags=["Social"],
    )
    def list(self, request, *args, **kwargs):
        user = request.user

        # Get IDs the user already follows or is friends with
        following_ids = set(
            UserFollow.objects.filter(follower=user).values_list('following_id', flat=True)
        )
        friend_ids = set()
        friendships = Friendship.objects.filter(
            Q(user1=user) | Q(user2=user), status='accepted'
        )
        for f in friendships:
            friend_ids.add(f.user2_id if f.user1_id == user.id else f.user1_id)

        # Get blocked IDs
        blocked_ids = set()
        blocks = BlockedUser.objects.filter(
            Q(blocker=user) | Q(blocked=user)
        ).values_list('blocker_id', 'blocked_id')
        for blocker_id, blocked_id in blocks:
            blocked_ids.add(blocker_id)
            blocked_ids.add(blocked_id)
        blocked_ids.discard(user.id)

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

        # Strategy 2: Friends of friends (mutual friends)
        fof_ids = set()
        for fid in list(friend_ids)[:20]:  # Limit for performance
            their_friendships = Friendship.objects.filter(
                Q(user1_id=fid) | Q(user2_id=fid), status='accepted'
            )
            for f in their_friendships:
                fof_id = f.user2_id if f.user1_id == fid else f.user1_id
                if fof_id not in exclude_ids:
                    fof_ids.add(fof_id)

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
        return Response({'suggestions': serializer.data})


class RecentSearchViewSet(viewsets.GenericViewSet):
    """CRUD for recent search queries."""

    permission_classes = [IsAuthenticated]

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
        return Response({'recent_searches': data})

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
