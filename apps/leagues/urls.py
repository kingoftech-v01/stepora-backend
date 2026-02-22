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
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import LeagueViewSet, LeaderboardViewSet, SeasonViewSet

router = DefaultRouter()
router.register(r'leagues', LeagueViewSet, basename='league')
router.register(r'leaderboard', LeaderboardViewSet, basename='leaderboard')
router.register(r'seasons', SeasonViewSet, basename='season')

urlpatterns = [
    path('', include(router.urls)),
]
