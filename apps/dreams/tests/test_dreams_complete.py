"""
Comprehensive tests for the Dreams app — covers CRUD, AI endpoints, tags,
templates, vision board, journal, progress photos, sharing, collaboration,
PDF export, calibration, check-ins, focus sessions, and IDOR guards.

Target: 95%+ coverage on apps/dreams/views.py.
"""

import uuid
from datetime import timedelta
from unittest.mock import Mock, patch

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from rest_framework.test import APIClient

from apps.dreams.models import (
    CalibrationResponse,
    Dream,
    DreamCollaborator,
    DreamJournal,
    DreamMilestone,
    DreamProgressSnapshot,
    DreamTag,
    DreamTagging,
    DreamTemplate,
    FocusSession,
    Goal,
    Obstacle,
    PlanCheckIn,
    ProgressPhoto,
    SharedDream,
    Task,
    VisionBoardImage,
)
from apps.subscriptions.models import Subscription, SubscriptionPlan
from apps.users.models import User

pytestmark = pytest.mark.django_db


# ── Fixtures ────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _mock_stripe():
    """Prevent Stripe API calls during tests."""
    with patch("apps.subscriptions.services.StripeService.create_customer"):
        yield


@pytest.fixture
def _no_moderate():
    """Disable content moderation."""
    mock_result = Mock(is_flagged=False)
    with patch(
        "core.moderation.ContentModerationService.moderate_text",
        return_value=mock_result,
    ):
        yield mock_result


def _make_plan(slug, **overrides):
    defaults = {
        "name": slug.capitalize(),
        "price_monthly": 0 if slug == "free" else 19.99,
        "is_active": True,
        "dream_limit": 3 if slug == "free" else 100,
        "has_ai": slug != "free",
        "has_vision_board": slug == "pro",
    }
    defaults.update(overrides)
    plan, _ = SubscriptionPlan.objects.get_or_create(slug=slug, defaults=defaults)
    return plan


def _subscribe(user, plan):
    Subscription.objects.update_or_create(
        user=user,
        defaults={
            "plan": plan,
            "status": "active",
            "current_period_start": timezone.now(),
            "current_period_end": timezone.now() + timedelta(days=30),
        },
    )


@pytest.fixture
def owner(db):
    u = User.objects.create_user(
        email="dc_owner@test.com",
        password="pass123456",
        display_name="Owner",
        timezone="UTC",
    )
    _subscribe(u, _make_plan("premium"))
    return u


@pytest.fixture
def other(db):
    u = User.objects.create_user(
        email="dc_other@test.com",
        password="pass123456",
        display_name="Other",
        timezone="UTC",
    )
    _subscribe(u, _make_plan("premium"))
    return u


@pytest.fixture
def free_user(db):
    u = User.objects.create_user(
        email="dc_free@test.com",
        password="pass123456",
        display_name="FreeUser",
        timezone="UTC",
    )
    _subscribe(u, _make_plan("free"))
    return u


@pytest.fixture
def pro_user(db):
    u = User.objects.create_user(
        email="dc_pro@test.com",
        password="pass123456",
        display_name="ProUser",
        timezone="UTC",
    )
    _subscribe(u, _make_plan("pro", price_monthly=29.99))
    return u


@pytest.fixture
def api(owner):
    c = APIClient()
    c.force_authenticate(user=owner)
    return c


@pytest.fixture
def api_other(other):
    c = APIClient()
    c.force_authenticate(user=other)
    return c


@pytest.fixture
def api_free(free_user):
    c = APIClient()
    c.force_authenticate(user=free_user)
    return c


@pytest.fixture
def api_anon():
    return APIClient()


@pytest.fixture
def dream(owner):
    return Dream.objects.create(
        user=owner,
        title="Learn Piano",
        description="Master piano playing from basics to advanced",
        category="hobbies",
        status="active",
        priority=2,
    )


@pytest.fixture
def dream_with_plan(dream):
    ms = DreamMilestone.objects.create(
        dream=dream, title="Month 1", description="Basics", order=1
    )
    goal = Goal.objects.create(
        dream=dream, milestone=ms, title="G1", description="desc", order=1
    )
    Task.objects.create(goal=goal, title="T1", order=1, duration_mins=30)
    Task.objects.create(goal=goal, title="T2", order=2, duration_mins=15)
    dream.plan_phase = "partial"
    dream.save(update_fields=["plan_phase"])
    return dream


# ── Helpers ─────────────────────────────────────────────────────────

DREAMS_URL = "/api/dreams/dreams/"
GOALS_URL = "/api/dreams/goals/"
TASKS_URL = "/api/dreams/tasks/"
MILESTONES_URL = "/api/dreams/milestones/"
OBSTACLES_URL = "/api/dreams/obstacles/"
JOURNAL_URL = "/api/dreams/journal/"
CHECKINS_URL = "/api/dreams/checkins/"


def _dream_url(dream_id, action=""):
    base = f"{DREAMS_URL}{dream_id}/"
    return f"{base}{action}/" if action else base


def _make_png_bytes():
    """Return minimal valid PNG bytes."""
    return (
        b"\x89PNG\r\n\x1a\n"
        + b"\x00\x00\x00\rIHDR"
        + b"\x00\x00\x00\x01\x00\x00\x00\x01"
        + b"\x08\x02\x00\x00\x00\x90wS\xde"
        + b"\x00\x00\x00\x0cIDATx"
        + b"\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05"
        + b"\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
    )


# ═══════════════════════════════════════════════════════════════════
# 1. DREAM CRUD
# ═══════════════════════════════════════════════════════════════════


class TestDreamCRUD:
    """Dream list, create, retrieve, update, partial update, delete."""

    def test_list_own_dreams(self, api, dream):
        resp = api.get(DREAMS_URL)
        assert resp.status_code == 200
        ids = [d["id"] for d in resp.data.get("results", resp.data)]
        assert str(dream.id) in ids

    def test_list_excludes_other_users(self, api, other):
        Dream.objects.create(user=other, title="X", description="Y", category="career")
        ids = [
            d["id"]
            for d in api.get(DREAMS_URL).data.get("results", api.get(DREAMS_URL).data)
        ]
        # other's dream should not appear
        assert all(
            Dream.objects.get(id=did).user != other
            for did in ids
            if Dream.objects.filter(id=did).exists()
        )

    @patch("core.moderation.ContentModerationService.moderate_text")
    def test_create_dream(self, mock_mod, api):
        mock_mod.return_value = Mock(is_flagged=False)
        resp = api.post(
            DREAMS_URL,
            {
                "title": "New Dream",
                "description": "A fresh start with new goals",
                "category": "career",
            },
            format="json",
        )
        assert resp.status_code == 201
        assert resp.data["title"] == "New Dream"

    @patch("core.moderation.ContentModerationService.moderate_text")
    def test_create_dream_moderation_blocks(self, mock_mod, api):
        mock_mod.return_value = Mock(is_flagged=True, user_message="Blocked")
        resp = api.post(
            DREAMS_URL,
            {
                "title": "Bad",
                "description": "Inappropriate content for testing purposes",
            },
            format="json",
        )
        assert resp.status_code == 400

    def test_retrieve_own_dream(self, api, dream):
        resp = api.get(_dream_url(dream.id))
        assert resp.status_code == 200
        assert resp.data["id"] == str(dream.id)

    @patch("core.moderation.ContentModerationService.moderate_text")
    def test_update_dream(self, mock_mod, api, dream):
        mock_mod.return_value = Mock(is_flagged=False)
        resp = api.patch(
            _dream_url(dream.id),
            {"title": "Learn Jazz Piano"},
            format="json",
        )
        assert resp.status_code == 200
        dream.refresh_from_db()
        assert dream.title == "Learn Jazz Piano"

    def test_delete_dream(self, api, dream):
        resp = api.delete(_dream_url(dream.id))
        assert resp.status_code == 204
        assert not Dream.objects.filter(id=dream.id).exists()

    def test_filter_by_status(self, api, owner):
        Dream.objects.create(
            user=owner, title="A", description="Active one", status="active"
        )
        Dream.objects.create(
            user=owner, title="P", description="Paused one", status="paused"
        )
        resp = api.get(f"{DREAMS_URL}?status=paused")
        for d in resp.data.get("results", resp.data):
            assert d["status"] == "paused"

    def test_filter_by_category(self, api, owner):
        Dream.objects.create(
            user=owner, title="H", description="Health dream", category="health"
        )
        resp = api.get(f"{DREAMS_URL}?category=health")
        for d in resp.data.get("results", resp.data):
            assert d["category"] == "health"

    def test_unauthenticated_blocked(self, api_anon):
        assert api_anon.get(DREAMS_URL).status_code == 401


# ═══════════════════════════════════════════════════════════════════
# 2. AI ANALYZE
# ═══════════════════════════════════════════════════════════════════


class TestAnalyze:
    """POST /dreams/<id>/analyze/"""

    @patch("integrations.openai_service.OpenAIService.analyze_dream")
    @patch("core.ai_validators.validate_analysis_response")
    @patch("core.ai_usage.AIUsageTracker.increment")
    def test_analyze_success(self, _inc, mock_validate, mock_ai, api, dream):
        result_mock = Mock()
        result_mock.model_dump.return_value = {
            "category": "hobbies",
            "summary": "Great dream",
            "detected_language": "en",
        }
        mock_validate.return_value = result_mock
        mock_ai.return_value = {"raw": "data"}
        resp = api.post(_dream_url(dream.id, "analyze"))
        assert resp.status_code == 200
        # Response contains the analysis dict (may be camelCase-transformed)
        assert "summary" in resp.data or "category" in resp.data

    @patch("integrations.openai_service.OpenAIService.analyze_dream")
    def test_analyze_openai_error(self, mock_ai, api, dream):
        from core.exceptions import OpenAIError

        mock_ai.side_effect = OpenAIError("Service unavailable")
        resp = api.post(_dream_url(dream.id, "analyze"))
        assert resp.status_code == 500

    @patch("integrations.openai_service.OpenAIService.analyze_dream")
    @patch("apps.dreams.views.validate_analysis_response")
    def test_analyze_validation_error(self, mock_validate, mock_ai, api, dream):
        from core.ai_validators import AIValidationError

        mock_ai.return_value = {"raw": "data"}
        mock_validate.side_effect = AIValidationError("Bad response")
        resp = api.post(_dream_url(dream.id, "analyze"))
        assert resp.status_code == 502


# ═══════════════════════════════════════════════════════════════════
# 3. AI REFINE
# ═══════════════════════════════════════════════════════════════════


