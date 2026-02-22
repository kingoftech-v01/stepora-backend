"""
Views for the Leagues & Ranking system.

Provides API endpoints for leagues, leaderboards, seasons, and rewards.
All leaderboard data exposes user scores and badges but NEVER their dreams
(privacy by design).
"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone as django_timezone
from drf_spectacular.utils import (
    extend_schema,
    extend_schema_view,
    OpenApiParameter,
    OpenApiResponse,
)

from .models import League, LeagueStanding, Season, SeasonReward
from .serializers import (
    LeagueSerializer,
    LeagueStandingSerializer,
    SeasonSerializer,
    SeasonRewardSerializer,
    LeaderboardEntrySerializer,
)
from .services import LeagueService


@extend_schema_view(
    list=extend_schema(
        summary="List all leagues",
        description="Retrieve all league tiers with their XP ranges, icons, and rewards.",
        tags=["Leagues"],
    ),
    retrieve=extend_schema(
        summary="Get league details",
        description="Retrieve detailed information about a specific league.",
        tags=["Leagues"],
    ),
)
class LeagueViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for listing and retrieving league information.

    Leagues are read-only resources that define the competitive tiers
    (Bronze through Legend) with their XP ranges and rewards.
    """

    queryset = League.objects.all().order_by('min_xp')
    serializer_class = LeagueSerializer
    permission_classes = [IsAuthenticated]
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

    permission_classes = [IsAuthenticated]
    serializer_class = LeaderboardEntrySerializer

    @extend_schema(
        summary="Global leaderboard",
        description=(
            "Retrieve the top 100 users ranked by XP for the current season. "
            "Shows user scores and badges but never their dreams."
        ),
        parameters=[
            OpenApiParameter(
                name='limit',
                type=int,
                location=OpenApiParameter.QUERY,
                description='Maximum number of entries to return (default 100, max 100).',
                required=False,
            ),
        ],
        responses={200: LeaderboardEntrySerializer(many=True)},
        tags=["Leagues"],
    )
    @action(detail=False, methods=['get'], url_path='global')
    def global_leaderboard(self, request):
        """
        Return the global leaderboard for the active season.

        Top 100 users ranked by XP earned this season. Each entry
        includes rank, user display info, league, and score metrics.
        """
        limit = min(int(request.query_params.get('limit', 100)), 100)

        entries = LeagueService.get_leaderboard(league=None, limit=limit)

        # Mark the current user's entry
        for entry in entries:
            if entry['user_id'] == request.user.id:
                entry['is_current_user'] = True

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
                name='league_id',
                type=str,
                location=OpenApiParameter.QUERY,
                description='UUID of a specific league to view. If omitted, uses the current user\'s league.',
                required=False,
            ),
            OpenApiParameter(
                name='limit',
                type=int,
                location=OpenApiParameter.QUERY,
                description='Maximum number of entries to return (default 50, max 100).',
                required=False,
            ),
        ],
        responses={200: LeaderboardEntrySerializer(many=True)},
        tags=["Leagues"],
    )
    @action(detail=False, methods=['get'], url_path='league')
    def league_leaderboard(self, request):
        """
        Return the leaderboard for users in the same league.

        If league_id is provided, show that league's rankings.
        Otherwise, show the current user's league rankings.
        """
        limit = min(int(request.query_params.get('limit', 50)), 100)
        league_id = request.query_params.get('league_id')

        if league_id:
            try:
                league = League.objects.get(id=league_id)
            except League.DoesNotExist:
                return Response(
                    {'error': 'League not found.'},
                    status=status.HTTP_404_NOT_FOUND
                )
        else:
            league = LeagueService.get_user_league(request.user)
            if not league:
                return Response(
                    {'error': 'No leagues configured.'},
                    status=status.HTTP_404_NOT_FOUND
                )

        entries = LeagueService.get_leaderboard(league=league, limit=limit)

        # Mark the current user's entry
        for entry in entries:
            if entry['user_id'] == request.user.id:
                entry['is_current_user'] = True

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
                name='limit',
                type=int,
                location=OpenApiParameter.QUERY,
                description='Maximum number of entries to return (default 50, max 100).',
                required=False,
            ),
        ],
        responses={200: LeaderboardEntrySerializer(many=True)},
        tags=["Leagues"],
    )
    @action(detail=False, methods=['get'], url_path='friends')
    def friends_leaderboard(self, request):
        """
        Return the leaderboard filtered to the user's friends (buddies).

        Uses the DreamBuddy model to find connected users and returns
        their standings ranked by XP.
        """
        from django.db.models import Q
        from apps.buddies.models import BuddyPairing

        limit = min(int(request.query_params.get('limit', 50)), 100)
        season = Season.get_active_season()

        if not season:
            return Response(
                {'error': 'No active season.'},
                status=status.HTTP_404_NOT_FOUND
            )

        # Get friend IDs from active buddy pairings
        buddy_relations = BuddyPairing.objects.filter(
            Q(user1=request.user) | Q(user2=request.user),
            status='active'
        )

        # Collect friend user IDs
        friend_ids = set()
        for buddy in buddy_relations:
            if buddy.user1_id == request.user.id:
                friend_ids.add(buddy.user2_id)
            else:
                friend_ids.add(buddy.user1_id)

        # Include the current user
        friend_ids.add(request.user.id)

        standings = (
            LeagueStanding.objects
            .filter(season=season, user_id__in=friend_ids)
            .select_related('user', 'league', 'user__gamification')
            .order_by('-xp_earned_this_season')[:limit]
        )

        entries = []
        for idx, standing in enumerate(standings, start=1):
            badges_count = 0
            try:
                badges_count = len(standing.user.gamification.badges or [])
            except Exception:
                pass

            entries.append({
                'rank': idx,
                'user_id': standing.user.id,
                'user_display_name': standing.user.display_name or 'Anonymous',
                'user_avatar_url': standing.user.avatar_url or '',
                'user_level': standing.user.level,
                'league_name': standing.league.name,
                'league_tier': standing.league.tier,
                'league_color_hex': standing.league.color_hex,
                'xp': standing.xp_earned_this_season,
                'tasks_completed': standing.tasks_completed,
                'badges_count': badges_count,
                'is_current_user': standing.user.id == request.user.id,
            })

        serializer = LeaderboardEntrySerializer(entries, many=True)
        return Response(serializer.data)

    @extend_schema(
        summary="My standing",
        description=(
            "Retrieve the current user's rank, league, and stats for the active season."
        ),
        responses={200: LeagueStandingSerializer},
        tags=["Leagues"],
    )
    @action(detail=False, methods=['get'], url_path='me')
    def my_standing(self, request):
        """
        Return the current user's standing for the active season.

        Includes rank, league, XP, tasks completed, dreams completed,
        and best streak. If no standing exists, one is created.
        """
        season = Season.get_active_season()
        if not season:
            return Response(
                {'error': 'No active season.'},
                status=status.HTTP_404_NOT_FOUND
            )

        try:
            standing = LeagueStanding.objects.select_related(
                'user', 'league', 'season', 'user__gamification'
            ).get(
                user=request.user,
                season=season
            )
        except LeagueStanding.DoesNotExist:
            # Create a standing for this user
            standing = LeagueService.update_standing(request.user)
            if not standing:
                return Response(
                    {'error': 'Could not create standing. No leagues configured.'},
                    status=status.HTTP_404_NOT_FOUND
                )
            # Re-fetch with proper relations
            standing = LeagueStanding.objects.select_related(
                'user', 'league', 'season', 'user__gamification'
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
                name='count',
                type=int,
                location=OpenApiParameter.QUERY,
                description='Number of users to show above and below (default 5, max 10).',
                required=False,
            ),
        ],
        responses={200: dict},
        tags=["Leagues"],
    )
    @action(detail=False, methods=['get'], url_path='nearby')
    def nearby_ranks(self, request):
        """
        Return users ranked just above and below the current user.

        Provides competitive context showing the 'neighborhood' of the
        user's current rank position.
        """
        count = min(int(request.query_params.get('count', 5)), 10)
        data = LeagueService.get_nearby_ranks(request.user, count=count)
        return Response(data)


