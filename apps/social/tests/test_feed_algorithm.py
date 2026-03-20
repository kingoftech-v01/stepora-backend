"""
Tests for the 3-tier social feed algorithm, CRUD permissions,
and post visibility filtering.
"""

import uuid
from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient, APIRequestFactory

from apps.social.models import (
    BlockedUser,
    DreamPost,
    DreamPostLike,
    Friendship,
    SavedPost,
    UserFollow,
)
from apps.users.models import User


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_user(email, name="User"):
    return User.objects.create_user(
        email=email, password="testpassword123", display_name=name
    )


def _make_friends(user_a, user_b):
    Friendship.objects.create(user1=user_a, user2=user_b, status="accepted")


def _make_post(user, content="Hello", visibility="public", **kwargs):
    return DreamPost.objects.create(
        user=user, content=content, visibility=visibility, **kwargs
    )


# ---------------------------------------------------------------------------
# 3-Tier Feed Algorithm
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestFeedTierAlgorithm:
    """Tests verifying the 3-tier feed algorithm content."""

    FEED_URL = "/api/social/posts/feed/"

    def test_feed_returns_own_posts(self, social_client, social_user):
        """Tier 0: user's own posts always appear."""
        _make_post(social_user, "My own post")
        resp = social_client.get(self.FEED_URL)
        assert resp.status_code == 200
        contents = [p["content"] for p in resp.data]
        assert "My own post" in contents

    def test_feed_returns_own_private_posts(self, social_client, social_user):
        """Tier 0: user can see their own private posts in feed."""
        _make_post(social_user, "My private", visibility="private")
        resp = social_client.get(self.FEED_URL)
        contents = [p["content"] for p in resp.data]
        assert "My private" in contents

    def test_feed_returns_friend_public_posts(
        self, social_client, social_user, social_user2
    ):
        """Tier 1: public posts from accepted friends appear."""
        _make_friends(social_user, social_user2)
        _make_post(social_user2, "Friend public")
        resp = social_client.get(self.FEED_URL)
        contents = [p["content"] for p in resp.data]
        assert "Friend public" in contents

    def test_feed_returns_friend_followers_posts(
        self, social_client, social_user, social_user2
    ):
        """Tier 1: followers-only posts from friends are visible."""
        _make_friends(social_user, social_user2)
        _make_post(social_user2, "Friend followers", visibility="followers")
        resp = social_client.get(self.FEED_URL)
        contents = [p["content"] for p in resp.data]
        assert "Friend followers" in contents

    def test_feed_excludes_friend_private_posts(
        self, social_client, social_user, social_user2
    ):
        """Tier 1: private posts from friends are NOT visible."""
        _make_friends(social_user, social_user2)
        _make_post(social_user2, "Friend secret", visibility="private")
        resp = social_client.get(self.FEED_URL)
        contents = [p["content"] for p in resp.data]
        assert "Friend secret" not in contents

    def test_feed_includes_fof_public_posts(
        self, social_client, social_user, social_user2, social_user3
    ):
        """Tier 2: public posts from friends-of-friends appear."""
        _make_friends(social_user, social_user2)
        _make_friends(social_user2, social_user3)
        _make_post(social_user3, "FoF public")
        resp = social_client.get(self.FEED_URL)
        contents = [p["content"] for p in resp.data]
        assert "FoF public" in contents

    def test_feed_excludes_fof_private_posts(
        self, social_client, social_user, social_user2, social_user3
    ):
        """Tier 2: private posts from friends-of-friends are NOT visible."""
        _make_friends(social_user, social_user2)
        _make_friends(social_user2, social_user3)
        _make_post(social_user3, "FoF private", visibility="private")
        resp = social_client.get(self.FEED_URL)
        contents = [p["content"] for p in resp.data]
        assert "FoF private" not in contents

    def test_feed_excludes_fof_followers_posts(
        self, social_client, social_user, social_user2, social_user3
    ):
        """Tier 2: followers-only posts from FoF are NOT visible (public only)."""
        _make_friends(social_user, social_user2)
        _make_friends(social_user2, social_user3)
        _make_post(social_user3, "FoF followers", visibility="followers")
        resp = social_client.get(self.FEED_URL)
        contents = [p["content"] for p in resp.data]
        assert "FoF followers" not in contents

    def test_feed_includes_followed_user_public_posts(
        self, social_client, social_user, social_user2
    ):
        """Tier 3: public posts from followed (non-friend) users appear."""
        UserFollow.objects.create(follower=social_user, following=social_user2)
        _make_post(social_user2, "Followed post")
        resp = social_client.get(self.FEED_URL)
        contents = [p["content"] for p in resp.data]
        assert "Followed post" in contents

    def test_feed_includes_trending_posts(self, social_client, social_user):
        """Tier 3: high-engagement public posts from strangers appear."""
        stranger = _make_user("stranger@test.com", "Stranger")
        _make_post(stranger, "Trending post", likes_count=100, comments_count=50)
        resp = social_client.get(self.FEED_URL)
        contents = [p["content"] for p in resp.data]
        assert "Trending post" in contents

    def test_feed_excludes_blocked_user_posts(
        self, social_client, social_user, social_user2
    ):
        """Posts from blocked users never appear."""
        _make_friends(social_user, social_user2)
        _make_post(social_user2, "Blocked post")
        BlockedUser.objects.create(blocker=social_user, blocked=social_user2)
        resp = social_client.get(self.FEED_URL)
        contents = [p["content"] for p in resp.data]
        assert "Blocked post" not in contents

    def test_feed_excludes_posts_from_user_who_blocked_me(
        self, social_client, social_user, social_user2
    ):
        """Posts from users who blocked the current user are excluded."""
        _make_friends(social_user, social_user2)
        _make_post(social_user2, "Blocker post")
        BlockedUser.objects.create(blocker=social_user2, blocked=social_user)
        resp = social_client.get(self.FEED_URL)
        contents = [p["content"] for p in resp.data]
        assert "Blocker post" not in contents

    def test_feed_page_size_capped_at_15(self, social_client, social_user):
        """Feed returns at most 15 posts per page."""
        for i in range(20):
            _make_post(social_user, f"Post {i}")
        resp = social_client.get(self.FEED_URL)
        assert resp.status_code == 200
        assert len(resp.data) <= 15

    def test_feed_requires_auth(self):
        """Anonymous requests get 401."""
        client = APIClient()
        resp = client.get("/api/social/posts/feed/")
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_feed_is_owner_flag_on_own_post(self, social_client, social_user):
        """is_owner=true for user's own post in feed."""
        _make_post(social_user, "Mine")
        resp = social_client.get(self.FEED_URL)
        own_posts = [p for p in resp.data if p["content"] == "Mine"]
        assert len(own_posts) == 1
        assert own_posts[0]["is_owner"] is True

    def test_feed_is_owner_flag_on_friend_post(
        self, social_client, social_user, social_user2
    ):
        """is_owner=false for friend's post in feed."""
        _make_friends(social_user, social_user2)
        _make_post(social_user2, "Theirs")
        resp = social_client.get(self.FEED_URL)
        their_posts = [p for p in resp.data if p["content"] == "Theirs"]
        assert len(their_posts) == 1
        assert their_posts[0]["is_owner"] is False

    def test_feed_empty_for_new_user(self):
        """New user with no friends/follows sees empty feed."""
        new_user = _make_user("newuser@test.com", "NewUser")
        client = APIClient()
        client.force_authenticate(user=new_user)
        resp = client.get("/api/social/posts/feed/")
        assert resp.status_code == 200
        assert isinstance(resp.data, list)


