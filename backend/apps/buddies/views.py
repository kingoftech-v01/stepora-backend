"""
Views for the Buddies system.

Provides API endpoints for Dream Buddy pairing, including finding matches,
creating pairings, tracking progress, sending encouragement, and ending
partnerships. All endpoints require authentication.
"""

import random

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Q, Count
from django.utils import timezone as django_timezone
from drf_spectacular.utils import (
    extend_schema,
    OpenApiResponse,
)

from apps.users.models import User
from .models import BuddyPairing, BuddyEncouragement
from .serializers import (
    BuddyPairingSerializer,
    BuddyProgressSerializer,
    BuddyMatchSerializer,
    BuddyPairRequestSerializer,
    BuddyEncourageSerializer,
)


class BuddyViewSet(viewsets.GenericViewSet):
    """
    ViewSet for Dream Buddy management.

    Supports finding matches, creating pairings, viewing progress,
    sending encouragement, and ending pairings.
    """

    permission_classes = [IsAuthenticated]
    queryset = BuddyPairing.objects.all()

    def _get_partner_data(self, user):
        """Build partner data dict from a User object."""
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

    def _get_active_pairing(self, user):
        """Find the user's current active buddy pairing."""
        return BuddyPairing.objects.filter(
            Q(user1=user) | Q(user2=user),
            status='active'
        ).select_related('user1', 'user2').first()

    def _get_partner_user(self, pairing, user):
        """Get the partner user from a pairing."""
        return pairing.user2 if pairing.user1_id == user.id else pairing.user1

    @extend_schema(
        summary="Get current buddy",
        description=(
            "Retrieve the current user's active buddy pairing. "
            "Returns null buddy if no active pairing exists."
        ),
        responses={200: BuddyPairingSerializer},
        tags=["Buddies"],
    )
    @action(detail=False, methods=['get'], url_path='current')
    def current(self, request):
        """
        Get the current active buddy pairing.

        Returns the pairing details including partner info and recent
        activity stats. Returns null buddy if no active pairing exists.
        """
        pairing = self._get_active_pairing(request.user)

        if not pairing:
            return Response({'buddy': None})

        partner = self._get_partner_user(pairing, request.user)

        # Calculate recent activity (tasks in last 7 days)
        from datetime import timedelta
        week_ago = django_timezone.now() - timedelta(days=7)
        recent_tasks = 0
        try:
            from apps.dreams.models import Task
            recent_tasks = Task.objects.filter(
                dream__user=partner,
                completed_at__gte=week_ago,
                status='completed'
            ).count()
        except (ImportError, Exception):
            recent_tasks = 0

        buddy_data = {
            'id': pairing.id,
            'partner': self._get_partner_data(partner),
            'compatibilityScore': pairing.compatibility_score,
            'status': pairing.status,
            'recentActivity': recent_tasks,
            'createdAt': pairing.created_at,
        }

        serializer = BuddyPairingSerializer(buddy_data)
        return Response({'buddy': serializer.data})

    @extend_schema(
        summary="Get buddy progress",
        description="Retrieve progress comparison between the current user and their buddy.",
        responses={200: BuddyProgressSerializer},
        tags=["Buddies"],
    )
    @action(detail=True, methods=['get'], url_path='progress')
    def progress(self, request, pk=None):
        """
        Get progress comparison for a buddy pairing.

        Returns side-by-side stats including streak, weekly tasks,
        and influence score for both users.
        """
        try:
            pairing = BuddyPairing.objects.select_related(
                'user1', 'user2'
            ).get(
                id=pk,
                status='active'
            )
        except BuddyPairing.DoesNotExist:
            return Response(
                {'error': 'Active buddy pairing not found.'},
                status=status.HTTP_404_NOT_FOUND
            )

        # Verify the user is part of this pairing
        if pairing.user1_id != request.user.id and pairing.user2_id != request.user.id:
            return Response(
                {'error': 'You are not part of this pairing.'},
                status=status.HTTP_403_FORBIDDEN
            )

        partner = self._get_partner_user(pairing, request.user)

        # Calculate weekly tasks for both users
        from datetime import timedelta
        week_ago = django_timezone.now() - timedelta(days=7)

        user_tasks_week = 0
        partner_tasks_week = 0
        try:
            from apps.dreams.models import Task
            user_tasks_week = Task.objects.filter(
                dream__user=request.user,
                completed_at__gte=week_ago,
                status='completed'
            ).count()
            partner_tasks_week = Task.objects.filter(
                dream__user=partner,
                completed_at__gte=week_ago,
                status='completed'
            ).count()
        except (ImportError, Exception):
            pass

        progress_data = {
            'user': {
                'currentStreak': request.user.streak_days,
                'tasksThisWeek': user_tasks_week,
                'influenceScore': request.user.xp,
            },
            'partner': {
                'currentStreak': partner.streak_days,
                'tasksThisWeek': partner_tasks_week,
                'influenceScore': partner.xp,
            },
        }

        serializer = BuddyProgressSerializer(progress_data)
        return Response({'progress': serializer.data})

    @extend_schema(
        summary="Find a buddy match",
        description=(
            "Find a compatible buddy match based on shared interests and activity level. "
            "Returns a potential match or null if no suitable match is found."
        ),
        responses={
            200: BuddyMatchSerializer,
            400: OpenApiResponse(description="Already have an active buddy."),
        },
        tags=["Buddies"],
    )
    @action(detail=False, methods=['post'], url_path='find-match')
    def find_match(self, request):
        """
        Find a compatible buddy match.

        Searches for available users without an active pairing who
        have similar activity levels and interests. Returns a match
        suggestion with compatibility score.
        """
        # Check if user already has an active pairing
        existing = self._get_active_pairing(request.user)
        if existing:
            return Response(
                {'error': 'You already have an active buddy pairing.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Find users without active pairings
        active_pairing_user_ids = set()
        active_pairings = BuddyPairing.objects.filter(status='active')
        for p in active_pairings:
            active_pairing_user_ids.add(p.user1_id)
            active_pairing_user_ids.add(p.user2_id)

        # Find candidates (active users, not already paired, not self)
        candidates = User.objects.filter(
            is_active=True
        ).exclude(
            id__in=active_pairing_user_ids
        ).exclude(
            id=request.user.id
        ).order_by('-last_activity')[:50]

        if not candidates.exists():
            return Response({'match': None})

        # Score candidates based on compatibility
        best_match = None
        best_score = 0.0

        user_level = request.user.level
        user_xp = request.user.xp

        for candidate in candidates:
            # Calculate compatibility based on level proximity and activity
            level_diff = abs(candidate.level - user_level)
            level_score = max(0.0, 1.0 - (level_diff / 50.0))

            xp_diff = abs(candidate.xp - user_xp)
            xp_score = max(0.0, 1.0 - (xp_diff / 10000.0))

            # Activity recency score
            days_since_activity = (django_timezone.now() - candidate.last_activity).days
            activity_score = max(0.0, 1.0 - (days_since_activity / 30.0))

            score = (level_score * 0.3) + (xp_score * 0.3) + (activity_score * 0.4)

            if score > best_score:
                best_score = score
                best_match = candidate

        if not best_match:
            return Response({'match': None})

        # Determine shared interests (based on gamification if available)
        shared_interests = []
        try:
            user_gam = request.user.gamification
            match_gam = best_match.gamification
            categories = ['health', 'career', 'relationships', 'personal_growth', 'finance', 'hobbies']
            for cat in categories:
                user_xp_attr = getattr(user_gam, f'{cat}_xp', 0)
                match_xp_attr = getattr(match_gam, f'{cat}_xp', 0)
                if user_xp_attr > 0 and match_xp_attr > 0:
                    shared_interests.append(cat)
        except Exception:
            shared_interests = []

        match_data = {
            'userId': best_match.id,
            'username': best_match.display_name or 'Anonymous',
            'avatar': best_match.avatar_url or '',
            'compatibilityScore': round(best_score, 2),
            'sharedInterests': shared_interests,
        }

        serializer = BuddyMatchSerializer(match_data)
        return Response({'match': serializer.data})

    @extend_schema(
        summary="Create a buddy pairing",
        description="Pair with a specific user to become accountability buddies.",
        request=BuddyPairRequestSerializer,
        responses={
            201: OpenApiResponse(description="Buddy pairing created."),
            400: OpenApiResponse(description="Already have a buddy or invalid partner."),
        },
        tags=["Buddies"],
    )
    @action(detail=False, methods=['post'], url_path='pair')
    def pair(self, request):
        """
        Create a buddy pairing with a specific user.

        Both users must not have an existing active pairing.
        The pairing is automatically set to 'active' status.
        """
        serializer = BuddyPairRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        partner_id = serializer.validated_data['partnerId']

        if partner_id == request.user.id:
            return Response(
                {'error': 'You cannot pair with yourself.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Check user doesn't already have active pairing
        existing = self._get_active_pairing(request.user)
        if existing:
            return Response(
                {'error': 'You already have an active buddy pairing.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            partner = User.objects.get(id=partner_id)
        except User.DoesNotExist:
            return Response(
                {'error': 'Partner user not found.'},
                status=status.HTTP_404_NOT_FOUND
            )

        # Check partner doesn't already have active pairing
        partner_pairing = BuddyPairing.objects.filter(
            Q(user1=partner) | Q(user2=partner),
            status='active'
        ).exists()

        if partner_pairing:
            return Response(
                {'error': 'This user already has an active buddy pairing.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Calculate compatibility score
        level_diff = abs(partner.level - request.user.level)
        level_score = max(0.0, 1.0 - (level_diff / 50.0))
        xp_diff = abs(partner.xp - request.user.xp)
        xp_score = max(0.0, 1.0 - (xp_diff / 10000.0))
        compatibility = round((level_score + xp_score) / 2, 2)

        pairing = BuddyPairing.objects.create(
            user1=request.user,
            user2=partner,
            status='active',
            compatibility_score=compatibility
        )

        return Response(
            {
                'message': f'Buddy pairing created with {partner.display_name or "user"}.',
                'pairing_id': str(pairing.id),
            },
            status=status.HTTP_201_CREATED
        )

    @extend_schema(
        summary="Send encouragement",
        description="Send an encouragement message to your buddy partner.",
        request=BuddyEncourageSerializer,
        responses={
            200: OpenApiResponse(description="Encouragement sent."),
            404: OpenApiResponse(description="Pairing not found."),
        },
        tags=["Buddies"],
    )
    @action(detail=True, methods=['post'], url_path='encourage')
    def encourage(self, request, pk=None):
        """
        Send encouragement to a buddy.

        Creates an encouragement record and optionally triggers a
        notification to the partner.
        """
        try:
            pairing = BuddyPairing.objects.get(
                id=pk,
                status='active'
            )
        except BuddyPairing.DoesNotExist:
            return Response(
                {'error': 'Active buddy pairing not found.'},
                status=status.HTTP_404_NOT_FOUND
            )

        # Verify the user is part of this pairing
        if pairing.user1_id != request.user.id and pairing.user2_id != request.user.id:
            return Response(
                {'error': 'You are not part of this pairing.'},
                status=status.HTTP_403_FORBIDDEN
            )

        serializer = BuddyEncourageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        BuddyEncouragement.objects.create(
            pairing=pairing,
            sender=request.user,
            message=serializer.validated_data.get('message', '')
        )

        # Determine the partner
        partner = pairing.user2 if pairing.user1_id == request.user.id else pairing.user1

        # Try to send a notification (best-effort)
        try:
            from apps.notifications.models import Notification
            Notification.objects.create(
                user=partner,
                title='Buddy Encouragement',
                body=serializer.validated_data.get('message', '') or
                     f'{request.user.display_name or "Your buddy"} sent you encouragement!',
                notification_type='buddy_encourage',
                data={'pairing_id': str(pairing.id)},
            )
        except (ImportError, Exception):
            pass

        return Response({
            'message': f'Encouragement sent to {partner.display_name or "your buddy"}.'
        })

    @extend_schema(
        summary="End buddy pairing",
        description="End an active buddy pairing. Sets status to cancelled.",
        responses={
            200: OpenApiResponse(description="Pairing ended."),
            404: OpenApiResponse(description="Pairing not found."),
        },
        tags=["Buddies"],
    )
    def destroy(self, request, pk=None):
        """
        End a buddy pairing.

        Sets the pairing status to 'cancelled' and records the end time.
        The pairing is not actually deleted from the database.
        """
        try:
            pairing = BuddyPairing.objects.get(
                id=pk,
                status='active'
            )
        except BuddyPairing.DoesNotExist:
            return Response(
                {'error': 'Active buddy pairing not found.'},
                status=status.HTTP_404_NOT_FOUND
            )

        # Verify the user is part of this pairing
        if pairing.user1_id != request.user.id and pairing.user2_id != request.user.id:
            return Response(
                {'error': 'You are not part of this pairing.'},
                status=status.HTTP_403_FORBIDDEN
            )

        pairing.status = 'cancelled'
        pairing.ended_at = django_timezone.now()
        pairing.save(update_fields=['status', 'ended_at', 'updated_at'])

        return Response({'message': 'Buddy pairing ended.'})
