"""
Views for the Gamification system.

Provides API endpoints for gamification profiles, achievements,
activity heatmaps, daily stats, streaks, and leaderboards.
"""

import logging
from datetime import date, timedelta

from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import (
    Achievement,
    DailyActivity,
    GamificationProfile,
    UserAchievement,
)
from .serializers import GamificationProfileSerializer

logger = logging.getLogger(__name__)


class GamificationProfileView(APIView):
    """Get or update the current user's gamification profile."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Get gamification profile",
        description="Return the current user's Life RPG gamification profile.",
        tags=["Gamification"],
        responses={200: GamificationProfileSerializer},
    )
    def get(self, request):
        profile, _ = GamificationProfile.objects.get_or_create(user=request.user)
        serializer = GamificationProfileSerializer(profile)
        return Response(serializer.data)


class AchievementsView(APIView):
    """List all achievements with unlock status and progress."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Get achievements",
        description="List all achievements with user unlock status and progress.",
        tags=["Gamification"],
        responses={200: dict},
    )
    def get(self, request):
        user = request.user
        all_achievements = Achievement.objects.filter(is_active=True)

        user_achievement_map = {
            ua.achievement_id: ua
            for ua in UserAchievement.objects.filter(user=user)
        }

        progress_cache = self._compute_achievement_progress(user)

        results = []
        for ach in all_achievements:
            ua = user_achievement_map.get(ach.id)
            is_unlocked = ua is not None

            if is_unlocked:
                progress = ua.progress if ua.progress > 0 else ach.condition_value
            else:
                progress = progress_cache.get(ach.condition_type, 0)

            results.append(
                {
                    "id": str(ach.id),
                    "name": ach.name,
                    "description": ach.description,
                    "icon": ach.icon,
                    "category": ach.category,
                    "rarity": ach.rarity,
                    "xp_reward": ach.xp_reward,
                    "condition_type": ach.condition_type,
                    "requirement_value": ach.condition_value,
                    "unlocked": is_unlocked,
                    "unlocked_at": ua.unlocked_at if ua else None,
                    "progress": min(progress, ach.condition_value),
                }
            )

        return Response(
            {
                "achievements": results,
                "unlocked_count": len(user_achievement_map),
                "total_count": all_achievements.count(),
            }
        )

    def _compute_achievement_progress(self, user):
        """Compute live progress values for each achievement condition type."""

        progress = {}
        progress["streak_days"] = user.streak_days or 0
        progress["dreams_created"] = user.dreams.count()
        progress["dreams_completed"] = user.dreams.filter(status="completed").count()
        progress["tasks_completed"] = sum(
            goal.tasks.filter(status="completed").count()
            for dream in user.dreams.all()
            for goal in dream.goals.all()
        )
        progress["level_reached"] = user.level
        progress["xp_earned"] = user.xp
        progress["first_dream"] = 1 if user.dreams.exists() else 0
        progress["vision_created"] = (
            1 if user.dreams.filter(vision_image_url__gt="").exists() else 0
        )

        try:
            from django.db.models import Q

            from apps.social.models import Friendship

            progress["friends_count"] = Friendship.objects.filter(
                Q(user1=user) | Q(user2=user), status="accepted"
            ).count()
        except Exception:
            progress["friends_count"] = 0

        try:
            from django.db.models import Q

            from apps.buddies.models import BuddyPairing

            progress["first_buddy"] = (
                1
                if BuddyPairing.objects.filter(
                    Q(user1=user) | Q(user2=user), status="active"
                ).exists()
                else 0
            )
        except Exception:
            progress["first_buddy"] = 0

        try:
            from apps.circles.models import CircleMembership

            progress["circles_joined"] = CircleMembership.objects.filter(
                user=user
            ).count()
        except Exception:
            progress["circles_joined"] = 0

        return progress


class ActivityHeatmapView(APIView):
    """Return heatmap data for the last N days."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Get activity heatmap",
        description="Return daily activity data for heatmap display (last 28 days).",
        tags=["Gamification"],
        responses={200: dict},
    )
    def get(self, request):
        user = request.user
        days = int(request.query_params.get("days", 28))
        today = date.today()
        start_date = today - timedelta(days=days - 1)

        activities = DailyActivity.objects.filter(
            user=user, date__gte=start_date
        ).order_by("date")
        activity_map = {a.date: a for a in activities}

        heatmap = []
        for i in range(days):
            d = start_date + timedelta(days=i)
            a = activity_map.get(d)
            heatmap.append(
                {
                    "date": str(d),
                    "tasks_completed": a.tasks_completed if a else 0,
                    "xp_earned": a.xp_earned if a else 0,
                    "minutes_active": a.minutes_active if a else 0,
                }
            )

        return Response({"heatmap": heatmap})


class DailyStatsView(APIView):
    """Return today's stats."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Get daily stats",
        description="Return today's gamification statistics.",
        tags=["Gamification"],
        responses={200: dict},
    )
    def get(self, request):
        user = request.user
        today = date.today()

        try:
            activity = DailyActivity.objects.get(user=user, date=today)
            data = {
                "tasks_completed": activity.tasks_completed,
                "xp_earned": activity.xp_earned,
                "minutes_active": activity.minutes_active,
            }
        except DailyActivity.DoesNotExist:
            data = {
                "tasks_completed": 0,
                "xp_earned": 0,
                "minutes_active": 0,
            }

        data.update(
            {
                "level": user.level,
                "xp": user.xp,
                "xp_to_next_level": 100 - (user.xp % 100),
                "streak_days": user.streak_days,
            }
        )

        return Response(data)


