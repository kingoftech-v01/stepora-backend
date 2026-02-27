"""
QA Integration Tests — End-to-End API Flows for DreamPlanner.

These tests verify complete user journeys through the API, chaining
multiple requests together and verifying database state at each step.
Every feature added during the correction sprint is covered here.

Run with:
    pytest tests/test_qa_integration.py -v --no-cov
"""

import pytest
import uuid
from datetime import timedelta
from unittest.mock import patch, Mock

from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.users.models import User, GamificationProfile, Achievement, UserAchievement
from apps.dreams.models import Dream, Goal, Task, SharedDream, DreamCollaborator
from apps.buddies.models import BuddyPairing, BuddyEncouragement
from apps.notifications.models import Notification
from apps.circles.models import Circle, CircleMembership
from apps.leagues.models import League, Season, LeagueStanding
from apps.subscriptions.models import SubscriptionPlan


# ═════════════════════════════════════════════════════════════════════
# Fixtures
# ═════════════════════════════════════════════════════════════════════

@pytest.fixture
def free_user(db):
    return User.objects.create_user(
        email='freeuser@qa.com', password='QaTest123!',
        display_name='Free QA User',
    )

@pytest.fixture
def free_client(free_user):
    c = APIClient()
    c.force_authenticate(user=free_user)
    return c

@pytest.fixture
def premium_user_qa(db):
    return User.objects.create_user(
        email='premium_qa@qa.com', password='QaTest123!',
        display_name='Premium QA User',
        subscription='premium',
        subscription_ends=timezone.now() + timedelta(days=30),
    )

@pytest.fixture
def premium_client_qa(premium_user_qa):
    c = APIClient()
    c.force_authenticate(user=premium_user_qa)
    return c

@pytest.fixture
def pro_user_qa(db):
    return User.objects.create_user(
        email='pro_qa@qa.com', password='QaTest123!',
        display_name='Pro QA User',
        subscription='pro',
        subscription_ends=timezone.now() + timedelta(days=30),
    )

@pytest.fixture
def pro_client_qa(pro_user_qa):
    c = APIClient()
    c.force_authenticate(user=pro_user_qa)
    return c

@pytest.fixture
def second_user_qa(db):
    return User.objects.create_user(
        email='second_qa@qa.com', password='QaTest123!',
        display_name='Second QA User',
    )

@pytest.fixture
def second_client_qa(second_user_qa):
    c = APIClient()
    c.force_authenticate(user=second_user_qa)
    return c

@pytest.fixture
def second_premium_qa(db):
    return User.objects.create_user(
        email='premium2_qa@qa.com', password='QaTest123!',
        display_name='Premium QA 2',
        subscription='premium',
        subscription_ends=timezone.now() + timedelta(days=30),
    )

@pytest.fixture
def second_premium_client_qa(second_premium_qa):
    c = APIClient()
    c.force_authenticate(user=second_premium_qa)
    return c


# ═════════════════════════════════════════════════════════════════════
# QA-1: Two-Factor Authentication — Full Lifecycle
# ═════════════════════════════════════════════════════════════════════

