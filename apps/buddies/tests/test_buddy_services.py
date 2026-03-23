"""
Tests for apps.buddies.services — BuddyMatchingService.

Covers compatibility scoring (category 40%, activity 25%, timezone 20%, level 15%),
eligible candidate filtering (excludes self, blocked, paired, inactive),
and buddy request creation.
"""

from datetime import timedelta
from unittest.mock import MagicMock, patch

import pytest
from django.utils import timezone

from apps.buddies.models import BuddyPairing
from apps.buddies.services import BuddyMatchingService
from apps.dreams.models import Dream
from apps.users.models import User

# ══════════════════════════════════════════════════════════════════════
#  Activity similarity scoring
# ══════════════════════════════════════════════════════════════════════


class TestActivitySimilarity:
    """Tests for _calculate_activity_similarity (25% weight)."""

    @pytest.fixture
    def svc(self):
        return BuddyMatchingService()

    def test_same_streak(self, svc):
        u1 = MagicMock(streak_days=10)
        u2 = MagicMock(streak_days=10)
        assert svc._calculate_activity_similarity(u1, u2) == 1.0

    def test_diff_1(self, svc):
        u1 = MagicMock(streak_days=5)
        u2 = MagicMock(streak_days=8)
        assert svc._calculate_activity_similarity(u1, u2) == 0.8

    def test_diff_5(self, svc):
        u1 = MagicMock(streak_days=5)
        u2 = MagicMock(streak_days=10)
        assert svc._calculate_activity_similarity(u1, u2) == 0.6

    def test_diff_10(self, svc):
        u1 = MagicMock(streak_days=0)
        u2 = MagicMock(streak_days=10)
        assert svc._calculate_activity_similarity(u1, u2) == 0.4

    def test_diff_20(self, svc):
        u1 = MagicMock(streak_days=0)
        u2 = MagicMock(streak_days=20)
        assert svc._calculate_activity_similarity(u1, u2) == 0.2

    def test_diff_large(self, svc):
        u1 = MagicMock(streak_days=0)
        u2 = MagicMock(streak_days=100)
        assert svc._calculate_activity_similarity(u1, u2) == 0.1


# ══════════════════════════════════════════════════════════════════════
#  Timezone proximity scoring
# ══════════════════════════════════════════════════════════════════════


class TestTimezoneProximity:
    """Tests for _calculate_timezone_proximity (20% weight)."""

    @pytest.fixture
    def svc(self):
        return BuddyMatchingService()

    def test_same_timezone(self, svc):
        u1 = MagicMock(timezone="Europe/Paris")
        u2 = MagicMock(timezone="Europe/Paris")
        assert svc._calculate_timezone_proximity(u1, u2) == 1.0

    def test_same_region(self, svc):
        u1 = MagicMock(timezone="Europe/Paris")
        u2 = MagicMock(timezone="Europe/Berlin")
        assert svc._calculate_timezone_proximity(u1, u2) == 0.7

    def test_different_region(self, svc):
        u1 = MagicMock(timezone="Europe/Paris")
        u2 = MagicMock(timezone="America/New_York")
        assert svc._calculate_timezone_proximity(u1, u2) == 0.3

    def test_null_timezone_defaults_utc(self, svc):
        """None timezone treated as UTC."""
        u1 = MagicMock(timezone=None)
        u2 = MagicMock(timezone=None)
        assert svc._calculate_timezone_proximity(u1, u2) == 1.0

    def test_one_null_timezone(self, svc):
        u1 = MagicMock(timezone=None)
        u2 = MagicMock(timezone="Europe/Paris")
        # None -> "UTC", different from "Europe/Paris", no "/" in "UTC" -> different
        assert svc._calculate_timezone_proximity(u1, u2) == 0.3


# ══════════════════════════════════════════════════════════════════════
#  Level similarity scoring
# ══════════════════════════════════════════════════════════════════════


