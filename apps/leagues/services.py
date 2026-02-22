"""
Service layer for the Leagues & Ranking system.

Contains all business logic for league assignment, standing updates,
leaderboard computation, promotion/demotion, and season reward calculation.
This service is the single source of truth for ranking operations and should
be used by views and signals instead of performing direct model queries.
"""

import logging
from typing import Optional

from django.db import transaction
from django.db.models import F, Window, Count
from django.db.models.functions import DenseRank
from django.utils import timezone as django_timezone

from apps.users.models import User
from .models import League, LeagueStanding, Season, SeasonReward

logger = logging.getLogger(__name__)


class LeagueService:
    """
    Service class that encapsulates all league and ranking business logic.

    Methods:
        get_user_league(user) - Determine league based on user's XP.
        update_standing(user) - Recalculate a user's rank after XP change.
        get_leaderboard(league, limit) - Retrieve ranked user list.
        promote_demote_users() - End-of-week league tier changes.
        calculate_season_rewards(season) - Compute rewards when season ends.
        get_nearby_ranks(user, count) - Users ranked just above/below.
    """

    @staticmethod
    def get_user_league(user: User) -> Optional[League]:
        """
        Determine which league a user belongs to based on their total XP.

        Looks up the league whose XP range contains the user's current XP.
        For the top league (Legend), max_xp is null, so any XP >= min_xp qualifies.

        Args:
            user: The User instance to check.

        Returns:
            The League instance the user belongs to, or None if no leagues exist.
        """
        user_xp = user.xp

        # Try exact range match first (leagues with max_xp set)
        league = League.objects.filter(
            min_xp__lte=user_xp,
            max_xp__gte=user_xp
        ).first()

        if league:
            return league

        # Check the top league (max_xp is null, meaning no upper bound)
        top_league = League.objects.filter(
            min_xp__lte=user_xp,
            max_xp__isnull=True
        ).order_by('-min_xp').first()

        if top_league:
            return top_league

        # Fallback: return the lowest league
        return League.objects.order_by('min_xp').first()

    @staticmethod
    @transaction.atomic
    def update_standing(user: User) -> Optional[LeagueStanding]:
        """
        Recalculate a user's league standing after an XP change.

        This method:
        1. Determines the user's current league based on XP.
        2. Gets or creates their standing for the active season.
        3. Updates XP, league, and stats.
        4. Recalculates rank among all users in the same season.

        Args:
            user: The User whose standing should be updated.

        Returns:
            The updated LeagueStanding instance, or None if no active season.
        """
        season = Season.get_active_season()
        if not season:
            logger.warning(
                "No active season found. Cannot update standing for user %s.",
                user.id
            )
            return None

        league = LeagueService.get_user_league(user)
        if not league:
            logger.warning(
                "No leagues configured. Cannot update standing for user %s.",
                user.id
            )
            return None

        # Get or create standing for this user and season
        standing, created = LeagueStanding.objects.select_for_update().get_or_create(
            user=user,
            season=season,
            defaults={
                'league': league,
                'xp_earned_this_season': user.xp,
                'rank': 0,
            }
        )

        # Update the standing
        standing.league = league
        standing.xp_earned_this_season = user.xp
        standing.streak_best = max(standing.streak_best, user.streak_days)
        standing.save(update_fields=[
            'league', 'xp_earned_this_season', 'streak_best', 'updated_at'
        ])

        # Recalculate ranks for all users in this season
        LeagueService._recalculate_ranks(season)

        # Refresh the standing to get the updated rank
        standing.refresh_from_db()

        if created:
            logger.info(
                "Created new standing for user %s in season %s (league: %s).",
                user.id, season.name, league.name
            )
        else:
            logger.info(
                "Updated standing for user %s in season %s (league: %s, rank: %d).",
                user.id, season.name, league.name, standing.rank
            )

        return standing

    @staticmethod
    def _recalculate_ranks(season: Season) -> None:
        """
        Recalculate ranks for all standings in a season using dense ranking.

        Users with the same XP receive the same rank. The next rank after
        a tie skips to the next integer (dense rank), so ties don't create
        gaps in the ranking sequence.

        Args:
            season: The Season to recalculate ranks for.
        """
        ranked = (
            LeagueStanding.objects
            .filter(season=season)
            .annotate(
                dense_rank=Window(
                    expression=DenseRank(),
                    order_by=F('xp_earned_this_season').desc(),
                )
            )
        )

        for standing in ranked:
            if standing.rank != standing.dense_rank:
                LeagueStanding.objects.filter(pk=standing.pk).update(
                    rank=standing.dense_rank
                )

    @staticmethod
    def get_leaderboard(
        league: Optional[League] = None,
        limit: int = 100,
        season: Optional[Season] = None
    ) -> list:
        """
        Retrieve the leaderboard as a list of ranked user entries.

        Returns a list of dictionaries suitable for serialization with
        LeaderboardEntrySerializer. Exposes user scores and badges count
        but NEVER their dreams.

        Args:
            league: Optional league to filter by. If None, returns global leaderboard.
            limit: Maximum number of entries to return (default 100).
            season: Season to query. If None, uses the active season.

        Returns:
            List of leaderboard entry dictionaries.
        """
        if season is None:
            season = Season.get_active_season()

        if not season:
            return []

        queryset = (
            LeagueStanding.objects
            .filter(season=season)
            .select_related('user', 'league', 'user__gamification')
            .order_by('-xp_earned_this_season', 'updated_at')
        )

        if league:
            queryset = queryset.filter(league=league)

        queryset = queryset[:limit]

        entries = []
        for idx, standing in enumerate(queryset, start=1):
            badges = []
            badges_count = 0
            try:
                gamification = standing.user.gamification
                badges = gamification.badges or []
                badges_count = len(badges)
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
                'is_current_user': False,
            })

        return entries

    @staticmethod
    @transaction.atomic
    def promote_demote_users() -> dict:
        """
        Perform end-of-week league tier changes (promotions and demotions).

        This method evaluates all standings in the active season and
        reassigns leagues based on current XP. Users who have gained
        enough XP move up; those who have fallen behind may move down.

        Returns:
            A dictionary with 'promoted' and 'demoted' counts.
        """
        season = Season.get_active_season()
        if not season:
            logger.warning("No active season found for promotion/demotion cycle.")
            return {'promoted': 0, 'demoted': 0}

        promoted = 0
        demoted = 0

        standings = (
            LeagueStanding.objects
            .filter(season=season)
            .select_related('league', 'user')
        )

        for standing in standings:
            new_league = LeagueService.get_user_league(standing.user)
            if new_league and new_league.id != standing.league_id:
                old_tier_order = League.TIER_ORDER.get(standing.league.tier, 0)
                new_tier_order = League.TIER_ORDER.get(new_league.tier, 0)

                if new_tier_order > old_tier_order:
                    promoted += 1
                    logger.info(
                        "User %s promoted from %s to %s.",
                        standing.user.id, standing.league.name, new_league.name
                    )
                elif new_tier_order < old_tier_order:
                    demoted += 1
                    logger.info(
                        "User %s demoted from %s to %s.",
                        standing.user.id, standing.league.name, new_league.name
                    )

                standing.league = new_league
                standing.save(update_fields=['league', 'updated_at'])

        # Recalculate ranks after promotion/demotion
        LeagueService._recalculate_ranks(season)

        logger.info(
            "Promotion/demotion cycle complete: %d promoted, %d demoted.",
            promoted, demoted
        )

        return {'promoted': promoted, 'demoted': demoted}

    @staticmethod
    @transaction.atomic
    def calculate_season_rewards(season: Season) -> int:
        """
        Calculate and create reward records for all users when a season ends.

        For each user with a standing in the given season, a SeasonReward
        record is created (or updated) with the league they achieved.
        Users must then claim their rewards separately.

        Args:
            season: The Season that has ended.

        Returns:
            The number of reward records created.
        """
        if not season.has_ended:
            logger.warning(
                "Season %s has not ended yet. Cannot calculate rewards.",
                season.name
            )
            return 0

        standings = (
            LeagueStanding.objects
            .filter(season=season)
            .select_related('league', 'user')
        )

        rewards_created = 0

        for standing in standings:
            _, created = SeasonReward.objects.get_or_create(
                season=season,
                user=standing.user,
                defaults={
                    'league_achieved': standing.league,
                    'rewards_claimed': False,
                }
            )
            if created:
                rewards_created += 1

        # Deactivate the season
        season.is_active = False
        season.save(update_fields=['is_active', 'updated_at'])

        logger.info(
            "Season %s rewards calculated: %d records created.",
            season.name, rewards_created
        )

        return rewards_created

    @staticmethod
    def get_nearby_ranks(user: User, count: int = 5) -> dict:
        """
        Get users ranked just above and below the given user.

        Useful for showing the user their competitive neighborhood
        and motivating them to climb the leaderboard.

        Args:
            user: The User to find neighbors for.
            count: Number of users to show above and below (default 5).

        Returns:
            Dictionary with 'above', 'current', and 'below' keys,
            each containing leaderboard entry data.
        """
        season = Season.get_active_season()
        if not season:
            return {'above': [], 'current': None, 'below': []}

        try:
            standing = LeagueStanding.objects.get(user=user, season=season)
        except LeagueStanding.DoesNotExist:
            return {'above': [], 'current': None, 'below': []}

        current_rank = standing.rank

        # Users ranked above (lower rank number = higher position)
        above = (
            LeagueStanding.objects
            .filter(season=season, rank__lt=current_rank, rank__gt=0)
            .select_related('user', 'league', 'user__gamification')
            .order_by('-rank')[:count]
        )

        # Users ranked below (higher rank number = lower position)
        below = (
            LeagueStanding.objects
            .filter(season=season, rank__gt=current_rank)
            .select_related('user', 'league', 'user__gamification')
            .order_by('rank')[:count]
        )

        def _standing_to_entry(s, is_current=False):
            """Convert a LeagueStanding to a leaderboard entry dict."""
            badges_count = 0
            try:
                badges_count = len(s.user.gamification.badges or [])
            except Exception:
                pass

            return {
                'rank': s.rank,
                'user_id': s.user.id,
                'user_display_name': s.user.display_name or 'Anonymous',
                'user_avatar_url': s.user.avatar_url or '',
                'user_level': s.user.level,
                'league_name': s.league.name,
                'league_tier': s.league.tier,
                'league_color_hex': s.league.color_hex,
                'xp': s.xp_earned_this_season,
                'tasks_completed': s.tasks_completed,
                'badges_count': badges_count,
                'is_current_user': is_current,
            }

        return {
            'above': [_standing_to_entry(s) for s in reversed(list(above))],
            'current': _standing_to_entry(standing, is_current=True),
            'below': [_standing_to_entry(s) for s in below],
        }

    @staticmethod
    def increment_tasks_completed(user: User) -> None:
        """
        Increment the tasks_completed counter for a user's active standing.

        Called when a user completes a task.

        Args:
            user: The User who completed a task.
        """
        season = Season.get_active_season()
        if not season:
            return

        LeagueStanding.objects.filter(
            user=user,
            season=season
        ).update(tasks_completed=F('tasks_completed') + 1)

    @staticmethod
    def increment_dreams_completed(user: User) -> None:
        """
        Increment the dreams_completed counter for a user's active standing.

        Called when a user completes a dream.

        Args:
            user: The User who completed a dream.
        """
        season = Season.get_active_season()
        if not season:
            return

        LeagueStanding.objects.filter(
            user=user,
            season=season
        ).update(dreams_completed=F('dreams_completed') + 1)
