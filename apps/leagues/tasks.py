"""
Celery tasks for the Leagues & Ranking system.

Handles season lifecycle automation, daily rank snapshots,
and promotion/demotion notifications.
"""

import logging

from celery import shared_task
from django.utils import timezone as django_timezone

logger = logging.getLogger(__name__)


@shared_task(name='apps.leagues.tasks.check_season_end')
def check_season_end():
    """
    Check if the active season has ended and handle the transition.

    When a season ends:
    1. Calculate rewards for all users
    2. Deactivate the season
    3. Create a new season
    4. Send promotion/demotion notifications
    """
    from .models import Season
    from .services import LeagueService

    season = Season.get_active_season()
    if not season:
        logger.info('No active season found.')
        return

    if not season.has_ended:
        logger.info(
            'Season "%s" still active (%d days remaining).',
            season.name,
            season.days_remaining,
        )
        return

    logger.info('Season "%s" has ended. Processing...', season.name)

    # Calculate rewards
    rewards_count = LeagueService.calculate_season_rewards(season)
    logger.info('Created %d season rewards.', rewards_count)

    # Send promotion/demotion notifications
    send_league_change_notifications.delay(str(season.id))

    # Create next season
    _create_next_season(season)


def _create_next_season(ended_season):
    """Create the next season after the current one ends."""
    from datetime import timedelta
    from .models import Season

    # Parse season number from name
    parts = ended_season.name.split(' ')
    try:
        season_num = int(parts[1]) + 1
    except (IndexError, ValueError):
        season_num = 2

    now = django_timezone.now()
    new_season = Season.objects.create(
        name=f'Season {season_num}',
        start_date=now,
        end_date=now + timedelta(days=90),
        is_active=True,
        rewards=ended_season.rewards,
    )

    logger.info(
        'Created new season: "%s" (ends %s).',
        new_season.name,
        new_season.end_date.strftime('%Y-%m-%d'),
    )


@shared_task(name='apps.leagues.tasks.send_league_change_notifications')
def send_league_change_notifications(season_id=None):
    """
    Send notifications for league promotions and demotions.

    Runs the promote/demote cycle and notifies affected users.
    """
    from .services import LeagueService
    from .models import LeagueStanding, Season, League
    from apps.notifications.models import Notification

    season = None
    if season_id:
        try:
            from .models import Season
            season = Season.objects.get(id=season_id)
        except Season.DoesNotExist:
            pass

    # Get current standings before promotion
    active_season = Season.get_active_season()
    if not active_season:
        return

    # Record old leagues
    old_leagues = {}
    for standing in LeagueStanding.objects.filter(season=active_season).select_related('league'):
        old_leagues[standing.user_id] = standing.league

    # Run promotion/demotion
    result = LeagueService.promote_demote_users()
    logger.info(
        'Promotion/demotion: %d promoted, %d demoted.',
        result['promoted'],
        result['demoted'],
    )

    # Send notifications for changed users
    now = django_timezone.now()
    for standing in LeagueStanding.objects.filter(season=active_season).select_related('league', 'user'):
        old_league = old_leagues.get(standing.user_id)
        if old_league and old_league.id != standing.league_id:
            old_order = League.TIER_ORDER.get(old_league.tier, 0)
            new_order = League.TIER_ORDER.get(standing.league.tier, 0)

            if new_order > old_order:
                title = f'Promoted to {standing.league.name}!'
                body = (
                    f'Congratulations! You have been promoted from '
                    f'{old_league.name} to {standing.league.name}. Keep up the great work!'
                )
                notif_type = 'achievement'
            else:
                title = f'League changed to {standing.league.name}'
                body = (
                    f'Your league has changed from {old_league.name} to '
                    f'{standing.league.name}. Keep working on your dreams to climb back!'
                )
                notif_type = 'system'

            Notification.objects.create(
                user=standing.user,
                notification_type=notif_type,
                title=title,
                body=body,
                data={
                    'screen': 'leaderboard',
                    'league_tier': standing.league.tier,
                },
                scheduled_for=now,
                status='sent',
            )


@shared_task(name='apps.leagues.tasks.create_daily_rank_snapshots')
def create_daily_rank_snapshots():
    """
    Create daily rank snapshots for all users with active standings.

    Records each user's rank and XP for historical tracking.
    Uses update_or_create to be idempotent if run multiple times per day.
    """
    from .models import LeagueStanding, Season, RankSnapshot

    season = Season.get_active_season()
    if not season:
        logger.info('No active season. Skipping rank snapshots.')
        return

    today = django_timezone.now().date()
    created_count = 0

    standings = (
        LeagueStanding.objects
        .filter(season=season)
        .select_related('league')
    )

    for standing in standings:
        _, created = RankSnapshot.objects.update_or_create(
            user_id=standing.user_id,
            season=season,
            snapshot_date=today,
            defaults={
                'league': standing.league,
                'rank': standing.rank,
                'xp': standing.xp_earned_this_season,
            },
        )
        if created:
            created_count += 1

    logger.info(
        'Created %d rank snapshots for season "%s" on %s.',
        created_count,
        season.name,
        today,
    )
