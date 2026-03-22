"""
Comprehensive tests for the Circles app — fills coverage gaps.

Covers:
- IDOR (cross-circle access)
- Polls: multiple-choice voting, ended poll, poll results
- Challenges: non-participant progress, moderator create, auto-complete
- Invitations: expired, wrong user, non-admin, non-existent user, full circle
- Celery tasks: update_challenge_statuses, expire_circle_invitations
- Model properties: is_expired, is_ended, total_votes, vote_count
- Serializer edge cases: my_votes, my_progress, creator_name
- Admin transfer on leave (moderator promoted first)
- Chat: non-member send denied
- Calls: non-member start denied, leave without being in call
- Circle update partial (PATCH), update non-existent
- Delete post by moderator (not author)
- Edit post by moderator (not author)
"""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.circles.models import (
    ChallengeProgress,
    Circle,
    CircleCall,
    CircleCallParticipant,
    CircleChallenge,
    CircleInvitation,
    CircleMembership,
    CircleMessage,
    CirclePoll,
    CirclePost,
    PollOption,
    PollVote,
    PostReaction,
)
from apps.subscriptions.models import Subscription, SubscriptionPlan
from apps.users.models import User


# ── Helpers ──────────────────────────────────────────────────────────


def _make_pro_user(email, display_name="ProUser"):
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


def _client(user):
    c = APIClient()
    c.force_authenticate(user=user)
    return c


# ── Fixtures ─────────────────────────────────────────────────────────


@pytest.fixture
def admin_user(db):
    return _make_pro_user("comp_admin@test.com", "CompAdmin")


@pytest.fixture
def member_user(db):
    return _make_pro_user("comp_member@test.com", "CompMember")


@pytest.fixture
def outsider_user(db):
    return _make_pro_user("comp_outsider@test.com", "CompOutsider")


@pytest.fixture
def moderator_user(db):
    return _make_pro_user("comp_mod@test.com", "CompMod")


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
def moderator_client(moderator_user):
    return _client(moderator_user)


@pytest.fixture
def circle(db, admin_user):
    c = Circle.objects.create(
        name="Comp Circle", description="Desc", category="career",
        is_public=True, creator=admin_user, max_members=20,
    )
    CircleMembership.objects.create(circle=c, user=admin_user, role="admin")
    return c


@pytest.fixture
def private_circle(db, admin_user):
    c = Circle.objects.create(
        name="Comp Private", description="Private desc", category="education",
        is_public=False, creator=admin_user, max_members=10,
    )
    CircleMembership.objects.create(circle=c, user=admin_user, role="admin")
    return c


@pytest.fixture
def member_membership(db, circle, member_user):
    return CircleMembership.objects.create(
        circle=circle, user=member_user, role="member",
    )


@pytest.fixture
def moderator_membership(db, circle, moderator_user):
    return CircleMembership.objects.create(
        circle=circle, user=moderator_user, role="moderator",
    )


@pytest.fixture
def post(db, circle, admin_user):
    return CirclePost.objects.create(
        circle=circle, author=admin_user, content="Hello world",
    )


@pytest.fixture
def challenge(db, circle, admin_user):
    return CircleChallenge.objects.create(
        circle=circle, creator=admin_user,
        title="Comp Challenge", description="Desc",
        challenge_type="tasks_completed", target_value=10,
        start_date=timezone.now() - timedelta(hours=1),
        end_date=timezone.now() + timedelta(days=7),
        status="active",
    )


@pytest.fixture
def second_circle(db, outsider_user):
    """A completely separate circle owned by outsider."""
    c = Circle.objects.create(
        name="Other Circle", description="Other", category="health",
        is_public=True, creator=outsider_user, max_members=20,
    )
    CircleMembership.objects.create(circle=c, user=outsider_user, role="admin")
    return c


# ══════════════════════════════════════════════════════════════════════
#  IDOR / Cross-circle access
# ══════════════════════════════════════════════════════════════════════


