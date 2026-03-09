"""
Tests for the 3 messaging systems, circle calls, and social dream posts.

Covers:
- AIChatConsumer (refactored from ChatConsumer)
- BuddyChatConsumer
- CircleChatConsumer
- Circle calls (start/join/leave/end/active)
- Social dream posts (CRUD, feed, like, comment, encourage, share)
"""

import uuid
import pytest
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from rest_framework import status
from rest_framework.authtoken.models import Token

from apps.users.models import User
from apps.conversations.models import Conversation, Message
from apps.buddies.models import BuddyPairing
from apps.circles.models import (
    Circle, CircleMembership, CircleMessage,
    CircleCall, CircleCallParticipant,
)
from apps.social.models import (
    BlockedUser, UserFollow,
    DreamPost, DreamPostLike, DreamPostComment, DreamEncouragement,
)


# ── Helpers ───────────────────────────────────────────────────────────

def _create_user(email=None, display_name='Test User', subscription='pro'):
    """Create a test user with auth token and subscription."""
    email = email or f'{uuid.uuid4().hex[:8]}@test.com'
    user = User.objects.create_user(
        email=email,
        password='testpass123',
        display_name=display_name,
    )
    # Set subscription via Subscription table (source of truth)
    if subscription:
        from apps.subscriptions.models import Subscription, SubscriptionPlan
        plan = SubscriptionPlan.objects.filter(slug=subscription).first()
        if plan:
            sub, _ = Subscription.objects.get_or_create(
                user=user, defaults={'plan': plan, 'status': 'active'},
            )
            if sub.plan_id != plan.pk:
                sub.plan = plan
                sub.status = 'active'
                sub.save(update_fields=['plan', 'status'])
    token = Token.objects.create(user=user)
    return user, token.key


def _authed_client(token_key):
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f'Token {token_key}')
    return client


# ── A2: AI Chat Consumer (refactored) ────────────────────────────────

class TestAIChatConsumerRefactor(TestCase):
    """Verify AIChatConsumer import paths and backward compat alias."""

    def test_import_aichat_consumer(self):
        from apps.conversations.consumers import AIChatConsumer
        assert AIChatConsumer is not None

    def test_backward_compat_alias(self):
        from apps.conversations.consumers import ChatConsumer, AIChatConsumer
        assert ChatConsumer is AIChatConsumer

    def test_routing_has_both_paths(self):
        from apps.conversations.routing import websocket_urlpatterns
        patterns = [r.pattern.regex.pattern for r in websocket_urlpatterns]
        assert any('ai-chat' in p for p in patterns)
        assert any('conversations' in p for p in patterns)


# ── A3: Buddy Chat ───────────────────────────────────────────────────

class TestBuddyChatConsumerImports(TestCase):
    """Verify BuddyChatConsumer and routing exist."""

    def test_import_buddy_consumer(self):
        from apps.buddies.consumers import BuddyChatConsumer
        assert BuddyChatConsumer is not None

    def test_routing_path(self):
        from apps.buddies.routing import websocket_urlpatterns
        patterns = [r.pattern.regex.pattern for r in websocket_urlpatterns]
        assert any('buddy-chat' in p for p in patterns)


# ── A4: Circle Chat + Calls ──────────────────────────────────────────

class TestCircleChatConsumerImports(TestCase):
    def test_import_circle_consumer(self):
        from apps.circles.consumers import CircleChatConsumer
        assert CircleChatConsumer is not None

    def test_routing_path(self):
        from apps.circles.routing import websocket_urlpatterns
        patterns = [r.pattern.regex.pattern for r in websocket_urlpatterns]
        assert any('circle-chat' in p for p in patterns)


class TestCircleMessageModel(TestCase):
    def setUp(self):
        self.user, _ = _create_user()
        self.circle = Circle.objects.create(
            name='Test Circle', creator=self.user,
        )
        CircleMembership.objects.create(
            circle=self.circle, user=self.user, role='admin',
        )

    def test_create_circle_message(self):
        msg = CircleMessage.objects.create(
            circle=self.circle, sender=self.user, content='Hello circle!',
        )
        assert msg.id is not None
        assert msg.content == 'Hello circle!'
        assert str(msg.circle_id) == str(self.circle.id)


