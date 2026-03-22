"""
Tests for circles views.

Covers:
- Circle CRUD
- Join/leave
- Feed, posts CRUD
- Reactions, polls, votes
- Challenges + join
- Members management (promote, demote, remove)
- Invitations
- Chat, calls
"""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.circles.models import (
    ChallengeProgress,
    Circle,
    CircleChallenge,
    CircleMembership,
    CirclePoll,
    CirclePost,
    PollOption,
)
from apps.subscriptions.models import Subscription, SubscriptionPlan
from apps.users.models import User

# ── Helpers ──────────────────────────────────────────────────────────

def _make_pro_user(email, display_name="ProUser"):
    """Create a pro user (can create circles + all circle access)."""
    user = User.objects.create_user(
        email=email, password="testpass123", display_name=display_name,
    )
    plan = SubscriptionPlan.objects.get(slug="pro")
    Subscription.objects.update_or_create(
        user=user,
        defaults={
            "plan": plan,
            "status": "active",
            "current_period_start": timezone.now(),
            "current_period_end": timezone.now() + timedelta(days=30),
        },
    )
    return user


def _make_premium_user(email, display_name="PremiumUser"):
    """Create a premium user (circle join access but NOT create)."""
    user = User.objects.create_user(
        email=email, password="testpass123", display_name=display_name,
    )
    plan = SubscriptionPlan.objects.get(slug="premium")
    Subscription.objects.update_or_create(
        user=user,
        defaults={
            "plan": plan,
            "status": "active",
            "current_period_start": timezone.now(),
            "current_period_end": timezone.now() + timedelta(days=30),
        },
    )
    return user


def _client(user):
    c = APIClient()
    c.force_authenticate(user=user)
    return c


# ── Fixtures ─────────────────────────────────────────────────────────

@pytest.fixture
def admin_user(db):
    return _make_pro_user("circle_admin@test.com", "CircleAdmin")


@pytest.fixture
def member_user(db):
    return _make_pro_user("circle_member@test.com", "CircleMember")


@pytest.fixture
def outsider_user(db):
    return _make_pro_user("circle_outsider@test.com", "Outsider")


@pytest.fixture
def admin_client(admin_user):
    return _client(admin_user)


@pytest.fixture
def member_client(member_user):
    return _client(member_user)


@pytest.fixture
def outsider_client(outsider_user):
    return _client(outsider_user)


@pytest.fixture
def circle(db, admin_user):
    c = Circle.objects.create(
        name="Test Circle", description="Desc", category="career",
        is_public=True, creator=admin_user, max_members=20,
    )
    CircleMembership.objects.create(circle=c, user=admin_user, role="admin")
    return c


@pytest.fixture
def private_circle(db, admin_user):
    c = Circle.objects.create(
        name="Private Circle", description="Private desc", category="education",
        is_public=False, creator=admin_user, max_members=10,
    )
    CircleMembership.objects.create(circle=c, user=admin_user, role="admin")
    return c


@pytest.fixture
def member_membership(db, circle, member_user):
    return CircleMembership.objects.create(circle=circle, user=member_user, role="member")


@pytest.fixture
def post(db, circle, admin_user):
    return CirclePost.objects.create(
        circle=circle, author=admin_user, content="Hello world",
    )


@pytest.fixture
def challenge(db, circle, admin_user):
    ch = CircleChallenge.objects.create(
        circle=circle, creator=admin_user,
        title="Test Challenge", description="Desc",
        challenge_type="tasks_completed", target_value=10,
        start_date=timezone.now() - timedelta(hours=1),
        end_date=timezone.now() + timedelta(days=7),
        status="active",
    )
    return ch


# ── Circle CRUD ──────────────────────────────────────────────────────

class TestCircleCreate:
    def test_create_success(self, admin_client, admin_user):
        resp = admin_client.post("/api/v1/circles/circles/", {
            "name": "New Circle", "description": "A new circle",
            "category": "health", "is_public": True,
        })
        assert resp.status_code == 201
        assert Circle.objects.filter(name="New Circle").exists()

    def test_create_auto_admin_membership(self, admin_client, admin_user):
        resp = admin_client.post("/api/v1/circles/circles/", {
            "name": "Auto Admin", "category": "fitness",
        })
        assert resp.status_code == 201
        circle = Circle.objects.get(name="Auto Admin")
        assert CircleMembership.objects.filter(
            circle=circle, user=admin_user, role="admin"
        ).exists()


