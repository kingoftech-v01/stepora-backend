"""
Celery tasks for the Leagues & Ranking system.

Handles season lifecycle automation, daily rank snapshots,
promotion/demotion notifications, group rebalancing, and
auto-grouping season transitions.
"""

import logging

from celery import shared_task
from django.utils import timezone as django_timezone

logger = logging.getLogger(__name__)


@shared_task(name='apps.leagues.tasks.check_season_end')
def check_season_end():
    """
    Check if the active season has ended and trigger processing.

    When a season has ended:
    1. Set status to 'processing' to prevent duplicate runs.
    2. Chain into process_season_end for the heavy lifting.
    """
    from .models import Season

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

    logger.info('Season "%s" has ended. Setting status to processing...', season.name)

    # Mark as processing to prevent duplicate runs
    season.status = 'processing'
    season.is_active = False
    season.save(update_fields=['status', 'is_active', 'updated_at'])

    # Invalidate active season cache
    from django.core.cache import cache
    cache.delete('active_season')

    # Trigger the heavy processing task
    process_season_end.delay(str(season.id))


@shared_task(name='apps.leagues.tasks.process_season_end')
def process_season_end(season_id):
    """
    Process a season that has ended.

    Steps:
    1. Calculate rewards for all users.
    2. Compute promotion/relegation indicators.
    3. Send league change notifications.
    4. Mark the season as 'ended'.
    5. Create the next season (if auto_create is enabled).

    Args:
        season_id: UUID string of the season to process.
    """
    from .models import Season
    from .services import LeagueService

    try:
        season = Season.objects.get(id=season_id)
    except Season.DoesNotExist:
        logger.error('Season %s not found for end processing.', season_id)
        return

    if season.status == 'ended':
        logger.warning('Season %s already ended. Skipping.', season.name)
        return

    logger.info('Processing season end for "%s"...', season.name)

    # 1. Calculate rewards
    rewards_count = LeagueService.calculate_season_rewards(season)
    logger.info('Created %d season rewards.', rewards_count)

    # 2. Compute promotion/relegation
    promo_stats = LeagueService.compute_season_end_promotions(season)
    logger.info(
        'Promotion stats: %d promoted, %d relegated, %d neutral.',
        promo_stats['promoted'], promo_stats['relegated'], promo_stats['neutral'],
    )

    # 3. Send league change notifications
    send_league_change_notifications.delay(str(season.id))

    # 4. Mark season as ended
    season.status = 'ended'
    season.is_active = False
    season.save(update_fields=['status', 'is_active', 'updated_at'])

    logger.info('Season "%s" marked as ended.', season.name)

    # 5. Create next season
    create_next_season_task.delay(str(season.id))


@shared_task(name='apps.leagues.tasks.create_next_season_task')
def create_next_season_task(ended_season_id):
    """
    Create the next season after one has ended.

    Delegates to LeagueService.create_next_season which handles
    duration, standings carry-over, and group assignment.

    Args:
        ended_season_id: UUID string of the ended season.
    """
    from .models import Season
    from .services import LeagueService

    try:
        ended_season = Season.objects.get(id=ended_season_id)
    except Season.DoesNotExist:
        logger.error('Ended season %s not found.', ended_season_id)
        return

    new_season = LeagueService.create_next_season(ended_season)
    if new_season:
        logger.info(
            'Created next season "%s" (ends %s).',
            new_season.name,
            new_season.end_date.strftime('%Y-%m-%d'),
        )
    else:
        logger.info('Auto-create next season is disabled or failed.')


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


@shared_task(name='apps.leagues.tasks.rebalance_groups_task')
def rebalance_groups_task(season_id=None, league_id=None):
    """
    Rebalance groups for one or all leagues in a season.

    If league_id is provided, only rebalance that league.
    Otherwise, rebalance all leagues in the given season
    (or the active season if season_id is not provided).

    Args:
        season_id: Optional UUID string of the season.
        league_id: Optional UUID string of a specific league.
    """
    from .models import Season, League
    from .services import LeagueService

    if season_id:
        try:
            season = Season.objects.get(id=season_id)
        except Season.DoesNotExist:
            logger.error('Season %s not found for rebalance.', season_id)
            return
    else:
        season = Season.get_active_season()
        if not season:
            logger.info('No active season. Skipping rebalance.')
            return

    if league_id:
        try:
            leagues = [League.objects.get(id=league_id)]
        except League.DoesNotExist:
            logger.error('League %s not found for rebalance.', league_id)
            return
    else:
        leagues = League.objects.all()

    total_stats = {'groups_active': 0, 'groups_deactivated': 0, 'members_moved': 0}

    for league in leagues:
        stats = LeagueService.rebalance_league_groups(season, league)
        for key in total_stats:
            total_stats[key] += stats[key]

    logger.info(
        'Rebalance complete for season "%s": %d groups active, '
        '%d deactivated, %d members moved.',
        season.name,
        total_stats['groups_active'],
        total_stats['groups_deactivated'],
        total_stats['members_moved'],
    )


@shared_task(name='apps.leagues.tasks.auto_activate_pending_seasons')
def auto_activate_pending_seasons():
    """
    Activate pending seasons whose start_date has arrived.

    Scans for seasons with status='pending' and start_date <= now,
    then sets them to status='active'. Also deactivates any other
    active season to enforce the one-active-at-a-time constraint.
    """
    from .models import Season
    from django.core.cache import cache

    now = django_timezone.now()
    pending = Season.objects.filter(
        status='pending',
        start_date__lte=now,
    )

    activated = 0
    for season in pending:
        # Deactivate any currently active season
        Season.objects.filter(
            status='active',
        ).exclude(id=season.id).update(
            status='ended',
            is_active=False,
        )

        season.status = 'active'
        season.is_active = True
        season.save(update_fields=['status', 'is_active', 'updated_at'])

        cache.delete('active_season')
        activated += 1

        logger.info(
            'Auto-activated pending season "%s" (started %s).',
            season.name,
            season.start_date.strftime('%Y-%m-%d'),
        )

    if activated:
        logger.info('Auto-activated %d pending season(s).', activated)
    else:
        logger.debug('No pending seasons to activate.')
