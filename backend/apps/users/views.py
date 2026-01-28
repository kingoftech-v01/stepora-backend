"""
Views for Users app.
"""

from django.db import models
from rest_framework import viewsets, status, views
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.utils import timezone
from .models import User, FcmToken, GamificationProfile, DreamBuddy
from .serializers import (
    UserSerializer, UserProfileSerializer, UserUpdateSerializer,
    FcmTokenSerializer, GamificationProfileSerializer, DreamBuddySerializer
)
from .services import BuddyMatchingService


class AuthViewSet(viewsets.ViewSet):
    """Authentication endpoints."""

    permission_classes = [AllowAny]

    @action(detail=False, methods=['post'])
    def register(self, request):
        """Register a new user."""
        firebase_uid = request.data.get('firebase_uid')
        email = request.data.get('email')

        if not firebase_uid or not email:
            return Response(
                {'error': 'firebase_uid and email are required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Create or get user
        user, created = User.objects.get_or_create(
            firebase_uid=firebase_uid,
            defaults={
                'email': email,
                'display_name': request.data.get('display_name', ''),
                'timezone': request.data.get('timezone', 'Europe/Paris'),
            }
        )

        # Create gamification profile
        if created:
            GamificationProfile.objects.create(user=user)

        # Register FCM token if provided
        fcm_token = request.data.get('fcm_token')
        if fcm_token:
            FcmToken.objects.get_or_create(
                user=user,
                token=fcm_token,
                defaults={'platform': request.data.get('platform', 'android')}
            )

        serializer = UserSerializer(user)
        return Response(
            serializer.data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK
        )


class UserViewSet(viewsets.ModelViewSet):
    """User management endpoints."""

    permission_classes = [IsAuthenticated]
    serializer_class = UserSerializer
    queryset = User.objects.all()

    def get_queryset(self):
        """Filter to only allow users to see their own data."""
        return User.objects.filter(id=self.request.user.id)

    @action(detail=False, methods=['get'])
    def me(self, request):
        """Get current user profile."""
        serializer = UserProfileSerializer(request.user)
        return Response(serializer.data)

    @action(detail=False, methods=['put', 'patch'])
    def update_profile(self, request):
        """Update current user profile."""
        serializer = UserUpdateSerializer(
            request.user,
            data=request.data,
            partial=True
        )

        if serializer.is_valid():
            serializer.save()
            return Response(UserSerializer(request.user).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['post'])
    def register_fcm_token(self, request):
        """Register FCM token for push notifications."""
        token = request.data.get('token')
        platform = request.data.get('platform', 'android')

        if not token:
            return Response(
                {'error': 'token is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Deactivate old tokens for this user
        FcmToken.objects.filter(user=request.user).update(is_active=False)

        # Create new token
        fcm_token, created = FcmToken.objects.get_or_create(
            user=request.user,
            token=token,
            defaults={'platform': platform, 'is_active': True}
        )

        if not created:
            fcm_token.is_active = True
            fcm_token.save()

        serializer = FcmTokenSerializer(fcm_token)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def gamification(self, request):
        """Get gamification profile."""
        profile, created = GamificationProfile.objects.get_or_create(user=request.user)
        serializer = GamificationProfileSerializer(profile)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Get user statistics."""
        user = request.user

        stats = {
            'level': user.level,
            'xp': user.xp,
            'streak_days': user.streak_days,
            'total_dreams': user.dreams.count(),
            'active_dreams': user.dreams.filter(status='active').count(),
            'completed_dreams': user.dreams.filter(status='completed').count(),
            'total_tasks_completed': sum(
                goal.tasks.filter(status='completed').count()
                for dream in user.dreams.all()
                for goal in dream.goals.all()
            ),
        }

        return Response(stats)


class DreamBuddyViewSet(viewsets.ModelViewSet):
    """Dream Buddy pairing endpoints."""

    permission_classes = [IsAuthenticated]
    serializer_class = DreamBuddySerializer

    def get_queryset(self):
        """Get buddy pairings for current user."""
        user = self.request.user
        return DreamBuddy.objects.filter(
            user1=user
        ) | DreamBuddy.objects.filter(
            user2=user
        )

    @action(detail=False, methods=['post'])
    def find_buddy(self, request):
        """Find a compatible dream buddy."""
        user = request.user

        # Check if user already has an active buddy
        existing_active = DreamBuddy.objects.filter(
            (models.Q(user1=user) | models.Q(user2=user)),
            status='active'
        ).first()

        if existing_active:
            return Response({
                'message': 'You already have an active buddy',
                'buddy': DreamBuddySerializer(existing_active).data
            }, status=status.HTTP_400_BAD_REQUEST)

        # Check for pending requests
        pending_request = DreamBuddy.objects.filter(
            user1=user,
            status='pending'
        ).first()

        if pending_request:
            return Response({
                'message': 'You have a pending buddy request',
                'buddy': DreamBuddySerializer(pending_request).data
            }, status=status.HTTP_400_BAD_REQUEST)

        # Find a compatible buddy
        service = BuddyMatchingService()
        result = service.find_compatible_buddy(user)

        if not result:
            return Response({
                'message': 'No compatible buddy found at the moment',
                'suggestion': 'Try again later or update your profile to improve matching'
            }, status=status.HTTP_404_NOT_FOUND)

        matched_user, compatibility_score, shared_categories = result

        # Create buddy pairing
        buddy_pair = service.create_buddy_request(
            requesting_user=user,
            target_user=matched_user,
            compatibility_score=compatibility_score,
            shared_categories=shared_categories
        )

        return Response({
            'message': 'Buddy request sent successfully',
            'buddy': DreamBuddySerializer(buddy_pair).data,
            'compatibility_score': round(compatibility_score * 100, 1),
            'shared_categories': shared_categories
        }, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def accept(self, request, pk=None):
        """Accept a buddy pairing."""
        buddy_pair = self.get_object()

        if buddy_pair.user2 != request.user:
            return Response(
                {'error': 'You can only accept pairings sent to you'},
                status=status.HTTP_403_FORBIDDEN
            )

        buddy_pair.status = 'active'
        buddy_pair.started_at = timezone.now()
        buddy_pair.save()

        return Response(DreamBuddySerializer(buddy_pair).data)

    @action(detail=True, methods=['post'])
    def decline(self, request, pk=None):
        """Decline a buddy pairing."""
        buddy_pair = self.get_object()

        if buddy_pair.user2 != request.user:
            return Response(
                {'error': 'You can only decline pairings sent to you'},
                status=status.HTTP_403_FORBIDDEN
            )

        buddy_pair.status = 'cancelled'
        buddy_pair.save()

        return Response(DreamBuddySerializer(buddy_pair).data)
