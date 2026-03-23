"""
Tests for friends services.
"""

import pytest

from apps.friends.models import BlockedUser, Friendship
from apps.friends.services import FriendshipService
from apps.users.models import User


@pytest.fixture
def svc_user_a(db):
    return User.objects.create_user(email="fsva@test.com", password="testpass123")


@pytest.fixture
def svc_user_b(db):
    return User.objects.create_user(email="fsvb@test.com", password="testpass123")


@pytest.fixture
def svc_user_c(db):
    return User.objects.create_user(email="fsvc@test.com", password="testpass123")


@pytest.mark.django_db
class TestFriendshipService:
    def test_is_friend(self, svc_user_a, svc_user_b):
        Friendship.objects.create(user1=svc_user_a, user2=svc_user_b, status="accepted")
        assert FriendshipService.is_friend(svc_user_a.id, svc_user_b.id)
        assert FriendshipService.is_friend(svc_user_b.id, svc_user_a.id)

    def test_not_friend(self, svc_user_a, svc_user_b):
        assert not FriendshipService.is_friend(svc_user_a.id, svc_user_b.id)

    def test_is_blocked(self, svc_user_a, svc_user_b):
        BlockedUser.objects.create(blocker=svc_user_a, blocked=svc_user_b)
        assert FriendshipService.is_blocked(svc_user_a.id, svc_user_b.id)

    def test_mutual_friends(self, svc_user_a, svc_user_b, svc_user_c):
        # A-C friends, B-C friends
        Friendship.objects.create(user1=svc_user_a, user2=svc_user_c, status="accepted")
        Friendship.objects.create(user1=svc_user_b, user2=svc_user_c, status="accepted")
        mutual = FriendshipService.mutual_friends(svc_user_a.id, svc_user_b.id)
        assert len(mutual) == 1
        assert mutual[0]["id"] == str(svc_user_c.id)

    def test_suggestions(self, svc_user_a, svc_user_b):
        suggestions = FriendshipService.suggestions(svc_user_a, limit=5)
        user_ids = [s["id"] for s in suggestions]
        assert str(svc_user_b.id) in user_ids