class TestCircleRetrieve:
    def test_retrieve_public(self, admin_client, circle):
        resp = admin_client.get(f"/api/v1/circles/circles/{circle.id}/")
        assert resp.status_code == 200

    def test_retrieve_private_non_member(self, outsider_client, private_circle):
        resp = outsider_client.get(f"/api/v1/circles/circles/{private_circle.id}/")
        assert resp.status_code == 403


class TestCircleList:
    def test_list_my(self, admin_client, circle):
        resp = admin_client.get("/api/v1/circles/circles/?filter=my")
        assert resp.status_code == 200

    def test_list_public(self, admin_client, circle):
        resp = admin_client.get("/api/v1/circles/circles/?filter=public")
        assert resp.status_code == 200

    def test_list_recommended(self, outsider_client, circle):
        resp = outsider_client.get("/api/v1/circles/circles/?filter=recommended")
        assert resp.status_code == 200


class TestCircleUpdate:
    def test_update_as_admin(self, admin_client, circle):
        resp = admin_client.put(
            f"/api/v1/circles/circles/{circle.id}/",
            {"name": "Updated Name", "description": "Updated"},
            format="json",
        )
        assert resp.status_code == 200

    def test_update_as_member_denied(self, member_client, circle, member_membership):
        resp = member_client.put(
            f"/api/v1/circles/circles/{circle.id}/",
            {"name": "Nope"},
            format="json",
        )
        assert resp.status_code == 403


class TestCircleDelete:
    def test_delete_as_admin(self, admin_client, circle):
        resp = admin_client.delete(f"/api/v1/circles/circles/{circle.id}/")
        assert resp.status_code == 204

    def test_delete_as_member_denied(self, member_client, circle, member_membership):
        resp = member_client.delete(f"/api/v1/circles/circles/{circle.id}/")
        assert resp.status_code == 403


# ── Join / Leave ─────────────────────────────────────────────────────

class TestJoinLeave:
    def test_join_public(self, outsider_client, circle):
        resp = outsider_client.post(f"/api/v1/circles/circles/{circle.id}/join/")
        assert resp.status_code == 200

    def test_join_private_denied(self, outsider_client, private_circle):
        resp = outsider_client.post(f"/api/v1/circles/circles/{private_circle.id}/join/")
        assert resp.status_code == 403

    def test_join_already_member(self, admin_client, circle):
        resp = admin_client.post(f"/api/v1/circles/circles/{circle.id}/join/")
        assert resp.status_code == 400

    def test_join_full_circle(self, outsider_client, db, admin_user):
        c = Circle.objects.create(
            name="Full", description="Full", category="other",
            is_public=True, creator=admin_user, max_members=1,
        )
        CircleMembership.objects.create(circle=c, user=admin_user, role="admin")
        resp = outsider_client.post(f"/api/v1/circles/circles/{c.id}/join/")
        assert resp.status_code == 400

    def test_leave(self, member_client, circle, member_membership):
        resp = member_client.post(f"/api/v1/circles/circles/{circle.id}/leave/")
        assert resp.status_code == 200

    def test_leave_not_member(self, outsider_client, circle):
        resp = outsider_client.post(f"/api/v1/circles/circles/{circle.id}/leave/")
        assert resp.status_code == 400

    def test_leave_last_admin_auto_transfer(self, admin_client, circle, member_membership):
        # Admin leaves, member should become admin
        resp = admin_client.post(f"/api/v1/circles/circles/{circle.id}/leave/")
        assert resp.status_code == 200
        member_membership.refresh_from_db()
        assert member_membership.role == "admin"


# ── Feed & Posts ─────────────────────────────────────────────────────

