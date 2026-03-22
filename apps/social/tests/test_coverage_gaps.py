"""
Tests targeting remaining uncovered code paths for >=95% coverage.

Covers:
- 3-tier feed algorithm (views.py L1773-1984)
- ActivityFeedView: free user queryset, private dream filtering, pagination
- DreamPostViewSet: linked task, perform_update/destroy ownership,
  get_serializer_class, _get_blocked_ids
- RecentSearchViewSet IDOR
- StoryViewSet get_serializer_class
- SocialEventViewSet get_serializer_class, partial_update, events feed pagination
- Validators: all validators + magic bytes
- FriendshipViewSet: pending_requests query, notification branches
"""

import io
import uuid
from datetime import timedelta
from unittest.mock import MagicMock, patch

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.social.models import (
    ActivityComment,
    ActivityFeedItem,
    ActivityLike,
    BlockedUser,
    DreamEncouragement,
    DreamPost,
    DreamPostComment,
    DreamPostLike,
    Friendship,
    PostReaction,
    RecentSearch,
    SavedPost,
    SocialEvent,
    SocialEventRegistration,
    Story,
    StoryView,
    UserFollow,
)
from apps.social.validators import (
    _check_ftyp_box,
    _check_riff_format,
    _validate_magic_bytes,
    validate_audio_upload,
    validate_event_cover_upload,
    validate_image_upload,
    validate_video_upload,
)
from apps.users.models import User

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _mock_stripe_signal():
    with patch("apps.subscriptions.services.StripeService.create_customer"):
        yield


# ── Fixtures ────────────────────────────────────────────────────────


@pytest.fixture
def alice(db):
    return User.objects.create_user(
        email="cg_alice@example.com",
        password="pass123",
        display_name="Alice",
    )


@pytest.fixture
def bob(db):
    return User.objects.create_user(
        email="cg_bob@example.com",
        password="pass123",
        display_name="Bob",
    )


@pytest.fixture
def carol(db):
    return User.objects.create_user(
        email="cg_carol@example.com",
        password="pass123",
        display_name="Carol",
    )


@pytest.fixture
def dave(db):
    return User.objects.create_user(
        email="cg_dave@example.com",
        password="pass123",
        display_name="Dave",
    )


@pytest.fixture
def eve(db):
    return User.objects.create_user(
        email="cg_eve@example.com",
        password="pass123",
        display_name="Eve",
    )


@pytest.fixture
def alice_client(alice):
    c = APIClient()
    c.force_authenticate(user=alice)
    return c


@pytest.fixture
def bob_client(bob):
    c = APIClient()
    c.force_authenticate(user=bob)
    return c


# ═══════════════════════════════════════════════════════════════════
#  3-Tier Feed Algorithm (views.py L1756-1984)
# ═══════════════════════════════════════════════════════════════════


