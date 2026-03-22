# Gamification App

Life RPG system for Stepora: per-category XP, achievements, streaks, daily activity heatmaps, and leaderboards.

## Models

| Model | Purpose |
|---|---|
| `GamificationProfile` | One-to-one with User. Stores per-category XP (health, career, relationships, personal growth, finance, hobbies), badges JSON, streak jokers (freeze tokens). Auto-created via `post_save` signal on User. |
| `Achievement` | Achievement definitions. Fields: name, description, icon (Lucide name), category, rarity (common/uncommon/rare/epic/legendary), xp_reward, condition_type + condition_value, is_active. |
| `UserAchievement` | Join table tracking which achievements a user has unlocked. Unique constraint on (user, achievement). Stores progress value. |
| `DailyActivity` | Per-user per-date activity record. Tracks tasks_completed, xp_earned, minutes_active. Unique constraint on (user, date). Used for heatmap display. |
| `HabitChain` | Individual habit events: check_in, task_completion, focus_timer. Linked to optional Dream. Used by StreakService for streak calculation. |

## Services

### AchievementService
- `check_achievements(user)` -- Checks all active achievement conditions against user stats. Unlocks newly met achievements, awards XP, sends notification. Idempotent (skips already-unlocked).

### StreakService
- `record_activity(user, chain_type, dream=None)` -- Records a HabitChain event and updates the user's streak. Idempotent per day. Increments streak on consecutive days, resets on gap.
- `use_streak_freeze(user)` -- Premium feature. Consumes a streak joker to protect streak. Max 1 per week.
- `get_streak_summary(user)` -- Returns current/longest streak, XP multiplier, next milestone.
- `get_calendar_heatmap(user, days=365)` -- Returns date/count/level data for heatmap rendering.
- `reset_broken_streaks()` -- Called daily by Celery. Resets broken streaks, sends at-risk notifications.
- `get_xp_multiplier(streak_days)` -- Returns 1.0/1.5/2.0/3.0 based on streak length.

### XPService
- `award_xp(user, amount, category=None)` -- Awards XP to user (and optionally to a category on GamificationProfile).
- `get_level_info(user)` -- Returns level, xp, xp_to_next_level, progress_percentage.

## API Endpoints

All under `/api/v1/gamification/`. Require authentication.

| Method | Path | View | Description |
|---|---|---|---|
| GET | `profile/` | GamificationProfileView | Gamification profile with per-category XP, levels, skill radar |
| GET | `achievements/` | AchievementsView | All achievements with unlock status and progress |
| GET | `heatmap/` | ActivityHeatmapView | Daily activity heatmap (default 28 days, `?days=N`) |
| GET | `daily-stats/` | DailyStatsView | Today's stats: tasks, xp, minutes, level, streak |
| GET | `streak-details/` | StreakDetailsView | Streak details: current, longest, 14-day history, freeze status |
| POST | `streak-freeze/` | StreakFreezeView | Use a streak joker (decrements streak_jokers) |
| GET | `leaderboard/` | LeaderboardStatsView | User's XP rank, streak rank, total users |

**Note:** The UserViewSet in `apps/users/views.py` also exposes `gamification`, `achievements`, and `streak-details` endpoints under `/api/v1/users/` (and `/api/users/`). The frontend uses the `/api/users/` paths.

## Celery Tasks

| Task | Schedule | Description |
|---|---|---|
| `check_broken_streaks` | Daily midnight UTC | Resets broken streaks, sends at-risk notifications |
| `refresh_leaderboard_cache` | Periodic | Placeholder for future leaderboard cache refresh |

## XP & Level System

- **100 XP per level** (level = xp // 100 + 1)
- **Streak multiplier**: 7+ days = 1.5x, 30+ = 2.0x, 100+ = 3.0x
- **Category XP**: 6 life categories, each tracked independently on GamificationProfile
- **Achievement XP**: Awarded on unlock, varies by achievement

## Streak System

- **Streak increment**: Recorded via `StreakService.record_activity()` on task completion, check-in, or focus timer
- **Break detection**: Daily Celery task checks `streak_updated_at` field on User
- **Freeze**: Premium users get 3 jokers (streak_jokers). Max 1 use per week.
- **Milestones**: 7, 14, 30, 60, 90, 180, 365 days -- trigger notifications

## Frontend Components

| Component | File | Description |
|---|---|---|
| AchievementsScreen | `src/pages/profile/AchievementsScreen/` | Full achievements list (Mobile/Desktop/Tablet variants) with unlock status, XP totals, streak counter |
| AchievementShowcase | `src/components/shared/AchievementShowcase.jsx` | Badge grid with rarity glows, progress rings, tap-to-expand popover. Used on Profile screen. |
| AchievementShareModal | `src/components/shared/AchievementShareModal.jsx` | Celebration popup after completing a goal/milestone/dream. Lets user share with media to social feed. |
| StreakWidget | `src/components/shared/StreakWidget.jsx` | Animated streak counter for home dashboard. Flame icon scales with streak length, 14-day dot heatmap, freeze indicator. |

## Frontend Endpoints Used

Defined in `src/services/endpoints.js`:
- `USERS.GAMIFICATION` = `/api/users/gamification/`
- `USERS.ACHIEVEMENTS` = `/api/users/achievements/`
- `USERS.STREAK_DETAILS` = `/api/users/streak-details/`

## Tests

### Backend (144 tests)
- `apps/gamification/tests/test_gamification_complete.py` -- 119 comprehensive tests
- `apps/gamification/tests/test_models.py` -- Model unit tests
- `apps/gamification/tests/test_views.py` -- API endpoint tests
- `apps/gamification/tests/test_services.py` -- Service layer tests

Coverage: models 100%, serializers 100%, signals 100%, tasks 100%, views 96%, services 92%, admin 93%.

### Frontend (26 tests)
- `src/components/shared/StreakWidget.test.jsx` -- 9 tests
- `src/components/shared/AchievementShowcase.test.jsx` -- 11 tests
- `src/pages/profile/AchievementsScreen/useAchievementsScreen.test.jsx` -- 6 tests

## Bug Fix Applied

**HabitChainSerializer** referenced non-existent fields (`name`, `description`, `frequency`, `current_streak`, `longest_streak`, `last_completed_at`, `is_active`, `updated_at`). Fixed to use actual model fields (`id`, `date`, `chain_type`, `completed`, `created_at`).