class TestFeedPosts:
    def test_feed(self, admin_client, circle, post):
        resp = admin_client.get(f"/api/v1/circles/circles/{circle.id}/feed/")
        assert resp.status_code == 200

    def test_feed_non_member_denied(self, outsider_client, circle):
        resp = outsider_client.get(f"/api/v1/circles/circles/{circle.id}/feed/")
        assert resp.status_code == 403

    def test_create_post(self, admin_client, circle):
        resp = admin_client.post(
            f"/api/v1/circles/circles/{circle.id}/posts/",
            {"content": "New post"},
        )
        assert resp.status_code == 201

    def test_create_post_non_member_denied(self, outsider_client, circle):
        resp = outsider_client.post(
            f"/api/v1/circles/circles/{circle.id}/posts/",
            {"content": "Nope"},
        )
        assert resp.status_code == 403

    def test_edit_post(self, admin_client, circle, post):
        resp = admin_client.put(
            f"/api/v1/circles/circles/{circle.id}/posts/{post.id}/edit/",
            {"content": "Updated content"},
        )
        assert resp.status_code == 200
        post.refresh_from_db()
        assert post.content == "Updated content"

    def test_delete_post(self, admin_client, circle, post):
        resp = admin_client.delete(
            f"/api/v1/circles/circles/{circle.id}/posts/{post.id}/delete/",
        )
        assert resp.status_code == 204

    def test_edit_post_non_author_non_mod(self, member_client, circle, post, member_membership):
        # member_membership is role=member, post author is admin
        resp = member_client.put(
            f"/api/v1/circles/circles/{circle.id}/posts/{post.id}/edit/",
            {"content": "Hack"},
        )
        assert resp.status_code == 403

    def test_create_post_with_poll(self, admin_client, circle):
        resp = admin_client.post(
            f"/api/v1/circles/circles/{circle.id}/posts/",
            {
                "content": "Post with poll",
                "poll": {
                    "question": "Favorite color?",
                    "options": [{"text": "Red"}, {"text": "Blue"}],
                    "allows_multiple": False,
                },
            },
            format="json",
        )
        assert resp.status_code == 201
        # Verify poll was created
        post_obj = CirclePost.objects.order_by("-created_at").first()
        assert hasattr(post_obj, "poll")
        assert post_obj.poll.question == "Favorite color?"
        assert post_obj.poll.options.count() == 2


# ── Reactions ────────────────────────────────────────────────────────

class TestReactions:
    def test_react(self, admin_client, circle, post):
        resp = admin_client.post(
            f"/api/v1/circles/circles/{circle.id}/posts/{post.id}/react/",
            {"reaction_type": "fire"},
        )
        assert resp.status_code == 201

    def test_react_update(self, admin_client, circle, post):
        admin_client.post(
            f"/api/v1/circles/circles/{circle.id}/posts/{post.id}/react/",
            {"reaction_type": "fire"},
        )
        resp = admin_client.post(
            f"/api/v1/circles/circles/{circle.id}/posts/{post.id}/react/",
            {"reaction_type": "heart"},
        )
        assert resp.status_code == 200

    def test_unreact(self, admin_client, circle, post):
        admin_client.post(
            f"/api/v1/circles/circles/{circle.id}/posts/{post.id}/react/",
            {"reaction_type": "fire"},
        )
        resp = admin_client.delete(
            f"/api/v1/circles/circles/{circle.id}/posts/{post.id}/unreact/",
        )
        assert resp.status_code == 200

    def test_unreact_no_reaction(self, admin_client, circle, post):
        resp = admin_client.delete(
            f"/api/v1/circles/circles/{circle.id}/posts/{post.id}/unreact/",
        )
        assert resp.status_code == 404

    def test_react_non_member(self, outsider_client, circle, post):
        resp = outsider_client.post(
            f"/api/v1/circles/circles/{circle.id}/posts/{post.id}/react/",
            {"reaction_type": "heart"},
        )
        assert resp.status_code == 403


# ── Polls / Votes ────────────────────────────────────────────────────

