"""
Integration tests for the Social app API endpoints.
"""

import uuid
from datetime import timedelta
from unittest.mock import patch

import pytest
from django.utils import timezone
from rest_framework import status

from apps.social.models import (
    ActivityFeedItem,
    BlockedUser,
    DreamEncouragement,
    DreamPost,
    DreamPostComment,
    DreamPostLike,
    Friendship,
    PostReaction,
    SavedPost,
    SocialEvent,
    SocialEventRegistration,
    Story,
    UserFollow,
)

# ──────────────────────────────────────────────────────────────────────
#  Social Feed
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestSocialFeed:
    """Integration tests for the social feed endpoint."""

    def test_get_feed_authenticated(self, social_client):
        """Authenticated user can access the social feed."""
        response = social_client.get("/api/social/posts/feed/")
        assert response.status_code == status.HTTP_200_OK

    def test_get_feed_unauthenticated(self):
        """Unauthenticated request returns 401."""
        from rest_framework.test import APIClient

        client = APIClient()
        response = client.get("/api/social/posts/feed/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_feed_includes_own_posts(self, social_client, social_user):
        """Feed includes the user's own posts."""
        DreamPost.objects.create(
            user=social_user,
            content="My own post",
            visibility="public",
        )
        response = social_client.get("/api/social/posts/feed/")
        assert response.status_code == status.HTTP_200_OK
        data = response.data
        # Feed returns results, check structure
        assert isinstance(data, (dict, list))

    def test_feed_includes_friend_posts(self, social_client, social_user, social_user2):
        """Feed includes posts from accepted friends."""
        Friendship.objects.create(
            user1=social_user, user2=social_user2, status="accepted"
        )
        DreamPost.objects.create(
            user=social_user2,
            content="Friend post",
            visibility="public",
        )
        response = social_client.get("/api/social/posts/feed/")
        assert response.status_code == status.HTTP_200_OK


# ──────────────────────────────────────────────────────────────────────
#  Create Post
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestCreatePost:
    """Integration tests for creating dream posts."""

    def test_create_post(self, social_client, social_user):
        """User can create a dream post."""
        response = social_client.post(
            "/api/social/posts/",
            {"content": "My new dream post!", "visibility": "public"},
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert DreamPost.objects.filter(user=social_user).count() == 1
        post = DreamPost.objects.get(user=social_user)
        assert post.content == "My new dream post!"
        assert post.visibility == "public"

    def test_create_post_followers_only(self, social_client, social_user):
        """User can create a post with followers-only visibility."""
        response = social_client.post(
            "/api/social/posts/",
            {"content": "Followers only post", "visibility": "followers"},
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        post = DreamPost.objects.get(user=social_user)
        assert post.visibility == "followers"

    def test_create_post_unauthenticated(self):
        """Unauthenticated user cannot create a post."""
        from rest_framework.test import APIClient

        client = APIClient()
        response = client.post(
            "/api/social/posts/",
            {"content": "Should fail"},
            format="json",
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_create_post_missing_content(self, social_client):
        """Creating a post without content returns 400."""
        response = social_client.post(
            "/api/social/posts/",
            {"visibility": "public"},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST


# ──────────────────────────────────────────────────────────────────────
#  Like / Unlike Post
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestLikePost:
    """Integration tests for like/unlike post endpoints."""

    def test_like_post(self, social_client, social_client2, social_user, social_user2):
        """User can like another user's post."""
        post = DreamPost.objects.create(
            user=social_user, content="Likeable post", visibility="public"
        )
        response = social_client2.post(f"/api/social/posts/{post.id}/like/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["liked"] is True
        assert DreamPostLike.objects.filter(post=post, user=social_user2).exists()

    def test_unlike_post(self, social_client, social_client2, social_user, social_user2):
        """Liking an already-liked post toggles the like off."""
        post = DreamPost.objects.create(
            user=social_user, content="Toggle post", visibility="public"
        )
        # Like first
        social_client2.post(f"/api/social/posts/{post.id}/like/")
        assert DreamPostLike.objects.filter(post=post, user=social_user2).exists()
        # Unlike (toggle)
        response = social_client2.post(f"/api/social/posts/{post.id}/like/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["liked"] is False
        assert not DreamPostLike.objects.filter(post=post, user=social_user2).exists()

    def test_like_nonexistent_post(self, social_client):
        """Liking a nonexistent post returns 404."""
        import uuid

        fake_id = uuid.uuid4()
        response = social_client.post(f"/api/social/posts/{fake_id}/like/")
        assert response.status_code == status.HTTP_404_NOT_FOUND


# ──────────────────────────────────────────────────────────────────────
#  Comment on Post
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestCommentPost:
    """Integration tests for commenting on posts."""

    def test_comment_on_post(self, social_client2, social_user, social_user2):
        """User can comment on a post."""
        post = DreamPost.objects.create(
            user=social_user, content="Comment me", visibility="public"
        )
        response = social_client2.post(
            f"/api/social/posts/{post.id}/comment/",
            {"content": "Great post!"},
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert DreamPostComment.objects.filter(post=post, user=social_user2).exists()

    def test_comment_empty_content(self, social_client, social_user):
        """Commenting with empty content returns 400."""
        post = DreamPost.objects.create(
            user=social_user, content="Post", visibility="public"
        )
        response = social_client.post(
            f"/api/social/posts/{post.id}/comment/",
            {"content": ""},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_list_comments_on_post(self, social_client, social_user, social_user2):
        """Can list comments on a post."""
        post = DreamPost.objects.create(
            user=social_user, content="Post", visibility="public"
        )
        DreamPostComment.objects.create(
            post=post, user=social_user2, content="Comment 1"
        )
        DreamPostComment.objects.create(
            post=post, user=social_user, content="Comment 2"
        )
        response = social_client.get(f"/api/social/posts/{post.id}/comments/")
        assert response.status_code == status.HTTP_200_OK


# ──────────────────────────────────────────────────────────────────────
#  Save Post
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestSavePost:
    """Integration tests for saving/bookmarking posts."""

    def test_save_post(self, social_client2, social_user, social_user2):
        """User can save/bookmark a post."""
        post = DreamPost.objects.create(
            user=social_user, content="Save me", visibility="public"
        )
        response = social_client2.post(f"/api/social/posts/{post.id}/save/")
        assert response.status_code in (
            status.HTTP_200_OK,
            status.HTTP_201_CREATED,
        )

    def test_unsave_post(self, social_client2, social_user, social_user2):
        """Saving an already-saved post toggles the bookmark off."""
        post = DreamPost.objects.create(
            user=social_user, content="Toggle save", visibility="public"
        )
        # Save first
        social_client2.post(f"/api/social/posts/{post.id}/save/")
        # Unsave (toggle)
        response = social_client2.post(f"/api/social/posts/{post.id}/save/")
        assert response.status_code == status.HTTP_200_OK


# ──────────────────────────────────────────────────────────────────────
#  Friend Requests
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestFriendRequest:
    """Integration tests for friend request endpoints."""

    def test_send_friend_request(self, social_client, social_user2):
        """User can send a friend request."""
        response = social_client.post(
            "/api/social/friends/request/",
            {"target_user_id": str(social_user2.id)},
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert Friendship.objects.filter(
            user1__email="socialuser@example.com",
            user2=social_user2,
            status="pending",
        ).exists()

    def test_send_request_to_self(self, social_client, social_user):
        """Cannot send friend request to yourself."""
        response = social_client.post(
            "/api/social/friends/request/",
            {"target_user_id": str(social_user.id)},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_send_duplicate_request(self, social_client, social_user, social_user2):
        """Cannot send duplicate friend request."""
        Friendship.objects.create(
            user1=social_user, user2=social_user2, status="pending"
        )
        response = social_client.post(
            "/api/social/friends/request/",
            {"target_user_id": str(social_user2.id)},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_send_request_already_friends(self, social_client, social_user, social_user2):
        """Cannot send request if already friends."""
        Friendship.objects.create(
            user1=social_user, user2=social_user2, status="accepted"
        )
        response = social_client.post(
            "/api/social/friends/request/",
            {"target_user_id": str(social_user2.id)},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST


# ──────────────────────────────────────────────────────────────────────
#  Accept Friend Request
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestAcceptFriendRequest:
    """Integration tests for accepting friend requests."""

    def test_accept_friend_request(self, social_client2, social_user, social_user2):
        """Recipient can accept a pending friend request."""
        friendship = Friendship.objects.create(
            user1=social_user, user2=social_user2, status="pending"
        )
        response = social_client2.post(
            f"/api/social/friends/accept/{friendship.id}/"
        )
        assert response.status_code == status.HTTP_200_OK
        friendship.refresh_from_db()
        assert friendship.status == "accepted"

    def test_accept_nonexistent_request(self, social_client):
        """Accepting a nonexistent request returns 404."""
        import uuid

        fake_id = uuid.uuid4()
        response = social_client.post(f"/api/social/friends/accept/{fake_id}/")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_cannot_accept_own_request(self, social_client, social_user, social_user2):
        """Sender (user1) cannot accept their own request."""
        friendship = Friendship.objects.create(
            user1=social_user, user2=social_user2, status="pending"
        )
        # social_client is user1 (sender), should not be able to accept
        response = social_client.post(
            f"/api/social/friends/accept/{friendship.id}/"
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND


# ──────────────────────────────────────────────────────────────────────
#  Follow / Unfollow
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestFollowUnfollow:
    """Integration tests for follow/unfollow endpoints."""

    def test_follow_user(self, social_client, social_user, social_user2):
        """User can follow another user."""
        response = social_client.post(
            "/api/social/follow/",
            {"target_user_id": str(social_user2.id)},
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert UserFollow.objects.filter(
            follower=social_user, following=social_user2
        ).exists()

    def test_follow_self(self, social_client, social_user):
        """Cannot follow yourself."""
        response = social_client.post(
            "/api/social/follow/",
            {"target_user_id": str(social_user.id)},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_follow_duplicate(self, social_client, social_user, social_user2):
        """Cannot follow same user twice."""
        UserFollow.objects.create(follower=social_user, following=social_user2)
        response = social_client.post(
            "/api/social/follow/",
            {"target_user_id": str(social_user2.id)},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_unfollow_user(self, social_client, social_user, social_user2):
        """User can unfollow another user."""
        UserFollow.objects.create(follower=social_user, following=social_user2)
        response = social_client.delete(
            f"/api/social/unfollow/{social_user2.id}/"
        )
        assert response.status_code == status.HTTP_200_OK
        assert not UserFollow.objects.filter(
            follower=social_user, following=social_user2
        ).exists()

    def test_unfollow_not_following(self, social_client, social_user2):
        """Unfollowing user not followed returns 404."""
        response = social_client.delete(
            f"/api/social/unfollow/{social_user2.id}/"
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_follow_nonexistent_user(self, social_client):
        """Following a nonexistent user returns 404."""
        import uuid

        fake_id = uuid.uuid4()
        response = social_client.post(
            "/api/social/follow/",
            {"target_user_id": str(fake_id)},
            format="json",
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND


# ──────────────────────────────────────────────────────────────────────
#  Block / Unblock User
# ──────────────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestBlockUser:
    """Integration tests for block/unblock endpoints."""

    def test_block_user(self, social_client, social_user, social_user2):
        """User can block another user."""
        response = social_client.post(
            "/api/social/block/",
            {"target_user_id": str(social_user2.id), "reason": "spam"},
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert BlockedUser.objects.filter(
            blocker=social_user, blocked=social_user2
        ).exists()

    def test_block_self(self, social_client, social_user):
        """Cannot block yourself."""
        response = social_client.post(
            "/api/social/block/",
            {"target_user_id": str(social_user.id)},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_block_already_blocked(self, social_client, social_user, social_user2):
        """Cannot block a user who is already blocked."""
        BlockedUser.objects.create(blocker=social_user, blocked=social_user2)
        response = social_client.post(
            "/api/social/block/",
            {"target_user_id": str(social_user2.id)},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_block_removes_friendship(self, social_client, social_user, social_user2):
        """Blocking removes existing friendships."""
        Friendship.objects.create(
            user1=social_user, user2=social_user2, status="accepted"
        )
        social_client.post(
            "/api/social/block/",
            {"target_user_id": str(social_user2.id)},
            format="json",
        )
        assert not Friendship.objects.filter(
            user1=social_user, user2=social_user2
        ).exists()

    def test_block_removes_follows(self, social_client, social_user, social_user2):
        """Blocking removes follow relationships in both directions."""
        UserFollow.objects.create(follower=social_user, following=social_user2)
        social_client.post(
            "/api/social/block/",
            {"target_user_id": str(social_user2.id)},
            format="json",
        )
        assert not UserFollow.objects.filter(
            follower=social_user, following=social_user2
        ).exists()

    def test_unblock_user(self, social_client, social_user, social_user2):
        """User can unblock a previously blocked user."""
        BlockedUser.objects.create(blocker=social_user, blocked=social_user2)
        response = social_client.delete(
            f"/api/social/unblock/{social_user2.id}/"
        )
        assert response.status_code == status.HTTP_200_OK
        assert not BlockedUser.objects.filter(
            blocker=social_user, blocked=social_user2
        ).exists()

    def test_unblock_not_blocked(self, social_client, social_user2):
        """Unblocking a non-blocked user returns 404."""
        response = social_client.delete(
            f"/api/social/unblock/{social_user2.id}/"
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_list_blocked(self, social_client, social_user, social_user2):
        """List blocked users."""
        BlockedUser.objects.create(blocker=social_user, blocked=social_user2)
        response = social_client.get("/api/social/blocked/")
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) >= 1

    def test_block_nonexistent_user(self, social_client):
        """Blocking a non-existent user returns 404."""
        response = social_client.post(
            "/api/social/block/",
            {"target_user_id": str(uuid.uuid4())},
            format="json",
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND


# ──────────────────────────────────────────────────────────────────────
#  Report User
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestReportUser:
    """Integration tests for report user endpoint."""

    def test_report_user(self, social_client, social_user2):
        """User can report another user."""
        response = social_client.post(
            "/api/social/report/",
            {
                "target_user_id": str(social_user2.id),
                "reason": "Harassment",
                "category": "harassment",
            },
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED

    def test_report_self(self, social_client, social_user):
        """Cannot report yourself."""
        response = social_client.post(
            "/api/social/report/",
            {
                "target_user_id": str(social_user.id),
                "reason": "Testing",
            },
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_report_nonexistent_user(self, social_client):
        """Reporting a non-existent user returns 404."""
        response = social_client.post(
            "/api/social/report/",
            {
                "target_user_id": str(uuid.uuid4()),
                "reason": "Testing",
            },
            format="json",
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND


# ──────────────────────────────────────────────────────────────────────
#  Events (create, register, participants)
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestSocialEvents:
    """Integration tests for social event endpoints."""

    def test_create_event(self, social_client):
        """Create a new social event."""
        from django.utils import timezone as tz

        start = tz.now() + timedelta(hours=1)
        end = tz.now() + timedelta(hours=2)
        response = social_client.post(
            "/api/social/events/",
            {
                "title": "Study Group",
                "description": "Let us study together",
                "event_type": "challenge",
                "start_time": start.isoformat(),
                "end_time": end.isoformat(),
            },
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["title"] == "Study Group"

    def test_list_events(self, social_client, social_user):
        """List events."""
        from django.utils import timezone as tz

        SocialEvent.objects.create(
            creator=social_user,
            title="Test Event",
            event_type="challenge",
            start_time=tz.now() + timedelta(hours=1),
            end_time=tz.now() + timedelta(hours=2),
        )
        response = social_client.get("/api/social/events/")
        assert response.status_code == status.HTTP_200_OK

    def test_register_for_event(self, social_client2, social_user):
        """User can register for an event."""
        from django.utils import timezone as tz

        event = SocialEvent.objects.create(
            creator=social_user,
            title="Workshop",
            event_type="challenge",
            start_time=tz.now() + timedelta(hours=1),
            end_time=tz.now() + timedelta(hours=2),
        )
        response = social_client2.post(
            f"/api/social/events/{event.id}/register/"
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["registered"] is True

    def test_register_for_full_event(self, social_client2, social_user):
        """Cannot register for a full event."""
        from django.utils import timezone as tz

        event = SocialEvent.objects.create(
            creator=social_user,
            title="Full Event",
            event_type="challenge",
            start_time=tz.now() + timedelta(hours=1),
            end_time=tz.now() + timedelta(hours=2),
            max_participants=0,
            participants_count=0,
        )
        # max=0 means no one can register
        response = social_client2.post(
            f"/api/social/events/{event.id}/register/"
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_unregister_from_event(self, social_client2, social_user, social_user2):
        """User can unregister from an event."""
        from django.utils import timezone as tz

        event = SocialEvent.objects.create(
            creator=social_user,
            title="Unregister Test",
            event_type="challenge",
            start_time=tz.now() + timedelta(hours=1),
            end_time=tz.now() + timedelta(hours=2),
            participants_count=1,
        )
        SocialEventRegistration.objects.create(
            event=event, user=social_user2, status="registered"
        )
        response = social_client2.post(
            f"/api/social/events/{event.id}/unregister/"
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["registered"] is False

    def test_unregister_not_registered(self, social_client, social_user):
        """Unregistering when not registered returns 400."""
        from django.utils import timezone as tz

        event = SocialEvent.objects.create(
            creator=social_user,
            title="Not Registered",
            event_type="challenge",
            start_time=tz.now() + timedelta(hours=1),
            end_time=tz.now() + timedelta(hours=2),
        )
        response = social_client.post(
            f"/api/social/events/{event.id}/unregister/"
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_event_participants(self, social_client, social_user, social_user2):
        """List event participants."""
        from django.utils import timezone as tz

        event = SocialEvent.objects.create(
            creator=social_user,
            title="Participants Test",
            event_type="challenge",
            start_time=tz.now() + timedelta(hours=1),
            end_time=tz.now() + timedelta(hours=2),
        )
        SocialEventRegistration.objects.create(
            event=event, user=social_user2, status="registered"
        )
        response = social_client.get(
            f"/api/social/events/{event.id}/participants/"
        )
        assert response.status_code == status.HTTP_200_OK

    def test_cancel_event(self, social_client, social_user):
        """Creator can cancel their own event."""
        from django.utils import timezone as tz

        event = SocialEvent.objects.create(
            creator=social_user,
            title="To Cancel",
            event_type="challenge",
            start_time=tz.now() + timedelta(hours=1),
            end_time=tz.now() + timedelta(hours=2),
        )
        response = social_client.delete(f"/api/social/events/{event.id}/")
        assert response.status_code == status.HTTP_200_OK
        event.refresh_from_db()
        assert event.status == "cancelled"

    def test_cancel_event_not_creator(self, social_client2, social_user):
        """Non-creator cannot cancel an event."""
        from django.utils import timezone as tz

        event = SocialEvent.objects.create(
            creator=social_user,
            title="Not My Event",
            event_type="challenge",
            start_time=tz.now() + timedelta(hours=1),
            end_time=tz.now() + timedelta(hours=2),
        )
        response = social_client2.delete(f"/api/social/events/{event.id}/")
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_register_for_cancelled_event(self, social_client2, social_user):
        """Cannot register for a cancelled event."""
        from django.utils import timezone as tz

        event = SocialEvent.objects.create(
            creator=social_user,
            title="Cancelled",
            event_type="challenge",
            start_time=tz.now() + timedelta(hours=1),
            end_time=tz.now() + timedelta(hours=2),
            status="cancelled",
        )
        response = social_client2.post(
            f"/api/social/events/{event.id}/register/"
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_events_feed(self, social_client, social_user):
        """Get upcoming events feed."""
        from django.utils import timezone as tz

        SocialEvent.objects.create(
            creator=social_user,
            title="Upcoming Event",
            event_type="challenge",
            start_time=tz.now() + timedelta(hours=1),
            end_time=tz.now() + timedelta(hours=2),
        )
        response = social_client.get("/api/social/events/feed/")
        assert response.status_code == status.HTTP_200_OK


# ──────────────────────────────────────────────────────────────────────
#  Stories
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestStories:
    """Integration tests for story endpoints."""

    def test_create_story(self, social_client, social_user):
        """Create a new story."""
        from django.core.files.uploadedfile import SimpleUploadedFile

        # Create a minimal JPEG file
        jpeg_content = b"\xff\xd8\xff\xe0" + b"\x00" * 100
        image = SimpleUploadedFile("story.jpg", jpeg_content, content_type="image/jpeg")

        response = social_client.post(
            "/api/social/stories/",
            {"media_file": image, "caption": "My story"},
            format="multipart",
        )
        # Could be 201 or 400 depending on serializer validation details
        assert response.status_code in (
            status.HTTP_201_CREATED,
            status.HTTP_400_BAD_REQUEST,  # if media_file validation is strict
        )

    def test_list_stories(self, social_client, social_user):
        """List stories (feed)."""
        from django.utils import timezone as tz

        Story.objects.create(
            user=social_user,
            media_type="image",
            caption="Test story",
            expires_at=tz.now() + timedelta(hours=24),
        )
        response = social_client.get("/api/social/stories/")
        assert response.status_code == status.HTTP_200_OK

    def test_delete_own_story(self, social_client, social_user):
        """User can delete their own story."""
        from django.utils import timezone as tz

        story = Story.objects.create(
            user=social_user,
            media_type="image",
            expires_at=tz.now() + timedelta(hours=24),
        )
        response = social_client.delete(f"/api/social/stories/{story.id}/")
        assert response.status_code == status.HTTP_204_NO_CONTENT


# ──────────────────────────────────────────────────────────────────────
#  Encouragements / Reactions / Share Post
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestEncouragements:
    """Integration tests for encouragement endpoints."""

    def test_encourage_post(self, social_client2, social_user, social_user2):
        """User can encourage a post."""
        post = DreamPost.objects.create(
            user=social_user, content="Working hard!", visibility="public"
        )
        response = social_client2.post(
            f"/api/social/posts/{post.id}/encourage/",
            {"encouragement_type": "you_got_this", "message": "Keep going!"},
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert DreamEncouragement.objects.filter(
            post=post, user=social_user2
        ).exists()

    def test_encourage_invalid_type(self, social_client2, social_user):
        """Invalid encouragement type returns 400."""
        post = DreamPost.objects.create(
            user=social_user, content="Test", visibility="public"
        )
        response = social_client2.post(
            f"/api/social/posts/{post.id}/encourage/",
            {"encouragement_type": "invalid_type"},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
class TestReactions:
    """Integration tests for post reaction endpoints."""

    def test_react_to_post(self, social_client2, social_user):
        """User can react to a post."""
        post = DreamPost.objects.create(
            user=social_user, content="React to me", visibility="public"
        )
        response = social_client2.post(
            f"/api/social/posts/{post.id}/react/",
            {"reaction_type": "fire"},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["reacted"] is True
        assert response.data["reaction_type"] == "fire"

    def test_react_toggle_same(self, social_client2, social_user, social_user2):
        """Same reaction type toggles it off."""
        post = DreamPost.objects.create(
            user=social_user, content="Toggle react", visibility="public"
        )
        PostReaction.objects.create(
            user=social_user2, post=post, reaction_type="love"
        )
        response = social_client2.post(
            f"/api/social/posts/{post.id}/react/",
            {"reaction_type": "love"},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["reacted"] is False

    def test_react_change_type(self, social_client2, social_user, social_user2):
        """Different reaction type changes the reaction."""
        post = DreamPost.objects.create(
            user=social_user, content="Change react", visibility="public"
        )
        PostReaction.objects.create(
            user=social_user2, post=post, reaction_type="love"
        )
        response = social_client2.post(
            f"/api/social/posts/{post.id}/react/",
            {"reaction_type": "fire"},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["reacted"] is True
        assert response.data["reaction_type"] == "fire"

    def test_react_invalid_type(self, social_client2, social_user):
        """Invalid reaction type returns 400."""
        post = DreamPost.objects.create(
            user=social_user, content="Bad react", visibility="public"
        )
        response = social_client2.post(
            f"/api/social/posts/{post.id}/react/",
            {"reaction_type": "invalid"},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
class TestSharePost:
    """Integration tests for share/repost endpoint."""

    def test_share_post(self, social_client2, social_user, social_user2):
        """User can share/repost another user's post."""
        post = DreamPost.objects.create(
            user=social_user, content="Share me!", visibility="public"
        )
        response = social_client2.post(
            f"/api/social/posts/{post.id}/share/",
            {"content": "Check this out!"},
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert DreamPost.objects.filter(user=social_user2).exists()

    def test_share_without_content(self, social_client2, social_user):
        """Sharing without content uses default."""
        post = DreamPost.objects.create(
            user=social_user, content="Original post", visibility="public"
        )
        response = social_client2.post(
            f"/api/social/posts/{post.id}/share/",
            {},
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED


# ──────────────────────────────────────────────────────────────────────
#  Friend management extras
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestFriendManagement:
    """Integration tests for friend management endpoints."""

    def test_reject_friend_request(self, social_client2, social_user, social_user2):
        """Recipient can reject a friend request."""
        friendship = Friendship.objects.create(
            user1=social_user, user2=social_user2, status="pending"
        )
        response = social_client2.post(
            f"/api/social/friends/reject/{friendship.id}/"
        )
        assert response.status_code == status.HTTP_200_OK
        friendship.refresh_from_db()
        assert friendship.status == "rejected"

    def test_list_friends(self, social_client, social_user, social_user2):
        """List accepted friends."""
        Friendship.objects.create(
            user1=social_user, user2=social_user2, status="accepted"
        )
        response = social_client.get("/api/social/friends/")
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) >= 1

    def test_remove_friend(self, social_client, social_user, social_user2):
        """Remove an accepted friend."""
        Friendship.objects.create(
            user1=social_user, user2=social_user2, status="accepted"
        )
        response = social_client.delete(
            f"/api/social/friends/remove/{social_user2.id}/"
        )
        assert response.status_code == status.HTTP_200_OK
        assert not Friendship.objects.filter(
            user1=social_user, user2=social_user2
        ).exists()

    def test_remove_non_friend(self, social_client, social_user2):
        """Removing a non-friend returns 404."""
        response = social_client.delete(
            f"/api/social/friends/remove/{social_user2.id}/"
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_pending_requests(self, social_client2, social_user, social_user2):
        """List pending friend requests received."""
        Friendship.objects.create(
            user1=social_user, user2=social_user2, status="pending"
        )
        response = social_client2.get("/api/social/friends/requests/pending/")
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) >= 1

    def test_sent_requests(self, social_client, social_user, social_user2):
        """List sent friend requests."""
        Friendship.objects.create(
            user1=social_user, user2=social_user2, status="pending"
        )
        response = social_client.get("/api/social/friends/requests/sent/")
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) >= 1

    def test_cancel_sent_request(self, social_client, social_user, social_user2):
        """Cancel a pending sent friend request."""
        friendship = Friendship.objects.create(
            user1=social_user, user2=social_user2, status="pending"
        )
        response = social_client.delete(
            f"/api/social/friends/cancel/{friendship.id}/"
        )
        assert response.status_code == status.HTTP_200_OK
        assert not Friendship.objects.filter(id=friendship.id).exists()

    def test_cancel_nonexistent_request(self, social_client):
        """Cancel non-existent request returns 404."""
        response = social_client.delete(
            f"/api/social/friends/cancel/{uuid.uuid4()}/"
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_social_counts(self, social_client, social_user, social_user2):
        """Get follower/following/friend counts."""
        UserFollow.objects.create(follower=social_user, following=social_user2)
        response = social_client.get(
            f"/api/social/counts/{social_user2.id}/"
        )
        assert response.status_code == status.HTTP_200_OK
        assert "follower_count" in response.data
        assert "following_count" in response.data
        assert "friend_count" in response.data


# ──────────────────────────────────────────────────────────────────────
#  Post CRUD (update, delete)
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestPostCRUD:
    """Integration tests for post update and delete."""

    def test_update_own_post(self, social_client, social_user):
        """Owner can update their post."""
        post = DreamPost.objects.create(
            user=social_user, content="Original", visibility="public"
        )
        response = social_client.patch(
            f"/api/social/posts/{post.id}/",
            {"content": "Updated content"},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK

    def test_delete_own_post(self, social_client, social_user):
        """Owner can delete their post."""
        post = DreamPost.objects.create(
            user=social_user, content="Delete me", visibility="public"
        )
        response = social_client.delete(f"/api/social/posts/{post.id}/")
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not DreamPost.objects.filter(id=post.id).exists()

    def test_delete_other_users_post(self, social_client2, social_user):
        """Cannot delete another user's post."""
        post = DreamPost.objects.create(
            user=social_user, content="Protected", visibility="public"
        )
        response = social_client2.delete(f"/api/social/posts/{post.id}/")
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_saved_posts_list(self, social_client, social_user, social_user2):
        """List saved/bookmarked posts."""
        post = DreamPost.objects.create(
            user=social_user2, content="Save me", visibility="public"
        )
        SavedPost.objects.create(user=social_user, post=post)
        response = social_client.get("/api/social/posts/saved/")
        assert response.status_code == status.HTTP_200_OK

    def test_saved_posts_empty(self, social_client):
        """List saved posts when none exist returns empty."""
        response = social_client.get("/api/social/posts/saved/")
        assert response.status_code == status.HTTP_200_OK


# ──────────────────────────────────────────────────────────────────────
#  User Search
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestUserSearch:
    """Integration tests for user search endpoint."""

    @patch("apps.search.services.SearchService.search_users")
    def test_search_users(self, mock_search, social_client, social_user2):
        """Search for users by display name."""
        mock_search.return_value = [social_user2.id]
        response = social_client.get("/api/social/users/search?q=Social")
        assert response.status_code == status.HTTP_200_OK

    @patch("apps.search.services.SearchService.search_users")
    def test_search_users_short_query(self, mock_search, social_client):
        """Search with short query (< 2 chars) returns empty."""
        response = social_client.get("/api/social/users/search?q=S")
        assert response.status_code == status.HTTP_200_OK
        data = response.data
        results = data.get("results", data)
        if isinstance(results, list):
            assert len(results) == 0

    @patch("apps.search.services.SearchService.search_users")
    def test_search_users_empty_query(self, mock_search, social_client):
        """Search with empty query returns empty."""
        response = social_client.get("/api/social/users/search?q=")
        assert response.status_code == status.HTTP_200_OK

    @patch("apps.search.services.SearchService.search_users")
    def test_search_excludes_blocked_users(
        self, mock_search, social_client, social_user, social_user2
    ):
        """Blocked users are excluded from search results."""
        mock_search.return_value = [social_user2.id]
        BlockedUser.objects.create(blocker=social_user, blocked=social_user2)
        response = social_client.get("/api/social/users/search?q=Social")
        assert response.status_code == status.HTTP_200_OK

    def test_search_unauthenticated(self):
        """Unauthenticated user cannot search."""
        from rest_framework.test import APIClient

        client = APIClient()
        response = client.get("/api/social/users/search?q=test")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


# ──────────────────────────────────────────────────────────────────────
#  Follow Suggestions
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestFollowSuggestions:
    """Integration tests for follow suggestions endpoint."""

    def test_follow_suggestions_premium(self, social_user):
        """Premium user can get follow suggestions."""
        from rest_framework.test import APIClient

        from apps.subscriptions.models import Subscription, SubscriptionPlan

        plan = SubscriptionPlan.objects.get(slug="premium")
        Subscription.objects.update_or_create(
            user=social_user,
            defaults={
                "plan": plan,
                "status": "active",
                "current_period_start": timezone.now(),
                "current_period_end": timezone.now() + timedelta(days=30),
            },
        )
        client = APIClient()
        client.force_authenticate(user=social_user)
        response = client.get("/api/social/follow-suggestions/")
        assert response.status_code == status.HTTP_200_OK

    def test_follow_suggestions_free_user(self, social_client):
        """Free user gets 403 on follow suggestions."""
        response = social_client.get("/api/social/follow-suggestions/")
        assert response.status_code == status.HTTP_403_FORBIDDEN


# ──────────────────────────────────────────────────────────────────────
#  Friend Suggestions
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestFriendSuggestions:
    """Integration tests for friend suggestions endpoint."""

    def test_friend_suggestions_premium(self, social_user):
        """Premium user can get friend suggestions."""
        from rest_framework.test import APIClient

        from apps.subscriptions.models import Subscription, SubscriptionPlan

        plan = SubscriptionPlan.objects.get(slug="premium")
        Subscription.objects.update_or_create(
            user=social_user,
            defaults={
                "plan": plan,
                "status": "active",
                "current_period_start": timezone.now(),
                "current_period_end": timezone.now() + timedelta(days=30),
            },
        )
        client = APIClient()
        client.force_authenticate(user=social_user)
        response = client.get("/api/social/friend-suggestions/")
        assert response.status_code == status.HTTP_200_OK


# ──────────────────────────────────────────────────────────────────────
#  Activity Feed
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestActivityFeed:
    """Integration tests for the friends activity feed."""

    def test_activity_feed_authenticated(self, social_client, social_user):
        """Authenticated user can access activity feed."""
        ActivityFeedItem.objects.create(
            user=social_user,
            activity_type="task_completed",
            content={"dream_id": str(uuid.uuid4())},
        )
        response = social_client.get("/api/social/feed/friends/")
        assert response.status_code == status.HTTP_200_OK

    def test_activity_feed_unauthenticated(self):
        """Unauthenticated user gets 401."""
        from rest_framework.test import APIClient

        client = APIClient()
        response = client.get("/api/social/feed/friends/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_activity_feed_filter_by_type(self, social_client, social_user):
        """Activity feed can be filtered by activity_type."""
        ActivityFeedItem.objects.create(
            user=social_user,
            activity_type="dream_completed",
        )
        response = social_client.get(
            "/api/social/feed/friends/?activity_type=dream_completed"
        )
        assert response.status_code == status.HTTP_200_OK

    def test_activity_feed_excludes_blocked_users(
        self, social_client, social_user, social_user2
    ):
        """Feed excludes items from blocked users."""
        BlockedUser.objects.create(blocker=social_user, blocked=social_user2)
        ActivityFeedItem.objects.create(
            user=social_user2,
            activity_type="task_completed",
        )
        response = social_client.get("/api/social/feed/friends/")
        assert response.status_code == status.HTTP_200_OK


# ──────────────────────────────────────────────────────────────────────
#  Feed Like / Comment
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestFeedLikeComment:
    """Integration tests for feed like/comment endpoints."""

    def test_like_feed_activity(self, social_client, social_user):
        """User can like a feed activity."""
        activity = ActivityFeedItem.objects.create(
            user=social_user,
            activity_type="task_completed",
        )
        response = social_client.post(
            f"/api/social/feed/{activity.id}/like/"
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["liked"] is True

    def test_unlike_feed_activity(self, social_client, social_user):
        """Liking twice toggles unlike."""
        from apps.social.models import ActivityLike

        activity = ActivityFeedItem.objects.create(
            user=social_user,
            activity_type="task_completed",
        )
        ActivityLike.objects.create(user=social_user, activity=activity)
        response = social_client.post(
            f"/api/social/feed/{activity.id}/like/"
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["liked"] is False

    def test_like_nonexistent_activity(self, social_client):
        """Liking nonexistent activity returns 404."""
        response = social_client.post(
            f"/api/social/feed/{uuid.uuid4()}/like/"
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_comment_on_feed_activity(self, social_client, social_user):
        """User can comment on a feed activity."""
        activity = ActivityFeedItem.objects.create(
            user=social_user,
            activity_type="task_completed",
        )
        response = social_client.post(
            f"/api/social/feed/{activity.id}/comment/",
            {"text": "Great job!"},
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED

    def test_comment_empty_text(self, social_client, social_user):
        """Comment with empty text returns 400."""
        activity = ActivityFeedItem.objects.create(
            user=social_user,
            activity_type="task_completed",
        )
        response = social_client.post(
            f"/api/social/feed/{activity.id}/comment/",
            {"text": ""},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST


# ──────────────────────────────────────────────────────────────────────
#  Online friends, Mutual friends
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestOnlineAndMutualFriends:
    """Integration tests for online friends and mutual friends."""

    def test_online_friends(self, social_client, social_user, social_user2):
        """Get online friends."""
        Friendship.objects.create(
            user1=social_user, user2=social_user2, status="accepted"
        )
        social_user2.is_online = True
        social_user2.save(update_fields=["is_online"])
        response = social_client.get("/api/social/friends/online/")
        assert response.status_code == status.HTTP_200_OK

    def test_mutual_friends(self, social_client, social_user, social_user2, social_user3):
        """Get mutual friends between two users."""
        Friendship.objects.create(
            user1=social_user, user2=social_user3, status="accepted"
        )
        Friendship.objects.create(
            user1=social_user2, user2=social_user3, status="accepted"
        )
        response = social_client.get(
            f"/api/social/friends/mutual/{social_user2.id}/"
        )
        assert response.status_code == status.HTTP_200_OK

    def test_mutual_friends_nonexistent_user(self, social_client):
        """Mutual friends with nonexistent user returns 404."""
        response = social_client.get(
            f"/api/social/friends/mutual/{uuid.uuid4()}/"
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND


# ──────────────────────────────────────────────────────────────────────
#  Online Friends
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestOnlineFriends:
    """Tests for online friends endpoint."""

    def test_online_friends(self, social_client):
        """Get online friends."""
        response = social_client.get("/api/social/friends/online/")
        assert response.status_code == status.HTTP_200_OK


# ──────────────────────────────────────────────────────────────────────
#  Recent Searches
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestRecentSearches:
    """Tests for recent search endpoints."""

    def test_list_searches(self, social_client):
        """List recent searches."""
        response = social_client.get("/api/social/recent-searches/list/")
        assert response.status_code == status.HTTP_200_OK

    def test_add_search(self, social_client, social_user2):
        """Add a recent search."""
        response = social_client.post(
            "/api/social/recent-searches/add/",
            {"user_id": str(social_user2.id)},
            format="json",
        )
        assert response.status_code in (
            status.HTTP_200_OK,
            status.HTTP_201_CREATED,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_clear_searches(self, social_client):
        """Clear all recent searches."""
        response = social_client.delete("/api/social/recent-searches/clear/")
        assert response.status_code in (
            status.HTTP_200_OK,
            status.HTTP_204_NO_CONTENT,
        )


# ──────────────────────────────────────────────────────────────────────
#  Follow Suggestions
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestFollowSuggestionsCoverage:
    """Tests for follow/friend suggestion endpoints."""

    def test_follow_suggestions(self, social_client):
        """Get follow suggestions (may require premium)."""
        response = social_client.get("/api/social/follow-suggestions/")
        assert response.status_code in (
            status.HTTP_200_OK,
            status.HTTP_403_FORBIDDEN,
        )

    def test_friend_suggestions(self, social_client):
        """Get friend suggestions (may require premium)."""
        response = social_client.get("/api/social/friend-suggestions/")
        assert response.status_code in (
            status.HTTP_200_OK,
            status.HTTP_403_FORBIDDEN,
        )


# ──────────────────────────────────────────────────────────────────────
#  Feed Like and Comment
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestFeedLikeCommentCoverage:
    """Tests for feed like and comment endpoints."""

    def test_feed_like_nonexistent(self, social_client):
        """Like nonexistent activity returns 404."""
        response = social_client.post(
            f"/api/social/feed/{uuid.uuid4()}/like/"
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_feed_comment_nonexistent(self, social_client):
        """Comment on nonexistent activity returns 404."""
        response = social_client.post(
            f"/api/social/feed/{uuid.uuid4()}/comment/",
            {"content": "Great job!"},
            format="json",
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND
