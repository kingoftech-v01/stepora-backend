"""
Django admin configuration for the Leagues & Ranking system.

Provides admin interfaces for managing leagues, seasons, standings,
and season rewards with inline editing and filtering capabilities.
"""

from django.contrib import admin

from .models import League, LeagueStanding, Season, SeasonReward, RankSnapshot, LeagueSeason, SeasonParticipant


@admin.register(League)
class LeagueAdmin(admin.ModelAdmin):
    """Admin interface for League model."""

    list_display = [
        'name', 'tier', 'min_xp', 'max_xp', 'color_hex',
    ]
    list_filter = ['tier']
    search_fields = ['name', 'tier']
    ordering = ['min_xp']
    readonly_fields = []

    fieldsets = (
        ('Basic Info', {
            'fields': ('name', 'tier', 'description')
        }),
        ('XP Range', {
            'fields': ('min_xp', 'max_xp')
        }),
        ('Appearance', {
            'fields': ('icon_url', 'color_hex')
        }),
        ('Rewards', {
            'fields': ('rewards',),
            'classes': ('collapse',)
        }),
    )


class LeagueStandingInline(admin.TabularInline):
    """Inline admin for LeagueStanding within Season."""

    model = LeagueStanding
    extra = 0
    fields = [
        'user', 'league', 'rank', 'xp_earned_this_season',
        'tasks_completed', 'dreams_completed', 'streak_best',
    ]
    readonly_fields = ['updated_at']
    raw_id_fields = ['user']


@admin.register(Season)
class SeasonAdmin(admin.ModelAdmin):
    """Admin interface for Season model."""

    list_display = [
        'name', 'start_date', 'end_date', 'is_active',
        'days_remaining', 'created_at',
    ]
    list_filter = ['is_active', 'start_date']
    search_fields = ['name']
    ordering = ['-start_date']
    readonly_fields = ['created_at', 'updated_at']

    inlines = [LeagueStandingInline]

    fieldsets = (
        ('Basic Info', {
            'fields': ('name', 'is_active')
        }),
        ('Dates', {
            'fields': ('start_date', 'end_date')
        }),
        ('Rewards', {
            'fields': ('rewards',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def days_remaining(self, obj):
        """Display the number of days remaining in the season."""
        return obj.days_remaining
    days_remaining.short_description = 'Days Remaining'


@admin.register(LeagueStanding)
class LeagueStandingAdmin(admin.ModelAdmin):
    """Admin interface for LeagueStanding model."""

    list_display = [
        'user', 'league', 'season', 'rank',
        'xp_earned_this_season', 'tasks_completed',
        'dreams_completed', 'streak_best', 'updated_at',
    ]
    list_filter = ['league', 'season']
    search_fields = ['user__email', 'user__display_name']
    ordering = ['season', 'rank']
    readonly_fields = ['updated_at']
    raw_id_fields = ['user']

    fieldsets = (
        ('User & League', {
            'fields': ('user', 'league', 'season')
        }),
        ('Ranking', {
            'fields': ('rank', 'xp_earned_this_season')
        }),
        ('Stats', {
            'fields': ('tasks_completed', 'dreams_completed', 'streak_best')
        }),
        ('Timestamps', {
            'fields': ('updated_at',),
            'classes': ('collapse',)
        }),
    )


@admin.register(SeasonReward)
class SeasonRewardAdmin(admin.ModelAdmin):
    """Admin interface for SeasonReward model."""

    list_display = [
        'user', 'season', 'league_achieved',
        'rewards_claimed', 'claimed_at', 'created_at',
    ]
    list_filter = ['rewards_claimed', 'league_achieved', 'season']
    search_fields = ['user__email', 'user__display_name']
    ordering = ['-created_at']
    readonly_fields = ['created_at']
    raw_id_fields = ['user']

    fieldsets = (
        ('Reward Info', {
            'fields': ('season', 'user', 'league_achieved')
        }),
        ('Claim Status', {
            'fields': ('rewards_claimed', 'claimed_at')
        }),
        ('Timestamps', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )


@admin.register(RankSnapshot)
class RankSnapshotAdmin(admin.ModelAdmin):
    """Admin interface for RankSnapshot model."""

    list_display = ['user', 'season', 'league', 'rank', 'xp', 'snapshot_date', 'created_at']
    list_filter = ['league', 'season', 'snapshot_date']
    search_fields = ['user__email', 'user__display_name']
    ordering = ['-snapshot_date']
    readonly_fields = ['id', 'created_at']
    raw_id_fields = ['user', 'season', 'league']


@admin.register(LeagueSeason)
class LeagueSeasonAdmin(admin.ModelAdmin):
    """Admin interface for LeagueSeason model."""

    list_display = ['name', 'theme', 'start_date', 'end_date', 'is_active', 'created_at']
    list_filter = ['is_active', 'theme', 'start_date']
    search_fields = ['name', 'description']
    ordering = ['-start_date']
    readonly_fields = ['id', 'created_at']

    fieldsets = (
        ('Basic Info', {
            'fields': ('name', 'theme', 'description', 'is_active')
        }),
        ('Dates', {
            'fields': ('start_date', 'end_date')
        }),
        ('Configuration', {
            'fields': ('rewards', 'theme_colors'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('id', 'created_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(SeasonParticipant)
class SeasonParticipantAdmin(admin.ModelAdmin):
    """Admin interface for SeasonParticipant model."""

    list_display = ['user', 'season', 'xp_earned', 'rank', 'rewards_claimed', 'joined_at']
    list_filter = ['rewards_claimed', 'season', 'joined_at']
    search_fields = ['user__email', 'user__display_name']
    ordering = ['-xp_earned']
    readonly_fields = ['id', 'joined_at']
    raw_id_fields = ['user', 'season']
