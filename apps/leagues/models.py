"""
Models for the Leagues & Ranking system.

Implements a competitive ranking system with tiered leagues, seasonal
standings, and rewards. Users can view others' scores and badges
but NOT their dreams (privacy by design).

League Tiers (by XP):
    - Bronze:   0 - 499 XP
    - Silver:   500 - 1,499 XP
    - Gold:     1,500 - 3,499 XP
    - Platinum: 3,500 - 6,999 XP
    - Diamond:  7,000 - 11,999 XP
    - Master:   12,000 - 19,999 XP
    - Legend:   20,000+ XP
"""

import uuid

from django.conf import settings
from django.db import models
from django.core.validators import MinValueValidator
from django.utils import timezone as django_timezone

from django.core.cache import cache
from apps.users.models import User


class League(models.Model):
    """
    Represents a competitive league tier in the ranking system.

    Each league has an XP range that determines which users belong to it.
    Leagues are ordered from Bronze (lowest) to Legend (highest).
    """

    TIER_CHOICES = [
        ('bronze', 'Bronze'),
        ('silver', 'Silver'),
        ('gold', 'Gold'),
        ('platinum', 'Platinum'),
        ('diamond', 'Diamond'),
        ('master', 'Master'),
        ('legend', 'Legend'),
    ]

    TIER_ORDER = {
        'bronze': 0,
        'silver': 1,
        'gold': 2,
        'platinum': 3,
        'diamond': 4,
        'master': 5,
        'legend': 6,
    }

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text='Unique identifier for this league.'
    )
    name = models.CharField(
        max_length=100,
        help_text='Display name of the league (e.g., "Bronze League").'
    )
    tier = models.CharField(
        max_length=20,
        choices=TIER_CHOICES,
        unique=True,
        db_index=True,
        help_text='The tier level of this league.'
    )
    min_xp = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0)],
        help_text='Minimum XP required to enter this league.'
    )
    max_xp = models.IntegerField(
        null=True,
        blank=True,
        help_text='Maximum XP for this league. Null for the top league (Legend).'
    )
    icon_url = models.URLField(
        max_length=500,
        blank=True,
        help_text='URL to the league icon/badge image.'
    )
    color_hex = models.CharField(
        max_length=7,
        blank=True,
        help_text='Hex color code for the league (e.g., "#CD7F32" for Bronze).'
    )
    description = models.TextField(
        blank=True,
        help_text='Description of the league and what it represents.'
    )
    rewards = models.JSONField(
        default=list,
        blank=True,
        help_text='List of rewards for reaching this league (e.g., badges, titles).'
    )

    class Meta:
        db_table = 'leagues'
        ordering = ['min_xp']
        verbose_name = 'League'
        verbose_name_plural = 'Leagues'
        indexes = [
            models.Index(fields=['min_xp', 'max_xp'], name='idx_league_xp_range'),
            models.Index(fields=['tier'], name='idx_league_tier'),
        ]

    def __str__(self):
        if self.max_xp is not None:
            return f"{self.name} ({self.min_xp}-{self.max_xp} XP)"
        return f"{self.name} ({self.min_xp}+ XP)"

    @property
    def tier_order(self):
        """Return the numeric order of this tier for sorting."""
        return self.TIER_ORDER.get(self.tier, 0)

    def contains_xp(self, xp):
        """Check if a given XP value falls within this league's range."""
        if self.max_xp is None:
            return xp >= self.min_xp
        return self.min_xp <= xp <= self.max_xp