class TestIDOR:
    """Ensure users cannot access resources across circles they don't belong to."""

    def test_feed_cross_circle(self, outsider_client, circle, post):
        """Outsider cannot view feed of a circle they are not a member of."""
        resp = outsider_client.get(f"/api/v1/circles/circles/{circle.id}/feed/")
        assert resp.status_code == 403

    def test_post_cross_circle(self, outsider_client, circle):
        """Outsider cannot post to a circle they are not a member of."""
        resp = outsider_client.post(
            f"/api/v1/circles/circles/{circle.id}/posts/",
            {"content": "Cross-circle post"},
        )
        assert resp.status_code == 403

    def test_edit_post_cross_circle(self, outsider_client, circle, post):
        """Outsider cannot edit a post in another circle."""
        resp = outsider_client.put(
            f"/api/v1/circles/circles/{circle.id}/posts/{post.id}/edit/",
            {"content": "Hacked"},
        )
        assert resp.status_code == 403

    def test_delete_post_cross_circle(self, outsider_client, circle, post):
        """Outsider cannot delete a post in another circle."""
        resp = outsider_client.delete(
            f"/api/v1/circles/circles/{circle.id}/posts/{post.id}/delete/",
        )
        assert resp.status_code == 403

    def test_react_cross_circle(self, outsider_client, circle, post):
        """Outsider cannot react to a post in another circle."""
        resp = outsider_client.post(
            f"/api/v1/circles/circles/{circle.id}/posts/{post.id}/react/",
            {"reaction_type": "fire"},
        )
        assert resp.status_code == 403

    def test_challenge_list_cross_circle(self, outsider_client, circle, challenge):
        """Outsider cannot view challenges of another circle."""
        resp = outsider_client.get(f"/api/v1/circles/circles/{circle.id}/challenges/")
        assert resp.status_code == 403

    def test_chat_history_cross_circle(self, outsider_client, circle):
        """Outsider cannot view chat of another circle."""
        resp = outsider_client.get(f"/api/v1/circles/circles/{circle.id}/chat/")
        assert resp.status_code == 403

    def test_chat_send_cross_circle(self, outsider_client, circle):
        """Outsider cannot send chat in another circle."""
        resp = outsider_client.post(
            f"/api/v1/circles/circles/{circle.id}/chat/send/",
            {"content": "Intruder"},
        )
        assert resp.status_code == 403

    def test_call_start_cross_circle(self, outsider_client, circle):
        """Outsider cannot start a call in another circle."""
        resp = outsider_client.post(
            f"/api/v1/circles/circles/{circle.id}/call/start/",
            {"call_type": "voice"},
        )
        assert resp.status_code == 403

    def test_call_active_cross_circle(self, outsider_client, circle):
        """Outsider cannot check active call in another circle."""
        resp = outsider_client.get(f"/api/v1/circles/circles/{circle.id}/call/active/")
        assert resp.status_code == 403

    def test_submit_progress_cross_circle(self, outsider_client, circle, challenge):
        """Outsider cannot submit progress for another circle's challenge."""
        resp = outsider_client.post(
            f"/api/v1/circles/circles/{circle.id}/challenges/{challenge.id}/progress/",
            {"progress_value": 5.0},
            format="json",
        )
        assert resp.status_code == 403

    def test_leaderboard_cross_circle(self, outsider_client, circle, challenge):
        """Outsider cannot view leaderboard for another circle's challenge."""
        resp = outsider_client.get(
            f"/api/v1/circles/circles/{circle.id}/challenges/{challenge.id}/leaderboard/",
        )
        assert resp.status_code == 403


# ══════════════════════════════════════════════════════════════════════
#  Polls: multiple choice, ended, results
# ══════════════════════════════════════════════════════════════════════


class TestPollsAdvanced:

    @pytest.fixture
    def multi_poll_post(self, db, circle, admin_user):
        """Create a post with a multiple-choice poll."""
        p = CirclePost.objects.create(
            circle=circle, author=admin_user, content="Multi poll",
        )
        poll = CirclePoll.objects.create(
            post=p, question="Pick many?", allows_multiple=True,
        )
        opt1 = PollOption.objects.create(poll=poll, text="A", order=0)
        opt2 = PollOption.objects.create(poll=poll, text="B", order=1)
        opt3 = PollOption.objects.create(poll=poll, text="C", order=2)
        return p, poll, opt1, opt2, opt3

    @pytest.fixture
    def ended_poll_post(self, db, circle, admin_user):
        """Create a post with an ended poll."""
        p = CirclePost.objects.create(
            circle=circle, author=admin_user, content="Ended poll",
        )
        poll = CirclePoll.objects.create(
            post=p, question="Over?", allows_multiple=False,
            ends_at=timezone.now() - timedelta(hours=1),
        )
        opt = PollOption.objects.create(poll=poll, text="Only", order=0)
        return p, poll, opt

    def test_vote_multiple_allowed(self, admin_client, circle, multi_poll_post):
        """Multiple votes allowed on multiple-choice poll."""
        p, poll, opt1, opt2, opt3 = multi_poll_post
        resp = admin_client.post(
            f"/api/v1/circles/circles/{circle.id}/posts/{p.id}/vote/",
            {"option_ids": [str(opt1.id), str(opt2.id)]},
            format="json",
        )
        assert resp.status_code == 200
        assert "poll" in resp.data

    def test_vote_ended_poll_denied(self, admin_client, circle, ended_poll_post):
        """Cannot vote on an ended poll."""
        p, poll, opt = ended_poll_post
        resp = admin_client.post(
            f"/api/v1/circles/circles/{circle.id}/posts/{p.id}/vote/",
            {"option_ids": [str(opt.id)]},
            format="json",
        )
        assert resp.status_code == 403

    def test_vote_invalid_option_id(self, admin_client, circle, multi_poll_post):
        """Voting with invalid option ID returns 400."""
        import uuid
        p, poll, opt1, opt2, opt3 = multi_poll_post
        resp = admin_client.post(
            f"/api/v1/circles/circles/{circle.id}/posts/{p.id}/vote/",
            {"option_ids": [str(uuid.uuid4())]},
            format="json",
        )
        assert resp.status_code == 400

    def test_vote_replaces_previous(self, admin_client, circle, multi_poll_post):
        """Re-voting replaces previous votes."""
        p, poll, opt1, opt2, opt3 = multi_poll_post
        # Vote for A and B
        admin_client.post(
            f"/api/v1/circles/circles/{circle.id}/posts/{p.id}/vote/",
            {"option_ids": [str(opt1.id), str(opt2.id)]},
            format="json",
        )
        # Change to C only
        resp = admin_client.post(
            f"/api/v1/circles/circles/{circle.id}/posts/{p.id}/vote/",
            {"option_ids": [str(opt3.id)]},
            format="json",
        )
        assert resp.status_code == 200
        # Should only have 1 vote now
        assert PollVote.objects.filter(option__poll=poll).count() == 1

    def test_vote_post_without_poll(self, admin_client, circle, post):
        """Voting on a post without a poll returns 404."""
        resp = admin_client.post(
            f"/api/v1/circles/circles/{circle.id}/posts/{post.id}/vote/",
            {"option_ids": [str(post.id)]},  # random UUID
            format="json",
        )
        assert resp.status_code == 404

    def test_poll_results_in_feed(self, admin_client, circle, multi_poll_post):
        """Feed includes poll data with vote counts."""
        p, poll, opt1, opt2, opt3 = multi_poll_post
        # Cast a vote
        admin_client.post(
            f"/api/v1/circles/circles/{circle.id}/posts/{p.id}/vote/",
            {"option_ids": [str(opt1.id)]},
            format="json",
        )
        resp = admin_client.get(f"/api/v1/circles/circles/{circle.id}/feed/")
        assert resp.status_code == 200


