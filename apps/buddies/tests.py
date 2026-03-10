"""Tests for buddies app."""
import pytest
import uuid
from django.utils import timezone
from datetime import timedelta
from rest_framework import status
from rest_framework.test import APIClient
from apps.users.models import User, GamificationProfile
from apps.notifications.models import Notification
from .models import BuddyPairing, BuddyEncouragement
from .admin import BuddyEncouragementAdmin


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _set_user_plan(user, slug):
    """Ensure a user has the given subscription plan via DB records."""
    from apps.subscriptions.models import Subscription, SubscriptionPlan
    plan = SubscriptionPlan.objects.filter(slug=slug).first()
    if not plan:
        return
    sub, _ = Subscription.objects.get_or_create(
        user=user, defaults={'plan': plan, 'status': 'active'},
    )
    if sub.plan_id != plan.pk or sub.status != 'active':
        sub.plan = plan
        sub.status = 'active'
        sub.save(update_fields=['plan', 'status'])
    if hasattr(user, '_cached_plan'):
        del user._cached_plan


# ---------------------------------------------------------------------------
# Local fixtures (override global user to be premium for buddy access)
# ---------------------------------------------------------------------------

@pytest.fixture
def user(db):
    """Premium user for buddy tests (buddies require premium+)."""
    u = User.objects.create_user(
        email='testuser@example.com',
        password='testpassword123',
        display_name='Test User',
        timezone='Europe/Paris',
    )
    _set_user_plan(u, 'premium')
    u.refresh_from_db()
    return u


@pytest.fixture
def authenticated_client(user):
    """Authenticated client with premium user."""
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def other_user(db):
    """Create a second premium user for pairing tests."""
    u = User.objects.create_user(
        email='other@example.com',
        password='testpass123',
        display_name='Other User',
    )
    _set_user_plan(u, 'premium')
    u.refresh_from_db()
    return u


@pytest.fixture
def third_user(db):
    """Create a third premium user for edge-case tests."""
    return User.objects.create_user(
        email='third@example.com',
        password='testpass123',
        display_name='Third User',
        subscription='premium',
        subscription_ends=timezone.now() + timedelta(days=30),
    )


@pytest.fixture
def buddy_pairing(db, user, other_user):
    """Create an active buddy pairing between user and other_user."""
    return BuddyPairing.objects.create(
        user1=user,
        user2=other_user,
        status='active',
        compatibility_score=0.8,
    )


@pytest.fixture
def pending_pairing(db, user, other_user):
    """Create a pending buddy pairing where other_user invited user (user2=user)."""
    return BuddyPairing.objects.create(
        user1=other_user,
        user2=user,
        status='pending',
        compatibility_score=0.7,
    )


@pytest.fixture
def encouragement(db, buddy_pairing, user):
    """Create a buddy encouragement message."""
    return BuddyEncouragement.objects.create(
        pairing=buddy_pairing,
        sender=user,
        message='Keep going, you are doing great!',
    )


@pytest.fixture
def candidate_user(db):
    """Create a user available as a buddy candidate (no active pairing)."""
    return User.objects.create_user(
        email='candidate@example.com',
        password='testpass123',
        display_name='Candidate User',
        level=2,
        xp=150,
        last_activity=timezone.now(),
    )


@pytest.fixture
def user_gamification(db, user):
    """Get or create a GamificationProfile for user fixture."""
    profile, _ = GamificationProfile.objects.get_or_create(
        user=user,
        defaults={'health_xp': 100, 'career_xp': 50},
    )
    if not _:
        profile.health_xp = 100
        profile.career_xp = 50
        profile.save(update_fields=['health_xp', 'career_xp'])
    return profile


@pytest.fixture
def candidate_gamification(db, candidate_user):
    """Get or create a GamificationProfile for the candidate user."""
    profile, _ = GamificationProfile.objects.get_or_create(
        user=candidate_user,
        defaults={'health_xp': 80, 'career_xp': 0},
    )
    if not _:
        profile.health_xp = 80
        profile.career_xp = 0
        profile.save(update_fields=['health_xp', 'career_xp'])
    return profile


# ---------------------------------------------------------------------------
# Model tests – BuddyPairing
# ---------------------------------------------------------------------------

