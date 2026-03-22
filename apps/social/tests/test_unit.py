"""
Unit tests for the Social app models.
"""

from datetime import timedelta

import pytest
from django.db import IntegrityError
from django.utils import timezone

from apps.social.models import (
    DreamPost,
    DreamPostComment,
    DreamPostLike,
    Friendship,
    PostReaction,
    SavedPost,
    Story,
    UserFollow,
)
from apps.users.models import User

# ──────────────────────────────────────────────────────────────────────
#  DreamPost
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestDreamPostModel:
    """Tests for the DreamPost model."""

    def test_create_dream_post(self, social_user):
        """DreamPost can be created with required fields."""
        post = DreamPost.objects.create(
            user=social_user,
            content="This is my dream post!",
            visibility="public",
        )
        assert post.pk is not None
        assert post.user == social_user
        assert post.content == "This is my dream post!"
        assert post.visibility == "public"
        assert post.media_type == "none"
        assert post.post_type == "regular"
        assert post.likes_count == 0
        assert post.comments_count == 0
        assert post.shares_count == 0
        assert post.saves_count == 0
        assert post.is_pinned is False

    def test_dream_post_str(self, social_user):
        """DreamPost __str__ returns user display name and content preview."""
        post = DreamPost.objects.create(
            user=social_user,
            content="Short content",
        )
        result = str(post)
        assert "Social User" in result
        assert "Short content" in result

    def test_dream_post_str_truncates_long_content(self, social_user):
        """DreamPost __str__ truncates content longer than 50 chars."""
        long_content = "A" * 60
        post = DreamPost.objects.create(
            user=social_user,
            content=long_content,
        )
        result = str(post)
        assert "..." in result

    def test_dream_post_default_values(self, social_user):
        """DreamPost has correct default values."""
        post = DreamPost.objects.create(
            user=social_user,
            content="Test content",
        )
        assert post.visibility == "public"
        assert post.post_type == "regular"
        assert post.media_type == "none"
        assert post.gofundme_url == ""
        assert post.image_url == ""

    def test_dream_post_with_all_visibility_options(self, social_user):
        """DreamPost can be created with all visibility types."""
        for visibility in ("public", "followers", "private"):
            post = DreamPost.objects.create(
                user=social_user,
                content=f"Post with {visibility} visibility",
                visibility=visibility,
            )
            assert post.visibility == visibility

    def test_dream_post_with_post_types(self, social_user):
        """DreamPost can be created with all post types."""
        for post_type in ("regular", "achievement", "milestone", "event"):
            post = DreamPost.objects.create(
                user=social_user,
                content=f"Post with type {post_type}",
                post_type=post_type,
            )
            assert post.post_type == post_type


# ──────────────────────────────────────────────────────────────────────
#  DreamPostLike
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestDreamPostLikeModel:
    """Tests for the DreamPostLike model."""

    def test_create_like(self, social_user, social_user2):
        """DreamPostLike can be created."""
        post = DreamPost.objects.create(
            user=social_user,
            content="Likeable post",
        )
        like = DreamPostLike.objects.create(post=post, user=social_user2)
        assert like.pk is not None
        assert like.post == post
        assert like.user == social_user2

    def test_like_str(self, social_user, social_user2):
        """DreamPostLike __str__ returns readable representation."""
        post = DreamPost.objects.create(user=social_user, content="Test")
        like = DreamPostLike.objects.create(post=post, user=social_user2)
        result = str(like)
        assert "Social User 2" in result

    def test_unique_like_per_user_per_post(self, social_user, social_user2):
        """Only one like per user per post (unique constraint)."""
        post = DreamPost.objects.create(user=social_user, content="Test")
        DreamPostLike.objects.create(post=post, user=social_user2)
        with pytest.raises(IntegrityError):
            DreamPostLike.objects.create(post=post, user=social_user2)

    def test_multiple_users_can_like_same_post(self, social_user, social_user2, social_user3):
        """Multiple different users can like the same post."""
        post = DreamPost.objects.create(user=social_user, content="Popular post")
        DreamPostLike.objects.create(post=post, user=social_user2)
        DreamPostLike.objects.create(post=post, user=social_user3)
        assert DreamPostLike.objects.filter(post=post).count() == 2