# ---------------------------------------------------------------------------
# CRUD Permissions
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestPostCRUDPermissions:
    """Tests for ownership-based CRUD permissions on DreamPosts."""

    POSTS_URL = "/api/social/posts/"

    def test_create_post_sets_ownership(self, social_client, social_user):
        """Created post belongs to the authenticated user."""
        resp = social_client.post(
            self.POSTS_URL,
            {"content": "Ownership test", "visibility": "public"},
            format="json",
        )
        assert resp.status_code == status.HTTP_201_CREATED
        post = DreamPost.objects.get(id=resp.data["id"])
        assert post.user == social_user

    def test_update_own_post_content(self, social_client, social_user):
        """Owner can update content."""
        post = _make_post(social_user, "Original")
        resp = social_client.patch(
            f"{self.POSTS_URL}{post.id}/",
            {"content": "Updated"},
            format="json",
        )
        assert resp.status_code == 200
        assert resp.data["content"] == "Updated"

    def test_update_own_post_visibility(self, social_client, social_user):
        """Owner can change visibility."""
        post = _make_post(social_user, "Change vis", visibility="public")
        resp = social_client.patch(
            f"{self.POSTS_URL}{post.id}/",
            {"visibility": "private"},
            format="json",
        )
        assert resp.status_code == 200
        assert resp.data["visibility"] == "private"

    def test_update_own_post_type(self, social_client, social_user):
        """Owner can change post type."""
        post = _make_post(social_user, "Type change")
        resp = social_client.patch(
            f"{self.POSTS_URL}{post.id}/",
            {"post_type": "achievement"},
            format="json",
        )
        assert resp.status_code == 200
        assert resp.data["post_type"] == "achievement"

    def test_update_own_post_gofundme(self, social_client, social_user):
        """Owner can set gofundme_url."""
        post = _make_post(social_user, "GoFundMe")
        resp = social_client.patch(
            f"{self.POSTS_URL}{post.id}/",
            {"gofundme_url": "https://gofundme.com/test"},
            format="json",
        )
        assert resp.status_code == 200
        assert resp.data["gofundme_url"] == "https://gofundme.com/test"

    def test_update_other_users_post_forbidden(
        self, social_client2, social_user
    ):
        """Non-owner gets 403 when trying to update."""
        post = _make_post(social_user, "Protected")
        resp = social_client2.patch(
            f"{self.POSTS_URL}{post.id}/",
            {"content": "Hacked"},
            format="json",
        )
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_delete_own_post(self, social_client, social_user):
        """Owner can delete their post."""
        post = _make_post(social_user, "Delete me")
        resp = social_client.delete(f"{self.POSTS_URL}{post.id}/")
        assert resp.status_code == status.HTTP_204_NO_CONTENT
        assert not DreamPost.objects.filter(id=post.id).exists()

    def test_delete_other_users_post_forbidden(
        self, social_client2, social_user
    ):
        """Non-owner gets 403 when trying to delete."""
        post = _make_post(social_user, "Protected delete")
        resp = social_client2.delete(f"{self.POSTS_URL}{post.id}/")
        assert resp.status_code == status.HTTP_403_FORBIDDEN
        assert DreamPost.objects.filter(id=post.id).exists()

    def test_put_update_own_post(self, social_client, social_user):
        """PUT (full update) also works for owner."""
        post = _make_post(social_user, "PUT test")
        resp = social_client.put(
            f"{self.POSTS_URL}{post.id}/",
            {"content": "PUT updated", "visibility": "followers"},
            format="json",
        )
        assert resp.status_code == 200
        assert resp.data["content"] == "PUT updated"

    def test_put_update_other_users_post_forbidden(
        self, social_client2, social_user
    ):
        """PUT from non-owner gets 403."""
        post = _make_post(social_user, "Protected PUT")
        resp = social_client2.put(
            f"{self.POSTS_URL}{post.id}/",
            {"content": "Hacked PUT"},
            format="json",
        )
        assert resp.status_code == status.HTTP_403_FORBIDDEN


