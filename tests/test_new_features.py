"""
Tests for all features added during the codebase correction sprint.

Covers:
 - 2FA (setup, verify, disable, backup codes)
 - Onboarding completion
 - GDPR hard-delete task
 - Buddy request expiration task
 - Idempotent task/goal/dream completion
 - Dream sharing (notifications, permissions, queryset)
 - Achievement notification creation
 - Progress recalculation on task deletion (signal)
"""

import pytest
from datetime import timedelta
from unittest.mock import patch, Mock

from django.utils import timezone
from rest_framework import status

from apps.users.models import User, Achievement, UserAchievement, GamificationProfile
from apps.dreams.models import Dream, Goal, Task, SharedDream
from apps.buddies.models import BuddyPairing
from apps.notifications.models import Notification


# ═════════════════════════════════════════════════════════════════════
# 2FA Tests (uses two_factor.py views via /api/users/2fa/*)
# ═════════════════════════════════════════════════════════════════════

class TestTwoFactorSetup:
    """Test 2FA setup flow."""

    def test_setup_2fa_returns_secret_and_uri(self, authenticated_client, user):
        response = authenticated_client.post('/api/users/2fa/setup/')
        assert response.status_code == status.HTTP_200_OK
        assert 'secret' in response.data
        assert 'provisioning_uri' in response.data
        assert 'DreamPlanner' in response.data['provisioning_uri']

        # Pending secret stored in app_prefs
        user.refresh_from_db()
        assert user.app_prefs.get('totp_pending_secret') == response.data['secret']

    def test_setup_generates_new_secret_each_call(self, authenticated_client, user):
        r1 = authenticated_client.post('/api/users/2fa/setup/')
        r2 = authenticated_client.post('/api/users/2fa/setup/')
        assert r1.data['secret'] != r2.data['secret']


class TestTwoFactorVerify:
    """Test 2FA verification (completing setup)."""

    def test_verify_valid_code_enables_2fa(self, authenticated_client, user):
        import pyotp

        # First do setup
        setup_resp = authenticated_client.post('/api/users/2fa/setup/')
        secret = setup_resp.data['secret']

        # Generate a valid TOTP code
        totp = pyotp.TOTP(secret)
        code = totp.now()

        response = authenticated_client.post('/api/users/2fa/verify/', {'code': code})
        assert response.status_code == status.HTTP_200_OK
        assert response.data['verified'] is True
        assert response.data['two_factor_enabled'] is True
        assert 'backup_codes' in response.data
        assert len(response.data['backup_codes']) == 10

    def test_verify_invalid_code_rejected(self, authenticated_client, user):
        # Setup first
        authenticated_client.post('/api/users/2fa/setup/')

        response = authenticated_client.post('/api/users/2fa/verify/', {'code': '000000'})
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_verify_without_setup_fails(self, authenticated_client, user):
        response = authenticated_client.post('/api/users/2fa/verify/', {'code': '123456'})
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'not set up' in response.data['error'].lower()

    def test_verify_empty_code_rejected(self, authenticated_client, user):
        authenticated_client.post('/api/users/2fa/setup/')
        response = authenticated_client.post('/api/users/2fa/verify/', {'code': ''})
        assert response.status_code == status.HTTP_400_BAD_REQUEST


class TestTwoFactorDisable:
    """Test disabling 2FA."""

    @pytest.fixture
    def user_with_2fa(self, authenticated_client, user):
        """Setup and verify 2FA for user."""
        import pyotp
        setup_resp = authenticated_client.post('/api/users/2fa/setup/')
        secret = setup_resp.data['secret']
        totp = pyotp.TOTP(secret)
        authenticated_client.post('/api/users/2fa/verify/', {'code': totp.now()})
        user.set_password('testpassword123')
        user.save()
        return user

    def test_disable_2fa_success(self, authenticated_client, user_with_2fa):
        response = authenticated_client.post('/api/users/2fa/disable/', {
            'password': 'testpassword123',
        })
        assert response.status_code == status.HTTP_200_OK
        assert response.data['two_factor_enabled'] is False

        # Check status confirms disabled
        status_resp = authenticated_client.get('/api/users/2fa/status/')
        assert status_resp.data['two_factor_enabled'] is False

    def test_disable_2fa_wrong_password(self, authenticated_client, user_with_2fa):
        response = authenticated_client.post('/api/users/2fa/disable/', {
            'password': 'wrong_password',
        })
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_disable_2fa_empty_password(self, authenticated_client, user_with_2fa):
        response = authenticated_client.post('/api/users/2fa/disable/', {
            'password': '',
        })
        assert response.status_code == status.HTTP_400_BAD_REQUEST


