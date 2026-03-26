"""
Service layer for the Leagues & Ranking system.

Contains all business logic for league assignment, standing updates,
leaderboard computation, promotion/demotion, season reward calculation,
and auto-grouping (group assignment, rebalance, season-end promotions).
This service is the single source of truth for ranking operations and should
be used by views and signals instead of performing direct model queries.
"""

import logging
import math
from datetime import timedelta
from typing import Optional

from django.db import transaction
from django.db.models import Count, F, Window
from django.db.models.functions import DenseRank
from django.utils import timezone as django_timezone

from core.decorators import retry_on_deadlock

from apps.users.models import User

from .models import (
    League,
    LeagueGroup,
    LeagueGroupMembership,
    LeagueStanding,
    Season,
    SeasonConfig,
    SeasonReward,
)

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
        league = League.objects.filter(min_xp__lte=user_xp, max_xp__gte=user_xp).first()

        if league:
            return league

        # Check the top league (max_xp is null, meaning no upper bound)
        top_league = (
            League.objects.filter(min_xp__lte=user_xp, max_xp__isnull=True)
            .order_by("-min_xp")
            .first()
        )

        if top_league:
            return top_league

        # Fallback: return the lowest league
        return League.objects.order_by("min_xp").first()

    @staticmethod
    @retry_on_deadlock()
    @transaction.atomic
    def update_standing(user: User) -> Optional[LeagueStanding]:
        """
        Recalculate a user's league standing after an XP change.

        This method:
        1. Determines the user's current league based on XP.
        2. Gets or creates their standing for the active season.
        3. Updates XP, league, and stats.
        4. Recalculates rank among all users in the same season.
        5. If the league tier changed (or standing is new), assigns
           the user to a group via assign_user_to_group.

        Args:
            user: The User whose standing should be updated.

        Returns:
            The updated LeagueStanding instance, or None if no active season.
        """
        season = Season.get_active_season()
        if not season:
            logger.warning(
                "No active season found. Cannot update standing for user %s.", user.id
            )
            return None

        league = LeagueService.get_user_league(user)
        if not league:
            logger.warning(
                "No leagues configured. Cannot update standing for user %s.", user.id
            )
            return None

        # Get or create standing for this user and season
        standing, created = LeagueStanding.objects.select_for_update().get_or_create(
            user=user,
            season=season,
            defaults={
                "league": league,
                "xp_earned_this_season": user.xp,
                "rank": 0,
            },
        )

        # Detect tier change
        old_league_id = standing.league_id
        tier_changed = old_league_id != league.id

        # Update the standing
        standing.league = league
        standing.xp_earned_this_season = user.xp
        standing.streak_best = max(standing.streak_best, user.streak_days)
        standing.save(
            update_fields=[
                "league",
                "xp_earned_this_season",
                "streak_best",
                "updated_at",
            ]
        )

        # Recalculate ranks for all users in this season
        LeagueService._recalculate_ranks(season)

        # Refresh the standing to get the updated rank
        standing.refresh_from_db()

        # Assign to group on creation or tier change
        if created or tier_changed:
            try:
                LeagueService.assign_user_to_group(standing, season, league)
            except Exception:
                logger.error(
                    "Failed to assign user %s to group after tier change.",
                    user.id,
                    exc_info=True,
                )

        if created:
            logger.info(
                "Created new standing for user %s in season %s (league: %s).",
                user.id,
                season.name,
                league.name,
            )
        else:
            logger.info(
                "Updated standing for user %s in season %s (league: %s, rank: %d).",
                user.id,
                season.name,
                league.name,
                standing.rank,
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
        ranked = LeagueStanding.objects.filter(season=season).annotate(
            dense_rank=Window(
                expression=DenseRank(),
                order_by=F("xp_earned_this_season").desc(),
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
        season: Optional[Season] = None,
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
            LeagueStanding.objects.filter(season=season)
            .select_related("user", "league", "user__gamification")
            .order_by("-xp_earned_this_season", "updated_at")
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
                logger.debug(
                    "Failed to load badges for user %s", standing.user.id, exc_info=True
                )
                badges_count = 0

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
                    "is_current_user": False,
                }
            )

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
            return {"promoted": 0, "demoted": 0}

        promoted = 0
        demoted = 0

        standings = LeagueStanding.objects.filter(season=season).select_related(
            "league", "user"
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
                        standing.user.id,
                        standing.league.name,
                        new_league.name,
                    )
                elif new_tier_order < old_tier_order:
                    demoted += 1
                    logger.info(
                        "User %s demoted from %s to %s.",
                        standing.user.id,
                        standing.league.name,
                        new_league.name,
                    )

                standing.league = new_league
                standing.save(update_fields=["league", "updated_at"])

        # Recalculate ranks after promotion/demotion
        LeagueService._recalculate_ranks(season)

        logger.info(
            "Promotion/demotion cycle complete: %d promoted, %d demoted.",
            promoted,
            demoted,
        )

        return {"promoted": promoted, "demoted": demoted}

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
                "Season %s has not ended yet. Cannot calculate rewards.", season.name
            )
            return 0

        standings = LeagueStanding.objects.filter(season=season).select_related(
            "league", "user"
        )

        rewards_created = 0

        for standing in standings:
            _, created = SeasonReward.objects.get_or_create(
                season=season,
                user=standing.user,
                defaults={
                    "league_achieved": standing.league,
                    "rewards_claimed": False,
                },
            )
            if created:
                rewards_created += 1

        # Deactivate the season
        season.is_active = False
        season.save(update_fields=["is_active", "updated_at"])

        logger.info(
            "Season %s rewards calculated: %d records created.",
            season.name,
            rewards_created,
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
            return {"above": [], "current": None, "below": []}

        try:
            standing = LeagueStanding.objects.get(user=user, season=season)
        except LeagueStanding.DoesNotExist:
            return {"above": [], "current": None, "below": []}

        current_rank = standing.rank

        # Users ranked above (lower rank number = higher position)
        above = (
            LeagueStanding.objects.filter(
                season=season, rank__lt=current_rank, rank__gt=0
            )
            .select_related("user", "league", "user__gamification")
            .order_by("-rank")[:count]
        )

        # Users ranked below (higher rank number = lower position)
        below = (
            LeagueStanding.objects.filter(season=season, rank__gt=current_rank)
            .select_related("user", "league", "user__gamification")
            .order_by("rank")[:count]
        )

        def _standing_to_entry(s, is_current=False):
            """Convert a LeagueStanding to a leaderboard entry dict."""
            badges_count = 0
            try:
                badges_count = len(s.user.gamification.badges or [])
            except Exception:
                logger.debug(
                    "Failed to load badges for user %s", s.user.id, exc_info=True
                )
                badges_count = 0

            return {
                "rank": s.rank,
                "user_id": s.user.id,
                "user_display_name": s.user.display_name or "Anonymous",
                "user_avatar_url": s.user.get_effective_avatar_url(),
                "user_level": s.user.level,
                "league_name": s.league.name,
                "league_tier": s.league.tier,
                "league_color_hex": s.league.color_hex,
                "xp": s.xp_earned_this_season,
                "tasks_completed": s.tasks_completed,
                "badges_count": badges_count,
                "is_current_user": is_current,
            }

        return {
            "above": [_standing_to_entry(s) for s in reversed(list(above))],
            "current": _standing_to_entry(standing, is_current=True),
            "below": [_standing_to_entry(s) for s in below],
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

        LeagueStanding.objects.filter(user=user, season=season).update(
            tasks_completed=F("tasks_completed") + 1
        )

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

        LeagueStanding.objects.filter(user=user, season=season).update(
            dreams_completed=F("dreams_completed") + 1
        )

    # ------------------------------------------------------------------
    # Auto-Grouping Methods
    # ------------------------------------------------------------------

    @staticmethod
    @transaction.atomic
    def assign_user_to_group(
        standing: LeagueStanding,
        season: Season,
        league: League,
    ) -> LeagueGroupMembership:
        """
        Assign a standing to a group within the given season + league.

        Finds the active group with the fewest members that is under
        the max size. If no such group exists, creates a new one.
        Uses select_for_update to prevent race conditions.

        Args:
            standing: The LeagueStanding to place in a group.
            season: The current Season.
            league: The League tier the standing belongs to.

        Returns:
            The LeagueGroupMembership that was created or updated.
        """
        config = SeasonConfig.get()

        # Remove any existing membership for this standing (handles tier changes)
        LeagueGroupMembership.objects.filter(standing=standing).delete()

        # Find active groups with room, ordered by member count (fewest first).
        # Note: select_for_update() cannot be combined with GROUP BY in PostgreSQL,
        # so we find the candidate first, then lock it separately.
        candidate = (
            LeagueGroup.objects.filter(season=season, league=league, is_active=True)
            .annotate(num_members=Count("memberships"))
            .filter(num_members__lt=config.group_max_size)
            .order_by("num_members", "group_number")
            .values_list("pk", flat=True)
            .first()
        )

        group = (
            LeagueGroup.objects.select_for_update().get(pk=candidate)
            if candidate
            else None
        )

        if not group:
            # Determine next group number
            last_number = (
                LeagueGroup.objects.filter(season=season, league=league)
                .order_by("-group_number")
                .values_list("group_number", flat=True)
                .first()
            ) or 0

            group = LeagueGroup.objects.create(
                season=season,
                league=league,
                group_number=last_number + 1,
                is_active=True,
            )
            logger.info(
                "Created new group #%d for %s in season %s.",
                group.group_number,
                league.name,
                season.name,
            )

        membership = LeagueGroupMembership.objects.create(
            group=group,
            standing=standing,
        )

        logger.debug(
            "Assigned standing %s to group #%d (%s).",
            standing.id,
            group.group_number,
            league.name,
        )
        return membership

    @staticmethod
    @transaction.atomic
    def rebalance_league_groups(season: Season, league: League) -> dict:
        """
        Rebalance groups for a given season + league combination.

        Algorithm:
        1. Count total members across all active groups.
        2. Compute desired number of groups from target size.
        3. Collect all standings ordered by XP (desc).
        4. Round-robin distribute into groups.
        5. Deactivate any now-empty groups.

        Args:
            season: The Season to rebalance.
            league: The League tier to rebalance.

        Returns:
            Dict with 'groups_active', 'groups_deactivated', 'members_moved'.
        """
        config = SeasonConfig.get()

        # All memberships for this season+league, ordered by XP desc
        memberships = list(
            LeagueGroupMembership.objects.filter(
                group__season=season,
                group__league=league,
                group__is_active=True,
            )
            .select_related("standing", "group")
            .order_by("-standing__xp_earned_this_season")
        )

        total_members = len(memberships)
        if total_members == 0:
            return {"groups_active": 0, "groups_deactivated": 0, "members_moved": 0}

        # Compute desired group count
        desired_groups = max(1, math.ceil(total_members / config.group_target_size))

        # Get or create groups
        active_groups = list(
            LeagueGroup.objects.filter(
                season=season, league=league, is_active=True
            ).order_by("group_number")
        )

        # Create more groups if needed
        while len(active_groups) < desired_groups:
            last_num = active_groups[-1].group_number if active_groups else 0
            new_group = LeagueGroup.objects.create(
                season=season,
                league=league,
                group_number=last_num + 1,
                is_active=True,
            )
            active_groups.append(new_group)

        # Round-robin assignment by XP rank
        target_groups = active_groups[:desired_groups]
        members_moved = 0

        for idx, membership in enumerate(memberships):
            target_group = target_groups[idx % len(target_groups)]
            if membership.group_id != target_group.id:
                membership.group = target_group
                membership.save(update_fields=["group"])
                members_moved += 1

        # Deactivate groups that are now empty
        groups_deactivated = 0
        for group in active_groups:
            if group.memberships.count() == 0:
                group.is_active = False
                group.save(update_fields=["is_active"])
                groups_deactivated += 1

        active_count = LeagueGroup.objects.filter(
            season=season,
            league=league,
            is_active=True,
        ).count()

        logger.info(
            "Rebalanced %s in season %s: %d members across %d groups "
            "(%d moved, %d groups deactivated).",
            league.name,
            season.name,
            total_members,
            active_count,
            members_moved,
            groups_deactivated,
        )

        return {
            "groups_active": active_count,
            "groups_deactivated": groups_deactivated,
            "members_moved": members_moved,
        }

    @staticmethod
    @transaction.atomic
    def compute_season_end_promotions(season: Season) -> dict:
        """
        Compute promotion/relegation flags for all standings at season end.

        Based on SeasonConfig thresholds:
        - xp >= promotion_xp_threshold  -> promotion eligible
        - xp <  relegation_xp_threshold -> relegation risk

        This does not move users between leagues; it annotates the data
        so the frontend can display promotion/relegation indicators.

        Args:
            season: The season that just ended.

        Returns:
            Dict with 'promoted', 'relegated', 'neutral' counts.
        """
        config = SeasonConfig.get()

        standings = LeagueStanding.objects.filter(season=season)

        promoted = standings.filter(
            xp_earned_this_season__gte=config.promotion_xp_threshold,
        ).count()

        relegated = standings.filter(
            xp_earned_this_season__lt=config.relegation_xp_threshold,
        ).count()

        total = standings.count()

        logger.info(
            "Season %s end promotions: %d promoted, %d relegated, %d neutral.",
            season.name,
            promoted,
            relegated,
            total - promoted - relegated,
        )

        return {
            "promoted": promoted,
            "relegated": relegated,
            "neutral": total - promoted - relegated,
        }

    @staticmethod
    @transaction.atomic
    def create_next_season(ended_season: Season) -> Optional[Season]:
        """
        Create a new season following the ended one.

        Steps:
        1. Read duration from SeasonConfig.
        2. Parse next season number from the ended season name.
        3. Create the new Season with status='active'.
        4. Bulk-create LeagueStanding records for all users who had standings.
        5. Trigger group assignment for each new standing.

        Args:
            ended_season: The Season that just ended.

        Returns:
            The newly created Season, or None if auto_create is disabled.
        """
        config = SeasonConfig.get()

        if not config.auto_create_next_season:
            logger.info(
                "Auto-create next season is disabled. Skipping.",
            )
            return None

        # Parse season number from name
        parts = ended_season.name.split(" ")
        try:
            season_num = int(parts[1]) + 1
        except (IndexError, ValueError):
            season_num = 2

        now = django_timezone.now()
        duration = config.season_duration_days
        new_season = Season.objects.create(
            name=f"Season {season_num}",
            start_date=now,
            end_date=now + timedelta(days=duration),
            status="active",
            is_active=True,
            duration_days=duration,
            rewards=ended_season.rewards,
        )

        # Invalidate active season cache
        from django.core.cache import cache as django_cache

        django_cache.delete("active_season")

        logger.info(
            'Created new season: "%s" (ends %s, duration %dd).',
            new_season.name,
            new_season.end_date.strftime("%Y-%m-%d"),
            duration,
        )

        # Bulk-create standings for users who had standings in the ended season
        old_standings = LeagueStanding.objects.filter(
            season=ended_season
        ).select_related("user", "league")

        new_standings = []
        for old in old_standings:
            league = LeagueService.get_user_league(old.user)
            if not league:
                league = old.league
            new_standings.append(
                LeagueStanding(
                    user=old.user,
                    league=league,
                    season=new_season,
                    xp_earned_this_season=0,
                    rank=0,
                )
            )

        if new_standings:
            LeagueStanding.objects.bulk_create(
                new_standings,
                ignore_conflicts=True,
            )

            # Assign each new standing to a group
            created_standings = LeagueStanding.objects.filter(
                season=new_season,
            ).select_related("league")

            for standing in created_standings:
                try:
                    LeagueService.assign_user_to_group(
                        standing,
                        new_season,
                        standing.league,
                    )
                except Exception:
                    logger.error(
                        "Failed to assign user %s to group in new season.",
                        standing.user_id,
                        exc_info=True,
                    )

        logger.info(
            "Carried over %d standings to season %s.",
            len(new_standings),
            new_season.name,
        )

        return new_season

    @staticmethod
    def get_group_leaderboard(group: LeagueGroup, limit: int = 30) -> list:
        """
        Return the ranked leaderboard for a specific group.

        Args:
            group: The LeagueGroup to get the leaderboard for.
            limit: Maximum entries to return.

        Returns:
            List of leaderboard entry dicts.
        """
        memberships = (
            LeagueGroupMembership.objects.filter(group=group)
            .select_related(
                "standing",
                "standing__user",
                "standing__league",
                "standing__user__gamification",
            )
            .order_by("-standing__xp_earned_this_season")[:limit]
        )

        entries = []
        for idx, membership in enumerate(memberships, start=1):
            standing = membership.standing
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
                    "is_current_user": False,
                    "group_id": str(group.id),
                    "group_number": group.group_number,
                }
            )

        return entries