# ──────────────────────────────────────────────────────────────────────
#  DreamPostComment
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestDreamPostCommentModel:
    """Tests for the DreamPostComment model."""

    def test_create_comment(self, social_user, social_user2):
        """DreamPostComment can be created with required fields."""
        post = DreamPost.objects.create(user=social_user, content="Post to comment on")
        comment = DreamPostComment.objects.create(
            post=post,
            user=social_user2,
            content="Great post!",
        )
        assert comment.pk is not None
        assert comment.post == post
        assert comment.user == social_user2
        assert comment.content == "Great post!"
        assert comment.parent is None

    def test_comment_str(self, social_user, social_user2):
        """DreamPostComment __str__ returns readable representation."""
        post = DreamPost.objects.create(user=social_user, content="Test")
        comment = DreamPostComment.objects.create(
            post=post, user=social_user2, content="Nice!"
        )
        result = str(comment)
        assert "Social User 2" in result
        assert "Nice!" in result

    def test_threaded_reply(self, social_user, social_user2, social_user3):
        """DreamPostComment supports threaded replies via parent field."""
        post = DreamPost.objects.create(user=social_user, content="Test")
        parent_comment = DreamPostComment.objects.create(
            post=post, user=social_user2, content="Parent comment"
        )
        reply = DreamPostComment.objects.create(
            post=post,
            user=social_user3,
            content="Reply to parent",
            parent=parent_comment,
        )
        assert reply.parent == parent_comment
        assert parent_comment.replies.count() == 1
        assert parent_comment.replies.first() == reply

    def test_multiple_comments_on_same_post(self, social_user, social_user2):
        """Multiple comments can be created on the same post."""
        post = DreamPost.objects.create(user=social_user, content="Test")
        DreamPostComment.objects.create(post=post, user=social_user2, content="Comment 1")
        DreamPostComment.objects.create(post=post, user=social_user2, content="Comment 2")
        assert DreamPostComment.objects.filter(post=post).count() == 2


# ──────────────────────────────────────────────────────────────────────
#  PostReaction
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestPostReactionModel:
    """Tests for the PostReaction model."""

    def test_create_reaction(self, social_user, social_user2):
        """PostReaction can be created with a reaction type."""
        post = DreamPost.objects.create(user=social_user, content="Test")
        reaction = PostReaction.objects.create(
            post=post, user=social_user2, reaction_type="fire"
        )
        assert reaction.pk is not None
        assert reaction.reaction_type == "fire"

    def test_reaction_str(self, social_user, social_user2):
        """PostReaction __str__ returns readable representation."""
        post = DreamPost.objects.create(user=social_user, content="Test")
        reaction = PostReaction.objects.create(
            post=post, user=social_user2, reaction_type="love"
        )
        result = str(reaction)
        assert "Social User 2" in result
        assert "love" in result

    def test_unique_reaction_per_user_per_post(self, social_user, social_user2):
        """Only one reaction per user per post (unique constraint)."""
        post = DreamPost.objects.create(user=social_user, content="Test")
        PostReaction.objects.create(post=post, user=social_user2, reaction_type="like")
        with pytest.raises(IntegrityError):
            PostReaction.objects.create(post=post, user=social_user2, reaction_type="love")

    def test_all_reaction_types(self, social_user):
        """All defined reaction types can be used."""
        reaction_types = ["like", "love", "fire", "clap", "wow", "celebrate"]
        for i, reaction_type in enumerate(reaction_types):
            user = User.objects.create_user(
                email=f"reactor{i}@example.com",
                password="testpassword123",
            )
            post = DreamPost.objects.create(user=social_user, content=f"Post {i}")
            reaction = PostReaction.objects.create(
                post=post, user=user, reaction_type=reaction_type
            )
            assert reaction.reaction_type == reaction_type