class Season(models.Model):
    """
    Represents a competitive season with a defined time period.

    Seasons provide a time-bounded context for rankings and rewards.
    Only one season can be active at a time. When a season ends,
    rewards are calculated and distributed to eligible users.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text='Unique identifier for this season.'
    )
    name = models.CharField(
        max_length=200,
        help_text='Display name of the season (e.g., "Season 1 - Winter 2026").'
    )
    start_date = models.DateTimeField(
        help_text='When this season starts.'
    )
    end_date = models.DateTimeField(
        help_text='When this season ends.'
    )
    is_active = models.BooleanField(
        default=False,
        db_index=True,
        help_text='Whether this season is currently active. Only one season should be active at a time.'
    )
    rewards = models.JSONField(
        default=list,
        blank=True,
        help_text='List of rewards available for this season (varies by league achieved).'
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'seasons'
        ordering = ['-start_date']
        verbose_name = 'Season'
        verbose_name_plural = 'Seasons'
        indexes = [
            models.Index(fields=['is_active'], name='idx_season_active'),
            models.Index(fields=['start_date', 'end_date'], name='idx_season_dates'),
        ]

    def __str__(self):
        status = "Active" if self.is_active else "Inactive"
        return f"{self.name} ({status})"

    @property
    def is_current(self):
        """Check if the current time falls within this season's dates."""
        now = django_timezone.now()
        return self.start_date <= now <= self.end_date

    @property
    def has_ended(self):
        """Check if this season has ended."""
        return django_timezone.now() > self.end_date

    @property
    def days_remaining(self):
        """Return the number of days remaining in this season."""
        if self.has_ended:
            return 0
        delta = self.end_date - django_timezone.now()
        return max(0, delta.days)

    @classmethod
    def get_active_season(cls):
        """Return the currently active season, or None if none is active."""
        key = 'active_season'
        season = cache.get(key)
        if season is None:
            season = cls.objects.filter(is_active=True).first()
            if season:
                cache.set(key, season, 3600)
        return season


class LeagueStanding(models.Model):
    """
    Tracks a user's standing within a league for a given season.

    This is the core model for leaderboard queries. It stores
    the user's rank, XP earned, and various achievement metrics
    for the current season. Indexed heavily for fast leaderboard
    retrieval.

    Privacy note: This model exposes scores and stats but NEVER
    references user dreams directly.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text='Unique identifier for this standing record.'
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='league_standings',
        help_text='The user this standing belongs to.'
    )
    league = models.ForeignKey(
        League,
        on_delete=models.CASCADE,
        related_name='standings',
        help_text='The league this user is currently in.'
    )
    season = models.ForeignKey(
        Season,
        on_delete=models.CASCADE,
        related_name='standings',
        help_text='The season this standing applies to.'
    )
    rank = models.IntegerField(
        default=0,
        db_index=True,
        help_text='Current rank within the league for this season (1 = top).'
    )
    xp_earned_this_season = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0)],
        help_text='Total XP earned during this season.'
    )
    tasks_completed = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0)],
        help_text='Number of tasks completed during this season.'
    )
    dreams_completed = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0)],
        help_text='Number of dreams completed during this season.'
    )
    streak_best = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0)],
        help_text='Best streak (consecutive days) during this season.'
    )

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'league_standings'
        ordering = ['rank']
        verbose_name = 'League Standing'
        verbose_name_plural = 'League Standings'
        constraints = [
            models.UniqueConstraint(fields=['user', 'season'], name='unique_league_standing'),
        ]
        indexes = [
            # Primary leaderboard query: rank within a season
            models.Index(
                fields=['season', 'rank'],
                name='idx_standing_season_rank'
            ),
            # League-specific leaderboard: users in same league, sorted by XP
            models.Index(
                fields=['season', 'league', '-xp_earned_this_season'],
                name='idx_standing_league_xp'
            ),
            # Global leaderboard: top users by XP across all leagues
            models.Index(
                fields=['season', '-xp_earned_this_season'],
                name='idx_standing_season_xp'
            ),
            # User lookup: find a specific user's standing quickly
            models.Index(
                fields=['user', 'season'],
                name='idx_standing_user_season'
            ),
            # Rank ordering within league
            models.Index(
                fields=['league', 'rank'],
                name='idx_standing_league_rank'
            ),
        ]

    def __str__(self):
        return (
            f"{self.user.display_name or self.user.email} - "
            f"Rank #{self.rank} in {self.league.name} "
            f"({self.xp_earned_this_season} XP)"
        )


class SeasonReward(models.Model):
    """
    Tracks rewards earned by a user at the end of a season.

    When a season ends, rewards are calculated based on the league
    the user achieved. Users must explicitly claim their rewards,
    which is tracked here.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text='Unique identifier for this reward record.'
    )
    season = models.ForeignKey(
        Season,
        on_delete=models.CASCADE,
        related_name='season_rewards',
        help_text='The season this reward is from.'
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='season_rewards',
        help_text='The user who earned this reward.'
    )
    league_achieved = models.ForeignKey(
        League,
        on_delete=models.CASCADE,
        related_name='season_rewards',
        help_text='The league the user was in when the season ended.'
    )
    rewards_claimed = models.BooleanField(
        default=False,
        help_text='Whether the user has claimed their rewards.'
    )
    claimed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text='Timestamp when the rewards were claimed.'
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'season_rewards'
        ordering = ['-created_at']
        verbose_name = 'Season Reward'
        verbose_name_plural = 'Season Rewards'
        constraints = [
            models.UniqueConstraint(fields=['season', 'user'], name='unique_season_reward'),
        ]
        indexes = [
            models.Index(
                fields=['user', 'rewards_claimed'],
                name='idx_reward_user_claimed'
            ),
            models.Index(
                fields=['season', 'league_achieved'],
                name='idx_reward_season_league'
            ),
        ]

    def __str__(self):
        claimed_str = "Claimed" if self.rewards_claimed else "Unclaimed"
        return (
            f"{self.user.display_name or self.user.email} - "
            f"{self.season.name} - {self.league_achieved.name} ({claimed_str})"
        )

    def claim(self):
        """Mark this reward as claimed."""
        if not self.rewards_claimed:
            self.rewards_claimed = True
            self.claimed_at = django_timezone.now()
            self.save(update_fields=['rewards_claimed', 'claimed_at'])
            return True
        return False


