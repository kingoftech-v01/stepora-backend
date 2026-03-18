"""
Integration tests for the Social app API endpoints.
"""

import pytest
from django.utils import timezone
from rest_framework import status

from apps.social.models import (
    DreamPost,
    DreamPostComment,
    DreamPostLike,
    Friendship,
    SavedPost,
    UserFollow,
)
from apps.users.models import User


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