class TestLevelSimilarity:
    """Tests for _calculate_level_similarity (15% weight)."""

    @pytest.fixture
    def svc(self):
        return BuddyMatchingService()

    def test_same_level(self, svc):
        u1 = MagicMock(level=5)
        u2 = MagicMock(level=5)
        assert svc._calculate_level_similarity(u1, u2) == 1.0

    def test_diff_1(self, svc):
        u1 = MagicMock(level=5)
        u2 = MagicMock(level=6)
        assert svc._calculate_level_similarity(u1, u2) == 0.8

    def test_diff_3(self, svc):
        u1 = MagicMock(level=5)
        u2 = MagicMock(level=8)
        assert svc._calculate_level_similarity(u1, u2) == 0.6

    def test_diff_8(self, svc):
        u1 = MagicMock(level=2)
        u2 = MagicMock(level=10)
        assert svc._calculate_level_similarity(u1, u2) == 0.4

    def test_diff_large(self, svc):
        u1 = MagicMock(level=1)
        u2 = MagicMock(level=50)
        assert svc._calculate_level_similarity(u1, u2) == 0.2


# ══════════════════════════════════════════════════════════════════════
#  Category matching (40% weight)
# ══════════════════════════════════════════════════════════════════════


class TestCategoryMatching:
    """Tests for _get_user_categories and the category component of _calculate_compatibility."""

    def test_get_user_categories_with_db(self, buddy_user1):
        """_get_user_categories returns set of category strings from active dreams."""
        Dream.objects.create(
            user=buddy_user1,
            title="D1",
            description="d",
            category="health",
            status="active",
        )
        Dream.objects.create(
            user=buddy_user1,
            title="D2",
            description="d",
            category="career",
            status="active",
        )
        Dream.objects.create(
            user=buddy_user1,
            title="D3",
            description="d",
            category="health",
            status="completed",
        )
        svc = BuddyMatchingService()
        cats = svc._get_user_categories(buddy_user1)
        assert cats == {"health", "career"}

    def test_get_user_categories_excludes_blank(self, buddy_user1):
        """Blank categories are excluded."""
        Dream.objects.create(
            user=buddy_user1, title="D1", description="d", category="", status="active"
        )
        svc = BuddyMatchingService()
        cats = svc._get_user_categories(buddy_user1)
        assert cats == set()

    def test_category_score_full_overlap(self, buddy_user1, buddy_user2):
        """Users with identical categories get category_score = 1.0."""
        for u in (buddy_user1, buddy_user2):
            Dream.objects.create(
                user=u, title="D", description="d", category="health", status="active"
            )
            u.last_activity = timezone.now()
            u.save(update_fields=["last_activity"])

        svc = BuddyMatchingService()
        score, shared = svc._calculate_compatibility(buddy_user1, buddy_user2)
        assert "health" in shared
        # category component = 1.0 * 0.40 = 0.40
        # Other components contribute additional score
        assert score >= 0.40

    def test_category_score_no_overlap(self, buddy_user1, buddy_user2):
        """Users with no overlapping categories get category_score = 0."""
        Dream.objects.create(
            user=buddy_user1,
            title="D",
            description="d",
            category="health",
            status="active",
        )
        Dream.objects.create(
            user=buddy_user2,
            title="D",
            description="d",
            category="career",
            status="active",
        )
        for u in (buddy_user1, buddy_user2):
            u.last_activity = timezone.now()
            u.save(update_fields=["last_activity"])

        svc = BuddyMatchingService()
        score, shared = svc._calculate_compatibility(buddy_user1, buddy_user2)
        assert shared == []
        # category contribution = 0; other components still contribute
        # With same tz/streak/level: 0*0.4 + 1.0*0.25 + 1.0*0.2 + 1.0*0.15 = 0.60
        assert score <= 0.60

    def test_category_score_partial_overlap(self, buddy_user1, buddy_user2):
        """Partial category overlap yields intermediate score."""
        Dream.objects.create(
            user=buddy_user1,
            title="D1",
            description="d",
            category="health",
            status="active",
        )
        Dream.objects.create(
            user=buddy_user1,
            title="D2",
            description="d",
            category="career",
            status="active",
        )
        Dream.objects.create(
            user=buddy_user2,
            title="D3",
            description="d",
            category="health",
            status="active",
        )
        Dream.objects.create(
            user=buddy_user2,
            title="D4",
            description="d",
            category="education",
            status="active",
        )
        for u in (buddy_user1, buddy_user2):
            u.last_activity = timezone.now()
            u.save(update_fields=["last_activity"])

        svc = BuddyMatchingService()
        score, shared = svc._calculate_compatibility(buddy_user1, buddy_user2)
        assert "health" in shared
        # 1 shared out of 3 unique = 0.333 category score
        # 0.333 * 0.40 = 0.133 from categories
        assert score > 0