class TestPollVote:
    @pytest.fixture
    def poll_post(self, db, circle, admin_user):
        p = CirclePost.objects.create(circle=circle, author=admin_user, content="Poll post")
        poll = CirclePoll.objects.create(post=p, question="Choice?", allows_multiple=False)
        opt1 = PollOption.objects.create(poll=poll, text="A", order=0)
        opt2 = PollOption.objects.create(poll=poll, text="B", order=1)
        return p, poll, opt1, opt2

    def test_vote_single(self, admin_client, circle, poll_post):
        p, poll, opt1, opt2 = poll_post
        resp = admin_client.post(
            f"/api/v1/circles/circles/{circle.id}/posts/{p.id}/vote/",
            {"option_ids": [str(opt1.id)]},
            format="json",
        )
        assert resp.status_code == 200

    def test_vote_multiple_on_single_choice_denied(self, admin_client, circle, poll_post):
        p, poll, opt1, opt2 = poll_post
        resp = admin_client.post(
            f"/api/v1/circles/circles/{circle.id}/posts/{p.id}/vote/",
            {"option_ids": [str(opt1.id), str(opt2.id)]},
            format="json",
        )
        assert resp.status_code == 400

    def test_vote_non_member(self, outsider_client, circle, poll_post):
        p, poll, opt1, opt2 = poll_post
        resp = outsider_client.post(
            f"/api/v1/circles/circles/{circle.id}/posts/{p.id}/vote/",
            {"option_ids": [str(opt1.id)]},
            format="json",
        )
        assert resp.status_code == 403


# ── Challenges ───────────────────────────────────────────────────────

class TestChallenges:
    def test_list_challenges(self, admin_client, circle, challenge):
        resp = admin_client.get(f"/api/v1/circles/circles/{circle.id}/challenges/")
        assert resp.status_code == 200

    def test_list_challenges_non_member(self, outsider_client, circle, challenge):
        resp = outsider_client.get(f"/api/v1/circles/circles/{circle.id}/challenges/")
        assert resp.status_code == 403

    def test_create_challenge(self, admin_client, circle):
        resp = admin_client.post(
            f"/api/v1/circles/circles/{circle.id}/challenges/create/",
            {
                "title": "New Challenge",
                "description": "Desc",
                "challenge_type": "tasks_completed",
                "target_value": 5,
                "start_date": (timezone.now() + timedelta(hours=1)).isoformat(),
                "end_date": (timezone.now() + timedelta(days=7)).isoformat(),
            },
            format="json",
        )
        assert resp.status_code == 201

    def test_create_challenge_member_denied(self, member_client, circle, member_membership):
        resp = member_client.post(
            f"/api/v1/circles/circles/{circle.id}/challenges/create/",
            {
                "title": "Nope",
                "challenge_type": "tasks_completed",
                "target_value": 1,
                "start_date": timezone.now().isoformat(),
                "end_date": (timezone.now() + timedelta(days=1)).isoformat(),
            },
            format="json",
        )
        assert resp.status_code == 403

    def test_join_challenge(self, member_client, circle, challenge, member_membership):
        resp = member_client.post(
            f"/api/v1/circles/circles/challenges/{challenge.id}/join/",
        )
        assert resp.status_code == 200

    def test_join_challenge_already_joined(self, admin_client, circle, challenge):
        challenge.participants.add(User.objects.get(email="circle_admin@test.com"))
        resp = admin_client.post(
            f"/api/v1/circles/circles/challenges/{challenge.id}/join/",
        )
        assert resp.status_code == 400

    def test_submit_progress(self, admin_client, circle, challenge):
        challenge.participants.add(User.objects.get(email="circle_admin@test.com"))
        resp = admin_client.post(
            f"/api/v1/circles/circles/{circle.id}/challenges/{challenge.id}/progress/",
            {"progress_value": 5.0, "notes": "Good progress"},
            format="json",
        )
        assert resp.status_code == 201

    def test_challenge_leaderboard(self, admin_client, circle, challenge):
        challenge.participants.add(User.objects.get(email="circle_admin@test.com"))
        ChallengeProgress.objects.create(
            challenge=challenge,
            user=User.objects.get(email="circle_admin@test.com"),
            progress_value=10.0,
        )
        resp = admin_client.get(
            f"/api/v1/circles/circles/{circle.id}/challenges/{challenge.id}/leaderboard/",
        )
        assert resp.status_code == 200
        assert "leaderboard" in resp.data


# ── Members management ───────────────────────────────────────────────