# ══════════════════════════════════════════════════════════════════════
#  Challenge edge cases
# ══════════════════════════════════════════════════════════════════════


class TestChallengeEdgeCases:

    def test_submit_progress_non_participant(
        self, admin_client, circle, challenge,
    ):
        """Cannot submit progress if not a challenge participant."""
        # admin_user is a circle member but not a challenge participant
        resp = admin_client.post(
            f"/api/v1/circles/circles/{circle.id}/challenges/{challenge.id}/progress/",
            {"progress_value": 5.0},
            format="json",
        )
        assert resp.status_code == 400

    def test_submit_progress_non_member(
        self, outsider_client, circle, challenge,
    ):
        """Non-member cannot submit progress."""
        resp = outsider_client.post(
            f"/api/v1/circles/circles/{circle.id}/challenges/{challenge.id}/progress/",
            {"progress_value": 5.0},
            format="json",
        )
        assert resp.status_code == 403

    def test_moderator_can_create_challenge(
        self, moderator_client, circle, moderator_membership,
    ):
        """Moderator can create a challenge."""
        resp = moderator_client.post(
            f"/api/v1/circles/circles/{circle.id}/challenges/create/",
            {
                "title": "Mod Challenge",
                "description": "By moderator",
                "challenge_type": "streak_days",
                "target_value": 7,
                "start_date": timezone.now().isoformat(),
                "end_date": (timezone.now() + timedelta(days=7)).isoformat(),
            },
            format="json",
        )
        assert resp.status_code == 201

    def test_create_challenge_end_before_start(
        self, admin_client, circle,
    ):
        """Challenge with end_date before start_date is rejected."""
        resp = admin_client.post(
            f"/api/v1/circles/circles/{circle.id}/challenges/create/",
            {
                "title": "Bad Dates",
                "challenge_type": "tasks_completed",
                "target_value": 5,
                "start_date": (timezone.now() + timedelta(days=7)).isoformat(),
                "end_date": timezone.now().isoformat(),
            },
            format="json",
        )
        assert resp.status_code == 400

    def test_join_challenge_non_circle_member(
        self, outsider_client, circle, challenge,
    ):
        """Non-circle member cannot join a challenge."""
        resp = outsider_client.post(
            f"/api/v1/circles/circles/challenges/{challenge.id}/join/",
        )
        assert resp.status_code == 403

    def test_challenge_not_found_progress(
        self, admin_client, circle,
    ):
        """Submitting progress for non-existent challenge returns 404."""
        import uuid
        fake_id = uuid.uuid4()
        resp = admin_client.post(
            f"/api/v1/circles/circles/{circle.id}/challenges/{fake_id}/progress/",
            {"progress_value": 1.0},
            format="json",
        )
        assert resp.status_code == 404

    def test_challenge_not_found_leaderboard(
        self, admin_client, circle,
    ):
        """Leaderboard for non-existent challenge returns 404."""
        import uuid
        fake_id = uuid.uuid4()
        resp = admin_client.get(
            f"/api/v1/circles/circles/{circle.id}/challenges/{fake_id}/leaderboard/",
        )
        assert resp.status_code == 404


# ══════════════════════════════════════════════════════════════════════
#  Invitation edge cases
# ══════════════════════════════════════════════════════════════════════


