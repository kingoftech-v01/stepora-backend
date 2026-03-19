"""
Services for Users app.
"""

import logging
from datetime import timedelta
from typing import List, Optional, Tuple

from django.db.models import Count, Q
from django.utils import timezone

from .models import User

logger = logging.getLogger(__name__)


# Backward compatibility — BuddyMatchingService moved to apps.buddies.services
from apps.buddies.models import BuddyPairing  # noqa: F401
from apps.buddies.services import BuddyMatchingService  # noqa: F401


class _BuddyMatchingServiceDeprecated:
    """DEPRECATED: Use apps.buddies.services.BuddyMatchingService instead.

    Matching algorithm considers:
    1. Shared dream categories (40% weight)
    2. Activity level similarity (25% weight)
    3. Timezone proximity (20% weight)
    4. Level similarity (15% weight)

    Users are excluded if:
    - Already in an active buddy pairing
    - Have a pending buddy request with the user
    - Are the same user
    """

    # Weight factors for compatibility scoring
    CATEGORY_WEIGHT = 0.40
    ACTIVITY_WEIGHT = 0.25
    TIMEZONE_WEIGHT = 0.20
    LEVEL_WEIGHT = 0.15

    # Minimum score to be considered a match
    MIN_COMPATIBILITY_SCORE = 0.3

    def find_compatible_buddy(
        self, user: User
    ) -> Optional[Tuple[User, float, List[str]]]:
        """
        Find the most compatible buddy for a user.

        Args:
            user: The user seeking a buddy

        Returns:
            Tuple of (matched_user, compatibility_score, shared_categories)
            or None if no suitable match found
        """
        # Get potential candidates
        candidates = self._get_eligible_candidates(user)

        if not candidates:
            return None

        # Score each candidate
        best_match = None
        best_score = 0
        best_categories = []

        for candidate in candidates:
            score, shared_categories = self._calculate_compatibility(user, candidate)

            if score > best_score and score >= self.MIN_COMPATIBILITY_SCORE:
                best_match = candidate
                best_score = score
                best_categories = shared_categories

        if best_match:
            return (best_match, best_score, best_categories)

        return None

    def _get_eligible_candidates(self, user: User) -> List[User]:
        """
        Get users eligible for buddy matching.

        Excludes:
        - The user themselves
        - Users already in active buddy pairings
        - Users with pending requests from this user
        - Inactive users (no activity in 30 days)
        """
        thirty_days_ago = timezone.now() - timedelta(days=30)

        # Get users already paired with this user
        existing_pairs = BuddyPairing.objects.filter(
            Q(user1=user) | Q(user2=user), status__in=["pending", "active"]
        ).values_list("user1_id", "user2_id")

        # Flatten and get unique user IDs to exclude
        excluded_ids = set()
        excluded_ids.add(user.id)
        for user1_id, user2_id in existing_pairs:
            excluded_ids.add(user1_id)
            excluded_ids.add(user2_id)

        # Find eligible candidates
        candidates = (
            User.objects.filter(is_active=True, last_activity__gte=thirty_days_ago)
            .exclude(id__in=excluded_ids)
            .annotate(
                active_dreams_count=Count("dreams", filter=Q(dreams__status="active"))
            )
            .filter(active_dreams_count__gte=1)  # Must have at least one active dream
        )

        return list(candidates[:100])  # Limit to prevent performance issues

    def _calculate_compatibility(
        self, user1: User, user2: User
    ) -> Tuple[float, List[str]]:
        """
        Calculate compatibility score between two users.

        Returns:
            Tuple of (score, shared_categories)
        """
        # Get dream categories for both users
        user1_categories = self._get_user_categories(user1)
        user2_categories = self._get_user_categories(user2)

        # Calculate category overlap
        shared_categories = list(user1_categories & user2_categories)
        if user1_categories or user2_categories:
            total_categories = user1_categories | user2_categories
            category_score = (
                len(shared_categories) / len(total_categories)
                if total_categories
                else 0
            )
        else:
            category_score = 0

        # Calculate activity similarity (based on streak days)
        activity_score = self._calculate_activity_similarity(user1, user2)

        # Calculate timezone proximity
        timezone_score = self._calculate_timezone_proximity(user1, user2)

        # Calculate level similarity
        level_score = self._calculate_level_similarity(user1, user2)

        # Calculate weighted total score
        total_score = (
            category_score * self.CATEGORY_WEIGHT
            + activity_score * self.ACTIVITY_WEIGHT
            + timezone_score * self.TIMEZONE_WEIGHT
            + level_score * self.LEVEL_WEIGHT
        )

        return (total_score, shared_categories)

    def _get_user_categories(self, user: User) -> set:
        """Get set of dream categories for a user."""
        categories = (
            user.dreams.filter(status="active")
            .values_list("category", flat=True)
            .distinct()
        )

        return set(cat for cat in categories if cat)

    def _calculate_activity_similarity(self, user1: User, user2: User) -> float:
        """
        Calculate how similar two users' activity levels are.
        Based on streak days - similar streaks indicate similar commitment.
        """
        streak_diff = abs(user1.streak_days - user2.streak_days)

        if streak_diff == 0:
            return 1.0
        elif streak_diff <= 3:
            return 0.8
        elif streak_diff <= 7:
            return 0.6
        elif streak_diff <= 14:
            return 0.4
        elif streak_diff <= 30:
            return 0.2
        else:
            return 0.1

    def _calculate_timezone_proximity(self, user1: User, user2: User) -> float:
        """
        Calculate how close two users' timezones are.
        Closer timezones allow for better synchronous communication.
        """
        # Extract timezone offset or use simple heuristic
        tz1 = user1.timezone or "UTC"
        tz2 = user2.timezone or "UTC"

        # Simple comparison - same timezone gets full score
        if tz1 == tz2:
            return 1.0

        # Check for same continent/region
        region1 = tz1.split("/")[0] if "/" in tz1 else tz1
        region2 = tz2.split("/")[0] if "/" in tz2 else tz2

        if region1 == region2:
            return 0.7

        # Different regions get base score
        return 0.3

    def _calculate_level_similarity(self, user1: User, user2: User) -> float:
        """
        Calculate how similar two users' levels are.
        Similar levels indicate similar experience.
        """
        level_diff = abs(user1.level - user2.level)

        if level_diff == 0:
            return 1.0
        elif level_diff <= 2:
            return 0.8
        elif level_diff <= 5:
            return 0.6
        elif level_diff <= 10:
            return 0.4
        else:
            return 0.2

    def create_buddy_request(
        self,
        requesting_user: User,
        target_user: User,
        compatibility_score: float,
        shared_categories: List[str],
    ) -> "BuddyPairing":
        """
        Create a new buddy pairing request.

        Args:
            requesting_user: User initiating the request
            target_user: User being matched with
            compatibility_score: Calculated compatibility score
            shared_categories: List of shared dream categories

        Returns:
            Created BuddyPairing instance
        """
        buddy_pair = BuddyPairing.objects.create(
            user1=requesting_user,
            user2=target_user,
            status="pending",
            compatibility_score=compatibility_score,
        )

        # Send notification to target_user about buddy request
        self._send_buddy_request_notification(
            requesting_user, target_user, shared_categories
        )

        return buddy_pair

    def _send_buddy_request_notification(
        self, requesting_user: User, target_user: User, shared_categories: List[str]
    ) -> None:
        """Send a notification to the target user about the buddy request."""
        from apps.notifications.services import NotificationService

        categories_text = (
            ", ".join(shared_categories[:3])
            if shared_categories
            else "achieving dreams"
        )

        NotificationService.create(
            user=target_user,
            notification_type="buddy_request",
            title="New Dream Buddy Request!",
            body=f'{requesting_user.display_name or "Someone"} wants to be your dream buddy! '
            f"You both share interests in {categories_text}.",
            data={
                "type": "buddy_request",
                "requesting_user_id": str(requesting_user.id),
                "requesting_user_name": requesting_user.display_name or "A user",
                "shared_categories": shared_categories,
            },
            scheduled_for=timezone.now(),
            status="pending",
        )


