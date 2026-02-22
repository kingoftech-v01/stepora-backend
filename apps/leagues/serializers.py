"""
Serializers for the Leagues & Ranking system.

These serializers expose league standings, leaderboard entries, and season
data. By design, they expose user display_name, avatar, level, and badges
but NEVER expose user dreams (privacy by design).
"""

from rest_framework import serializers

from .models import League, LeagueStanding, Season, SeasonReward


class LeagueSerializer(serializers.ModelSerializer):
    """
    Serializer for the League model.

    Provides full league details including tier, XP range, styling,
    and associated rewards.
    """

    tier_order = serializers.IntegerField(read_only=True)

    class Meta:
        model = League
        fields = [
            'id',
            'name',
            'tier',
            'tier_order',
            'min_xp',
            'max_xp',
            'icon_url',
            'color_hex',
            'description',
            'rewards',
        ]
        read_only_fields = fields


class LeagueStandingSerializer(serializers.ModelSerializer):
    """
    Serializer for a user's league standing.

    Includes user public profile data (display_name, avatar_url, level, badges)
    but explicitly excludes any dream-related information to protect privacy.
    """

    user_display_name = serializers.CharField(
        source='user.display_name',
        read_only=True
    )
    user_avatar_url = serializers.URLField(
        source='user.avatar_url',
        read_only=True
    )
    user_level = serializers.IntegerField(
        source='user.level',
        read_only=True
    )
    user_badges = serializers.SerializerMethodField()
    league_name = serializers.CharField(
        source='league.name',
        read_only=True
    )
    league_tier = serializers.CharField(
        source='league.tier',
        read_only=True
    )
    league_color_hex = serializers.CharField(
        source='league.color_hex',
        read_only=True
    )
    league_icon_url = serializers.URLField(
        source='league.icon_url',
        read_only=True
    )

    class Meta:
        model = LeagueStanding
        fields = [
            'id',
            'user',
            'user_display_name',
            'user_avatar_url',
            'user_level',
            'user_badges',
            'league',
            'league_name',
            'league_tier',
            'league_color_hex',
            'league_icon_url',
            'season',
            'rank',
            'xp_earned_this_season',
            'tasks_completed',
            'dreams_completed',
            'streak_best',
            'updated_at',
        ]
        read_only_fields = fields

    def get_user_badges(self, obj):
        """
        Retrieve the user's badges from their gamification profile.

        Returns an empty list if the user has no gamification profile.
        This is public data; dreams are never exposed.
        """
        try:
            gamification = obj.user.gamification
            return gamification.badges or []
        except Exception:
            return []


class SeasonSerializer(serializers.ModelSerializer):
    """
    Serializer for the Season model.

    Includes computed properties for season status (remaining days,
    whether it has ended, etc.).
    """

    is_current = serializers.BooleanField(read_only=True)
    has_ended = serializers.BooleanField(read_only=True)
    days_remaining = serializers.IntegerField(read_only=True)

    class Meta:
        model = Season
        fields = [
            'id',
            'name',
            'start_date',
            'end_date',
            'is_active',
            'rewards',
            'is_current',
            'has_ended',
            'days_remaining',
            'created_at',
            'updated_at',
        ]
        read_only_fields = fields


class SeasonRewardSerializer(serializers.ModelSerializer):
    """
    Serializer for season rewards.

    Shows what rewards a user earned for a given season and whether
    they have been claimed.
    """

    season_name = serializers.CharField(
        source='season.name',
        read_only=True
    )
    league_name = serializers.CharField(
        source='league_achieved.name',
        read_only=True
    )
    league_tier = serializers.CharField(
        source='league_achieved.tier',
        read_only=True
    )
    league_rewards = serializers.JSONField(
        source='league_achieved.rewards',
        read_only=True
    )

    class Meta:
        model = SeasonReward
        fields = [
            'id',
            'season',
            'season_name',
            'user',
            'league_achieved',
            'league_name',
            'league_tier',
            'league_rewards',
            'rewards_claimed',
            'claimed_at',
            'created_at',
        ]
        read_only_fields = fields


class LeaderboardEntrySerializer(serializers.Serializer):
    """
    Lightweight serializer for leaderboard display.

    Optimized for the leaderboard list view where only essential
    ranking information is needed. Exposes scores and badges count
    but NEVER user dreams.
    """

    rank = serializers.IntegerField(
        help_text='Position on the leaderboard (1 = highest).'
    )
    user_id = serializers.UUIDField(
        help_text='Unique identifier of the user.'
    )
    user_display_name = serializers.CharField(
        help_text='Public display name of the user.'
    )
    user_avatar_url = serializers.URLField(
        allow_blank=True,
        help_text='URL to the user avatar image.'
    )
    user_level = serializers.IntegerField(
        help_text='Current level of the user.'
    )
    league_name = serializers.CharField(
        help_text='Name of the league the user belongs to.'
    )
    league_tier = serializers.CharField(
        help_text='Tier of the league (e.g., bronze, silver, gold).'
    )
    league_color_hex = serializers.CharField(
        help_text='Hex color code for the league.'
    )
    xp = serializers.IntegerField(
        help_text='Total XP earned this season.'
    )
    tasks_completed = serializers.IntegerField(
        help_text='Number of tasks completed this season.'
    )
    badges_count = serializers.IntegerField(
        help_text='Total number of badges earned.'
    )
    is_current_user = serializers.BooleanField(
        default=False,
        help_text='Whether this entry represents the requesting user.'
    )