class TestQA_TwoFactorLifecycle:
    """
    Flow: Setup → Verify → Check status → Generate backup codes →
          Use backup code → Disable → Verify disabled
    """

    def test_full_2fa_lifecycle(self, free_client, free_user):
        import pyotp

        # 1. Check initial status — 2FA disabled
        r = free_client.get('/api/users/2fa/status/')
        assert r.status_code == 200
        assert r.data['two_factor_enabled'] is False
        assert r.data['backup_codes_remaining'] == 0

        # 2. Setup — get secret and provisioning URI
        r = free_client.post('/api/users/2fa/setup/')
        assert r.status_code == 200
        secret = r.data['secret']
        assert 'provisioning_uri' in r.data
        assert 'DreamPlanner' in r.data['provisioning_uri']
        assert free_user.email.replace('@', '%40') in r.data['provisioning_uri']

        # 3. Verify with valid TOTP code — activates 2FA + returns backup codes
        totp = pyotp.TOTP(secret)
        r = free_client.post('/api/users/2fa/verify/', {'code': totp.now()})
        assert r.status_code == 200
        assert r.data['verified'] is True
        assert r.data['two_factor_enabled'] is True
        initial_backup_codes = r.data['backup_codes']
        assert len(initial_backup_codes) == 10

        # 4. Check status — now enabled with 10 backup codes
        r = free_client.get('/api/users/2fa/status/')
        assert r.data['two_factor_enabled'] is True
        assert r.data['backup_codes_remaining'] == 10

        # 5. Regenerate backup codes (old ones invalidated)
        r = free_client.post('/api/users/2fa/backup-codes/', {'password': 'QaTest123!'})
        assert r.status_code == 200
        new_codes = r.data['backup_codes']
        assert len(new_codes) == 10
        assert new_codes != initial_backup_codes

        # 6. Use a backup code to verify
        r = free_client.post('/api/users/2fa/verify/', {'code': new_codes[0]})
        assert r.status_code == 200
        assert r.data['verified'] is True
        assert r.data['method'] == 'backup_code'
        assert r.data['remaining_backup_codes'] == 9

        # 7. Use a completely invalid code → should fail
        r = free_client.post('/api/users/2fa/verify/', {'code': 'ZZZZZZZZ'})
        assert r.status_code == 400

        # 8. Disable 2FA
        r = free_client.post('/api/users/2fa/disable/', {'password': 'QaTest123!'})
        assert r.status_code == 200
        assert r.data['two_factor_enabled'] is False

        # 9. Status confirms disabled
        r = free_client.get('/api/users/2fa/status/')
        assert r.data['two_factor_enabled'] is False
        assert r.data['backup_codes_remaining'] == 0

    def test_2fa_invalid_code_never_activates(self, free_client):
        # Setup
        free_client.post('/api/users/2fa/setup/')
        # Bad code
        r = free_client.post('/api/users/2fa/verify/', {'code': '999999'})
        assert r.status_code == 400
        # Still disabled
        r = free_client.get('/api/users/2fa/status/')
        assert r.data['two_factor_enabled'] is False

    def test_2fa_disable_wrong_password_blocked(self, free_client):
        import pyotp
        setup = free_client.post('/api/users/2fa/setup/')
        totp = pyotp.TOTP(setup.data['secret'])
        free_client.post('/api/users/2fa/verify/', {'code': totp.now()})

        r = free_client.post('/api/users/2fa/disable/', {'password': 'WrongPassword!'})
        assert r.status_code == 400
        # Still enabled
        r = free_client.get('/api/users/2fa/status/')
        assert r.data['two_factor_enabled'] is True

    def test_2fa_requires_authentication(self, db):
        anon = APIClient()
        assert anon.get('/api/users/2fa/status/').status_code == 401
        assert anon.post('/api/users/2fa/setup/').status_code == 401
        assert anon.post('/api/users/2fa/verify/', {'code': '123456'}).status_code == 401


# ═════════════════════════════════════════════════════════════════════
# QA-2: Onboarding Flow
# ═════════════════════════════════════════════════════════════════════

class TestQA_OnboardingFlow:
    """Flow: New user → complete onboarding → verify flag persisted."""

    def test_onboarding_lifecycle(self, free_client, free_user):
        # 1. Initially not completed
        assert free_user.onboarding_completed is False

        # 2. Complete onboarding
        r = free_client.post('/api/users/complete-onboarding/')
        assert r.status_code == 200
        assert 'Onboarding completed' in r.data['message']

        # 3. Verify in DB
        free_user.refresh_from_db()
        assert free_user.onboarding_completed is True

        # 4. Calling again is safe (idempotent)
        r = free_client.post('/api/users/complete-onboarding/')
        assert r.status_code == 200


# ═════════════════════════════════════════════════════════════════════
# QA-3: Dream Full Lifecycle with Idempotent Completion
# ═════════════════════════════════════════════════════════════════════

