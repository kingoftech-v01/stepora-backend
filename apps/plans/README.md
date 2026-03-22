# Plans App

The `plans` app manages the structured plan hierarchy for dreams: milestones, goals, tasks, obstacles, check-ins, focus sessions, and progress tracking.

## Data Model Hierarchy

```
Dream (apps.dreams)
  |-- DreamMilestone       Time-based milestone (e.g. "Month 1")
  |     |-- Goal           Actionable goal within a milestone
  |     |     |-- Task     Individual task within a goal
  |     |-- Obstacle       Predicted/actual obstacle (optional link to goal)
  |-- CalibrationResponse  AI calibration Q&A for plan generation
  |-- PlanCheckIn          Periodic AI check-in session
  |-- DreamProgressSnapshot  Daily progress snapshot (sparkline charts)

FocusSession               Pomodoro session linked to a user + optional task
```

## Models

| Model | Table | Key Fields |
|-------|-------|------------|
| `DreamMilestone` | `milestones` | dream, title, order, status, target_date, expected_date, deadline_date, progress_percentage |
| `Goal` | `goals` | dream, milestone (nullable), title, order, status, scheduled_start/end, expected_date, deadline_date, progress_percentage |
| `Task` | `tasks` | goal, title, order, status, scheduled_date, duration_mins, recurrence (JSON), chain_* fields, is_two_minute_start |
| `Obstacle` | `obstacles` | dream, milestone (opt), goal (opt), title, description, obstacle_type, solution, status |
| `CalibrationResponse` | `calibration_responses` | dream, question, answer, question_number, category |
| `PlanCheckIn` | `plan_checkins` | dream, status, triggered_by, questionnaire (JSON), user_responses (JSON), pace_status, coaching_message, ai_actions (JSON) |
| `DreamProgressSnapshot` | `dream_progress_snapshots` | dream, date, progress_percentage (unique together) |
| `FocusSession` | `focus_sessions` | user, task (opt), duration_minutes, actual_minutes, session_type, completed |

## Progress Propagation

Task completion cascades upward:

1. `Task.complete()` -> awards XP, updates streak, records daily activity
2. `Goal.update_progress()` -> recalculates from completed tasks ratio
3. `Milestone.update_progress()` -> recalculates from completed goals ratio
4. `Dream.update_progress()` -> recalculates from milestone/goal ratio

## Task Chains

Tasks support recurring chains via `chain_next_delay_days`:
- When a chain task is completed, `_create_chain_next()` auto-creates the next task
- New task is scheduled `chain_next_delay_days` days after completion
- Uses `chain_template_title` if set, otherwise current title
- Chain ancestry tracked via `chain_parent` FK + `is_chain` flag
- `get_chain_position()` returns `(position, total)` for display

## XP Formula

```
xp_amount = max(10, (duration_mins or 30) // 3)
```

| Duration | XP |
|----------|-----|
| None/0 | 10 |
| 30 min | 10 |
| 60 min | 20 |
| 90 min | 30 |
| 120 min | 40 |

Milestone completion: +200 XP. Goal completion: +100 XP.

## API Endpoints

All under `/api/v1/plans/` (and `/api/plans/` backward-compat):

### CRUD ViewSets

| Endpoint | ViewSet | Methods |
|----------|---------|---------|
| `/milestones/` | `DreamMilestoneViewSet` | GET, POST, PATCH, PUT, DELETE |
| `/goals/` | `GoalViewSet` | GET, POST, PATCH, PUT, DELETE |
| `/tasks/` | `TaskViewSet` | GET, POST, PATCH, PUT, DELETE |
| `/obstacles/` | `ObstacleViewSet` | GET, POST, PATCH, PUT, DELETE |
| `/checkins/` | `CheckInViewSet` | GET (read-only) |

### Actions

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/goals/{id}/complete/` | POST | Mark goal completed |
| `/tasks/{id}/complete/` | POST | Mark task completed |
| `/checkins/{id}/respond/` | POST | Submit questionnaire responses |
| `/checkins/{id}/status_poll/` | GET | Poll check-in processing status |

### Focus Sessions

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/focus/start/` | POST | Start focus session (`duration_minutes`, `session_type`, `task_id`) |
| `/focus/complete/` | POST | Complete session (`session_id`, `actual_minutes`) |
| `/focus/history/` | GET | Recent sessions (limit 20) |
| `/focus/stats/` | GET | Weekly stats (total_sessions, total_minutes, average_minutes) |

### Query Parameters

- `?dream=<uuid>` - Filter milestones, goals, obstacles, check-ins by dream
- `?milestone=<uuid>` - Filter goals by milestone
- `?goal=<uuid>` - Filter tasks by goal
- `?status=<status>` - Filter check-ins by status

## IDOR Protection

All ViewSets filter by `dream__user=request.user` in `get_queryset()`.
All `perform_create()` methods verify `dream.user == request.user`.

## Services

`PlanService` provides:
- `process_checkin(checkin)` - Analyze progress, compute pace, adjust interval, generate coaching message
- `get_dream_plan_summary(dream)` - Count milestones/goals/tasks for a dream
- `_compute_pace(dream, overdue_count)` - Determine pace status (significantly_behind to significantly_ahead)
- `_generate_coaching_message(pace, completed, overdue)` - Human-readable coaching text

## Celery Tasks

- `process_checkin_responses(checkin_id)` - Async check-in processing after user submits responses
- `generate_plan_for_dream(dream_id, user_id)` - Delegates to `apps.dreams.tasks.generate_dream_plan_task`

## Frontend Integration

The frontend accesses plan data primarily through `/api/dreams/` endpoints (not `/api/plans/`).
The plans app endpoints serve as a secondary/admin API.

| Frontend Screen | Hook | Key API Calls |
|-----------------|------|---------------|
| DreamDetail | `useDreamDetailScreen` | Dream detail (includes milestones/goals/tasks), obstacles, check-ins, progress history |
| CheckInScreen | `useCheckInScreen` | Check-in detail, respond, status polling |
| FocusTimerScreen | `useFocusTimerScreen` | Focus start/complete/stats, pending tasks |

## Tests

```
apps/plans/tests/
  conftest.py                  - Shared fixtures
  test_models.py               - Model CRUD and basic methods
  test_views.py                - View endpoint smoke tests
  test_services.py             - PlanService unit tests
  test_task_xp.py              - TaskSerializer XP formula regression
  test_plans_complete.py       - Comprehensive test suite (173 tests)
```

Run tests:
```bash
DJANGO_SETTINGS_MODULE=config.settings.testing python -m pytest apps/plans/tests/ -v --no-cov
```