class TestCircleChatREST(TestCase):
    """Test circle chat REST endpoints (fallback for WebSocket)."""

    def setUp(self):
        self.user, self.token = _create_user()
        self.client = _authed_client(self.token)
        self.circle = Circle.objects.create(
            name='Test Circle', creator=self.user,
        )
        CircleMembership.objects.create(
            circle=self.circle, user=self.user, role='admin',
        )

    def test_chat_history_empty(self):
        resp = self.client.get(f'/api/circles/{self.circle.id}/chat/')
        assert resp.status_code == status.HTTP_200_OK

    @override_settings(CHANNEL_LAYERS={'default': {'BACKEND': 'channels.layers.InMemoryChannelLayer'}})
    def test_chat_send_message(self):
        resp = self.client.post(
            f'/api/circles/{self.circle.id}/chat/send/',
            {'content': 'Hello from REST!'},
        )
        assert resp.status_code == status.HTTP_201_CREATED
        assert resp.data['content'] == 'Hello from REST!'

    def test_chat_history_with_messages(self):
        CircleMessage.objects.create(
            circle=self.circle, sender=self.user, content='msg1',
        )
        CircleMessage.objects.create(
            circle=self.circle, sender=self.user, content='msg2',
        )
        resp = self.client.get(f'/api/circles/{self.circle.id}/chat/')
        assert resp.status_code == status.HTTP_200_OK

    def test_non_member_cannot_view_chat(self):
        user2, token2 = _create_user()
        client2 = _authed_client(token2)
        resp = client2.get(f'/api/circles/{self.circle.id}/chat/')
        assert resp.status_code == status.HTTP_403_FORBIDDEN