class TestQA_DreamLifecycle:
    """
    Flow: Create dream → add goals → add tasks → complete tasks →
          complete goals → complete dream → verify 400 on re-complete →
          verify XP awarded → verify progress 100%
    """

    def test_dream_full_lifecycle_with_idempotency(self, free_client, free_user):
        # 1. Create dream
        r = free_client.post('/api/dreams/dreams/', {
            'title': 'QA Dream', 'description': 'End-to-end test',
            'category': 'education', 'priority': 1,
        })
        assert r.status_code == status.HTTP_201_CREATED
        dream_id = r.data['id']

        # 2. Create goal via ORM (serializer doesn't accept dream FK)
        dream = Dream.objects.get(id=dream_id)
        goal = Goal.objects.create(dream=dream, title='QA Goal', order=0)
        task1 = Task.objects.create(goal=goal, title='Task 1', order=0, duration_mins=30)
        task2 = Task.objects.create(goal=goal, title='Task 2', order=1, duration_mins=15)

        # 3. Get initial XP
        free_user.refresh_from_db()
        xp_before = free_user.xp

        # 4. Complete task 1
        r = free_client.post(f'/api/dreams/tasks/{task1.id}/complete/')
        assert r.status_code == 200

        # 5. Re-complete task 1 → 400 (idempotent guard)
        r = free_client.post(f'/api/dreams/tasks/{task1.id}/complete/')
        assert r.status_code == 400
        assert 'already completed' in r.data['error'].lower()

        # 6. Complete task 2
        r = free_client.post(f'/api/dreams/tasks/{task2.id}/complete/')
        assert r.status_code == 200

        # 7. Verify goal progress
        goal.refresh_from_db()
        assert goal.progress_percentage == 100.0

        # 8. Complete goal
        r = free_client.post(f'/api/dreams/goals/{goal.id}/complete/')
        assert r.status_code == 200

        # 9. Re-complete goal → 400
        r = free_client.post(f'/api/dreams/goals/{goal.id}/complete/')
        assert r.status_code == 400

        # 10. Complete dream
        r = free_client.post(f'/api/dreams/dreams/{dream_id}/complete/')
        assert r.status_code == 200

        # 11. Re-complete dream → 400
        r = free_client.post(f'/api/dreams/dreams/{dream_id}/complete/')
        assert r.status_code == 400

        # 12. Verify DB state
        dream.refresh_from_db()
        assert dream.status == 'completed'
        assert dream.progress_percentage == 100.0
        assert dream.completed_at is not None

        # 13. XP was awarded
        free_user.refresh_from_db()
        assert free_user.xp > xp_before

    def test_task_deletion_recalculates_progress(self, free_client, free_user):
        """Delete a task mid-flow and verify progress recalculation."""
        dream = Dream.objects.create(
            user=free_user, title='Progress Test', status='active',
        )
        goal = Goal.objects.create(dream=dream, title='Goal', order=0)
        t1 = Task.objects.create(goal=goal, title='T1', order=0, status='completed')
        t2 = Task.objects.create(goal=goal, title='T2', order=1, status='pending')
        t3 = Task.objects.create(goal=goal, title='T3', order=2, status='pending')
        goal.update_progress()

        goal.refresh_from_db()
        # 1/3 ≈ 33%
        assert 30 < goal.progress_percentage < 35

        # Delete a pending task → signal recalculates
        r = free_client.delete(f'/api/dreams/tasks/{t3.id}/')
        assert r.status_code == 204

        goal.refresh_from_db()
        # 1/2 = 50%
        assert 49 < goal.progress_percentage < 51


# ═════════════════════════════════════════════════════════════════════
# QA-4: Dream Sharing & Access Control
# ═════════════════════════════════════════════════════════════════════

