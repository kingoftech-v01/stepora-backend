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
from drf_spectacular.utils import (
    extend_schema,
    extend_schema_view,
    OpenApiParameter,
    OpenApiResponse,
)

from apps.users.models import User
from .models import Friendship, UserFollow, ActivityFeedItem
from .serializers import (
    FriendSerializer,
    FriendRequestSerializer,
    UserSearchResultSerializer,
    ActivityFeedItemSerializer,
    SendFriendRequestSerializer,
    FollowUserSerializer,
    UserPublicSerializer,
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


class ActivityFeedView(generics.ListAPIView):
    """
    View for retrieving the friends activity feed.

    Shows activity items from the user's friends and followed users,
    ordered by most recent first.
    """

    permission_classes = [IsAuthenticated]
    serializer_class = ActivityFeedItemSerializer

    def get_queryset(self):
        user = self.request.user

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

        # Combine friends and followed users
        all_ids = friend_ids | followed_ids
        all_ids.add(user.id)  # Include own activity

        return ActivityFeedItem.objects.filter(
            user_id__in=all_ids
        ).select_related('user').order_by('-created_at')

    @extend_schema(
        summary="Friends activity feed",
        description=(
            "Retrieve activity feed from friends and followed users. "
            "Shows recent activities like task completions, dream achievements, and milestones."
        ),
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

        users = User.objects.filter(
            Q(display_name__icontains=query) | Q(email__icontains=query),
            is_active=True
        ).exclude(
            id=request.user.id
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