# ══════════════════════════════════════════════════════════════════════
#  Eligible candidate filtering
# ══════════════════════════════════════════════════════════════════════


class TestEligibleCandidates:
    """Tests for _get_eligible_candidates — exclusion logic."""

    @pytest.fixture
    def active_user_with_dream(self, db):
        """Create an active user with a recent activity and an active dream."""
        u = User.objects.create_user(
            email="candidate@example.com",
            password="testpass",
            display_name="Candidate",
            timezone="Europe/Paris",
        )
        u.last_activity = timezone.now()
        u.save(update_fields=["last_activity"])
        Dream.objects.create(
            user=u, title="Dream", description="d", category="health", status="active"
        )
        return u

    def test_excludes_self(self, buddy_user1, active_user_with_dream):
        """The requesting user is excluded from candidates."""
        buddy_user1.last_activity = timezone.now()
        buddy_user1.save(update_fields=["last_activity"])
        Dream.objects.create(
            user=buddy_user1, title="D", description="d", status="active"
        )

        svc = BuddyMatchingService()
        candidates = svc._get_eligible_candidates(buddy_user1)
        assert buddy_user1 not in candidates

    def test_excludes_paired_users(self, buddy_user1, active_user_with_dream):
        """Users with active/pending pairings with the requesting user are excluded."""
        BuddyPairing.objects.create(
            user1=buddy_user1,
            user2=active_user_with_dream,
            status="active",
            compatibility_score=0.5,
        )
        svc = BuddyMatchingService()
        candidates = svc._get_eligible_candidates(buddy_user1)
        assert active_user_with_dream not in candidates

    def test_excludes_pending_paired_users(self, buddy_user1, active_user_with_dream):
        """Users with pending pairings are also excluded."""
        BuddyPairing.objects.create(
            user1=buddy_user1,
            user2=active_user_with_dream,
            status="pending",
            compatibility_score=0.5,
        )
        svc = BuddyMatchingService()
        candidates = svc._get_eligible_candidates(buddy_user1)
        assert active_user_with_dream not in candidates

    def test_includes_completed_pair_user(self, buddy_user1, active_user_with_dream):
        """Users with completed (ended) pairings are eligible again."""
        BuddyPairing.objects.create(
            user1=buddy_user1,
            user2=active_user_with_dream,
            status="completed",
            compatibility_score=0.5,
        )
        svc = BuddyMatchingService()
        candidates = svc._get_eligible_candidates(buddy_user1)
        assert active_user_with_dream in candidates

    def test_excludes_inactive_users(self, buddy_user1):
        """Users with last_activity > 30 days ago are excluded."""
        old_user = User.objects.create_user(
            email="old@example.com",
            password="testpass",
            display_name="Old",
            timezone="Europe/Paris",
        )
        old_user.last_activity = timezone.now() - timedelta(days=60)
        old_user.save(update_fields=["last_activity"])
        Dream.objects.create(user=old_user, title="D", description="d", status="active")
        svc = BuddyMatchingService()
        candidates = svc._get_eligible_candidates(buddy_user1)
        assert old_user not in candidates

    def test_excludes_users_without_active_dreams(self, buddy_user1):
        """Users with no active dreams are excluded."""
        no_dream_user = User.objects.create_user(
            email="nodream@example.com",
            password="testpass",
            display_name="NoDream",
            timezone="Europe/Paris",
        )
        no_dream_user.last_activity = timezone.now()
        no_dream_user.save(update_fields=["last_activity"])
        # Only paused dream
        Dream.objects.create(
            user=no_dream_user, title="D", description="d", status="paused"
        )
        svc = BuddyMatchingService()
        candidates = svc._get_eligible_candidates(buddy_user1)
        assert no_dream_user not in candidates

    def test_includes_eligible_user(self, buddy_user1, active_user_with_dream):
        """An active user with a dream and no existing pairing is eligible."""
        svc = BuddyMatchingService()
        candidates = svc._get_eligible_candidates(buddy_user1)
        assert active_user_with_dream in candidates