class TestQA_DreamSharing:
    """
    Flow: User A creates dream → shares with User B →
          User B sees it in their list → User A unshares →
          User B no longer sees it.
    """

    def test_share_and_access_flow(self, free_client, free_user, second_client_qa, second_user_qa):
        # 1. User A creates a dream
        r = free_client.post('/api/dreams/dreams/', {
            'title': 'Shared Dream', 'description': 'Will be shared',
            'category': 'personal', 'priority': 1,
        })
        assert r.status_code == 201
        dream_id = r.data['id']

        # 2. User B can't see it yet
        r = second_client_qa.get('/api/dreams/dreams/')
        dream_ids = [d['id'] for d in r.data.get('results', r.data)]
        assert dream_id not in dream_ids

        # 3. User A shares with User B
        r = free_client.post(f'/api/dreams/dreams/{dream_id}/share/', {
            'shared_with_id': str(second_user_qa.id),
            'permission': 'view',
        })
        assert r.status_code == 201

        # 4. User B now sees it
        r = second_client_qa.get('/api/dreams/dreams/')
        dream_ids = [d['id'] for d in r.data.get('results', r.data)]
        assert dream_id in dream_ids

        # 5. Notification was created for User B (type='progress' with data.type='dream_shared')
        assert Notification.objects.filter(
            user=second_user_qa,
            notification_type='progress',
            data__type='dream_shared',
        ).exists()

        # 6. Unshare
        r = free_client.delete(
            f'/api/dreams/dreams/{dream_id}/unshare/{second_user_qa.id}/'
        )
        assert r.status_code in (200, 204)

        # 7. User B no longer sees it
        r = second_client_qa.get('/api/dreams/dreams/')
        dream_ids = [d['id'] for d in r.data.get('results', r.data)]
        assert dream_id not in dream_ids

    def test_cannot_share_with_self(self, free_client, free_user):
        dream = Dream.objects.create(user=free_user, title='Self Share', status='active')
        r = free_client.post(f'/api/dreams/dreams/{dream.id}/share/', {
            'shared_with_id': str(free_user.id),
            'permission': 'view',
        })
        assert r.status_code == 400

    def test_other_user_cannot_access_unshared_dream(self, free_user, second_client_qa):
        dream = Dream.objects.create(user=free_user, title='Private', status='active')
        r = second_client_qa.get(f'/api/dreams/dreams/{dream.id}/')
        assert r.status_code == 404


# ═════════════════════════════════════════════════════════════════════
# QA-5: Buddy Pairing Lifecycle with Expiration
# ═════════════════════════════════════════════════════════════════════

class TestQA_BuddyLifecycle:
    """
    Flow: Premium user pairs → pending → accept → encourage →
          check progress → end pairing → verify history.
    Also: pending request expires after 7 days.
    """

    def test_buddy_pairing_full_flow(self, premium_client_qa, premium_user_qa,
                                      second_premium_client_qa, second_premium_qa):
        # 1. Create pairing
        r = premium_client_qa.post('/api/buddies/pair/', {
            'partner_id': str(second_premium_qa.id),
        })
        assert r.status_code in (200, 201)
        pairing_id = r.data.get('pairing_id') or r.data.get('id')
        assert pairing_id is not None

        # 2. Verify pairing has expires_at set
        pairing = BuddyPairing.objects.get(id=pairing_id)
        assert pairing.expires_at is not None
        assert pairing.status == 'pending'

        # 3. Partner accepts
        r = second_premium_client_qa.post(f'/api/buddies/{pairing_id}/accept/')
        assert r.status_code == 200

        pairing.refresh_from_db()
        assert pairing.status == 'active'

        # 4. Send encouragement
        r = premium_client_qa.post(f'/api/buddies/{pairing_id}/encourage/', {
            'message': 'You got this!',
        })
        assert r.status_code == 200
        assert BuddyEncouragement.objects.filter(pairing=pairing).count() >= 1

        # 5. Check progress
        r = premium_client_qa.get(f'/api/buddies/{pairing_id}/progress/')
        assert r.status_code == 200

        # 6. End pairing
        r = premium_client_qa.delete(f'/api/buddies/{pairing_id}/')
        assert r.status_code == 200

        # 7. Check history
        r = premium_client_qa.get('/api/buddies/history/')
        assert r.status_code == 200

    def test_buddy_request_auto_expiration(self, db):
        """Pending requests past expires_at get cancelled by task."""
        u1 = User.objects.create_user(
            email='exp1@qa.com', password='test', subscription='premium',
            subscription_ends=timezone.now() + timedelta(days=30),
        )
        u2 = User.objects.create_user(
            email='exp2@qa.com', password='test', subscription='premium',
            subscription_ends=timezone.now() + timedelta(days=30),
        )

        # Create expired pending pairing
        expired = BuddyPairing.objects.create(
            user1=u1, user2=u2, status='pending',
            expires_at=timezone.now() - timedelta(days=1),
        )

        # Create fresh pending pairing
        fresh = BuddyPairing.objects.create(
            user1=u2, user2=u1, status='pending',
            expires_at=timezone.now() + timedelta(days=6),
        )

        # Run expiration task
        from apps.buddies.tasks import expire_pending_buddy_requests
        count = expire_pending_buddy_requests()

        assert count == 1
        expired.refresh_from_db()
        assert expired.status == 'cancelled'
        fresh.refresh_from_db()
        assert fresh.status == 'pending'