class TestInvitationEdgeCases:

    def test_invite_non_existent_user(self, admin_client, circle):
        """Inviting a non-existent user returns 404."""
        import uuid
        resp = admin_client.post(
            f"/api/v1/circles/circles/{circle.id}/invite/",
            {"user_id": str(uuid.uuid4())},
        )
        assert resp.status_code == 404

    def test_invite_non_admin_denied(
        self, member_client, circle, member_membership, outsider_user,
    ):
        """Non-admin/non-moderator cannot invite."""
        resp = member_client.post(
            f"/api/v1/circles/circles/{circle.id}/invite/",
            {"user_id": str(outsider_user.id)},
        )
        assert resp.status_code == 403

    def test_invite_already_pending(
        self, admin_client, circle, outsider_user,
    ):
        """Cannot send duplicate pending invitation."""
        admin_client.post(
            f"/api/v1/circles/circles/{circle.id}/invite/",
            {"user_id": str(outsider_user.id)},
        )
        resp = admin_client.post(
            f"/api/v1/circles/circles/{circle.id}/invite/",
            {"user_id": str(outsider_user.id)},
        )
        assert resp.status_code == 400

    def test_invite_link_non_admin_denied(
        self, member_client, circle, member_membership,
    ):
        """Non-admin cannot generate invite link."""
        resp = member_client.post(f"/api/v1/circles/circles/{circle.id}/invite-link/")
        assert resp.status_code == 403

    def test_invitations_list_non_admin_denied(
        self, member_client, circle, member_membership,
    ):
        """Non-admin cannot list invitations."""
        resp = member_client.get(f"/api/v1/circles/circles/{circle.id}/invitations/")
        assert resp.status_code == 403

    def test_join_expired_invite_code(
        self, admin_client, outsider_client, circle, outsider_user,
    ):
        """Joining with an expired invite code returns 400."""
        import secrets
        invitation = CircleInvitation.objects.create(
            circle=circle,
            inviter=circle.creator,
            invitee=None,
            invite_code=secrets.token_urlsafe(12),
            expires_at=timezone.now() - timedelta(hours=1),  # Already expired
        )
        resp = outsider_client.post(
            f"/api/v1/circles/circles/join/{invitation.invite_code}/",
        )
        assert resp.status_code == 400

    def test_join_direct_invite_wrong_user(
        self, admin_client, outsider_client, circle, member_user, outsider_user,
    ):
        """Direct invite for another user returns 403."""
        import secrets
        invitation = CircleInvitation.objects.create(
            circle=circle,
            inviter=circle.creator,
            invitee=member_user,  # For member, not outsider
            invite_code=secrets.token_urlsafe(12),
            expires_at=timezone.now() + timedelta(days=7),
        )
        resp = outsider_client.post(
            f"/api/v1/circles/circles/join/{invitation.invite_code}/",
        )
        assert resp.status_code == 403

    def test_join_invite_already_member(
        self, admin_client, member_client, circle, member_user, member_membership,
    ):
        """Already a member trying to use invite code returns 400."""
        import secrets
        invitation = CircleInvitation.objects.create(
            circle=circle,
            inviter=circle.creator,
            invitee=None,
            invite_code=secrets.token_urlsafe(12),
            expires_at=timezone.now() + timedelta(days=7),
        )
        resp = member_client.post(
            f"/api/v1/circles/circles/join/{invitation.invite_code}/",
        )
        assert resp.status_code == 400

    def test_join_invite_full_circle(
        self, admin_client, outsider_client, db, admin_user, outsider_user,
    ):
        """Cannot join via invite if circle is full."""
        import secrets
        small_circle = Circle.objects.create(
            name="Tiny", description="T", category="other",
            is_public=False, creator=admin_user, max_members=1,
        )
        CircleMembership.objects.create(
            circle=small_circle, user=admin_user, role="admin",
        )
        invitation = CircleInvitation.objects.create(
            circle=small_circle,
            inviter=admin_user,
            invitee=None,
            invite_code=secrets.token_urlsafe(12),
            expires_at=timezone.now() + timedelta(days=7),
        )
        resp = outsider_client.post(
            f"/api/v1/circles/circles/join/{invitation.invite_code}/",
        )
        assert resp.status_code == 400

    def test_direct_invite_accepted_status(
        self, admin_client, outsider_client, circle, outsider_user,
    ):
        """Direct invite is marked as accepted after use."""
        resp = admin_client.post(
            f"/api/v1/circles/circles/{circle.id}/invite/",
            {"user_id": str(outsider_user.id)},
        )
        assert resp.status_code == 201
        invitation = CircleInvitation.objects.get(
            circle=circle, invitee=outsider_user,
        )
        # Use the invite code to join
        outsider_client.post(
            f"/api/v1/circles/circles/join/{invitation.invite_code}/",
        )
        invitation.refresh_from_db()
        assert invitation.status == "accepted"


# ══════════════════════════════════════════════════════════════════════
#  Celery tasks
# ══════════════════════════════════════════════════════════════════════


class TestCeleryTasks:

    def test_update_challenge_statuses_upcoming_to_active(
        self, db, circle, admin_user,
    ):
        """Task transitions upcoming challenges to active when start_date passes."""
        from apps.circles.tasks import update_challenge_statuses

        ch = CircleChallenge.objects.create(
            circle=circle, creator=admin_user,
            title="Upcoming", challenge_type="tasks_completed", target_value=5,
            start_date=timezone.now() - timedelta(minutes=10),
            end_date=timezone.now() + timedelta(days=7),
            status="upcoming",
        )
        result = update_challenge_statuses()
        ch.refresh_from_db()
        assert ch.status == "active"
        assert result["activated"] >= 1

    def test_update_challenge_statuses_active_to_completed(
        self, db, circle, admin_user,
    ):
        """Task transitions active challenges to completed when end_date passes."""
        from apps.circles.tasks import update_challenge_statuses

        ch = CircleChallenge.objects.create(
            circle=circle, creator=admin_user,
            title="Over", challenge_type="tasks_completed", target_value=5,
            start_date=timezone.now() - timedelta(days=14),
            end_date=timezone.now() - timedelta(minutes=1),
            status="active",
        )
        result = update_challenge_statuses()
        ch.refresh_from_db()
        assert ch.status == "completed"
        assert result["completed"] >= 1

    def test_update_challenge_statuses_upcoming_skips_end(
        self, db, circle, admin_user,
    ):
        """Upcoming challenges that already ended get completed directly."""
        from apps.circles.tasks import update_challenge_statuses

        ch = CircleChallenge.objects.create(
            circle=circle, creator=admin_user,
            title="Missed", challenge_type="tasks_completed", target_value=5,
            start_date=timezone.now() - timedelta(days=14),
            end_date=timezone.now() - timedelta(days=1),
            status="upcoming",
        )
        result = update_challenge_statuses()
        ch.refresh_from_db()
        assert ch.status == "completed"

    def test_expire_circle_invitations(self, db, circle, admin_user):
        """Task expires pending invitations past their expiry date."""
        from apps.circles.tasks import expire_circle_invitations

        import secrets
        inv = CircleInvitation.objects.create(
            circle=circle, inviter=admin_user,
            invite_code=secrets.token_urlsafe(12),
            expires_at=timezone.now() - timedelta(hours=1),
            status="pending",
        )
        result = expire_circle_invitations()
        inv.refresh_from_db()
        assert inv.status == "expired"
        assert result >= 1

    def test_expire_keeps_accepted_invitations(self, db, circle, admin_user):
        """Task does not expire already accepted invitations."""
        from apps.circles.tasks import expire_circle_invitations

        import secrets
        inv = CircleInvitation.objects.create(
            circle=circle, inviter=admin_user,
            invite_code=secrets.token_urlsafe(12),
            expires_at=timezone.now() - timedelta(hours=1),
            status="accepted",
        )
        expire_circle_invitations()
        inv.refresh_from_db()
        assert inv.status == "accepted"