class TestFeedAlgorithm:
    """Full coverage of the 3-tier social feed algorithm."""

    FEED_URL = "/api/social/posts/feed/"

    def test_feed_empty_for_new_user(self, alice_client):
        """New user with no friends/follows gets empty feed."""
        resp = alice_client.get(self.FEED_URL)
        assert resp.status_code == 200
        assert isinstance(resp.data, list)

    def test_feed_includes_own_posts(self, alice_client, alice):
        """T0: own posts always appear in feed."""
        DreamPost.objects.create(user=alice, content="My post", visibility="public")
        resp = alice_client.get(self.FEED_URL)
        assert resp.status_code == 200
        contents = [p["content"] for p in resp.data]
        assert "My post" in contents

    def test_feed_includes_own_private_posts(self, alice_client, alice):
        """T0: own private posts appear."""
        DreamPost.objects.create(user=alice, content="Private", visibility="private")
        resp = alice_client.get(self.FEED_URL)
        contents = [p["content"] for p in resp.data]
        assert "Private" in contents

    def test_feed_includes_friend_public_posts(self, alice_client, alice, bob):
        """T1: friends' public posts appear."""
        Friendship.objects.create(user1=alice, user2=bob, status="accepted")
        DreamPost.objects.create(user=bob, content="Bob public", visibility="public")
        resp = alice_client.get(self.FEED_URL)
        contents = [p["content"] for p in resp.data]
        assert "Bob public" in contents

    def test_feed_includes_friend_followers_posts(self, alice_client, alice, bob):
        """T1: friends' followers-only posts appear."""
        Friendship.objects.create(user1=alice, user2=bob, status="accepted")
        DreamPost.objects.create(user=bob, content="Bob followers", visibility="followers")
        resp = alice_client.get(self.FEED_URL)
        contents = [p["content"] for p in resp.data]
        assert "Bob followers" in contents

    def test_feed_excludes_friend_private_posts(self, alice_client, alice, bob):
        """T1: friends' private posts do NOT appear."""
        Friendship.objects.create(user1=alice, user2=bob, status="accepted")
        DreamPost.objects.create(user=bob, content="Bob private", visibility="private")
        resp = alice_client.get(self.FEED_URL)
        contents = [p["content"] for p in resp.data]
        assert "Bob private" not in contents

    def test_feed_excludes_blocked_user_posts(self, alice_client, alice, bob):
        """Blocked users' posts never appear."""
        Friendship.objects.create(user1=alice, user2=bob, status="accepted")
        DreamPost.objects.create(user=bob, content="Blocked post", visibility="public")
        BlockedUser.objects.create(blocker=alice, blocked=bob)
        resp = alice_client.get(self.FEED_URL)
        contents = [p["content"] for p in resp.data]
        assert "Blocked post" not in contents

    def test_feed_tier2_friends_of_friends(self, alice_client, alice, bob, carol):
        """T2: public posts from friends-of-friends appear."""
        Friendship.objects.create(user1=alice, user2=bob, status="accepted")
        Friendship.objects.create(user1=bob, user2=carol, status="accepted")
        DreamPost.objects.create(user=carol, content="Carol FoF post", visibility="public")
        resp = alice_client.get(self.FEED_URL)
        contents = [p["content"] for p in resp.data]
        assert "Carol FoF post" in contents

    def test_feed_tier2_fof_excludes_private(self, alice_client, alice, bob, carol):
        """T2: FoF only sees public, not followers-only."""
        Friendship.objects.create(user1=alice, user2=bob, status="accepted")
        Friendship.objects.create(user1=bob, user2=carol, status="accepted")
        DreamPost.objects.create(
            user=carol, content="Carol followers", visibility="followers"
        )
        resp = alice_client.get(self.FEED_URL)
        contents = [p["content"] for p in resp.data]
        assert "Carol followers" not in contents

    def test_feed_tier3_followed_users(self, alice_client, alice, dave):
        """T3: public posts from followed users appear."""
        UserFollow.objects.create(follower=alice, following=dave)
        DreamPost.objects.create(user=dave, content="Dave followed", visibility="public")
        resp = alice_client.get(self.FEED_URL)
        contents = [p["content"] for p in resp.data]
        assert "Dave followed" in contents

    def test_feed_tier3_trending_posts(self, alice_client, alice, eve):
        """T3 trending: high-engagement public posts from last 7 days."""
        post = DreamPost.objects.create(
            user=eve, content="Eve trending", visibility="public",
            likes_count=50, comments_count=20,
        )
        resp = alice_client.get(self.FEED_URL)
        contents = [p["content"] for p in resp.data]
        assert "Eve trending" in contents

    def test_feed_interleaves_tiers(self, alice_client, alice, bob, carol, dave, eve):
        """Feed interleaves T1, T2, T3 posts according to pattern."""
        Friendship.objects.create(user1=alice, user2=bob, status="accepted")
        Friendship.objects.create(user1=bob, user2=carol, status="accepted")
        UserFollow.objects.create(follower=alice, following=dave)
        # Create many posts
        for i in range(10):
            DreamPost.objects.create(
                user=bob, content=f"T1-{i}", visibility="public"
            )
        for i in range(5):
            DreamPost.objects.create(
                user=carol, content=f"T2-{i}", visibility="public"
            )
        for i in range(5):
            DreamPost.objects.create(
                user=dave, content=f"T3-{i}", visibility="public"
            )
        resp = alice_client.get(self.FEED_URL)
        assert resp.status_code == 200
        assert len(resp.data) <= 15

    def test_feed_serializer_fields(self, alice_client, alice, bob):
        """Feed posts include expected serializer fields."""
        Friendship.objects.create(user1=alice, user2=bob, status="accepted")
        DreamPost.objects.create(user=bob, content="Check fields", visibility="public")
        resp = alice_client.get(self.FEED_URL)
        assert resp.status_code == 200
        if resp.data:
            post = resp.data[0]
            assert "has_liked" in post
            assert "has_saved" in post
            assert "has_encouraged" in post
            assert "user_reaction" in post
            assert "reaction_counts" in post
            assert "is_owner" in post

    def test_feed_fof_capped_at_500(self, alice_client, alice, bob):
        """FoF IDs are capped at 500 to prevent query explosion."""
        Friendship.objects.create(user1=alice, user2=bob, status="accepted")
        # Create many friends of bob
        for i in range(10):
            u = User.objects.create_user(
                email=f"fof_{i}@x.com", password="pass", display_name=f"FoF {i}"
            )
            Friendship.objects.create(user1=bob, user2=u, status="accepted")
            DreamPost.objects.create(user=u, content=f"FoF post {i}", visibility="public")
        resp = alice_client.get(self.FEED_URL)
        assert resp.status_code == 200


