"""
Tests for Buddy Matching Service.
"""

import pytest
from django.utils import timezone
from datetime import timedelta
from unittest.mock import patch, Mock

from .models import User, DreamBuddy
from .services import BuddyMatchingService
from apps.dreams.models import Dream


@pytest.fixture
def matching_service():
    """Create BuddyMatchingService instance."""
    return BuddyMatchingService()


@pytest.fixture
def user_with_dreams(db):
    """Create a user with active dreams."""
    user = User.objects.create(
        firebase_uid='test-user-1',
        email='user1@test.com',
        display_name='Test User 1',
        timezone='Europe/Paris',
        level=5,
        streak_days=10
    )
    # Create active dream
    Dream.objects.create(
        user=user,
        title='Learn Python',
        description='Become a Python expert',
        category='career',
        status='active'
    )
    Dream.objects.create(
        user=user,
        title='Get Fit',
        description='Improve fitness',
        category='health',
        status='active'
    )
    return user


@pytest.fixture
def potential_buddy(db):
    """Create a potential buddy user."""
    user = User.objects.create(
        firebase_uid='test-user-2',
        email='user2@test.com',
        display_name='Test User 2',
        timezone='Europe/Paris',
        level=4,
        streak_days=8
    )
    # Create active dream with matching category
    Dream.objects.create(
        user=user,
        title='Master Python',
        description='Become proficient in Python',
        category='career',
        status='active'
    )
    return user


@pytest.fixture
def incompatible_user(db):
    """Create an incompatible user (inactive, different categories)."""
    user = User.objects.create(
        firebase_uid='test-user-3',
        email='user3@test.com',
        display_name='Test User 3',
        timezone='America/New_York',
        level=50,
        streak_days=0,
        last_activity=timezone.now() - timedelta(days=60)  # Inactive
    )
    return user


class TestBuddyMatchingService:
    """Tests for BuddyMatchingService."""

    def test_find_compatible_buddy_success(
        self, matching_service, user_with_dreams, potential_buddy
    ):
        """Test finding a compatible buddy successfully."""
        result = matching_service.find_compatible_buddy(user_with_dreams)

        assert result is not None
        matched_user, score, categories = result
        assert matched_user == potential_buddy
        assert score > 0
        assert 'career' in categories

    def test_find_compatible_buddy_no_candidates(
        self, matching_service, user_with_dreams
    ):
        """Test when no compatible candidates exist."""
        # No other users exist
        result = matching_service.find_compatible_buddy(user_with_dreams)

        assert result is None

    def test_excludes_self(self, matching_service, user_with_dreams):
        """Test that user is excluded from their own matching."""
        # Only the user exists
        result = matching_service.find_compatible_buddy(user_with_dreams)

        assert result is None

    def test_excludes_existing_buddies(
        self, matching_service, user_with_dreams, potential_buddy
    ):
        """Test that existing buddy pairs are excluded."""
        # Create an active buddy pair
        DreamBuddy.objects.create(
            user1=user_with_dreams,
            user2=potential_buddy,
            status='active'
        )

        result = matching_service.find_compatible_buddy(user_with_dreams)

        assert result is None

    def test_excludes_pending_requests(
        self, matching_service, user_with_dreams, potential_buddy
    ):
        """Test that pending requests are excluded."""
        # Create a pending buddy request
        DreamBuddy.objects.create(
            user1=user_with_dreams,
            user2=potential_buddy,
            status='pending'
        )

        result = matching_service.find_compatible_buddy(user_with_dreams)

        assert result is None

    def test_excludes_inactive_users(
        self, matching_service, user_with_dreams, incompatible_user
    ):
        """Test that inactive users are excluded."""
        # Only incompatible user exists (inactive for 60 days)
        result = matching_service.find_compatible_buddy(user_with_dreams)

        assert result is None

    def test_calculate_compatibility_matching_categories(
        self, matching_service, user_with_dreams, potential_buddy
    ):
        """Test compatibility calculation with matching categories."""
        score, categories = matching_service._calculate_compatibility(
            user_with_dreams, potential_buddy
        )

        assert score > 0
        assert 'career' in categories

    def test_calculate_activity_similarity_same_streak(
        self, matching_service, user_with_dreams
    ):
        """Test activity similarity with same streak."""
        # Create user with same streak
        similar_user = User.objects.create(
            firebase_uid='similar-streak',
            email='similar@test.com',
            streak_days=user_with_dreams.streak_days
        )

        score = matching_service._calculate_activity_similarity(
            user_with_dreams, similar_user
        )

        assert score == 1.0

    def test_calculate_activity_similarity_different_streak(
        self, matching_service, user_with_dreams
    ):
        """Test activity similarity with different streaks."""
        different_user = User.objects.create(
            firebase_uid='different-streak',
            email='different@test.com',
            streak_days=user_with_dreams.streak_days + 50
        )

        score = matching_service._calculate_activity_similarity(
            user_with_dreams, different_user
        )

        assert score < 0.5  # Different streaks should have low score

    def test_calculate_timezone_proximity_same(
        self, matching_service, user_with_dreams, potential_buddy
    ):
        """Test timezone proximity with same timezone."""
        score = matching_service._calculate_timezone_proximity(
            user_with_dreams, potential_buddy
        )

        assert score == 1.0

    def test_calculate_timezone_proximity_different_region(
        self, matching_service, user_with_dreams
    ):
        """Test timezone proximity with different region."""
        different_tz_user = User.objects.create(
            firebase_uid='different-tz',
            email='differenttz@test.com',
            timezone='America/New_York'
        )

        score = matching_service._calculate_timezone_proximity(
            user_with_dreams, different_tz_user
        )

        assert score < 1.0

    def test_calculate_level_similarity_same_level(
        self, matching_service, user_with_dreams
    ):
        """Test level similarity with same level."""
        same_level_user = User.objects.create(
            firebase_uid='same-level',
            email='samelevel@test.com',
            level=user_with_dreams.level
        )

        score = matching_service._calculate_level_similarity(
            user_with_dreams, same_level_user
        )

        assert score == 1.0

    def test_create_buddy_request(
        self, matching_service, user_with_dreams, potential_buddy
    ):
        """Test creating a buddy request."""
        buddy_pair = matching_service.create_buddy_request(
            requesting_user=user_with_dreams,
            target_user=potential_buddy,
            compatibility_score=0.75,
            shared_categories=['career']
        )

        assert buddy_pair.user1 == user_with_dreams
        assert buddy_pair.user2 == potential_buddy
        assert buddy_pair.status == 'pending'
        assert buddy_pair.compatibility_score == 0.75
        assert 'career' in buddy_pair.shared_categories


class TestDreamBuddyModel:
    """Tests for DreamBuddy model."""

    def test_create_dream_buddy(self, db, user_with_dreams, potential_buddy):
        """Test creating a DreamBuddy instance."""
        buddy = DreamBuddy.objects.create(
            user1=user_with_dreams,
            user2=potential_buddy,
            status='pending',
            compatibility_score=0.8,
            shared_categories=['career', 'health']
        )

        assert buddy.user1 == user_with_dreams
        assert buddy.user2 == potential_buddy
        assert buddy.status == 'pending'

    def test_unique_together_constraint(
        self, db, user_with_dreams, potential_buddy
    ):
        """Test that duplicate buddy pairs are prevented."""
        DreamBuddy.objects.create(
            user1=user_with_dreams,
            user2=potential_buddy
        )

        from django.db import IntegrityError
        with pytest.raises(IntegrityError):
            DreamBuddy.objects.create(
                user1=user_with_dreams,
                user2=potential_buddy
            )