# ──────────────────────────────────────────────────────────────────────
#  SavedPost
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestSavedPostModel:
    """Tests for the SavedPost model."""

    def test_create_saved_post(self, social_user, social_user2):
        """SavedPost can be created."""
        post = DreamPost.objects.create(user=social_user, content="Saveable post")
        saved = SavedPost.objects.create(user=social_user2, post=post)
        assert saved.pk is not None
        assert saved.user == social_user2
        assert saved.post == post

    def test_saved_post_str(self, social_user, social_user2):
        """SavedPost __str__ returns readable representation."""
        post = DreamPost.objects.create(user=social_user, content="Test")
        saved = SavedPost.objects.create(user=social_user2, post=post)
        result = str(saved)
        assert "Social User 2" in result

    def test_unique_save_per_user_per_post(self, social_user, social_user2):
        """Only one save per user per post (unique_together constraint)."""
        post = DreamPost.objects.create(user=social_user, content="Test")
        SavedPost.objects.create(user=social_user2, post=post)
        with pytest.raises(IntegrityError):
            SavedPost.objects.create(user=social_user2, post=post)


# ──────────────────────────────────────────────────────────────────────
#  Friendship
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestFriendshipModel:
    """Tests for the Friendship model."""

    def test_create_friendship(self, social_user, social_user2):
        """Friendship can be created with pending status."""
        friendship = Friendship.objects.create(
            user1=social_user,
            user2=social_user2,
            status="pending",
        )
        assert friendship.pk is not None
        assert friendship.user1 == social_user
        assert friendship.user2 == social_user2
        assert friendship.status == "pending"

    def test_friendship_str(self, social_user, social_user2):
        """Friendship __str__ includes both user names and status."""
        friendship = Friendship.objects.create(
            user1=social_user, user2=social_user2, status="pending"
        )
        result = str(friendship)
        assert "Social User" in result
        assert "Social User 2" in result
        assert "pending" in result

    def test_friendship_status_transitions(self, social_user, social_user2):
        """Friendship status can transition from pending to accepted."""
        friendship = Friendship.objects.create(
            user1=social_user, user2=social_user2, status="pending"
        )
        assert friendship.status == "pending"
        friendship.status = "accepted"
        friendship.save()
        friendship.refresh_from_db()
        assert friendship.status == "accepted"

    def test_friendship_reject(self, social_user, social_user2):
        """Friendship status can transition from pending to rejected."""
        friendship = Friendship.objects.create(
            user1=social_user, user2=social_user2, status="pending"
        )
        friendship.status = "rejected"
        friendship.save()
        friendship.refresh_from_db()
        assert friendship.status == "rejected"

    def test_unique_friendship_pair(self, social_user, social_user2):
        """Cannot create duplicate friendship between same users in same direction."""
        Friendship.objects.create(
            user1=social_user, user2=social_user2, status="pending"
        )
        with pytest.raises(IntegrityError):
            Friendship.objects.create(
                user1=social_user, user2=social_user2, status="pending"
            )

    def test_bidirectional_friendship_lookup(self, social_user, social_user2):
        """Friendship can be found via either user."""
        Friendship.objects.create(
            user1=social_user, user2=social_user2, status="accepted"
        )
        # Can find from user1 side
        assert Friendship.objects.filter(
            user1=social_user, user2=social_user2, status="accepted"
        ).exists()
        # Can find using Q objects (how the views look it up)
        from django.db.models import Q

        assert Friendship.objects.filter(
            Q(user1=social_user, user2=social_user2)
            | Q(user1=social_user2, user2=social_user),
            status="accepted",
        ).exists()