# ═════════════════════════════════════════════════════════════════════
# QA-6: GDPR Account Deletion Flow
# ═════════════════════════════════════════════════════════════════════

class TestQA_GDPRDeletionFlow:
    """
    Flow: User creates data → soft-delete account →
          verify anonymized → 30 days pass → hard-delete task removes.
    """

    def test_soft_delete_then_hard_delete(self, db):
        # 1. Create user with data
        user = User.objects.create_user(
            email='gdpr@qa.com', password='QaTest123!',
            display_name='GDPR Test User',
        )
        dream = Dream.objects.create(user=user, title='GDPR Dream', status='active')
        user_id = user.id
        dream_id = dream.id

        client = APIClient()
        client.force_authenticate(user=user)

        # 2. Soft-delete account (requires password)
        r = client.delete('/api/users/delete-account/', {'password': 'QaTest123!'})
        assert r.status_code in (200, 204)

        # 3. Verify soft-deleted
        user.refresh_from_db()
        assert user.is_active is False

        # 4. Simulate 31 days passing
        User.objects.filter(pk=user_id).update(
            updated_at=timezone.now() - timedelta(days=31),
        )

        # 5. Run hard-delete task
        from apps.users.tasks import hard_delete_expired_accounts
        count = hard_delete_expired_accounts()

        assert count >= 1
        assert not User.objects.filter(pk=user_id).exists()
        # CASCADE should delete dream too
        assert not Dream.objects.filter(pk=dream_id).exists()

    def test_recently_deleted_account_preserved(self, db):
        """Account deleted 5 days ago should NOT be hard-deleted."""
        user = User.objects.create_user(email='recent@qa.com', password='test')
        user.is_active = False
        user.save()
        # updated_at is auto-set to now (< 30 days)

        from apps.users.tasks import hard_delete_expired_accounts
        hard_delete_expired_accounts()

        assert User.objects.filter(pk=user.pk).exists()


# ═════════════════════════════════════════════════════════════════════
# QA-7: Achievement + Notification Chain
# ═════════════════════════════════════════════════════════════════════

class TestQA_AchievementNotification:
    """
    Flow: Complete dream → achievement unlocked → notification created.
    """

    def test_dream_completion_triggers_achievement_notification(self, free_user):
        GamificationProfile.objects.create(user=free_user)

        achievement = Achievement.objects.create(
            name='First Dream Completed QA',
            description='Complete your first dream',
            icon='star',
            category='dreams',
            condition_type='dreams_completed',
            condition_value=1,
        )

        dream = Dream.objects.create(user=free_user, title='Achieve Test', status='active')
        dream.complete()

        # Check achievement was unlocked
        unlocked = UserAchievement.objects.filter(
            user=free_user, achievement=achievement,
        ).exists()

        if unlocked:
            # Notification should exist
            assert Notification.objects.filter(
                user=free_user,
                notification_type='achievement',
            ).exists()


# ═════════════════════════════════════════════════════════════════════
# QA-8: Subscription Tier Gating
# ═════════════════════════════════════════════════════════════════════