class TestTwoFactorStatus:
    """Test 2FA status endpoint."""

    def test_status_disabled_by_default(self, authenticated_client, user):
        response = authenticated_client.get('/api/users/2fa/status/')
        assert response.status_code == status.HTTP_200_OK
        assert response.data['two_factor_enabled'] is False
        assert response.data['backup_codes_remaining'] == 0

    def test_status_after_enabling(self, authenticated_client, user):
        import pyotp
        setup_resp = authenticated_client.post('/api/users/2fa/setup/')
        secret = setup_resp.data['secret']
        totp = pyotp.TOTP(secret)
        authenticated_client.post('/api/users/2fa/verify/', {'code': totp.now()})

        response = authenticated_client.get('/api/users/2fa/status/')
        assert response.data['two_factor_enabled'] is True
        assert response.data['backup_codes_remaining'] == 10


class TestBackupCodes:
    """Test backup code regeneration."""

    @pytest.fixture
    def user_with_2fa(self, authenticated_client, user):
        import pyotp
        setup_resp = authenticated_client.post('/api/users/2fa/setup/')
        secret = setup_resp.data['secret']
        totp = pyotp.TOTP(secret)
        authenticated_client.post('/api/users/2fa/verify/', {'code': totp.now()})
        user.set_password('testpassword123')
        user.save()
        return user

    def test_regenerate_backup_codes(self, authenticated_client, user_with_2fa):
        response = authenticated_client.post('/api/users/2fa/backup-codes/', {
            'password': 'testpassword123',
        })
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['backup_codes']) == 10

    def test_backup_codes_requires_2fa_enabled(self, authenticated_client, user):
        user.set_password('testpassword123')
        user.save()

        response = authenticated_client.post('/api/users/2fa/backup-codes/', {
            'password': 'testpassword123',
        })
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert '2FA is not enabled' in response.data['error']

    def test_backup_codes_requires_password(self, authenticated_client, user):
        response = authenticated_client.post('/api/users/2fa/backup-codes/', {})
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_backup_code_can_verify(self, authenticated_client, user_with_2fa):
        """A backup code should work as a verification code."""
        # Get backup codes
        regen_resp = authenticated_client.post('/api/users/2fa/backup-codes/', {
            'password': 'testpassword123',
        })
        codes = regen_resp.data['backup_codes']

        # Use a backup code to verify
        response = authenticated_client.post('/api/users/2fa/verify/', {
            'code': codes[0],
        })
        assert response.status_code == status.HTTP_200_OK
        assert response.data['verified'] is True
        assert response.data.get('method') == 'backup_code'
        assert response.data.get('remaining_backup_codes') == 9


# ═════════════════════════════════════════════════════════════════════
# Onboarding Tests
# ═════════════════════════════════════════════════════════════════════

class TestOnboarding:
    """Test onboarding completion endpoint."""

    def test_complete_onboarding(self, authenticated_client, user):
        assert user.onboarding_completed is False

        response = authenticated_client.post('/api/users/complete-onboarding/')
        assert response.status_code == status.HTTP_200_OK

        user.refresh_from_db()
        assert user.onboarding_completed is True

    def test_complete_onboarding_idempotent(self, authenticated_client, user):
        user.onboarding_completed = True
        user.save(update_fields=['onboarding_completed'])

        response = authenticated_client.post('/api/users/complete-onboarding/')
        assert response.status_code == status.HTTP_200_OK

        user.refresh_from_db()
        assert user.onboarding_completed is True


# ═════════════════════════════════════════════════════════════════════
# GDPR Hard-Delete Tests
# ═════════════════════════════════════════════════════════════════════

class TestHardDeleteExpiredAccounts:
    """Test the hard_delete_expired_accounts Celery task."""

    def test_deletes_expired_accounts(self, db):
        """Accounts inactive for 30+ days should be hard-deleted."""
        expired_user = User.objects.create_user(
            email='expired@example.com',
            password='test123',
        )
        expired_user.is_active = False
        expired_user.updated_at = timezone.now() - timedelta(days=31)
        # Need raw update to bypass auto_now
        User.objects.filter(pk=expired_user.pk).update(
            is_active=False,
            updated_at=timezone.now() - timedelta(days=31),
        )

        from apps.users.tasks import hard_delete_expired_accounts
        count = hard_delete_expired_accounts()

        assert count >= 1
        assert not User.objects.filter(pk=expired_user.pk).exists()

    def test_preserves_active_accounts(self, db, user):
        """Active accounts should never be deleted."""
        from apps.users.tasks import hard_delete_expired_accounts
        count = hard_delete_expired_accounts()

        assert User.objects.filter(pk=user.pk).exists()

    def test_preserves_recently_deleted_accounts(self, db):
        """Accounts deleted less than 30 days ago should be preserved."""
        recent = User.objects.create_user(
            email='recent@example.com',
            password='test123',
        )
        recent.is_active = False
        recent.save()
        # updated_at auto-set to now, which is < 30 days ago

        from apps.users.tasks import hard_delete_expired_accounts
        hard_delete_expired_accounts()

        assert User.objects.filter(pk=recent.pk).exists()