class TestBuddyPairingModel:
    """Tests for the BuddyPairing model."""

    def test_create_buddy_pairing(self, user, other_user):
        pairing = BuddyPairing.objects.create(
            user1=user,
            user2=other_user,
            status='active',
            compatibility_score=0.85,
        )
        assert pairing.pk is not None
        assert pairing.user1 == user
        assert pairing.user2 == other_user
        assert pairing.status == 'active'
        assert pairing.compatibility_score == 0.85

    def test_str_representation(self, buddy_pairing):
        result = str(buddy_pairing)
        assert 'Test User' in result
        assert 'Other User' in result
        assert 'active' in result

    def test_str_falls_back_to_email(self, db):
        u1 = User.objects.create_user(email='noname1@test.com', password='pass')
        u2 = User.objects.create_user(email='noname2@test.com', password='pass')
        pairing = BuddyPairing.objects.create(user1=u1, user2=u2)
        result = str(pairing)
        assert 'noname1@test.com' in result
        assert 'noname2@test.com' in result

    def test_status_choices(self, user, other_user):
        for code, _ in BuddyPairing.STATUS_CHOICES:
            pairing = BuddyPairing.objects.create(
                user1=user,
                user2=other_user,
                status=code,
            )
            assert pairing.status == code
            pairing.delete()

    def test_default_status_is_pending(self, user, other_user):
        pairing = BuddyPairing.objects.create(user1=user, user2=other_user)
        assert pairing.status == 'pending'

    def test_default_compatibility_score(self, user, other_user):
        pairing = BuddyPairing.objects.create(user1=user, user2=other_user)
        assert pairing.compatibility_score == 0.0

    def test_default_streak_values(self, user, other_user):
        pairing = BuddyPairing.objects.create(user1=user, user2=other_user)
        assert pairing.encouragement_streak == 0
        assert pairing.best_encouragement_streak == 0
        assert pairing.last_encouragement_at is None

    def test_ended_at_null_by_default(self, user, other_user):
        pairing = BuddyPairing.objects.create(user1=user, user2=other_user)
        assert pairing.ended_at is None

    def test_ordering(self, user, other_user):
        p1 = BuddyPairing.objects.create(user1=user, user2=other_user, status='completed')
        # Shift p1's created_at into the past so ordering is deterministic
        BuddyPairing.objects.filter(id=p1.id).update(
            created_at=timezone.now() - timedelta(days=1),
        )
        p2 = BuddyPairing.objects.create(user1=user, user2=other_user, status='active')
        pairings = list(BuddyPairing.objects.all())
        # Most recent first (ordering = ['-created_at'])
        assert pairings[0] == p2
        assert pairings[1] == p1

    def test_uuid_primary_key(self, buddy_pairing):
        assert isinstance(buddy_pairing.pk, uuid.UUID)


# ---------------------------------------------------------------------------
# Model tests – BuddyEncouragement
# ---------------------------------------------------------------------------

class TestBuddyEncouragementModel:
    """Tests for the BuddyEncouragement model."""

    def test_create_encouragement(self, buddy_pairing, user):
        enc = BuddyEncouragement.objects.create(
            pairing=buddy_pairing,
            sender=user,
            message='Great job!',
        )
        assert enc.pk is not None
        assert enc.pairing == buddy_pairing
        assert enc.sender == user
        assert enc.message == 'Great job!'

    def test_str_with_message(self, encouragement):
        result = str(encouragement)
        assert 'Test User' in result
        assert 'Keep going' in result

    def test_str_without_message(self, buddy_pairing, user):
        enc = BuddyEncouragement.objects.create(
            pairing=buddy_pairing,
            sender=user,
            message='',
        )
        result = str(enc)
        assert '(no message)' in result

    def test_str_long_message_truncated(self, buddy_pairing, user):
        long_msg = 'A' * 60
        enc = BuddyEncouragement.objects.create(
            pairing=buddy_pairing,
            sender=user,
            message=long_msg,
        )
        result = str(enc)
        assert '...' in result
        # Preview is first 50 chars + '...'
        assert 'A' * 50 in result

    def test_str_falls_back_to_email(self, buddy_pairing, db):
        sender = User.objects.create_user(email='noname@enc.com', password='pass')
        enc = BuddyEncouragement.objects.create(
            pairing=buddy_pairing,
            sender=sender,
            message='hi',
        )
        result = str(enc)
        assert 'noname@enc.com' in result

    def test_ordering(self, buddy_pairing, user):
        e1 = BuddyEncouragement.objects.create(
            pairing=buddy_pairing, sender=user, message='first',
        )
        # Push e1's created_at into the past so ordering is deterministic
        BuddyEncouragement.objects.filter(id=e1.id).update(
            created_at=timezone.now() - timedelta(days=1),
        )
        e2 = BuddyEncouragement.objects.create(
            pairing=buddy_pairing, sender=user, message='second',
        )
        encouragements = list(BuddyEncouragement.objects.all())
        assert encouragements[0] == e2  # Most recent first
        assert encouragements[1] == e1

    def test_default_message_is_empty(self, buddy_pairing, user):
        enc = BuddyEncouragement.objects.create(
            pairing=buddy_pairing,
            sender=user,
        )
        assert enc.message == ''

    def test_uuid_primary_key(self, encouragement):
        assert isinstance(encouragement.pk, uuid.UUID)