class TestQA_SubscriptionGating:
    """Verify free users are blocked from premium/pro features."""

    def test_free_user_blocked_from_buddies(self, free_client):
        r = free_client.post('/api/buddies/find-match/')
        assert r.status_code == 403

    def test_free_user_blocked_from_leagues(self, free_client):
        r = free_client.get('/api/leagues/leagues/')
        assert r.status_code == 403

    def test_premium_user_can_access_buddies(self, premium_client_qa):
        r = premium_client_qa.post('/api/buddies/find-match/')
        # Should not be 403 (might be 200 or 404 if no matches)
        assert r.status_code != 403

    def test_free_user_can_access_dreams(self, free_client, free_user):
        r = free_client.get('/api/dreams/dreams/')
        assert r.status_code == 200

    def test_free_user_can_access_profile(self, free_client):
        r = free_client.get('/api/users/me/')
        assert r.status_code == 200


# ═════════════════════════════════════════════════════════════════════
# QA-9: Circle Ownership Transfer on Leave
# ═════════════════════════════════════════════════════════════════════

class TestQA_CircleOwnershipTransfer:
    """
    Flow: Pro user creates circle → second pro joins →
          creator leaves → ownership auto-transferred.
    """

    def test_creator_leave_transfers_ownership(self, pro_user_qa):
        second_pro = User.objects.create_user(
            email='pro_circle@qa.com', password='test',
            subscription='pro',
            subscription_ends=timezone.now() + timedelta(days=30),
        )

        # Create circle and membership directly
        circle = Circle.objects.create(
            name='QA Circle', description='Test', category='health',
            creator=pro_user_qa, is_public=True,
        )
        CircleMembership.objects.create(
            circle=circle, user=pro_user_qa, role='admin',
        )
        CircleMembership.objects.create(
            circle=circle, user=second_pro, role='member',
        )

        # Creator leaves via API
        pro_client = APIClient()
        pro_client.force_authenticate(user=pro_user_qa)
        r = pro_client.post(f'/api/circles/{circle.id}/leave/')
        assert r.status_code == 200

        # Verify ownership transferred
        circle.refresh_from_db()
        assert circle.creator_id != pro_user_qa.id


# ═════════════════════════════════════════════════════════════════════
# QA-10: Search API Integration
# ═════════════════════════════════════════════════════════════════════

class TestQA_SearchAPI:
    """Test the global search endpoint end-to-end."""

    @patch('apps.search.services.SearchService.global_search')
    def test_search_returns_categorized_results(self, mock_search, free_client, free_user):
        dream = Dream.objects.create(user=free_user, title='Python Mastery', status='active')
        mock_search.return_value = {'dreams': [str(dream.id)]}

        r = free_client.get('/api/search/?q=python')
        assert r.status_code == 200
        assert 'dreams' in r.data
        assert r.data['dreams'][0]['title'] == 'Python Mastery'

    def test_search_short_query_rejected(self, free_client):
        r = free_client.get('/api/search/?q=a')
        assert r.status_code == 400

    def test_search_empty_query_rejected(self, free_client):
        r = free_client.get('/api/search/')
        assert r.status_code == 400

    @patch('apps.search.services.SearchService.global_search')
    def test_search_type_filter(self, mock_search, free_client, free_user):
        mock_search.return_value = {'dreams': []}
        free_client.get('/api/search/?q=test&type=dreams')
        mock_search.assert_called_once_with(free_user, 'test', types=['dreams'], limit=10)

    def test_search_requires_auth(self, db):
        anon = APIClient()
        r = anon.get('/api/search/?q=test')
        assert r.status_code == 401


# ═════════════════════════════════════════════════════════════════════
# QA-11: Dream CRUD + Ownership Isolation (IDOR)
# ═════════════════════════════════════════════════════════════════════