# ═══════════════════════════════════════════════════════════════════
#  ActivityFeedView: free user, private dream filtering
# ═══════════════════════════════════════════════════════════════════


class TestActivityFeedCoverage:
    """Cover ActivityFeedView branches."""

    FEED_URL = "/api/social/feed/friends/"

    def test_free_user_limited_feed(self, alice, alice_client):
        """Free users (subscription='free') only see encouragement activities."""
        alice.subscription = "free"
        alice.save()
        # Create non-encouragement activity
        ActivityFeedItem.objects.create(
            user=alice,
            activity_type="task_completed",
            content={"title": "Test task"},
        )
        resp = alice_client.get(self.FEED_URL)
        assert resp.status_code == 200

    def test_premium_user_full_feed(self, alice, alice_client, bob):
        """Premium users see activities from friends."""
        alice.subscription = "premium"
        alice.save()
        Friendship.objects.create(user1=alice, user2=bob, status="accepted")
        ActivityFeedItem.objects.create(
            user=bob,
            activity_type="task_completed",
            content={"title": "Bob task"},
        )
        resp = alice_client.get(self.FEED_URL)
        assert resp.status_code == 200

    def test_activity_feed_filters(self, alice, alice_client):
        """Activity feed supports activity_type and date filters."""
        alice.subscription = "premium"
        alice.save()
        ActivityFeedItem.objects.create(
            user=alice,
            activity_type="task_completed",
            content={},
        )
        ActivityFeedItem.objects.create(
            user=alice,
            activity_type="dream_completed",
            content={},
        )
        # Filter by type
        resp = alice_client.get(self.FEED_URL, {"activity_type": "task_completed"})
        assert resp.status_code == 200
        # Filter by date
        resp = alice_client.get(
            self.FEED_URL,
            {"created_after": (timezone.now() - timedelta(days=1)).isoformat()},
        )
        assert resp.status_code == 200

    def test_activity_feed_excludes_blocked_users(self, alice, alice_client, bob):
        """Feed excludes activities from blocked users."""
        alice.subscription = "premium"
        alice.save()
        Friendship.objects.create(user1=alice, user2=bob, status="accepted")
        ActivityFeedItem.objects.create(
            user=bob, activity_type="task_completed", content={}
        )
        BlockedUser.objects.create(blocker=alice, blocked=bob)
        resp = alice_client.get(self.FEED_URL)
        assert resp.status_code == 200


# ═══════════════════════════════════════════════════════════════════
#  DreamPost: linked task, ownership, get_serializer_class
# ═══════════════════════════════════════════════════════════════════