class TestRefine:
    """POST /dreams/refine/"""

    @patch("integrations.openai_service.OpenAIService.refine_dream")
    @patch("core.moderation.ContentModerationService.moderate_text")
    @patch("core.ai_usage.AIUsageTracker.increment")
    def test_refine_success(self, _inc, mock_mod, mock_ai, api):
        mock_mod.return_value = Mock(is_flagged=False)
        mock_ai.return_value = {"title": "Refined", "description": "Better desc"}
        resp = api.post(
            f"{DREAMS_URL}refine/",
            {
                "title": "My dream title",
                "description": "A description that is long enough to pass validation",
            },
            format="json",
        )
        assert resp.status_code == 200

    @patch("core.moderation.ContentModerationService.moderate_text")
    def test_refine_missing_title(self, mock_mod, api):
        mock_mod.return_value = Mock(is_flagged=False)
        resp = api.post(
            f"{DREAMS_URL}refine/",
            {"title": "", "description": "A description that is long enough"},
            format="json",
        )
        assert resp.status_code == 400

    @patch("core.moderation.ContentModerationService.moderate_text")
    def test_refine_short_title(self, mock_mod, api):
        mock_mod.return_value = Mock(is_flagged=False)
        resp = api.post(
            f"{DREAMS_URL}refine/",
            {"title": "AB", "description": "A description that is long enough"},
            format="json",
        )
        assert resp.status_code == 400

    @patch("core.moderation.ContentModerationService.moderate_text")
    def test_refine_short_description(self, mock_mod, api):
        mock_mod.return_value = Mock(is_flagged=False)
        resp = api.post(
            f"{DREAMS_URL}refine/",
            {"title": "Good title", "description": "Short"},
            format="json",
        )
        assert resp.status_code == 400

    @patch("core.moderation.ContentModerationService.moderate_text")
    def test_refine_moderation_blocks(self, mock_mod, api):
        mock_mod.return_value = Mock(is_flagged=True, user_message="Blocked")
        resp = api.post(
            f"{DREAMS_URL}refine/",
            {
                "title": "Bad dream title",
                "description": "Inappropriate content for testing moderation blocking",
            },
            format="json",
        )
        assert resp.status_code == 400

    @patch("integrations.openai_service.OpenAIService.refine_dream")
    @patch("core.moderation.ContentModerationService.moderate_text")
    def test_refine_openai_error(self, mock_mod, mock_ai, api):
        from core.exceptions import OpenAIError

        mock_mod.return_value = Mock(is_flagged=False)
        mock_ai.side_effect = OpenAIError("Fail")
        resp = api.post(
            f"{DREAMS_URL}refine/",
            {
                "title": "Good title for dream",
                "description": "A description that is long enough for refine",
            },
            format="json",
        )
        assert resp.status_code == 500


# ═══════════════════════════════════════════════════════════════════
# 4. DUPLICATE DREAM
# ═══════════════════════════════════════════════════════════════════


class TestDuplicate:
    """POST /dreams/<id>/duplicate/"""

    def test_duplicate_without_milestones(self, api, dream):
        resp = api.post(_dream_url(dream.id, "duplicate"))
        assert resp.status_code == 201
        assert "(Copy)" in resp.data["title"]

    def test_duplicate_with_goals_and_tasks(self, api, dream_with_plan):
        original_goals = Goal.objects.filter(dream=dream_with_plan).count()
        original_tasks = Task.objects.filter(goal__dream=dream_with_plan).count()
        resp = api.post(_dream_url(dream_with_plan.id, "duplicate"))
        assert resp.status_code == 201
        new_id = resp.data["id"]
        new_goals = Goal.objects.filter(dream_id=new_id).count()
        new_tasks = Task.objects.filter(goal__dream_id=new_id).count()
        assert new_goals == original_goals
        assert new_tasks == original_tasks

    def test_duplicate_copies_tags(self, api, dream):
        tag, _ = DreamTag.objects.get_or_create(name="piano")
        DreamTagging.objects.create(dream=dream, tag=tag)
        resp = api.post(_dream_url(dream.id, "duplicate"))
        assert resp.status_code == 201
        new_id = resp.data["id"]
        assert DreamTagging.objects.filter(dream_id=new_id, tag=tag).exists()


# ═══════════════════════════════════════════════════════════════════
# 5. SHARE & COLLABORATORS
# ═══════════════════════════════════════════════════════════════════


class TestShare:
    """Share dream with another user."""

    def test_share_dream(self, api, dream, other):
        resp = api.post(
            _dream_url(dream.id, "share"),
            {"shared_with_id": str(other.id), "permission": "view"},
            format="json",
        )
        assert resp.status_code == 201
        assert SharedDream.objects.filter(dream=dream, shared_with=other).exists()

    def test_share_with_self_fails(self, api, dream, owner):
        resp = api.post(
            _dream_url(dream.id, "share"),
            {"shared_with_id": str(owner.id)},
            format="json",
        )
        assert resp.status_code == 400

    def test_share_duplicate_fails(self, api, dream, other):
        SharedDream.objects.create(dream=dream, shared_by=dream.user, shared_with=other)
        resp = api.post(
            _dream_url(dream.id, "share"),
            {"shared_with_id": str(other.id)},
            format="json",
        )
        assert resp.status_code == 400

    def test_share_nonexistent_user(self, api, dream):
        resp = api.post(
            _dream_url(dream.id, "share"),
            {"shared_with_id": str(uuid.uuid4())},
            format="json",
        )
        assert resp.status_code == 404

    def test_unshare(self, api, dream, other):
        SharedDream.objects.create(dream=dream, shared_by=dream.user, shared_with=other)
        resp = api.delete(f"{DREAMS_URL}{dream.id}/unshare/{other.id}/")
        assert resp.status_code == 200

    def test_unshare_nonexistent(self, api, dream):
        resp = api.delete(f"{DREAMS_URL}{dream.id}/unshare/{uuid.uuid4()}/")
        assert resp.status_code == 404

    def test_shared_with_me(self, api_other, dream, other):
        SharedDream.objects.create(dream=dream, shared_by=dream.user, shared_with=other)
        resp = api_other.get("/api/dreams/dreams/shared-with-me/")
        assert resp.status_code == 200
        assert len(resp.data.get("shared_dreams", [])) >= 1


class TestCollaborators:
    """Add, list, remove collaborators."""

    def test_add_collaborator(self, api, dream, other):
        resp = api.post(
            _dream_url(dream.id, "collaborators"),
            {"user_id": str(other.id), "role": "collaborator"},
            format="json",
        )
        assert resp.status_code == 201

    def test_add_self_as_collaborator_fails(self, api, dream, owner):
        resp = api.post(
            _dream_url(dream.id, "collaborators"),
            {"user_id": str(owner.id)},
            format="json",
        )
        assert resp.status_code == 400

    def test_add_duplicate_collaborator_fails(self, api, dream, other):
        DreamCollaborator.objects.create(dream=dream, user=other, role="viewer")
        resp = api.post(
            _dream_url(dream.id, "collaborators"),
            {"user_id": str(other.id)},
            format="json",
        )
        assert resp.status_code == 400

    def test_add_nonexistent_user(self, api, dream):
        resp = api.post(
            _dream_url(dream.id, "collaborators"),
            {"user_id": str(uuid.uuid4())},
            format="json",
        )
        assert resp.status_code == 404

    def test_list_collaborators(self, api, dream, other):
        DreamCollaborator.objects.create(dream=dream, user=other, role="viewer")
        resp = api.get(f"{DREAMS_URL}{dream.id}/collaborators/list/")
        assert resp.status_code == 200
        assert len(resp.data.get("collaborators", [])) == 1

    def test_remove_collaborator(self, api, dream, other):
        DreamCollaborator.objects.create(dream=dream, user=other, role="viewer")
        resp = api.delete(f"{DREAMS_URL}{dream.id}/collaborators/{other.id}/")
        assert resp.status_code == 200

    def test_remove_nonexistent_collaborator(self, api, dream):
        resp = api.delete(f"{DREAMS_URL}{dream.id}/collaborators/{uuid.uuid4()}/")
        assert resp.status_code == 404

    def test_non_owner_cannot_add_collaborator(self, api_other, dream, other):
        """Only dream owner can add collaborators."""
        resp = api_other.post(
            _dream_url(dream.id, "collaborators"),
            {"user_id": str(other.id)},
            format="json",
        )
        # Should be 403 or 404 (IDOR guard)
        assert resp.status_code in (403, 404)


# ═══════════════════════════════════════════════════════════════════
# 6. TAGS
# ═══════════════════════════════════════════════════════════════════


class TestTags:
    """Add, remove, list tags."""

    def test_add_tag(self, api, dream):
        resp = api.post(
            _dream_url(dream.id, "tags"),
            {"tag_name": "Music"},
            format="json",
        )
        assert resp.status_code == 200
        assert DreamTagging.objects.filter(dream=dream).exists()

    def test_add_tag_creates_tag_if_not_exists(self, api, dream):
        api.post(
            _dream_url(dream.id, "tags"),
            {"tag_name": "BrandNew"},
            format="json",
        )
        assert DreamTag.objects.filter(name="brandnew").exists()

    def test_add_duplicate_tag_idempotent(self, api, dream):
        api.post(_dream_url(dream.id, "tags"), {"tag_name": "dup"}, format="json")
        api.post(_dream_url(dream.id, "tags"), {"tag_name": "dup"}, format="json")
        assert DreamTagging.objects.filter(dream=dream, tag__name="dup").count() == 1

    def test_remove_tag(self, api, dream):
        tag, _ = DreamTag.objects.get_or_create(name="removeme")
        DreamTagging.objects.create(dream=dream, tag=tag)
        resp = api.delete(f"{DREAMS_URL}{dream.id}/tags/removeme/")
        assert resp.status_code == 200

    def test_remove_nonexistent_tag(self, api, dream):
        resp = api.delete(f"{DREAMS_URL}{dream.id}/tags/nonexistent/")
        assert resp.status_code == 404

    def test_list_all_tags(self, api):
        DreamTag.objects.get_or_create(name="alpha")
        DreamTag.objects.get_or_create(name="beta")
        resp = api.get("/api/dreams/dreams/tags/")
        assert resp.status_code == 200


# ═══════════════════════════════════════════════════════════════════
# 7. TEMPLATES
# ═══════════════════════════════════════════════════════════════════


