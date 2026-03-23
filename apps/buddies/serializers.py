"""
Serializers for the Buddies system.

These serializers handle buddy pairing data, progress comparisons,
and match results for the DreamBuddyScreen in the mobile app.
"""

from rest_framework import serializers

from core.sanitizers import sanitize_text


class BuddyPartnerSerializer(serializers.Serializer):
    """Serializer for a buddy partner's public profile."""

    id = serializers.UUIDField(help_text="Partner user ID.")
    username = serializers.CharField(help_text="Partner display name.")
    avatar = serializers.CharField(
        allow_blank=True, default="", help_text="Partner avatar URL."
    )
    title = serializers.CharField(help_text="Partner title based on level.")
    current_level = serializers.IntegerField(help_text="Partner current level.")
    influence_score = serializers.IntegerField(help_text="Partner influence (XP).")
    current_streak = serializers.IntegerField(help_text="Partner streak days.")


class BuddyPairingSerializer(serializers.Serializer):
    """Serializer for the current buddy pairing detail."""

    id = serializers.UUIDField(help_text="Pairing ID.")
    partner = BuddyPartnerSerializer(help_text="Partner profile info.")
    compatibility_score = serializers.FloatField(help_text="Compatibility score 0-1.")
    status = serializers.CharField(help_text="Pairing status.")
    recent_activity = serializers.IntegerField(help_text="Partner tasks this week.")
    encouragement_streak = serializers.IntegerField(
        help_text="Current encouragement streak."
    )
    best_encouragement_streak = serializers.IntegerField(
        help_text="Best encouragement streak ever."
    )
    created_at = serializers.DateTimeField(help_text="When the pairing was created.")


class BuddyProgressSerializer(serializers.Serializer):
    """Serializer for buddy progress comparison."""

    user = serializers.DictField(help_text="Current user progress stats.")
    partner = serializers.DictField(help_text="Partner progress stats.")


class BuddyMatchSerializer(serializers.Serializer):
    """Serializer for a potential buddy match result."""

    user_id = serializers.UUIDField(help_text="Matched user ID.")
    username = serializers.CharField(help_text="Matched user display name.")
    avatar = serializers.CharField(
        allow_blank=True, default="", help_text="Matched user avatar."
    )
    compatibility_score = serializers.FloatField(help_text="Compatibility score 0-1.")
    shared_interests = serializers.ListField(
        child=serializers.CharField(), help_text="List of shared interest categories."
    )


class AIBuddyMatchSerializer(serializers.Serializer):
    """Serializer for an AI-scored buddy match result."""

    user_id = serializers.UUIDField(help_text="Matched user ID.")
    username = serializers.CharField(help_text="Matched user display name.")
    avatar = serializers.CharField(
        allow_blank=True, default="", help_text="Matched user avatar."
    )
    bio = serializers.CharField(
        allow_blank=True, default="", help_text="Matched user bio."
    )
    level = serializers.IntegerField(help_text="User level.")
    streak = serializers.IntegerField(help_text="User streak days.")
    xp = serializers.IntegerField(help_text="User XP.")
    dreamer_type = serializers.CharField(
        allow_blank=True, default="", help_text="User dreamer type."
    )
    compatibility_score = serializers.FloatField(
        help_text="AI compatibility score 0-1."
    )
    reasons = serializers.ListField(
        child=serializers.CharField(), help_text="Reasons why these users match well."
    )
    shared_interests = serializers.ListField(
        child=serializers.CharField(),
        help_text="Shared interest areas identified by AI.",
    )
    potential_challenges = serializers.ListField(
        child=serializers.CharField(), help_text="Potential challenges in the pairing."
    )
    suggested_icebreaker = serializers.CharField(
        help_text="AI-suggested opening message."
    )
    dreams = serializers.ListField(
        child=serializers.CharField(), help_text="Candidate dream titles."
    )
    categories = serializers.ListField(
        child=serializers.CharField(), help_text="Candidate dream categories."
    )


class BuddyPairRequestSerializer(serializers.Serializer):
    """Serializer for pairing with a specific user."""

    partner_id = serializers.UUIDField(help_text="The UUID of the user to pair with.")


class BuddyEncourageSerializer(serializers.Serializer):
    """Serializer for sending encouragement to a buddy."""

    message = serializers.CharField(
        required=False,
        default="",
        max_length=1000,
        help_text="Optional motivational message.",
    )

    def validate_message(self, value):
        return sanitize_text(value)