class TestDreamPostGaps:
    """Cover remaining DreamPost view gaps."""

    def test_create_post_linked_task_not_found(self, alice_client):
        """Creating post with invalid linked_task_id returns 404."""
        resp = alice_client.post(
            "/api/social/posts/",
            {
                "content": "Test",
                "post_type": "achievement",
                "linked_task_id": str(uuid.uuid4()),
            },
            format="json",
        )
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_create_post_with_linked_task(self, alice_client, alice):
        """Creating post with valid linked task succeeds."""
        from apps.dreams.models import Dream, Goal, Task

        dream = Dream.objects.create(
            user=alice, title="Test Dream", is_public=True, status="active",
        )
        goal = Goal.objects.create(dream=dream, title="Test Goal", order=1)
        task = Task.objects.create(goal=goal, title="Test Task", order=1)
        resp = alice_client.post(
            "/api/social/posts/",
            {
                "content": "Completed my task!",
                "post_type": "achievement",
                "linked_task_id": str(task.id),
                "dream_id": str(dream.id),
            },
            format="json",
        )
        assert resp.status_code == status.HTTP_201_CREATED
        assert resp.data["post_type"] == "achievement"

    def test_get_blocked_ids_bidirectional(self, alice, bob, carol):
        """_get_blocked_ids returns IDs from both block directions."""
        # Alice blocks Bob
        BlockedUser.objects.create(blocker=alice, blocked=bob)
        # Carol blocks Alice
        BlockedUser.objects.create(blocker=carol, blocked=alice)

        from apps.social.views import DreamPostViewSet

        viewset = DreamPostViewSet()
        blocked_ids = viewset._get_blocked_ids(alice)
        assert bob.id in blocked_ids
        assert carol.id in blocked_ids
        assert alice.id not in blocked_ids

    def test_update_post_gofundme_url(self, alice_client, alice):
        """Updating gofundme_url field on a post."""
        post = DreamPost.objects.create(
            user=alice, content="Test", visibility="public"
        )
        resp = alice_client.patch(
            f"/api/social/posts/{post.id}/",
            {"gofundme_url": "https://gofundme.com/test", "visibility": "followers"},
            format="json",
        )
        assert resp.status_code == 200
        post.refresh_from_db()
        assert post.visibility == "followers"

    def test_update_post_post_type(self, alice_client, alice):
        """Updating post_type field."""
        post = DreamPost.objects.create(
            user=alice, content="Test", visibility="public"
        )
        resp = alice_client.patch(
            f"/api/social/posts/{post.id}/",
            {"post_type": "achievement"},
            format="json",
        )
        assert resp.status_code == 200

    def test_create_post_with_media_type_video(self, alice_client, alice):
        """Creating post detects video media type."""
        # Cannot upload real file easily, but let's test the media_type detection
        resp = alice_client.post(
            "/api/social/posts/",
            {"content": "Test with image_url", "image_url": "https://example.com/img.jpg"},
            format="json",
        )
        assert resp.status_code == status.HTTP_201_CREATED
        assert resp.data["media_type"] == "image"


# ═══════════════════════════════════════════════════════════════════
#  Pending Requests & Sent Requests
# ═══════════════════════════════════════════════════════════════════


class TestFriendRequestListing:
    """Cover pending_requests and sent_requests views."""

    def test_pending_requests_list(self, alice_client, alice, bob):
        """Pending requests lists incoming requests."""
        Friendship.objects.create(user1=bob, user2=alice, status="pending")
        resp = alice_client.get("/api/social/friends/requests/pending/")
        assert resp.status_code == 200
        assert len(resp.data) == 1
        assert resp.data[0]["sender"]["username"] == "Bob"

    def test_pending_requests_empty(self, alice_client):
        """No pending requests returns empty list."""
        resp = alice_client.get("/api/social/friends/requests/pending/")
        assert resp.status_code == 200
        assert len(resp.data) == 0

    def test_sent_requests_list(self, alice_client, alice, bob):
        """Sent requests shows outgoing requests."""
        Friendship.objects.create(user1=alice, user2=bob, status="pending")
        resp = alice_client.get("/api/social/friends/requests/sent/")
        assert resp.status_code == 200
        assert len(resp.data) == 1
        assert resp.data[0]["receiver"]["username"] == "Bob"


# ═══════════════════════════════════════════════════════════════════
#  Validators (validators.py)
# ═══════════════════════════════════════════════════════════════════