class TestTemplates:
    """List templates, use template, featured."""

    @pytest.fixture
    def template(self, db):
        return DreamTemplate.objects.create(
            title="Marathon Training",
            description="Train for a full marathon",
            category="health",
            template_goals=[
                {
                    "title": "Build Base",
                    "description": "Base mileage",
                    "order": 1,
                    "tasks": [
                        {"title": "Run 5k", "order": 1, "duration_mins": 30},
                    ],
                }
            ],
            is_active=True,
            is_featured=True,
        )

    def test_list_templates(self, api, template):
        resp = api.get("/api/dreams/dreams/templates/")
        assert resp.status_code == 200

    def test_retrieve_template(self, api, template):
        resp = api.get(f"/api/dreams/dreams/templates/{template.id}/")
        assert resp.status_code == 200

    def test_use_template(self, api, template):
        resp = api.post(f"/api/dreams/dreams/templates/{template.id}/use/")
        assert resp.status_code == 201
        new_dream_id = resp.data["id"]
        assert Dream.objects.filter(id=new_dream_id).exists()
        assert Goal.objects.filter(dream_id=new_dream_id).count() == 1
        assert Task.objects.filter(goal__dream_id=new_dream_id).count() == 1
        # Usage count incremented
        template.refresh_from_db()
        assert template.usage_count == 1

    def test_featured_templates(self, api, template):
        resp = api.get("/api/dreams/dreams/templates/featured/")
        assert resp.status_code == 200
        ids = [t["id"] for t in resp.data]
        assert str(template.id) in ids


# ═══════════════════════════════════════════════════════════════════
# 8. VISION BOARD
# ═══════════════════════════════════════════════════════════════════


class TestVisionBoard:
    """Vision board add, remove, list, generate AI."""

    def test_list_empty(self, api, dream):
        resp = api.get(_dream_url(dream.id, "vision-board"))
        assert resp.status_code == 200
        assert resp.data["images"] == []

    def test_add_via_url(self, api, dream):
        with patch("core.validators.validate_url_no_ssrf"):
            resp = api.post(
                _dream_url(dream.id, "vision-board/add"),
                {"image_url": "https://example.com/img.png", "caption": "Test"},
            )
        assert resp.status_code == 201

    def test_add_via_file(self, api, dream):
        png = SimpleUploadedFile(
            "test.png", _make_png_bytes(), content_type="image/png"
        )
        resp = api.post(
            _dream_url(dream.id, "vision-board/add"),
            {"image": png, "caption": "Upload"},
            format="multipart",
        )
        assert resp.status_code == 201

    def test_add_no_image_fails(self, api, dream):
        resp = api.post(
            _dream_url(dream.id, "vision-board/add"),
            {"caption": "Nothing"},
        )
        assert resp.status_code == 400

    def test_add_invalid_format(self, api, dream):
        bad = SimpleUploadedFile("test.txt", b"not an image", content_type="text/plain")
        resp = api.post(
            _dream_url(dream.id, "vision-board/add"),
            {"image": bad},
            format="multipart",
        )
        assert resp.status_code == 400

    def test_add_invalid_magic_bytes(self, api, dream):
        bad = SimpleUploadedFile(
            "test.png", b"\x00\x00\x00\x00" * 10, content_type="image/png"
        )
        resp = api.post(
            _dream_url(dream.id, "vision-board/add"),
            {"image": bad},
            format="multipart",
        )
        assert resp.status_code == 400

    def test_add_too_large(self, api, dream):
        big = SimpleUploadedFile(
            "big.png",
            _make_png_bytes() + b"\x00" * (11 * 1024 * 1024),
            content_type="image/png",
        )
        resp = api.post(
            _dream_url(dream.id, "vision-board/add"),
            {"image": big},
            format="multipart",
        )
        assert resp.status_code == 400

    def test_remove_image(self, api, dream):
        vbi = VisionBoardImage.objects.create(
            dream=dream, image_url="https://example.com/x.png", order=0
        )
        resp = api.delete(f"{DREAMS_URL}{dream.id}/vision-board/{vbi.id}/")
        assert resp.status_code == 200

    def test_remove_nonexistent(self, api, dream):
        resp = api.delete(f"{DREAMS_URL}{dream.id}/vision-board/{uuid.uuid4()}/")
        assert resp.status_code == 404

    @patch("integrations.openai_service.OpenAIService.generate_vision_image")
    @patch("apps.dreams.views.http_requests.get")
    @patch("core.ai_usage.AIUsageTracker.increment")
    def test_generate_vision(self, _inc, mock_get, mock_ai, pro_user):
        """Generate vision requires pro subscription."""
        pro_dream = Dream.objects.create(
            user=pro_user,
            title="Pro Dream",
            description="Dream with vision board access",
            category="hobbies",
        )
        pro_client = APIClient()
        pro_client.force_authenticate(user=pro_user)
        mock_ai.return_value = "https://dalle.example.com/img.png"
        mock_resp = Mock()
        mock_resp.content = _make_png_bytes()
        mock_resp.raise_for_status = Mock()
        mock_get.return_value = mock_resp
        resp = pro_client.post(_dream_url(pro_dream.id, "generate_vision"))
        assert resp.status_code == 200
        assert "image_url" in resp.data or "imageUrl" in resp.data


# ═══════════════════════════════════════════════════════════════════
# 9. JOURNAL CRUD
# ═══════════════════════════════════════════════════════════════════


class TestJournal:
    """Dream journal CRUD."""

    def test_create_entry(self, api, dream):
        resp = api.post(
            JOURNAL_URL,
            {
                "dream": str(dream.id),
                "title": "Day 1",
                "content": "Started practice today",
                "mood": "excited",
            },
            format="json",
        )
        assert resp.status_code == 201

    def test_list_entries(self, api, dream):
        DreamJournal.objects.create(dream=dream, title="J1", content="Entry 1")
        resp = api.get(f"{JOURNAL_URL}?dream={dream.id}")
        assert resp.status_code == 200

    def test_update_entry(self, api, dream):
        j = DreamJournal.objects.create(dream=dream, title="J1", content="C1")
        resp = api.patch(
            f"{JOURNAL_URL}{j.id}/",
            {"content": "Updated content"},
            format="json",
        )
        assert resp.status_code == 200
        j.refresh_from_db()
        assert j.content == "Updated content"

    def test_delete_entry(self, api, dream):
        j = DreamJournal.objects.create(dream=dream, title="J1", content="C1")
        resp = api.delete(f"{JOURNAL_URL}{j.id}/")
        assert resp.status_code == 204

    def test_cannot_create_on_other_dream(self, api, other):
        od = Dream.objects.create(
            user=other, title="O", description="Other", category="career"
        )
        resp = api.post(
            JOURNAL_URL,
            {"dream": str(od.id), "content": "Sneak"},
            format="json",
        )
        assert resp.status_code == 403


# ═══════════════════════════════════════════════════════════════════
# 10. PROGRESS PHOTOS
# ═══════════════════════════════════════════════════════════════════


class TestProgressPhotos:
    """Upload, list, and analyze progress photos."""

    def test_list_photos(self, api, dream):
        resp = api.get(_dream_url(dream.id, "progress-photos"))
        assert resp.status_code == 200

    def test_upload_photo(self, api, dream):
        png = SimpleUploadedFile(
            "photo.png", _make_png_bytes(), content_type="image/png"
        )
        resp = api.post(
            _dream_url(dream.id, "progress-photos/upload"),
            {"image": png, "caption": "Day 1"},
            format="multipart",
        )
        assert resp.status_code == 201

    def test_upload_no_image_fails(self, api, dream):
        resp = api.post(
            _dream_url(dream.id, "progress-photos/upload"),
            {"caption": "No image"},
            format="multipart",
        )
        assert resp.status_code == 400

    def test_upload_invalid_format(self, api, dream):
        bad = SimpleUploadedFile("x.txt", b"text", content_type="text/plain")
        resp = api.post(
            _dream_url(dream.id, "progress-photos/upload"),
            {"image": bad},
            format="multipart",
        )
        assert resp.status_code == 400

    def test_upload_invalid_magic_bytes(self, api, dream):
        bad = SimpleUploadedFile("x.png", b"\x00" * 20, content_type="image/png")
        resp = api.post(
            _dream_url(dream.id, "progress-photos/upload"),
            {"image": bad},
            format="multipart",
        )
        assert resp.status_code == 400


# ═══════════════════════════════════════════════════════════════════
# 11. PUBLISH / COMPLETE / FAVORITE
# ═══════════════════════════════════════════════════════════════════


class TestDreamActions:
    """Complete, like (favorite), explore."""

    def test_complete_dream(self, api, dream, owner):
        resp = api.post(_dream_url(dream.id, "complete"))
        assert resp.status_code == 200
        dream.refresh_from_db()
        assert dream.status == "completed"

    def test_complete_already_completed(self, api, dream):
        dream.status = "completed"
        dream.save()
        resp = api.post(_dream_url(dream.id, "complete"))
        # Idempotent: completing an already-completed dream returns 200
        assert resp.status_code == 200

    def test_like_toggle(self, api, dream):
        assert dream.is_favorited is False
        resp = api.post(_dream_url(dream.id, "like"))
        assert resp.status_code == 200
        dream.refresh_from_db()
        assert dream.is_favorited is True
        # Toggle back
        resp2 = api.post(_dream_url(dream.id, "like"))
        dream.refresh_from_db()
        assert dream.is_favorited is False

    def test_explore_public(self, api, other):
        Dream.objects.create(
            user=other,
            title="Public",
            description="Public dream",
            category="career",
            is_public=True,
            status="active",
        )
        resp = api.get(f"{DREAMS_URL}explore/")
        assert resp.status_code == 200

    def test_analytics(self, api, dream):
        resp = api.get(_dream_url(dream.id, "analytics"))
        assert resp.status_code == 200
        assert "task_stats" in resp.data

    def test_progress_history(self, api, dream):
        DreamProgressSnapshot.record_snapshot(dream)
        resp = api.get(_dream_url(dream.id, "progress-history"))
        assert resp.status_code == 200
        assert "snapshots" in resp.data


# ═══════════════════════════════════════════════════════════════════
# 12. PDF EXPORT
# ═══════════════════════════════════════════════════════════════════


class TestPDFExport:
    """GET /dreams/<id>/export-pdf/"""

    @patch("apps.dreams.views.DreamPDFExportView.get")
    def test_export_pdf_success(self, mock_get, api, dream):
        """PDF export endpoint is reachable (mocked)."""
        from django.http import HttpResponse

        mock_get.return_value = HttpResponse(b"PDF", content_type="application/pdf")
        resp = api.get(f"/api/dreams/dreams/{dream.id}/export-pdf/")
        assert resp.status_code == 200

    def test_export_pdf_other_user(self, api_other, dream):
        resp = api_other.get(f"/api/dreams/dreams/{dream.id}/export-pdf/")
        assert resp.status_code == 404