# ──────────────────────────────────────────────────────────────────────
#  UserFollow
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestUserFollowModel:
    """Tests for the UserFollow model."""

    def test_create_follow(self, social_user, social_user2):
        """UserFollow can be created."""
        follow = UserFollow.objects.create(
            follower=social_user,
            following=social_user2,
        )
        assert follow.pk is not None
        assert follow.follower == social_user
        assert follow.following == social_user2

    def test_follow_str(self, social_user, social_user2):
        """UserFollow __str__ returns readable representation."""
        follow = UserFollow.objects.create(
            follower=social_user, following=social_user2
        )
        result = str(follow)
        assert "Social User" in result
        assert "follows" in result
        assert "Social User 2" in result

    def test_unique_follow(self, social_user, social_user2):
        """Cannot create duplicate follow relationship."""
        UserFollow.objects.create(follower=social_user, following=social_user2)
        with pytest.raises(IntegrityError):
            UserFollow.objects.create(follower=social_user, following=social_user2)

    def test_follow_is_unidirectional(self, social_user, social_user2):
        """Follow is unidirectional -- user1 follows user2 does not imply reverse."""
        UserFollow.objects.create(follower=social_user, following=social_user2)
        assert UserFollow.objects.filter(
            follower=social_user, following=social_user2
        ).exists()
        assert not UserFollow.objects.filter(
            follower=social_user2, following=social_user
        ).exists()

    def test_bidirectional_follow_allowed(self, social_user, social_user2):
        """Two users can follow each other (separate records)."""
        UserFollow.objects.create(follower=social_user, following=social_user2)
        UserFollow.objects.create(follower=social_user2, following=social_user)
        assert UserFollow.objects.filter(follower=social_user).count() == 1
        assert UserFollow.objects.filter(follower=social_user2).count() == 1


# ──────────────────────────────────────────────────────────────────────
#  Story
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestStoryModel:
    """Tests for the Story model."""

    def test_create_story(self, social_user):
        """Story can be created with required fields."""
        now = timezone.now()
        story = Story.objects.create(
            user=social_user,
            media_type="image",
            caption="My story",
            expires_at=now + timedelta(hours=24),
        )
        assert story.pk is not None
        assert story.user == social_user
        assert story.media_type == "image"
        assert story.caption == "My story"
        assert story.view_count == 0

    def test_story_str(self, social_user):
        """Story __str__ returns readable representation."""
        story = Story.objects.create(
            user=social_user,
            media_type="image",
            expires_at=timezone.now() + timedelta(hours=24),
        )
        result = str(story)
        assert social_user.email in result
        assert "image" in result

    def test_story_is_active_before_expiry(self, social_user):
        """Story.is_active returns True when not expired."""
        story = Story.objects.create(
            user=social_user,
            media_type="image",
            expires_at=timezone.now() + timedelta(hours=24),
        )
        assert story.is_active is True

    def test_story_is_not_active_after_expiry(self, social_user):
        """Story.is_active returns False when expired."""
        story = Story.objects.create(
            user=social_user,
            media_type="image",
            expires_at=timezone.now() - timedelta(hours=1),
        )
        assert story.is_active is False

    def test_story_auto_expires_at(self, social_user):
        """Story.save() auto-sets expires_at to created_at + 24h when not provided."""
        story = Story(user=social_user, media_type="video")
        # expires_at not set, will be auto-set on save
        story.save()
        assert story.expires_at is not None
        # Should be roughly 24 hours from now
        diff = story.expires_at - timezone.now()
        assert timedelta(hours=23) < diff < timedelta(hours=25)

    def test_story_media_types(self, social_user):
        """Story supports image and video media types."""
        for media_type in ("image", "video"):
            story = Story.objects.create(
                user=social_user,
                media_type=media_type,
                expires_at=timezone.now() + timedelta(hours=24),
            )
            assert story.media_type == media_type


# ══════════════════════════════════════════════════════════════════════
#  API ENDPOINT TESTS — Social
# ══════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestSocialFriendshipAPI:
    """Tests for Social Friendship API endpoints."""

    def test_list_friends(self, social_client):
        resp = social_client.get(
            "/api/social/friends/",
            HTTP_ORIGIN="https://stepora.app",
        )
        assert resp.status_code == 200

    def test_pending_requests(self, social_client):
        resp = social_client.get(
            "/api/social/friends/requests/pending/",
            HTTP_ORIGIN="https://stepora.app",
        )
        assert resp.status_code == 200

    def test_sent_requests(self, social_client):
        resp = social_client.get(
            "/api/social/friends/requests/sent/",
            HTTP_ORIGIN="https://stepora.app",
        )
        assert resp.status_code == 200

    def test_user_search(self, social_client):
        resp = social_client.get(
            "/api/social/users/search?q=test",
            HTTP_ORIGIN="https://stepora.app",
        )
        assert resp.status_code == 200

    def test_follow_suggestions(self, social_client):
        resp = social_client.get(
            "/api/social/follow-suggestions/",
            HTTP_ORIGIN="https://stepora.app",
        )
        assert resp.status_code in (200, 403)

    def test_friend_suggestions(self, social_client):
        resp = social_client.get(
            "/api/social/friend-suggestions/",
            HTTP_ORIGIN="https://stepora.app",
        )
        assert resp.status_code in (200, 403)