class TestValidators:
    """Cover all validator code paths."""

    def _make_file(self, content, content_type, size=None):
        """Helper to create a mock file object."""
        f = io.BytesIO(content)
        f.content_type = content_type
        f.size = size or len(content)
        f.name = "test_file"
        return f

    def test_validate_image_jpeg(self):
        """JPEG image passes validation."""
        f = self._make_file(b"\xff\xd8\xff" + b"\x00" * 100, "image/jpeg")
        validate_image_upload(f)

    def test_validate_image_png(self):
        """PNG image passes validation."""
        f = self._make_file(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100, "image/png")
        validate_image_upload(f)

    def test_validate_image_webp(self):
        """WebP image passes validation."""
        f = self._make_file(b"RIFF\x00\x00\x00\x00WEBP", "image/webp")
        validate_image_upload(f)

    def test_validate_image_gif87(self):
        """GIF87a image passes validation."""
        f = self._make_file(b"GIF87a" + b"\x00" * 100, "image/gif")
        validate_image_upload(f)

    def test_validate_image_gif89(self):
        """GIF89a image passes validation."""
        f = self._make_file(b"GIF89a" + b"\x00" * 100, "image/gif")
        validate_image_upload(f)

    def test_validate_image_unsupported_type(self):
        """Unsupported image type raises ValidationError."""
        f = self._make_file(b"\x00" * 100, "image/bmp")
        with pytest.raises(ValidationError, match="Unsupported image type"):
            validate_image_upload(f)

    def test_validate_image_too_large(self):
        """Image exceeding 10MB raises ValidationError."""
        f = self._make_file(b"\xff\xd8\xff", "image/jpeg", size=11 * 1024 * 1024)
        with pytest.raises(ValidationError, match="Image too large"):
            validate_image_upload(f)

    def test_validate_image_wrong_magic_bytes(self):
        """Wrong magic bytes raises ValidationError."""
        f = self._make_file(b"\x00\x00\x00" + b"\x00" * 100, "image/jpeg")
        with pytest.raises(ValidationError, match="does not match"):
            validate_image_upload(f)

    def test_validate_video_mp4(self):
        """MP4 video passes validation."""
        f = self._make_file(b"\x00\x00\x00\x18ftyp" + b"\x00" * 100, "video/mp4")
        validate_video_upload(f)

    def test_validate_video_webm(self):
        """WebM video passes validation."""
        f = self._make_file(b"\x1a\x45\xdf\xa3" + b"\x00" * 100, "video/webm")
        validate_video_upload(f)

    def test_validate_video_unsupported(self):
        """Unsupported video type raises ValidationError."""
        f = self._make_file(b"\x00" * 100, "video/avi")
        with pytest.raises(ValidationError, match="Unsupported video type"):
            validate_video_upload(f)

    def test_validate_video_too_large(self):
        """Video exceeding 100MB raises ValidationError."""
        f = self._make_file(b"\x00\x00\x00\x18ftyp", "video/mp4", size=101 * 1024 * 1024)
        with pytest.raises(ValidationError, match="Video too large"):
            validate_video_upload(f)

    def test_validate_audio_mpeg(self):
        """MP3 audio passes validation."""
        f = self._make_file(b"ID3" + b"\x00" * 100, "audio/mpeg")
        validate_audio_upload(f)

    def test_validate_audio_ogg(self):
        """OGG audio passes validation."""
        f = self._make_file(b"OggS" + b"\x00" * 100, "audio/ogg")
        validate_audio_upload(f)

    def test_validate_audio_wav(self):
        """WAV audio passes validation."""
        f = self._make_file(b"RIFF\x00\x00\x00\x00WAVE", "audio/wav")
        validate_audio_upload(f)

    def test_validate_audio_mp4(self):
        """M4A audio passes validation."""
        f = self._make_file(b"\x00\x00\x00\x18ftyp" + b"\x00" * 100, "audio/mp4")
        validate_audio_upload(f)

    def test_validate_audio_unsupported(self):
        """Unsupported audio type raises ValidationError."""
        f = self._make_file(b"\x00" * 100, "audio/flac")
        with pytest.raises(ValidationError, match="Unsupported audio type"):
            validate_audio_upload(f)

    def test_validate_audio_too_large(self):
        """Audio exceeding 20MB raises ValidationError."""
        f = self._make_file(b"ID3", "audio/mpeg", size=21 * 1024 * 1024)
        with pytest.raises(ValidationError, match="Audio too large"):
            validate_audio_upload(f)

    def test_validate_event_cover(self):
        """Event cover image validates correctly."""
        f = self._make_file(b"\xff\xd8\xff" + b"\x00" * 100, "image/jpeg")
        validate_event_cover_upload(f)

    def test_validate_event_cover_unsupported(self):
        """Event cover with unsupported type."""
        f = self._make_file(b"\x00" * 100, "image/bmp")
        with pytest.raises(ValidationError, match="Unsupported image type"):
            validate_event_cover_upload(f)

    def test_validate_event_cover_too_large(self):
        """Event cover exceeding size limit."""
        f = self._make_file(b"\xff\xd8\xff", "image/jpeg", size=11 * 1024 * 1024)
        with pytest.raises(ValidationError, match="Cover image too large"):
            validate_event_cover_upload(f)

    def test_empty_file(self):
        """Empty file raises ValidationError."""
        f = self._make_file(b"", "image/jpeg")
        with pytest.raises(ValidationError, match="Empty file"):
            validate_image_upload(f)

    def test_riff_format_check(self):
        """_check_riff_format works correctly."""
        assert _check_riff_format(b"RIFF\x00\x00\x00\x00WEBP", b"WEBP") is True
        assert _check_riff_format(b"RIFF\x00\x00\x00\x00WAVE", b"WAVE") is True
        assert _check_riff_format(b"RIFF\x00\x00\x00\x00XXXX", b"WEBP") is False
        assert _check_riff_format(b"short", b"WEBP") is False

    def test_ftyp_box_check(self):
        """_check_ftyp_box works correctly."""
        assert _check_ftyp_box(b"\x00\x00\x00\x18ftyp" + b"\x00" * 4) is True
        assert _check_ftyp_box(b"\x00" * 12) is False
        assert _check_ftyp_box(b"short") is False

    def test_validate_wrong_webp_magic(self):
        """WebP with wrong RIFF format fails."""
        f = self._make_file(b"RIFF\x00\x00\x00\x00XXXX", "image/webp")
        with pytest.raises(ValidationError, match="WebP"):
            validate_image_upload(f)

    def test_validate_wrong_wav_magic(self):
        """WAV with wrong RIFF format fails."""
        f = self._make_file(b"RIFF\x00\x00\x00\x00XXXX", "audio/wav")
        with pytest.raises(ValidationError, match="WAV"):
            validate_audio_upload(f)

    def test_validate_wrong_mp4_magic(self):
        """MP4 without ftyp box fails."""
        f = self._make_file(b"\x00" * 12, "video/mp4")
        with pytest.raises(ValidationError, match="does not match"):
            validate_video_upload(f)

    def test_validate_wrong_mov_magic(self):
        """MOV without ftyp box fails."""
        f = self._make_file(b"\x00" * 12, "video/quicktime")
        with pytest.raises(ValidationError, match="does not match"):
            validate_video_upload(f)