# ═══════════════════════════════════════════════════════════════════
# 13. CALIBRATION
# ═══════════════════════════════════════════════════════════════════


class TestCalibration:
    """Start, answer, skip calibration."""

    @patch("integrations.openai_service.OpenAIService.generate_calibration_questions")
    @patch("core.ai_validators.validate_calibration_questions")
    @patch("core.ai_usage.AIUsageTracker.increment")
    @patch("integrations.plan_processors.detect_category_with_ambiguity")
    def test_start_calibration(
        self, mock_detect, _inc, mock_validate, mock_ai, api, dream
    ):
        mock_detect.return_value = {
            "category": "hobbies",
            "is_ambiguous": False,
            "candidates": [],
        }
        q_mock = Mock()
        q_mock.question = "How much time?"
        q_mock.category = "specifics"
        result = Mock()
        result.refusal_reason = None
        result.questions = [q_mock]
        mock_validate.return_value = result
        mock_ai.return_value = {"questions": []}
        resp = api.post(_dream_url(dream.id, "start_calibration"))
        assert resp.status_code == 200
        assert resp.data["status"] == "in_progress"
        dream.refresh_from_db()
        assert dream.calibration_status == "in_progress"

    def test_start_calibration_already_completed(self, api, dream):
        dream.calibration_status = "completed"
        dream.save()
        resp = api.post(_dream_url(dream.id, "start_calibration"))
        assert resp.status_code == 400

    def test_answer_calibration_pending_rejected(self, api, dream):
        """Cannot answer if calibration not started."""
        resp = api.post(
            _dream_url(dream.id, "answer_calibration"),
            {"answers": [{"question_id": str(uuid.uuid4()), "answer": "Yes I do"}]},
            format="json",
        )
        assert resp.status_code == 400

    @patch("core.moderation.ContentModerationService.moderate_text")
    def test_answer_calibration_success(self, mock_mod, api, dream):
        mock_mod.return_value = Mock(is_flagged=False)
        dream.calibration_status = "in_progress"
        dream.save()
        cr = CalibrationResponse.objects.create(
            dream=dream, question="How much time?", question_number=1
        )
        # Answer enough to trigger completion (10+)
        for i in range(2, 12):
            cr_i = CalibrationResponse.objects.create(
                dream=dream, question=f"Q{i}", question_number=i, answer=f"A{i}"
            )
        resp = api.post(
            _dream_url(dream.id, "answer_calibration"),
            {
                "answers": [
                    {"question_id": str(cr.id), "answer": "About 30 minutes daily"},
                ]
            },
            format="json",
        )
        assert resp.status_code == 200
        assert resp.data["status"] == "completed"

    def test_skip_calibration(self, api, dream):
        resp = api.post(_dream_url(dream.id, "skip_calibration"))
        assert resp.status_code == 200
        dream.refresh_from_db()
        assert dream.calibration_status == "skipped"

    def test_skip_when_completed_fails(self, api, dream):
        dream.calibration_status = "completed"
        dream.save()
        resp = api.post(_dream_url(dream.id, "skip_calibration"))
        assert resp.status_code == 400


# ═══════════════════════════════════════════════════════════════════
# 14. PLAN GENERATION & CHECK-INS
# ═══════════════════════════════════════════════════════════════════


class TestPlanGeneration:
    """Generate plan, plan status, trigger check-in."""

    @patch("apps.dreams.tasks.generate_dream_skeleton_task.apply_async")
    @patch("apps.dreams.tasks.set_plan_status")
    @patch("apps.dreams.tasks.get_plan_status", return_value=None)
    def test_generate_plan(self, _get, _set, _task, api, dream):
        resp = api.post(_dream_url(dream.id, "generate_plan"))
        assert resp.status_code == 202

    @patch("apps.dreams.tasks.get_plan_status")
    def test_plan_status_generating(self, mock_status, api, dream):
        mock_status.return_value = {"status": "generating", "message": "Working..."}
        resp = api.get(_dream_url(dream.id, "plan_status"))
        assert resp.status_code == 200
        assert resp.data["status"] == "generating"

    @patch("apps.dreams.tasks.get_plan_status", return_value=None)
    def test_plan_status_idle(self, _mock, api, dream):
        resp = api.get(_dream_url(dream.id, "plan_status"))
        assert resp.status_code == 200
        assert resp.data["status"] == "idle"


class TestCheckIns:
    """Trigger, respond, and list check-ins."""

    @patch("apps.dreams.tasks.generate_checkin_questionnaire_task.apply_async")
    def test_trigger_checkin(self, _task, api, dream_with_plan):
        resp = api.post(_dream_url(dream_with_plan.id, "trigger-checkin"))
        assert resp.status_code == 202

    def test_trigger_checkin_no_plan(self, api, dream):
        resp = api.post(_dream_url(dream.id, "trigger-checkin"))
        assert resp.status_code == 400

    @patch("apps.dreams.tasks.generate_checkin_questionnaire_task.apply_async")
    def test_trigger_checkin_cooldown(self, _task, api, dream_with_plan):
        dream_with_plan.last_checkin_at = timezone.now() - timedelta(days=3)
        dream_with_plan.save()
        resp = api.post(_dream_url(dream_with_plan.id, "trigger-checkin"))
        assert resp.status_code == 429

    def test_list_checkins(self, api, dream_with_plan):
        PlanCheckIn.objects.create(
            dream=dream_with_plan,
            status="completed",
            scheduled_for=timezone.now(),
        )
        resp = api.get(_dream_url(dream_with_plan.id, "checkins"))
        assert resp.status_code == 200

    def test_checkin_viewset_list(self, api, dream_with_plan):
        PlanCheckIn.objects.create(
            dream=dream_with_plan,
            status="completed",
            scheduled_for=timezone.now(),
        )
        resp = api.get(CHECKINS_URL)
        assert resp.status_code == 200

    @patch("apps.dreams.tasks.process_checkin_responses_task.apply_async")
    def test_checkin_respond(self, _task, api, dream_with_plan):
        ci = PlanCheckIn.objects.create(
            dream=dream_with_plan,
            status="awaiting_user",
            scheduled_for=timezone.now(),
            questionnaire=[
                {"id": "q1", "text": "How is it going?", "is_required": True}
            ],
        )
        resp = api.post(
            f"{CHECKINS_URL}{ci.id}/respond/",
            {"responses": {"q1": "Going well!"}},
            format="json",
        )
        assert resp.status_code == 202

    def test_checkin_respond_not_awaiting(self, api, dream_with_plan):
        ci = PlanCheckIn.objects.create(
            dream=dream_with_plan,
            status="completed",
            scheduled_for=timezone.now(),
        )
        resp = api.post(
            f"{CHECKINS_URL}{ci.id}/respond/",
            {"responses": {"q1": "test"}},
            format="json",
        )
        assert resp.status_code == 400

    def test_checkin_status_poll(self, api, dream_with_plan):
        ci = PlanCheckIn.objects.create(
            dream=dream_with_plan,
            status="ai_processing",
            scheduled_for=timezone.now(),
        )
        resp = api.get(f"{CHECKINS_URL}{ci.id}/status/")
        assert resp.status_code == 200


# ═══════════════════════════════════════════════════════════════════
# 15. GOALS CRUD
# ═══════════════════════════════════════════════════════════════════


class TestGoals:
    """Goal CRUD + complete."""

    def test_create_goal(self, api, dream):
        resp = api.post(
            GOALS_URL,
            {"dream": str(dream.id), "title": "Goal 1", "description": "Desc"},
            format="json",
        )
        assert resp.status_code == 201

    def test_list_goals(self, api, dream):
        Goal.objects.create(dream=dream, title="G1", description="D1", order=1)
        resp = api.get(f"{GOALS_URL}?dream={dream.id}")
        assert resp.status_code == 200

    def test_complete_goal(self, api, dream):
        g = Goal.objects.create(dream=dream, title="G1", description="D1", order=1)
        resp = api.post(f"{GOALS_URL}{g.id}/complete/")
        assert resp.status_code == 200
        g.refresh_from_db()
        assert g.status == "completed"

    def test_complete_already_completed(self, api, dream):
        g = Goal.objects.create(
            dream=dream, title="G1", description="D1", order=1, status="completed"
        )
        resp = api.post(f"{GOALS_URL}{g.id}/complete/")
        # Idempotent: completing an already-completed goal returns 200
        assert resp.status_code == 200


# ═══════════════════════════════════════════════════════════════════
# 16. TASKS CRUD
# ═══════════════════════════════════════════════════════════════════


class TestTasks:
    """Task CRUD + complete, skip, quick_create, reorder."""

    @pytest.fixture
    def goal(self, dream):
        return Goal.objects.create(dream=dream, title="G1", description="D1", order=1)

    @pytest.fixture
    def task(self, goal):
        return Task.objects.create(
            goal=goal, title="T1", description="D1", order=1, duration_mins=25
        )

    def test_create_task(self, api, goal):
        resp = api.post(
            TASKS_URL,
            {"goal": str(goal.id), "title": "New Task", "duration_mins": 30},
            format="json",
        )
        assert resp.status_code == 201

    def test_list_tasks(self, api, task):
        resp = api.get(TASKS_URL)
        assert resp.status_code == 200

    def test_complete_task(self, api, task, owner):
        resp = api.post(f"{TASKS_URL}{task.id}/complete/")
        assert resp.status_code == 200
        task.refresh_from_db()
        assert task.status == "completed"

    def test_complete_already_completed(self, api, task):
        task.status = "completed"
        task.save()
        resp = api.post(f"{TASKS_URL}{task.id}/complete/")
        # Idempotent: completing an already-completed task returns 200
        assert resp.status_code == 200

    def test_skip_task(self, api, task):
        resp = api.post(f"{TASKS_URL}{task.id}/skip/")
        assert resp.status_code == 200
        task.refresh_from_db()
        assert task.status == "skipped"

    def test_quick_create(self, api, dream, goal):
        resp = api.post(
            f"{TASKS_URL}quick_create/",
            {"title": "Quick task"},
            format="json",
        )
        assert resp.status_code == 201

    def test_quick_create_with_dream_id(self, api, dream, goal):
        resp = api.post(
            f"{TASKS_URL}quick_create/",
            {"title": "Quick task", "dream_id": str(dream.id)},
            format="json",
        )
        assert resp.status_code == 201

    def test_quick_create_no_title(self, api):
        resp = api.post(
            f"{TASKS_URL}quick_create/",
            {"title": ""},
            format="json",
        )
        assert resp.status_code == 400

    def test_reorder_tasks(self, api, goal):
        t1 = Task.objects.create(goal=goal, title="A", order=1)
        t2 = Task.objects.create(goal=goal, title="B", order=2)
        resp = api.post(
            f"{TASKS_URL}reorder/",
            {"goal_id": str(goal.id), "task_ids": [str(t2.id), str(t1.id)]},
            format="json",
        )
        assert resp.status_code == 200
        t1.refresh_from_db()
        t2.refresh_from_db()
        assert t2.order == 0
        assert t1.order == 1

    def test_reorder_missing_data(self, api):
        resp = api.post(
            f"{TASKS_URL}reorder/",
            {},
            format="json",
        )
        assert resp.status_code == 400

    def test_task_chain(self, api, goal):
        parent = Task.objects.create(goal=goal, title="Parent", order=1, is_chain=True)
        child = Task.objects.create(
            goal=goal,
            title="Child",
            order=2,
            chain_parent=parent,
            is_chain=True,
        )
        resp = api.get(f"{TASKS_URL}{child.id}/chain/")
        assert resp.status_code == 200
        assert len(resp.data) == 2


# ═══════════════════════════════════════════════════════════════════
# 17. MILESTONES
# ═══════════════════════════════════════════════════════════════════


class TestMilestones:
    """Milestone CRUD + complete."""

    @pytest.fixture
    def milestone(self, dream):
        return DreamMilestone.objects.create(
            dream=dream, title="M1", description="Month 1", order=1
        )

    def test_list_milestones(self, api, milestone, dream):
        resp = api.get(f"{MILESTONES_URL}?dream={dream.id}")
        assert resp.status_code == 200

    def test_complete_milestone(self, api, milestone, owner):
        resp = api.post(f"{MILESTONES_URL}{milestone.id}/complete/")
        assert resp.status_code == 200
        milestone.refresh_from_db()
        assert milestone.status == "completed"

    def test_complete_already_completed(self, api, milestone):
        milestone.status = "completed"
        milestone.save()
        resp = api.post(f"{MILESTONES_URL}{milestone.id}/complete/")
        # Idempotent: completing an already-completed milestone returns 200
        assert resp.status_code == 200


# ═══════════════════════════════════════════════════════════════════
# 18. OBSTACLES
# ═══════════════════════════════════════════════════════════════════


class TestObstacles:
    """Obstacle CRUD + resolve."""

    def test_create_obstacle(self, api, dream):
        resp = api.post(
            OBSTACLES_URL,
            {
                "dream": str(dream.id),
                "title": "Lack of time",
                "description": "Hard to find time",
            },
            format="json",
        )
        assert resp.status_code == 201

    def test_list_obstacles(self, api, dream):
        Obstacle.objects.create(dream=dream, title="O1", description="D1")
        resp = api.get(f"{OBSTACLES_URL}?dream={dream.id}")
        assert resp.status_code == 200

    def test_resolve_obstacle(self, api, dream):
        o = Obstacle.objects.create(dream=dream, title="O1", description="D1")
        resp = api.post(f"{OBSTACLES_URL}{o.id}/resolve/")
        assert resp.status_code == 200
        o.refresh_from_db()
        assert o.status == "resolved"


# ═══════════════════════════════════════════════════════════════════
# 19. FOCUS SESSIONS
# ═══════════════════════════════════════════════════════════════════


class TestFocusSessions:
    """Start, complete, history, stats."""

    @pytest.fixture
    def task_for_focus(self, dream):
        g = Goal.objects.create(dream=dream, title="G", order=1)
        return Task.objects.create(goal=g, title="T", order=1, duration_mins=25)

    def test_start_session(self, api, task_for_focus):
        resp = api.post(
            "/api/dreams/focus/start/",
            {
                "task_id": str(task_for_focus.id),
                "duration_minutes": 25,
                "session_type": "work",
            },
            format="json",
        )
        assert resp.status_code == 201

    def test_start_without_task(self, api):
        resp = api.post(
            "/api/dreams/focus/start/",
            {"duration_minutes": 25, "session_type": "work"},
            format="json",
        )
        assert resp.status_code == 201

    def test_start_with_bad_task(self, api):
        resp = api.post(
            "/api/dreams/focus/start/",
            {
                "task_id": str(uuid.uuid4()),
                "duration_minutes": 25,
                "session_type": "work",
            },
            format="json",
        )
        assert resp.status_code == 404

    def test_complete_session(self, api, owner, task_for_focus):
        session = FocusSession.objects.create(
            user=owner,
            task=task_for_focus,
            duration_minutes=25,
            session_type="work",
        )
        resp = api.post(
            "/api/dreams/focus/complete/",
            {"session_id": str(session.id), "actual_minutes": 25},
            format="json",
        )
        assert resp.status_code == 200
        session.refresh_from_db()
        assert session.completed is True

    def test_complete_nonexistent_session(self, api):
        resp = api.post(
            "/api/dreams/focus/complete/",
            {"session_id": str(uuid.uuid4()), "actual_minutes": 10},
            format="json",
        )
        assert resp.status_code == 404

    def test_focus_history(self, api, owner):
        resp = api.get("/api/dreams/focus/history/")
        assert resp.status_code == 200

    def test_focus_stats(self, api, owner):
        resp = api.get("/api/dreams/focus/stats/")
        assert resp.status_code == 200
        assert "weekly" in resp.data
        assert "today" in resp.data


# ═══════════════════════════════════════════════════════════════════
# 20. IDOR GUARDS
# ═══════════════════════════════════════════════════════════════════


class TestIDOR:
    """Ensure users cannot access/modify other users' resources."""

    def test_cannot_retrieve_other_dream(self, api_other, dream):
        """Other user cannot retrieve a non-public dream."""
        resp = api_other.get(_dream_url(dream.id))
        assert resp.status_code == 404

    def test_cannot_update_other_dream(self, api_other, dream):
        resp = api_other.patch(
            _dream_url(dream.id),
            {"title": "Hacked"},
            format="json",
        )
        assert resp.status_code == 404

    def test_cannot_delete_other_dream(self, api_other, dream):
        resp = api_other.delete(_dream_url(dream.id))
        assert resp.status_code == 404

    def test_cannot_analyze_other_dream(self, api_other, dream):
        resp = api_other.post(_dream_url(dream.id, "analyze"))
        assert resp.status_code == 404

    def test_cannot_share_other_dream(self, api_other, dream, other):
        resp = api_other.post(
            _dream_url(dream.id, "share"),
            {"shared_with_id": str(other.id)},
            format="json",
        )
        assert resp.status_code == 404

    def test_cannot_duplicate_other_dream(self, api_other, dream):
        resp = api_other.post(_dream_url(dream.id, "duplicate"))
        assert resp.status_code == 404

    def test_cannot_add_tag_to_other_dream(self, api_other, dream):
        resp = api_other.post(
            _dream_url(dream.id, "tags"),
            {"tag_name": "hack"},
            format="json",
        )
        assert resp.status_code == 404

    def test_cannot_access_other_goals(self, api_other, dream):
        g = Goal.objects.create(dream=dream, title="G", order=1)
        resp = api_other.get(f"{GOALS_URL}{g.id}/")
        assert resp.status_code == 404

    def test_cannot_complete_other_goal(self, api_other, dream):
        g = Goal.objects.create(dream=dream, title="G", order=1)
        resp = api_other.post(f"{GOALS_URL}{g.id}/complete/")
        assert resp.status_code == 404

    def test_cannot_access_other_tasks(self, api_other, dream):
        g = Goal.objects.create(dream=dream, title="G", order=1)
        t = Task.objects.create(goal=g, title="T", order=1)
        resp = api_other.get(f"{TASKS_URL}{t.id}/")
        assert resp.status_code == 404

    def test_cannot_complete_other_task(self, api_other, dream):
        g = Goal.objects.create(dream=dream, title="G", order=1)
        t = Task.objects.create(goal=g, title="T", order=1)
        resp = api_other.post(f"{TASKS_URL}{t.id}/complete/")
        assert resp.status_code == 404

    def test_cannot_create_goal_for_other_dream(self, api_other, dream):
        resp = api_other.post(
            GOALS_URL,
            {"dream": str(dream.id), "title": "Hack", "description": "IDOR"},
            format="json",
        )
        assert resp.status_code == 403

    def test_cannot_create_task_for_other_goal(self, api_other, dream):
        g = Goal.objects.create(dream=dream, title="G", order=1)
        resp = api_other.post(
            TASKS_URL,
            {"goal": str(g.id), "title": "Hack"},
            format="json",
        )
        assert resp.status_code == 403

    def test_cannot_create_obstacle_for_other_dream(self, api_other, dream):
        resp = api_other.post(
            OBSTACLES_URL,
            {"dream": str(dream.id), "title": "Hack", "description": "IDOR"},
            format="json",
        )
        assert resp.status_code == 403

    def test_cannot_access_other_journal(self, api_other, dream):
        j = DreamJournal.objects.create(dream=dream, title="J", content="C")
        resp = api_other.get(f"{JOURNAL_URL}{j.id}/")
        assert resp.status_code == 404

    def test_cannot_access_other_milestone(self, api_other, dream):
        m = DreamMilestone.objects.create(dream=dream, title="M", order=1)
        resp = api_other.get(f"{MILESTONES_URL}{m.id}/")
        assert resp.status_code == 404

    def test_cannot_access_other_obstacle(self, api_other, dream):
        o = Obstacle.objects.create(dream=dream, title="O", description="D")
        resp = api_other.get(f"{OBSTACLES_URL}{o.id}/")
        assert resp.status_code == 404

    def test_cannot_access_other_checkin(self, api_other, dream_with_plan):
        ci = PlanCheckIn.objects.create(
            dream=dream_with_plan,
            status="completed",
            scheduled_for=timezone.now(),
        )
        resp = api_other.get(f"{CHECKINS_URL}{ci.id}/")
        assert resp.status_code == 404

    def test_public_dream_readable(self, api_other, dream):
        """Public dreams should be retrievable by other users."""
        dream.is_public = True
        dream.save()
        resp = api_other.get(_dream_url(dream.id))
        assert resp.status_code == 200

    def test_cannot_complete_other_focus_session(self, api_other, owner, dream):
        g = Goal.objects.create(dream=dream, title="G", order=1)
        t = Task.objects.create(goal=g, title="T", order=1)
        session = FocusSession.objects.create(
            user=owner, task=t, duration_minutes=25, session_type="work"
        )
        resp = api_other.post(
            "/api/dreams/focus/complete/",
            {"session_id": str(session.id), "actual_minutes": 25},
            format="json",
        )
        assert resp.status_code == 404