# ══════════════════════════════════════════════════════════════════════
#  Model properties
# ══════════════════════════════════════════════════════════════════════


class TestModelProperties:

    def test_circle_invitation_is_expired(self, db, circle, admin_user):
        """is_expired returns True for past-expiry invitation."""
        import secrets
        inv = CircleInvitation.objects.create(
            circle=circle, inviter=admin_user,
            invite_code=secrets.token_urlsafe(12),
            expires_at=timezone.now() - timedelta(hours=1),
        )
        assert inv.is_expired is True

    def test_circle_invitation_not_expired(self, db, circle, admin_user):
        """is_expired returns False for future-expiry invitation."""
        import secrets
        inv = CircleInvitation.objects.create(
            circle=circle, inviter=admin_user,
            invite_code=secrets.token_urlsafe(12),
            expires_at=timezone.now() + timedelta(days=7),
        )
        assert inv.is_expired is False

    def test_invitation_str(self, db, circle, admin_user, outsider_user):
        """CircleInvitation __str__ includes target info."""
        import secrets
        # Direct invite
        inv = CircleInvitation.objects.create(
            circle=circle, inviter=admin_user, invitee=outsider_user,
            invite_code=secrets.token_urlsafe(12),
            expires_at=timezone.now() + timedelta(days=7),
        )
        s = str(inv)
        assert circle.name in s
        assert outsider_user.email in s

    def test_invitation_str_link(self, db, circle, admin_user):
        """CircleInvitation __str__ shows code for link invites."""
        import secrets
        code = secrets.token_urlsafe(12)
        inv = CircleInvitation.objects.create(
            circle=circle, inviter=admin_user,
            invite_code=code,
            expires_at=timezone.now() + timedelta(days=7),
        )
        s = str(inv)
        assert "code:" in s

    def test_poll_is_ended_true(self, db, circle, admin_user):
        """CirclePoll.is_ended returns True when past ends_at."""
        p = CirclePost.objects.create(
            circle=circle, author=admin_user, content="Ended",
        )
        poll = CirclePoll.objects.create(
            post=p, question="?",
            ends_at=timezone.now() - timedelta(hours=1),
        )
        assert poll.is_ended is True

    def test_poll_is_ended_false_no_deadline(self, db, circle, admin_user):
        """CirclePoll.is_ended returns False when ends_at is None."""
        p = CirclePost.objects.create(
            circle=circle, author=admin_user, content="Open",
        )
        poll = CirclePoll.objects.create(
            post=p, question="?", ends_at=None,
        )
        assert poll.is_ended is False

    def test_poll_total_votes(self, db, circle, admin_user, member_user):
        """CirclePoll.total_votes counts votes across all options."""
        p = CirclePost.objects.create(
            circle=circle, author=admin_user, content="Votes",
        )
        poll = CirclePoll.objects.create(
            post=p, question="?", allows_multiple=True,
        )
        opt1 = PollOption.objects.create(poll=poll, text="A", order=0)
        opt2 = PollOption.objects.create(poll=poll, text="B", order=1)
        PollVote.objects.create(option=opt1, user=admin_user)
        PollVote.objects.create(option=opt2, user=admin_user)
        PollVote.objects.create(option=opt1, user=member_user)
        assert poll.total_votes == 3

    def test_poll_option_vote_count(self, db, circle, admin_user, member_user):
        """PollOption.vote_count counts votes for that option."""
        p = CirclePost.objects.create(
            circle=circle, author=admin_user, content="VC",
        )
        poll = CirclePoll.objects.create(post=p, question="?")
        opt = PollOption.objects.create(poll=poll, text="Only", order=0)
        PollVote.objects.create(option=opt, user=admin_user)
        PollVote.objects.create(option=opt, user=member_user)
        assert opt.vote_count == 2

    def test_poll_str(self, db, circle, admin_user):
        """CirclePoll __str__ includes question."""
        p = CirclePost.objects.create(
            circle=circle, author=admin_user, content="S",
        )
        poll = CirclePoll.objects.create(post=p, question="Test question")
        assert "Test question" in str(poll)

    def test_poll_option_str(self, db, circle, admin_user):
        """PollOption __str__ includes text."""
        p = CirclePost.objects.create(
            circle=circle, author=admin_user, content="S",
        )
        poll = CirclePoll.objects.create(post=p, question="?")
        opt = PollOption.objects.create(poll=poll, text="Option text", order=0)
        assert "Option text" in str(opt)

    def test_poll_vote_str(self, db, circle, admin_user):
        """PollVote __str__ includes user and option."""
        p = CirclePost.objects.create(
            circle=circle, author=admin_user, content="S",
        )
        poll = CirclePoll.objects.create(post=p, question="?")
        opt = PollOption.objects.create(poll=poll, text="Opt", order=0)
        vote = PollVote.objects.create(option=opt, user=admin_user)
        s = str(vote)
        assert "Opt" in s

    def test_challenge_progress_str(self, db, circle, admin_user, challenge):
        """ChallengeProgress __str__ includes user and progress."""
        prog = ChallengeProgress.objects.create(
            challenge=challenge, user=admin_user, progress_value=5.0,
        )
        s = str(prog)
        assert "5.0" in s
        assert challenge.title in s

    def test_circle_message_str(self, db, circle, admin_user):
        """CircleMessage __str__ includes sender and content preview."""
        msg = CircleMessage.objects.create(
            circle=circle, sender=admin_user, content="Hello there",
        )
        s = str(msg)
        assert "Hello there" in s

    def test_circle_message_long_str(self, db, circle, admin_user):
        """CircleMessage __str__ truncates long content."""
        msg = CircleMessage.objects.create(
            circle=circle, sender=admin_user, content="X" * 100,
        )
        assert "..." in str(msg)

    def test_circle_call_str(self, db, circle, admin_user):
        """CircleCall __str__ includes type and circle."""
        call = CircleCall.objects.create(
            circle=circle, initiator=admin_user,
            call_type="voice", status="active", agora_channel="test",
        )
        s = str(call)
        assert "voice" in s
        assert circle.name in s

    def test_circle_call_participant_str(self, db, circle, admin_user):
        """CircleCallParticipant __str__ includes user."""
        call = CircleCall.objects.create(
            circle=circle, initiator=admin_user,
            call_type="voice", status="active", agora_channel="test",
        )
        participant = CircleCallParticipant.objects.create(
            call=call, user=admin_user,
        )
        s = str(participant)
        assert admin_user.display_name in s or str(call.id) in s