@extend_schema_view(
    list=extend_schema(
        summary="List seasons",
        description="Retrieve all seasons (current and past).",
        tags=["Leagues"],
    ),
    retrieve=extend_schema(
        summary="Get season details",
        description="Retrieve detailed information about a specific season.",
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
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Current season",
        description="Retrieve the currently active season.",
        responses={200: SeasonSerializer},
        tags=["Leagues"],
    )
    @action(detail=False, methods=['get'], url_path='current')
    def current_season(self, request):
        """Return the currently active season."""
        season = Season.get_active_season()
        if not season:
            return Response(
                {'error': 'No active season.'},
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = SeasonSerializer(season)
        return Response(serializer.data)

    @extend_schema(
        summary="Past seasons",
        description="Retrieve all past (inactive) seasons.",
        responses={200: SeasonSerializer(many=True)},
        tags=["Leagues"],
    )
    @action(detail=False, methods=['get'], url_path='past')
    def past_seasons(self, request):
        """Return all past (inactive) seasons."""
        seasons = Season.objects.filter(is_active=False).order_by('-end_date')
        serializer = SeasonSerializer(seasons, many=True)
        return Response(serializer.data)

    @extend_schema(
        summary="My season rewards",
        description="List all season rewards for the current user.",
        responses={200: SeasonRewardSerializer(many=True)},
        tags=["Leagues"],
    )
    @action(detail=False, methods=['get'], url_path='my-rewards')
    def my_rewards(self, request):
        """List all season rewards for the current user."""
        rewards = (
            SeasonReward.objects
            .filter(user=request.user)
            .select_related('season', 'league_achieved')
            .order_by('-created_at')
        )
        serializer = SeasonRewardSerializer(rewards, many=True)
        return Response(serializer.data)

    @extend_schema(
        summary="Claim season reward",
        description="Claim rewards for a completed season.",
        responses={
            200: SeasonRewardSerializer,
            400: OpenApiResponse(description="Rewards already claimed or season not ended."),
            404: OpenApiResponse(description="No reward found for this season."),
        },
        tags=["Leagues"],
    )
    @action(detail=True, methods=['post'], url_path='claim-reward')
    def claim_reward(self, request, pk=None):
        """
        Claim rewards for a completed season.

        The season must have ended and rewards must not have been
        previously claimed.
        """
        season = self.get_object()

        if not season.has_ended:
            return Response(
                {'error': 'Season has not ended yet.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            reward = SeasonReward.objects.select_related(
                'season', 'league_achieved'
            ).get(
                season=season,
                user=request.user
            )
        except SeasonReward.DoesNotExist:
            return Response(
                {'error': 'No reward found for this season.'},
                status=status.HTTP_404_NOT_FOUND
            )

        if reward.rewards_claimed:
            return Response(
                {'error': 'Rewards have already been claimed.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        reward.claim()
        serializer = SeasonRewardSerializer(reward)
        return Response(serializer.data)