# ═══════════════════════════════════════════════════════════════════
# 21. AI ENDPOINTS (ADDITIONAL)
# ═══════════════════════════════════════════════════════════════════


class TestAIEndpoints:
    """Additional AI endpoints: auto-categorize, predict obstacles, etc."""

    @patch("integrations.openai_service.OpenAIService.auto_categorize")
    @patch("core.ai_usage.AIUsageTracker.increment")
    def test_auto_categorize(self, _inc, mock_ai, api):
        mock_ai.return_value = {"category": "health", "tags": ["fitness"]}
        resp = api.post(
            f"{DREAMS_URL}auto-categorize/",
            {
                "title": "Run marathon",
                "description": "Train for and complete a marathon running event",
            },
            format="json",
        )
        assert resp.status_code == 200

    def test_auto_categorize_missing_fields(self, api):
        resp = api.post(
            f"{DREAMS_URL}auto-categorize/",
            {"title": "X"},
            format="json",
        )
        assert resp.status_code == 400

    @patch("integrations.openai_service.OpenAIService.predict_obstacles")
    @patch("core.ai_usage.AIUsageTracker.increment")
    def test_predict_obstacles(self, _inc, mock_ai, api, dream):
        mock_ai.return_value = {"obstacles": [{"title": "Time", "risk": "high"}]}
        resp = api.post(_dream_url(dream.id, "predict-obstacles"))
        assert resp.status_code == 200

    @patch("integrations.openai_service.OpenAIService.generate_starters")
    @patch("core.ai_usage.AIUsageTracker.increment")
    def test_conversation_starters(self, _inc, mock_ai, api, dream):
        mock_ai.return_value = {"starters": ["How about...", "Let's try..."]}
        resp = api.get(_dream_url(dream.id, "conversation-starters"))
        assert resp.status_code == 200

    @patch("integrations.openai_service.OpenAIService.find_similar_dreams")
    @patch("core.ai_usage.AIUsageTracker.increment")
    def test_similar_dreams(self, _inc, mock_ai, api, dream):
        mock_ai.return_value = {"similar_dreams": [], "similar_templates": []}
        resp = api.get(_dream_url(dream.id, "similar"))
        assert resp.status_code == 200

    @patch("integrations.openai_service.OpenAIService.smart_analysis")
    @patch("core.ai_validators.validate_smart_analysis_response")
    @patch("core.ai_usage.AIUsageTracker.increment")
    def test_smart_analysis(self, _inc, mock_validate, mock_ai, api, dream):
        result_mock = Mock()
        result_mock.model_dump.return_value = {
            "patterns": [],
            "synergies": [],
            "risks": [],
        }
        mock_validate.return_value = result_mock
        mock_ai.return_value = {}
        resp = api.get(f"{DREAMS_URL}smart-analysis/")
        assert resp.status_code == 200

    def test_smart_analysis_no_dreams(self, api, owner):
        # Delete all dreams
        Dream.objects.filter(user=owner).delete()
        resp = api.get(f"{DREAMS_URL}smart-analysis/")
        assert resp.status_code == 400

    @patch("integrations.openai_service.OpenAIService.generate_two_minute_start")
    @patch("core.ai_usage.AIUsageTracker.increment")
    def test_two_minute_start(self, _inc, mock_ai, api, dream):
        mock_ai.return_value = "Write one sentence about your dream"
        resp = api.post(_dream_url(dream.id, "generate_two_minute_start"))
        assert resp.status_code == 200
        dream.refresh_from_db()
        assert dream.has_two_minute_start is True

    def test_two_minute_start_already_generated(self, api, dream):
        dream.has_two_minute_start = True
        dream.save()
        resp = api.post(_dream_url(dream.id, "generate_two_minute_start"))
        assert resp.status_code == 400


# ═══════════════════════════════════════════════════════════════════
# 22. GOAL REFINE
# ═══════════════════════════════════════════════════════════════════


class TestGoalRefine:
    """POST /goals/refine/"""

    @patch("integrations.openai_service.OpenAIService.refine_goal")
    @patch("core.ai_usage.AIUsageTracker.check_quota", return_value=(True, {}))
    @patch("core.ai_usage.AIUsageTracker.increment")
    def test_refine_goal(self, _inc, _quota, mock_ai, api, dream):
        g = Goal.objects.create(dream=dream, title="G1", description="D1", order=1)
        mock_ai.return_value = {
            "message": "Let me help refine this.",
            "refined_goal": {"title": "Improved G1"},
            "milestones": None,
            "is_complete": False,
        }
        resp = api.post(
            f"{GOALS_URL}refine/",
            {"goal_id": str(g.id), "message": "Help me refine this goal"},
            format="json",
        )
        assert resp.status_code == 200
        assert "message" in resp.data

    def test_refine_goal_missing_id(self, api):
        resp = api.post(
            f"{GOALS_URL}refine/",
            {"message": "Help"},
            format="json",
        )
        assert resp.status_code == 400

    def test_refine_goal_empty_message(self, api, dream):
        g = Goal.objects.create(dream=dream, title="G", description="D", order=1)
        resp = api.post(
            f"{GOALS_URL}refine/",
            {"goal_id": str(g.id), "message": ""},
            format="json",
        )
        assert resp.status_code == 400

    def test_refine_other_user_goal(self, api_other, dream):
        g = Goal.objects.create(dream=dream, title="G", description="D", order=1)
        resp = api_other.post(
            f"{GOALS_URL}refine/",
            {"goal_id": str(g.id), "message": "Hack"},
            format="json",
        )
        assert resp.status_code == 404


# ═══════════════════════════════════════════════════════════════════
# 23. TASK AI ENDPOINTS
# ═══════════════════════════════════════════════════════════════════


class TestTaskAI:
    """Daily priorities, estimate durations, parse natural, calibrate difficulty."""

    @pytest.fixture
    def task_for_ai(self, dream):
        g = Goal.objects.create(dream=dream, title="G", order=1)
        return Task.objects.create(
            goal=g, title="Study", order=1, duration_mins=30, status="pending"
        )

    @patch("integrations.openai_service.OpenAIService.prioritize_tasks")
    @patch("core.ai_usage.AIUsageTracker.increment")
    def test_daily_priorities(self, _inc, mock_ai, api, task_for_ai):
        mock_ai.return_value = {
            "prioritized_tasks": [{"task_id": str(task_for_ai.id)}],
            "focus_task": {"task_id": str(task_for_ai.id)},
            "quick_wins": [],
        }
        resp = api.get(f"{TASKS_URL}daily-priorities/")
        assert resp.status_code == 200

    @patch("integrations.openai_service.OpenAIService.estimate_durations")
    @patch("core.ai_usage.AIUsageTracker.increment")
    def test_estimate_durations(self, _inc, mock_ai, api, task_for_ai):
        mock_ai.return_value = {
            "estimates": [
                {
                    "task_id": str(task_for_ai.id),
                    "optimistic_minutes": 20,
                    "realistic_minutes": 30,
                    "pessimistic_minutes": 45,
                }
            ]
        }
        resp = api.post(
            f"{TASKS_URL}estimate-durations/",
            {"task_ids": [str(task_for_ai.id)]},
            format="json",
        )
        assert resp.status_code == 200

    def test_estimate_durations_empty(self, api):
        resp = api.post(
            f"{TASKS_URL}estimate-durations/",
            {"task_ids": []},
            format="json",
        )
        assert resp.status_code == 400

    def test_estimate_durations_too_many(self, api):
        resp = api.post(
            f"{TASKS_URL}estimate-durations/",
            {"task_ids": [str(uuid.uuid4()) for _ in range(51)]},
            format="json",
        )
        assert resp.status_code == 400

    @patch("integrations.openai_service.OpenAIService.parse_natural_language_tasks")
    @patch("core.ai_usage.AIUsageTracker.increment")
    def test_parse_natural(self, _inc, mock_ai, api, dream):
        mock_ai.return_value = {
            "tasks": [{"title": "Do X", "matched_dream_id": str(dream.id)}]
        }
        resp = api.post(
            f"{TASKS_URL}parse-natural/",
            {"text": "I need to do X and Y today"},
            format="json",
        )
        assert resp.status_code == 200

    def test_parse_natural_empty(self, api):
        resp = api.post(
            f"{TASKS_URL}parse-natural/",
            {"text": ""},
            format="json",
        )
        assert resp.status_code == 400

    def test_create_from_parsed(self, api, dream):
        g = Goal.objects.create(dream=dream, title="G", order=1)
        resp = api.post(
            f"{TASKS_URL}create-from-parsed/",
            {
                "tasks": [
                    {
                        "title": "Parsed Task",
                        "matched_dream_id": str(dream.id),
                        "matched_goal_id": str(g.id),
                        "duration_mins": 15,
                    }
                ]
            },
            format="json",
        )
        assert resp.status_code == 201

    def test_create_from_parsed_empty(self, api):
        resp = api.post(
            f"{TASKS_URL}create-from-parsed/",
            {"tasks": []},
            format="json",
        )
        assert resp.status_code == 400

    @patch("integrations.openai_service.OpenAIService.calibrate_difficulty")
    @patch("core.ai_usage.AIUsageTracker.increment")
    def test_calibrate_difficulty(self, _inc, mock_ai, api, task_for_ai):
        mock_ai.return_value = {
            "difficulty_level": "moderate",
            "calibration_score": 0.7,
            "analysis": "Good balance",
            "suggestions": [],
            "daily_target": {"tasks": 3, "focus_minutes": 60, "reason": "OK"},
            "challenge": None,
        }
        resp = api.get(f"{TASKS_URL}calibrate-difficulty/")
        assert resp.status_code == 200

    def test_apply_calibration(self, api, dream):
        g = Goal.objects.create(dream=dream, title="G", order=1)
        t = Task.objects.create(goal=g, title="T", order=1, duration_mins=30)
        resp = api.post(
            f"{TASKS_URL}apply-calibration/",
            {
                "suggestions": [
                    {
                        "task_id": str(t.id),
                        "modified_task": {
                            "title": "Modified T",
                            "duration_mins": 20,
                        },
                    }
                ]
            },
            format="json",
        )
        assert resp.status_code == 200
        t.refresh_from_db()
        assert t.title == "Modified T"
        assert t.duration_mins == 20

    def test_apply_calibration_empty(self, api):
        resp = api.post(
            f"{TASKS_URL}apply-calibration/",
            {"suggestions": []},
            format="json",
        )
        assert resp.status_code == 400