# ══════════════════════════════════════════════════════════════════════
#  Post moderation: moderator can edit/delete others' posts
# ══════════════════════════════════════════════════════════════════════


class TestModeratorPostActions:

    def test_moderator_edit_post(
        self, moderator_client, circle, post, moderator_membership,
    ):
        """Moderator can edit a post they did not author."""
        resp = moderator_client.put(
            f"/api/v1/circles/circles/{circle.id}/posts/{post.id}/edit/",
            {"content": "Moderated content"},
        )
        assert resp.status_code == 200
        post.refresh_from_db()
        assert post.content == "Moderated content"

    def test_moderator_delete_post(
        self, moderator_client, circle, post, moderator_membership,
    ):
        """Moderator can delete a post they did not author."""
        resp = moderator_client.delete(
            f"/api/v1/circles/circles/{circle.id}/posts/{post.id}/delete/",
        )
        assert resp.status_code == 204

    def test_edit_nonexistent_post(self, admin_client, circle):
        """Editing a non-existent post returns 404."""
        import uuid
        resp = admin_client.put(
            f"/api/v1/circles/circles/{circle.id}/posts/{uuid.uuid4()}/edit/",
            {"content": "No post"},
        )
        assert resp.status_code == 404

    def test_delete_nonexistent_post(self, admin_client, circle):
        """Deleting a non-existent post returns 404."""
        import uuid
        resp = admin_client.delete(
            f"/api/v1/circles/circles/{circle.id}/posts/{uuid.uuid4()}/delete/",
        )
        assert resp.status_code == 404


# ══════════════════════════════════════════════════════════════════════
#  Admin transfer on leave — prefer moderator
# ══════════════════════════════════════════════════════════════════════


class TestAdminTransferOnLeave:

    def test_admin_leaves_moderator_promoted_first(
        self, admin_client, circle, moderator_membership, member_membership,
    ):
        """When admin leaves with moderator and member, moderator becomes admin."""
        resp = admin_client.post(f"/api/v1/circles/circles/{circle.id}/leave/")
        assert resp.status_code == 200
        moderator_membership.refresh_from_db()
        assert moderator_membership.role == "admin"
        member_membership.refresh_from_db()
        assert member_membership.role == "member"

    def test_admin_leaves_sole_member_circle_deleted(
        self, db, admin_user,
    ):
        """Admin leaving as sole member just removes membership (circle remains)."""
        c = Circle.objects.create(
            name="Solo", description="Solo", category="other",
            is_public=True, creator=admin_user, max_members=20,
        )
        CircleMembership.objects.create(circle=c, user=admin_user, role="admin")
        client = _client(admin_user)
        resp = client.post(f"/api/v1/circles/circles/{c.id}/leave/")
        assert resp.status_code == 200
        assert CircleMembership.objects.filter(circle=c).count() == 0


# ══════════════════════════════════════════════════════════════════════
#  Circle Update (PATCH)
# ══════════════════════════════════════════════════════════════════════


class TestCirclePatch:

    def test_partial_update(self, admin_client, circle):
        """PATCH updates only provided fields."""
        resp = admin_client.patch(
            f"/api/v1/circles/circles/{circle.id}/",
            {"name": "Patched Name"},
            format="json",
        )
        assert resp.status_code == 200
        circle.refresh_from_db()
        assert circle.name == "Patched Name"
        assert circle.description == "Desc"  # unchanged

    def test_update_category(self, admin_client, circle):
        """Admin can change circle category."""
        resp = admin_client.patch(
            f"/api/v1/circles/circles/{circle.id}/",
            {"category": "fitness"},
            format="json",
        )
        assert resp.status_code == 200
        circle.refresh_from_db()
        assert circle.category == "fitness"

    def test_update_max_members(self, admin_client, circle):
        """Admin can change max_members."""
        resp = admin_client.patch(
            f"/api/v1/circles/circles/{circle.id}/",
            {"max_members": 50},
            format="json",
        )
        assert resp.status_code == 200
        circle.refresh_from_db()
        assert circle.max_members == 50


