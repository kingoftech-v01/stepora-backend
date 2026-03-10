"""
Django admin configuration for the Leagues & Ranking system.

Provides admin interfaces for managing leagues, seasons, standings,
season rewards, groups, and the SeasonConfig singleton with inline
editing and filtering capabilities.
"""

from django.contrib import admin, messages

from .models import (
    League, LeagueStanding, Season, SeasonReward, RankSnapshot,
    LeagueSeason, SeasonParticipant, SeasonConfig, LeagueGroup,
    LeagueGroupMembership,
)


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
        'name', 'status', 'start_date', 'end_date', 'is_active',
        'duration_days', 'days_remaining', 'created_at',
    ]
    list_filter = ['is_active', 'status', 'start_date']
    search_fields = ['name']
    ordering = ['-start_date']
    readonly_fields = ['created_at', 'updated_at']

    inlines = [LeagueStandingInline]

    fieldsets = (
        ('Basic Info', {
            'fields': ('name', 'status', 'is_active')
        }),
        ('Dates', {
            'fields': ('start_date', 'end_date', 'duration_days')
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


# ------------------------------------------------------------------
# Auto-Grouping Admin
# ------------------------------------------------------------------

@admin.register(SeasonConfig)
class SeasonConfigAdmin(admin.ModelAdmin):
    """
    Singleton admin for SeasonConfig.

    Only one row should exist. The add permission is blocked once a
    config row exists, and delete is always blocked.
    """

    list_display = [
        'season_duration_days', 'group_target_size', 'group_max_size',
        'group_min_size', 'promotion_xp_threshold', 'relegation_xp_threshold',
        'auto_create_next_season', 'updated_at',
    ]
    readonly_fields = ['id', 'updated_at']

    fieldsets = (
        ('Season Duration', {
            'fields': ('season_duration_days', 'auto_create_next_season'),
        }),
        ('Group Sizing', {
            'fields': ('group_target_size', 'group_max_size', 'group_min_size'),
        }),
        ('Promotion / Relegation', {
            'fields': ('promotion_xp_threshold', 'relegation_xp_threshold'),
        }),
        ('Metadata', {
            'fields': ('id', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    def has_add_permission(self, request):
        """Block adding if a config already exists."""
        if SeasonConfig.objects.exists():
            return False
        return super().has_add_permission(request)

    def has_delete_permission(self, request, obj=None):
        """Never allow deleting the singleton config."""
        return False


class LeagueGroupMembershipInline(admin.TabularInline):
    """Inline admin for group memberships within LeagueGroup."""

    model = LeagueGroupMembership
    fk_name = 'group'
    extra = 0
    fields = ['standing', 'joined_at', 'promoted_from_group']
    readonly_fields = ['joined_at']
    raw_id_fields = ['standing', 'promoted_from_group']


@admin.register(LeagueGroup)
class LeagueGroupAdmin(admin.ModelAdmin):
    """Admin interface for LeagueGroup with inline memberships."""

    list_display = [
        'group_number', 'league', 'season', 'is_active',
        'member_count_display', 'created_at',
    ]
    list_filter = ['is_active', 'league', 'season']
    search_fields = ['league__name', 'season__name']
    ordering = ['season', 'league', 'group_number']
    readonly_fields = ['id', 'created_at']
    raw_id_fields = ['season', 'league']

    inlines = [LeagueGroupMembershipInline]

    actions = ['rebalance_groups']

    fieldsets = (
        ('Group Info', {
            'fields': ('season', 'league', 'group_number', 'is_active'),
        }),
        ('Metadata', {
            'fields': ('id', 'created_at'),
            'classes': ('collapse',),
        }),
    )

    def member_count_display(self, obj):
        """Display the number of members in this group."""
        return obj.member_count
    member_count_display.short_description = 'Members'

    @admin.action(description='Rebalance groups for selected league(s)')
    def rebalance_groups(self, request, queryset):
        """
        Admin action to rebalance groups.

        Collects unique (season, league) pairs from the selected groups
        and runs the rebalance service for each.
        """
        from .services import LeagueService

        pairs_seen = set()
        total_moved = 0

        for group in queryset.select_related('season', 'league'):
            pair = (group.season_id, group.league_id)
            if pair in pairs_seen:
                continue
            pairs_seen.add(pair)

            stats = LeagueService.rebalance_league_groups(group.season, group.league)
            total_moved += stats['members_moved']

        self.message_user(
            request,
            f'Rebalanced {len(pairs_seen)} league(s). {total_moved} member(s) moved.',
            messages.SUCCESS,
        )