# ---------------------------------------------------------------------------
# View tests – BuddyViewSet
# ---------------------------------------------------------------------------

BASE_URL = '/api/buddies/'


class TestBuddyCurrentAction:
    """Tests for GET /api/buddies/current/."""

    def test_current_with_active_pairing(self, authenticated_client, buddy_pairing, user, other_user):
        response = authenticated_client.get(f'{BASE_URL}current/')
        assert response.status_code == status.HTTP_200_OK
        data = response.data
        assert data['buddy'] is not None
        assert data['buddy']['status'] == 'active'
        assert data['buddy']['compatibilityScore'] == 0.8
        assert data['buddy']['partner']['username'] == 'Other User'

    def test_current_no_pairing(self, authenticated_client):
        response = authenticated_client.get(f'{BASE_URL}current/')
        assert response.status_code == status.HTTP_200_OK
        assert response.data['buddy'] is None

    def test_current_requires_auth(self, api_client):
        response = api_client.get(f'{BASE_URL}current/')
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestBuddyProgressAction:
    """Tests for GET /api/buddies/{id}/progress/."""

    def test_progress_returns_comparison(self, authenticated_client, buddy_pairing, user, other_user):
        response = authenticated_client.get(f'{BASE_URL}{buddy_pairing.id}/progress/')
        assert response.status_code == status.HTTP_200_OK
        progress = response.data['progress']
        assert 'user' in progress
        assert 'partner' in progress
        assert 'currentStreak' in progress['user']
        assert 'tasksThisWeek' in progress['user']
        assert 'influenceScore' in progress['user']

    def test_progress_not_part_of_pairing(self, api_client, buddy_pairing, third_user):
        api_client.force_authenticate(user=third_user)
        response = api_client.get(f'{BASE_URL}{buddy_pairing.id}/progress/')
        assert response.status_code == status.HTTP_403_FORBIDDEN
        resp_str = str(response.data)
        assert 'not part of' in resp_str or 'error' in resp_str

    def test_progress_not_found(self, authenticated_client):
        fake_id = uuid.uuid4()
        response = authenticated_client.get(f'{BASE_URL}{fake_id}/progress/')
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_progress_inactive_pairing_not_found(self, authenticated_client, user, other_user):
        pairing = BuddyPairing.objects.create(
            user1=user, user2=other_user, status='completed',
        )
        response = authenticated_client.get(f'{BASE_URL}{pairing.id}/progress/')
        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestBuddyFindMatchAction:
    """Tests for POST /api/buddies/find-match/."""

    def test_find_match_success(self, authenticated_client, candidate_user, user_gamification, candidate_gamification):
        response = authenticated_client.post(f'{BASE_URL}find-match/')
        assert response.status_code == status.HTTP_200_OK
        match = response.data['match']
        assert match is not None
        assert match['username'] == 'Candidate User'
        assert 0.0 <= match['compatibilityScore'] <= 1.0

    def test_find_match_shared_interests(self, authenticated_client, candidate_user, user_gamification, candidate_gamification):
        """When both users have health_xp > 0, 'health' should appear in sharedInterests."""
        response = authenticated_client.post(f'{BASE_URL}find-match/')
        assert response.status_code == status.HTTP_200_OK
        match = response.data['match']
        assert 'health' in match['sharedInterests']
        # career_xp is 0 for candidate, so career should not appear
        assert 'career' not in match['sharedInterests']

    def test_find_match_already_has_buddy(self, authenticated_client, buddy_pairing):
        response = authenticated_client.post(f'{BASE_URL}find-match/')
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'already have' in response.data['error']

    def test_find_match_no_candidates(self, authenticated_client):
        """No other users exist -> match is None."""
        response = authenticated_client.post(f'{BASE_URL}find-match/')
        assert response.status_code == status.HTTP_200_OK
        assert response.data['match'] is None

    def test_find_match_excludes_users_with_active_pairing(
        self, authenticated_client, other_user, third_user,
    ):
        """Candidates who already have an active pairing should be excluded."""
        BuddyPairing.objects.create(
            user1=other_user, user2=third_user, status='active',
        )
        response = authenticated_client.post(f'{BASE_URL}find-match/')
        assert response.status_code == status.HTTP_200_OK
        assert response.data['match'] is None


