"""
Views for the Leagues & Ranking system.

Provides API endpoints for leagues, leaderboards, seasons, and rewards.
All leaderboard data exposes user scores and badges but NEVER their dreams
(privacy by design).
"""

from django.utils.decorators import method_decorator
from django.utils.translation import gettext as _
from django.views.decorators.cache import cache_page
from drf_spectacular.utils import (
    OpenApiParameter,
    OpenApiResponse,
    extend_schema,
    extend_schema_view,
)
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.permissions import CanUseLeague

from .models import (
    League,
    LeagueGroup,
    LeagueGroupMembership,
    LeagueSeason,
    LeagueStanding,
    Season,
    SeasonParticipant,
    SeasonReward,
)
from .serializers import (
    LeaderboardEntrySerializer,
    LeagueGroupSerializer,
    LeagueSeasonSerializer,
    LeagueSerializer,
    LeagueStandingSerializer,
    SeasonParticipantSerializer,
    SeasonRewardSerializer,
    SeasonSerializer,
)
from .services import LeagueService


@extend_schema_view(
    list=extend_schema(
        summary="List all leagues",
        description="Retrieve all league tiers with their XP ranges, icons, and rewards.",
        responses={
            403: OpenApiResponse(description="Subscription required."),
        },
        tags=["Leagues"],
    ),
    retrieve=extend_schema(
        summary="Get league details",
        description="Retrieve detailed information about a specific league.",
        responses={
            403: OpenApiResponse(description="Subscription required."),
            404: OpenApiResponse(description="Resource not found."),
        },
        tags=["Leagues"],
    ),
)
class LeagueViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for listing and retrieving league information.

    Leagues are read-only resources that define the competitive tiers
    (Bronze through Legend) with their XP ranges and rewards.
    Requires premium+ subscription.
    """

    queryset = League.objects.all().order_by("min_xp")
    serializer_class = LeagueSerializer
    permission_classes = [IsAuthenticated, CanUseLeague]
    pagination_class = None  # Leagues are a small, fixed set


class LeaderboardViewSet(viewsets.GenericViewSet):
    """
    ViewSet for leaderboard operations.

    Provides multiple leaderboard views:
    - Global leaderboard (top 100 by XP)
    - League-specific leaderboard (users in same league)
    - Friends leaderboard (requires social system)
    - Personal standing (current user's rank and stats)
    - Nearby ranks (users just above and below)

    All leaderboard data exposes scores and badges but NEVER dreams.
    """

    queryset = LeagueStanding.objects.none()
    permission_classes = [IsAuthenticated, CanUseLeague]
    serializer_class = LeaderboardEntrySerializer

    @extend_schema(
        summary="Global leaderboard",
        description=(
            "Retrieve the top 100 users ranked by XP for the current season. "
            "Shows user scores and badges but never their dreams."
        ),
        parameters=[
            OpenApiParameter(
                name="limit",
                type=int,
                location=OpenApiParameter.QUERY,
                description="Maximum number of entries to return (default 100, max 100).",
                required=False,
            ),
        ],
        responses={
            200: LeaderboardEntrySerializer(many=True),
            403: OpenApiResponse(description="Subscription required."),
        },
        tags=["Leagues"],
    )
    @method_decorator(cache_page(300))  # Cache for 5 minutes
    @action(detail=False, methods=["get"], url_path="global")
    def global_leaderboard(self, request):
        """
        Return the global leaderboard for the active season.

        Top 100 users ranked by XP earned this season. Each entry
        includes rank, user display info, league, and score metrics.
        """
        limit = min(int(request.query_params.get("limit", 100)), 100)

        entries = LeagueService.get_leaderboard(league=None, limit=limit)

        # Mark the current user's entry
        for entry in entries:
            if entry["user_id"] == request.user.id:
                entry["is_current_user"] = True

        serializer = LeaderboardEntrySerializer(entries, many=True)
        return Response(serializer.data)

    @extend_schema(
        summary="League leaderboard",
        description=(
            "Retrieve users in the same league as the requesting user, "
            "ranked by XP. Shows scores and badges but never dreams."
        ),
        parameters=[
            OpenApiParameter(
                name="league_id",
                type=str,
                location=OpenApiParameter.QUERY,
                description="UUID of a specific league to view. If omitted, uses the current user's league.",
                required=False,
            ),
            OpenApiParameter(
                name="limit",
                type=int,
                location=OpenApiParameter.QUERY,
                description="Maximum number of entries to return (default 50, max 100).",
                required=False,
            ),
        ],
        responses={
            200: LeaderboardEntrySerializer(many=True),
            403: OpenApiResponse(description="Subscription required."),
            404: OpenApiResponse(description="Resource not found."),
        },
        tags=["Leagues"],
    )
    @action(detail=False, methods=["get"], url_path="league")
    def league_leaderboard(self, request):
        """
        Return the leaderboard for users in the same league.

        If league_id is provided, show that league's rankings.
        Otherwise, show the current user's league rankings.
        """
        limit = min(int(request.query_params.get("limit", 50)), 100)
        league_id = request.query_params.get("league_id")

        if league_id:
            try:
                league = League.objects.get(id=league_id)
            except League.DoesNotExist:
                return Response(
                    {"error": _("League not found.")}, status=status.HTTP_404_NOT_FOUND
                )
        else:
            league = LeagueService.get_user_league(request.user)
            if not league:
                return Response(
                    {"error": _("No leagues configured.")},
                    status=status.HTTP_404_NOT_FOUND,
                )

        entries = LeagueService.get_leaderboard(league=league, limit=limit)

        # Mark the current user's entry
        for entry in entries:
            if entry["user_id"] == request.user.id:
                entry["is_current_user"] = True

        serializer = LeaderboardEntrySerializer(entries, many=True)
        return Response(serializer.data)

    @extend_schema(
        summary="Friends leaderboard",
        description=(
            "Retrieve the leaderboard filtered to friends only. "
            "Requires the social/buddy system. Shows scores and badges but never dreams."
        ),
        parameters=[
            OpenApiParameter(
                name="limit",
                type=int,
                location=OpenApiParameter.QUERY,
                description="Maximum number of entries to return (default 50, max 100).",
                required=False,
            ),
        ],
        responses={
            200: LeaderboardEntrySerializer(many=True),
            403: OpenApiResponse(description="Subscription required."),
        },
        tags=["Leagues"],
    )
    @action(detail=False, methods=["get"], url_path="friends")
    def friends_leaderboard(self, request):
        """
        Return the leaderboard filtered to the user's friends.

        Uses the Friendship model (accepted) and BuddyPairing to find
        connected users and returns their standings ranked by XP.
        """
        from django.db.models import Q

        from apps.buddies.models import BuddyPairing
        from apps.social.models import Friendship

        limit = min(int(request.query_params.get("limit", 50)), 100)
        season = Season.get_active_season()

        if not season:
            return Response([], status=status.HTTP_200_OK)

        # Get friend IDs from accepted friendships — 2 queries instead of loading all objects
        friend_ids = set(
            Friendship.objects.filter(
                user1=request.user, status="accepted"
            ).values_list("user2_id", flat=True)
        ) | set(
            Friendship.objects.filter(
                user2=request.user, status="accepted"
            ).values_list("user1_id", flat=True)
        )

        # Also include active buddy pairings
        buddy_relations = BuddyPairing.objects.filter(
            Q(user1=request.user) | Q(user2=request.user), status="active"
        )
        for buddy in buddy_relations:
            friend_ids.add(
                buddy.user2_id if buddy.user1_id == request.user.id else buddy.user1_id
            )

        # Include the current user
        friend_ids.add(request.user.id)

        standings = (
            LeagueStanding.objects.filter(season=season, user_id__in=friend_ids)
            .select_related("user", "league", "user__gamification")
            .order_by("-xp_earned_this_season")[:limit]
        )

        entries = []
        for idx, standing in enumerate(standings, start=1):
            badges_count = 0
            try:
                badges_count = len(standing.user.gamification.badges or [])
            except Exception:
                pass

            entries.append(
                {
                    "rank": idx,
                    "user_id": standing.user.id,
                    "user_display_name": standing.user.display_name or "Anonymous",
                    "user_avatar_url": standing.user.get_effective_avatar_url(),
                    "user_level": standing.user.level,
                    "league_name": standing.league.name,
                    "league_tier": standing.league.tier,
                    "league_color_hex": standing.league.color_hex,
                    "xp": standing.xp_earned_this_season,
                    "tasks_completed": standing.tasks_completed,
                    "badges_count": badges_count,
                    "is_current_user": standing.user.id == request.user.id,
                }
            )

        serializer = LeaderboardEntrySerializer(entries, many=True)
        return Response(serializer.data)

    @extend_schema(
        summary="My standing",
        description=(
            "Retrieve the current user's rank, league, and stats for the active season."
        ),
        responses={
            200: LeagueStandingSerializer,
            403: OpenApiResponse(description="Subscription required."),
            404: OpenApiResponse(description="Resource not found."),
        },
        tags=["Leagues"],
    )
    @action(detail=False, methods=["get"], url_path="me")
    def my_standing(self, request):
        """
        Return the current user's standing for the active season.

        Includes rank, league, XP, tasks completed, dreams completed,
        and best streak. If no standing exists, one is created.
        """
        season = Season.get_active_season()
        if not season:
            return Response(None, status=status.HTTP_204_NO_CONTENT)

        try:
            standing = LeagueStanding.objects.select_related(
                "user", "league", "season", "user__gamification"
            ).get(user=request.user, season=season)
        except LeagueStanding.DoesNotExist:
            # Create a standing for this user
            standing = LeagueService.update_standing(request.user)
            if not standing:
                return Response(
                    {"error": _("Could not create standing. No leagues configured.")},
                    status=status.HTTP_404_NOT_FOUND,
                )
            # Re-fetch with proper relations
            standing = LeagueStanding.objects.select_related(
                "user", "league", "season", "user__gamification"
            ).get(pk=standing.pk)

        serializer = LeagueStandingSerializer(standing)
        return Response(serializer.data)

    @extend_schema(
        summary="Nearby ranks",
        description=(
            "Retrieve users ranked just above and below the current user. "
            "Useful for showing competitive context."
        ),
        parameters=[
            OpenApiParameter(
                name="count",
                type=int,
                location=OpenApiParameter.QUERY,
                description="Number of users to show above and below (default 5, max 10).",
                required=False,
            ),
        ],
        responses={
            200: dict,
            403: OpenApiResponse(description="Subscription required."),
        },
        tags=["Leagues"],
    )
    @action(detail=False, methods=["get"], url_path="nearby")
    def nearby_ranks(self, request):
        """
        Return users ranked just above and below the current user.

        Provides competitive context showing the 'neighborhood' of the
        user's current rank position.
        """
        count = min(int(request.query_params.get("count", 5)), 10)
        data = LeagueService.get_nearby_ranks(request.user, count=count)
        return Response(data)

    @extend_schema(
        summary="Group leaderboard",
        description=(
            "Retrieve the leaderboard for a specific group. "
            "Shows user scores and badges but never their dreams."
        ),
        parameters=[
            OpenApiParameter(
                name="group_id",
                type=str,
                location=OpenApiParameter.QUERY,
                description="UUID of the group. If omitted, returns the current user's group.",
                required=False,
            ),
            OpenApiParameter(
                name="limit",
                type=int,
                location=OpenApiParameter.QUERY,
                description="Maximum number of entries (default 30, max 50).",
                required=False,
            ),
        ],
        responses={
            200: LeaderboardEntrySerializer(many=True),
            403: OpenApiResponse(description="Subscription required."),
            404: OpenApiResponse(description="Group not found."),
        },
        tags=["Leagues"],
    )
    @action(detail=False, methods=["get"], url_path="group")
    def group_leaderboard(self, request):
        """
        Return the leaderboard for a specific group.

        If group_id is provided, show that group's rankings.
        Otherwise, show the current user's group rankings.
        """
        limit = min(int(request.query_params.get("limit", 30)), 50)
        group_id = request.query_params.get("group_id")

        if group_id:
            try:
                group = LeagueGroup.objects.select_related("league", "season").get(
                    id=group_id
                )
            except LeagueGroup.DoesNotExist:
                return Response(
                    {"error": _("Group not found.")}, status=status.HTTP_404_NOT_FOUND
                )
        else:
            # Find the current user's group
            season = Season.get_active_season()
            if not season:
                return Response([], status=status.HTTP_200_OK)

            try:
                standing = LeagueStanding.objects.get(user=request.user, season=season)
                membership = LeagueGroupMembership.objects.select_related(
                    "group",
                    "group__league",
                    "group__season",
                ).get(standing=standing)
                group = membership.group
            except (LeagueStanding.DoesNotExist, LeagueGroupMembership.DoesNotExist):
                return Response(
                    {"error": _("You are not assigned to a group yet.")},
                    status=status.HTTP_404_NOT_FOUND,
                )

        entries = LeagueService.get_group_leaderboard(group, limit=limit)

        # Mark the current user's entry
        for entry in entries:
            if entry["user_id"] == request.user.id:
                entry["is_current_user"] = True

        serializer = LeaderboardEntrySerializer(entries, many=True)
        return Response(serializer.data)


@extend_schema_view(
    list=extend_schema(
        summary="List seasons",
        description="Retrieve all seasons (current and past).",
        responses={
            403: OpenApiResponse(description="Subscription required."),
        },
        tags=["Leagues"],
    ),
    retrieve=extend_schema(
        summary="Get season details",
        description="Retrieve detailed information about a specific season.",
        responses={
            403: OpenApiResponse(description="Subscription required."),
            404: OpenApiResponse(description="Resource not found."),
        },
        tags=["Leagues"],
    ),
)
class SeasonViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for season information and reward claiming.

    Provides endpoints for:
    - Listing all seasons
    - Retrieving season details
    - Getting the current active season
    - Viewing past seasons
    - Claiming season rewards
    """

    queryset = Season.objects.all()
    serializer_class = SeasonSerializer
    permission_classes = [IsAuthenticated, CanUseLeague]

    @extend_schema(
        summary="Current season",
        description="Retrieve the currently active season.",
        responses={
            200: SeasonSerializer,
            403: OpenApiResponse(description="Subscription required."),
            404: OpenApiResponse(description="Resource not found."),
        },
        tags=["Leagues"],
    )
    @action(detail=False, methods=["get"], url_path="current")
    def current_season(self, request):
        """Return the currently active season."""
        season = Season.get_active_season()
        if not season:
            return Response(
                {"error": _("No active season.")}, status=status.HTTP_404_NOT_FOUND
            )

        serializer = SeasonSerializer(season)
        return Response(serializer.data)

    @extend_schema(
        summary="Past seasons",
        description="Retrieve all past (inactive) seasons.",
        responses={
            200: SeasonSerializer(many=True),
            403: OpenApiResponse(description="Subscription required."),
        },
        tags=["Leagues"],
    )
    @action(detail=False, methods=["get"], url_path="past")
    def past_seasons(self, request):
        """Return all past (inactive) seasons."""
        seasons = Season.objects.filter(is_active=False).order_by("-end_date")
        serializer = SeasonSerializer(seasons, many=True)
        return Response(serializer.data)

    @extend_schema(
        summary="My season rewards",
        description="List all season rewards for the current user.",
        responses={
            200: SeasonRewardSerializer(many=True),
            403: OpenApiResponse(description="Subscription required."),
        },
        tags=["Leagues"],
    )
    @action(detail=False, methods=["get"], url_path="my-rewards")
    def my_rewards(self, request):
        """List all season rewards for the current user."""
        rewards = (
            SeasonReward.objects.filter(user=request.user)
            .select_related("season", "league_achieved")
            .order_by("-created_at")
        )
        serializer = SeasonRewardSerializer(rewards, many=True)
        return Response(serializer.data)

    @extend_schema(
        summary="Claim season reward",
        description="Claim rewards for a completed season.",
        responses={
            200: SeasonRewardSerializer,
            400: OpenApiResponse(
                description="Rewards already claimed or season not ended."
            ),
            403: OpenApiResponse(description="Subscription required."),
            404: OpenApiResponse(description="No reward found for this season."),
        },
        tags=["Leagues"],
    )
    @action(detail=True, methods=["post"], url_path="claim-reward")
    def claim_reward(self, request, pk=None):
        """
        Claim rewards for a completed season.

        The season must have ended and rewards must not have been
        previously claimed.
        """
        season = self.get_object()

        if not season.has_ended:
            return Response(
                {"error": _("Season has not ended yet.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            reward = SeasonReward.objects.select_related(
                "season", "league_achieved"
            ).get(season=season, user=request.user)
        except SeasonReward.DoesNotExist:
            return Response(
                {"error": _("No reward found for this season.")},
                status=status.HTTP_404_NOT_FOUND,
            )

        if reward.rewards_claimed:
            return Response(
                {"error": _("Rewards have already been claimed.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        reward.claim()
        serializer = SeasonRewardSerializer(reward)
        return Response(serializer.data)


@extend_schema_view(
    list=extend_schema(
        summary="List league groups",
        description=(
            "List all active groups for the current season, "
            "optionally filtered by league."
        ),
        parameters=[
            OpenApiParameter(
                name="league_id",
                type=str,
                location=OpenApiParameter.QUERY,
                description="Filter groups by league UUID.",
                required=False,
            ),
        ],
        responses={
            200: LeagueGroupSerializer(many=True),
            403: OpenApiResponse(description="Subscription required."),
        },
        tags=["Leagues"],
    ),
    retrieve=extend_schema(
        summary="Get group details",
        description="Retrieve details for a specific league group.",
        responses={
            200: LeagueGroupSerializer,
            403: OpenApiResponse(description="Subscription required."),
            404: OpenApiResponse(description="Resource not found."),
        },
        tags=["Leagues"],
    ),
)
class LeagueGroupViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for league groups within the auto-grouping system.

    Provides endpoints for:
    - Listing groups (optionally filtered by league)
    - Retrieving group details
    - Getting the current user's group (mine)
    - Group leaderboard
    """

    serializer_class = LeagueGroupSerializer
    permission_classes = [IsAuthenticated, CanUseLeague]

    def get_queryset(self):
        """Return active groups for the current season."""
        season = Season.get_active_season()
        if not season:
            return LeagueGroup.objects.none()

        qs = (
            LeagueGroup.objects.filter(season=season, is_active=True)
            .select_related("league", "season")
            .order_by("league__min_xp", "group_number")
        )

        league_id = self.request.query_params.get("league_id")
        if league_id:
            qs = qs.filter(league_id=league_id)

        return qs

    @extend_schema(
        summary="My group",
        description="Retrieve the current user's group assignment for the active season.",
        responses={
            200: LeagueGroupSerializer,
            403: OpenApiResponse(description="Subscription required."),
            404: OpenApiResponse(description="Not assigned to a group."),
        },
        tags=["Leagues"],
    )
    @action(detail=False, methods=["get"], url_path="mine")
    def mine(self, request):
        """Return the current user's group for the active season."""
        season = Season.get_active_season()
        if not season:
            return Response(
                {"error": _("No active season.")},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            standing = LeagueStanding.objects.get(
                user=request.user,
                season=season,
            )
            membership = LeagueGroupMembership.objects.select_related(
                "group",
                "group__league",
                "group__season",
            ).get(standing=standing)
        except (LeagueStanding.DoesNotExist, LeagueGroupMembership.DoesNotExist):
            return Response(
                {"error": _("You are not assigned to a group yet.")},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = LeagueGroupSerializer(membership.group)
        return Response(serializer.data)

    @extend_schema(
        summary="Group leaderboard",
        description=(
            "Retrieve the ranked leaderboard for a specific group. "
            "Shows user scores and badges but never their dreams."
        ),
        parameters=[
            OpenApiParameter(
                name="limit",
                type=int,
                location=OpenApiParameter.QUERY,
                description="Maximum entries (default 30, max 50).",
                required=False,
            ),
        ],
        responses={
            200: LeaderboardEntrySerializer(many=True),
            403: OpenApiResponse(description="Subscription required."),
            404: OpenApiResponse(description="Group not found."),
        },
        tags=["Leagues"],
    )
    @action(detail=True, methods=["get"], url_path="leaderboard")
    def leaderboard(self, request, pk=None):
        """Return the leaderboard for a specific group."""
        group = self.get_object()
        limit = min(int(request.query_params.get("limit", 30)), 50)

        entries = LeagueService.get_group_leaderboard(group, limit=limit)

        # Mark the current user's entry
        for entry in entries:
            if entry["user_id"] == request.user.id:
                entry["is_current_user"] = True

        serializer = LeaderboardEntrySerializer(entries, many=True)
        return Response(serializer.data)


@extend_schema_view(
    list=extend_schema(
        summary="List league seasons",
        description="Retrieve all league seasons (current and past) with themed rewards.",
        responses={
            403: OpenApiResponse(description="Subscription required."),
        },
        tags=["Leagues"],
    ),
    retrieve=extend_schema(
        summary="Get league season details",
        description="Retrieve detailed information about a specific league season.",
        responses={
            403: OpenApiResponse(description="Subscription required."),
            404: OpenApiResponse(description="Resource not found."),
        },
        tags=["Leagues"],
    ),
)
class LeagueSeasonViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for themed league seasons with rewards.

    Provides endpoints for:
    - Listing all league seasons
    - Retrieving season details (with user participation info)
    - Getting the current active league season
    - Joining the current season
    - Viewing the season leaderboard
    - Claiming end-of-season rewards
    """

    queryset = LeagueSeason.objects.all()
    serializer_class = LeagueSeasonSerializer
    permission_classes = [IsAuthenticated, CanUseLeague]

    def get_serializer_context(self):
        """Include request in serializer context for user participation lookup."""
        context = super().get_serializer_context()
        context["request"] = self.request
        return context

    @extend_schema(
        summary="Current league season",
        description="Retrieve the currently active league season with theme and rewards.",
        responses={
            200: LeagueSeasonSerializer,
            403: OpenApiResponse(description="Subscription required."),
            404: OpenApiResponse(description="No active league season."),
        },
        tags=["Leagues"],
    )
    @action(detail=False, methods=["get"], url_path="current")
    def current_season(self, request):
        """Return the currently active league season."""
        season = LeagueSeason.get_active_league_season()
        if not season:
            return Response(
                {"error": _("No active league season.")},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = LeagueSeasonSerializer(season, context={"request": request})
        return Response(serializer.data)

    @extend_schema(
        summary="Join current league season",
        description="Join the currently active league season. Creates a participant record.",
        responses={
            200: LeagueSeasonSerializer,
            400: OpenApiResponse(description="Already joined or no active season."),
            403: OpenApiResponse(description="Subscription required."),
            404: OpenApiResponse(description="No active league season."),
        },
        tags=["Leagues"],
    )
    @action(detail=False, methods=["post"], url_path="current/join")
    def join_current_season(self, request):
        """
        Join the currently active league season.

        Creates a SeasonParticipant record for the current user. Returns
        400 if already joined.
        """
        season = LeagueSeason.get_active_league_season()
        if not season:
            return Response(
                {"error": _("No active league season.")},
                status=status.HTTP_404_NOT_FOUND,
            )

        if season.has_ended:
            return Response(
                {"error": _("This season has already ended.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        _participant, created = SeasonParticipant.objects.get_or_create(
            season=season,
            user=request.user,
            defaults={
                "xp_earned": request.user.xp,
            },
        )

        if not created:
            return Response(
                {"error": _("You have already joined this season.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = LeagueSeasonSerializer(season, context={"request": request})
        return Response(serializer.data)

    @extend_schema(
        summary="League season leaderboard",
        description=(
            "Retrieve the top 50 participants for a specific league season, "
            "ranked by XP earned. Shows user scores but never dreams."
        ),
        parameters=[
            OpenApiParameter(
                name="limit",
                type=int,
                location=OpenApiParameter.QUERY,
                description="Maximum number of entries (default 50, max 100).",
                required=False,
            ),
        ],
        responses={
            200: SeasonParticipantSerializer(many=True),
            403: OpenApiResponse(description="Subscription required."),
            404: OpenApiResponse(description="Resource not found."),
        },
        tags=["Leagues"],
    )
    @method_decorator(cache_page(300))
    @action(detail=True, methods=["get"], url_path="leaderboard")
    def leaderboard(self, request, pk=None):
        """
        Return the leaderboard for a specific league season.

        Top participants ranked by XP earned. Each entry includes rank,
        user display info, and XP metrics.
        """
        season = self.get_object()
        limit = min(int(request.query_params.get("limit", 50)), 100)

        participants = (
            SeasonParticipant.objects.filter(season=season)
            .select_related("user")
            .order_by("-xp_earned")[:limit]
        )

        # Assign ranks
        entries = []
        for idx, participant in enumerate(participants, start=1):
            participant.rank = idx
            entries.append(participant)

        serializer = SeasonParticipantSerializer(entries, many=True)

        # Mark the current user's entry
        data = serializer.data
        for entry in data:
            if str(entry.get("user")) == str(request.user.id):
                entry["is_current_user"] = True
            else:
                entry["is_current_user"] = False

        return Response(data)

    @extend_schema(
        summary="Claim league season rewards",
        description="Claim end-of-season rewards for a completed league season.",
        responses={
            200: SeasonParticipantSerializer,
            400: OpenApiResponse(
                description="Season not ended or rewards already claimed."
            ),
            403: OpenApiResponse(description="Subscription required."),
            404: OpenApiResponse(description="Not a participant in this season."),
        },
        tags=["Leagues"],
    )
    @action(detail=True, methods=["post"], url_path="claim-rewards")
    def claim_rewards(self, request, pk=None):
        """
        Claim rewards for a completed league season.

        The season must have ended and rewards must not have been
        previously claimed. Returns the participant record with
        the projected reward based on final rank.
        """
        season = self.get_object()

        if not season.has_ended:
            return Response(
                {"error": _("Season has not ended yet.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            participant = SeasonParticipant.objects.select_related(
                "season", "user"
            ).get(season=season, user=request.user)
        except SeasonParticipant.DoesNotExist:
            return Response(
                {"error": _("You did not participate in this season.")},
                status=status.HTTP_404_NOT_FOUND,
            )

        if participant.rewards_claimed:
            return Response(
                {"error": _("Rewards have already been claimed.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        participant.claim_rewards()
        serializer = SeasonParticipantSerializer(participant)
        return Response(serializer.data)