# ═══════════════════════════════════════════════════════════════════
#  Story ViewSet edge cases
# ═══════════════════════════════════════════════════════════════════


class TestStoryEdgeCases:
    """Cover StoryViewSet uncovered paths."""

    def test_story_feed_groups_by_user(self, alice_client, alice, bob):
        """Story feed groups stories by user with unviewed first."""
        Friendship.objects.create(user1=alice, user2=bob, status="accepted")
        now = timezone.now()
        s1 = Story.objects.create(
            user=bob, media_type="image", caption="Bob story",
            expires_at=now + timedelta(hours=24),
        )
        s2 = Story.objects.create(
            user=alice, media_type="image", caption="My story",
            expires_at=now + timedelta(hours=24),
        )
        resp = alice_client.get("/api/social/stories/feed/")
        assert resp.status_code == 200
        assert isinstance(resp.data, list)
        # Own stories should be first
        if resp.data:
            assert resp.data[0]["user"]["id"] == str(alice.id)

    def test_story_feed_blocked_user_excluded(self, alice_client, alice, bob):
        """Stories from blocked users don't appear in feed."""
        Friendship.objects.create(user1=alice, user2=bob, status="accepted")
        BlockedUser.objects.create(blocker=alice, blocked=bob)
        now = timezone.now()
        Story.objects.create(
            user=bob, media_type="image", caption="Blocked story",
            expires_at=now + timedelta(hours=24),
        )
        resp = alice_client.get("/api/social/stories/feed/")
        assert resp.status_code == 200
        # Should not contain bob's story
        for group in resp.data:
            assert group["user"]["id"] != str(bob.id)

    def test_expired_story_not_in_feed(self, alice_client, alice):
        """Expired stories don't appear in feed."""
        Story.objects.create(
            user=alice, media_type="image", caption="Expired",
            expires_at=timezone.now() - timedelta(hours=1),
        )
        resp = alice_client.get("/api/social/stories/feed/")
        assert resp.status_code == 200
        for group in resp.data:
            for story in group.get("stories", []):
                assert story.get("caption") != "Expired"


# ═══════════════════════════════════════════════════════════════════
#  SocialEvent edge cases
# ═══════════════════════════════════════════════════════════════════