class TestBuddyPairAction:
    """Tests for POST /api/buddies/pair/."""

    def test_pair_success(self, authenticated_client, other_user, user):
        response = authenticated_client.post(f'{BASE_URL}pair/', {'partner_id': str(other_user.id)})
        assert response.status_code == status.HTTP_201_CREATED
        assert 'pairing_id' in response.data
        pairing = BuddyPairing.objects.get(id=response.data['pairing_id'])
        assert pairing.user1 == user
        assert pairing.user2 == other_user
        # Pairings start as pending until the partner accepts
        assert pairing.status == 'pending'

    def test_pair_self_pairing(self, authenticated_client, user):
        response = authenticated_client.post(f'{BASE_URL}pair/', {'partner_id': str(user.id)})
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'cannot pair with yourself' in response.data['error']

    def test_pair_already_paired(self, authenticated_client, buddy_pairing, third_user):
        response = authenticated_client.post(f'{BASE_URL}pair/', {'partner_id': str(third_user.id)})
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'already have' in response.data['error']

    def test_pair_partner_not_found(self, authenticated_client):
        fake_id = uuid.uuid4()
        response = authenticated_client.post(f'{BASE_URL}pair/', {'partner_id': str(fake_id)})
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert 'not found' in response.data['error']

    def test_pair_partner_already_paired(self, authenticated_client, other_user, third_user):
        BuddyPairing.objects.create(
            user1=other_user, user2=third_user, status='active',
        )
        response = authenticated_client.post(f'{BASE_URL}pair/', {'partner_id': str(other_user.id)})
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'already has' in response.data['error']

    def test_pair_calculates_compatibility(self, authenticated_client, other_user, user):
        """Verify compatibility is stored and is between 0 and 1."""
        response = authenticated_client.post(f'{BASE_URL}pair/', {'partner_id': str(other_user.id)})
        assert response.status_code == status.HTTP_201_CREATED
        pairing = BuddyPairing.objects.get(id=response.data['pairing_id'])
        assert 0.0 <= pairing.compatibility_score <= 1.0


