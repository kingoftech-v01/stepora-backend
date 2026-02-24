"""
Views for the Circles system.

Provides API endpoints for circle management, membership, feed posts,
and challenges. All endpoints require authentication.
"""

from rest_framework import viewsets, status, generics
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from django.db.models import Q, Count
from drf_spectacular.utils import (
    extend_schema,
    extend_schema_view,
    OpenApiParameter,
    OpenApiResponse,
)

import secrets
from django.utils import timezone as django_timezone
from datetime import timedelta

from .models import (
    Circle, CircleMembership, CirclePost, CircleChallenge,
    PostReaction, CircleInvitation, ChallengeProgress,
)
from core.permissions import CanUseCircles
from .serializers import (
    CircleListSerializer,
    CircleDetailSerializer,
    CircleCreateSerializer,
    CircleUpdateSerializer,
    CirclePostSerializer,
    CirclePostCreateSerializer,
    CirclePostUpdateSerializer,
    CircleChallengeSerializer,
    PostReactionSerializer,
    MemberRoleSerializer,
    CircleInvitationSerializer,
    DirectInviteSerializer,
    ChallengeProgressSerializer,
    ChallengeProgressCreateSerializer,
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
        responses={
            403: OpenApiResponse(description='Subscription required.'),
        },
        tags=["Circles"],
    ),
    retrieve=extend_schema(
        summary="Get circle details",
        description="Retrieve detailed information about a specific circle including members and challenges.",
        responses={
            403: OpenApiResponse(description='Subscription required.'),
            404: OpenApiResponse(description='Resource not found.'),
        },
        tags=["Circles"],
    ),
    create=extend_schema(
        summary="Create a circle",
        description="Create a new Dream Circle. The creator is automatically added as an admin member.",
        responses={
            400: OpenApiResponse(description='Validation error.'),
            403: OpenApiResponse(description='Subscription required.'),
        },
        tags=["Circles"],
    ),
)
class CircleViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Dream Circle management.

    Supports listing (with filters), creating, retrieving details,
    joining, leaving, posting to feed, and viewing challenges.
    Requires premium+ for all access; creating circles requires pro.
    """

    permission_classes = [IsAuthenticated, CanUseCircles]

    def _get_membership(self, circle, user):
        """Get the membership for a user in a circle, or None."""
        try:
            return CircleMembership.objects.get(circle=circle, user=user)
        except CircleMembership.DoesNotExist:
            return None

    def _is_admin_or_moderator(self, circle, user):
        """Check if the user is an admin or moderator of the circle."""
        return CircleMembership.objects.filter(
            circle=circle, user=user, role__in=['admin', 'moderator']
        ).exists()

    def get_serializer_class(self):
        if self.action == 'create':
            return CircleCreateSerializer
        if self.action in ('update', 'partial_update'):
            return CircleUpdateSerializer
        if self.action == 'retrieve':
            return CircleDetailSerializer
        if self.action in ('feed', 'posts'):
            return CirclePostSerializer
        if self.action == 'challenges':
            return CircleChallengeSerializer
        return CircleListSerializer

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return Circle.objects.none()
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
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

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
            403: OpenApiResponse(description='Subscription required.'),
            404: OpenApiResponse(description='Resource not found.'),
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
            403: OpenApiResponse(description='Subscription required.'),
            404: OpenApiResponse(description='Resource not found.'),
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
        responses={
            200: CirclePostSerializer(many=True),
            403: OpenApiResponse(description='Subscription required.'),
            404: OpenApiResponse(description='Resource not found.'),
        },
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
            return self.get_paginated_response(serializer.data)

        serializer = CirclePostSerializer(posts, many=True)
        return Response(serializer.data)

    @extend_schema(
        summary="Create a circle post",
        description="Post a new update to a circle's feed. Must be a member.",
        request=CirclePostCreateSerializer,
        responses={
            201: CirclePostSerializer,
            400: OpenApiResponse(description='Validation error.'),
            403: OpenApiResponse(description="Not a member or subscription required."),
            404: OpenApiResponse(description='Resource not found.'),
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
        responses={
            200: CircleChallengeSerializer(many=True),
            403: OpenApiResponse(description='Subscription required.'),
            404: OpenApiResponse(description='Resource not found.'),
        },
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
        return Response(serializer.data)

    @extend_schema(
        summary="Update a circle",
        description="Update circle details. Only admins can update.",
        request=CircleUpdateSerializer,
        responses={
            200: CircleDetailSerializer,
            400: OpenApiResponse(description='Validation error.'),
            403: OpenApiResponse(description='Subscription required.'),
            404: OpenApiResponse(description='Resource not found.'),
        },
        tags=["Circles"],
    )
    def update(self, request, *args, **kwargs):
        """Update a circle (admin only)."""
        circle = self.get_object()
        membership = self._get_membership(circle, request.user)

        if not membership or membership.role != 'admin':
            return Response(
                {'error': 'Only admins can update this circle.'},
                status=status.HTTP_403_FORBIDDEN
            )

        serializer = CircleUpdateSerializer(circle, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response({'circle': CircleDetailSerializer(circle, context={'request': request}).data})

    def partial_update(self, request, *args, **kwargs):
        """Partial update delegates to update."""
        return self.update(request, *args, **kwargs)

    @extend_schema(
        summary="Delete a circle",
        description="Delete a circle. Only the circle admin can delete it.",
        responses={
            204: None,
            403: OpenApiResponse(description='Subscription required.'),
            404: OpenApiResponse(description='Resource not found.'),
        },
        tags=["Circles"],
    )
    def destroy(self, request, *args, **kwargs):
        """Delete a circle (admin only)."""
        circle = self.get_object()
        membership = self._get_membership(circle, request.user)

        if not membership or membership.role != 'admin':
            return Response(
                {'error': 'Only admins can delete this circle.'},
                status=status.HTTP_403_FORBIDDEN
            )

        circle.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(
        summary="Edit a circle post",
        description="Edit a post. Only the author or a moderator/admin can edit.",
        request=CirclePostUpdateSerializer,
        responses={
            200: CirclePostSerializer,
            403: OpenApiResponse(description='Subscription required.'),
            404: OpenApiResponse(description='Resource not found.'),
        },
        tags=["Circles"],
    )
    @action(detail=True, methods=['put'], url_path=r'posts/(?P<post_id>[0-9a-f-]+)/edit')
    def edit_post(self, request, pk=None, post_id=None):
        """Edit a circle post."""
        circle = self.get_object()

        try:
            post = CirclePost.objects.get(id=post_id, circle=circle)
        except CirclePost.DoesNotExist:
            return Response({'error': 'Post not found.'}, status=status.HTTP_404_NOT_FOUND)

        # Only author or moderator/admin can edit
        is_author = post.author == request.user
        is_mod = self._is_admin_or_moderator(circle, request.user)

        if not is_author and not is_mod:
            return Response(
                {'error': 'You do not have permission to edit this post.'},
                status=status.HTTP_403_FORBIDDEN
            )

        serializer = CirclePostUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        post.content = serializer.validated_data['content']
        post.save(update_fields=['content', 'updated_at'])

        return Response(CirclePostSerializer(post).data)

    @extend_schema(
        summary="Delete a circle post",
        description="Delete a post. Only the author or a moderator/admin can delete.",
        responses={
            204: None,
            403: OpenApiResponse(description='Subscription required.'),
            404: OpenApiResponse(description='Resource not found.'),
        },
        tags=["Circles"],
    )
    @action(detail=True, methods=['delete'], url_path=r'posts/(?P<post_id>[0-9a-f-]+)/delete')
    def delete_post(self, request, pk=None, post_id=None):
        """Delete a circle post."""
        circle = self.get_object()

        try:
            post = CirclePost.objects.get(id=post_id, circle=circle)
        except CirclePost.DoesNotExist:
            return Response({'error': 'Post not found.'}, status=status.HTTP_404_NOT_FOUND)

        is_author = post.author == request.user
        is_mod = self._is_admin_or_moderator(circle, request.user)

        if not is_author and not is_mod:
            return Response(
                {'error': 'You do not have permission to delete this post.'},
                status=status.HTTP_403_FORBIDDEN
            )

        post.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(
        summary="React to a post",
        description="Add or update a reaction on a circle post.",
        request=PostReactionSerializer,
        responses={
            200: OpenApiResponse(description="Reaction updated."),
            201: OpenApiResponse(description="Reaction added."),
            403: OpenApiResponse(description='Subscription required.'),
            404: OpenApiResponse(description='Resource not found.'),
        },
        tags=["Circles"],
    )
    @action(detail=True, methods=['post'], url_path=r'posts/(?P<post_id>[0-9a-f-]+)/react')
    def react_to_post(self, request, pk=None, post_id=None):
        """Add or update a reaction on a circle post."""
        circle = self.get_object()

        # Verify membership
        if not CircleMembership.objects.filter(circle=circle, user=request.user).exists():
            return Response(
                {'error': 'You must be a member to react.'},
                status=status.HTTP_403_FORBIDDEN
            )

        try:
            post = CirclePost.objects.get(id=post_id, circle=circle)
        except CirclePost.DoesNotExist:
            return Response({'error': 'Post not found.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = PostReactionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        reaction, created = PostReaction.objects.update_or_create(
            post=post,
            user=request.user,
            defaults={'reaction_type': serializer.validated_data['reaction_type']}
        )

        if created:
            return Response({'message': 'Reaction added.'}, status=status.HTTP_201_CREATED)
        return Response({'message': 'Reaction updated.'})

    @extend_schema(
        summary="Remove reaction from a post",
        description="Remove your reaction from a circle post.",
        responses={
            200: OpenApiResponse(description="Reaction removed."),
            403: OpenApiResponse(description='Subscription required.'),
            404: OpenApiResponse(description='Resource not found.'),
        },
        tags=["Circles"],
    )
    @action(detail=True, methods=['delete'], url_path=r'posts/(?P<post_id>[0-9a-f-]+)/unreact')
    def unreact_to_post(self, request, pk=None, post_id=None):
        """Remove a reaction from a circle post."""
        circle = self.get_object()

        try:
            post = CirclePost.objects.get(id=post_id, circle=circle)
        except CirclePost.DoesNotExist:
            return Response({'error': 'Post not found.'}, status=status.HTTP_404_NOT_FOUND)

        deleted_count, _ = PostReaction.objects.filter(
            post=post, user=request.user
        ).delete()

        if deleted_count == 0:
            return Response({'error': 'No reaction found.'}, status=status.HTTP_404_NOT_FOUND)

        return Response({'message': 'Reaction removed.'})

    @extend_schema(
        summary="Promote a member",
        description="Promote a circle member to moderator. Only admins can promote.",
        request=MemberRoleSerializer,
        responses={
            200: OpenApiResponse(description="Member role updated."),
            403: OpenApiResponse(description='Subscription required.'),
            404: OpenApiResponse(description='Resource not found.'),
        },
        tags=["Circles"],
    )
    @action(detail=True, methods=['post'], url_path=r'members/(?P<member_id>[0-9a-f-]+)/promote')
    def promote_member(self, request, pk=None, member_id=None):
        """Promote a member to moderator (admin only)."""
        circle = self.get_object()
        my_membership = self._get_membership(circle, request.user)

        if not my_membership or my_membership.role != 'admin':
            return Response(
                {'error': 'Only admins can promote members.'},
                status=status.HTTP_403_FORBIDDEN
            )

        try:
            target_membership = CircleMembership.objects.get(id=member_id, circle=circle)
        except CircleMembership.DoesNotExist:
            return Response({'error': 'Member not found.'}, status=status.HTTP_404_NOT_FOUND)

        if target_membership.role == 'admin':
            return Response(
                {'error': 'Cannot change an admin role.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        target_membership.role = 'moderator'
        target_membership.save(update_fields=['role'])

        return Response({'message': f'{target_membership.user.display_name or "User"} promoted to moderator.'})

    @extend_schema(
        summary="Demote a member",
        description="Demote a circle moderator to regular member. Only admins can demote.",
        responses={
            200: OpenApiResponse(description="Member demoted."),
            403: OpenApiResponse(description='Subscription required.'),
            404: OpenApiResponse(description='Resource not found.'),
        },
        tags=["Circles"],
    )
    @action(detail=True, methods=['post'], url_path=r'members/(?P<member_id>[0-9a-f-]+)/demote')
    def demote_member(self, request, pk=None, member_id=None):
        """Demote a moderator to member (admin only)."""
        circle = self.get_object()
        my_membership = self._get_membership(circle, request.user)

        if not my_membership or my_membership.role != 'admin':
            return Response(
                {'error': 'Only admins can demote members.'},
                status=status.HTTP_403_FORBIDDEN
            )

        try:
            target_membership = CircleMembership.objects.get(id=member_id, circle=circle)
        except CircleMembership.DoesNotExist:
            return Response({'error': 'Member not found.'}, status=status.HTTP_404_NOT_FOUND)

        if target_membership.role != 'moderator':
            return Response(
                {'error': 'Only moderators can be demoted.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        target_membership.role = 'member'
        target_membership.save(update_fields=['role'])

        return Response({'message': f'{target_membership.user.display_name or "User"} demoted to member.'})

    @extend_schema(
        summary="Remove a member",
        description="Remove a member from the circle. Only admins and moderators can remove.",
        responses={
            200: OpenApiResponse(description="Member removed."),
            403: OpenApiResponse(description='Subscription required.'),
            404: OpenApiResponse(description='Resource not found.'),
        },
        tags=["Circles"],
    )
    @action(detail=True, methods=['delete'], url_path=r'members/(?P<member_id>[0-9a-f-]+)/remove')
    def remove_member(self, request, pk=None, member_id=None):
        """Remove a member from a circle (admin/moderator only)."""
        circle = self.get_object()

        if not self._is_admin_or_moderator(circle, request.user):
            return Response(
                {'error': 'Only admins and moderators can remove members.'},
                status=status.HTTP_403_FORBIDDEN
            )

        try:
            target_membership = CircleMembership.objects.get(id=member_id, circle=circle)
        except CircleMembership.DoesNotExist:
            return Response({'error': 'Member not found.'}, status=status.HTTP_404_NOT_FOUND)

        if target_membership.role == 'admin':
            return Response(
                {'error': 'Cannot remove an admin.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        target_membership.delete()
        return Response({'message': 'Member removed from circle.'})

    @extend_schema(
        summary="Invite a user to a circle",
        description="Send a direct invitation to a specific user to join a private circle.",
        request=DirectInviteSerializer,
        responses={
            201: CircleInvitationSerializer,
            400: OpenApiResponse(description="User already a member or already invited."),
            403: OpenApiResponse(description="Not an admin/moderator or subscription required."),
            404: OpenApiResponse(description='Resource not found.'),
        },
        tags=["Circles"],
    )
    @action(detail=True, methods=['post'], url_path='invite')
    def invite(self, request, pk=None):
        """Send a direct invitation to a user."""
        circle = self.get_object()

        if not self._is_admin_or_moderator(circle, request.user):
            return Response(
                {'error': 'Only admins and moderators can invite users.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = DirectInviteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        target_user_id = serializer.validated_data['user_id']

        from apps.users.models import User
        try:
            target_user = User.objects.get(id=target_user_id)
        except User.DoesNotExist:
            return Response({'error': 'User not found.'}, status=status.HTTP_404_NOT_FOUND)

        if CircleMembership.objects.filter(circle=circle, user=target_user).exists():
            return Response(
                {'error': 'User is already a member of this circle.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Check for existing pending invitation
        if CircleInvitation.objects.filter(
            circle=circle, invitee=target_user, status='pending'
        ).exists():
            return Response(
                {'error': 'An invitation is already pending for this user.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        invitation = CircleInvitation.objects.create(
            circle=circle,
            inviter=request.user,
            invitee=target_user,
            invite_code=secrets.token_urlsafe(12),
            expires_at=django_timezone.now() + timedelta(days=7),
        )

        return Response(
            CircleInvitationSerializer(invitation).data,
            status=status.HTTP_201_CREATED,
        )

    @extend_schema(
        summary="Generate invite link",
        description="Generate a shareable invite code for a circle.",
        responses={
            201: CircleInvitationSerializer,
            403: OpenApiResponse(description='Subscription required.'),
            404: OpenApiResponse(description='Resource not found.'),
        },
        tags=["Circles"],
    )
    @action(detail=True, methods=['post'], url_path='invite-link')
    def invite_link(self, request, pk=None):
        """Generate a shareable invite link (no specific invitee)."""
        circle = self.get_object()

        if not self._is_admin_or_moderator(circle, request.user):
            return Response(
                {'error': 'Only admins and moderators can generate invite links.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        invitation = CircleInvitation.objects.create(
            circle=circle,
            inviter=request.user,
            invitee=None,
            invite_code=secrets.token_urlsafe(12),
            expires_at=django_timezone.now() + timedelta(days=14),
        )

        return Response(
            CircleInvitationSerializer(invitation).data,
            status=status.HTTP_201_CREATED,
        )

    @extend_schema(
        summary="List circle invitations",
        description="List all pending invitations for a circle.",
        responses={
            200: CircleInvitationSerializer(many=True),
            403: OpenApiResponse(description='Subscription required.'),
            404: OpenApiResponse(description='Resource not found.'),
        },
        tags=["Circles"],
    )
    @action(detail=True, methods=['get'], url_path='invitations')
    def invitations(self, request, pk=None):
        """List pending invitations for a circle (admin/moderator only)."""
        circle = self.get_object()

        if not self._is_admin_or_moderator(circle, request.user):
            return Response(
                {'error': 'Only admins and moderators can view invitations.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        invitations = CircleInvitation.objects.filter(
            circle=circle, status='pending'
        ).select_related('inviter', 'invitee').order_by('-created_at')

        serializer = CircleInvitationSerializer(invitations, many=True)
        return Response({'invitations': serializer.data})

    @extend_schema(
        summary="Submit challenge progress",
        description="Submit a progress entry for a circle challenge.",
        request=ChallengeProgressCreateSerializer,
        responses={
            201: ChallengeProgressSerializer,
            400: OpenApiResponse(description='Validation error.'),
            403: OpenApiResponse(description='Subscription required.'),
            404: OpenApiResponse(description='Resource not found.'),
        },
        tags=["Circles"],
    )
    @action(detail=True, methods=['post'], url_path=r'challenges/(?P<challenge_id>[0-9a-f-]+)/progress')
    def submit_progress(self, request, pk=None, challenge_id=None):
        """Submit progress for a challenge within this circle."""
        circle = self.get_object()

        # Verify membership
        if not CircleMembership.objects.filter(circle=circle, user=request.user).exists():
            return Response(
                {'error': 'You must be a member of the circle.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            challenge = CircleChallenge.objects.get(id=challenge_id, circle=circle)
        except CircleChallenge.DoesNotExist:
            return Response({'error': 'Challenge not found.'}, status=status.HTTP_404_NOT_FOUND)

        if not challenge.participants.filter(id=request.user.id).exists():
            return Response(
                {'error': 'You must join the challenge first.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = ChallengeProgressCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        progress = ChallengeProgress.objects.create(
            challenge=challenge,
            user=request.user,
            progress_value=serializer.validated_data['progress_value'],
            notes=serializer.validated_data.get('notes', ''),
        )

        return Response(
            ChallengeProgressSerializer(progress).data,
            status=status.HTTP_201_CREATED,
        )

    @extend_schema(
        summary="Challenge leaderboard",
        description="Get a leaderboard for a specific challenge based on total progress.",
        responses={
            200: dict,
            403: OpenApiResponse(description='Subscription required.'),
            404: OpenApiResponse(description='Resource not found.'),
        },
        tags=["Circles"],
    )
    @action(detail=True, methods=['get'], url_path=r'challenges/(?P<challenge_id>[0-9a-f-]+)/leaderboard')
    def challenge_leaderboard(self, request, pk=None, challenge_id=None):
        """Get leaderboard for a challenge, ranked by total progress."""
        circle = self.get_object()

        try:
            challenge = CircleChallenge.objects.get(id=challenge_id, circle=circle)
        except CircleChallenge.DoesNotExist:
            return Response({'error': 'Challenge not found.'}, status=status.HTTP_404_NOT_FOUND)

        from django.db.models import Sum

        rankings = (
            ChallengeProgress.objects
            .filter(challenge=challenge)
            .values('user__id', 'user__display_name', 'user__avatar_url')
            .annotate(total_progress=Sum('progress_value'))
            .order_by('-total_progress')
        )

        leaderboard = []
        for idx, entry in enumerate(rankings, start=1):
            leaderboard.append({
                'rank': idx,
                'user_id': str(entry['user__id']),
                'user_display_name': entry['user__display_name'] or 'Anonymous',
                'user_avatar_url': entry['user__avatar_url'] or '',
                'total_progress': entry['total_progress'] or 0,
                'is_current_user': entry['user__id'] == request.user.id,
            })

        return Response({
            'challenge_id': str(challenge.id),
            'challenge_title': challenge.title,
            'leaderboard': leaderboard,
        })


class ChallengeViewSet(viewsets.GenericViewSet):
    """
    ViewSet for challenge actions that operate outside a specific circle context.

    Supports joining challenges by ID. Requires premium+ subscription.
    """

    permission_classes = [IsAuthenticated, CanUseCircles]
    serializer_class = CircleChallengeSerializer
    queryset = CircleChallenge.objects.all()

    @extend_schema(
        summary="Join a challenge",
        description="Join a specific circle challenge. Must be a member of the circle.",
        responses={
            200: OpenApiResponse(description="Successfully joined the challenge."),
            400: OpenApiResponse(description="Already joined or not a circle member."),
            403: OpenApiResponse(description='Subscription required.'),
            404: OpenApiResponse(description='Resource not found.'),
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


class JoinByInviteCodeView(APIView):
    """Join a circle using an invite code. Requires premium+ subscription."""

    permission_classes = [IsAuthenticated, CanUseCircles]

    @extend_schema(
        summary="Join circle via invite code",
        description="Accept a circle invitation using a shareable invite code.",
        request=None,
        responses={
            200: OpenApiResponse(description="Successfully joined the circle."),
            400: OpenApiResponse(description="Already a member or circle is full."),
            403: OpenApiResponse(description='Subscription required.'),
            404: OpenApiResponse(description="Invalid or expired invite code."),
        },
        tags=["Circles"],
    )
    def post(self, request, invite_code):
        """Join a circle using an invite code."""
        try:
            invitation = CircleInvitation.objects.select_related('circle').get(
                invite_code=invite_code,
                status='pending',
            )
        except CircleInvitation.DoesNotExist:
            return Response(
                {'error': 'Invalid or expired invite code.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        if invitation.is_expired:
            invitation.status = 'expired'
            invitation.save(update_fields=['status'])
            return Response(
                {'error': 'This invitation has expired.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        circle = invitation.circle

        # If this is a direct invite, verify it's for this user
        if invitation.invitee and invitation.invitee != request.user:
            return Response(
                {'error': 'This invitation is for another user.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        if CircleMembership.objects.filter(circle=circle, user=request.user).exists():
            return Response(
                {'error': 'You are already a member of this circle.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if circle.is_full:
            return Response(
                {'error': 'This circle has reached its maximum number of members.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        CircleMembership.objects.create(
            circle=circle,
            user=request.user,
            role='member',
        )

        # Mark invitation as accepted (for direct invites)
        if invitation.invitee:
            invitation.status = 'accepted'
            invitation.save(update_fields=['status'])

        return Response({
            'message': f'Successfully joined {circle.name}.',
            'circle_id': str(circle.id),
        })


class MyInvitationsView(generics.ListAPIView):
    """List pending invitations received by the current user. Requires premium+."""

    permission_classes = [IsAuthenticated, CanUseCircles]
    serializer_class = CircleInvitationSerializer

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return CircleInvitation.objects.none()
        from django.utils import timezone as django_timezone
        return CircleInvitation.objects.filter(
            invitee=self.request.user,
            status='pending',
            expires_at__gt=django_timezone.now(),  # filter expired at DB level
        ).select_related('circle', 'inviter').order_by('-created_at')
