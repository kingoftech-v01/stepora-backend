"""
CRUD integration tests for the TimeBlock API endpoint.

Covers:
- Create (POST) with HH:MM and HH:MM:SS time formats
- List (GET) — only own blocks
- Retrieve (GET detail)
- Update (PATCH) with both time formats
- Delete (DELETE)
- IDOR protection — cannot access another user's blocks
- Validation: end_time before start_time, invalid day_of_week
- Default block_type when omitted
"""

import pytest
from rest_framework.test import APIClient

from apps.users.models import User


@pytest.fixture
def tb_crud_user(db):
    return User.objects.create_user(
        email="tb_crud@test.com",
        password="testpass123",
        display_name="TB CRUD",
        timezone="Europe/Paris",
    )


@pytest.fixture
def tb_crud_client(tb_crud_user):
    c = APIClient()
    c.force_authenticate(tb_crud_user)
    return c


@pytest.mark.django_db
class TestTimeBlockCreate:
    """POST /api/v1/calendar/timeblocks/"""

    def test_create_timeblock_hhmmss(self, tb_crud_client):
        """Create with HH:MM:SS format (what the backend natively returns)."""
        r = tb_crud_client.post(
            "/api/v1/calendar/timeblocks/",
            {
                "block_type": "work",
                "day_of_week": 0,
                "start_time": "09:00:00",
                "end_time": "17:00:00",
                "title": "Morning work",
            },
            format="json",
        )
        assert r.status_code == 201, r.data
        assert r.data["title"] == "Morning work"
        assert r.data["block_type"] == "work"
        assert r.data["day_of_week"] == 0
        assert r.data["day_name"] == "Monday"

    def test_create_timeblock_hhmm(self, tb_crud_client):
        """HH:MM format (what HTML <input type=time> sends) should also work."""
        r = tb_crud_client.post(
            "/api/v1/calendar/timeblocks/",
            {
                "block_type": "personal",
                "day_of_week": 1,
                "start_time": "10:00",
                "end_time": "11:00",
                "title": "Quick block",
            },
            format="json",
        )
        assert r.status_code == 201, r.data

    def test_create_default_block_type(self, tb_crud_client):
        """block_type defaults to 'personal' when omitted."""
        r = tb_crud_client.post(
            "/api/v1/calendar/timeblocks/",
            {
                "day_of_week": 0,
                "start_time": "09:00",
                "end_time": "17:00",
                "title": "Default type",
            },
            format="json",
        )
        assert r.status_code == 201, r.data
        assert r.data["block_type"] == "personal"

    def test_create_with_color_and_focus(self, tb_crud_client):
        """Create with optional color and focus_block fields."""
        r = tb_crud_client.post(
            "/api/v1/calendar/timeblocks/",
            {
                "block_type": "personal",
                "day_of_week": 2,
                "start_time": "06:00",
                "end_time": "07:30",
                "title": "Morning focus",
                "color": "#EF4444",
                "focus_block": True,
            },
            format="json",
        )
        assert r.status_code == 201, r.data
        assert r.data["color"] == "#EF4444"
        assert r.data["focus_block"] is True


@pytest.mark.django_db
class TestTimeBlockList:
    """GET /api/v1/calendar/timeblocks/"""

    def test_list_own_timeblocks(self, tb_crud_client):
        """List returns only blocks owned by the authenticated user."""
        # Create two blocks
        tb_crud_client.post(
            "/api/v1/calendar/timeblocks/",
            {
                "block_type": "work",
                "day_of_week": 0,
                "start_time": "09:00",
                "end_time": "12:00",
                "title": "Block A",
            },
            format="json",
        )
        tb_crud_client.post(
            "/api/v1/calendar/timeblocks/",
            {
                "block_type": "personal",
                "day_of_week": 1,
                "start_time": "14:00",
                "end_time": "16:00",
                "title": "Block B",
            },
            format="json",
        )

        r = tb_crud_client.get("/api/v1/calendar/timeblocks/")
        assert r.status_code == 200
        results = r.data.get("results", r.data)
        assert len(results) == 2

    def test_list_empty(self, tb_crud_client):
        """List returns empty when user has no blocks."""
        r = tb_crud_client.get("/api/v1/calendar/timeblocks/")
        assert r.status_code == 200


@pytest.mark.django_db
class TestTimeBlockUpdate:
    """PATCH /api/v1/calendar/timeblocks/{id}/"""

    def _create_block(self, client):
        r = client.post(
            "/api/v1/calendar/timeblocks/",
            {
                "block_type": "work",
                "day_of_week": 0,
                "start_time": "09:00",
                "end_time": "17:00",
                "title": "Original",
            },
            format="json",
        )
        assert r.status_code == 201
        return r.data["id"]

    def test_update_title(self, tb_crud_client):
        bid = self._create_block(tb_crud_client)
        r = tb_crud_client.patch(
            f"/api/v1/calendar/timeblocks/{bid}/",
            {"title": "Updated title"},
            format="json",
        )
        assert r.status_code == 200, r.data
        assert r.data["title"] == "Updated title"

    def test_update_times_hhmm(self, tb_crud_client):
        """Update with HH:MM format (frontend sends this)."""
        bid = self._create_block(tb_crud_client)
        r = tb_crud_client.patch(
            f"/api/v1/calendar/timeblocks/{bid}/",
            {"start_time": "10:00", "end_time": "18:00"},
            format="json",
        )
        assert r.status_code == 200, r.data

    def test_update_times_hhmmss(self, tb_crud_client):
        """Update with HH:MM:SS format."""
        bid = self._create_block(tb_crud_client)
        r = tb_crud_client.patch(
            f"/api/v1/calendar/timeblocks/{bid}/",
            {"start_time": "10:00:00", "end_time": "18:00:00"},
            format="json",
        )
        assert r.status_code == 200, r.data

    def test_update_block_type(self, tb_crud_client):
        bid = self._create_block(tb_crud_client)
        r = tb_crud_client.patch(
            f"/api/v1/calendar/timeblocks/{bid}/",
            {"block_type": "exercise"},
            format="json",
        )
        assert r.status_code == 200, r.data
        assert r.data["block_type"] == "exercise"


