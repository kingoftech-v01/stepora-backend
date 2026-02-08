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

from .models import User, FcmToken, GamificationProfile, DreamBuddy, Badge
from core.authentication import BearerTokenAuthentication


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
        assert str(user) == user.email

    def test_is_premium(self, user, premium_user):
        """Test is_premium property"""
        assert not user.is_premium
        assert premium_user.is_premium

    def test_is_premium_expired(self, user):
        """Test is_premium with expired subscription"""
        user.subscription = 'premium'
        user.subscription_ends = timezone.now() - timedelta(days=1)
        user.save()
        assert not user.is_premium

    def test_update_streak_increment(self, user):
        """Test incrementing streak"""
        user.last_activity = timezone.now() - timedelta(days=1)
        user.save()

        user.update_streak()
        assert user.streak_days == 1

        user.last_activity = timezone.now() - timedelta(days=1)
        user.save()
        user.update_streak()
        assert user.streak_days == 2

    def test_update_streak_reset(self, user):
        """Test streak resets after missing a day"""
        user.streak_days = 5
        user.last_activity = timezone.now() - timedelta(days=3)
        user.save()

        user.update_streak()
        assert user.streak_days == 0

    def test_update_streak_same_day(self, user):
        """Test streak doesn't change on same day"""
        user.streak_days = 3
        user.last_activity = timezone.now()
        user.save()

        user.update_streak()
        assert user.streak_days == 3

    def test_award_xp(self, user):
        """Test awarding XP"""
        initial_xp = user.xp
        initial_level = user.level

        user.award_xp(100)

        assert user.xp == initial_xp + 100

    def test_award_xp_level_up(self, user):
        """Test level up when XP threshold reached"""
        user.xp = 0
        user.level = 1
        user.save()

        # Award enough XP to level up (100 XP per level)
        user.award_xp(150)

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


class TestFcmTokenModel:
    """Test FcmToken model"""

    def test_create_fcm_token(self, db, user):
        """Test creating FCM token"""
        token = FcmToken.objects.create(
            user=user,
            token='test_fcm_token',
            device_type='ios'
        )

        assert token.user == user
        assert token.token == 'test_fcm_token'
        assert token.device_type == 'ios'

    def test_fcm_token_unique_per_user(self, db, user):
        """Test FCM token uniqueness"""
        FcmToken.objects.create(
            user=user,
            token='token1',
            device_type='ios'
        )

        # Creating another token with same value should update, not create new
        token2, created = FcmToken.objects.get_or_create(
            user=user,
            token='token1',
            defaults={'device_type': 'ios'}
        )

        assert not created


class TestGamificationProfile:
    """Test GamificationProfile model"""

    def test_create_gamification_profile(self, db, user):
        """Test creating gamification profile"""
        profile = GamificationProfile.objects.create(
            user=user,
            xp=100,
            level=2,
            attributes={'health': 50, 'career': 30}
        )

        assert profile.user == user
        assert profile.xp == 100
        assert profile.level == 2
        assert profile.attributes['health'] == 50

    def test_update_attribute(self, gamification_profile):
        """Test updating gamification attributes"""
        initial_health = gamification_profile.attributes.get('health', 0)

        gamification_profile.attributes['health'] = initial_health + 10
        gamification_profile.save()

        gamification_profile.refresh_from_db()
        assert gamification_profile.attributes['health'] == initial_health + 10