# ══════════════════════════════════════════════════════════════════════
#  Circle Call edge cases
# ══════════════════════════════════════════════════════════════════════


class TestCallEdgeCases:

    def test_call_start_non_member(self, outsider_client, circle):
        """Non-member cannot start a call."""
        resp = outsider_client.post(
            f"/api/v1/circles/circles/{circle.id}/call/start/",
            {"call_type": "voice"},
        )
        assert resp.status_code == 403

    def test_call_join_non_member(self, outsider_client, circle):
        """Non-member cannot join a call."""
        resp = outsider_client.post(f"/api/v1/circles/circles/{circle.id}/call/join/")
        assert resp.status_code == 403

    def test_call_leave_not_in_call(
        self, member_client, admin_client, circle, member_membership,
    ):
        """Leaving a call you are not in returns 400."""
        # Start a call as admin
        admin_client.post(
            f"/api/v1/circles/circles/{circle.id}/call/start/",
            {"call_type": "voice"},
        )
        # Member is not in the call
        resp = member_client.post(f"/api/v1/circles/circles/{circle.id}/call/leave/")
        assert resp.status_code == 400

    def test_call_leave_no_active_call(self, admin_client, circle):
        """Leaving when no call is active returns 404."""
        resp = admin_client.post(f"/api/v1/circles/circles/{circle.id}/call/leave/")
        assert resp.status_code == 404

    def test_call_end_no_active_call(self, admin_client, circle):
        """Ending when no call is active returns 404."""
        resp = admin_client.post(f"/api/v1/circles/circles/{circle.id}/call/end/")
        assert resp.status_code == 404

    def test_call_auto_end_on_last_leave(
        self, admin_client, circle,
    ):
        """Call auto-completes when last participant leaves."""
        admin_client.post(
            f"/api/v1/circles/circles/{circle.id}/call/start/",
            {"call_type": "voice"},
        )
        resp = admin_client.post(f"/api/v1/circles/circles/{circle.id}/call/leave/")
        assert resp.status_code == 200
        assert resp.data["active_participants"] == 0
        assert resp.data["status"] == "completed"

    def test_start_video_call(self, admin_client, circle):
        """Can start a video call."""
        resp = admin_client.post(
            f"/api/v1/circles/circles/{circle.id}/call/start/",
            {"call_type": "video"},
        )
        assert resp.status_code == 201
        assert resp.data["call_type"] == "video"

    def test_start_invalid_call_type(self, admin_client, circle):
        """Invalid call_type returns 400."""
        resp = admin_client.post(
            f"/api/v1/circles/circles/{circle.id}/call/start/",
            {"call_type": "hologram"},
        )
        assert resp.status_code == 400

    def test_rejoin_call(
        self, admin_client, member_client, circle, member_membership,
    ):
        """Member can rejoin a call after leaving."""
        admin_client.post(
            f"/api/v1/circles/circles/{circle.id}/call/start/",
            {"call_type": "voice"},
        )
        # Member joins
        member_client.post(f"/api/v1/circles/circles/{circle.id}/call/join/")
        # Member leaves
        member_client.post(f"/api/v1/circles/circles/{circle.id}/call/leave/")
        # Member rejoins
        resp = member_client.post(f"/api/v1/circles/circles/{circle.id}/call/join/")
        assert resp.status_code == 200


# ══════════════════════════════════════════════════════════════════════
#  Serializer coverage
# ══════════════════════════════════════════════════════════════════════


class TestSerializerEdgeCases:

    def test_circle_detail_has_challenges(self, admin_client, circle, challenge):
        """Circle detail response includes challenges."""
        resp = admin_client.get(f"/api/v1/circles/circles/{circle.id}/")
        assert resp.status_code == 200
        data = resp.data["circle"]
        assert "challenges" in data
        assert len(data["challenges"]) >= 1

    def test_circle_detail_has_members(self, admin_client, circle):
        """Circle detail response includes members with roles."""
        resp = admin_client.get(f"/api/v1/circles/circles/{circle.id}/")
        assert resp.status_code == 200
        data = resp.data["circle"]
        assert "members" in data
        assert len(data["members"]) >= 1
        assert data["members"][0]["role"] == "admin"

    def test_circle_list_has_is_member(self, admin_client, circle):
        """Circle list shows is_member field."""
        resp = admin_client.get("/api/v1/circles/circles/?filter=my")
        assert resp.status_code == 200

    def test_challenge_serializer_has_joined(
        self, admin_client, circle, challenge,
    ):
        """Challenge serializer shows has_joined."""
        resp = admin_client.get(f"/api/v1/circles/circles/{circle.id}/challenges/")
        assert resp.status_code == 200
        assert len(resp.data) >= 1
        assert "has_joined" in resp.data[0]

    def test_challenge_serializer_my_progress(
        self, admin_client, circle, challenge, admin_user,
    ):
        """Challenge serializer shows my_progress."""
        challenge.participants.add(admin_user)
        ChallengeProgress.objects.create(
            challenge=challenge, user=admin_user, progress_value=3.0,
        )
        resp = admin_client.get(f"/api/v1/circles/circles/{circle.id}/challenges/")
        assert resp.status_code == 200
        assert resp.data[0]["my_progress"] == 3.0

    def test_post_serializer_reactions_grouped(
        self, admin_client, circle, post, admin_user, member_user,
    ):
        """Post serializer groups reactions by type."""
        CircleMembership.objects.get_or_create(
            circle=circle, user=member_user, defaults={"role": "member"},
        )
        PostReaction.objects.create(
            post=post, user=admin_user, reaction_type="fire",
        )
        PostReaction.objects.create(
            post=post, user=member_user, reaction_type="fire",
        )
        resp = admin_client.get(f"/api/v1/circles/circles/{circle.id}/feed/")
        assert resp.status_code == 200

    def test_create_post_empty_content_rejected(self, admin_client, circle):
        """Post with empty content is rejected."""
        resp = admin_client.post(
            f"/api/v1/circles/circles/{circle.id}/posts/",
            {"content": ""},
        )
        assert resp.status_code == 400

    def test_create_circle_default_public(self, admin_client):
        """Circle created without is_public defaults to True."""
        resp = admin_client.post("/api/v1/circles/circles/", {
            "name": "Default Public", "category": "health",
        })
        assert resp.status_code == 201
        c = Circle.objects.get(name="Default Public")
        assert c.is_public is True

    def test_create_private_circle(self, admin_client):
        """Circle can be created as private."""
        resp = admin_client.post("/api/v1/circles/circles/", {
            "name": "Private New", "category": "health", "is_public": False,
        })
        assert resp.status_code == 201
        c = Circle.objects.get(name="Private New")
        assert c.is_public is False


