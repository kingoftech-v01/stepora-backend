"""
Views for the Buddies system.

Provides API endpoints for Dream Buddy pairing, including finding matches,
creating pairings, tracking progress, sending encouragement, and ending
partnerships. All endpoints require authentication.
"""

import logging
import random
from datetime import timedelta

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Q, Count
from django.utils import timezone
from django.utils import timezone as django_timezone
from django.utils.translation import gettext as _
from drf_spectacular.utils import (
    extend_schema,
    OpenApiResponse,
)

from apps.users.models import User
from .models import BuddyPairing, BuddyEncouragement
from core.permissions import CanUseBuddy
from core.sanitizers import sanitize_text
from .serializers import (
    BuddyPairingSerializer,
    BuddyProgressSerializer,
    BuddyMatchSerializer,
    BuddyPairRequestSerializer,
    BuddyEncourageSerializer,
    BuddyHistorySerializer,
)

logger = logging.getLogger(__name__)


class BuddyViewSet(viewsets.GenericViewSet):
    """
    ViewSet for Dream Buddy management.

    Supports finding matches, creating pairings, viewing progress,
    sending encouragement, and ending pairings.
    All buddy features require a premium+ subscription.
    """

    permission_classes = [IsAuthenticated, CanUseBuddy]
    queryset = BuddyPairing.objects.all()
    serializer_class = BuddyPairingSerializer

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
        responses={
            200: BuddyPairingSerializer,
            403: OpenApiResponse(description='Subscription required.'),
        },
        tags=["Buddies"],
    )
    @action(detail=False, methods=['get'], url_path='current')
    def current(self, request):
        """Get the current active buddy pairing."""
        pairing = self._get_active_pairing(request.user)

        if not pairing:
            return Response({'buddy': None})

        partner = self._get_partner_user(pairing, request.user)

        # Calculate recent activity (tasks in last 7 days)
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
            logger.debug("Failed to compute shared interests", exc_info=True)
            recent_tasks = 0

        buddy_data = {
            'id': pairing.id,
            'partner': self._get_partner_data(partner),
            'compatibilityScore': pairing.compatibility_score,
            'status': pairing.status,
            'recentActivity': recent_tasks,
            'encouragementStreak': pairing.encouragement_streak,
            'bestEncouragementStreak': pairing.best_encouragement_streak,
            'createdAt': pairing.created_at,
        }

        serializer = BuddyPairingSerializer(buddy_data)
        return Response({'buddy': serializer.data})

    @extend_schema(
        summary="Find or create buddy chat",
        description="Find or create a buddy_chat conversation with a specific user.",
        responses={
            200: OpenApiResponse(description="Conversation found or created."),
            404: OpenApiResponse(description="User not found or no active buddy pairing."),
        },
        tags=["Buddies"],
    )
    @action(detail=False, methods=['post'], url_path='chat')
    def chat(self, request):
        """Find or create a buddy_chat conversation for the given user."""
        from apps.conversations.models import Conversation
        target_user_id = (
            request.data.get('userId')
            or request.data.get('user_id')
            or request.data.get('targetUserId')
            or request.data.get('target_user_id')
        )

        if not target_user_id or target_user_id == 'undefined':
            return Response({'error': _('userId is required.')}, status=status.HTTP_400_BAD_REQUEST)

        target_user = None
        try:
            target_user = User.objects.get(id=target_user_id)
        except User.DoesNotExist:
            pass

        # If not a user ID, maybe it's a conversation ID (from ConversationList)
        if not target_user:
            try:
                conv = Conversation.objects.get(
                    id=target_user_id, conversation_type='buddy_chat'
                )
                # Find the buddy (the other user in the pairing)
                buddy_user = None
                if conv.buddy_pairing:
                    bp = conv.buddy_pairing
                    buddy_user = bp.user2 if bp.user1_id == request.user.id else bp.user1
                if not buddy_user and conv.user_id != request.user.id:
                    buddy_user = conv.user
                return Response({
                    'conversationId': str(conv.id),
                    'buddy': {
                        'id': str(buddy_user.id) if buddy_user else '',
                        'displayName': (buddy_user.display_name if buddy_user else '') or 'Buddy',
                        'isOnline': buddy_user.is_online if buddy_user else False,
                        'level': buddy_user.level if buddy_user else 0,
                        'streak': buddy_user.streak_days if buddy_user else 0,
                    },
                })
            except Conversation.DoesNotExist:
                return Response({'error': _('User not found.')}, status=status.HTTP_404_NOT_FOUND)

        # Find active buddy pairing between the two users
        pairing = BuddyPairing.objects.filter(
            Q(user1=request.user, user2=target_user) | Q(user1=target_user, user2=request.user),
            status='active'
        ).first()

        # Look for existing buddy_chat conversation
        existing = None
        if pairing:
            existing = Conversation.objects.filter(
                conversation_type='buddy_chat',
                buddy_pairing=pairing,
            ).filter(Q(user=request.user) | Q(user=target_user)).first()

        if not existing:
            # Also try to find by user + type (no pairing link)
            existing = Conversation.objects.filter(
                user=request.user,
                conversation_type='buddy_chat',
            ).filter(
                Q(buddy_pairing__user1=target_user) | Q(buddy_pairing__user2=target_user)
            ).first()

        if existing:
            conv = existing
        else:
            # Create new buddy_chat conversation
            conv = Conversation.objects.create(
                user=request.user,
                conversation_type='buddy_chat',
                title=target_user.display_name or "Buddy",
                buddy_pairing=pairing,
                total_messages=0,
                total_tokens_used=0,
            )
            # Store target user as a system message so send_message can resolve recipient
            from apps.conversations.models import Message
            Message.objects.create(
                conversation=conv,
                role='system',
                content='',
                metadata={'target_user_id': str(target_user.id)},
            )

        return Response({
            'conversationId': str(conv.id),
            'buddy': {
                'id': str(target_user.id),
                'displayName': target_user.display_name or 'Buddy',
                'isOnline': target_user.is_online,
                'level': target_user.level,
                'streak': target_user.streak_days,
            },
        })

    @extend_schema(
        summary="Send buddy chat message",
        description="Send a message in a buddy chat conversation (no AI).",
        responses={
            200: OpenApiResponse(description="Message sent."),
            404: OpenApiResponse(description="Conversation not found."),
        },
        tags=["Buddies"],
    )
    @action(detail=False, methods=['post'], url_path='send-message')
    def send_message(self, request):
        """Send a buddy chat message (REST fallback when WebSocket unavailable)."""
        from apps.conversations.models import Conversation, Message
        from django.db.models import F

        conv_id = request.data.get('conversationId') or request.data.get('conversation_id')
        content = sanitize_text((request.data.get('content') or '').strip())

        if not conv_id or conv_id == 'undefined' or not content:
            return Response({'error': _('conversationId and content are required.')}, status=status.HTTP_400_BAD_REQUEST)

        # Limit message length to prevent storage abuse
        if len(content) > 5000:
            return Response({'error': _('Message too long. Maximum 5000 characters.')}, status=status.HTTP_400_BAD_REQUEST)

        import uuid
        try:
            uuid.UUID(str(conv_id))
        except (ValueError, AttributeError):
            return Response({'error': _('Invalid conversationId.')}, status=status.HTTP_400_BAD_REQUEST)

        try:
            conv = Conversation.objects.get(id=conv_id, conversation_type='buddy_chat')
        except Conversation.DoesNotExist:
            return Response({'error': _('Conversation not found.')}, status=status.HTTP_404_NOT_FOUND)

        # Verify user has access (is part of the buddy pairing or owns the conversation)
        has_access = conv.user_id == request.user.id
        if not has_access and conv.buddy_pairing:
            bp = conv.buddy_pairing
            has_access = request.user.id in (bp.user1_id, bp.user2_id)
        if not has_access:
            return Response({'error': _('Access denied.')}, status=status.HTTP_403_FORBIDDEN)

        # Block enforcement: determine the other user and check
        other_user = None
        if conv.buddy_pairing:
            bp = conv.buddy_pairing
            other_user = bp.user2 if bp.user1_id == request.user.id else bp.user1
        elif conv.user_id != request.user.id:
            other_user = conv.user

        # Fallback: check the system message metadata for target_user_id
        if not other_user:
            from apps.conversations.models import Message as ConvMessage
            sys_msg = ConvMessage.objects.filter(
                conversation=conv, role='system',
            ).exclude(metadata={}).first()
            if sys_msg and sys_msg.metadata and sys_msg.metadata.get('target_user_id'):
                try:
                    other_user = User.objects.get(id=sys_msg.metadata['target_user_id'])
                except User.DoesNotExist:
                    pass

        if not other_user:
            return Response({'error': _('Cannot determine recipient. The other user may no longer exist.')}, status=status.HTTP_400_BAD_REQUEST)

        from apps.social.models import BlockedUser
        if BlockedUser.is_blocked(request.user, other_user):
            return Response({'detail': _('Cannot send message')}, status=status.HTTP_403_FORBIDDEN)

        msg = Message.objects.create(
            conversation=conv,
            role='user',
            content=content,
            metadata={'sender_id': str(request.user.id)},
        )
        Conversation.objects.filter(id=conv.id).update(
            total_messages=F('total_messages') + 1,
            updated_at=django_timezone.now(),
        )

        # Send push notification to the other user
        try:
            from apps.notifications.models import Notification
            Notification.objects.create(
                user=other_user,
                notification_type='buddy',
                title=_('Message from %(name)s') % {'name': request.user.display_name or _("Your buddy")},
                body=content[:100],
                scheduled_for=django_timezone.now(),
                data={
                    'conversation_id': str(conv.id),
                    'sender_id': str(request.user.id),
                    'screen': 'BuddyChat',
                },
            )
        except Exception:
            logger.warning("Failed to send buddy notification", exc_info=True)

        return Response({
            'id': str(msg.id),
            'content': msg.content,
            'senderId': str(request.user.id),
            'createdAt': msg.created_at.isoformat(),
        })

    @extend_schema(
        summary="Get buddy progress",
        description="Retrieve progress comparison between the current user and their buddy.",
        responses={
            200: BuddyProgressSerializer,
            400: OpenApiResponse(description='Validation error.'),
            403: OpenApiResponse(description='Subscription required.'),
            404: OpenApiResponse(description='Resource not found.'),
        },
        tags=["Buddies"],
    )
    @action(detail=True, methods=['get'], url_path='progress')
    def progress(self, request, pk=None):
        """Get progress comparison for a buddy pairing."""
        try:
            pairing = BuddyPairing.objects.select_related(
                'user1', 'user2'
            ).get(
                id=pk,
                status='active'
            )
        except BuddyPairing.DoesNotExist:
            return Response(
                {'error': _('Active buddy pairing not found.')},
                status=status.HTTP_404_NOT_FOUND
            )

        if pairing.user1_id != request.user.id and pairing.user2_id != request.user.id:
            return Response(
                {'error': _('You are not part of this pairing.')},
                status=status.HTTP_403_FORBIDDEN
            )

        partner = self._get_partner_user(pairing, request.user)

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
                dream__is_public=True,
                completed_at__gte=week_ago,
                status='completed'
            ).count()
        except (ImportError, Exception):
            logger.debug("Failed to compute shared interests", exc_info=True)

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
            "Find a compatible buddy match based on shared interests and activity level."
        ),
        responses={
            200: BuddyMatchSerializer,
            400: OpenApiResponse(description="Already have an active buddy."),
            403: OpenApiResponse(description='Subscription required.'),
        },
        tags=["Buddies"],
    )
    @action(detail=False, methods=['post'], url_path='find-match')
    def find_match(self, request):
        """Find a compatible buddy match."""
        existing = self._get_active_pairing(request.user)
        if existing:
            return Response(
                {'error': _('You already have an active buddy pairing.')},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Find users without active pairings
        active_pairing_user_ids = set()
        active_pairings = BuddyPairing.objects.filter(status='active')
        for p in active_pairings:
            active_pairing_user_ids.add(p.user1_id)
            active_pairing_user_ids.add(p.user2_id)

        candidates = User.objects.filter(
            is_active=True
        ).exclude(
            id__in=active_pairing_user_ids
        ).exclude(
            id=request.user.id
        ).order_by('-last_activity')[:50]

        if not candidates.exists():
            return Response({'match': None})

        best_match = None
        best_score = 0.0
        user_level = request.user.level
        user_xp = request.user.xp

        for candidate in candidates:
            level_diff = abs(candidate.level - user_level)
            level_score = max(0.0, 1.0 - (level_diff / 50.0))
            xp_diff = abs(candidate.xp - user_xp)
            xp_score = max(0.0, 1.0 - (xp_diff / 10000.0))
            days_since_activity = (django_timezone.now() - candidate.last_activity).days
            activity_score = max(0.0, 1.0 - (days_since_activity / 30.0))
            score = (level_score * 0.3) + (xp_score * 0.3) + (activity_score * 0.4)

            if score > best_score:
                best_score = score
                best_match = candidate

        if not best_match:
            return Response({'match': None})

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
            logger.debug("Failed to compute shared interests", exc_info=True)
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
            403: OpenApiResponse(description='Subscription required.'),
            404: OpenApiResponse(description='Resource not found.'),
        },
        tags=["Buddies"],
    )
    @action(detail=False, methods=['post'], url_path='pair')
    def pair(self, request):
        """Create a buddy pairing with a specific user."""
        serializer = BuddyPairRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        partner_id = serializer.validated_data['partner_id']

        if partner_id == request.user.id:
            return Response(
                {'error': _('You cannot pair with yourself.')},
                status=status.HTTP_400_BAD_REQUEST
            )

        existing = self._get_active_pairing(request.user)
        if existing:
            return Response(
                {'error': _('You already have an active buddy pairing.')},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            partner = User.objects.get(id=partner_id)
        except User.DoesNotExist:
            return Response(
                {'error': _('Partner user not found.')},
                status=status.HTTP_404_NOT_FOUND
            )

        partner_pairing = BuddyPairing.objects.filter(
            Q(user1=partner) | Q(user2=partner),
            status='active'
        ).exists()

        if partner_pairing:
            return Response(
                {'error': _('This user already has an active buddy pairing.')},
                status=status.HTTP_400_BAD_REQUEST
            )

        level_diff = abs(partner.level - request.user.level)
        level_score = max(0.0, 1.0 - (level_diff / 50.0))
        xp_diff = abs(partner.xp - request.user.xp)
        xp_score = max(0.0, 1.0 - (xp_diff / 10000.0))
        compatibility = round((level_score + xp_score) / 2, 2)

        pairing = BuddyPairing.objects.create(
            user1=request.user,
            user2=partner,
            status='pending',
            compatibility_score=compatibility,
            expires_at=timezone.now() + timedelta(days=7),
        )

        return Response(
            {
                'message': _('Buddy pairing created with %(name)s.') % {'name': partner.display_name or _("user")},
                'pairing_id': str(pairing.id),
            },
            status=status.HTTP_201_CREATED
        )

    @extend_schema(
        summary="Accept buddy pairing",
        description="Accept a pending buddy pairing request.",
        responses={
            200: OpenApiResponse(description="Pairing accepted."),
            403: OpenApiResponse(description='Subscription required.'),
            404: OpenApiResponse(description="Pairing not found."),
        },
        tags=["Buddies"],
    )
    @action(detail=True, methods=['post'], url_path='accept')
    def accept(self, request, pk=None):
        """Accept a pending buddy pairing."""
        try:
            pairing = BuddyPairing.objects.get(
                id=pk, user2=request.user, status='pending'
            )
        except BuddyPairing.DoesNotExist:
            return Response(
                {'error': _('Pending buddy pairing not found.')},
                status=status.HTTP_404_NOT_FOUND
            )

        pairing.status = 'active'
        pairing.save(update_fields=['status', 'updated_at'])

        return Response({'message': _('Buddy pairing accepted.')})

    @extend_schema(
        summary="Reject buddy pairing",
        description="Reject a pending buddy pairing request.",
        responses={
            200: OpenApiResponse(description="Pairing rejected."),
            403: OpenApiResponse(description='Subscription required.'),
            404: OpenApiResponse(description="Pairing not found."),
        },
        tags=["Buddies"],
    )
    @action(detail=True, methods=['post'], url_path='reject')
    def reject(self, request, pk=None):
        """Reject a pending buddy pairing."""
        try:
            pairing = BuddyPairing.objects.get(
                id=pk, user2=request.user, status='pending'
            )
        except BuddyPairing.DoesNotExist:
            return Response(
                {'error': _('Pending buddy pairing not found.')},
                status=status.HTTP_404_NOT_FOUND
            )

        pairing.status = 'cancelled'
        pairing.ended_at = django_timezone.now()
        pairing.save(update_fields=['status', 'ended_at', 'updated_at'])

        return Response({'message': _('Buddy pairing rejected.')})

    @extend_schema(
        summary="Send encouragement",
        description="Send an encouragement message to your buddy partner.",
        request=BuddyEncourageSerializer,
        responses={
            200: OpenApiResponse(description="Encouragement sent."),
            400: OpenApiResponse(description='Validation error.'),
            403: OpenApiResponse(description='Subscription required.'),
            404: OpenApiResponse(description="Pairing not found."),
        },
        tags=["Buddies"],
    )
    @action(detail=True, methods=['post'], url_path='encourage')
    def encourage(self, request, pk=None):
        """Send encouragement to a buddy with streak tracking."""
        try:
            pairing = BuddyPairing.objects.get(
                id=pk,
                status='active'
            )
        except BuddyPairing.DoesNotExist:
            return Response(
                {'error': _('Active buddy pairing not found.')},
                status=status.HTTP_404_NOT_FOUND
            )

        if pairing.user1_id != request.user.id and pairing.user2_id != request.user.id:
            return Response(
                {'error': _('You are not part of this pairing.')},
                status=status.HTTP_403_FORBIDDEN
            )

        serializer = BuddyEncourageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        BuddyEncouragement.objects.create(
            pairing=pairing,
            sender=request.user,
            message=serializer.validated_data.get('message', '')
        )

        # Update encouragement streak
        now = django_timezone.now()
        if pairing.last_encouragement_at:
            days_since = (now.date() - pairing.last_encouragement_at.date()).days
            if days_since <= 1:
                if days_since == 1:
                    pairing.encouragement_streak += 1
            else:
                pairing.encouragement_streak = 1
        else:
            pairing.encouragement_streak = 1

        pairing.last_encouragement_at = now
        if pairing.encouragement_streak > pairing.best_encouragement_streak:
            pairing.best_encouragement_streak = pairing.encouragement_streak

        pairing.save(update_fields=[
            'encouragement_streak', 'best_encouragement_streak',
            'last_encouragement_at', 'updated_at'
        ])

        # Determine the partner
        partner = pairing.user2 if pairing.user1_id == request.user.id else pairing.user1

        # Try to send a notification (best-effort)
        try:
            from apps.notifications.models import Notification
            Notification.objects.create(
                user=partner,
                title=_('Buddy Encouragement'),
                body=serializer.validated_data.get('message', '') or
                     _('%(name)s sent you encouragement!') % {'name': request.user.display_name or _("Your buddy")},
                notification_type='buddy',
                scheduled_for=now,
                status='sent',
                data={'pairing_id': str(pairing.id)},
            )
        except (ImportError, Exception):
            logger.warning("Failed to send buddy notification", exc_info=True)

        return Response({
            'message': _('Encouragement sent to %(name)s.') % {'name': partner.display_name or _("your buddy")},
            'encouragement_streak': pairing.encouragement_streak,
            'best_encouragement_streak': pairing.best_encouragement_streak,
        })

    @extend_schema(
        summary="End buddy pairing",
        description="End an active buddy pairing. Sets status to cancelled.",
        responses={
            200: OpenApiResponse(description="Pairing ended."),
            403: OpenApiResponse(description='Subscription required.'),
            404: OpenApiResponse(description="Pairing not found."),
        },
        tags=["Buddies"],
    )
    def destroy(self, request, pk=None):
        """End a buddy pairing."""
        try:
            pairing = BuddyPairing.objects.get(
                id=pk,
                status='active'
            )
        except BuddyPairing.DoesNotExist:
            return Response(
                {'error': _('Active buddy pairing not found.')},
                status=status.HTTP_404_NOT_FOUND
            )

        if pairing.user1_id != request.user.id and pairing.user2_id != request.user.id:
            return Response(
                {'error': _('You are not part of this pairing.')},
                status=status.HTTP_403_FORBIDDEN
            )

        pairing.status = 'cancelled'
        pairing.ended_at = django_timezone.now()
        pairing.save(update_fields=['status', 'ended_at', 'updated_at'])

        return Response({'message': _('Buddy pairing ended.')})

    @extend_schema(
        summary="Buddy pairing history",
        description="Get the user's past buddy pairings with stats.",
        responses={
            200: BuddyHistorySerializer(many=True),
            403: OpenApiResponse(description='Subscription required.'),
        },
        tags=["Buddies"],
    )
    @action(detail=False, methods=['get'], url_path='history')
    def history(self, request):
        """Get past buddy pairings with stats."""
        pairings = BuddyPairing.objects.filter(
            Q(user1=request.user) | Q(user2=request.user),
        ).select_related('user1', 'user2').order_by('-created_at')

        results = []
        for pairing in pairings:
            partner = self._get_partner_user(pairing, request.user)
            encouragement_count = pairing.encouragements.count()
            duration_days = None
            if pairing.ended_at:
                duration_days = (pairing.ended_at - pairing.created_at).days

            results.append({
                'id': pairing.id,
                'partner': self._get_partner_data(partner),
                'status': pairing.status,
                'compatibilityScore': pairing.compatibility_score,
                'encouragementCount': encouragement_count,
                'encouragementStreak': pairing.encouragement_streak,
                'bestEncouragementStreak': pairing.best_encouragement_streak,
                'durationDays': duration_days,
                'createdAt': pairing.created_at,
                'endedAt': pairing.ended_at,
            })

        serializer = BuddyHistorySerializer(results, many=True)
        return Response({'pairings': serializer.data})