class TestCircleCallEndpoints(TestCase):
    """Test circle call start/join/leave/end/active."""

    def setUp(self):
        self.user1, self.token1 = _create_user(display_name='Caller')
        self.user2, self.token2 = _create_user(display_name='Joiner')
        self.client1 = _authed_client(self.token1)
        self.client2 = _authed_client(self.token2)
        self.circle = Circle.objects.create(
            name='Call Circle', creator=self.user1,
        )
        CircleMembership.objects.create(
            circle=self.circle, user=self.user1, role='admin',
        )
        CircleMembership.objects.create(
            circle=self.circle, user=self.user2, role='member',
        )

    @override_settings(
        CHANNEL_LAYERS={'default': {'BACKEND': 'channels.layers.InMemoryChannelLayer'}},
        AGORA_APP_ID='',
        AGORA_APP_CERTIFICATE='',
    )
    def test_start_call(self):
        resp = self.client1.post(
            f'/api/circles/{self.circle.id}/call/start/',
            {'call_type': 'voice'},
        )
        assert resp.status_code == status.HTTP_201_CREATED
        assert resp.data['status'] == 'active'
        assert resp.data['call_type'] == 'voice'
        assert resp.data['agora_channel']

    @override_settings(
        CHANNEL_LAYERS={'default': {'BACKEND': 'channels.layers.InMemoryChannelLayer'}},
        AGORA_APP_ID='',
        AGORA_APP_CERTIFICATE='',
    )
    def test_join_call(self):
        # Start a call
        self.client1.post(
            f'/api/circles/{self.circle.id}/call/start/',
            {'call_type': 'voice'},
        )
        # Join
        resp = self.client2.post(f'/api/circles/{self.circle.id}/call/join/')
        assert resp.status_code == status.HTTP_200_OK

    @override_settings(
        CHANNEL_LAYERS={'default': {'BACKEND': 'channels.layers.InMemoryChannelLayer'}},
        AGORA_APP_ID='',
        AGORA_APP_CERTIFICATE='',
    )
    def test_leave_call_auto_end(self):
        # Start call
        self.client1.post(
            f'/api/circles/{self.circle.id}/call/start/',
            {'call_type': 'voice'},
        )
        # Leave (only participant → auto-end)
        resp = self.client1.post(f'/api/circles/{self.circle.id}/call/leave/')
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data['active_participants'] == 0

        call = CircleCall.objects.filter(circle=self.circle).first()
        assert call.status == 'completed'

    @override_settings(
        CHANNEL_LAYERS={'default': {'BACKEND': 'channels.layers.InMemoryChannelLayer'}},
        AGORA_APP_ID='',
        AGORA_APP_CERTIFICATE='',
    )
    def test_end_call(self):
        self.client1.post(
            f'/api/circles/{self.circle.id}/call/start/',
            {'call_type': 'voice'},
        )
        resp = self.client1.post(f'/api/circles/{self.circle.id}/call/end/')
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data['status'] == 'completed'

    @override_settings(
        CHANNEL_LAYERS={'default': {'BACKEND': 'channels.layers.InMemoryChannelLayer'}},
        AGORA_APP_ID='',
        AGORA_APP_CERTIFICATE='',
    )
    def test_active_call(self):
        resp = self.client1.get(f'/api/circles/{self.circle.id}/call/active/')
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data['active_call'] is None

        self.client1.post(
            f'/api/circles/{self.circle.id}/call/start/',
            {'call_type': 'video'},
        )
        resp = self.client1.get(f'/api/circles/{self.circle.id}/call/active/')
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data['active_call'] is not None

    @override_settings(
        CHANNEL_LAYERS={'default': {'BACKEND': 'channels.layers.InMemoryChannelLayer'}},
        AGORA_APP_ID='',
        AGORA_APP_CERTIFICATE='',
    )
    def test_cannot_start_two_calls(self):
        self.client1.post(
            f'/api/circles/{self.circle.id}/call/start/',
            {'call_type': 'voice'},
        )
        resp = self.client1.post(
            f'/api/circles/{self.circle.id}/call/start/',
            {'call_type': 'voice'},
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    @override_settings(
        CHANNEL_LAYERS={'default': {'BACKEND': 'channels.layers.InMemoryChannelLayer'}},
        AGORA_APP_ID='',
        AGORA_APP_CERTIFICATE='',
    )
    def test_non_initiator_cannot_end_call(self):
        self.client1.post(
            f'/api/circles/{self.circle.id}/call/start/',
            {'call_type': 'voice'},
        )
        resp = self.client2.post(f'/api/circles/{self.circle.id}/call/end/')
        assert resp.status_code == status.HTTP_403_FORBIDDEN


# ── B3: Buddy Call WebSocket Broadcast ────────────────────────────────

class TestBuddyCallBroadcast(TestCase):
    """Verify CallViewSet.initiate() looks up pairing for WS broadcast."""

    def setUp(self):
        self.user1, self.token1 = _create_user(display_name='Caller')
        self.user2, self.token2 = _create_user(display_name='Callee')
        self.client1 = _authed_client(self.token1)

        self.pairing = BuddyPairing.objects.create(
            user1=self.user1, user2=self.user2, status='active',
        )

    @override_settings(CHANNEL_LAYERS={'default': {'BACKEND': 'channels.layers.InMemoryChannelLayer'}})
    def test_initiate_call_creates_call_with_pairing(self):
        resp = self.client1.post(
            '/api/conversations/calls/initiate/',
            {'callee_id': str(self.user2.id), 'call_type': 'voice'},
        )
        assert resp.status_code == status.HTTP_201_CREATED
        from apps.conversations.models import Call
        call = Call.objects.get(id=resp.data['callId'])
        assert call.buddy_pairing == self.pairing


# ── C: Social Dream Posts ─────────────────────────────────────────────

class TestDreamPostModels(TestCase):
    """Test DreamPost, DreamPostLike, DreamPostComment, DreamEncouragement models."""

    def setUp(self):
        self.user, _ = _create_user()

    def test_create_dream_post(self):
        post = DreamPost.objects.create(
            user=self.user, content='My dream!', visibility='public',
        )
        assert post.id is not None
        assert post.likes_count == 0
        assert post.comments_count == 0

    def test_create_like(self):
        post = DreamPost.objects.create(user=self.user, content='Dream')
        like = DreamPostLike.objects.create(post=post, user=self.user)
        assert like.id is not None

    def test_unique_like(self):
        post = DreamPost.objects.create(user=self.user, content='Dream')
        DreamPostLike.objects.create(post=post, user=self.user)
        with pytest.raises(Exception):
            DreamPostLike.objects.create(post=post, user=self.user)

    def test_create_comment(self):
        post = DreamPost.objects.create(user=self.user, content='Dream')
        comment = DreamPostComment.objects.create(
            post=post, user=self.user, content='Great!',
        )
        assert comment.id is not None

    def test_threaded_comment(self):
        post = DreamPost.objects.create(user=self.user, content='Dream')
        parent = DreamPostComment.objects.create(
            post=post, user=self.user, content='Great!',
        )
        reply = DreamPostComment.objects.create(
            post=post, user=self.user, content='Thanks!', parent=parent,
        )
        assert reply.parent == parent
        assert parent.replies.count() == 1

    def test_create_encouragement(self):
        post = DreamPost.objects.create(user=self.user, content='Dream')
        enc = DreamEncouragement.objects.create(
            post=post, user=self.user,
            encouragement_type='you_got_this',
        )
        assert enc.id is not None

    def test_unique_encouragement(self):
        post = DreamPost.objects.create(user=self.user, content='Dream')
        DreamEncouragement.objects.create(
            post=post, user=self.user, encouragement_type='you_got_this',
        )
        with pytest.raises(Exception):
            DreamEncouragement.objects.create(
                post=post, user=self.user, encouragement_type='keep_going',
            )


class TestDreamPostAPI(TestCase):
    """Test DreamPostViewSet API endpoints."""

    def setUp(self):
        self.user1, self.token1 = _create_user(display_name='Poster')
        self.user2, self.token2 = _create_user(display_name='Viewer')
        self.client1 = _authed_client(self.token1)
        self.client2 = _authed_client(self.token2)

        # user2 follows user1
        UserFollow.objects.create(follower=self.user2, following=self.user1)

    def test_create_post(self):
        resp = self.client1.post('/api/social/posts/', {
            'content': 'My amazing dream!',
            'visibility': 'public',
        })
        assert resp.status_code == status.HTTP_201_CREATED
        assert resp.data['content'] == 'My amazing dream!'
        assert resp.data['visibility'] == 'public'

    def test_create_post_with_gofundme(self):
        resp = self.client1.post('/api/social/posts/', {
            'content': 'Help fund my dream!',
            'gofundme_url': 'https://gofundme.com/my-dream',
        })
        assert resp.status_code == status.HTTP_201_CREATED
        assert resp.data['gofundmeUrl'] == 'https://gofundme.com/my-dream'

    def test_list_posts(self):
        DreamPost.objects.create(user=self.user1, content='Post 1')
        DreamPost.objects.create(user=self.user1, content='Post 2')
        resp = self.client1.get('/api/social/posts/')
        assert resp.status_code == status.HTTP_200_OK

    def test_get_single_post(self):
        post = DreamPost.objects.create(user=self.user1, content='Post 1')
        resp = self.client1.get(f'/api/social/posts/{post.id}/')
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data['content'] == 'Post 1'

    def test_update_own_post(self):
        post = DreamPost.objects.create(user=self.user1, content='Original')
        resp = self.client1.patch(f'/api/social/posts/{post.id}/', {
            'content': 'Updated',
        })
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data['content'] == 'Updated'

    def test_cannot_update_others_post(self):
        post = DreamPost.objects.create(user=self.user1, content='Original')
        resp = self.client2.patch(f'/api/social/posts/{post.id}/', {
            'content': 'Hacked',
        })
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_delete_own_post(self):
        post = DreamPost.objects.create(user=self.user1, content='Delete me')
        resp = self.client1.delete(f'/api/social/posts/{post.id}/')
        assert resp.status_code == status.HTTP_204_NO_CONTENT
        assert not DreamPost.objects.filter(id=post.id).exists()

    def test_cannot_delete_others_post(self):
        post = DreamPost.objects.create(user=self.user1, content='Keep me')
        resp = self.client2.delete(f'/api/social/posts/{post.id}/')
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_feed(self):
        DreamPost.objects.create(
            user=self.user1, content='Public post', visibility='public',
        )
        resp = self.client2.get('/api/social/posts/feed/')
        assert resp.status_code == status.HTTP_200_OK

    def test_feed_excludes_blocked_users(self):
        DreamPost.objects.create(
            user=self.user1, content='Blocked post', visibility='public',
        )
        BlockedUser.objects.create(blocker=self.user2, blocked=self.user1)
        resp = self.client2.get('/api/social/posts/feed/')
        assert resp.status_code == status.HTTP_200_OK
        results = resp.data.get('results', resp.data)
        # Should not contain posts from blocked user
        for post in results:
            assert post['user']['id'] != str(self.user1.id)

    def test_like_unlike(self):
        post = DreamPost.objects.create(user=self.user1, content='Like me')
        # Like
        resp = self.client2.post(f'/api/social/posts/{post.id}/like/')
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data['liked'] is True

        # Unlike
        resp = self.client2.post(f'/api/social/posts/{post.id}/like/')
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data['liked'] is False

    def test_comment(self):
        post = DreamPost.objects.create(user=self.user1, content='Comment me')
        resp = self.client2.post(
            f'/api/social/posts/{post.id}/comment/',
            {'content': 'Great dream!'},
        )
        assert resp.status_code == status.HTTP_201_CREATED
        assert resp.data['content'] == 'Great dream!'

    def test_comment_empty_content_rejected(self):
        post = DreamPost.objects.create(user=self.user1, content='Comment me')
        resp = self.client2.post(
            f'/api/social/posts/{post.id}/comment/',
            {'content': ''},
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_list_comments(self):
        post = DreamPost.objects.create(user=self.user1, content='Post')
        DreamPostComment.objects.create(
            post=post, user=self.user2, content='Comment 1',
        )
        resp = self.client1.get(f'/api/social/posts/{post.id}/comments/')
        assert resp.status_code == status.HTTP_200_OK

    def test_encourage(self):
        post = DreamPost.objects.create(user=self.user1, content='Encourage me')
        resp = self.client2.post(
            f'/api/social/posts/{post.id}/encourage/',
            {'encouragement_type': 'you_got_this', 'message': 'Go for it!'},
        )
        assert resp.status_code == status.HTTP_201_CREATED
        assert resp.data['encouragementType'] == 'you_got_this'
        assert resp.data['message'] == 'Go for it!'

    def test_encourage_invalid_type(self):
        post = DreamPost.objects.create(user=self.user1, content='Encourage me')
        resp = self.client2.post(
            f'/api/social/posts/{post.id}/encourage/',
            {'encouragement_type': 'invalid_type'},
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_share(self):
        post = DreamPost.objects.create(user=self.user1, content='Share me')
        resp = self.client2.post(
            f'/api/social/posts/{post.id}/share/',
            {'content': 'Check this out!'},
        )
        assert resp.status_code == status.HTTP_201_CREATED
        # Original should have shares_count incremented
        post.refresh_from_db()
        assert post.shares_count == 1

    def test_user_posts(self):
        DreamPost.objects.create(
            user=self.user1, content='Post 1', visibility='public',
        )
        DreamPost.objects.create(
            user=self.user1, content='Post 2', visibility='followers',
        )
        # user2 follows user1, should see both
        resp = self.client2.get(
            f'/api/social/posts/user/{self.user1.id}/',
        )
        assert resp.status_code == status.HTTP_200_OK

    def test_user_posts_blocked(self):
        DreamPost.objects.create(
            user=self.user1, content='Blocked', visibility='public',
        )
        BlockedUser.objects.create(blocker=self.user2, blocked=self.user1)
        resp = self.client2.get(
            f'/api/social/posts/user/{self.user1.id}/',
        )
        assert resp.status_code == status.HTTP_403_FORBIDDEN


# ── ASGI Config ───────────────────────────────────────────────────────

class TestASGIConfig(TestCase):
    def test_asgi_imports(self):
        """Verify ASGI config includes all 4 WS route sets."""
        from apps.conversations.routing import websocket_urlpatterns as ai_ws
        from apps.buddies.routing import websocket_urlpatterns as buddy_ws
        from apps.circles.routing import websocket_urlpatterns as circle_ws
        from apps.notifications.routing import websocket_urlpatterns as notif_ws

        combined = ai_ws + buddy_ws + circle_ws + notif_ws
        assert len(combined) == 5  # 2 AI + 1 buddy + 1 circle + 1 notif


# ── Shared Mixins ─────────────────────────────────────────────────────

class TestSharedMixins(TestCase):
    """Test core.consumers shared mixins."""

    def test_rate_limit_mixin(self):
        from core.consumers import RateLimitMixin

        class TestConsumer(RateLimitMixin):
            rate_limit_msgs = 3
            rate_limit_window = 60

        c = TestConsumer()
        c._init_rate_limit()
        assert not c._is_rate_limited()
        assert not c._is_rate_limited()
        assert not c._is_rate_limited()
        assert c._is_rate_limited()  # 4th should be limited

    def test_blocking_mixin_no_block(self):
        from core.consumers import BlockingMixin
        user1, _ = _create_user()
        user2, _ = _create_user()
        mixin = BlockingMixin()
        # Sync wrapper for testing
        from asgiref.sync import async_to_sync
        result = async_to_sync(mixin._is_blocked)(user1, user2)
        assert result is False

    def test_blocking_mixin_with_block(self):
        from core.consumers import BlockingMixin
        user1, _ = _create_user()
        user2, _ = _create_user()
        BlockedUser.objects.create(blocker=user1, blocked=user2)
        mixin = BlockingMixin()
        from asgiref.sync import async_to_sync
        result = async_to_sync(mixin._is_blocked)(user1, user2)
        assert result is True