class TestBuddyAcceptAction:
    """Tests for POST /api/buddies/{id}/accept/."""

    def test_accept_success(self, authenticated_client, pending_pairing, user):
        response = authenticated_client.post(f'{BASE_URL}{pending_pairing.id}/accept/')
        assert response.status_code == status.HTTP_200_OK
        assert 'accepted' in response.data['message']
        pending_pairing.refresh_from_db()
        assert pending_pairing.status == 'active'

    def test_accept_not_found(self, authenticated_client):
        fake_id = uuid.uuid4()
        response = authenticated_client.post(f'{BASE_URL}{fake_id}/accept/')
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_accept_only_user2_can_accept(self, api_client, pending_pairing, other_user):
        """other_user is user1 (initiator), so they cannot accept."""
        api_client.force_authenticate(user=other_user)
        response = api_client.post(f'{BASE_URL}{pending_pairing.id}/accept/')
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_accept_already_active(self, authenticated_client, buddy_pairing):
        """Active pairings can't be accepted (status must be 'pending')."""
        response = authenticated_client.post(f'{BASE_URL}{buddy_pairing.id}/accept/')
        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestBuddyRejectAction:
    """Tests for POST /api/buddies/{id}/reject/."""

    def test_reject_success(self, authenticated_client, pending_pairing, user):
        response = authenticated_client.post(f'{BASE_URL}{pending_pairing.id}/reject/')
        assert response.status_code == status.HTTP_200_OK
        assert 'rejected' in response.data['message']
        pending_pairing.refresh_from_db()
        assert pending_pairing.status == 'cancelled'
        assert pending_pairing.ended_at is not None

    def test_reject_not_found(self, authenticated_client):
        fake_id = uuid.uuid4()
        response = authenticated_client.post(f'{BASE_URL}{fake_id}/reject/')
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_reject_only_user2_can_reject(self, api_client, pending_pairing, other_user):
        api_client.force_authenticate(user=other_user)
        response = api_client.post(f'{BASE_URL}{pending_pairing.id}/reject/')
        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestBuddyEncourageAction:
    """Tests for POST /api/buddies/{id}/encourage/."""

    def test_encourage_with_message(self, authenticated_client, buddy_pairing, user):
        response = authenticated_client.post(
            f'{BASE_URL}{buddy_pairing.id}/encourage/',
            {'message': 'You can do it!'},
        )
        assert response.status_code == status.HTTP_200_OK
        assert 'Encouragement sent' in response.data['message']
        assert BuddyEncouragement.objects.filter(pairing=buddy_pairing).count() == 1
        enc = BuddyEncouragement.objects.first()
        assert enc.message == 'You can do it!'
        assert enc.sender == user

    def test_encourage_without_message(self, authenticated_client, buddy_pairing):
        response = authenticated_client.post(
            f'{BASE_URL}{buddy_pairing.id}/encourage/',
            {},
        )
        assert response.status_code == status.HTTP_200_OK
        enc = BuddyEncouragement.objects.first()
        assert enc.message == ''

    def test_encourage_streak_first_time(self, authenticated_client, buddy_pairing):
        """First encouragement sets streak to 1."""
        response = authenticated_client.post(
            f'{BASE_URL}{buddy_pairing.id}/encourage/',
            {'message': 'First!'},
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data['encouragement_streak'] == 1
        assert response.data['best_encouragement_streak'] == 1

    def test_encourage_streak_increment_next_day(self, authenticated_client, buddy_pairing):
        """If last encouragement was yesterday, streak increments."""
        yesterday = timezone.now() - timedelta(days=1)
        buddy_pairing.last_encouragement_at = yesterday
        buddy_pairing.encouragement_streak = 3
        buddy_pairing.best_encouragement_streak = 3
        buddy_pairing.save()

        response = authenticated_client.post(
            f'{BASE_URL}{buddy_pairing.id}/encourage/',
            {'message': 'Day 4!'},
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data['encouragement_streak'] == 4
        assert response.data['best_encouragement_streak'] == 4

    def test_encourage_streak_same_day_no_change(self, authenticated_client, buddy_pairing):
        """If last encouragement was today (same day), streak does not change."""
        now = timezone.now()
        buddy_pairing.last_encouragement_at = now
        buddy_pairing.encouragement_streak = 5
        buddy_pairing.best_encouragement_streak = 5
        buddy_pairing.save()

        response = authenticated_client.post(
            f'{BASE_URL}{buddy_pairing.id}/encourage/',
            {'message': 'Same day!'},
        )
        assert response.status_code == status.HTTP_200_OK
        # days_since == 0, which is <= 1 but not == 1, so no increment
        assert response.data['encouragement_streak'] == 5

    def test_encourage_streak_reset_gap(self, authenticated_client, buddy_pairing):
        """If gap > 1 day, streak resets to 1."""
        three_days_ago = timezone.now() - timedelta(days=3)
        buddy_pairing.last_encouragement_at = three_days_ago
        buddy_pairing.encouragement_streak = 10
        buddy_pairing.best_encouragement_streak = 10
        buddy_pairing.save()

        response = authenticated_client.post(
            f'{BASE_URL}{buddy_pairing.id}/encourage/',
            {'message': 'Back at it!'},
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data['encouragement_streak'] == 1
        # best_encouragement_streak should remain 10
        assert response.data['best_encouragement_streak'] == 10

    def test_encourage_best_streak_updates(self, authenticated_client, buddy_pairing):
        """Best streak updates when current exceeds it."""
        yesterday = timezone.now() - timedelta(days=1)
        buddy_pairing.last_encouragement_at = yesterday
        buddy_pairing.encouragement_streak = 5
        buddy_pairing.best_encouragement_streak = 5
        buddy_pairing.save()

        response = authenticated_client.post(
            f'{BASE_URL}{buddy_pairing.id}/encourage/',
            {'message': 'New record!'},
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data['encouragement_streak'] == 6
        assert response.data['best_encouragement_streak'] == 6

    def test_encourage_creates_notification(self, authenticated_client, buddy_pairing, user, other_user):
        """Encouragement creates a Notification for the partner."""
        response = authenticated_client.post(
            f'{BASE_URL}{buddy_pairing.id}/encourage/',
            {'message': 'Stay strong!'},
        )
        assert response.status_code == status.HTTP_200_OK
        # Notification should be created for the partner (other_user)
        notif = Notification.objects.filter(user=other_user, notification_type='buddy').first()
        assert notif is not None
        assert notif.title == 'Buddy Encouragement'
        assert str(buddy_pairing.id) in notif.data['pairing_id']

    def test_encourage_not_found(self, authenticated_client):
        fake_id = uuid.uuid4()
        response = authenticated_client.post(
            f'{BASE_URL}{fake_id}/encourage/',
            {'message': 'Hello!'},
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_encourage_not_part_of_pairing(self, api_client, buddy_pairing, third_user):
        api_client.force_authenticate(user=third_user)
        response = api_client.post(
            f'{BASE_URL}{buddy_pairing.id}/encourage/',
            {'message': 'Hello!'},
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_encourage_inactive_pairing(self, authenticated_client, user, other_user):
        pairing = BuddyPairing.objects.create(
            user1=user, user2=other_user, status='completed',
        )
        response = authenticated_client.post(
            f'{BASE_URL}{pairing.id}/encourage/',
            {'message': 'Hello!'},
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestBuddyDestroyAction:
    """Tests for DELETE /api/buddies/{id}/."""

    def test_destroy_success(self, authenticated_client, buddy_pairing):
        response = authenticated_client.delete(f'{BASE_URL}{buddy_pairing.id}/')
        assert response.status_code == status.HTTP_200_OK
        assert 'ended' in response.data['message']
        buddy_pairing.refresh_from_db()
        assert buddy_pairing.status == 'cancelled'
        assert buddy_pairing.ended_at is not None

    def test_destroy_not_part_of_pairing(self, api_client, buddy_pairing, third_user):
        api_client.force_authenticate(user=third_user)
        response = api_client.delete(f'{BASE_URL}{buddy_pairing.id}/')
        assert response.status_code == status.HTTP_403_FORBIDDEN
        # Custom exception handler wraps errors: check message or detail
        resp_str = str(response.data)
        assert 'not part of' in resp_str or 'error' in resp_str

    def test_destroy_not_found(self, authenticated_client):
        fake_id = uuid.uuid4()
        response = authenticated_client.delete(f'{BASE_URL}{fake_id}/')
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_destroy_inactive_pairing(self, authenticated_client, user, other_user):
        pairing = BuddyPairing.objects.create(
            user1=user, user2=other_user, status='completed',
        )
        response = authenticated_client.delete(f'{BASE_URL}{pairing.id}/')
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_destroy_as_user2(self, api_client, buddy_pairing, other_user):
        """user2 should also be able to end the pairing."""
        api_client.force_authenticate(user=other_user)
        response = api_client.delete(f'{BASE_URL}{buddy_pairing.id}/')
        assert response.status_code == status.HTTP_200_OK
        buddy_pairing.refresh_from_db()
        assert buddy_pairing.status == 'cancelled'


class TestBuddyHistoryAction:
    """Tests for GET /api/buddies/history/."""

    def test_history_returns_past_pairings(self, authenticated_client, user, other_user):
        now = timezone.now()
        p1 = BuddyPairing.objects.create(
            user1=user, user2=other_user, status='completed',
            ended_at=now,
        )
        p2 = BuddyPairing.objects.create(
            user1=user, user2=other_user, status='cancelled',
            ended_at=now,
        )
        response = authenticated_client.get(f'{BASE_URL}history/')
        assert response.status_code == status.HTTP_200_OK
        pairings = response.data['pairings']
        assert len(pairings) == 2

    def test_history_empty(self, authenticated_client):
        response = authenticated_client.get(f'{BASE_URL}history/')
        assert response.status_code == status.HTTP_200_OK
        assert response.data['pairings'] == []

    def test_history_includes_active_pairings(self, authenticated_client, buddy_pairing):
        """History returns all pairings, including active ones."""
        response = authenticated_client.get(f'{BASE_URL}history/')
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['pairings']) == 1
        assert response.data['pairings'][0]['status'] == 'active'

    def test_history_includes_encouragement_count(self, authenticated_client, buddy_pairing, user):
        BuddyEncouragement.objects.create(pairing=buddy_pairing, sender=user, message='1')
        BuddyEncouragement.objects.create(pairing=buddy_pairing, sender=user, message='2')
        response = authenticated_client.get(f'{BASE_URL}history/')
        assert response.status_code == status.HTTP_200_OK
        assert response.data['pairings'][0]['encouragementCount'] == 2

    def test_history_includes_duration_days(self, authenticated_client, user, other_user):
        created = timezone.now() - timedelta(days=10)
        ended = timezone.now()
        pairing = BuddyPairing.objects.create(
            user1=user, user2=other_user, status='completed',
            ended_at=ended,
        )
        # Override created_at via queryset update (auto_now_add prevents direct set)
        BuddyPairing.objects.filter(id=pairing.id).update(created_at=created)
        response = authenticated_client.get(f'{BASE_URL}history/')
        assert response.status_code == status.HTTP_200_OK
        assert response.data['pairings'][0]['durationDays'] == 10

    def test_history_duration_null_when_not_ended(self, authenticated_client, buddy_pairing):
        response = authenticated_client.get(f'{BASE_URL}history/')
        assert response.status_code == status.HTTP_200_OK
        assert response.data['pairings'][0]['durationDays'] is None

    def test_history_partner_data(self, authenticated_client, buddy_pairing):
        response = authenticated_client.get(f'{BASE_URL}history/')
        assert response.status_code == status.HTTP_200_OK
        partner = response.data['pairings'][0]['partner']
        assert partner['username'] == 'Other User'
        assert 'currentLevel' in partner
        assert 'influenceScore' in partner

    def test_history_does_not_include_other_users_pairings(
        self, authenticated_client, other_user, third_user,
    ):
        """Pairings that don't involve the authenticated user should not appear."""
        BuddyPairing.objects.create(
            user1=other_user, user2=third_user, status='active',
        )
        response = authenticated_client.get(f'{BASE_URL}history/')
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['pairings']) == 0


# ---------------------------------------------------------------------------
# Admin tests
# ---------------------------------------------------------------------------

class TestBuddyEncouragementAdminMessagePreview:
    """Tests for BuddyEncouragementAdmin.message_preview custom method."""

    def test_message_preview_with_short_message(self, buddy_pairing, user):
        enc = BuddyEncouragement.objects.create(
            pairing=buddy_pairing,
            sender=user,
            message='Short message',
        )
        admin_instance = BuddyEncouragementAdmin(BuddyEncouragement, None)
        result = admin_instance.message_preview(enc)
        assert result == 'Short message'

    def test_message_preview_with_long_message(self, buddy_pairing, user):
        long_msg = 'X' * 100
        enc = BuddyEncouragement.objects.create(
            pairing=buddy_pairing,
            sender=user,
            message=long_msg,
        )
        admin_instance = BuddyEncouragementAdmin(BuddyEncouragement, None)
        result = admin_instance.message_preview(enc)
        assert len(result) == 83  # 80 chars + '...'
        assert result.endswith('...')

    def test_message_preview_without_message(self, buddy_pairing, user):
        enc = BuddyEncouragement.objects.create(
            pairing=buddy_pairing,
            sender=user,
            message='',
        )
        admin_instance = BuddyEncouragementAdmin(BuddyEncouragement, None)
        result = admin_instance.message_preview(enc)
        assert result == '(no message)'

    def test_message_preview_exactly_80_chars(self, buddy_pairing, user):
        msg = 'Y' * 80
        enc = BuddyEncouragement.objects.create(
            pairing=buddy_pairing,
            sender=user,
            message=msg,
        )
        admin_instance = BuddyEncouragementAdmin(BuddyEncouragement, None)
        result = admin_instance.message_preview(enc)
        assert result == msg  # Exactly 80, no truncation

    def test_message_preview_81_chars_truncated(self, buddy_pairing, user):
        msg = 'Z' * 81
        enc = BuddyEncouragement.objects.create(
            pairing=buddy_pairing,
            sender=user,
            message=msg,
        )
        admin_instance = BuddyEncouragementAdmin(BuddyEncouragement, None)
        result = admin_instance.message_preview(enc)
        assert result == 'Z' * 80 + '...'