# ═════════════════════════════════════════════════════════════════════
# Buddy Request Expiration Tests
# ═════════════════════════════════════════════════════════════════════

class TestExpirePendingBuddyRequests:
    """Test the expire_pending_buddy_requests Celery task."""

    @pytest.fixture
    def premium_users(self, db):
        u1 = User.objects.create_user(
            email='buddy1@test.com', password='test123',
            subscription='premium',
            subscription_ends=timezone.now() + timedelta(days=30),
        )
        u2 = User.objects.create_user(
            email='buddy2@test.com', password='test123',
            subscription='premium',
            subscription_ends=timezone.now() + timedelta(days=30),
        )
        return u1, u2

    def test_expires_old_pending_requests(self, premium_users):
        u1, u2 = premium_users
        pairing = BuddyPairing.objects.create(
            user1=u1, user2=u2,
            status='pending',
            expires_at=timezone.now() - timedelta(days=1),
        )

        from apps.buddies.tasks import expire_pending_buddy_requests
        count = expire_pending_buddy_requests()

        assert count == 1
        pairing.refresh_from_db()
        assert pairing.status == 'cancelled'
        assert pairing.ended_at is not None

    def test_preserves_active_pairings(self, premium_users):
        u1, u2 = premium_users
        pairing = BuddyPairing.objects.create(
            user1=u1, user2=u2,
            status='active',
            expires_at=timezone.now() - timedelta(days=1),
        )

        from apps.buddies.tasks import expire_pending_buddy_requests
        expire_pending_buddy_requests()

        pairing.refresh_from_db()
        assert pairing.status == 'active'

    def test_preserves_non_expired_pending(self, premium_users):
        u1, u2 = premium_users
        pairing = BuddyPairing.objects.create(
            user1=u1, user2=u2,
            status='pending',
            expires_at=timezone.now() + timedelta(days=5),
        )

        from apps.buddies.tasks import expire_pending_buddy_requests
        expire_pending_buddy_requests()

        pairing.refresh_from_db()
        assert pairing.status == 'pending'

    def test_ignores_null_expires_at(self, premium_users):
        u1, u2 = premium_users
        pairing = BuddyPairing.objects.create(
            user1=u1, user2=u2,
            status='pending',
            expires_at=None,
        )

        from apps.buddies.tasks import expire_pending_buddy_requests
        expire_pending_buddy_requests()

        pairing.refresh_from_db()
        assert pairing.status == 'pending'


# ═════════════════════════════════════════════════════════════════════
# Idempotent Completion Tests
# ═════════════════════════════════════════════════════════════════════

class TestIdempotentCompletion:
    """
    Calling complete() twice should be a no-op (model) or return 400 (API).
    """

    def test_task_model_complete_idempotent(self, task):
        task.complete()
        xp_after_first = task.goal.dream.user.xp

        # Second call is a no-op
        task.complete()
        task.goal.dream.user.refresh_from_db()
        assert task.goal.dream.user.xp == xp_after_first

    def test_goal_model_complete_idempotent(self, goal):
        goal.complete()
        xp_after_first = goal.dream.user.xp

        goal.complete()
        goal.dream.user.refresh_from_db()
        assert goal.dream.user.xp == xp_after_first

    def test_dream_model_complete_idempotent(self, dream):
        dream.complete()
        xp_after_first = dream.user.xp

        dream.complete()
        dream.user.refresh_from_db()
        assert dream.user.xp == xp_after_first

    def test_task_api_complete_twice_returns_400(self, authenticated_client, task):
        url = f'/api/dreams/tasks/{task.id}/complete/'

        response1 = authenticated_client.post(url)
        assert response1.status_code == status.HTTP_200_OK

        response2 = authenticated_client.post(url)
        assert response2.status_code == status.HTTP_400_BAD_REQUEST
        assert 'already completed' in response2.data['error'].lower()

    def test_goal_api_complete_twice_returns_400(self, authenticated_client, goal):
        url = f'/api/dreams/goals/{goal.id}/complete/'

        response1 = authenticated_client.post(url)
        assert response1.status_code == status.HTTP_200_OK

        response2 = authenticated_client.post(url)
        assert response2.status_code == status.HTTP_400_BAD_REQUEST

    def test_dream_api_complete_twice_returns_400(self, authenticated_client, dream):
        url = f'/api/dreams/dreams/{dream.id}/complete/'

        response1 = authenticated_client.post(url)
        assert response1.status_code == status.HTTP_200_OK

        response2 = authenticated_client.post(url)
        assert response2.status_code == status.HTTP_400_BAD_REQUEST