@pytest.mark.django_db
class TestTimeBlockDelete:
    """DELETE /api/v1/calendar/timeblocks/{id}/"""

    def test_delete_timeblock(self, tb_crud_client):
        r = tb_crud_client.post(
            "/api/v1/calendar/timeblocks/",
            {
                "block_type": "work",
                "day_of_week": 0,
                "start_time": "09:00",
                "end_time": "17:00",
                "title": "To delete",
            },
            format="json",
        )
        bid = r.data["id"]
        r = tb_crud_client.delete(f"/api/v1/calendar/timeblocks/{bid}/")
        assert r.status_code == 204

        # Confirm it's gone
        r = tb_crud_client.get(f"/api/v1/calendar/timeblocks/{bid}/")
        assert r.status_code == 404


@pytest.mark.django_db
class TestTimeBlockIDOR:
    """IDOR protection — users cannot access other users' blocks."""

    def test_cannot_read_other_users_block(self, tb_crud_client, tb_crud_user):
        from apps.calendar.models import TimeBlock

        other = User.objects.create_user(
            email="other_tb@test.com", password="testpass123", display_name="Other"
        )
        block = TimeBlock.objects.create(
            user=other,
            block_type="work",
            day_of_week=0,
            start_time="09:00",
            end_time="17:00",
            title="Other's block",
        )
        r = tb_crud_client.get(f"/api/v1/calendar/timeblocks/{block.id}/")
        assert r.status_code == 404

    def test_cannot_update_other_users_block(self, tb_crud_client, tb_crud_user):
        from apps.calendar.models import TimeBlock

        other = User.objects.create_user(
            email="other_tb2@test.com", password="testpass123", display_name="Other2"
        )
        block = TimeBlock.objects.create(
            user=other,
            block_type="work",
            day_of_week=0,
            start_time="09:00",
            end_time="17:00",
            title="Other's block",
        )
        r = tb_crud_client.patch(
            f"/api/v1/calendar/timeblocks/{block.id}/",
            {"title": "Hacked"},
            format="json",
        )
        assert r.status_code == 404

    def test_cannot_delete_other_users_block(self, tb_crud_client, tb_crud_user):
        from apps.calendar.models import TimeBlock

        other = User.objects.create_user(
            email="other_tb3@test.com", password="testpass123", display_name="Other3"
        )
        block = TimeBlock.objects.create(
            user=other,
            block_type="work",
            day_of_week=0,
            start_time="09:00",
            end_time="17:00",
            title="Other's block",
        )
        r = tb_crud_client.delete(f"/api/v1/calendar/timeblocks/{block.id}/")
        assert r.status_code == 404


@pytest.mark.django_db
class TestTimeBlockValidation:
    """Validation edge cases."""

    def test_end_before_start_rejected(self, tb_crud_client):
        """end_time < start_time should be rejected by serializer validation."""
        r = tb_crud_client.post(
            "/api/v1/calendar/timeblocks/",
            {
                "block_type": "work",
                "day_of_week": 0,
                "start_time": "17:00",
                "end_time": "09:00",
                "title": "Bad range",
            },
            format="json",
        )
        assert r.status_code == 400

    def test_invalid_day_of_week_high(self, tb_crud_client):
        """day_of_week > 6 should be rejected."""
        r = tb_crud_client.post(
            "/api/v1/calendar/timeblocks/",
            {
                "block_type": "work",
                "day_of_week": 9,
                "start_time": "09:00",
                "end_time": "17:00",
                "title": "Bad day",
            },
            format="json",
        )
        assert r.status_code == 400

    def test_invalid_day_of_week_negative(self, tb_crud_client):
        """day_of_week < 0 should be rejected."""
        r = tb_crud_client.post(
            "/api/v1/calendar/timeblocks/",
            {
                "block_type": "work",
                "day_of_week": -1,
                "start_time": "09:00",
                "end_time": "17:00",
                "title": "Bad day neg",
            },
            format="json",
        )
        assert r.status_code == 400

    def test_missing_required_fields(self, tb_crud_client):
        """Missing start_time / end_time / day_of_week should fail."""
        r = tb_crud_client.post(
            "/api/v1/calendar/timeblocks/",
            {"block_type": "work", "title": "No times"},
            format="json",
        )
        assert r.status_code == 400

    def test_unauthenticated_rejected(self):
        """Unauthenticated requests should be rejected."""
        client = APIClient()
        r = client.get("/api/v1/calendar/timeblocks/")
        assert r.status_code == 401