# ═══════════════════════════════════════════════════════════════════
# 24. SUBSCRIPTION PERMISSION GUARDS
# ═══════════════════════════════════════════════════════════════════


class TestSubscriptionGuards:
    """Free users blocked from AI features, pro features."""

    def test_free_user_blocked_from_analyze(self, api_free, free_user):
        d = Dream.objects.create(
            user=free_user,
            title="Free Dream",
            description="A dream for free users to test",
            category="personal",
        )
        resp = api_free.post(_dream_url(d.id, "analyze"))
        assert resp.status_code == 403

    def test_free_user_blocked_from_refine(self, api_free):
        resp = api_free.post(
            f"{DREAMS_URL}refine/",
            {
                "title": "My title here",
                "description": "Long enough desc for validation",
            },
            format="json",
        )
        assert resp.status_code == 403

    def test_free_user_can_create_dream(self, api_free):
        with patch(
            "core.moderation.ContentModerationService.moderate_text",
            return_value=Mock(is_flagged=False),
        ):
            resp = api_free.post(
                DREAMS_URL,
                {
                    "title": "Free dream",
                    "description": "A dream anyone can create",
                    "category": "personal",
                },
                format="json",
            )
        assert resp.status_code == 201


# ═══════════════════════════════════════════════════════════════════
# 25. CALIBRATION EXTENDED
# ═══════════════════════════════════════════════════════════════════


class TestCalibrationExtended:
    """Additional calibration tests for deeper coverage."""

    def test_start_calibration_resume_in_progress(self, api, dream):
        """Resume returns existing unanswered questions."""
        dream.calibration_status = "in_progress"
        dream.save()
        CalibrationResponse.objects.create(
            dream=dream, question="Q1?", question_number=1, answer=""
        )
        resp = api.post(_dream_url(dream.id, "start_calibration"))
        assert resp.status_code == 200
        assert resp.data["status"] == "in_progress"

    def test_start_calibration_generating_lock(self, api, dream):
        """Returns 'generating' when Redis lock is active."""
        dream.calibration_status = "in_progress"
        dream.save()
        # No unanswered questions — all answered
        CalibrationResponse.objects.create(
            dream=dream, question="Q1?", question_number=1, answer="A1"
        )
        # Simulate the lock being active
        from django.core.cache import cache

        lock_key = f"calibration:generating:{dream.id}"
        cache.set(lock_key, "1", timeout=60)
        try:
            resp = api.post(_dream_url(dream.id, "start_calibration"))
            assert resp.status_code == 200
            assert resp.data["status"] == "generating"
        finally:
            cache.delete(lock_key)

    @patch("core.moderation.ContentModerationService.moderate_text")
    def test_answer_single_format(self, mock_mod, api, dream):
        """Test single-answer format from frontend."""
        mock_mod.return_value = Mock(is_flagged=False)
        dream.calibration_status = "in_progress"
        dream.save()
        cr = CalibrationResponse.objects.create(
            dream=dream, question="How much time?", question_number=1
        )
        # Fill up to 10 answered to trigger completion
        for i in range(2, 11):
            CalibrationResponse.objects.create(
                dream=dream, question=f"Q{i}", question_number=i, answer=f"A{i}"
            )
        resp = api.post(
            _dream_url(dream.id, "answer_calibration"),
            {
                "question": "How much time?",
                "answer": "About 30 minutes daily practicing piano",
                "question_number": 1,
            },
            format="json",
        )
        assert resp.status_code == 200

    @patch("core.moderation.ContentModerationService.moderate_text")
    def test_answer_too_short(self, mock_mod, api, dream):
        """Short answer rejected."""
        mock_mod.return_value = Mock(is_flagged=False)
        dream.calibration_status = "in_progress"
        dream.save()
        CalibrationResponse.objects.create(
            dream=dream, question="Q1", question_number=1
        )
        resp = api.post(
            _dream_url(dream.id, "answer_calibration"),
            {"answers": [{"question_id": "fake", "answer": "ab"}]},
            format="json",
        )
        assert resp.status_code == 400

    @patch("core.moderation.ContentModerationService.moderate_text")
    def test_answer_moderation_flagged(self, mock_mod, api, dream):
        """Moderated answer rejected."""
        mock_mod.return_value = Mock(is_flagged=True, user_message="Blocked")
        dream.calibration_status = "in_progress"
        dream.save()
        CalibrationResponse.objects.create(
            dream=dream, question="Q1", question_number=1
        )
        resp = api.post(
            _dream_url(dream.id, "answer_calibration"),
            {"answers": [{"question_id": "fake", "answer": "Bad content here"}]},
            format="json",
        )
        assert resp.status_code == 400

    def test_answer_no_answers_provided(self, api, dream):
        """No answers provided."""
        dream.calibration_status = "in_progress"
        dream.save()
        resp = api.post(
            _dream_url(dream.id, "answer_calibration"),
            {},
            format="json",
        )
        assert resp.status_code == 400

    @patch("core.moderation.ContentModerationService.moderate_text")
    def test_answer_already_answered_question(self, mock_mod, api, dream):
        """Answering same question twice blocked."""
        mock_mod.return_value = Mock(is_flagged=False)
        dream.calibration_status = "in_progress"
        dream.save()
        cr = CalibrationResponse.objects.create(
            dream=dream, question="Q1", question_number=1, answer="Already answered"
        )
        resp = api.post(
            _dream_url(dream.id, "answer_calibration"),
            {"answers": [{"question_id": str(cr.id), "answer": "Try again please"}]},
            format="json",
        )
        assert resp.status_code == 400

    @patch("core.moderation.ContentModerationService.moderate_text")
    def test_answer_force_complete_at_25(self, mock_mod, api, dream):
        """Force complete when 25 questions reached."""
        mock_mod.return_value = Mock(is_flagged=False)
        dream.calibration_status = "in_progress"
        dream.save()
        for i in range(1, 26):
            CalibrationResponse.objects.create(
                dream=dream,
                question=f"Q{i}",
                question_number=i,
                answer=f"A{i}" if i < 25 else "",
            )
        cr = CalibrationResponse.objects.get(dream=dream, question_number=25)
        resp = api.post(
            _dream_url(dream.id, "answer_calibration"),
            {
                "answers": [
                    {
                        "question_id": str(cr.id),
                        "answer": "Final answer for question 25",
                    }
                ]
            },
            format="json",
        )
        assert resp.status_code == 200
        assert resp.data["status"] == "completed"

    @patch("integrations.openai_service.OpenAIService.generate_calibration_questions")
    @patch("apps.dreams.views.validate_calibration_questions")
    @patch("core.moderation.ContentModerationService.moderate_text")
    @patch("core.ai_usage.AIUsageTracker.increment")
    def test_answer_gets_followups(
        self, _inc, mock_mod, mock_validate, mock_ai, api, dream
    ):
        """AI returns follow-up questions."""
        mock_mod.return_value = Mock(is_flagged=False)
        dream.calibration_status = "in_progress"
        dream.save()
        # Create 7 questions, answer 6, leave 1 unanswered
        for i in range(1, 8):
            CalibrationResponse.objects.create(
                dream=dream,
                question=f"Q{i}",
                question_number=i,
                answer=f"A{i}" if i < 7 else "",
            )
        cr = CalibrationResponse.objects.get(dream=dream, question_number=7)

        q_mock = Mock()
        q_mock.question = "Follow-up Q"
        q_mock.category = "specifics"
        result = Mock()
        result.refusal_reason = None
        result.sufficient = False
        result.questions = [q_mock]
        result.confidence_score = 0.6
        result.missing_areas = ["timeline"]
        mock_validate.return_value = result

        resp = api.post(
            _dream_url(dream.id, "answer_calibration"),
            {
                "answers": [
                    {"question_id": str(cr.id), "answer": "My answer to this question"}
                ]
            },
            format="json",
        )
        assert resp.status_code == 200
        assert resp.data["status"] == "in_progress"


# ═══════════════════════════════════════════════════════════════════
# 26. PDF EXPORT EXTENDED
# ═══════════════════════════════════════════════════════════════════


class TestPDFExportExtended:
    """PDF export with actual reportlab if available."""

    def test_export_pdf_real(self, api, dream):
        """Try real PDF export."""
        g = Goal.objects.create(dream=dream, title="G1", description="D1", order=1)
        Task.objects.create(
            goal=g, title="T1", order=1, duration_mins=30, status="completed"
        )
        Task.objects.create(goal=g, title="T2", order=2, duration_mins=15)
        Obstacle.objects.create(
            dream=dream, title="O1", description="D1", solution="S1"
        )
        resp = api.get(f"/api/dreams/dreams/{dream.id}/export-pdf/")
        # Either 200 (reportlab installed) or 501 (not installed)
        assert resp.status_code in (200, 501)

    def test_export_pdf_with_target_date(self, api, dream):
        """PDF with target date."""
        dream.target_date = timezone.now() + timedelta(days=90)
        dream.save()
        resp = api.get(f"/api/dreams/dreams/{dream.id}/export-pdf/")
        assert resp.status_code in (200, 501)


# ═══════════════════════════════════════════════════════════════════
# 27. PROGRESS PHOTO ANALYSIS
# ═══════════════════════════════════════════════════════════════════


class TestProgressPhotoAnalysis:
    """AI analysis of progress photos."""

    @patch("integrations.openai_service.OpenAIService.analyze_progress_image")
    @patch("core.ai_usage.AIUsageTracker.increment")
    @patch(
        "core.ai_usage.AIUsageTracker.check_quota",
        return_value=(True, {"limit": 10, "used": 0}),
    )
    def test_analyze_photo(self, _quota, _inc, mock_ai, pro_user):
        """Analyze requires AI image quota (pro plan)."""
        pro_dream = Dream.objects.create(
            user=pro_user, title="Pro Dream", description="D", category="hobbies"
        )
        mock_ai.return_value = {"analysis": "Good progress visible"}
        photo = ProgressPhoto.objects.create(
            dream=pro_dream,
            image=SimpleUploadedFile(
                "p.png", _make_png_bytes(), content_type="image/png"
            ),
            taken_at=timezone.now(),
        )
        pro_client = APIClient()
        pro_client.force_authenticate(user=pro_user)
        resp = pro_client.post(
            f"{DREAMS_URL}{pro_dream.id}/progress-photos/{photo.id}/analyze/"
        )
        assert resp.status_code == 200

    def test_analyze_nonexistent_photo(self, api, dream):
        with patch(
            "core.ai_usage.AIUsageTracker.check_quota",
            return_value=(True, {"limit": 10, "used": 0}),
        ):
            resp = api.post(
                f"{DREAMS_URL}{dream.id}/progress-photos/{uuid.uuid4()}/analyze/"
            )
        assert resp.status_code == 404


# ═══════════════════════════════════════════════════════════════════
# 28. MILESTONE IDOR + CREATE GUARD
# ═══════════════════════════════════════════════════════════════════


class TestMilestoneCreateGuard:
    """Milestone IDOR protection on create."""

    def test_cannot_create_milestone_for_other_dream(self, api_other, dream):
        resp = api_other.post(
            MILESTONES_URL,
            {
                "dream": str(dream.id),
                "title": "Hack",
                "description": "IDOR",
                "order": 1,
            },
            format="json",
        )
        assert resp.status_code == 403


# ═══════════════════════════════════════════════════════════════════
# 29. EDGE CASES
# ═══════════════════════════════════════════════════════════════════


class TestEdgeCases:
    """Various edge cases for branch coverage."""

    def test_explore_with_category_filter(self, api, other):
        Dream.objects.create(
            user=other,
            title="P",
            description="Public",
            category="health",
            is_public=True,
            status="active",
        )
        resp = api.get(f"{DREAMS_URL}explore/?category=health")
        assert resp.status_code == 200

    def test_explore_with_ordering(self, api, other):
        Dream.objects.create(
            user=other,
            title="P",
            description="Public",
            category="health",
            is_public=True,
            status="active",
        )
        resp = api.get(f"{DREAMS_URL}explore/?ordering=-progress_percentage")
        assert resp.status_code == 200

    def test_explore_invalid_ordering(self, api, other):
        Dream.objects.create(
            user=other,
            title="P",
            description="Public",
            category="health",
            is_public=True,
            status="active",
        )
        resp = api.get(f"{DREAMS_URL}explore/?ordering=hacked")
        assert resp.status_code == 200  # Falls back to -created_at

    def test_analytics_with_range(self, api, dream):
        resp = api.get(f"{DREAMS_URL}{dream.id}/analytics/?range=1m")
        assert resp.status_code == 200

    def test_analytics_with_range_1w(self, api, dream):
        resp = api.get(f"{DREAMS_URL}{dream.id}/analytics/?range=1w")
        assert resp.status_code == 200

    def test_analytics_with_range_3m(self, api, dream):
        resp = api.get(f"{DREAMS_URL}{dream.id}/analytics/?range=3m")
        assert resp.status_code == 200

    def test_checkin_respond_missing_required(self, api, dream_with_plan):
        ci = PlanCheckIn.objects.create(
            dream=dream_with_plan,
            status="awaiting_user",
            scheduled_for=timezone.now(),
            questionnaire=[
                {"id": "q1", "text": "Q?", "is_required": True},
                {"id": "q2", "text": "Q2?", "is_required": True},
            ],
        )
        resp = api.post(
            f"{CHECKINS_URL}{ci.id}/respond/",
            {"responses": {"q1": "Only one"}},
            format="json",
        )
        assert resp.status_code == 400

    @patch("apps.dreams.tasks.get_plan_status", return_value=None)
    def test_plan_status_completed(self, _mock, api, dream_with_plan):
        """Dream with existing milestones shows completed status."""
        resp = api.get(_dream_url(dream_with_plan.id, "plan_status"))
        assert resp.status_code == 200
        assert resp.data["status"] == "completed"

    @patch("apps.dreams.tasks.generate_dream_skeleton_task.apply_async")
    @patch("apps.dreams.tasks.set_plan_status")
    @patch("apps.dreams.tasks.get_plan_status")
    def test_generate_plan_already_generating(self, mock_get, _set, _task, api, dream):
        mock_get.return_value = {"status": "generating", "message": "Working..."}
        resp = api.post(_dream_url(dream.id, "generate_plan"))
        assert resp.status_code == 202
        assert resp.data["status"] == "generating"

    @patch("apps.dreams.tasks.generate_checkin_questionnaire_task.apply_async")
    def test_trigger_checkin_active_exists(self, _task, api, dream_with_plan):
        """Active check-in already in progress returns 202."""
        PlanCheckIn.objects.create(
            dream=dream_with_plan,
            status="pending",
            scheduled_for=timezone.now(),
        )
        resp = api.post(_dream_url(dream_with_plan.id, "trigger-checkin"))
        assert resp.status_code == 202

    def test_quick_create_no_active_dream(self, api, owner):
        """Quick create fails when no active dreams."""
        Dream.objects.filter(user=owner).update(status="archived")
        resp = api.post(
            f"{TASKS_URL}quick_create/",
            {"title": "Orphan task"},
            format="json",
        )
        assert resp.status_code == 400

    def test_quick_create_bad_dream_id(self, api):
        resp = api.post(
            f"{TASKS_URL}quick_create/",
            {"title": "Task", "dream_id": str(uuid.uuid4())},
            format="json",
        )
        assert resp.status_code == 400

    def test_create_goal_auto_order(self, api, dream):
        """Goal order auto-computed when not provided."""
        ms = DreamMilestone.objects.create(dream=dream, title="M", order=1)
        Goal.objects.create(dream=dream, milestone=ms, title="Existing", order=1)
        resp = api.post(
            GOALS_URL,
            {"dream": str(dream.id), "milestone": str(ms.id), "title": "Auto"},
            format="json",
        )
        assert resp.status_code == 201

    def test_create_task_auto_order(self, api, dream):
        """Task order auto-computed when not provided."""
        g = Goal.objects.create(dream=dream, title="G", order=1)
        Task.objects.create(goal=g, title="Existing", order=1)
        resp = api.post(
            TASKS_URL,
            {"goal": str(g.id), "title": "Auto"},
            format="json",
        )
        assert resp.status_code == 201

    def test_vision_board_add_sets_primary_url(self, api, dream):
        """First vision board image sets dream.vision_image_url."""
        assert not dream.vision_image_url
        with patch("core.validators.validate_url_no_ssrf"):
            api.post(
                _dream_url(dream.id, "vision-board/add"),
                {"image_url": "https://example.com/first.png"},
            )
        dream.refresh_from_db()
        assert dream.vision_image_url == "https://example.com/first.png"

    def test_auto_categorize_short_description(self, api):
        resp = api.post(
            f"{DREAMS_URL}auto-categorize/",
            {"title": "Run", "description": "Short"},
            format="json",
        )
        assert resp.status_code == 400

    def test_focus_session_incomplete(self, api, owner, dream):
        """Session not completed if actual < planned minutes."""
        g = Goal.objects.create(dream=dream, title="G", order=1)
        t = Task.objects.create(goal=g, title="T", order=1, duration_mins=25)
        s = FocusSession.objects.create(
            user=owner, task=t, duration_minutes=25, session_type="work"
        )
        resp = api.post(
            "/api/dreams/focus/complete/",
            {"session_id": str(s.id), "actual_minutes": 10},
            format="json",
        )
        assert resp.status_code == 200
        s.refresh_from_db()
        assert s.completed is False  # 10 < 25

    def test_template_filter_by_category(self, api):
        DreamTemplate.objects.create(
            title="T1",
            description="D1",
            category="health",
            template_goals=[],
            is_active=True,
        )
        resp = api.get("/api/dreams/dreams/templates/?category=health")
        assert resp.status_code == 200

    def test_goals_filter_by_milestone(self, api, dream):
        ms = DreamMilestone.objects.create(dream=dream, title="M", order=1)
        Goal.objects.create(dream=dream, milestone=ms, title="G", order=1)
        resp = api.get(f"{GOALS_URL}?milestone={ms.id}")
        assert resp.status_code == 200

    def test_tasks_filter_by_goal(self, api, dream):
        g = Goal.objects.create(dream=dream, title="G", order=1)
        Task.objects.create(goal=g, title="T", order=1)
        resp = api.get(f"{TASKS_URL}?goal={g.id}")
        assert resp.status_code == 200

    def test_obstacles_filter_by_dream(self, api, dream):
        Obstacle.objects.create(dream=dream, title="O", description="D")
        resp = api.get(f"{OBSTACLES_URL}?dream={dream.id}")
        assert resp.status_code == 200

    def test_journal_filter_by_mood(self, api, dream):
        DreamJournal.objects.create(dream=dream, title="J", content="C", mood="happy")
        resp = api.get(f"{JOURNAL_URL}?mood=happy")
        assert resp.status_code == 200

    def test_checkin_filter_by_status(self, api, dream_with_plan):
        PlanCheckIn.objects.create(
            dream=dream_with_plan, status="completed", scheduled_for=timezone.now()
        )
        resp = api.get(f"{CHECKINS_URL}?status=completed")
        assert resp.status_code == 200

    def test_daily_priorities_no_tasks(self, api, owner):
        """Empty tasks returns empty list."""
        Dream.objects.filter(user=owner).delete()
        resp = api.get(f"{TASKS_URL}daily-priorities/")
        assert resp.status_code == 200

    @patch("integrations.openai_service.OpenAIService.estimate_durations")
    @patch("core.ai_usage.AIUsageTracker.increment")
    def test_estimate_durations_with_apply(self, _inc, mock_ai, api, dream):
        g = Goal.objects.create(dream=dream, title="G", order=1)
        t = Task.objects.create(goal=g, title="T", order=1, duration_mins=30)
        mock_ai.return_value = {
            "estimates": [
                {
                    "task_id": str(t.id),
                    "optimistic_minutes": 20,
                    "realistic_minutes": 25,
                    "pessimistic_minutes": 40,
                }
            ]
        }
        resp = api.post(
            f"{TASKS_URL}estimate-durations/",
            {"task_ids": [str(t.id)], "apply": True},
            format="json",
        )
        assert resp.status_code == 200
        assert resp.data["applied"] is True
        t.refresh_from_db()
        assert t.duration_mins == 25

    def test_parse_natural_too_long(self, api):
        resp = api.post(
            f"{TASKS_URL}parse-natural/",
            {"text": "x" * 5001},
            format="json",
        )
        assert resp.status_code == 400