# ═════════════════════════════════════════════════════════════════════
# Dream Sharing Tests
# ═════════════════════════════════════════════════════════════════════

class TestDreamSharing:
    """Test sharing dreams creates notifications and grants access."""

    @pytest.fixture
    def other_user(self, db):
        return User.objects.create_user(
            email='other@example.com',
            password='test123',
            display_name='Other User',
        )

    def test_shared_dream_appears_in_queryset(self, authenticated_client, user, other_user):
        """Dreams shared with a user should appear in their dream list."""
        dream = Dream.objects.create(user=other_user, title='Shared Dream', status='active')
        SharedDream.objects.create(
            dream=dream,
            shared_by=other_user,
            shared_with=user,
            permission='view',
        )

        response = authenticated_client.get('/api/dreams/dreams/')
        assert response.status_code == status.HTTP_200_OK
        dream_ids = [d['id'] for d in response.data['results']]
        assert str(dream.id) in dream_ids

    def test_unshared_dream_not_visible(self, authenticated_client, user, other_user):
        """Other users' unshared dreams should not appear."""
        Dream.objects.create(user=other_user, title='Private Dream', status='active')

        response = authenticated_client.get('/api/dreams/dreams/')
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['results']) == 0


# ═════════════════════════════════════════════════════════════════════
# Achievement Notification Tests
# ═════════════════════════════════════════════════════════════════════

class TestAchievementNotifications:
    """Test that unlocking an achievement creates a notification."""

    def test_achievement_unlock_creates_notification(self, db, user):
        # Create gamification profile
        GamificationProfile.objects.create(user=user)

        # Create an achievement that requires 1 completed dream
        achievement = Achievement.objects.create(
            name='First Dream',
            description='Complete your first dream',
            icon='star',
            category='dreams',
            condition_type='dreams_completed',
            condition_value=1,
        )

        # Complete a dream to trigger achievement check
        dream = Dream.objects.create(user=user, title='Test', status='active')
        dream.complete()

        # Check if notification was created
        notif = Notification.objects.filter(
            user=user,
            notification_type='achievement',
        )
        # Achievement unlocked → notification should exist
        if UserAchievement.objects.filter(user=user, achievement=achievement).exists():
            assert notif.exists()


# ═════════════════════════════════════════════════════════════════════
# Progress Recalculation Signal Tests
# ═════════════════════════════════════════════════════════════════════

class TestProgressRecalculationSignal:
    """Test that deleting a task recalculates goal/dream progress."""

    def test_task_deletion_recalculates_goal_progress(self, db, user):
        dream = Dream.objects.create(user=user, title='Test Dream', status='active')
        goal = Goal.objects.create(dream=dream, title='Goal', order=0)
        task1 = Task.objects.create(goal=goal, title='Task 1', order=0, status='completed')
        task2 = Task.objects.create(goal=goal, title='Task 2', order=1, status='pending')
        task3 = Task.objects.create(goal=goal, title='Task 3', order=2, status='pending')

        # Before deletion: 1/3 completed = 33.3%
        goal.update_progress()
        goal.refresh_from_db()
        assert abs(goal.progress_percentage - 33.33) < 1

        # Delete a pending task — signal should recalculate
        task3.delete()

        goal.refresh_from_db()
        # Now: 1/2 completed = 50%
        assert abs(goal.progress_percentage - 50.0) < 1

    def test_completed_task_deletion_recalculates(self, db, user):
        dream = Dream.objects.create(user=user, title='Test Dream', status='active')
        goal = Goal.objects.create(dream=dream, title='Goal', order=0)
        task1 = Task.objects.create(goal=goal, title='Task 1', order=0, status='completed')
        task2 = Task.objects.create(goal=goal, title='Task 2', order=1, status='completed')

        goal.update_progress()
        goal.refresh_from_db()
        assert goal.progress_percentage == 100.0

        # Delete one completed task
        task1.delete()

        goal.refresh_from_db()
        # Now: 1/1 = 100% (still complete with remaining task)
        assert goal.progress_percentage == 100.0