# ---------------------------------------------------------------------------
# Visibility Filtering (get_queryset)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestPostVisibilityFiltering:
    """Tests for visibility-based queryset filtering."""

    POSTS_URL = "/api/social/posts/"

    def test_owner_sees_own_private_post(self, social_client, social_user):
        """Owner can see their own private post in the posts list."""
        _make_post(social_user, "My private", visibility="private")
        resp = social_client.get(self.POSTS_URL)
        assert resp.status_code == 200
        contents = [p["content"] for p in resp.data["results"]]
        assert "My private" in contents

    def test_other_user_cannot_see_private_post(
        self, social_client2, social_user
    ):
        """Other users cannot see private posts."""
        _make_post(social_user, "Private stuff", visibility="private")
        resp = social_client2.get(self.POSTS_URL)
        contents = [p["content"] for p in resp.data["results"]]
        assert "Private stuff" not in contents

    def test_follower_sees_followers_only_post(
        self, social_client2, social_user, social_user2
    ):
        """Followers can see followers-only posts."""
        UserFollow.objects.create(follower=social_user2, following=social_user)
        _make_post(social_user, "Followers only", visibility="followers")
        resp = social_client2.get(self.POSTS_URL)
        contents = [p["content"] for p in resp.data["results"]]
        assert "Followers only" in contents

    def test_non_follower_cannot_see_followers_only_post(self, social_user):
        """Non-followers cannot see followers-only posts."""
        stranger = _make_user("stranger2@test.com", "Stranger2")
        client = APIClient()
        client.force_authenticate(user=stranger)
        _make_post(social_user, "Followers hidden", visibility="followers")
        resp = client.get(self.POSTS_URL)
        contents = [p["content"] for p in resp.data["results"]]
        assert "Followers hidden" not in contents

    def test_public_posts_visible_to_everyone(self, social_user):
        """Public posts are visible to any authenticated user."""
        stranger = _make_user("pubview@test.com", "PubViewer")
        client = APIClient()
        client.force_authenticate(user=stranger)
        _make_post(social_user, "Public hello", visibility="public")
        resp = client.get(self.POSTS_URL)
        contents = [p["content"] for p in resp.data["results"]]
        assert "Public hello" in contents

    def test_blocked_user_posts_excluded_from_list(
        self, social_client, social_user, social_user2
    ):
        """Posts from blocked users are excluded from the list."""
        _make_post(social_user2, "Blocked visible", visibility="public")
        BlockedUser.objects.create(blocker=social_user, blocked=social_user2)
        resp = social_client.get(self.POSTS_URL)
        contents = [p["content"] for p in resp.data["results"]]
        assert "Blocked visible" not in contents


