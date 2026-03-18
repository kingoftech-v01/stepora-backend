"""
Unit tests for the Buddies app models and services.
"""

from datetime import timedelta
from unittest.mock import MagicMock, patch

import pytest
from django.utils import timezone

from apps.buddies.models import (
    AccountabilityContract,
    BuddyEncouragement,
    BuddyPairing,
)
from apps.buddies.services import BuddyMatchingService
from apps.users.models import User


# ── BuddyPairing model ───────────────────────────────────────────────


class TestBuddyPairingModel:
    """Tests for the BuddyPairing model."""

    def test_create_pairing(self, active_pairing, buddy_user1, buddy_user2):
        """BuddyPairing can be created with two users."""
        assert active_pairing.user1 == buddy_user1
        assert active_pairing.user2 == buddy_user2
        assert active_pairing.status == "active"
        assert active_pairing.compatibility_score == 0.75

    def test_status_choices(self, buddy_user1, buddy_user2):
        """All status choices work."""
        for code, _ in BuddyPairing.STATUS_CHOICES:
            pairing = BuddyPairing.objects.create(
                user1=buddy_user1,
                user2=buddy_user2,
                status=code,
                compatibility_score=0.5,
            )
            assert pairing.status == code
            pairing.delete()

    def test_str_representation(self, active_pairing):
        """__str__ includes both user names and status."""
        s = str(active_pairing)
        assert "Buddy One" in s
        assert "Buddy Two" in s
        assert "active" in s

    def test_compatibility_score_bounds(self, buddy_user1, buddy_user2):
        """Compatibility score is stored correctly."""
        pairing = BuddyPairing.objects.create(
            user1=buddy_user1,
            user2=buddy_user2,
            status="pending",
            compatibility_score=0.0,
        )
        assert pairing.compatibility_score == 0.0

    def test_ended_at_field(self, active_pairing):
        """ended_at can be set when pairing ends."""
        active_pairing.status = "completed"
        active_pairing.ended_at = timezone.now()
        active_pairing.save()
        active_pairing.refresh_from_db()
        assert active_pairing.ended_at is not None
        assert active_pairing.status == "completed"

    def test_expires_at_field(self, pending_pairing):
        """Pending pairings have an expiration date."""
        assert pending_pairing.expires_at is not None
        assert pending_pairing.status == "pending"

    def test_encouragement_streak(self, active_pairing):
        """Encouragement streak fields work correctly."""
        active_pairing.encouragement_streak = 5
        active_pairing.best_encouragement_streak = 10
        active_pairing.last_encouragement_at = timezone.now()
        active_pairing.save()
        active_pairing.refresh_from_db()
        assert active_pairing.encouragement_streak == 5
        assert active_pairing.best_encouragement_streak == 10


# ── BuddyMatchingService ─────────────────────────────────────────────


class TestBuddyMatchingService:
    """Tests for the BuddyMatchingService."""

    def test_service_instantiation(self):
        """BuddyMatchingService can be instantiated."""
        service = BuddyMatchingService()
        assert service is not None
        assert service.CATEGORY_WEIGHT == 0.40
        assert service.ACTIVITY_WEIGHT == 0.25
        assert service.TIMEZONE_WEIGHT == 0.20
        assert service.LEVEL_WEIGHT == 0.15

    def test_min_compatibility_score(self):
        """MIN_COMPATIBILITY_SCORE is 0.3."""
        assert BuddyMatchingService.MIN_COMPATIBILITY_SCORE == 0.3

    def test_calculate_activity_similarity_same(self):
        """Same streak days gives perfect score."""
        service = BuddyMatchingService()
        user1 = MagicMock(streak_days=5)
        user2 = MagicMock(streak_days=5)
        score = service._calculate_activity_similarity(user1, user2)
        assert score == 1.0

    def test_calculate_activity_similarity_close(self):
        """Close streak days give high score."""
        service = BuddyMatchingService()
        user1 = MagicMock(streak_days=5)
        user2 = MagicMock(streak_days=7)
        score = service._calculate_activity_similarity(user1, user2)
        assert score == 0.8

    def test_calculate_activity_similarity_medium(self):
        """Medium gap streak days give medium score."""
        service = BuddyMatchingService()
        user1 = MagicMock(streak_days=5)
        user2 = MagicMock(streak_days=12)
        score = service._calculate_activity_similarity(user1, user2)
        assert score == 0.6

    def test_calculate_activity_similarity_far(self):
        """Large gap streak days give low score."""
        service = BuddyMatchingService()
        user1 = MagicMock(streak_days=0)
        user2 = MagicMock(streak_days=50)
        score = service._calculate_activity_similarity(user1, user2)
        assert score == 0.1

    def test_calculate_timezone_proximity_same(self):
        """Same timezone gives perfect score."""
        service = BuddyMatchingService()
        user1 = MagicMock(timezone="Europe/Paris")
        user2 = MagicMock(timezone="Europe/Paris")
        score = service._calculate_timezone_proximity(user1, user2)
        assert score == 1.0

    def test_calculate_timezone_proximity_same_region(self):
        """Same region gives high score."""
        service = BuddyMatchingService()
        user1 = MagicMock(timezone="Europe/Paris")
        user2 = MagicMock(timezone="Europe/London")
        score = service._calculate_timezone_proximity(user1, user2)
        assert score == 0.7

    def test_calculate_timezone_proximity_different(self):
        """Different regions give low score."""
        service = BuddyMatchingService()
        user1 = MagicMock(timezone="Europe/Paris")
        user2 = MagicMock(timezone="America/New_York")
        score = service._calculate_timezone_proximity(user1, user2)
        assert score == 0.3

    def test_calculate_level_similarity_same(self):
        """Same level gives perfect score."""
        service = BuddyMatchingService()
        user1 = MagicMock(level=5)
        user2 = MagicMock(level=5)
        score = service._calculate_level_similarity(user1, user2)
        assert score == 1.0

    def test_calculate_level_similarity_close(self):
        """Close levels give high score."""
        service = BuddyMatchingService()
        user1 = MagicMock(level=5)
        user2 = MagicMock(level=7)
        score = service._calculate_level_similarity(user1, user2)
        assert score == 0.8

    def test_calculate_level_similarity_far(self):
        """Far levels give low score."""
        service = BuddyMatchingService()
        user1 = MagicMock(level=1)
        user2 = MagicMock(level=20)
        score = service._calculate_level_similarity(user1, user2)
        assert score == 0.2

    def test_find_compatible_no_candidates(self, buddy_user1):
        """find_compatible_buddy returns None when no candidates exist."""
        service = BuddyMatchingService()
        result = service.find_compatible_buddy(buddy_user1)
        assert result is None

    def test_create_buddy_request(self, buddy_user1, buddy_user3):
        """create_buddy_request creates a pending pairing."""
        service = BuddyMatchingService()
        with patch.object(service, "_send_buddy_request_notification"):
            pairing = service.create_buddy_request(
                buddy_user1, buddy_user3, 0.8, ["career"]
            )
        assert pairing.user1 == buddy_user1
        assert pairing.user2 == buddy_user3
        assert pairing.status == "pending"
        assert pairing.compatibility_score == 0.8


# ── BuddyEncouragement model ─────────────────────────────────────────


class TestBuddyEncouragementModel:
    """Tests for the BuddyEncouragement model."""

    def test_create_encouragement(self, active_pairing, buddy_user1):
        """BuddyEncouragement can be created."""
        enc = BuddyEncouragement.objects.create(
            pairing=active_pairing,
            sender=buddy_user1,
            message="Keep going!",
        )
        assert enc.message == "Keep going!"
        assert enc.sender == buddy_user1

    def test_empty_message(self, active_pairing, buddy_user1):
        """Encouragement can have empty message."""
        enc = BuddyEncouragement.objects.create(
            pairing=active_pairing,
            sender=buddy_user1,
            message="",
        )
        assert enc.message == ""

    def test_str_representation(self, active_pairing, buddy_user1):
        """__str__ includes sender name and message preview."""
        enc = BuddyEncouragement.objects.create(
            pairing=active_pairing,
            sender=buddy_user1,
            message="You're doing great!",
        )
        s = str(enc)
        assert "Buddy One" in s
