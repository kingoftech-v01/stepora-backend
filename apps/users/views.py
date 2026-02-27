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

import logging
import secrets
from datetime import timedelta
from django.utils import timezone
from django.db.models import Q, Count

logger = logging.getLogger(__name__)

from .models import User, GamificationProfile, EmailChangeRequest, DailyActivity, Achievement, UserAchievement
from .serializers import (
    UserSerializer, UserProfileSerializer, UserUpdateSerializer,
    GamificationProfileSerializer,
)
from core.audit import log_data_export, log_account_change
from core.throttles import ExportRateThrottle
from core.ai_usage import AIUsageTracker


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
        if getattr(self, 'swagger_fake_view', False):
            return User.objects.none()
        return User.objects.filter(id=self.request.user.id)

    def retrieve(self, request, *args, **kwargs):
        """Get a user's public profile by ID."""
        user_id = kwargs.get('pk')
        try:
            target_user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response(
                {'error': 'User not found.'},
                status=status.HTTP_404_NOT_FOUND
            )
        # Return public profile data (no email, no private settings)
        from apps.dreams.models import Dream
        from apps.social.models import Friendship
        dreams = Dream.objects.filter(
            user=target_user, status='active'
        ).values_list('title', flat=True)[:10]
        categories = list(
            Dream.objects.filter(user=target_user, status='active')
            .values_list('category', flat=True).distinct()
        )
        friend_count = Friendship.objects.filter(
            Q(user1=target_user) | Q(user2=target_user),
            status='accepted'
        ).count()
        mutual = 0
        if request.user != target_user:
            my_friend_ids = set(
                Friendship.objects.filter(
                    Q(user1=request.user) | Q(user2=request.user),
                    status='accepted'
                ).values_list('user1_id', 'user2_id')
            )
            my_friends = set()
            for u1, u2 in my_friend_ids:
                my_friends.add(u1)
                my_friends.add(u2)
            my_friends.discard(request.user.id)
            their_friend_ids = set(
                Friendship.objects.filter(
                    Q(user1=target_user) | Q(user2=target_user),
                    status='accepted'
                ).values_list('user1_id', 'user2_id')
            )
            their_friends = set()
            for u1, u2 in their_friend_ids:
                their_friends.add(u1)
                their_friends.add(u2)
            their_friends.discard(target_user.id)
            mutual = len(my_friends & their_friends)

        is_friend = Friendship.objects.filter(
            Q(user1=request.user, user2=target_user) | Q(user1=target_user, user2=request.user),
            status='accepted'
        ).exists()

        return Response({
            'id': str(target_user.id),
            'displayName': target_user.display_name,
            'name': target_user.display_name,
            'initial': (target_user.display_name or 'U')[0].upper(),
            'bio': target_user.bio or '',
            'location': target_user.location or '',
            'avatarUrl': target_user.avatar_url or '',
            'level': target_user.level,
            'xp': target_user.xp,
            'streak': target_user.streak_days,
            'isOnline': target_user.is_online,
            'isFriend': is_friend,
            'mutualFriends': mutual,
            'friendCount': friend_count,
            'dreams': list(dreams),
            'categories': categories,
            'dateJoined': target_user.created_at.strftime('%b %Y') if target_user.created_at else '',
        })

    @extend_schema(summary="Get current user", description="Get the current authenticated user's profile", tags=["Users"], responses={200: UserProfileSerializer, 404: OpenApiResponse(description='Resource not found.')})
    @action(detail=False, methods=['get'])
    def me(self, request):
        """Get current user profile."""
        serializer = UserProfileSerializer(request.user)
        return Response(serializer.data)

    @extend_schema(summary="Update profile", description="Update the current user's profile", tags=["Users"], request=UserUpdateSerializer, responses={200: UserSerializer, 400: OpenApiResponse(description='Validation error.')})
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

    @extend_schema(summary="Get gamification profile", description="Get the current user's gamification profile with XP and levels", tags=["Users"], responses={200: GamificationProfileSerializer, 404: OpenApiResponse(description='Resource not found.')})
    @action(detail=False, methods=['get'])
    def gamification(self, request):
        """Get gamification profile."""
        profile, created = GamificationProfile.objects.get_or_create(user=request.user)
        serializer = GamificationProfileSerializer(profile)
        return Response(serializer.data)

    @extend_schema(summary="Get AI usage", description="Get the current user's AI usage quotas for today", tags=["Users"], responses={200: dict, 404: OpenApiResponse(description='Resource not found.')})
    @action(detail=False, methods=['get'], url_path='ai-usage')
    def ai_usage(self, request):
        """Get current user's AI usage and remaining quotas for today."""
        tracker = AIUsageTracker()
        usage = tracker.get_usage(request.user)
        reset_time = tracker.get_reset_time()

        return Response({
            'date': timezone.now().date().isoformat(),
            'usage': usage,
            'plan': getattr(request.user, 'subscription', 'free'),
            'resets_at': reset_time.isoformat(),
        })

    @extend_schema(
        summary="Upload avatar",
        description="Upload an avatar image for the current user.",
        request={'multipart/form-data': {'type': 'object', 'properties': {'avatar': {'type': 'string', 'format': 'binary'}}}},
        responses={
            200: UserSerializer,
            400: OpenApiResponse(description='Validation error.'),
        },
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
        from apps.dreams.models import Task
        user = request.user

        stats = {
            'level': user.level,
            'xp': user.xp,
            'streak_days': user.streak_days,
            'total_dreams': user.dreams.count(),
            'active_dreams': user.dreams.filter(status='active').count(),
            'completed_dreams': user.dreams.filter(status='completed').count(),
            'total_tasks_completed': Task.objects.filter(
                goal__dream__user=user, status='completed'
            ).count(),
        }

        return Response(stats)

    @extend_schema(
        summary="Delete account",
        description="Soft-delete the current user's account. Anonymizes personal data and deactivates the account.",
        responses={
            200: OpenApiResponse(description="Account scheduled for deletion."),
            400: OpenApiResponse(description='Validation error.'),
        },
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

        log_account_change(user, 'account_deletion')

        # Cancel Stripe subscription if active
        try:
            from apps.subscriptions.services import StripeService
            StripeService.cancel_subscription(user)
        except Exception:
            logger.exception(
                "Failed to cancel Stripe subscription for user %s during deletion", user.id
            )

        # End active buddy pairings
        try:
            from apps.buddies.models import BuddyPairing
            BuddyPairing.objects.filter(
                Q(user1=user) | Q(user2=user),
                status__in=['pending', 'active']
            ).update(status='cancelled', ended_at=timezone.now())
        except Exception:
            logger.exception(
                "Failed to end buddy pairings for user %s during deletion", user.id
            )

        # Remove from circles
        try:
            from apps.circles.models import CircleMembership
            CircleMembership.objects.filter(user=user).delete()
        except Exception:
            logger.exception(
                "Failed to remove circle memberships for user %s during deletion", user.id
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
        responses={
            200: dict,
            429: OpenApiResponse(description='Rate limit exceeded.'),
        },
        tags=["Users"],
    )
    @action(detail=False, methods=['get'], url_path='export-data', throttle_classes=[ExportRateThrottle])
    def export_data(self, request):
        """Export all user data as JSON for GDPR compliance."""
        user = request.user
        log_data_export(user)

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
        responses={
            200: OpenApiResponse(description="Verification email sent."),
            400: OpenApiResponse(description='Validation error.'),
        },
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

    @extend_schema(summary="Get dashboard", description="Aggregated dashboard data: heatmap, stats, upcoming tasks, top dreams", tags=["Users"], responses={200: dict, 404: OpenApiResponse(description='Resource not found.')})
    @action(detail=False, methods=['get'])
    def dashboard(self, request):
        """Get aggregated dashboard data for the home screen."""
        user = request.user

        # Heatmap: last 28 days of DailyActivity
        from datetime import date, timedelta as td
        today = date.today()
        start_date = today - td(days=27)
        activities = DailyActivity.objects.filter(
            user=user, date__gte=start_date
        ).order_by('date')
        activity_map = {a.date: a for a in activities}
        heatmap = []
        for i in range(28):
            d = start_date + td(days=i)
            a = activity_map.get(d)
            heatmap.append({
                'date': str(d),
                'tasks_completed': a.tasks_completed if a else 0,
                'xp_earned': a.xp_earned if a else 0,
                'minutes_active': a.minutes_active if a else 0,
            })

        # Stats
        from apps.dreams.models import Dream, Task
        week_start = today - td(days=6)
        completed_tasks_week = Task.objects.filter(
            goal__dream__user=user,
            status='completed',
            completed_at__date__gte=week_start,
        ).count()

        stats = {
            'active_dreams': Dream.objects.filter(user=user, status='active').count(),
            'completed_tasks_week': completed_tasks_week,
            'streak_days': user.streak_days,
            'xp': user.xp,
            'level': user.level,
        }

        # Upcoming tasks: next 5 scheduled tasks
        upcoming_tasks = Task.objects.filter(
            goal__dream__user=user,
            status='pending',
            scheduled_date__gte=timezone.now(),
        ).select_related('goal__dream').order_by('scheduled_date')[:5]
        upcoming_list = [
            {
                'id': str(t.id),
                'title': t.title,
                'scheduled_date': t.scheduled_date,
                'duration_mins': t.duration_mins,
                'dream_title': t.goal.dream.title,
                'dream_id': str(t.goal.dream.id),
            }
            for t in upcoming_tasks
        ]

        # Top 3 active dreams with sparkline
        from apps.dreams.models import DreamProgressSnapshot
        top_dreams = Dream.objects.filter(
            user=user, status='active'
        ).order_by('-updated_at')[:3]
        dreams_data = []
        for dream in top_dreams:
            snapshots = DreamProgressSnapshot.objects.filter(
                dream=dream
            ).order_by('-date')[:7]
            sparkline = list(reversed([
                {'date': str(s.date), 'progress': s.progress_percentage}
                for s in snapshots
            ]))
            dreams_data.append({
                'id': str(dream.id),
                'title': dream.title,
                'category': dream.category,
                'progress_percentage': dream.progress_percentage,
                'sparkline_data': sparkline,
            })

        return Response({
            'heatmap': heatmap,
            'stats': stats,
            'upcoming_tasks': upcoming_list,
            'top_dreams': dreams_data,
        })

    @extend_schema(summary="Get achievements", description="List all achievements with unlock status", tags=["Users"], responses={200: dict, 404: OpenApiResponse(description='Resource not found.')})
    @action(detail=False, methods=['get'])
    def achievements(self, request):
        """Get all achievements with user unlock status."""
        user = request.user
        all_achievements = Achievement.objects.filter(is_active=True)
        unlocked_ids = set(
            UserAchievement.objects.filter(user=user).values_list('achievement_id', flat=True)
        )
        unlocked_map = {
            ua.achievement_id: ua.unlocked_at
            for ua in UserAchievement.objects.filter(user=user)
        }

        results = []
        for ach in all_achievements:
            is_unlocked = ach.id in unlocked_ids
            results.append({
                'id': str(ach.id),
                'name': ach.name,
                'description': ach.description,
                'icon': ach.icon,
                'category': ach.category,
                'xp_reward': ach.xp_reward,
                'condition_type': ach.condition_type,
                'condition_value': ach.condition_value,
                'unlocked': is_unlocked,
                'unlocked_at': unlocked_map.get(ach.id),
            })

        return Response({
            'achievements': results,
            'unlocked_count': len(unlocked_ids),
            'total_count': all_achievements.count(),
        })

    @extend_schema(
        summary="Update notification preferences",
        description="Update per-type notification preferences (push/email toggles).",
        responses={
            200: UserSerializer,
            400: OpenApiResponse(description='Validation error.'),
        },
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

    # ── Two-Factor Authentication ────────────────────────────────────

    @extend_schema(
        summary="Setup 2FA",
        description="Generate TOTP secret and return provisioning URI for authenticator apps.",
        responses={200: dict},
        tags=["Users"],
    )
    @action(detail=False, methods=['post'], url_path='2fa/setup')
    def setup_2fa(self, request):
        """Generate TOTP secret and return OTP auth URI."""
        import pyotp
        user = request.user
        if user.totp_enabled:
            return Response(
                {'error': '2FA is already enabled.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        secret = pyotp.random_base32()
        user.totp_secret = secret
        user.save(update_fields=['totp_secret'])
        totp = pyotp.TOTP(secret)
        uri = totp.provisioning_uri(name=user.email, issuer_name='DreamPlanner')
        return Response({'secret': secret, 'otpauth_url': uri})

    @extend_schema(
        summary="Verify 2FA setup",
        description="Verify TOTP code to complete 2FA activation.",
        request={'application/json': {'type': 'object', 'properties': {'code': {'type': 'string'}}}},
        responses={200: dict},
        tags=["Users"],
    )
    @action(detail=False, methods=['post'], url_path='2fa/verify-setup')
    def verify_2fa_setup(self, request):
        """Verify TOTP code to complete 2FA setup."""
        import pyotp
        code = request.data.get('code', '')
        user = request.user
        if not user.totp_secret:
            return Response(
                {'error': 'Run 2FA setup first.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        totp = pyotp.TOTP(user.totp_secret)
        if totp.verify(code):
            user.totp_enabled = True
            user.save(update_fields=['totp_enabled'])
            return Response({'message': '2FA enabled successfully.'})
        return Response(
            {'error': 'Invalid code.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    @extend_schema(
        summary="Disable 2FA",
        description="Disable two-factor authentication. Requires password and current TOTP code.",
        request={'application/json': {'type': 'object', 'properties': {'password': {'type': 'string'}, 'code': {'type': 'string'}}}},
        responses={200: dict},
        tags=["Users"],
    )
    @action(detail=False, methods=['post'], url_path='2fa/disable')
    def disable_2fa(self, request):
        """Disable 2FA — requires password + TOTP code."""
        import pyotp
        user = request.user
        password = request.data.get('password', '')
        code = request.data.get('code', '')
        if not user.check_password(password):
            return Response(
                {'error': 'Invalid password.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        if not user.totp_enabled:
            return Response(
                {'error': '2FA is not enabled.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        totp = pyotp.TOTP(user.totp_secret)
        if not totp.verify(code):
            return Response(
                {'error': 'Invalid 2FA code.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        user.totp_enabled = False
        user.totp_secret = ''
        user.backup_codes = None
        user.save(update_fields=['totp_enabled', 'totp_secret', 'backup_codes'])
        return Response({'message': '2FA disabled.'})

    @extend_schema(
        summary="Generate backup codes",
        description="Generate 10 one-time backup codes for 2FA recovery. Requires 2FA to be enabled.",
        responses={200: dict},
        tags=["Users"],
    )
    @action(detail=False, methods=['post'], url_path='2fa/backup-codes')
    def generate_backup_codes(self, request):
        """Generate 10 one-time backup codes."""
        import hashlib
        user = request.user
        if not user.totp_enabled:
            return Response(
                {'error': '2FA must be enabled first.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        codes = [secrets.token_hex(4) for _ in range(10)]
        hashed = [hashlib.sha256(c.encode()).hexdigest() for c in codes]
        user.backup_codes = hashed
        user.save(update_fields=['backup_codes'])
        return Response({
            'backup_codes': codes,
            'message': 'Save these codes securely. They cannot be shown again.',
        })

    # ── Onboarding ───────────────────────────────────────────────────

    @extend_schema(
        summary="Complete onboarding",
        description="Mark the onboarding flow as completed for the current user.",
        responses={200: dict},
        tags=["Users"],
    )
    @action(detail=False, methods=['post'], url_path='complete-onboarding')
    def complete_onboarding(self, request):
        """Mark onboarding as completed."""
        user = request.user
        user.onboarding_completed = True
        user.save(update_fields=['onboarding_completed'])
        return Response({'message': 'Onboarding completed.'})
