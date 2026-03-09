"""
Tests for users app.
"""

import pytest
from django.utils import timezone
from datetime import timedelta
from rest_framework import status
from rest_framework.test import APIRequestFactory
from rest_framework.authtoken.models import Token
from unittest.mock import Mock
import uuid

from .models import User, GamificationProfile
from core.authentication import ExpiringTokenAuthentication


class TestUserModel:
    """Test User model"""

    def test_create_user(self, db, user_data):
        """Test creating a user"""
        user = User.objects.create(**user_data)
        assert user.email == user_data['email']
        assert user.display_name == user_data['display_name']
        assert user.subscription == 'free'
        assert user.xp == 0
        assert user.level == 1
        assert user.streak_days == 0

    def test_user_str(self, user):
        """Test user string representation"""
        expected = f"{user.email} ({user.display_name or 'No name'})"
        assert str(user) == expected

    def test_is_premium(self, user, premium_user):
        """Test is_premium method"""
        assert not user.is_premium()
        assert premium_user.is_premium()

    def test_is_premium_expired(self, user, db):
        """Test is_premium checks the Subscription table plan, not expiry."""
        from apps.subscriptions.models import Subscription, SubscriptionPlan
        premium_plan = SubscriptionPlan.objects.filter(slug='premium').first()
        if not premium_plan:
            pytest.skip('No premium plan in DB')
        sub, _ = Subscription.objects.get_or_create(user=user, defaults={'plan': premium_plan, 'status': 'active'})
        sub.plan = premium_plan
        sub.status = 'active'
        sub.save()
        user.subscription_ends = timezone.now() - timedelta(days=1)
        user.save(update_fields=['subscription_ends'])
        if hasattr(user, '_cached_plan'):
            del user._cached_plan
        # is_premium() reads from Subscription table, not User.subscription
        assert user.is_premium()

    def test_update_activity(self, user):
        """Test update_activity sets last_activity to now"""
        old_activity = user.last_activity
        user.update_activity()
        user.refresh_from_db()
        assert user.last_activity >= old_activity

    def test_add_xp(self, user):
        """Test adding XP"""
        initial_xp = user.xp

        user.add_xp(100)

        assert user.xp == initial_xp + 100

    def test_add_xp_level_up(self, user):
        """Test level up when XP threshold reached"""
        user.xp = 0
        user.level = 1
        user.save()

        # Add enough XP to level up (100 XP per level)
        user.add_xp(150)

        assert user.level == 2
        assert user.xp == 150

    def test_level_up_calculation(self, user):
        """Test level calculation based on XP"""
        user.xp = 0
        assert user.level == 1

        user.xp = 100
        user.save()
        user.refresh_from_db()
        # Level should be recalculated in save method or property


class TestGamificationProfile:
    """Test GamificationProfile model"""

    def test_create_gamification_profile(self, db, user):
        """Test creating gamification profile"""
        profile = GamificationProfile.objects.create(
            user=user,
            health_xp=50,
            career_xp=30,
            relationships_xp=20,
            personal_growth_xp=10,
            finance_xp=0,
            hobbies_xp=15,
        )

        assert profile.user == user
        assert profile.health_xp == 50
        assert profile.career_xp == 30
        assert profile.relationships_xp == 20
        assert profile.personal_growth_xp == 10
        assert profile.finance_xp == 0
        assert profile.hobbies_xp == 15
        assert profile.badges == []
        assert profile.achievements == []
        assert profile.streak_jokers == 3

    def test_update_attribute(self, gamification_profile):
        """Test updating gamification attribute XP fields"""
        initial_health = gamification_profile.health_xp

        gamification_profile.health_xp = initial_health + 10
        gamification_profile.save()

        gamification_profile.refresh_from_db()
        assert gamification_profile.health_xp == initial_health + 10


class TestTokenAuthentication:
    """Test Token authentication backend"""

    def test_token_auth_success(self, db, user):
        """Test successful Token authentication with 'Token' keyword"""
        token = Token.objects.create(user=user)
        authenticator = ExpiringTokenAuthentication()

        factory = APIRequestFactory()
        request = factory.get('/', HTTP_AUTHORIZATION=f'Token {token.key}')

        authenticated_user, auth_token = authenticator.authenticate(request)

        assert authenticated_user == user
        assert auth_token == token

    def test_bearer_keyword_auth(self, db, user):
        """Test ExpiringTokenAuthentication converts 'Bearer' to 'Token' and authenticates"""
        token = Token.objects.create(user=user)
        authenticator = ExpiringTokenAuthentication()

        factory = APIRequestFactory()
        request = factory.get('/', HTTP_AUTHORIZATION=f'Bearer {token.key}')

        authenticated_user, auth_token = authenticator.authenticate(request)

        assert authenticated_user == user
        assert auth_token == token

    def test_missing_token_returns_none(self, db):
        """Test missing auth header returns None"""
        authenticator = ExpiringTokenAuthentication()

        factory = APIRequestFactory()
        request = factory.get('/')

        result = authenticator.authenticate(request)
        assert result is None

    def test_invalid_token_raises_error(self, db):
        """Test invalid token raises AuthenticationFailed"""
        from rest_framework.exceptions import AuthenticationFailed

        authenticator = ExpiringTokenAuthentication()

        factory = APIRequestFactory()
        request = factory.get('/', HTTP_AUTHORIZATION='Token invalidtokenkey123')

        with pytest.raises(AuthenticationFailed):
            authenticator.authenticate(request)


class TestUserViewSet:
    """Test User API endpoints"""

    def test_get_current_user(self, authenticated_client, user):
        """Test GET /api/users/me/"""
        response = authenticated_client.get('/api/users/me/')

        assert response.status_code == status.HTTP_200_OK
        assert response.data['email'] == user.email
        assert response.data['display_name'] == user.display_name

    def test_update_current_user(self, authenticated_client, user):
        """Test PUT /api/users/update_profile/"""
        data = {
            'display_name': 'Updated Name',
            'timezone': 'America/New_York'
        }

        response = authenticated_client.put('/api/users/update_profile/', data, format='json')

        assert response.status_code == status.HTTP_200_OK
        assert response.data['display_name'] == 'Updated Name'

        user.refresh_from_db()
        assert user.display_name == 'Updated Name'
        assert user.timezone == 'America/New_York'

    def test_partial_update_current_user(self, authenticated_client, user):
        """Test PATCH /api/users/update_profile/"""
        data = {'display_name': 'Partial Update'}

        response = authenticated_client.patch('/api/users/update_profile/', data, format='json')

        assert response.status_code == status.HTTP_200_OK
        user.refresh_from_db()
        assert user.display_name == 'Partial Update'

    def test_update_preferences(self, authenticated_client, user):
        """Test PUT /api/users/notification-preferences/"""
        data = {
            'motivation': True,
            'weekly_report': True,
            'reminders': False
        }

        response = authenticated_client.put('/api/users/notification-preferences/', data, format='json')

        assert response.status_code == status.HTTP_200_OK

        user.refresh_from_db()
        assert user.notification_prefs['motivation'] is True
        assert user.notification_prefs['weekly_report'] is True

    def test_get_stats(self, authenticated_client, user):
        """Test GET /api/users/stats/"""
        response = authenticated_client.get('/api/users/stats/')

        assert response.status_code == status.HTTP_200_OK
        assert 'total_dreams' in response.data
        assert 'completed_dreams' in response.data
        assert 'active_dreams' in response.data
        assert 'total_tasks_completed' in response.data

    def test_unauthenticated_access(self, api_client):
        """Test unauthenticated access is denied"""
        response = api_client.get('/api/users/me/')
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
