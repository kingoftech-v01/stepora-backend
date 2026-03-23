"""
Services for the Friends system.

Provides business logic for friendship management, blocking checks,
mutual friends computation, and friend suggestions.
"""

import logging

from django.db.models import Q

logger = logging.getLogger(__name__)


class FriendshipService:
    """Service for friendship-related business logic."""

    @staticmethod
    def is_friend(user_a_id, user_b_id):
        """Check if two users are friends."""
        from .models import Friendship

        return Friendship.objects.filter(
            Q(user1_id=user_a_id, user2_id=user_b_id)
            | Q(user1_id=user_b_id, user2_id=user_a_id),
            status="accepted",
        ).exists()

    @staticmethod
    def is_blocked(user_a_id, user_b_id):
        """Check if either user has blocked the other."""
        from .models import BlockedUser

        return BlockedUser.objects.filter(
            Q(blocker_id=user_a_id, blocked_id=user_b_id)
            | Q(blocker_id=user_b_id, blocked_id=user_a_id)
        ).exists()

    @staticmethod
    def mutual_friends(user_a_id, user_b_id):
        """Get list of mutual friends between two users."""
        from .models import Friendship

        # Get friend sets for each user
        def _get_friend_ids(uid):
            qs = Friendship.objects.filter(
                Q(user1_id=uid) | Q(user2_id=uid), status="accepted"
            ).values_list("user1_id", "user2_id")
            ids = set()
            for u1, u2 in qs:
                if str(u1) != str(uid):
                    ids.add(str(u1))
                if str(u2) != str(uid):
                    ids.add(str(u2))
            return ids

        friends_a = _get_friend_ids(user_a_id)
        friends_b = _get_friend_ids(user_b_id)
        mutual_ids = friends_a & friends_b

        from apps.users.models import User

        mutual_users = User.objects.filter(id__in=mutual_ids)
        return [
            {
                "id": str(u.id),
                "display_name": u.display_name or "",
                "avatar_url": u.get_effective_avatar_url(),
                "level": u.level,
            }
            for u in mutual_users
        ]

    @staticmethod
    def suggestions(user, limit=10):
        """Get friend suggestions based on mutual friends and activity."""
        from .models import BlockedUser, Friendship

        # Get already-connected user IDs
        existing = Friendship.objects.filter(Q(user1=user) | Q(user2=user)).values_list(
            "user1_id", "user2_id"
        )

        excluded_ids = {str(user.id)}
        for u1, u2 in existing:
            excluded_ids.add(str(u1))
            excluded_ids.add(str(u2))

        # Also exclude blocked users
        blocked = BlockedUser.objects.filter(
            Q(blocker=user) | Q(blocked=user)
        ).values_list("blocker_id", "blocked_id")
        for b1, b2 in blocked:
            excluded_ids.add(str(b1))
            excluded_ids.add(str(b2))

        from apps.users.models import User

        suggestions = (
            User.objects.filter(is_active=True)
            .exclude(id__in=excluded_ids)
            .order_by("-last_activity")[:limit]
        )

        return [
            {
                "id": str(u.id),
                "display_name": u.display_name or "",
                "avatar_url": u.get_effective_avatar_url(),
                "level": u.level,
            }
            for u in suggestions
        ]