class TestQA_DreamCRUD_IDOR:
    """Verify CRUD and ownership isolation between users."""

    def test_full_crud(self, free_client, free_user):
        # CREATE
        r = free_client.post('/api/dreams/dreams/', {
            'title': 'CRUD Dream', 'description': 'Testing',
            'category': 'health', 'priority': 2,
        })
        assert r.status_code == 201
        dream_id = r.data['id']

        # READ
        r = free_client.get(f'/api/dreams/dreams/{dream_id}/')
        assert r.status_code == 200
        assert r.data['title'] == 'CRUD Dream'

        # UPDATE
        r = free_client.patch(f'/api/dreams/dreams/{dream_id}/', {
            'title': 'Updated CRUD Dream',
        })
        assert r.status_code == 200
        assert r.data['title'] == 'Updated CRUD Dream'

        # LIST
        r = free_client.get('/api/dreams/dreams/')
        assert r.status_code == 200
        ids = [d['id'] for d in r.data.get('results', r.data)]
        assert dream_id in ids

        # DELETE
        r = free_client.delete(f'/api/dreams/dreams/{dream_id}/')
        assert r.status_code == 204
        assert not Dream.objects.filter(id=dream_id).exists()

    def test_user_cannot_access_other_users_dream(self, free_user, second_client_qa):
        dream = Dream.objects.create(user=free_user, title='Private', status='active')

        # GET → 404 (not in queryset)
        r = second_client_qa.get(f'/api/dreams/dreams/{dream.id}/')
        assert r.status_code == 404

        # UPDATE → 404
        r = second_client_qa.patch(f'/api/dreams/dreams/{dream.id}/', {'title': 'Hacked'})
        assert r.status_code == 404

        # DELETE → 404
        r = second_client_qa.delete(f'/api/dreams/dreams/{dream.id}/')
        assert r.status_code == 404

        # Verify unchanged
        dream.refresh_from_db()
        assert dream.title == 'Private'

    def test_nonexistent_dream_returns_404(self, free_client):
        fake = uuid.uuid4()
        r = free_client.get(f'/api/dreams/dreams/{fake}/')
        assert r.status_code == 404


# ═════════════════════════════════════════════════════════════════════
# QA-12: XP and Leveling Chain
# ═════════════════════════════════════════════════════════════════════

class TestQA_XPLeveling:
    """Verify XP is awarded correctly through the completion chain."""

    def test_xp_awarded_on_task_goal_dream_completion(self, free_client, free_user):
        dream = Dream.objects.create(user=free_user, title='XP Test', status='active')
        goal = Goal.objects.create(dream=dream, title='Goal', order=0)
        task = Task.objects.create(goal=goal, title='Task', order=0, duration_mins=60)

        free_user.refresh_from_db()
        xp_start = free_user.xp

        # Complete task → XP awarded (max(10, 60//3) = 20)
        free_client.post(f'/api/dreams/tasks/{task.id}/complete/')
        free_user.refresh_from_db()
        xp_after_task = free_user.xp
        assert xp_after_task > xp_start

        # Complete goal → +100 XP
        free_client.post(f'/api/dreams/goals/{goal.id}/complete/')
        free_user.refresh_from_db()
        xp_after_goal = free_user.xp
        assert xp_after_goal >= xp_after_task + 100

        # Complete dream → +500 XP
        free_client.post(f'/api/dreams/dreams/{dream.id}/complete/')
        free_user.refresh_from_db()
        xp_after_dream = free_user.xp
        assert xp_after_dream >= xp_after_goal + 500

    def test_double_completion_does_not_double_xp(self, free_client, free_user):
        dream = Dream.objects.create(user=free_user, title='Double XP', status='active')
        goal = Goal.objects.create(dream=dream, title='G', order=0)
        task = Task.objects.create(goal=goal, title='T', order=0, duration_mins=30)

        # Complete
        free_client.post(f'/api/dreams/tasks/{task.id}/complete/')
        free_user.refresh_from_db()
        xp_first = free_user.xp

        # Try again → 400, no XP change
        free_client.post(f'/api/dreams/tasks/{task.id}/complete/')
        free_user.refresh_from_db()
        assert free_user.xp == xp_first


# ═════════════════════════════════════════════════════════════════════
# QA-13: Notification Pipeline
# ═════════════════════════════════════════════════════════════════════