class BuddyHistorySerializer(serializers.Serializer):
    """Serializer for buddy pairing history entries."""

    id = serializers.UUIDField(help_text="Pairing ID.")
    partner = BuddyPartnerSerializer(help_text="Partner profile info.")
    status = serializers.CharField(help_text="Pairing status.")
    compatibility_score = serializers.FloatField(help_text="Compatibility score.")
    encouragement_count = serializers.IntegerField(
        help_text="Total encouragements sent."
    )
    encouragement_streak = serializers.IntegerField(
        help_text="Final encouragement streak."
    )
    best_encouragement_streak = serializers.IntegerField(
        help_text="Best encouragement streak."
    )
    duration_days = serializers.IntegerField(
        allow_null=True, help_text="Duration in days."
    )
    created_at = serializers.DateTimeField(help_text="Pairing start date.")
    ended_at = serializers.DateTimeField(allow_null=True, help_text="Pairing end date.")


# ─── Accountability Contracts ─────────────────────────────────────────


class ContractGoalSerializer(serializers.Serializer):
    """Serializer for a single goal within a contract."""

    title = serializers.CharField(max_length=200, help_text="Goal title.")
    target = serializers.FloatField(help_text="Target number to achieve.")
    unit = serializers.CharField(
        max_length=50, help_text="Unit of measurement (e.g. tasks, minutes)."
    )


class ContractCheckInSerializer(serializers.Serializer):
    """Serializer for a contract check-in entry."""

    id = serializers.UUIDField(read_only=True, help_text="Check-in ID.")
    user_id = serializers.UUIDField(read_only=True, help_text="User who checked in.")
    username = serializers.CharField(
        read_only=True, help_text="Display name of the user."
    )
    progress = serializers.DictField(help_text="Progress values keyed by goal index.")
    note = serializers.CharField(
        required=False,
        allow_blank=True,
        default="",
        max_length=2000,
        help_text="Optional note.",
    )
    mood = serializers.CharField(
        required=False,
        allow_blank=True,
        default="",
        max_length=20,
        help_text="User mood.",
    )
    created_at = serializers.DateTimeField(
        read_only=True,
        help_text="When the check-in was submitted.",
    )

    def validate_note(self, value):
        return sanitize_text(value)


class AccountabilityContractSerializer(serializers.Serializer):
    """Serializer for accountability contract list and detail."""

    id = serializers.UUIDField(read_only=True, help_text="Contract ID.")
    pairing_id = serializers.UUIDField(help_text="Buddy pairing ID.")
    title = serializers.CharField(max_length=200, help_text="Contract title.")
    description = serializers.CharField(
        required=False, allow_blank=True, default="", help_text="Contract description."
    )
    goals = ContractGoalSerializer(many=True, help_text="List of goals.")
    check_in_frequency = serializers.ChoiceField(
        choices=["daily", "weekly", "biweekly"],
        default="weekly",
        help_text="Check-in frequency.",
    )
    start_date = serializers.DateField(help_text="Contract start date.")
    end_date = serializers.DateField(help_text="Contract end date.")
    status = serializers.CharField(read_only=True, help_text="Contract status.")
    created_by_id = serializers.UUIDField(read_only=True, help_text="Creator user ID.")
    accepted_by_partner = serializers.BooleanField(
        read_only=True,
        help_text="Whether partner accepted.",
    )
    created_at = serializers.DateTimeField(
        read_only=True, help_text="Creation timestamp."
    )

    def validate_title(self, value):
        return sanitize_text(value)

    def validate_description(self, value):
        return sanitize_text(value)

    def validate(self, data):
        if data.get("start_date") and data.get("end_date"):
            if data["end_date"] <= data["start_date"]:
                raise serializers.ValidationError(
                    {"end_date": "End date must be after start date."}
                )
        goals = data.get("goals", [])
        if not goals:
            raise serializers.ValidationError(
                {"goals": "At least one goal is required."}
            )
        if len(goals) > 10:
            raise serializers.ValidationError(
                {"goals": "Maximum 10 goals per contract."}
            )
        return data


class ContractCheckInCreateSerializer(serializers.Serializer):
    """Serializer for creating a new check-in."""

    progress = serializers.DictField(help_text="Progress values keyed by goal index.")
    note = serializers.CharField(
        required=False,
        allow_blank=True,
        default="",
        max_length=2000,
        help_text="Optional note.",
    )
    mood = serializers.CharField(
        required=False,
        allow_blank=True,
        default="",
        max_length=20,
        help_text="User mood.",
    )

    def validate_note(self, value):
        return sanitize_text(value)


class ContractProgressSerializer(serializers.Serializer):
    """Serializer for contract progress comparison between both partners."""

    contract = AccountabilityContractSerializer(help_text="Contract details.")
    user_check_ins = ContractCheckInSerializer(
        many=True, help_text="Current user check-ins."
    )
    partner_check_ins = ContractCheckInSerializer(
        many=True, help_text="Partner check-ins."
    )
    user_totals = serializers.DictField(
        help_text="Aggregated progress totals for current user."
    )
    partner_totals = serializers.DictField(
        help_text="Aggregated progress totals for partner."
    )