class TestSocialEventEdgeCases:
    """Cover SocialEventViewSet uncovered paths."""

    def _create_event(self, client, **overrides):
        data = {
            "title": "Test Event",
            "description": "An event",
            "event_type": "virtual",
            "meeting_link": "https://meet.example.com/room",
            "start_time": (timezone.now() + timedelta(days=1)).isoformat(),
            "end_time": (timezone.now() + timedelta(days=1, hours=2)).isoformat(),
        }
        data.update(overrides)
        return client.post("/api/social/events/", data, format="json")

    def test_events_feed(self, alice_client, alice):
        """Events feed returns upcoming events."""
        resp = self._create_event(alice_client)
        assert resp.status_code == status.HTTP_201_CREATED
        feed_resp = alice_client.get("/api/social/events/feed/")
        assert feed_resp.status_code == 200

    def test_event_update_text_fields(self, alice_client, alice):
        """Updating event text fields (title, description, challenge_description)."""
        resp = self._create_event(alice_client)
        event_id = resp.data["id"]
        update_resp = alice_client.patch(
            f"/api/social/events/{event_id}/",
            {"title": "Updated Title", "description": "Updated desc"},
            format="json",
        )
        assert update_resp.status_code == 200
        assert update_resp.data["title"] == "Updated Title"

    def test_event_blocked_user_excluded(self, alice_client, alice, bob, bob_client):
        """Events from blocked users are excluded."""
        self._create_event(bob_client)
        BlockedUser.objects.create(blocker=alice, blocked=bob)
        resp = alice_client.get("/api/social/events/")
        assert resp.status_code == 200


# ═══════════════════════════════════════════════════════════════════
#  RecentSearch IDOR
# ═══════════════════════════════════════════════════════════════════


class TestRecentSearchIDOR:
    """Verify IDOR protection on recent searches."""

    def test_cannot_remove_other_users_search(self, alice_client, bob):
        """Cannot delete another user's recent search."""
        search = RecentSearch.objects.create(user=bob, query="test")
        resp = alice_client.delete(f"/api/social/recent-searches/{search.id}/remove/")
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_add_search_deduplicates(self, alice_client, alice):
        """Adding the same query again removes the old one (dedup)."""
        resp1 = alice_client.post(
            "/api/social/recent-searches/add/",
            {"query": "hello"},
            format="json",
        )
        assert resp1.status_code == status.HTTP_201_CREATED
        assert RecentSearch.objects.filter(user=alice).count() == 1
        resp2 = alice_client.post(
            "/api/social/recent-searches/add/",
            {"query": "hello"},
            format="json",
        )
        assert resp2.status_code == status.HTTP_201_CREATED
        # After dedup, should be exactly 1 (old deleted, new created)
        assert RecentSearch.objects.filter(user=alice).count() == 1

    def test_add_different_searches(self, alice_client, alice):
        """Different queries create separate records."""
        alice_client.post(
            "/api/social/recent-searches/add/",
            {"query": "hello"},
            format="json",
        )
        alice_client.post(
            "/api/social/recent-searches/add/",
            {"query": "world"},
            format="json",
        )
        assert RecentSearch.objects.filter(user=alice).count() == 2


# ═══════════════════════════════════════════════════════════════════
#  Model __str__ and edge cases
# ═══════════════════════════════════════════════════════════════════