class UserStatsService:
    """Service for calculating user statistics."""

    @staticmethod
    def get_user_stats(user: User) -> dict:
        """Get comprehensive statistics for a user."""

        active_dreams = user.dreams.filter(status="active")
        completed_dreams = user.dreams.filter(status="completed")

        # Calculate total tasks completed
        total_tasks_completed = 0
        for dream in user.dreams.all():
            for goal in dream.goals.all():
                total_tasks_completed += goal.tasks.filter(status="completed").count()

        # Calculate current week activity
        week_ago = timezone.now() - timedelta(days=7)
        tasks_this_week = 0
        for dream in active_dreams:
            for goal in dream.goals.all():
                tasks_this_week += goal.tasks.filter(
                    status="completed", completed_at__gte=week_ago
                ).count()

        return {
            "level": user.level,
            "xp": user.xp,
            "xp_to_next_level": 100 - (user.xp % 100),
            "streak_days": user.streak_days,
            "total_dreams": user.dreams.count(),
            "active_dreams": active_dreams.count(),
            "completed_dreams": completed_dreams.count(),
            "total_tasks_completed": total_tasks_completed,
            "tasks_completed_this_week": tasks_this_week,
            "subscription": user.subscription,
            "is_premium": user.is_premium(),
            "member_since": user.created_at,
        }