class StreakDetailsView(APIView):
    """Return detailed streak data for the streak widget."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Get streak details",
        description="Return current streak, longest streak, 14-day history, and streak-freeze status.",
        tags=["Gamification"],
        responses={200: dict},
    )
    def get(self, request):
        user = request.user
        today = date.today()

        # Fetch last 14 days of DailyActivity
        start_date = today - timedelta(days=13)
        activities = DailyActivity.objects.filter(
            user=user, date__gte=start_date
        ).order_by("date")
        activity_map = {a.date: a for a in activities}

        streak_history = []
        for i in range(14):
            d = start_date + timedelta(days=i)
            a = activity_map.get(d)
            streak_history.append(1 if (a and a.tasks_completed > 0) else 0)

        # Calculate longest streak from all DailyActivity records
        all_activities = (
            DailyActivity.objects.filter(user=user, tasks_completed__gt=0)
            .order_by("date")
            .values_list("date", flat=True)
        )
        longest_streak = 0
        current_run = 0
        prev_date = None
        for d in all_activities:
            if prev_date is not None and (d - prev_date).days == 1:
                current_run += 1
            else:
                current_run = 1
            if current_run > longest_streak:
                longest_streak = current_run
            prev_date = d

        # Streak freeze from GamificationProfile (streak_jokers)
        profile, _ = GamificationProfile.objects.get_or_create(user=user)
        freeze_count = profile.streak_jokers
        streak_frozen = False
        yesterday = today - timedelta(days=1)
        yesterday_activity = activity_map.get(yesterday)
        if user.streak_days > 0 and (
            not yesterday_activity or yesterday_activity.tasks_completed == 0
        ):
            streak_frozen = True

        return Response(
            {
                "current_streak": user.streak_days,
                "longest_streak": max(longest_streak, user.streak_days),
                "streak_history": streak_history,
                "streak_frozen": streak_frozen,
                "freeze_count": freeze_count,
                "freeze_available": freeze_count > 0,
            }
        )


class StreakFreezeView(APIView):
    """Use a streak freeze (joker) to protect the streak."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Use streak freeze",
        description="Consume one streak joker to protect the streak from breaking.",
        tags=["Gamification"],
        responses={
            200: OpenApiResponse(description="Streak freeze applied."),
            400: OpenApiResponse(description="No streak freezes available."),
        },
    )
    def post(self, request):
        # SECURITY: Delegate to StreakService which enforces premium check,
        # per-week limit, and active streak validation — instead of just
        # decrementing streak_jokers without any business rule enforcement.
        from apps.gamification.services import StreakService

        result = StreakService.use_streak_freeze(request.user)
        if not result.get("success"):
            return Response(result, status=status.HTTP_400_BAD_REQUEST)
        return Response(result)


class LeaderboardStatsView(APIView):
    """Return leaderboard stats for the current user."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Get leaderboard stats",
        description="Return the user's position and stats for leaderboard display.",
        tags=["Gamification"],
        responses={200: dict},
    )
    def get(self, request):
        from apps.users.models import User

        user = request.user

        # Rank by XP
        xp_rank = User.objects.filter(xp__gt=user.xp, is_active=True).count() + 1

        # SECURITY: Bucket the total user count to avoid disclosing exact
        # platform size (information disclosure).
        count = User.objects.filter(is_active=True).count()
        if count < 100:
            total_display = "50+"
        elif count < 1000:
            total_display = f"{(count // 100) * 100}+"
        else:
            total_display = f"{count // 1000}K+"

        # Rank by streak
        streak_rank = (
            User.objects.filter(
                streak_days__gt=user.streak_days, is_active=True
            ).count()
            + 1
        )

        return Response(
            {
                "xp_rank": xp_rank,
                "streak_rank": streak_rank,
                "total_users": total_display,
                "xp": user.xp,
                "level": user.level,
                "streak_days": user.streak_days,
            }
        )