class TestMembersManagement:
    def test_promote(self, admin_client, circle, member_membership):
        resp = admin_client.post(
            f"/api/v1/circles/circles/{circle.id}/members/{member_membership.id}/promote/",
        )
        assert resp.status_code == 200
        member_membership.refresh_from_db()
        assert member_membership.role == "moderator"

    def test_promote_non_admin_denied(self, member_client, circle, member_membership):
        resp = member_client.post(
            f"/api/v1/circles/circles/{circle.id}/members/{member_membership.id}/promote/",
        )
        assert resp.status_code == 403

    def test_demote(self, admin_client, circle, member_membership):
        # First promote to moderator
        member_membership.role = "moderator"
        member_membership.save()
        resp = admin_client.post(
            f"/api/v1/circles/circles/{circle.id}/members/{member_membership.id}/demote/",
        )
        assert resp.status_code == 200
        member_membership.refresh_from_db()
        assert member_membership.role == "member"

    def test_demote_non_moderator_fails(self, admin_client, circle, member_membership):
        resp = admin_client.post(
            f"/api/v1/circles/circles/{circle.id}/members/{member_membership.id}/demote/",
        )
        assert resp.status_code == 400

    def test_remove(self, admin_client, circle, member_membership):
        resp = admin_client.delete(
            f"/api/v1/circles/circles/{circle.id}/members/{member_membership.id}/remove/",
        )
        assert resp.status_code == 200

    def test_remove_admin_denied(self, admin_client, circle, admin_user):
        admin_ms = CircleMembership.objects.get(circle=circle, user=admin_user)
        # Create another admin client to try removing
        other_admin = _make_pro_user("other_admin@test.com", "OtherAdmin")
        CircleMembership.objects.create(circle=circle, user=other_admin, role="admin")
        oc = _client(other_admin)
        resp = oc.delete(
            f"/api/v1/circles/circles/{circle.id}/members/{admin_ms.id}/remove/",
        )
        assert resp.status_code == 400


# ── Invitations ──────────────────────────────────────────────────────

class TestInvitations:
    def test_invite_user(self, admin_client, circle, outsider_user):
        resp = admin_client.post(
            f"/api/v1/circles/circles/{circle.id}/invite/",
            {"user_id": str(outsider_user.id)},
        )
        assert resp.status_code == 201

    def test_invite_already_member(self, admin_client, circle, member_user, member_membership):
        resp = admin_client.post(
            f"/api/v1/circles/circles/{circle.id}/invite/",
            {"user_id": str(member_user.id)},
        )
        assert resp.status_code == 400

    def test_invite_link(self, admin_client, circle):
        resp = admin_client.post(f"/api/v1/circles/circles/{circle.id}/invite-link/")
        assert resp.status_code == 201
        assert "invite_code" in resp.data

    def test_list_invitations(self, admin_client, circle, outsider_user):
        # First create an invitation
        admin_client.post(
            f"/api/v1/circles/circles/{circle.id}/invite/",
            {"user_id": str(outsider_user.id)},
        )
        resp = admin_client.get(f"/api/v1/circles/circles/{circle.id}/invitations/")
        assert resp.status_code == 200

    def test_join_by_invite_code(self, admin_client, outsider_client, circle, outsider_user):
        # Generate invite link
        invite_resp = admin_client.post(f"/api/v1/circles/circles/{circle.id}/invite-link/")
        code = invite_resp.data["invite_code"]
        resp = outsider_client.post(f"/api/v1/circles/circles/join/{code}/")
        assert resp.status_code == 200

    def test_my_invitations(self, admin_client, outsider_client, circle, outsider_user):
        admin_client.post(
            f"/api/v1/circles/circles/{circle.id}/invite/",
            {"user_id": str(outsider_user.id)},
        )
        resp = outsider_client.get("/api/v1/circles/circles/my-invitations/")
        assert resp.status_code == 200


# ── Chat ─────────────────────────────────────────────────────────────