class RankSnapshot(models.Model):
    """
    Periodic snapshot of a user's rank for historical tracking.

    Created daily by a Celery beat task to enable rank history
    charts and trend analysis.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='rank_snapshots',
    )
    season = models.ForeignKey(
        Season,
        on_delete=models.CASCADE,
        related_name='rank_snapshots',
    )
    league = models.ForeignKey(
        League,
        on_delete=models.CASCADE,
        related_name='rank_snapshots',
    )
    rank = models.IntegerField(
        help_text='Rank at the time of snapshot.',
    )
    xp = models.IntegerField(
        help_text='XP earned this season at the time of snapshot.',
    )
    snapshot_date = models.DateField(
        db_index=True,
        help_text='Date of this snapshot.',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'rank_snapshots'
        ordering = ['-snapshot_date']
        constraints = [
            models.UniqueConstraint(fields=['user', 'season', 'snapshot_date'], name='unique_rank_snapshot'),
        ]
        indexes = [
            models.Index(
                fields=['user', 'season', '-snapshot_date'],
                name='idx_snapshot_user_season_date',
            ),
        ]

    def __str__(self):
        return (
            f"{self.user.display_name or self.user.email} - "
            f"Rank #{self.rank} on {self.snapshot_date}"
        )


class LeagueSeason(models.Model):
    """
    Represents a themed competitive season with rewards.

    League seasons provide time-bounded, themed competitive periods with
    rank-based rewards. Each season has a visual theme (colors, name) and
    a set of tiered rewards that participants earn based on their final rank.
    Only one league season can be active at a time.
    """

    THEME_CHOICES = [
        ('growth', 'Growth'),
        ('fire', 'Fire'),
        ('ocean', 'Ocean'),
        ('cosmic', 'Cosmic'),
        ('aurora', 'Aurora'),
        ('crystal', 'Crystal'),
        ('storm', 'Storm'),
        ('bloom', 'Bloom'),
    ]

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text='Unique identifier for this league season.'
    )
    name = models.CharField(
        max_length=200,
        help_text='Display name of the season (e.g., "Season of Growth - Spring 2026").'
    )
    theme = models.CharField(
        max_length=50,
        choices=THEME_CHOICES,
        default='growth',
        help_text='Visual theme for the season (growth, fire, ocean, cosmic, etc.).'
    )
    description = models.TextField(
        blank=True,
        help_text='Description of the season theme and what makes it special.'
    )
    start_date = models.DateField(
        help_text='When this season starts.'
    )
    end_date = models.DateField(
        help_text='When this season ends.'
    )
    is_active = models.BooleanField(
        default=False,
        db_index=True,
        help_text='Whether this season is currently active. Only one should be active at a time.'
    )
    rewards = models.JSONField(
        default=list,
        blank=True,
        help_text=(
            'Tiered reward definitions. Each entry: '
            '{"rank_min": 1, "rank_max": 3, "reward_type": "badge", '
            '"reward_id": "gold_crown", "title": "Gold Crown Badge"}.'
        )
    )
    theme_colors = models.JSONField(
        default=dict,
        blank=True,
        help_text='Theme color palette: {"primary": "#hex", "secondary": "#hex", "accent": "#hex"}.'
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'league_seasons'
        ordering = ['-start_date']
        verbose_name = 'League Season'
        verbose_name_plural = 'League Seasons'
        indexes = [
            models.Index(fields=['is_active'], name='idx_lseason_active'),
            models.Index(fields=['start_date', 'end_date'], name='idx_lseason_dates'),
        ]

    def __str__(self):
        status = "Active" if self.is_active else "Inactive"
        return f"{self.name} ({status})"

    @property
    def is_current(self):
        """Check if today falls within this season's dates."""
        today = django_timezone.now().date()
        return self.start_date <= today <= self.end_date

    @property
    def has_ended(self):
        """Check if this season has ended."""
        return django_timezone.now().date() > self.end_date

    @property
    def days_remaining(self):
        """Return the number of days remaining in this season."""
        if self.has_ended:
            return 0
        delta = self.end_date - django_timezone.now().date()
        return max(0, delta.days)

    @classmethod
    def get_active_league_season(cls):
        """Return the currently active league season, or None."""
        key = 'active_league_season'
        season = cache.get(key)
        if season is None:
            season = cls.objects.filter(is_active=True).first()
            if season:
                cache.set(key, season, 3600)
        return season

    def get_reward_for_rank(self, rank):
        """Return the reward definition matching a given rank, or None."""
        for reward in (self.rewards or []):
            rank_min = reward.get('rank_min', 0)
            rank_max = reward.get('rank_max', 0)
            if rank_min <= rank <= rank_max:
                return reward
        return None


