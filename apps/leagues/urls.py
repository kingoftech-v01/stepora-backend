"""
URL configuration for the Leagues & Ranking system.

Routes:
    /leagues/           - List all leagues
    /leagues/<id>/      - League detail
    /seasons/           - List all seasons
    /seasons/<id>/      - Season detail
    /seasons/current/   - Current active season
    /seasons/past/      - Past seasons
    /seasons/my-rewards/ - User's season rewards
    /seasons/<id>/claim-reward/ - Claim season reward
    /leaderboard/global/  - Global leaderboard (top 100)
    /leaderboard/league/  - League-specific leaderboard
    /leaderboard/friends/ - Friends leaderboard
    /leaderboard/me/      - Current user's standing
    /leaderboard/nearby/  - Users ranked near the current user
    /leaderboard/group/   - Group leaderboard
    /groups/              - List league groups (active season)
    /groups/<id>/         - Group detail
    /groups/mine/         - Current user's group
    /groups/<id>/leaderboard/ - Group leaderboard (detail)
    /league-seasons/            - List all league seasons
    /league-seasons/<id>/       - League season detail
    /league-seasons/current/    - Current active league season
    /league-seasons/current/join/ - Join current league season
    /league-seasons/<id>/leaderboard/ - Season leaderboard
    /league-seasons/<id>/claim-rewards/ - Claim end-of-season rewards
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    LeaderboardViewSet,
    LeagueGroupViewSet,
    LeagueSeasonViewSet,
    LeagueViewSet,
    SeasonViewSet,
)

router = DefaultRouter()
router.register(r"leagues", LeagueViewSet, basename="league")
router.register(r"leaderboard", LeaderboardViewSet, basename="leaderboard")
router.register(r"seasons", SeasonViewSet, basename="season")
router.register(r"groups", LeagueGroupViewSet, basename="league-group")
router.register(r"league-seasons", LeagueSeasonViewSet, basename="league-season")

urlpatterns = [
    path("", include(router.urls)),
]