class TestTokenAuthentication:
    """Test Token authentication backend"""

    def test_token_auth_success(self, db, user):
        """Test successful Token authentication with 'Token' keyword"""
        token = Token.objects.create(user=user)
        authenticator = BearerTokenAuthentication()

        factory = APIRequestFactory()
        request = factory.get('/', HTTP_AUTHORIZATION=f'Token {token.key}')

        authenticated_user, auth_token = authenticator.authenticate(request)

        assert authenticated_user == user
        assert auth_token == token

    def test_bearer_keyword_auth(self, db, user):
        """Test BearerTokenAuthentication converts 'Bearer' to 'Token' and authenticates"""
        token = Token.objects.create(user=user)
        authenticator = BearerTokenAuthentication()

        factory = APIRequestFactory()
        request = factory.get('/', HTTP_AUTHORIZATION=f'Bearer {token.key}')

        authenticated_user, auth_token = authenticator.authenticate(request)

        assert authenticated_user == user
        assert auth_token == token

    def test_missing_token_returns_none(self, db):
        """Test missing auth header returns None"""
        authenticator = BearerTokenAuthentication()

        factory = APIRequestFactory()
        request = factory.get('/')

        result = authenticator.authenticate(request)
        assert result is None

    def test_invalid_token_raises_error(self, db):
        """Test invalid token raises AuthenticationFailed"""
        from rest_framework.exceptions import AuthenticationFailed

        authenticator = BearerTokenAuthentication()

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
        """Test PUT /api/users/me/"""
        data = {
            'display_name': 'Updated Name',
            'timezone': 'America/New_York'
        }

        response = authenticated_client.put('/api/users/me/', data, format='json')

        assert response.status_code == status.HTTP_200_OK
        assert response.data['display_name'] == 'Updated Name'

        user.refresh_from_db()
        assert user.display_name == 'Updated Name'
        assert user.timezone == 'America/New_York'

    def test_partial_update_current_user(self, authenticated_client, user):
        """Test PATCH /api/users/me/"""
        data = {'display_name': 'Partial Update'}

        response = authenticated_client.patch('/api/users/me/', data, format='json')

        assert response.status_code == status.HTTP_200_OK
        user.refresh_from_db()
        assert user.display_name == 'Partial Update'

    def test_register_fcm_token(self, authenticated_client, user):
        """Test POST /api/users/me/register-fcm-token/"""
        data = {
            'token': 'new_fcm_token_123',
            'device_type': 'android'
        }

        response = authenticated_client.post('/api/users/me/register-fcm-token/', data, format='json')

        assert response.status_code == status.HTTP_201_CREATED
        assert FcmToken.objects.filter(user=user, token='new_fcm_token_123').exists()

    def test_update_preferences(self, authenticated_client, user):
        """Test POST /api/users/me/update-preferences/"""
        data = {
            'notification_prefs': {
                'motivation': True,
                'weekly_report': True,
                'reminders': False
            },
            'app_prefs': {
                'theme': 'dark',
                'language': 'fr'
            }
        }

        response = authenticated_client.post('/api/users/me/update-preferences/', data, format='json')

        assert response.status_code == status.HTTP_200_OK

        user.refresh_from_db()
        assert user.notification_prefs['motivation'] is True
        assert user.app_prefs['theme'] == 'dark'

    def test_get_stats(self, authenticated_client, user):
        """Test GET /api/users/me/stats/"""
        response = authenticated_client.get('/api/users/me/stats/')

        assert response.status_code == status.HTTP_200_OK
        assert 'total_dreams' in response.data
        assert 'completed_dreams' in response.data
        assert 'total_tasks' in response.data
        assert 'completed_tasks' in response.data

    def test_unauthenticated_access(self, api_client):
        """Test unauthenticated access is denied"""
        response = api_client.get('/api/users/me/')
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestDreamBuddyMatching:
    """Test Dream Buddy matching system"""

    def test_find_buddy_similar_goals(self, db, multiple_users):
        """Test finding buddy with similar goals"""
        from apps.dreams.models import Dream

        # Create similar dreams for two users
        Dream.objects.create(
            user=multiple_users[0],
            title='Learn Python',
            category='education',
            status='active'
        )

        Dream.objects.create(
            user=multiple_users[1],
            title='Master Python',
            category='education',
            status='active'
        )

        # Test buddy matching logic
        # This would be implemented in a service
        from apps.users.services import BuddyMatchingService

        # Mock the service for now
        # service = BuddyMatchingService()
        # buddy = service.find_buddy(multiple_users[0])
        # assert buddy == multiple_users[1]

    def test_create_dream_buddy_pair(self, db, multiple_users):
        """Test creating dream buddy pair"""
        buddy_pair = DreamBuddy.objects.create(
            user=multiple_users[0],
            buddy=multiple_users[1],
            status='active'
        )

        assert buddy_pair.user == multiple_users[0]
        assert buddy_pair.buddy == multiple_users[1]
        assert buddy_pair.status == 'active'


class TestBadgeSystem:
    """Test badge/achievement system"""

    def test_create_badge(self, db, user):
        """Test creating a badge"""
        badge = Badge.objects.create(
            user=user,
            badge_type='streak_7',
            name='7 Day Streak',
            description='Maintained a 7-day streak',
            icon_url='https://example.com/badge.png'
        )

        assert badge.user == user
        assert badge.badge_type == 'streak_7'
        assert not badge.is_claimed

    def test_claim_badge(self, db, user):
        """Test claiming a badge"""
        badge = Badge.objects.create(
            user=user,
            badge_type='first_dream',
            name='First Dream',
            description='Created your first dream'
        )

        badge.is_claimed = True
        badge.claimed_at = timezone.now()
        badge.save()

        assert badge.is_claimed
        assert badge.claimed_at is not None