# ══════════════════════════════════════════════════════════════════════
#  Full compatibility scoring (weighted)
# ══════════════════════════════════════════════════════════════════════


class TestFullCompatibilityScoring:
    """Integration tests for the full weighted scoring."""

    def test_weights_sum_to_one(self):
        svc = BuddyMatchingService()
        total = (
            svc.CATEGORY_WEIGHT
            + svc.ACTIVITY_WEIGHT
            + svc.TIMEZONE_WEIGHT
            + svc.LEVEL_WEIGHT
        )
        assert abs(total - 1.0) < 0.001

    def test_perfect_compatibility(self, buddy_user1, buddy_user2):
        """Identical attributes yield maximum score."""
        # Same categories
        for u in (buddy_user1, buddy_user2):
            Dream.objects.create(
                user=u, title="D", description="d", category="health", status="active"
            )
            u.streak_days = 10
            u.level = 5
            u.timezone = "Europe/Paris"
            u.last_activity = timezone.now()
            u.save()

        svc = BuddyMatchingService()
        score, shared = svc._calculate_compatibility(buddy_user1, buddy_user2)
        # All sub-scores = 1.0, weighted sum = 1.0
        assert abs(score - 1.0) < 0.001
        assert "health" in shared

    def test_zero_categories_still_scores(self, buddy_user1, buddy_user2):
        """Users with no categories get 0 for category but still score on others."""
        for u in (buddy_user1, buddy_user2):
            u.streak_days = 10
            u.level = 5
            u.timezone = "Europe/Paris"
            u.save()

        svc = BuddyMatchingService()
        score, shared = svc._calculate_compatibility(buddy_user1, buddy_user2)
        # category_score = 0, others = 1.0
        expected = 0 * 0.40 + 1.0 * 0.25 + 1.0 * 0.20 + 1.0 * 0.15
        assert abs(score - expected) < 0.001
        assert shared == []


# ══════════════════════════════════════════════════════════════════════
#  find_compatible_buddy
# ══════════════════════════════════════════════════════════════════════


