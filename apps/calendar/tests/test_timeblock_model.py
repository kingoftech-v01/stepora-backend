"""
Regression tests for TimeBlock model changes.

Covers:
- TimeBlock creation with title, color, dream FK
- block_type default is "personal"
- TimeBlock serializer includes new fields (title, color, dream_id)
"""

from datetime import time

import pytest

from apps.calendar.models import TimeBlock
from apps.calendar.serializers import TimeBlockSerializer
from apps.dreams.models import Dream
from apps.users.models import User

# ───────────────────────────────────────────────────────────────────
# Fixtures
# ───────────────────────────────────────────────────────────────────


@pytest.fixture
def tb_user(db):
    return User.objects.create_user(
        email="tb_user@test.com",
        password="testpass123",
        display_name="TB User",
        timezone="Europe/Paris",
    )


@pytest.fixture
def tb_dream(tb_user):
    return Dream.objects.create(
        user=tb_user,
        title="TimeBlock Dream",
        description="Dream for time block tests",
        category="career",
        status="active",
    )


# ───────────────────────────────────────────────────────────────────
# Model creation with new fields
# ───────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestTimeBlockCreation:
    """Test TimeBlock model creation with title, color, dream FK."""

    def test_create_with_title(self, tb_user):
        block = TimeBlock.objects.create(
            user=tb_user,
            title="Morning Routine",
            block_type="personal",
            day_of_week=0,
            start_time=time(6, 0),
            end_time=time(8, 0),
        )
        assert block.title == "Morning Routine"

    def test_create_with_color(self, tb_user):
        block = TimeBlock.objects.create(
            user=tb_user,
            color="#FF5733",
            block_type="work",
            day_of_week=1,
            start_time=time(9, 0),
            end_time=time(17, 0),
        )
        assert block.color == "#FF5733"

    def test_create_with_dream_fk(self, tb_user, tb_dream):
        block = TimeBlock.objects.create(
            user=tb_user,
            dream=tb_dream,
            block_type="personal",
            day_of_week=2,
            start_time=time(10, 0),
            end_time=time(12, 0),
        )
        assert block.dream == tb_dream
        assert block.dream_id == tb_dream.id

    def test_create_with_all_new_fields(self, tb_user, tb_dream):
        block = TimeBlock.objects.create(
            user=tb_user,
            title="Study Session",
            color="#3498DB",
            dream=tb_dream,
            block_type="personal",
            day_of_week=3,
            start_time=time(14, 0),
            end_time=time(16, 0),
        )
        assert block.title == "Study Session"
        assert block.color == "#3498DB"
        assert block.dream == tb_dream

    def test_dream_fk_nullable(self, tb_user):
        """Dream FK is optional (null=True, blank=True)."""
        block = TimeBlock.objects.create(
            user=tb_user,
            block_type="work",
            day_of_week=4,
            start_time=time(9, 0),
            end_time=time(17, 0),
        )
        assert block.dream is None

    def test_title_default_empty(self, tb_user):
        """Title defaults to empty string."""
        block = TimeBlock.objects.create(
            user=tb_user,
            block_type="work",
            day_of_week=5,
            start_time=time(9, 0),
            end_time=time(17, 0),
        )
        assert block.title == ""

    def test_color_default(self, tb_user):
        """Color defaults to #8B5CF6."""
        block = TimeBlock.objects.create(
            user=tb_user,
            block_type="work",
            day_of_week=6,
            start_time=time(9, 0),
            end_time=time(17, 0),
        )
        assert block.color == "#8B5CF6"

    def test_dream_set_null_on_delete(self, tb_user, tb_dream):
        """When dream is deleted, TimeBlock.dream becomes NULL."""
        block = TimeBlock.objects.create(
            user=tb_user,
            dream=tb_dream,
            block_type="personal",
            day_of_week=0,
            start_time=time(10, 0),
            end_time=time(12, 0),
        )
        tb_dream.delete()
        block.refresh_from_db()
        assert block.dream is None


# ───────────────────────────────────────────────────────────────────
# block_type default
# ───────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestTimeBlockDefaultBlockType:
    """Test that block_type defaults to 'personal'."""

    def test_default_block_type(self, tb_user):
        block = TimeBlock.objects.create(
            user=tb_user,
            day_of_week=0,
            start_time=time(8, 0),
            end_time=time(9, 0),
        )
        assert block.block_type == "personal"


# ───────────────────────────────────────────────────────────────────
# Serializer includes new fields
# ───────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestTimeBlockSerializerNewFields:
    """Test that TimeBlockSerializer includes title, color, dream_id."""

    def test_serializer_includes_title(self, tb_user):
        block = TimeBlock.objects.create(
            user=tb_user,
            title="Deep Work",
            block_type="work",
            day_of_week=0,
            start_time=time(9, 0),
            end_time=time(12, 0),
        )
        data = TimeBlockSerializer(block).data
        assert "title" in data
        assert data["title"] == "Deep Work"

    def test_serializer_includes_color(self, tb_user):
        block = TimeBlock.objects.create(
            user=tb_user,
            color="#E74C3C",
            block_type="work",
            day_of_week=1,
            start_time=time(9, 0),
            end_time=time(12, 0),
        )
        data = TimeBlockSerializer(block).data
        assert "color" in data
        assert data["color"] == "#E74C3C"

    def test_serializer_includes_dream_id(self, tb_user, tb_dream):
        block = TimeBlock.objects.create(
            user=tb_user,
            dream=tb_dream,
            block_type="personal",
            day_of_week=2,
            start_time=time(10, 0),
            end_time=time(12, 0),
        )
        data = TimeBlockSerializer(block).data
        assert "dream_id" in data
        assert str(data["dream_id"]) == str(tb_dream.id)

    def test_serializer_dream_id_null_when_no_dream(self, tb_user):
        block = TimeBlock.objects.create(
            user=tb_user,
            block_type="work",
            day_of_week=3,
            start_time=time(9, 0),
            end_time=time(17, 0),
        )
        data = TimeBlockSerializer(block).data
        assert "dream_id" in data
        assert data["dream_id"] is None

    def test_serializer_all_fields_present(self, tb_user):
        """Verify all expected fields are in the serialized output."""
        block = TimeBlock.objects.create(
            user=tb_user,
            title="Test Block",
            color="#2ECC71",
            block_type="personal",
            day_of_week=4,
            start_time=time(10, 0),
            end_time=time(11, 0),
        )
        data = TimeBlockSerializer(block).data
        expected_fields = {
            "id",
            "user",
            "title",
            "block_type",
            "day_of_week",
            "day_name",
            "start_time",
            "end_time",
            "color",
            "dream_id",
            "is_active",
            "focus_block",
            "created_at",
            "updated_at",
        }
        assert expected_fields.issubset(set(data.keys()))
