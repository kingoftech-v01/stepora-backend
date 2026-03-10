"""
Serializers for the Leagues & Ranking system.

These serializers expose league standings, leaderboard entries, and season
data. By design, they expose user display_name, avatar, level, and badges
but NEVER expose user dreams (privacy by design).
"""

from rest_framework import serializers

from .models import (
    League,
    LeagueGroup,
    LeagueGroupMembership,
    LeagueSeason,
    LeagueStanding,
    Season,
    SeasonConfig,
    SeasonParticipant,
    SeasonReward,
)


class LeagueSerializer(serializers.ModelSerializer):
    """
    Serializer for the League model.

    Provides full league details including tier, XP range, styling,
    and associated rewards.
    """

    tier_order = serializers.IntegerField(
        read_only=True, help_text="Numeric ordering of the tier for sorting."
    )

    class Meta:
        model = League
        fields = [
            "id",
            "name",
            "tier",
            "tier_order",
            "min_xp",
            "max_xp",
            "icon_url",
            "color_hex",
            "description",
            "rewards",
        ]
        read_only_fields = fields
        extra_kwargs = {
            "id": {"help_text": "Unique identifier for the league."},
            "name": {"help_text": "Display name of the league."},
            "tier": {"help_text": "Tier level of the league (e.g., bronze, silver)."},
            "min_xp": {"help_text": "Minimum XP required to enter this league."},
            "max_xp": {"help_text": "Maximum XP before promotion to the next league."},
            "icon_url": {"help_text": "URL to the league icon image."},
            "color_hex": {"help_text": "Hex color code representing the league."},
            "description": {"help_text": "Brief description of the league."},
            "rewards": {"help_text": "Rewards granted for reaching this league."},
        }


class LeagueStandingSerializer(serializers.ModelSerializer):
    """
    Serializer for a user's league standing.

    Includes user public profile data (display_name, avatar_url, level, badges)
    and auto-grouping fields (group_number, group_id, rank_in_group,
    promotion_eligible, relegation_risk). Explicitly excludes any
    dream-related information to protect privacy.
    """

    user_display_name = serializers.CharField(
        source="user.display_name",
        read_only=True,
        help_text="Public display name of the user.",
    )
    user_avatar_url = serializers.URLField(
        source="user.avatar_url",
        read_only=True,
        help_text="URL to the user avatar image.",
    )
    user_level = serializers.IntegerField(
        source="user.level", read_only=True, help_text="Current level of the user."
    )
    user_badges = serializers.SerializerMethodField(
        help_text="List of badges earned by the user."
    )
    league_name = serializers.CharField(
        source="league.name",
        read_only=True,
        help_text="Name of the league the user is in.",
    )
    league_tier = serializers.CharField(
        source="league.tier",
        read_only=True,
        help_text="Tier of the league (e.g., bronze, silver).",
    )
    league_color_hex = serializers.CharField(
        source="league.color_hex",
        read_only=True,
        help_text="Hex color code for the league.",
    )
    league_icon_url = serializers.URLField(
        source="league.icon_url",
        read_only=True,
        help_text="URL to the league icon image.",
    )

    # Auto-grouping fields
    group_number = serializers.SerializerMethodField(
        help_text="The group number the user is assigned to within their league."
    )
    group_id = serializers.SerializerMethodField(
        help_text="UUID of the group the user belongs to."
    )
    rank_in_group = serializers.SerializerMethodField(
        help_text="Rank within the user's group (1-indexed)."
    )
    promotion_eligible = serializers.SerializerMethodField(
        help_text="Whether the user's XP meets the promotion threshold."
    )
    relegation_risk = serializers.SerializerMethodField(
        help_text="Whether the user's XP is below the relegation threshold."
    )

    class Meta:
        model = LeagueStanding
        fields = [
            "id",
            "user",
            "user_display_name",
            "user_avatar_url",
            "user_level",
            "user_badges",
            "league",
            "league_name",
            "league_tier",
            "league_color_hex",
            "league_icon_url",
            "season",
            "rank",
            "xp_earned_this_season",
            "tasks_completed",
            "dreams_completed",
            "streak_best",
            "updated_at",
            "group_number",
            "group_id",
            "rank_in_group",
            "promotion_eligible",
            "relegation_risk",
        ]
        read_only_fields = fields
        extra_kwargs = {
            "id": {"help_text": "Unique identifier for the standing record."},
            "user": {"help_text": "User this standing belongs to."},
            "league": {"help_text": "League the user is currently placed in."},
            "season": {"help_text": "Season this standing applies to."},
            "rank": {"help_text": "Current rank within the league."},
            "xp_earned_this_season": {
                "help_text": "Total XP earned during this season."
            },
            "tasks_completed": {"help_text": "Number of tasks completed this season."},
            "dreams_completed": {
                "help_text": "Number of dreams completed this season."
            },
            "streak_best": {"help_text": "Longest streak achieved this season."},
            "updated_at": {
                "help_text": "Timestamp when the standing was last updated."
            },
        }

    def get_user_badges(self, obj) -> list:
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

    def _get_membership(self, obj):
        """Cache and return the group membership for this standing."""
        if not hasattr(obj, "_cached_group_membership"):
            try:
                obj._cached_group_membership = obj.group_membership
            except LeagueGroupMembership.DoesNotExist:
                obj._cached_group_membership = None
        return obj._cached_group_membership

    def get_group_number(self, obj) -> int:
        """Return the group number or None."""
        membership = self._get_membership(obj)
        return membership.group.group_number if membership else None

    def get_group_id(self, obj) -> str:
        """Return the group UUID or None."""
        membership = self._get_membership(obj)
        return str(membership.group_id) if membership else None

    def get_rank_in_group(self, obj) -> int:
        """
        Compute the user's rank within their group.

        Counts how many group members have more XP than this standing.
        """
        membership = self._get_membership(obj)
        if not membership:
            return None
        rank = (
            LeagueGroupMembership.objects.filter(
                group=membership.group,
                standing__xp_earned_this_season__gt=obj.xp_earned_this_season,
            ).count()
        ) + 1
        return rank

    def get_promotion_eligible(self, obj) -> bool:
        """Check if the user's XP meets the promotion threshold."""
        config = SeasonConfig.get()
        return obj.xp_earned_this_season >= config.promotion_xp_threshold

    def get_relegation_risk(self, obj) -> bool:
        """Check if the user's XP is below the relegation threshold."""
        config = SeasonConfig.get()
        return obj.xp_earned_this_season < config.relegation_xp_threshold