class SeasonParticipant(models.Model):
    """
    Tracks a user's participation in a themed league season.

    Records XP earned, final rank, and whether rewards have been claimed.
    Each user can only participate once per season.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text='Unique identifier for this participant record.'
    )
    season = models.ForeignKey(
        LeagueSeason,
        on_delete=models.CASCADE,
        related_name='participants',
        help_text='The league season this participation belongs to.'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='season_participations',
        help_text='The user participating in the season.'
    )
    xp_earned = models.PositiveIntegerField(
        default=0,
        help_text='Total XP earned during this season.'
    )
    rank = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text='Final rank in the season (computed from XP).'
    )
    rewards_claimed = models.BooleanField(
        default=False,
        help_text='Whether the user has claimed their end-of-season rewards.'
    )
    joined_at = models.DateTimeField(
        auto_now_add=True,
        help_text='When the user joined this season.'
    )

    class Meta:
        db_table = 'season_participants'
        unique_together = ('season', 'user')
        ordering = ['-xp_earned']
        verbose_name = 'Season Participant'
        verbose_name_plural = 'Season Participants'
        indexes = [
            models.Index(
                fields=['season', '-xp_earned'],
                name='idx_sparticipant_season_xp'
            ),
            models.Index(
                fields=['season', 'rank'],
                name='idx_sparticipant_season_rank'
            ),
            models.Index(
                fields=['user', 'season'],
                name='idx_sparticipant_user_season'
            ),
        ]

    def __str__(self):
        rank_str = f"Rank #{self.rank}" if self.rank else "Unranked"
        return (
            f"{self.user.display_name or self.user.email} - "
            f"{self.season.name} - {rank_str} ({self.xp_earned} XP)"
        )

    def claim_rewards(self):
        """Mark rewards as claimed if not already done."""
        if not self.rewards_claimed:
            self.rewards_claimed = True
            self.save(update_fields=['rewards_claimed'])
            return True
        return False
