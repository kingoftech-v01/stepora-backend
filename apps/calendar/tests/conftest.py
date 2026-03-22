"""
Fixtures for calendar tests.
"""

from datetime import time, timedelta

import pytest
from django.utils import timezone

from apps.calendar.models import CalendarEvent, TimeBlock
from apps.users.models import User


@pytest.fixture
def cal_user(db):
    """Create a user for calendar tests."""
    return User.objects.create_user(
        email="caluser@example.com",
        password="testpass123",
        display_name="Calendar User",
        timezone="Europe/Paris",
    )


@pytest.fixture
def cal_event(db, cal_user):
    """Create a test calendar event."""
    return CalendarEvent.objects.create(
        user=cal_user,
        title="Test Meeting",
        description="A test meeting",
        start_time=timezone.now() + timedelta(hours=1),
        end_time=timezone.now() + timedelta(hours=2),
        category="meeting",
        status="scheduled",
    )


@pytest.fixture
def all_day_event(db, cal_user):
    """Create an all-day calendar event."""
    return CalendarEvent.objects.create(
        user=cal_user,
        title="All Day Event",
        start_time=timezone.now().replace(hour=0, minute=0, second=0),
        end_time=timezone.now().replace(hour=23, minute=59, second=59),
        all_day=True,
        category="custom",
    )


@pytest.fixture
def time_block(db, cal_user):
    """Create a test time block."""
    return TimeBlock.objects.create(
        user=cal_user,
        block_type="work",
        day_of_week=0,
        start_time=time(9, 0),
        end_time=time(17, 0),
        is_active=True,
    )


@pytest.fixture
def focus_time_block(db, cal_user):
    """Create a focus time block."""
    return TimeBlock.objects.create(
        user=cal_user,
        block_type="personal",
        day_of_week=1,
        start_time=time(6, 0),
        end_time=time(8, 0),
        is_active=True,
        focus_block=True,
    )
