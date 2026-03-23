"""
Tests for friends models.
"""

import pytest

from apps.friends.models import BlockedUser, Friendship, ReportedUser, UserFollow


@pytest.mark.django_db
class TestFriendship:
    def test_create(self, friend_user_a, friend_user_b):
        f = Friendship.objects.create(
            user1=friend_user_a, user2=friend_user_b, status="pending"
        )
        assert f.status == "pending"

    def test_accept(self, friend_user_a, friend_user_b):
        f = Friendship.objects.create(
            user1=friend_user_a, user2=friend_user_b, status="pending"
        )
        f.status = "accepted"
        f.save()
        assert f.status == "accepted"

    def test_unique_constraint(self, friend_user_a, friend_user_b):
        Friendship.objects.create(user1=friend_user_a, user2=friend_user_b)
        with pytest.raises(Exception):
            Friendship.objects.create(user1=friend_user_a, user2=friend_user_b)


@pytest.mark.django_db
class TestUserFollow:
    def test_follow(self, friend_user_a, friend_user_b):
        follow = UserFollow.objects.create(
            follower=friend_user_a, following=friend_user_b
        )
        assert follow.follower == friend_user_a
        assert follow.following == friend_user_b


@pytest.mark.django_db
class TestBlockedUser:
    def test_block(self, friend_user_a, friend_user_b):
        block = BlockedUser.objects.create(blocker=friend_user_a, blocked=friend_user_b)
        assert BlockedUser.is_blocked(friend_user_a, friend_user_b)
        assert BlockedUser.is_blocked(friend_user_b, friend_user_a)

    def test_not_blocked(self, friend_user_a, friend_user_b):
        assert not BlockedUser.is_blocked(friend_user_a, friend_user_b)


@pytest.mark.django_db
class TestReportedUser:
    def test_report(self, friend_user_a, friend_user_b):
        report = ReportedUser.objects.create(
            reporter=friend_user_a,
            reported=friend_user_b,
            reason="Test report",
            category="spam",
        )
        assert report.status == "pending"
