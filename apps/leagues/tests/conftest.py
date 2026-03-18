"""
Fixtures for leagues tests.
"""

from datetime import timedelta

import pytest
from django.utils import timezone

from apps.leagues.models import League, Season, LeagueStanding
from apps.users.models import User


@pytest.fixture
def league_user(db):
    """Create a user for league tests."""
    return User.objects.create_user(
        email="leagueuser@example.com",
        password="testpass123",
        display_name="League User",
    )


@pytest.fixture
def league_user2(db):
    """Create a second user for league tests."""
    return User.objects.create_user(
        email="leagueuser2@example.com",
        password="testpass123",
        display_name="League User 2",
    )


@pytest.fixture
def bronze_league(db):
    """Create or get the bronze league."""
    league, _ = League.objects.get_or_create(
        tier="bronze",
        defaults={
            "name": "Bronze League",
            "min_xp": 0,
            "max_xp": 499,
            "color_hex": "#CD7F32",
            "description": "Every dreamer starts here.",
        },
    )
    return league


@pytest.fixture
def silver_league(db):
    """Create or get the silver league."""
    league, _ = League.objects.get_or_create(
        tier="silver",
        defaults={
            "name": "Silver League",
            "min_xp": 500,
            "max_xp": 1499,
            "color_hex": "#C0C0C0",
            "description": "Building momentum.",
        },
    )
    return league


@pytest.fixture
def legend_league(db):
    """Create or get the legend league (no max_xp)."""
    league, _ = League.objects.get_or_create(
        tier="legend",
        defaults={
            "name": "Legend League",
            "min_xp": 20000,
            "max_xp": None,
            "color_hex": "#FF4500",
            "description": "Living legend.",
        },
    )
    return league


@pytest.fixture
def test_season(db):
    """Create a test season."""
    return Season.objects.create(
        name="Test Season 1",
        start_date=timezone.now() - timedelta(days=30),
        end_date=timezone.now() + timedelta(days=150),
        is_active=True,
        status="active",
    )


@pytest.fixture
def ended_season(db):
    """Create a season that has ended."""
    return Season.objects.create(
        name="Past Season",
        start_date=timezone.now() - timedelta(days=200),
        end_date=timezone.now() - timedelta(days=10),
        is_active=False,
        status="ended",
    )


@pytest.fixture
def league_standing(db, league_user, bronze_league, test_season):
    """Create a league standing for a user."""
    return LeagueStanding.objects.create(
        user=league_user,
        league=bronze_league,
        season=test_season,
        rank=1,
        xp_earned_this_season=100,
        tasks_completed=5,
    )
