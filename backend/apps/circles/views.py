"""
Views for the Circles system.

Provides API endpoints for circle management, membership, feed posts,
and challenges. All endpoints require authentication.
"""

from rest_framework import viewsets, status, generics
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Q, Count
from drf_spectacular.utils import (
    extend_schema,
    extend_schema_view,
    OpenApiParameter,
    OpenApiResponse,
)

from .models import Circle, CircleMembership, CirclePost, CircleChallenge
from .serializers import (
    CircleListSerializer,
    CircleDetailSerializer,
    CircleCreateSerializer,
    CirclePostSerializer,
    CirclePostCreateSerializer,
    CircleChallengeSerializer,
)


@extend_schema_view(
    list=extend_schema(
        summary="List circles",
        description=(
            "Retrieve circles filtered by type: 'my' (user's circles), "
            "'public' (all public circles), or 'recommended' (suggested based on category)."
        ),
        parameters=[
            OpenApiParameter(
                name='filter',
                type=str,
                location=OpenApiParameter.QUERY,
                description="Filter type: 'my', 'public', or 'recommended'.",
                required=False,
                enum=['my', 'public', 'recommended'],
            ),
        ],
        tags=["Circles"],
    ),
    retrieve=extend_schema(
        summary="Get circle details",
        description="Retrieve detailed information about a specific circle including members and challenges.",
        tags=["Circles"],
    ),
    create=extend_schema(
        summary="Create a circle",
        description="Create a new Dream Circle. The creator is automatically added as an admin member.",
        tags=["Circles"],
    ),
)
class CircleViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Dream Circle management.

    Supports listing (with filters), creating, retrieving details,
    joining, leaving, posting to feed, and viewing challenges.
    """

    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.action == 'create':
            return CircleCreateSerializer
        if self.action == 'retrieve':
            return CircleDetailSerializer
        if self.action in ('feed', 'posts'):
            return CirclePostSerializer
        if self.action == 'challenges':
            return CircleChallengeSerializer
        return CircleListSerializer

    def get_queryset(self):
        return Circle.objects.annotate(
            members_count=Count('memberships')
        ).select_related('creator')

    def list(self, request, *args, **kwargs):
        """
        List circles with optional filtering.

        Filters:
        - 'my': circles the user is a member of
        - 'public': all public circles
        - 'recommended': public circles matching user interests, excluding joined ones
        """
        filter_type = request.query_params.get('filter', 'recommended')
        queryset = self.get_queryset()

        if filter_type == 'my':
            user_circle_ids = CircleMembership.objects.filter(
                user=request.user
            ).values_list('circle_id', flat=True)
            queryset = queryset.filter(id__in=user_circle_ids)
        elif filter_type == 'public':
            queryset = queryset.filter(is_public=True)
        else:  # recommended
            user_circle_ids = CircleMembership.objects.filter(
                user=request.user
            ).values_list('circle_id', flat=True)
            queryset = queryset.filter(
                is_public=True
            ).exclude(
                id__in=user_circle_ids
            ).order_by('-members_count', '-created_at')

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            response = self.get_paginated_response(serializer.data)
            response.data['circles'] = response.data.pop('results')
            return response

        serializer = self.get_serializer(queryset, many=True)
        return Response({'circles': serializer.data})

    def retrieve(self, request, *args, **kwargs):
        """Retrieve circle detail with members and challenges."""
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response({'circle': serializer.data})

    @extend_schema(
        summary="Join a circle",
        description="Join a public circle. Fails if the circle is full or the user is already a member.",
        responses={
            200: OpenApiResponse(description="Successfully joined the circle."),
            400: OpenApiResponse(description="Circle is full or user already a member."),
        },
        tags=["Circles"],
    )
    @action(detail=True, methods=['post'], url_path='join')
    def join(self, request, pk=None):
        """
        Join a circle.

        Adds the requesting user as a member with the 'member' role.
        Checks that the circle is not full and the user is not already a member.
        """
        circle = self.get_object()

        # Check if already a member
        if CircleMembership.objects.filter(circle=circle, user=request.user).exists():
            return Response(
                {'error': 'You are already a member of this circle.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Check if circle is full
        if circle.is_full:
            return Response(
                {'error': 'This circle has reached its maximum number of members.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Check if public
        if not circle.is_public:
            return Response(
                {'error': 'This circle is private. You need an invitation to join.'},
                status=status.HTTP_403_FORBIDDEN
            )

        CircleMembership.objects.create(
            circle=circle,
            user=request.user,
            role='member'
        )

        return Response({
            'message': f'Successfully joined {circle.name}.',
            'circle_id': str(circle.id),
        })

    @extend_schema(
        summary="Leave a circle",
        description="Leave a circle. Admins cannot leave unless they are the last member.",
        responses={
            200: OpenApiResponse(description="Successfully left the circle."),
            400: OpenApiResponse(description="Cannot leave (e.g., last admin)."),
        },
        tags=["Circles"],
    )
    @action(detail=True, methods=['post'], url_path='leave')
    def leave(self, request, pk=None):
        """
        Leave a circle.

        Removes the requesting user's membership. If the user is the last
        admin and there are other members, they cannot leave without
        transferring ownership.
        """
        circle = self.get_object()

        try:
            membership = CircleMembership.objects.get(
                circle=circle,
                user=request.user
            )
        except CircleMembership.DoesNotExist:
            return Response(
                {'error': 'You are not a member of this circle.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # If admin and other members exist, check for other admins
        if membership.role == 'admin':
            other_admins = CircleMembership.objects.filter(
                circle=circle,
                role='admin'
            ).exclude(user=request.user).count()

            other_members = CircleMembership.objects.filter(
                circle=circle
            ).exclude(user=request.user).count()

            if other_members > 0 and other_admins == 0:
                return Response(
                    {'error': 'You are the only admin. Please assign another admin before leaving.'},
                    status=status.HTTP_400_BAD_REQUEST
                )

        membership.delete()
        return Response({'message': f'Successfully left {circle.name}.'})

    @extend_schema(
        summary="Get circle feed",
        description="Retrieve the feed of posts for a specific circle.",
        responses={200: CirclePostSerializer(many=True)},
        tags=["Circles"],
    )
    @action(detail=True, methods=['get'], url_path='feed')
    def feed(self, request, pk=None):
        """
        Retrieve the circle's post feed.

        Returns posts ordered by most recent first. Only accessible
        to circle members.
        """
        circle = self.get_object()

        # Verify membership
        if not CircleMembership.objects.filter(circle=circle, user=request.user).exists():
            return Response(
                {'error': 'You must be a member to view the feed.'},
                status=status.HTTP_403_FORBIDDEN
            )

        posts = CirclePost.objects.filter(
            circle=circle
        ).select_related('author').order_by('-created_at')

        page = self.paginate_queryset(posts)
        if page is not None:
            serializer = CirclePostSerializer(page, many=True)
            response = self.get_paginated_response(serializer.data)
            response.data['feed'] = response.data.pop('results')
            return response

        serializer = CirclePostSerializer(posts, many=True)
        return Response({'feed': serializer.data})

    @extend_schema(
        summary="Create a circle post",
        description="Post a new update to a circle's feed. Must be a member.",
        request=CirclePostCreateSerializer,
        responses={
            201: CirclePostSerializer,
            403: OpenApiResponse(description="Not a member of this circle."),
        },
        tags=["Circles"],
    )
    @action(detail=True, methods=['post'], url_path='posts')
    def posts(self, request, pk=None):
        """
        Create a new post in the circle's feed.

        Only circle members can post. Returns the newly created post.
        """
        circle = self.get_object()

        # Verify membership
        if not CircleMembership.objects.filter(circle=circle, user=request.user).exists():
            return Response(
                {'error': 'You must be a member to post.'},
                status=status.HTTP_403_FORBIDDEN
            )

        create_serializer = CirclePostCreateSerializer(data=request.data)
        create_serializer.is_valid(raise_exception=True)

        post = CirclePost.objects.create(
            circle=circle,
            author=request.user,
            content=create_serializer.validated_data['content']
        )

        serializer = CirclePostSerializer(post)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @extend_schema(
        summary="List circle challenges",
        description="Retrieve active and upcoming challenges for a specific circle.",
        responses={200: CircleChallengeSerializer(many=True)},
        tags=["Circles"],
    )
    @action(detail=True, methods=['get'], url_path='challenges')
    def challenges(self, request, pk=None):
        """
        List challenges for a circle.

        Returns active and upcoming challenges, ordered by start date.
        """
        circle = self.get_object()
        challenges = CircleChallenge.objects.filter(
            circle=circle,
            status__in=['upcoming', 'active']
        ).order_by('-start_date')

        serializer = CircleChallengeSerializer(challenges, many=True)
        return Response({'challenges': serializer.data})


@extend_schema_view(
    list=extend_schema(
        summary="List all challenges",
        description="List all active and upcoming challenges across all circles.",
        tags=["Circles"],
    ),
)
class ChallengeViewSet(viewsets.GenericViewSet):
    """
    ViewSet for challenge actions that operate outside a specific circle context.

    Supports joining challenges by ID.
    """

    permission_classes = [IsAuthenticated]
    serializer_class = CircleChallengeSerializer
    queryset = CircleChallenge.objects.all()

    @extend_schema(
        summary="Join a challenge",
        description="Join a specific circle challenge. Must be a member of the circle.",
        responses={
            200: OpenApiResponse(description="Successfully joined the challenge."),
            400: OpenApiResponse(description="Already joined or not a circle member."),
        },
        tags=["Circles"],
    )
    @action(detail=True, methods=['post'], url_path='join')
    def join(self, request, pk=None):
        """
        Join a challenge.

        The user must be a member of the circle the challenge belongs to.
        Returns an error if already joined.
        """
        challenge = self.get_object()

        # Verify circle membership
        if not CircleMembership.objects.filter(
            circle=challenge.circle,
            user=request.user
        ).exists():
            return Response(
                {'error': 'You must be a member of the circle to join this challenge.'},
                status=status.HTTP_403_FORBIDDEN
            )

        # Check if already a participant
        if challenge.participants.filter(id=request.user.id).exists():
            return Response(
                {'error': 'You have already joined this challenge.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        challenge.participants.add(request.user)

        return Response({
            'message': f'Successfully joined challenge: {challenge.title}.',
            'challenge_id': str(challenge.id),
        })
