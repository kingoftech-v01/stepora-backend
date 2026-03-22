"""
Regression tests for TaskSerializer XP computed field.

The XP formula is: max(10, duration_mins / 3)
- No duration (None) -> defaults to 30 -> 30 // 3 = 10 -> max(10, 10) = 10
- 0 min task -> 0 // 3 = 0 -> max(10, 0) = 10
- 30 min task -> 30 // 3 = 10 -> max(10, 10) = 10
- 60 min task -> 60 // 3 = 20 -> max(10, 20) = 20
- 90 min task -> 90 // 3 = 30 -> max(10, 30) = 30
"""

import pytest

from apps.plans.models import Task
from apps.plans.serializers import TaskSerializer


@pytest.mark.django_db
class TestTaskSerializerXP:
    """Tests for the get_xp method on TaskSerializer."""

    def test_xp_with_no_duration_returns_10(self, plans_goal):
        """Task without duration uses default 30 -> 30 // 3 = 10."""
        task = Task.objects.create(
            goal=plans_goal,
            title="No Duration Task",
            order=1,
            duration_mins=None,
        )
        data = TaskSerializer(task).data
        assert data["xp"] == 10

    def test_xp_with_zero_duration_returns_10(self, plans_goal):
        """Task with 0 mins -> max(10, 0) = 10 (minimum floor)."""
        task = Task.objects.create(
            goal=plans_goal,
            title="Zero Duration Task",
            order=1,
            duration_mins=0,
        )
        data = TaskSerializer(task).data
        assert data["xp"] == 10

    def test_xp_with_30min_duration_returns_10(self, plans_goal):
        """30 min task -> 30 // 3 = 10 -> max(10, 10) = 10."""
        task = Task.objects.create(
            goal=plans_goal,
            title="30 Min Task",
            order=1,
            duration_mins=30,
        )
        data = TaskSerializer(task).data
        assert data["xp"] == 10

    def test_xp_with_60min_duration_returns_20(self, plans_goal):
        """60 min task -> 60 // 3 = 20 -> max(10, 20) = 20."""
        task = Task.objects.create(
            goal=plans_goal,
            title="60 Min Task",
            order=1,
            duration_mins=60,
        )
        data = TaskSerializer(task).data
        assert data["xp"] == 20

    def test_xp_with_90min_duration_returns_30(self, plans_goal):
        """90 min task -> 90 // 3 = 30 -> max(10, 30) = 30."""
        task = Task.objects.create(
            goal=plans_goal,
            title="90 Min Task",
            order=1,
            duration_mins=90,
        )
        data = TaskSerializer(task).data
        assert data["xp"] == 30

    def test_xp_with_15min_duration_returns_10(self, plans_goal):
        """15 min task -> 15 // 3 = 5 -> max(10, 5) = 10 (floor applies)."""
        task = Task.objects.create(
            goal=plans_goal,
            title="15 Min Task",
            order=1,
            duration_mins=15,
        )
        data = TaskSerializer(task).data
        assert data["xp"] == 10

    def test_xp_with_120min_duration_returns_40(self, plans_goal):
        """120 min task -> 120 // 3 = 40 -> max(10, 40) = 40."""
        task = Task.objects.create(
            goal=plans_goal,
            title="120 Min Task",
            order=1,
            duration_mins=120,
        )
        data = TaskSerializer(task).data
        assert data["xp"] == 40

    def test_xp_field_is_read_only(self, plans_task):
        """XP field should be read-only (computed, not writable)."""
        serializer = TaskSerializer(plans_task, data={"xp": 999}, partial=True)
        assert serializer.is_valid()
        assert "xp" not in serializer.validated_data

    def test_xp_field_present_in_serialized_data(self, plans_task):
        """XP field should always be present in serialized output."""
        data = TaskSerializer(plans_task).data
        assert "xp" in data
        assert isinstance(data["xp"], int)