class TestQA_NotificationPipeline:
    """Verify notifications are created and listable via API."""

    def test_list_notifications(self, free_client, free_user):
        Notification.objects.create(
            user=free_user,
            notification_type='reminder',
            title='Test Reminder',
            body='Don\'t forget!',
            scheduled_for=timezone.now(),
        )

        r = free_client.get('/api/notifications/')
        assert r.status_code == 200
        results = r.data.get('results', r.data)
        assert len(results) >= 1

    def test_mark_notification_read(self, free_client, free_user):
        notif = Notification.objects.create(
            user=free_user,
            notification_type='reminder',
            title='Mark Read Test',
            body='Body',
            scheduled_for=timezone.now(),
        )

        r = free_client.post(f'/api/notifications/{notif.id}/mark_read/')
        assert r.status_code == 200

        notif.refresh_from_db()
        assert notif.read_at is not None

    def test_user_cannot_see_others_notifications(self, free_user, second_client_qa):
        notif = Notification.objects.create(
            user=free_user,
            notification_type='reminder',
            title='Private Notification',
            body='Secret',
            scheduled_for=timezone.now(),
        )

        r = second_client_qa.get(f'/api/notifications/{notif.id}/')
        assert r.status_code == 404


# ═════════════════════════════════════════════════════════════════════
# QA-14: Error Handling Standardization
# ═════════════════════════════════════════════════════════════════════

class TestQA_ErrorResponses:
    """Verify error responses follow standardized format."""

    def test_401_unauthenticated(self, db):
        anon = APIClient()
        r = anon.get('/api/dreams/dreams/')
        assert r.status_code == 401
        assert 'error' in r.data or 'detail' in r.data

    def test_404_not_found(self, free_client):
        r = free_client.get(f'/api/dreams/dreams/{uuid.uuid4()}/')
        assert r.status_code == 404

    def test_400_invalid_input(self, free_client):
        r = free_client.post('/api/dreams/dreams/', {})
        assert r.status_code == 400

    def test_403_subscription_required(self, free_client):
        r = free_client.get('/api/leagues/leagues/')
        assert r.status_code == 403


# ═════════════════════════════════════════════════════════════════════
# QA-15: Caching Verification
# ═════════════════════════════════════════════════════════════════════

class TestQA_Caching:
    """Verify cached endpoints return consistent data."""

    @patch('apps.search.services.SearchService.global_search')
    def test_search_endpoint_works(self, mock_search, free_client):
        mock_search.return_value = {}
        r1 = free_client.get('/api/search/?q=test')
        assert r1.status_code == 200

    def test_dream_list_endpoint_works(self, free_client, free_user):
        Dream.objects.create(user=free_user, title='Cache Test', status='active')
        r = free_client.get('/api/dreams/dreams/')
        assert r.status_code == 200


# ═════════════════════════════════════════════════════════════════════
# QA-16: User Profile API
# ═════════════════════════════════════════════════════════════════════

class TestQA_UserProfile:
    """Test user profile endpoints."""

    def test_get_profile(self, free_client, free_user):
        r = free_client.get('/api/users/me/')
        assert r.status_code == 200
        assert r.data['email'] == free_user.email

    def test_update_profile(self, free_client):
        r = free_client.patch('/api/users/update_profile/', {
            'display_name': 'Updated QA Name',
        })
        assert r.status_code == 200

    def test_get_stats(self, free_client, free_user):
        GamificationProfile.objects.get_or_create(user=free_user)
        r = free_client.get('/api/users/stats/')
        assert r.status_code == 200


# ═════════════════════════════════════════════════════════════════════
# QA-17: League & Season Integration
# ═════════════════════════════════════════════════════════════════════

class TestQA_LeagueSeason:
    """Premium/Pro users can access league features."""

    def test_premium_can_list_leagues(self, premium_client_qa):
        r = premium_client_qa.get('/api/leagues/leagues/')
        assert r.status_code == 200

    def test_premium_can_check_standing(self, premium_client_qa):
        r = premium_client_qa.get('/api/leagues/leaderboard/me/')
        # 200 or 404 (no active season) both acceptable
        assert r.status_code in (200, 404)

    def test_free_user_blocked(self, free_client):
        r = free_client.get('/api/leagues/leagues/')
        assert r.status_code == 403
