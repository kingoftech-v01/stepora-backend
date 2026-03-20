"""
URLs for the Gamification system.

Routes:
    /profile/                - Get gamification profile
    /achievements/           - List all achievements with status
    /heatmap/                - Activity heatmap data
    /daily-stats/            - Today's stats
    /streak-details/         - Streak details
    /streak-freeze/          - Use a streak freeze
    /leaderboard/            - Leaderboard stats
"""

from django.urls import path

from .views import (
    AchievementsView,
    ActivityHeatmapView,
    DailyStatsView,
    GamificationProfileView,
    LeaderboardStatsView,
    StreakDetailsView,
    StreakFreezeView,
)

urlpatterns = [
    path("profile/", GamificationProfileView.as_view(), name="gamification-profile"),
    path("achievements/", AchievementsView.as_view(), name="gamification-achievements"),
    path("heatmap/", ActivityHeatmapView.as_view(), name="gamification-heatmap"),
    path("daily-stats/", DailyStatsView.as_view(), name="gamification-daily-stats"),
    path("streak-details/", StreakDetailsView.as_view(), name="gamification-streak-details"),
    path("streak-freeze/", StreakFreezeView.as_view(), name="gamification-streak-freeze"),
    path("leaderboard/", LeaderboardStatsView.as_view(), name="gamification-leaderboard"),
]