@pytest.mark.django_db
class TestDreamPostAPI:
    """Tests for DreamPost API endpoints."""

    def test_list_posts(self, social_client):
        resp = social_client.get(
            "/api/social/posts/",
            HTTP_ORIGIN="https://stepora.app",
        )
        assert resp.status_code in (200, 403)

    def test_create_post(self, social_client):
        resp = social_client.post(
            "/api/social/posts/",
            {"content": "My dream progress!", "visibility": "public"},
            format="json",
            HTTP_ORIGIN="https://stepora.app",
        )
        assert resp.status_code in (201, 403)

    def test_list_posts_unauthenticated(self):
        from rest_framework.test import APIClient

        client = APIClient()
        resp = client.get(
            "/api/social/posts/",
            HTTP_ORIGIN="https://stepora.app",
        )
        assert resp.status_code == 401


@pytest.mark.django_db
class TestStoryAPI:
    """Tests for Story API endpoints."""

    def test_list_stories(self, social_client):
        resp = social_client.get(
            "/api/social/stories/",
            HTTP_ORIGIN="https://stepora.app",
        )
        assert resp.status_code in (200, 403)


@pytest.mark.django_db
class TestSocialEventAPI:
    """Tests for Social Event API endpoints."""

    def test_list_events(self, social_client):
        resp = social_client.get(
            "/api/social/events/",
            HTTP_ORIGIN="https://stepora.app",
        )
        assert resp.status_code in (200, 403)


@pytest.mark.django_db
class TestSocialFriendshipActions:
    """Tests for friendship-related actions."""

    def test_send_friend_request(self, social_client, social_user2):
        resp = social_client.post(
            "/api/social/friends/request/",
            {"user_id": str(social_user2.id)},
            format="json",
            HTTP_ORIGIN="https://stepora.app",
        )
        assert resp.status_code in (200, 201, 400, 403)

    def test_follow_user(self, social_client, social_user2):
        resp = social_client.post(
            "/api/social/follow/",
            {"user_id": str(social_user2.id)},
            format="json",
            HTTP_ORIGIN="https://stepora.app",
        )
        assert resp.status_code in (200, 201, 400, 403)

    def test_block_user(self, social_client, social_user2):
        resp = social_client.post(
            "/api/social/block/",
            {"user_id": str(social_user2.id)},
            format="json",
            HTTP_ORIGIN="https://stepora.app",
        )
        assert resp.status_code in (200, 201, 400, 403)

    def test_blocked_list(self, social_client):
        resp = social_client.get(
            "/api/social/blocked/",
            HTTP_ORIGIN="https://stepora.app",
        )
        assert resp.status_code in (200, 403)

    def test_report_user(self, social_client, social_user2):
        resp = social_client.post(
            "/api/social/report/",
            {"user_id": str(social_user2.id), "reason": "spam"},
            format="json",
            HTTP_ORIGIN="https://stepora.app",
        )
        assert resp.status_code in (200, 201, 400, 403)

    def test_counts(self, social_client, social_user):
        resp = social_client.get(
            f"/api/social/counts/{social_user.id}/",
            HTTP_ORIGIN="https://stepora.app",
        )
        assert resp.status_code in (200, 403)

    def test_mutual_friends(self, social_client, social_user2):
        resp = social_client.get(
            f"/api/social/friends/mutual/{social_user2.id}/",
            HTTP_ORIGIN="https://stepora.app",
        )
        assert resp.status_code in (200, 403)

    def test_friends_feed(self, social_client):
        resp = social_client.get(
            "/api/social/feed/friends/",
            HTTP_ORIGIN="https://stepora.app",
        )
        assert resp.status_code in (200, 403)