class TestFindCompatibleBuddy:
    """Tests for the top-level find_compatible_buddy method."""

    def test_no_candidates_returns_none(self, buddy_user1):
        """Returns None when no eligible candidates exist."""
        svc = BuddyMatchingService()
        result = svc.find_compatible_buddy(buddy_user1)
        assert result is None

    def test_finds_best_match(self, buddy_user1, buddy_user2, buddy_user3):
        """Returns the candidate with the highest score."""
        # Make both candidates eligible
        for u in (buddy_user1, buddy_user2, buddy_user3):
            u.last_activity = timezone.now()
            u.streak_days = 5
            u.level = 3
            u.save()

        # buddy_user2 shares timezone with user1 (Europe/Paris)
        Dream.objects.create(
            user=buddy_user1,
            title="D",
            description="d",
            category="health",
            status="active",
        )
        Dream.objects.create(
            user=buddy_user2,
            title="D",
            description="d",
            category="health",
            status="active",
        )
        # buddy_user3 has different timezone (America/New_York) and different category
        Dream.objects.create(
            user=buddy_user3,
            title="D",
            description="d",
            category="career",
            status="active",
        )

        svc = BuddyMatchingService()
        result = svc.find_compatible_buddy(buddy_user1)
        assert result is not None
        matched_user, score, shared = result
        assert matched_user == buddy_user2
        assert score >= svc.MIN_COMPATIBILITY_SCORE
        assert "health" in shared

    def test_below_min_score_returns_none(self, buddy_user1):
        """Returns None when all candidates score below MIN_COMPATIBILITY_SCORE."""
        svc = BuddyMatchingService()
        # Create a candidate with maximally different attributes
        far_user = User.objects.create_user(
            email="far@example.com",
            password="testpass",
            display_name="Far",
            timezone="Pacific/Auckland",
        )
        far_user.last_activity = timezone.now()
        far_user.streak_days = 100
        far_user.level = 50
        far_user.save()
        Dream.objects.create(
            user=far_user,
            title="D",
            description="d",
            category="finance",
            status="active",
        )
        Dream.objects.create(
            user=buddy_user1,
            title="D",
            description="d",
            category="health",
            status="active",
        )
        buddy_user1.streak_days = 0
        buddy_user1.level = 1
        buddy_user1.save()

        result = svc.find_compatible_buddy(buddy_user1)
        # The score may or may not meet threshold depending on sub-scores
        # activity: 0.1, tz: 0.3, level: 0.2, cat: 0.0
        # total = 0*0.4 + 0.1*0.25 + 0.3*0.2 + 0.2*0.15 = 0 + 0.025 + 0.06 + 0.03 = 0.115
        # Below MIN_COMPATIBILITY_SCORE of 0.3, so should return None
        assert result is None


# ══════════════════════════════════════════════════════════════════════
#  create_buddy_request
# ══════════════════════════════════════════════════════════════════════


class TestCreateBuddyRequest:
    """Tests for creating buddy pairing requests."""

    def test_creates_pending_pairing(self, buddy_user1, buddy_user3):
        """create_buddy_request creates a BuddyPairing with status=pending."""
        svc = BuddyMatchingService()
        with patch.object(svc, "_send_buddy_request_notification"):
            pairing = svc.create_buddy_request(
                buddy_user1, buddy_user3, 0.85, ["health", "career"]
            )
        assert isinstance(pairing, BuddyPairing)
        assert pairing.user1 == buddy_user1
        assert pairing.user2 == buddy_user3
        assert pairing.status == "pending"
        assert pairing.compatibility_score == 0.85

    def test_sends_notification(self, buddy_user1, buddy_user3):
        """create_buddy_request sends a notification to the target user."""
        svc = BuddyMatchingService()
        with patch.object(svc, "_send_buddy_request_notification") as mock_notify:
            svc.create_buddy_request(buddy_user1, buddy_user3, 0.7, ["education"])
            mock_notify.assert_called_once_with(buddy_user1, buddy_user3, ["education"])

    def test_notification_content(self, buddy_user1, buddy_user3):
        """_send_buddy_request_notification creates a notification with correct content."""
        from apps.notifications.models import Notification

        svc = BuddyMatchingService()
        svc._send_buddy_request_notification(
            buddy_user1, buddy_user3, ["health", "career"]
        )
        notif = Notification.objects.filter(
            user=buddy_user3, notification_type="buddy_request"
        ).first()
        assert notif is not None
        assert "Buddy One" in notif.body
        assert "health" in notif.body

    def test_notification_empty_categories(self, buddy_user1, buddy_user3):
        """_send_buddy_request_notification with empty categories uses fallback text."""
        from apps.notifications.models import Notification

        svc = BuddyMatchingService()
        svc._send_buddy_request_notification(buddy_user1, buddy_user3, [])
        notif = Notification.objects.filter(
            user=buddy_user3, notification_type="buddy_request"
        ).first()
        assert notif is not None
        assert "achieving dreams" in notif.body
