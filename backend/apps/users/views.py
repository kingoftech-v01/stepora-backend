"""
Views for Users app.
Authentication is handled by dj-rest-auth at /api/auth/ endpoints.
"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiResponse

import secrets
from datetime import timedelta
from django.utils import timezone

from .models import User, FcmToken, GamificationProfile, EmailChangeRequest
from .serializers import (
    UserSerializer, UserProfileSerializer, UserUpdateSerializer,
    FcmTokenSerializer, GamificationProfileSerializer,
)


@extend_schema_view(
    list=extend_schema(summary="List users", description="Get user list (current user only)", tags=["Users"]),
    retrieve=extend_schema(summary="Get user", description="Get a specific user", tags=["Users"]),
    update=extend_schema(summary="Update user", description="Update a user", tags=["Users"]),
    partial_update=extend_schema(summary="Partial update user", description="Partially update a user", tags=["Users"]),
    destroy=extend_schema(summary="Delete user", description="Delete a user", tags=["Users"]),
)
class UserViewSet(viewsets.ModelViewSet):
    """User management endpoints."""

    permission_classes = [IsAuthenticated]
    serializer_class = UserSerializer
    queryset = User.objects.all()

    def get_queryset(self):
        """Filter to only allow users to see their own data."""
        return User.objects.filter(id=self.request.user.id)

    @extend_schema(summary="Get current user", description="Get the current authenticated user's profile", tags=["Users"], responses={200: UserProfileSerializer})
    @action(detail=False, methods=['get'])
    def me(self, request):
        """Get current user profile."""
        serializer = UserProfileSerializer(request.user)
        return Response(serializer.data)

    @extend_schema(summary="Update profile", description="Update the current user's profile", tags=["Users"], request=UserUpdateSerializer, responses={200: UserSerializer})
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

    @extend_schema(summary="Register FCM token", description="Register a Firebase Cloud Messaging token for push notifications", tags=["Users"], responses={200: FcmTokenSerializer})
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

    @extend_schema(summary="Get gamification profile", description="Get the current user's gamification profile with XP and levels", tags=["Users"], responses={200: GamificationProfileSerializer})
    @action(detail=False, methods=['get'])
    def gamification(self, request):
        """Get gamification profile."""
        profile, created = GamificationProfile.objects.get_or_create(user=request.user)
        serializer = GamificationProfileSerializer(profile)
        return Response(serializer.data)

    @extend_schema(
        summary="Upload avatar",
        description="Upload an avatar image for the current user.",
        request={'multipart/form-data': {'type': 'object', 'properties': {'avatar': {'type': 'string', 'format': 'binary'}}}},
        responses={200: UserSerializer},
        tags=["Users"],
    )
    @action(detail=False, methods=['post'], parser_classes=[MultiPartParser, FormParser])
    def upload_avatar(self, request):
        """Upload avatar image for the current user."""
        avatar_file = request.FILES.get('avatar')
        if not avatar_file:
            return Response(
                {'error': 'No avatar file provided.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Validate file type
        allowed_types = ['image/jpeg', 'image/png', 'image/gif', 'image/webp']
        if avatar_file.content_type not in allowed_types:
            return Response(
                {'error': 'Invalid file type. Allowed: JPEG, PNG, GIF, WebP.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Validate file size (5MB max)
        if avatar_file.size > 5 * 1024 * 1024:
            return Response(
                {'error': 'File too large. Maximum size is 5MB.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        user = request.user
        # Delete old avatar image if exists
        if user.avatar_image:
            user.avatar_image.delete(save=False)

        user.avatar_image = avatar_file
        user.save(update_fields=['avatar_image'])

        return Response(UserSerializer(user).data)

    @extend_schema(summary="Get user statistics", description="Get comprehensive statistics for the current user", tags=["Users"], responses={200: dict})
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

    @extend_schema(
        summary="Delete account",
        description="Soft-delete the current user's account. Anonymizes personal data and deactivates the account.",
        responses={200: OpenApiResponse(description="Account scheduled for deletion.")},
        tags=["Users"],
    )
    @action(detail=False, methods=['delete'], url_path='delete-account')
    def delete_account(self, request):
        """
        Soft-delete user account (GDPR compliant).
        Anonymizes personal data and deactivates the account.
        A background task will hard-delete after 30 days.
        """
        user = request.user

        # Verify password for security
        password = request.data.get('password')
        if not password or not user.check_password(password):
            return Response(
                {'error': 'Invalid password. Please confirm your password to delete your account.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Anonymize personal data
        user.display_name = 'Deleted User'
        user.email = f'deleted_{user.id}@deleted.dreamplanner.app'
        user.avatar_url = ''
        if user.avatar_image:
            user.avatar_image.delete(save=False)
        user.bio = ''
        user.location = ''
        user.social_links = None
        user.notification_prefs = None
        user.app_prefs = None
        user.work_schedule = None
        user.is_active = False
        user.save()

        # Deactivate FCM tokens
        FcmToken.objects.filter(user=user).update(is_active=False)

        # Delete auth tokens
        from rest_framework.authtoken.models import Token
        Token.objects.filter(user=user).delete()

        return Response({
            'message': 'Account scheduled for deletion. Your data has been anonymized. '
                       'The account will be permanently deleted in 30 days.',
        })

    @extend_schema(
        summary="Export user data",
        description="Export all user data as JSON (GDPR data portability).",
        responses={200: dict},
        tags=["Users"],
    )
    @action(detail=False, methods=['get'], url_path='export-data')
    def export_data(self, request):
        """Export all user data as JSON for GDPR compliance."""
        user = request.user

        data = {
            'profile': {
                'email': user.email,
                'display_name': user.display_name,
                'bio': user.bio,
                'location': user.location,
                'timezone': user.timezone,
                'subscription': user.subscription,
                'level': user.level,
                'xp': user.xp,
                'streak_days': user.streak_days,
                'created_at': str(user.created_at),
            },
            'dreams': [],
            'notifications': [],
        }

        # Export dreams with goals and tasks
        for dream in user.dreams.all():
            dream_data = {
                'title': dream.title,
                'description': dream.description,
                'category': dream.category,
                'status': dream.status,
                'progress_percentage': dream.progress_percentage,
                'created_at': str(dream.created_at),
                'goals': [],
            }
            for goal in dream.goals.all():
                goal_data = {
                    'title': goal.title,
                    'description': goal.description,
                    'status': goal.status,
                    'tasks': list(goal.tasks.values('title', 'description', 'status', 'completed_at')),
                }
                dream_data['goals'].append(goal_data)
            data['dreams'].append(dream_data)

        # Export notifications
        from apps.notifications.models import Notification
        for notif in Notification.objects.filter(user=user).order_by('-created_at')[:200]:
            data['notifications'].append({
                'type': notif.notification_type,
                'title': notif.title,
                'body': notif.body,
                'created_at': str(notif.created_at),
            })

        return Response(data)

    @extend_schema(
        summary="Change email",
        description="Request to change the user's email address. Sends a verification email to the new address.",
        responses={200: OpenApiResponse(description="Verification email sent.")},
        tags=["Users"],
    )
    @action(detail=False, methods=['post'], url_path='change-email')
    def change_email(self, request):
        """Request email change with verification."""
        new_email = request.data.get('new_email', '').strip()
        password = request.data.get('password', '')

        if not new_email:
            return Response(
                {'error': 'new_email is required.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not password or not request.user.check_password(password):
            return Response(
                {'error': 'Invalid password.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Check if email is already taken
        if User.objects.filter(email=new_email).exclude(id=request.user.id).exists():
            return Response(
                {'error': 'This email is already in use.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Invalidate previous requests
        EmailChangeRequest.objects.filter(
            user=request.user, is_verified=False
        ).delete()

        # Create new request
        token = secrets.token_urlsafe(64)
        EmailChangeRequest.objects.create(
            user=request.user,
            new_email=new_email,
            token=token,
            expires_at=timezone.now() + timedelta(hours=24),
        )

        # Send verification email via Celery task
        from .tasks import send_email_change_verification
        send_email_change_verification.delay(request.user.id, new_email, token)

        return Response({
            'message': 'Verification email sent to the new address. Please check your inbox.',
        })

    @extend_schema(
        summary="Update notification preferences",
        description="Update per-type notification preferences (push/email toggles).",
        responses={200: UserSerializer},
        tags=["Users"],
    )
    @action(detail=False, methods=['put'], url_path='notification-preferences')
    def notification_preferences(self, request):
        """Update notification preferences."""
        prefs = request.data

        # Validate structure
        if not isinstance(prefs, dict):
            return Response(
                {'error': 'Expected a JSON object with notification preferences.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        user = request.user
        user.notification_prefs = prefs
        user.save(update_fields=['notification_prefs'])

        return Response(UserSerializer(user).data)