class TestCircleChat:
    def test_chat_history(self, admin_client, circle):
        resp = admin_client.get(f"/api/v1/circles/circles/{circle.id}/chat/")
        assert resp.status_code == 200

    def test_chat_send(self, admin_client, circle):
        resp = admin_client.post(
            f"/api/v1/circles/circles/{circle.id}/chat/send/",
            {"content": "Hello circle!"},
        )
        assert resp.status_code == 201

    def test_chat_send_empty(self, admin_client, circle):
        resp = admin_client.post(
            f"/api/v1/circles/circles/{circle.id}/chat/send/",
            {"content": ""},
        )
        assert resp.status_code == 400

    def test_chat_non_member(self, outsider_client, circle):
        resp = outsider_client.get(f"/api/v1/circles/circles/{circle.id}/chat/")
        assert resp.status_code == 403


# ── Calls ────────────────────────────────────────────────────────────

class TestCircleCalls:
    def test_start_call(self, admin_client, circle):
        resp = admin_client.post(
            f"/api/v1/circles/circles/{circle.id}/call/start/",
            {"call_type": "voice"},
        )
        assert resp.status_code == 201
        assert "call_id" in resp.data

    def test_start_call_duplicate(self, admin_client, circle):
        admin_client.post(
            f"/api/v1/circles/circles/{circle.id}/call/start/",
            {"call_type": "voice"},
        )
        resp = admin_client.post(
            f"/api/v1/circles/circles/{circle.id}/call/start/",
            {"call_type": "voice"},
        )
        assert resp.status_code == 400

    def test_join_call(self, admin_client, member_client, circle, member_membership):
        admin_client.post(
            f"/api/v1/circles/circles/{circle.id}/call/start/",
            {"call_type": "voice"},
        )
        resp = member_client.post(f"/api/v1/circles/circles/{circle.id}/call/join/")
        assert resp.status_code == 200

    def test_leave_call(self, admin_client, circle):
        admin_client.post(
            f"/api/v1/circles/circles/{circle.id}/call/start/",
            {"call_type": "voice"},
        )
        resp = admin_client.post(f"/api/v1/circles/circles/{circle.id}/call/leave/")
        assert resp.status_code == 200

    def test_end_call(self, admin_client, circle):
        admin_client.post(
            f"/api/v1/circles/circles/{circle.id}/call/start/",
            {"call_type": "voice"},
        )
        resp = admin_client.post(f"/api/v1/circles/circles/{circle.id}/call/end/")
        assert resp.status_code == 200

    def test_active_call(self, admin_client, circle):
        resp = admin_client.get(f"/api/v1/circles/circles/{circle.id}/call/active/")
        assert resp.status_code == 200
        assert resp.data["active_call"] is None

    def test_active_call_exists(self, admin_client, circle):
        admin_client.post(
            f"/api/v1/circles/circles/{circle.id}/call/start/",
            {"call_type": "video"},
        )
        resp = admin_client.get(f"/api/v1/circles/circles/{circle.id}/call/active/")
        assert resp.status_code == 200
        assert resp.data["active_call"] is not None

    def test_no_active_call_join(self, member_client, circle, member_membership):
        resp = member_client.post(f"/api/v1/circles/circles/{circle.id}/call/join/")
        assert resp.status_code == 404

    def test_end_call_non_initiator_non_admin(self, member_client, admin_client, circle, member_membership):
        admin_client.post(
            f"/api/v1/circles/circles/{circle.id}/call/start/",
            {"call_type": "voice"},
        )
        resp = member_client.post(f"/api/v1/circles/circles/{circle.id}/call/end/")
        assert resp.status_code == 403


# ── Permission checks ────────────────────────────────────────────────

class TestCirclePermissions:
    def test_unauthenticated(self, db):
        client = APIClient()
        resp = client.get("/api/v1/circles/circles/")
        assert resp.status_code == 401

    def test_free_user_denied(self, db):
        user = User.objects.create_user(
            email="freecircle@test.com", password="testpass123", display_name="FreeCircle",
        )
        plan, _ = SubscriptionPlan.objects.get_or_create(
            slug="free",
            defaults={"name": "Free", "price_monthly": Decimal("0.00"), "has_circles": False},
        )
        Subscription.objects.update_or_create(
            user=user, defaults={"plan": plan, "status": "active"},
        )
        c = _client(user)
        resp = c.get("/api/v1/circles/circles/")
        assert resp.status_code == 403