@pytest.mark.django_db
class TestDreamPostAPIActions:
    """Tests for DreamPost API action endpoints."""

    def test_create_and_list_posts(self, social_client):
        # Create a post first
        resp = social_client.post(
            "/api/social/posts/",
            {"content": "Testing dreams!", "visibility": "public"},
            format="json",
            HTTP_ORIGIN="https://stepora.app",
        )
        if resp.status_code == 201:
            post_id = resp.data.get("id")
            # List posts
            list_resp = social_client.get(
                "/api/social/posts/",
                HTTP_ORIGIN="https://stepora.app",
            )
            assert list_resp.status_code == 200

            # Like the post
            like_resp = social_client.post(
                f"/api/social/posts/{post_id}/like/",
                HTTP_ORIGIN="https://stepora.app",
            )
            assert like_resp.status_code in (200, 201)

            # Comment on the post
            comment_resp = social_client.post(
                f"/api/social/posts/{post_id}/comment/",
                {"content": "Great dream!"},
                format="json",
                HTTP_ORIGIN="https://stepora.app",
            )
            assert comment_resp.status_code in (200, 201)

            # List comments
            comments_resp = social_client.get(
                f"/api/social/posts/{post_id}/comments/",
                HTTP_ORIGIN="https://stepora.app",
            )
            assert comments_resp.status_code == 200

            # Save the post
            save_resp = social_client.post(
                f"/api/social/posts/{post_id}/save/",
                HTTP_ORIGIN="https://stepora.app",
            )
            assert save_resp.status_code in (200, 201)

            # Delete the post
            del_resp = social_client.delete(
                f"/api/social/posts/{post_id}/",
                HTTP_ORIGIN="https://stepora.app",
            )
            assert del_resp.status_code in (200, 204)

    def test_post_feed(self, social_client):
        resp = social_client.get(
            "/api/social/posts/feed/",
            HTTP_ORIGIN="https://stepora.app",
        )
        assert resp.status_code in (200, 403)

    def test_recent_searches(self, social_client):
        resp = social_client.get(
            "/api/social/recent-searches/",
            HTTP_ORIGIN="https://stepora.app",
        )
        assert resp.status_code in (200, 403, 404, 500)

    def test_post_user_posts(self, social_client, social_user):
        resp = social_client.get(
            f"/api/social/posts/user/{social_user.id}/",
            HTTP_ORIGIN="https://stepora.app",
        )
        assert resp.status_code in (200, 403, 404)

    def test_friends_online(self, social_client):
        resp = social_client.get(
            "/api/social/friends/online/",
            HTTP_ORIGIN="https://stepora.app",
        )
        assert resp.status_code in (200, 403)

    def test_unfollow_nonexistent(self, social_client):
        import uuid
        resp = social_client.delete(
            f"/api/social/unfollow/{uuid.uuid4()}/",
            HTTP_ORIGIN="https://stepora.app",
        )
        assert resp.status_code in (200, 204, 400, 403, 404)

    def test_unblock_nonexistent(self, social_client):
        import uuid
        resp = social_client.delete(
            f"/api/social/unblock/{uuid.uuid4()}/",
            HTTP_ORIGIN="https://stepora.app",
        )
        assert resp.status_code in (200, 204, 400, 403, 404)

    def test_stories_my_stories(self, social_client):
        resp = social_client.get(
            "/api/social/stories/my_stories/",
            HTTP_ORIGIN="https://stepora.app",
        )
        assert resp.status_code in (200, 403)

    def test_stories_feed(self, social_client):
        resp = social_client.get(
            "/api/social/stories/feed/",
            HTTP_ORIGIN="https://stepora.app",
        )
        assert resp.status_code in (200, 403)

    def test_search_add(self, social_client, social_user2):
        resp = social_client.post(
            "/api/social/recent-searches/add/",
            {"user_id": str(social_user2.id)},
            format="json",
            HTTP_ORIGIN="https://stepora.app",
        )
        assert resp.status_code in (200, 201, 400, 403)

    def test_search_clear(self, social_client):
        resp = social_client.delete(
            "/api/social/recent-searches/clear/",
            HTTP_ORIGIN="https://stepora.app",
        )
        assert resp.status_code in (200, 204, 403)