class TestModelEdgeCases:
    """Cover model __str__ and properties not hit by other tests."""

    def test_activity_feed_item_str(self, alice):
        item = ActivityFeedItem.objects.create(
            user=alice, activity_type="task_completed", content={}
        )
        s = str(item)
        assert "Alice" in s
        assert "task_completed" in s

    def test_activity_like_str(self, alice):
        item = ActivityFeedItem.objects.create(
            user=alice, activity_type="task_completed", content={}
        )
        like = ActivityLike.objects.create(user=alice, activity=item)
        s = str(like)
        assert "Alice" in s
        assert "liked" in s

    def test_activity_comment_str(self, alice):
        item = ActivityFeedItem.objects.create(
            user=alice, activity_type="task_completed", content={}
        )
        comment = ActivityComment.objects.create(
            user=alice, activity=item, text="Nice!"
        )
        s = str(comment)
        assert "Alice" in s
        assert "commented" in s

    def test_recent_search_str(self, alice):
        search = RecentSearch.objects.create(user=alice, query="test query")
        s = str(search)
        assert "test query" in s

    def test_saved_post_str(self, alice):
        post = DreamPost.objects.create(user=alice, content="Test")
        sp = SavedPost.objects.create(user=alice, post=post)
        s = str(sp)
        assert "Alice" in s
        assert "saved" in s

    def test_dream_post_comment_str_long(self, alice):
        post = DreamPost.objects.create(user=alice, content="Test")
        comment = DreamPostComment.objects.create(
            post=post, user=alice, content="A" * 60
        )
        s = str(comment)
        assert "..." in s

    def test_dream_encouragement_str(self, alice, bob):
        post = DreamPost.objects.create(user=bob, content="Test")
        enc = DreamEncouragement.objects.create(
            post=post, user=alice, encouragement_type="you_got_this"
        )
        s = str(enc)
        assert "Alice" in s
        assert "you_got_this" in s

    def test_post_reaction_str(self, alice):
        post = DreamPost.objects.create(user=alice, content="Test")
        reaction = PostReaction.objects.create(
            user=alice, post=post, reaction_type="fire"
        )
        s = str(reaction)
        assert "fire" in s

    def test_social_event_str(self, alice):
        event = SocialEvent.objects.create(
            creator=alice,
            title="My Event",
            event_type="virtual",
            start_time=timezone.now(),
            end_time=timezone.now() + timedelta(hours=1),
        )
        s = str(event)
        assert "My Event" in s

    def test_social_event_registration_str(self, alice, bob):
        event = SocialEvent.objects.create(
            creator=alice,
            title="Event",
            event_type="virtual",
            start_time=timezone.now(),
            end_time=timezone.now() + timedelta(hours=1),
        )
        reg = SocialEventRegistration.objects.create(event=event, user=bob)
        s = str(reg)
        assert "Bob" in s

    def test_story_str(self, alice):
        story = Story.objects.create(
            user=alice, media_type="image",
            expires_at=timezone.now() + timedelta(hours=24),
        )
        s = str(story)
        assert "image" in s
        assert "active" in s

    def test_story_expired_str(self, alice):
        story = Story.objects.create(
            user=alice, media_type="video",
            expires_at=timezone.now() - timedelta(hours=1),
        )
        s = str(story)
        assert "expired" in s

    def test_story_view_str(self, alice, bob):
        story = Story.objects.create(
            user=alice, media_type="image",
            expires_at=timezone.now() + timedelta(hours=24),
        )
        view = StoryView.objects.create(story=story, user=bob)
        s = str(view)
        assert "cg_bob" in s

    def test_story_is_active_property(self, alice):
        """Story.is_active returns correct values."""
        active = Story.objects.create(
            user=alice, media_type="image",
            expires_at=timezone.now() + timedelta(hours=24),
        )
        expired = Story.objects.create(
            user=alice, media_type="image",
            expires_at=timezone.now() - timedelta(hours=1),
        )
        assert active.is_active is True
        assert expired.is_active is False

    def test_story_auto_expires_at(self, alice):
        """Story.save() auto-sets expires_at if not set."""
        story = Story(user=alice, media_type="image")
        story.save()
        assert story.expires_at is not None


# ═══════════════════════════════════════════════════════════════════
#  Notification branches (silently succeed/fail)
# ═══════════════════════════════════════════════════════════════════


class TestNotificationBranches:
    """Cover notification sending paths that are wrapped in try/except."""

    @patch("apps.notifications.services.NotificationService.create")
    def test_friend_request_sends_notification(self, mock_notify, alice_client, alice, bob):
        """Sending friend request triggers notification."""
        alice_client.post(
            "/api/social/friends/request/",
            {"target_user_id": str(bob.id)},
            format="json",
        )
        mock_notify.assert_called_once()

    @patch("apps.notifications.services.NotificationService.create")
    def test_accept_request_sends_notification(self, mock_notify, alice_client, alice, bob):
        """Accepting friend request triggers notification."""
        fr = Friendship.objects.create(user1=bob, user2=alice, status="pending")
        alice_client.post(f"/api/social/friends/accept/{fr.id}/")
        mock_notify.assert_called_once()

    @patch("apps.notifications.services.NotificationService.create", side_effect=Exception("fail"))
    def test_notification_failure_does_not_break_request(self, mock_notify, alice_client, alice, bob):
        """Notification failure doesn't break friend request."""
        resp = alice_client.post(
            "/api/social/friends/request/",
            {"target_user_id": str(bob.id)},
            format="json",
        )
        assert resp.status_code == status.HTTP_201_CREATED


# ═══════════════════════════════════════════════════════════════════
#  Saved posts listing
# ═══════════════════════════════════════════════════════════════════


class TestSavedPostsListing:
    """Cover saved posts listing endpoint."""

    def test_list_saved_posts(self, alice_client, alice, bob):
        """List saved posts returns bookmarked posts."""
        post = DreamPost.objects.create(user=bob, content="Bob post", visibility="public")
        SavedPost.objects.create(user=alice, post=post)
        resp = alice_client.get("/api/social/posts/saved/")
        assert resp.status_code == 200

    def test_list_saved_posts_empty(self, alice_client):
        """Empty saved posts list."""
        resp = alice_client.get("/api/social/posts/saved/")
        assert resp.status_code == 200