class SeasonSerializer(serializers.ModelSerializer):
    """
    Serializer for the Season model.

    Includes computed properties for season status (remaining days/seconds,
    whether it has ended, etc.) and promotion/relegation thresholds from
    the SeasonConfig singleton.
    """

    is_current = serializers.BooleanField(
        read_only=True, help_text="Whether this is the currently active season."
    )
    has_ended = serializers.BooleanField(
        read_only=True, help_text="Whether this season has ended."
    )
    days_remaining = serializers.IntegerField(
        read_only=True, help_text="Number of days left in the season."
    )
    seconds_remaining = serializers.IntegerField(
        read_only=True,
        help_text="Number of seconds remaining for live countdown.",
    )
    ends_at = serializers.DateTimeField(
        read_only=True,
        help_text="Alias for end_date as a datetime for live countdown.",
    )
    thresholds = serializers.SerializerMethodField(
        help_text="Promotion/relegation XP thresholds from SeasonConfig.",
    )

    class Meta:
        model = Season
        fields = [
            "id",
            "name",
            "start_date",
            "end_date",
            "ends_at",
            "is_active",
            "status",
            "duration_days",
            "rewards",
            "is_current",
            "has_ended",
            "days_remaining",
            "seconds_remaining",
            "thresholds",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields
        extra_kwargs = {
            "id": {"help_text": "Unique identifier for the season."},
            "name": {"help_text": "Display name of the season."},
            "start_date": {"help_text": "Start date of the season."},
            "end_date": {"help_text": "End date of the season."},
            "is_active": {"help_text": "Whether this season is currently active."},
            "status": {
                "help_text": "Lifecycle status (pending/active/processing/ended)."
            },
            "duration_days": {"help_text": "Duration of the season in days."},
            "rewards": {"help_text": "Rewards available for this season."},
            "created_at": {"help_text": "Timestamp when the season was created."},
            "updated_at": {"help_text": "Timestamp when the season was last updated."},
        }

    def get_thresholds(self, obj) -> dict:
        """Return promotion/relegation XP thresholds from SeasonConfig."""
        config = SeasonConfig.get()
        return {
            "promotion_xp": config.promotion_xp_threshold,
            "relegation_xp": config.relegation_xp_threshold,
        }


class SeasonRewardSerializer(serializers.ModelSerializer):
    """
    Serializer for season rewards.

    Shows what rewards a user earned for a given season and whether
    they have been claimed.
    """

    season_name = serializers.CharField(
        source="season.name",
        read_only=True,
        help_text="Name of the season the reward belongs to.",
    )
    league_name = serializers.CharField(
        source="league_achieved.name",
        read_only=True,
        help_text="Name of the league achieved.",
    )
    league_tier = serializers.CharField(
        source="league_achieved.tier",
        read_only=True,
        help_text="Tier of the league achieved.",
    )
    league_rewards = serializers.JSONField(
        source="league_achieved.rewards",
        read_only=True,
        help_text="Rewards associated with the achieved league.",
    )

    class Meta:
        model = SeasonReward
        fields = [
            "id",
            "season",
            "season_name",
            "user",
            "league_achieved",
            "league_name",
            "league_tier",
            "league_rewards",
            "rewards_claimed",
            "claimed_at",
            "created_at",
        ]
        read_only_fields = fields
        extra_kwargs = {
            "id": {"help_text": "Unique identifier for the season reward."},
            "season": {"help_text": "Season this reward belongs to."},
            "user": {"help_text": "User who earned this reward."},
            "league_achieved": {"help_text": "League the user reached in this season."},
            "rewards_claimed": {
                "help_text": "Whether the user has claimed the rewards."
            },
            "claimed_at": {"help_text": "Timestamp when the rewards were claimed."},
            "created_at": {
                "help_text": "Timestamp when the reward record was created."
            },
        }


class LeaderboardEntrySerializer(serializers.Serializer):
    """
    Lightweight serializer for leaderboard display.

    Optimized for the leaderboard list view where only essential
    ranking information is needed. Exposes scores and badges count
    but NEVER user dreams.
    """

    rank = serializers.IntegerField(
        help_text="Position on the leaderboard (1 = highest)."
    )
    user_id = serializers.UUIDField(help_text="Unique identifier of the user.")
    user_display_name = serializers.CharField(
        help_text="Public display name of the user."
    )
    user_avatar_url = serializers.URLField(
        allow_blank=True, help_text="URL to the user avatar image."
    )
    user_level = serializers.IntegerField(help_text="Current level of the user.")
    league_name = serializers.CharField(
        help_text="Name of the league the user belongs to."
    )
    league_tier = serializers.CharField(
        help_text="Tier of the league (e.g., bronze, silver, gold)."
    )
    league_color_hex = serializers.CharField(help_text="Hex color code for the league.")
    xp = serializers.IntegerField(help_text="Total XP earned this season.")
    tasks_completed = serializers.IntegerField(
        help_text="Number of tasks completed this season."
    )
    badges_count = serializers.IntegerField(help_text="Total number of badges earned.")
    is_current_user = serializers.BooleanField(
        default=False, help_text="Whether this entry represents the requesting user."
    )


class LeagueSeasonSerializer(serializers.ModelSerializer):
    """
    Serializer for the LeagueSeason model.

    Includes computed properties for season status (remaining days,
    whether it's current, whether it has ended) and participant count.
    """

    is_current = serializers.BooleanField(
        read_only=True, help_text="Whether today falls within this season's dates."
    )
    has_ended = serializers.BooleanField(
        read_only=True, help_text="Whether this season has ended."
    )
    days_remaining = serializers.IntegerField(
        read_only=True, help_text="Number of days left in the season."
    )
    participant_count = serializers.SerializerMethodField(
        help_text="Total number of participants in this season."
    )
    user_participation = serializers.SerializerMethodField(
        help_text="Current user's participation data, or null if not joined."
    )

    class Meta:
        model = LeagueSeason
        fields = [
            "id",
            "name",
            "theme",
            "description",
            "start_date",
            "end_date",
            "is_active",
            "rewards",
            "theme_colors",
            "is_current",
            "has_ended",
            "days_remaining",
            "participant_count",
            "user_participation",
            "created_at",
        ]
        read_only_fields = fields
        extra_kwargs = {
            "id": {"help_text": "Unique identifier for the league season."},
            "name": {"help_text": "Display name of the season."},
            "theme": {"help_text": "Visual theme key (growth, fire, ocean, etc.)."},
            "description": {"help_text": "Description of the season."},
            "start_date": {"help_text": "Start date of the season."},
            "end_date": {"help_text": "End date of the season."},
            "is_active": {"help_text": "Whether this season is currently active."},
            "rewards": {"help_text": "Tiered reward definitions."},
            "theme_colors": {
                "help_text": "Theme color palette (primary, secondary, accent)."
            },
            "created_at": {"help_text": "Timestamp when the season was created."},
        }

    def get_participant_count(self, obj) -> int:
        """Return the total number of participants in this season."""
        return obj.participants.count()

    def get_user_participation(self, obj) -> dict:
        """
        Return the current user's participation data for this season.

        Returns None if the user is not participating.
        """
        request = self.context.get("request")
        if not request or not request.user or not request.user.is_authenticated:
            return None

        try:
            participant = SeasonParticipant.objects.get(season=obj, user=request.user)
            return {
                "id": str(participant.id),
                "xp_earned": participant.xp_earned,
                "rank": participant.rank,
                "rewards_claimed": participant.rewards_claimed,
                "joined_at": (
                    participant.joined_at.isoformat() if participant.joined_at else None
                ),
            }
        except SeasonParticipant.DoesNotExist:
            return None


class SeasonParticipantSerializer(serializers.ModelSerializer):
    """
    Serializer for season participant entries on the leaderboard.

    Includes user display data (name, avatar, level) for leaderboard
    rendering. Never exposes user dreams (privacy by design).
    """

    user_display_name = serializers.CharField(
        source="user.display_name",
        read_only=True,
        help_text="Public display name of the user.",
    )
    user_avatar_url = serializers.URLField(
        source="user.avatar_url",
        read_only=True,
        allow_blank=True,
        help_text="URL to the user avatar image.",
    )
    user_level = serializers.IntegerField(
        source="user.level", read_only=True, help_text="Current level of the user."
    )
    projected_reward = serializers.SerializerMethodField(
        help_text="The reward the user would earn at their current rank."
    )

    class Meta:
        model = SeasonParticipant
        fields = [
            "id",
            "season",
            "user",
            "user_display_name",
            "user_avatar_url",
            "user_level",
            "xp_earned",
            "rank",
            "rewards_claimed",
            "joined_at",
            "projected_reward",
        ]
        read_only_fields = fields
        extra_kwargs = {
            "id": {"help_text": "Unique identifier for this participant record."},
            "season": {"help_text": "The season this participation belongs to."},
            "user": {"help_text": "The user participating."},
            "xp_earned": {"help_text": "Total XP earned this season."},
            "rank": {"help_text": "Current rank in the season."},
            "rewards_claimed": {"help_text": "Whether rewards have been claimed."},
            "joined_at": {"help_text": "When the user joined this season."},
        }

    def get_projected_reward(self, obj) -> dict:
        """Return the reward matching the user's current rank, or None."""
        if obj.rank is None:
            return None
        return obj.season.get_reward_for_rank(obj.rank)


class LeagueGroupSerializer(serializers.ModelSerializer):
    """
    Serializer for the LeagueGroup model.

    Includes league name/tier, member count, and season info.
    """

    league_name = serializers.CharField(
        source="league.name",
        read_only=True,
        help_text="Display name of the league tier.",
    )
    league_tier = serializers.CharField(
        source="league.tier",
        read_only=True,
        help_text="Tier key of the league.",
    )
    league_color_hex = serializers.CharField(
        source="league.color_hex",
        read_only=True,
        help_text="Hex color code for the league.",
    )
    season_name = serializers.CharField(
        source="season.name",
        read_only=True,
        help_text="Display name of the season.",
    )
    member_count = serializers.IntegerField(
        read_only=True,
        help_text="Number of members in this group.",
    )

    class Meta:
        model = LeagueGroup
        fields = [
            "id",
            "season",
            "season_name",
            "league",
            "league_name",
            "league_tier",
            "league_color_hex",
            "group_number",
            "is_active",
            "member_count",
            "created_at",
        ]
        read_only_fields = fields
        extra_kwargs = {
            "id": {"help_text": "Unique identifier for the group."},
            "season": {"help_text": "Season this group belongs to."},
            "league": {"help_text": "League tier this group is in."},
            "group_number": {"help_text": "Group number within the league."},
            "is_active": {"help_text": "Whether this group is currently active."},
            "created_at": {"help_text": "When this group was created."},
        }


class SeasonConfigSerializer(serializers.ModelSerializer):
    """
    Read-only serializer for the SeasonConfig singleton.

    Exposes all configuration values for frontend display.
    """

    class Meta:
        model = SeasonConfig
        fields = [
            "season_duration_days",
            "group_target_size",
            "group_max_size",
            "group_min_size",
            "promotion_xp_threshold",
            "relegation_xp_threshold",
            "auto_create_next_season",
        ]
        read_only_fields = fields