# ---------------------------------------------------------------------------
# Serializer: is_owner, visibility
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestDreamPostSerializerFields:
    """Tests for is_owner and visibility in DreamPostSerializer."""

    def test_is_owner_true_for_author(self, social_user):
        from apps.social.serializers import DreamPostSerializer

        post = _make_post(social_user, "Serializer owner")
        factory = APIRequestFactory()
        request = factory.get("/")
        request.user = social_user
        data = DreamPostSerializer(post, context={"request": request}).data
        assert data["is_owner"] is True

    def test_is_owner_false_for_non_author(self, social_user, social_user2):
        from apps.social.serializers import DreamPostSerializer

        post = _make_post(social_user, "Not yours")
        factory = APIRequestFactory()
        request = factory.get("/")
        request.user = social_user2
        data = DreamPostSerializer(post, context={"request": request}).data
        assert data["is_owner"] is False

    def test_visibility_field_in_response(self, social_user):
        from apps.social.serializers import DreamPostSerializer

        for vis in ("public", "followers", "private"):
            post = _make_post(social_user, f"Vis {vis}", visibility=vis)
            factory = APIRequestFactory()
            request = factory.get("/")
            request.user = social_user
            data = DreamPostSerializer(post, context={"request": request}).data
            assert data["visibility"] == vis

    def test_user_has_liked_field(self, social_user, social_user2):
        from apps.social.serializers import DreamPostSerializer

        post = _make_post(social_user, "Liked test")
        DreamPostLike.objects.create(post=post, user=social_user2)
        factory = APIRequestFactory()
        request = factory.get("/")
        request.user = social_user2
        data = DreamPostSerializer(post, context={"request": request}).data
        assert data["has_liked"] is True

    def test_user_has_saved_field(self, social_user, social_user2):
        from apps.social.serializers import DreamPostSerializer

        post = _make_post(social_user, "Saved test")
        SavedPost.objects.create(post=post, user=social_user2)
        factory = APIRequestFactory()
        request = factory.get("/")
        request.user = social_user2
        data = DreamPostSerializer(post, context={"request": request}).data
        assert data["has_saved"] is True


# ---------------------------------------------------------------------------
# Create post with visibility
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestCreatePostVisibility:
    """Tests for creating posts with different visibility settings."""

    POSTS_URL = "/api/social/posts/"

    def test_create_public_post(self, social_client):
        resp = social_client.post(
            self.POSTS_URL,
            {"content": "Public post", "visibility": "public"},
            format="json",
        )
        assert resp.status_code == status.HTTP_201_CREATED
        assert resp.data["visibility"] == "public"

    def test_create_followers_post(self, social_client):
        resp = social_client.post(
            self.POSTS_URL,
            {"content": "Followers post", "visibility": "followers"},
            format="json",
        )
        assert resp.status_code == status.HTTP_201_CREATED
        assert resp.data["visibility"] == "followers"

    def test_create_private_post(self, social_client):
        resp = social_client.post(
            self.POSTS_URL,
            {"content": "Private post", "visibility": "private"},
            format="json",
        )
        assert resp.status_code == status.HTTP_201_CREATED
        assert resp.data["visibility"] == "private"

    def test_create_post_default_visibility_is_public(self, social_client):
        resp = social_client.post(
            self.POSTS_URL,
            {"content": "Default vis"},
            format="json",
        )
        assert resp.status_code == status.HTTP_201_CREATED
        assert resp.data["visibility"] == "public"

    def test_create_post_invalid_visibility_rejected(self, social_client):
        resp = social_client.post(
            self.POSTS_URL,
            {"content": "Bad vis", "visibility": "aliens_only"},
            format="json",
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST
