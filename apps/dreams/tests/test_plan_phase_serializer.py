"""
Regression tests: plan_phase field present in DreamSerializer and DreamDetailSerializer.
"""

import pytest
from rest_framework.test import APIRequestFactory

from apps.dreams.models import Dream
from apps.dreams.serializers import DreamDetailSerializer, DreamSerializer
from apps.users.models import User


@pytest.fixture
def phase_user(db):
    return User.objects.create_user(
        email="phase@test.com",
        password="testpass123",
        display_name="Phase User",
    )


@pytest.fixture
def phase_dream(phase_user):
    return Dream.objects.create(
        user=phase_user,
        title="Phase Test Dream",
        description="Dream for plan_phase testing",
        category="education",
        status="active",
        plan_phase="partial",
    )


def _serialize(dream, user, serializer_class):
    factory = APIRequestFactory()
    request = factory.get("/")
    request.user = user
    return serializer_class(dream, context={"request": request}).data


@pytest.mark.django_db
class TestPlanPhaseInDreamSerializer:
    """Verify DreamSerializer includes plan_phase field."""

    def test_plan_phase_present(self, phase_dream, phase_user):
        data = _serialize(phase_dream, phase_user, DreamSerializer)
        assert "plan_phase" in data

    def test_plan_phase_value_partial(self, phase_dream, phase_user):
        data = _serialize(phase_dream, phase_user, DreamSerializer)
        assert data["plan_phase"] == "partial"

    def test_plan_phase_value_full(self, phase_dream, phase_user):
        phase_dream.plan_phase = "full"
        phase_dream.save(update_fields=["plan_phase"])
        data = _serialize(phase_dream, phase_user, DreamSerializer)
        assert data["plan_phase"] == "full"

    def test_plan_phase_value_none(self, phase_dream, phase_user):
        phase_dream.plan_phase = "none"
        phase_dream.save(update_fields=["plan_phase"])
        data = _serialize(phase_dream, phase_user, DreamSerializer)
        assert data["plan_phase"] == "none"


@pytest.mark.django_db
class TestPlanPhaseInDreamDetailSerializer:
    """Verify DreamDetailSerializer includes plan_phase field."""

    def test_plan_phase_present(self, phase_dream, phase_user):
        data = _serialize(phase_dream, phase_user, DreamDetailSerializer)
        assert "plan_phase" in data

    def test_plan_phase_value_partial(self, phase_dream, phase_user):
        data = _serialize(phase_dream, phase_user, DreamDetailSerializer)
        assert data["plan_phase"] == "partial"

    def test_plan_phase_value_full(self, phase_dream, phase_user):
        phase_dream.plan_phase = "full"
        phase_dream.save(update_fields=["plan_phase"])
        data = _serialize(phase_dream, phase_user, DreamDetailSerializer)
        assert data["plan_phase"] == "full"