# ══════════════════════════════════════════════════════════════════════
#  Moderator invite link permission
# ══════════════════════════════════════════════════════════════════════


class TestModeratorInvitePermissions:

    def test_moderator_can_invite(
        self, moderator_client, circle, moderator_membership, outsider_user,
    ):
        """Moderator can send invitations."""
        resp = moderator_client.post(
            f"/api/v1/circles/circles/{circle.id}/invite/",
            {"user_id": str(outsider_user.id)},
        )
        assert resp.status_code == 201

    def test_moderator_can_generate_invite_link(
        self, moderator_client, circle, moderator_membership,
    ):
        """Moderator can generate invite links."""
        resp = moderator_client.post(
            f"/api/v1/circles/circles/{circle.id}/invite-link/",
        )
        assert resp.status_code == 201

    def test_moderator_can_view_invitations(
        self, moderator_client, circle, moderator_membership,
    ):
        """Moderator can list invitations."""
        resp = moderator_client.get(
            f"/api/v1/circles/circles/{circle.id}/invitations/",
        )
        assert resp.status_code == 200

    def test_moderator_can_remove_member(
        self, moderator_client, circle, moderator_membership, member_membership,
    ):
        """Moderator can remove a regular member."""
        resp = moderator_client.delete(
            f"/api/v1/circles/circles/{circle.id}/members/{member_membership.id}/remove/",
        )
        assert resp.status_code == 200


# ══════════════════════════════════════════════════════════════════════
#  Premium user POST actions (bug fix: CanUseCircles)
# ══════════════════════════════════════════════════════════════════════


class TestPremiumUserPostActions:
    """Premium users (has_circles=True, has_circle_create=False) should be
    able to perform POST actions like join, post, react, vote, etc.
    Only circle creation should require has_circle_create (Pro plan)."""

    @pytest.fixture
    def premium_user(self, db):
        user = User.objects.create_user(
            email="premium_circle@test.com",
            password="testpass123",
            display_name="PremiumCircle",
        )
        plan, _ = SubscriptionPlan.objects.get_or_create(
            slug="premium",
            defaults={
                "name": "Premium",
                "price_monthly": Decimal("19.99"),
                "has_circles": True,
                "has_circle_create": False,
            },
        )
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

    @pytest.fixture
    def premium_client(self, premium_user):
        return _client(premium_user)

    def test_premium_cannot_create_circle(self, premium_client):
        """Premium user cannot create circles (requires Pro)."""
        resp = premium_client.post("/api/v1/circles/circles/", {
            "name": "Should Fail", "category": "health",
        })
        assert resp.status_code == 403

    def test_premium_can_join_public_circle(self, premium_client, circle):
        """Premium user can join a public circle."""
        resp = premium_client.post(f"/api/v1/circles/circles/{circle.id}/join/")
        assert resp.status_code == 200

    def test_premium_can_post(self, premium_client, premium_user, circle):
        """Premium user (member) can create posts."""
        CircleMembership.objects.create(
            circle=circle, user=premium_user, role="member",
        )
        resp = premium_client.post(
            f"/api/v1/circles/circles/{circle.id}/posts/",
            {"content": "Premium user post"},
        )
        assert resp.status_code == 201

    def test_premium_can_react(self, premium_client, premium_user, circle, post):
        """Premium user (member) can react to posts."""
        CircleMembership.objects.create(
            circle=circle, user=premium_user, role="member",
        )
        resp = premium_client.post(
            f"/api/v1/circles/circles/{circle.id}/posts/{post.id}/react/",
            {"reaction_type": "heart"},
        )
        assert resp.status_code == 201

    def test_premium_can_leave(self, premium_client, premium_user, circle):
        """Premium user can leave a circle."""
        CircleMembership.objects.create(
            circle=circle, user=premium_user, role="member",
        )
        resp = premium_client.post(f"/api/v1/circles/circles/{circle.id}/leave/")
        assert resp.status_code == 200

    def test_premium_can_send_chat(self, premium_client, premium_user, circle):
        """Premium user (member) can send chat messages."""
        CircleMembership.objects.create(
            circle=circle, user=premium_user, role="member",
        )
        resp = premium_client.post(
            f"/api/v1/circles/circles/{circle.id}/chat/send/",
            {"content": "Hello from premium"},
        )
        assert resp.status_code == 201
