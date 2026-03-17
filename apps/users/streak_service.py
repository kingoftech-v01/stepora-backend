"""
Streak & Habit Chain service.

Central place for all streak-related logic:
- Recording daily activity (task completion, check-in, focus timer)
- Incrementing / resetting streaks
- Tracking longest streak
- Streak freeze (premium feature, max 1 per week)
- XP multiplier calculation
- Calendar heatmap data (365 days)
- Daily broken-streak detection (Celery task helper)
"""

import logging
from datetime import date, timedelta
from typing import Optional

from django.db.models import Count, F, Q
from django.utils import timezone

logger = logging.getLogger(__name__)


class StreakService:
    """Stateless service — all methods are classmethods / staticmethods."""

    # ── Streak milestones that unlock badges / notifications ──
    MILESTONES = [7, 14, 30, 60, 90, 180, 365]

    # ── XP Multipliers ──
    @staticmethod
    def get_xp_multiplier(streak_days: int) -> float:
        if streak_days >= 100:
            return 3.0
        if streak_days >= 30:
            return 2.0
        if streak_days >= 7:
            return 1.5
        return 1.0

    # ────────────────────────────────────────────────────────────
    # Core: record_activity — called on task completion, check-in, etc.
    # ────────────────────────────────────────────────────────────
    @classmethod
    def record_activity(
        cls,
        user,
        chain_type: str,
        dream=None,
    ):
        """Record activity and update the user's streak.

        Idempotent per day: calling multiple times on the same date
        only creates one HabitChain per (user, date, chain_type) combo
        but the streak increment happens only on the first call of the day.
        """
        from .models import HabitChain

        today = timezone.now().date()

        # Record the habit chain event
        HabitChain.objects.get_or_create(
            user=user,
            date=today,
            chain_type=chain_type,
            defaults={"dream": dream, "completed": True},
        )

        # Check if streak was already updated today
        if user.streak_updated_at == today:
            return

        yesterday = today - timedelta(days=1)

        if user.streak_updated_at == yesterday:
            # Consecutive day — increment
            from django.contrib.auth import get_user_model

            User = get_user_model()
            User.objects.filter(id=user.id).update(
                streak_days=F("streak_days") + 1,
                streak_updated_at=today,
            )
            user.refresh_from_db(fields=["streak_days", "streak_updated_at"])
        elif user.streak_updated_at is None or user.streak_updated_at < yesterday:
            # Gap of 2+ days — reset to 1 (today counts)
            from django.contrib.auth import get_user_model

            User = get_user_model()
            User.objects.filter(id=user.id).update(
                streak_days=1,
                streak_updated_at=today,
            )
            user.refresh_from_db(fields=["streak_days", "streak_updated_at"])

        # Update longest streak if needed
        if user.streak_days > user.longest_streak:
            from django.contrib.auth import get_user_model

            User = get_user_model()
            User.objects.filter(id=user.id).update(
                longest_streak=user.streak_days,
            )
            user.refresh_from_db(fields=["longest_streak"])

        # Check for milestone notifications
        cls._check_streak_milestone(user)

    # ────────────────────────────────────────────────────────────
    # Streak Freeze
    # ────────────────────────────────────────────────────────────
    @classmethod
    def use_streak_freeze(cls, user) -> dict:
        """Use a streak freeze to protect a streak for today.

        Rules:
        - User must be premium/pro
        - User must have streak_jokers > 0 (from GamificationProfile)
        - Max 1 freeze per week
        - Streak must be > 0 (no point freezing a 0 streak)

        Returns a dict with ``success`` bool and ``message``.
        """
        from .models import GamificationProfile

        if not user.is_premium():
            return {"success": False, "message": "Streak freeze is a premium feature."}

        if user.streak_days == 0:
            return {"success": False, "message": "No active streak to freeze."}

        profile, _ = GamificationProfile.objects.get_or_create(user=user)
        if profile.streak_jokers <= 0:
            return {"success": False, "message": "No streak freezes remaining."}

        today = timezone.now().date()
        week_ago = today - timedelta(days=7)
        if user.streak_freeze_used_at and user.streak_freeze_used_at > week_ago:
            return {
                "success": False,
                "message": "You can only use one streak freeze per week.",
            }

        # Apply freeze: mark today as "active" so streak doesn't break
        from django.contrib.auth import get_user_model

        User = get_user_model()
        User.objects.filter(id=user.id).update(
            streak_updated_at=today,
            streak_freeze_used_at=today,
        )
        user.refresh_from_db(
            fields=["streak_updated_at", "streak_freeze_used_at"]
        )

        # Decrement jokers
        GamificationProfile.objects.filter(id=profile.id).update(
            streak_jokers=F("streak_jokers") - 1
        )
        profile.refresh_from_db(fields=["streak_jokers"])

        logger.info(
            "User %s used streak freeze (streak: %d, jokers left: %d)",
            user.id,
            user.streak_days,
            profile.streak_jokers,
        )

        return {
            "success": True,
            "message": "Streak freeze activated! Your streak is safe for today.",
            "freeze_count": profile.streak_jokers,
        }

    # ────────────────────────────────────────────────────────────
    # Calendar heatmap (365 days)
    # ────────────────────────────────────────────────────────────
    @classmethod
    def get_streak_summary(cls, user) -> dict:
        """Return current streak info + last 365 days of activity counts.

        Used by ``GET /api/v1/users/me/streaks/``.
        """
        today = timezone.now().date()
        multiplier = cls.get_xp_multiplier(user.streak_days)

        return {
            "current_streak": user.streak_days,
            "longest_streak": max(user.longest_streak, user.streak_days),
            "streak_updated_at": str(user.streak_updated_at) if user.streak_updated_at else None,
            "xp_multiplier": multiplier,
            "xp_multiplier_label": f"{multiplier}x" if multiplier > 1 else None,
            "next_milestone": cls._next_milestone(user.streak_days),
            "milestones": cls.MILESTONES,
        }

    @classmethod
    def get_calendar_heatmap(cls, user, days: int = 365) -> list:
        """Return heatmap data for the last ``days`` days.

        Each entry: ``{"date": "YYYY-MM-DD", "count": <int>, "level": 0-3}``
        """
        from .models import DailyActivity

        today = timezone.now().date()
        start = today - timedelta(days=days - 1)

        activities = (
            DailyActivity.objects.filter(user=user, date__gte=start)
            .order_by("date")
        )
        act_map = {a.date: a.tasks_completed for a in activities}

        result = []
        for i in range(days):
            d = start + timedelta(days=i)
            count = act_map.get(d, 0)
            level = 0 if count == 0 else (1 if count <= 1 else (2 if count <= 3 else 3))
            result.append({
                "date": d.isoformat(),
                "count": count,
                "level": level,
            })

        return result

    # ────────────────────────────────────────────────────────────
    # Daily broken-streak detection (called from Celery)
    # ────────────────────────────────────────────────────────────
    @classmethod
    def reset_broken_streaks(cls):
        """Reset streaks for users who missed yesterday AND today so far.

        Called daily at midnight UTC by the ``check_broken_streaks`` Celery task.
        Also sends at-risk notifications to users whose streak could break today.
        """
        from django.contrib.auth import get_user_model

        User = get_user_model()

        today = timezone.now().date()
        yesterday = today - timedelta(days=1)

        # Users whose streak_updated_at is BEFORE yesterday -> streak is broken
        broken = User.objects.filter(
            streak_days__gt=0,
            streak_updated_at__lt=yesterday,
        )

        reset_count = 0
        for user in broken:
            old_streak = user.streak_days
            User.objects.filter(id=user.id).update(streak_days=0)
            reset_count += 1
            logger.info(
                "Reset broken streak for user %s (was %d days)",
                user.id,
                old_streak,
            )

        # At-risk: users whose streak_updated_at IS yesterday (so they need
        # to do something TODAY to keep the streak alive).
        at_risk = User.objects.filter(
            streak_days__gte=3,  # only notify if streak is meaningful
            streak_updated_at=yesterday,
        )

        notified = 0
        for user in at_risk:
            cls._send_at_risk_notification(user)
            notified += 1

        logger.info(
            "Broken streak reset: %d users. At-risk notifications: %d users.",
            reset_count,
            notified,
        )
        return {"reset": reset_count, "notified": notified}

    # ────────────────────────────────────────────────────────────
    # Internal helpers
    # ────────────────────────────────────────────────────────────
    @classmethod
    def _next_milestone(cls, current: int) -> Optional[int]:
        for m in cls.MILESTONES:
            if current < m:
                return m
        return None

    @classmethod
    def _check_streak_milestone(cls, user):
        """Send a notification when a user hits a streak milestone."""
        if user.streak_days not in cls.MILESTONES:
            return

        try:
            from apps.notifications.models import Notification

            Notification.objects.create(
                user=user,
                notification_type="achievement",
                title=f"Streak Milestone: {user.streak_days} days!",
                body=(
                    f"You've maintained a {user.streak_days}-day streak! "
                    f"Your XP multiplier is now {cls.get_xp_multiplier(user.streak_days)}x."
                ),
                scheduled_for=timezone.now(),
                data={
                    "type": "streak_milestone",
                    "streak_days": user.streak_days,
                    "xp_multiplier": cls.get_xp_multiplier(user.streak_days),
                },
            )
        except Exception:
            logger.exception(
                "Failed to create streak milestone notification for user %s",
                user.id,
            )

    @classmethod
    def _send_at_risk_notification(cls, user):
        """Send push notification that streak is at risk."""
        try:
            from apps.notifications.models import Notification

            Notification.objects.create(
                user=user,
                notification_type="system",
                title="Your streak is at risk!",
                body=(
                    f"Your {user.streak_days}-day streak is at risk! "
                    "Complete a task today to keep it alive."
                ),
                scheduled_for=timezone.now(),
                data={
                    "type": "streak_at_risk",
                    "streak_days": user.streak_days,
                    "screen": "Home",
                },
            )
        except Exception:
            logger.exception(
                "Failed to create at-risk notification for user %s",
                user.id,
            )