class AchievementService:
    """Service for checking and unlocking achievements."""

    @staticmethod
    def check_achievements(user: User):
        """Check all achievement conditions and unlock any newly met ones."""
        from django.db.models import Q

        from apps.social.models import Friendship

        from .models import Achievement, UserAchievement

        all_achievements = Achievement.objects.filter(is_active=True)
        already_unlocked = set(
            UserAchievement.objects.filter(user=user).values_list(
                "achievement_id", flat=True
            )
        )

        # Pre-compute stats
        stats = {
            "streak_days": user.streak_days,
            "level_reached": user.level,
            "xp_earned": user.xp,
            "dreams_created": user.dreams.count(),
            "dreams_completed": user.dreams.filter(status="completed").count(),
            "tasks_completed": sum(
                goal.tasks.filter(status="completed").count()
                for dream in user.dreams.all()
                for goal in dream.goals.all()
            ),
            "friends_count": Friendship.objects.filter(
                Q(user1=user) | Q(user2=user), status="accepted"
            ).count(),
            "first_dream": 1 if user.dreams.exists() else 0,
            "vision_created": (
                1 if user.dreams.filter(vision_image_url__gt="").exists() else 0
            ),
        }

        # Check buddy
        try:
            from apps.buddies.models import BuddyPairing

            stats["first_buddy"] = (
                1
                if BuddyPairing.objects.filter(
                    Q(user1=user) | Q(user2=user), status="active"
                ).exists()
                else 0
            )
        except Exception:
            stats["first_buddy"] = 0

        # Check circles
        try:
            from apps.circles.models import CircleMembership

            stats["circles_joined"] = CircleMembership.objects.filter(user=user).count()
        except Exception:
            stats["circles_joined"] = 0

        newly_unlocked = []
        for ach in all_achievements:
            if ach.id in already_unlocked:
                continue

            current_val = stats.get(ach.condition_type, 0)
            if current_val >= ach.condition_value:
                UserAchievement.objects.create(user=user, achievement=ach)
                user.add_xp(ach.xp_reward)
                # Send achievement notification
                try:
                    from apps.notifications.services import NotificationService

                    NotificationService.create(
                        user=user,
                        notification_type="achievement",
                        title=f"Achievement Unlocked: {ach.name}!",
                        body=f'You earned the "{ach.name}" achievement! +{ach.xp_reward} XP',
                        scheduled_for=timezone.now(),
                        data={
                            "type": "achievement",
                            "achievement_id": str(ach.id),
                            "achievement_name": ach.name,
                            "xp_reward": ach.xp_reward,
                        },
                    )
                except Exception:
                    logger.exception(
                        "Failed to create achievement notification for user %s, achievement %s",
                        user.id,
                        ach.id,
                    )
                newly_unlocked.append(ach)

        return newly_unlocked
