# Leagues App

Django application implementing a competitive ranking system with 7-tier leagues, seasonal competitions, auto-grouping, leaderboards, promotion/relegation, and season rewards.

## Overview

The Leagues app provides a gamification layer with XP-based league tiers, seasonal standings, and leaderboard views. Users earn XP through task and dream completions and are ranked within their league tier. The system supports global, league-specific, group, and friends leaderboards. Privacy is enforced by design: leaderboards expose scores and badges but never user dreams.

The **auto-grouping system** distributes users into smaller competitive groups within each league tier, creating tighter leaderboards (typically 20 users) instead of one giant list per league. Groups are automatically created, merged, split, and rebalanced by Celery tasks.

### How It All Fits Together

1. **Leagues** define static tiers (Bronze through Legend) based on XP thresholds.
2. **Seasons** provide time-bounded competitive periods (default 6 months).
3. **Standings** track each user's rank and stats within a season.
4. **Groups** break each league tier into smaller competitive pods within a season.
5. **Promotion/Relegation** moves users between league tiers based on season XP thresholds.
6. **Rewards** are calculated at season end and must be claimed by users.

### League Tiers (by XP)

| Tier | XP Range | Color |
|------|----------|-------|
| Bronze | 0 - 499 XP | `#CD7F32` |
| Silver | 500 - 1,499 XP | `#C0C0C0` |
| Gold | 1,500 - 3,499 XP | `#FFD700` |
| Platinum | 3,500 - 6,999 XP | `#E5E4E2` |
| Diamond | 7,000 - 11,999 XP | `#B9F2FF` |
| Master | 12,000 - 19,999 XP | `#9B59B6` |
| Legend | 20,000+ XP | `#FF4500` |

---

## Admin Configuration Guide

All league system settings are managed from the Django admin panel. This section covers what to configure and in what order.

### Step 1: Create League Tiers

**Admin URL:** `/admin/leagues/league/`

Leagues define the competitive tiers users are sorted into based on their total XP. You can either seed the defaults or create them manually.

**Seeding defaults (recommended for first setup):**

```bash
python manage.py seed_leagues
```

This creates the 7 default tiers (Bronze through Legend) with XP ranges, colors, and descriptions. It is idempotent and safe to run multiple times.

**Manual creation:** Click "Add League" and fill in:

| Field | Description | Example |
|-------|-------------|---------|
| Name | Display name shown to users | "Gold League" |
| Tier | Tier key (unique, determines sort order) | `gold` |
| Min XP | Minimum XP to enter this league | 1500 |
| Max XP | Maximum XP (leave blank for the top league) | 3499 |
| Color Hex | Hex color for UI rendering | `#FFD700` |
| Icon URL | URL to league badge/icon image | (optional) |
| Description | Flavor text shown in the app | "Consistent progress." |
| Rewards | JSON list of rewards for reaching this league | (optional, collapsed) |

Leagues are ordered by `min_xp` ascending. Make sure XP ranges do not overlap and cover the full spectrum from 0 to infinity (top league has `max_xp = null`).

### Step 2: Configure SeasonConfig (Singleton)

**Admin URL:** `/admin/leagues/seasonconfig/`

SeasonConfig is a singleton model -- only one row exists. It controls all auto-grouping and season lifecycle parameters. If no row exists yet, click "Add Season Config" (the button disappears once a row exists). You can never delete it.

| Field | Default | Description |
|-------|---------|-------------|
| `season_duration_days` | 180 | Duration in days for new auto-created seasons (6 months). |
| `group_target_size` | 20 | Ideal number of users per group. The rebalance algorithm aims for this size. |
| `group_max_size` | 30 | Maximum members before a group must split. New users are never placed into a group above this limit. |
| `group_min_size` | 5 | Minimum members to keep a group alive. Groups below this threshold are merged during rebalancing. |
| `promotion_xp_threshold` | 1000 | Season XP at or above which a user is flagged for promotion at season end. |
| `relegation_xp_threshold` | 100 | Season XP below which a user is flagged for relegation at season end. |
| `auto_create_next_season` | True | When enabled, a new season is automatically created when the current one ends. Disable to manually control season transitions. |

**Admin fieldsets:**
- **Season Duration** -- `season_duration_days`, `auto_create_next_season`
- **Group Sizing** -- `group_target_size`, `group_max_size`, `group_min_size`
- **Promotion / Relegation** -- `promotion_xp_threshold`, `relegation_xp_threshold`
- **Metadata** (collapsed) -- `id`, `updated_at`

Changes to SeasonConfig take effect immediately (the cache is invalidated on save).

### Step 3: Create a Season

**Admin URL:** `/admin/leagues/season/`

Seasons define the competitive time window. Only one season can be active at a time.

**Creating a season manually:** Click "Add Season" and fill in:

| Field | Description |
|-------|-------------|
| Name | Display name (e.g., "Season 1 - Spring 2026") |
| Status | `pending` (will auto-activate when `start_date` arrives), or `active` to start immediately |
| Start Date | When the season begins (datetime) |
| End Date | When the season ends (datetime) |
| Duration Days | Informational; stored at creation for reference |
| Rewards | JSON list of season rewards (optional, collapsed) |

**Status lifecycle:**

```
pending  -->  active  -->  processing  -->  ended
```

- **pending** -- Scheduled for the future. The `auto_activate_pending_seasons` task (runs hourly) activates it when `start_date <= now`.
- **active** -- The live season. Users earn XP, get grouped, and compete.
- **processing** -- Transient state during season-end computation (rewards, promotions). Set automatically by `check_season_end`.
- **ended** -- Archived. Rewards can still be claimed.

**Tips:**
- To schedule a season in advance, create it with status `pending` and a future `start_date`. The hourly Celery task will activate it automatically.
- If `auto_create_next_season` is enabled in SeasonConfig, the next season is auto-created when the current one ends. The name increments automatically (e.g., "Season 1" -> "Season 2").
- The admin list view shows `status`, `start_date`, `end_date`, `is_active`, `duration_days`, `days_remaining`, and `created_at`.
- Expanding a season row shows an inline table of all `LeagueStanding` records for that season.

### Step 4: Managing Groups

**Admin URL:** `/admin/leagues/leaguegroup/`

Groups are typically auto-managed. When a user earns XP and gets a standing, the system assigns them to a group within their league tier. However, the admin provides full visibility and manual controls.

**List view columns:** `group_number`, `league`, `season`, `is_active`, `member_count`, `created_at`

**Filters:** `is_active`, `league`, `season`

**Inline:** Each group shows a `LeagueGroupMembershipInline` table listing all members (standing, joined_at, promoted_from_group).

**Admin action -- "Rebalance groups for selected league(s)":**
Select one or more groups and run this action. It collects unique (season, league) pairs from the selection and runs the rebalance algorithm for each. The algorithm:

1. Counts total members across all active groups for the season+league.
2. Computes the desired number of groups from `group_target_size`.
3. Collects all standings ordered by XP descending.
4. Round-robin distributes members into groups (highest XP users spread evenly).
5. Deactivates any now-empty groups.

After running, you see a success message like: "Rebalanced 2 league(s). 15 member(s) moved."

### Other Admin Panels

| Admin URL | Model | Notes |
|-----------|-------|-------|
| `/admin/leagues/leaguestanding/` | LeagueStanding | Filter by league/season. Search by user email/display name. |
| `/admin/leagues/seasonreward/` | SeasonReward | Filter by claimed status, league achieved, season. |
| `/admin/leagues/ranksnapshot/` | RankSnapshot | Daily snapshots. Filter by league, season, date. |
| `/admin/leagues/leagueseason/` | LeagueSeason | Themed cosmetic seasons (separate from competitive Season). |
| `/admin/leagues/seasonparticipant/` | SeasonParticipant | Participants in themed league seasons. |

---

## How Auto-Grouping Works

### User Flow

```
User earns XP
    |
    v
LeagueService.update_standing(user)
    |
    +--> Determines league from total XP
    +--> Creates/updates LeagueStanding for active season
    +--> Recalculates ranks (dense ranking by XP desc)
    +--> If new standing or league tier changed:
             |
             v
         LeagueService.assign_user_to_group(standing, season, league)
             |
             +--> Removes any existing group membership (handles tier changes)
             +--> Finds active group with fewest members under max_size
             +--> If none found, creates a new group
             +--> Creates LeagueGroupMembership
```

### Season Lifecycle

```
1. Admin creates leagues + SeasonConfig
2. Admin creates a Season (status=active or pending)
3. Pending seasons auto-activate when start_date arrives (hourly check)
4. Users earn XP --> standings created --> assigned to groups
5. Weekly: groups rebalance (Monday 3 AM)
6. Weekly: promotion/demotion cycle (Sunday 11 PM)
7. Daily: rank snapshots captured (11:55 PM)
8. Daily: check if season has ended (12:05 AM)
9. Season ends:
   a. Status set to "processing"
   b. Rewards calculated for all users
   c. Promotion/relegation flags computed
   d. League change notifications sent
   e. Status set to "ended"
   f. Next season auto-created (if enabled)
   g. All standings carried over, groups reassigned
```

### Group Sizing Logic

Given `N` users in a league tier with `target_size = 20`:

| Users | Groups | ~Size Each |
|-------|--------|-----------|
| 15 | 1 | 15 |
| 25 | 2 | 12-13 |
| 45 | 3 | 15 |
| 60 | 3 | 20 |
| 100 | 5 | 20 |

Groups are created as `ceil(N / target_size)`. Members are round-robin assigned by XP rank, so the strongest users are spread evenly across groups.

---

## Models

### SeasonConfig (Singleton)

Admin-configurable settings for the auto-grouping system. Only one row exists. Retrieved via `SeasonConfig.get()` which caches the result for 5 minutes.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| id | UUID | auto | Primary key |
| season_duration_days | PositiveInteger | 180 | Default duration for new seasons |
| group_target_size | PositiveInteger | 20 | Target members per group |
| group_max_size | PositiveInteger | 30 | Maximum members per group |
| group_min_size | PositiveInteger | 5 | Minimum members to keep group active |
| promotion_xp_threshold | PositiveInteger | 1000 | XP for promotion eligibility |
| relegation_xp_threshold | PositiveInteger | 100 | XP below which relegation risk triggers |
| auto_create_next_season | Boolean | True | Auto-create next season on end |
| updated_at | DateTimeField | auto | Last modification timestamp |

**DB table:** `season_config`

### League

Represents a competitive league tier.

| Field | Type | Description |
|-------|------|-------------|
| id | UUID | Primary key |
| name | CharField(100) | Display name (e.g., "Bronze League") |
| tier | CharField(20) | Tier key: `bronze`, `silver`, `gold`, `platinum`, `diamond`, `master`, `legend` (unique) |
| min_xp | Integer | Minimum XP to enter (default: 0) |
| max_xp | Integer | Maximum XP for this league (null for Legend) |
| icon_url | URLField(500) | League badge image URL |
| color_hex | CharField(7) | Hex color code (e.g., `#CD7F32`) |
| description | TextField | League description |
| rewards | JSONField | List of rewards for reaching this league |

**DB table:** `leagues`

**Properties:**
- `tier_order` -- Numeric sort order (0=bronze through 6=legend)

**Methods:**
- `contains_xp(xp)` -- Check if a given XP value falls within this league's range
- `seed_defaults()` -- Class method to create all 7 default tiers (idempotent)

### Season

Represents a competitive season with defined start and end dates.

| Field | Type | Description |
|-------|------|-------------|
| id | UUID | Primary key |
| name | CharField(200) | Display name (e.g., "Season 1 - Winter 2026") |
| start_date | DateTimeField | Season start |
| end_date | DateTimeField | Season end |
| is_active | Boolean | Whether currently active (synced from status) |
| status | CharField(20) | Lifecycle status: `pending`, `active`, `processing`, `ended` |
| duration_days | PositiveInteger | Duration stored at creation time (nullable) |
| rewards | JSONField | List of available rewards for this season |
| created_at | DateTimeField | Auto-set on creation |
| updated_at | DateTimeField | Auto-set on update |

**DB table:** `seasons`

**Properties:**
- `is_current` -- True if current time falls within start/end dates
- `has_ended` -- True if season end date has passed
- `days_remaining` -- Number of days left in the season
- `seconds_remaining` -- Seconds left (used for frontend countdown timers)
- `ends_at` -- Alias for `end_date` (used by serializer)

**Class methods:**
- `get_active_season()` -- Return the currently active season or None (cached 1 hour)

**Note:** `save()` keeps `is_active` in sync with `status` for backward compatibility. Setting status to `active` sets `is_active=True`; `processing` or `ended` sets `is_active=False`.

### LeagueStanding

Tracks a user's rank and stats within a league for a season.

| Field | Type | Description |
|-------|------|-------------|
| id | UUID | Primary key |
| user | FK(User) | The ranked user (related_name: `league_standings`) |
| league | FK(League) | Current league (related_name: `standings`) |
| season | FK(Season) | Season context (related_name: `standings`) |
| rank | Integer | Current rank within the season (1 = top), uses dense ranking |
| xp_earned_this_season | Integer | Total XP earned this season |
| tasks_completed | Integer | Tasks completed this season |
| dreams_completed | Integer | Dreams completed this season |
| streak_best | Integer | Best streak (consecutive days) this season |
| updated_at | DateTimeField | Auto-set on update |

**DB table:** `league_standings`
**Constraint:** Unique on `(user, season)`

### LeagueGroup

A competitive group within a league tier for a specific season.

| Field | Type | Description |
|-------|------|-------------|
| id | UUID | Primary key |
| season | FK(Season) | The season this group belongs to (related_name: `groups`) |
| league | FK(League) | The league tier (related_name: `groups`) |
| group_number | PositiveInteger | Group number within season+league (1-indexed) |
| is_active | Boolean | Whether the group is active (deactivated when empty after rebalance) |
| created_at | DateTimeField | Auto-set on creation |

**DB table:** `league_groups`
**Constraint:** Unique on `(season, league, group_number)`

**Properties:**
- `member_count` -- Number of active members (computed from memberships)

### LeagueGroupMembership

Junction table linking a LeagueStanding to a LeagueGroup. Each standing belongs to exactly one group (OneToOne on standing).

| Field | Type | Description |
|-------|------|-------------|
| id | UUID | Primary key |
| group | FK(LeagueGroup) | The group (related_name: `memberships`) |
| standing | OneToOne(LeagueStanding) | The standing (related_name: `group_membership`) |
| joined_at | DateTimeField | When assigned to this group |
| promoted_from_group | FK(LeagueGroup, nullable) | Previous group if promoted (related_name: `promotions_out`) |

**DB table:** `league_group_memberships`

### SeasonReward

Tracks rewards earned by a user at season end.

| Field | Type | Description |
|-------|------|-------------|
| id | UUID | Primary key |
| season | FK(Season) | Source season (related_name: `season_rewards`) |
| user | FK(User) | Reward recipient (related_name: `season_rewards`) |
| league_achieved | FK(League) | League when season ended (related_name: `season_rewards`) |
| rewards_claimed | Boolean | Whether user has claimed rewards (default: False) |
| claimed_at | DateTimeField | Claim timestamp (nullable) |
| created_at | DateTimeField | Auto-set on creation |

**DB table:** `season_rewards`
**Constraint:** Unique on `(season, user)`

**Methods:**
- `claim()` -- Mark reward as claimed with timestamp

### RankSnapshot

Daily snapshot of user rankings for historical tracking and trend analysis.

| Field | Type | Description |
|-------|------|-------------|
| id | UUID | Primary key |
| user | FK(User) | Tracked user (related_name: `rank_snapshots`) |
| season | FK(Season) | Season context (related_name: `rank_snapshots`) |
| league | FK(League) | User's league at snapshot time |
| rank | Integer | User's rank at snapshot time |
| xp | Integer | User's XP at snapshot time |
| snapshot_date | DateField | Date of the snapshot |
| created_at | DateTimeField | Auto-set on creation |

**DB table:** `rank_snapshots`
**Constraint:** Unique on `(user, season, snapshot_date)`

---

## API Endpoints

All league endpoints are mounted under `/api/leagues/` (via `config/urls.py`). All require `IsAuthenticated` + `CanUseLeague` permission (premium subscription).

### Leagues

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/leagues/leagues/` | List all league tiers (no pagination) |
| GET | `/api/leagues/leagues/{id}/` | League detail |

### Leaderboards

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/leagues/leaderboard/global/` | Top 100 users by XP (query: `?limit=N`, max 100). Cached 5 min. |
| GET | `/api/leagues/leaderboard/league/` | Users in same league (query: `?league_id=UUID&limit=N`) |
| GET | `/api/leagues/leaderboard/friends/` | Friends leaderboard (via Friendship + BuddyPairing) |
| GET | `/api/leagues/leaderboard/me/` | Current user's standing (creates if missing) |
| GET | `/api/leagues/leaderboard/nearby/` | Users ranked above/below (query: `?count=N`, max 10) |
| GET | `/api/leagues/leaderboard/group/` | Group leaderboard (query: `?group_id=UUID&limit=N`). Falls back to user's own group. |

### Seasons

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/leagues/seasons/` | List all seasons |
| GET | `/api/leagues/seasons/{id}/` | Season detail |
| GET | `/api/leagues/seasons/current/` | Current active season (with countdown data) |
| GET | `/api/leagues/seasons/past/` | Past (ended) seasons |
| GET | `/api/leagues/seasons/my-rewards/` | Current user's season rewards |
| POST | `/api/leagues/seasons/{id}/claim-reward/` | Claim rewards for a completed season |

### Groups

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/leagues/groups/` | List active groups for current season (query: `?league_id=UUID`) |
| GET | `/api/leagues/groups/{id}/` | Group detail |
| GET | `/api/leagues/groups/mine/` | Current user's group assignment |
| GET | `/api/leagues/groups/{id}/leaderboard/` | Group leaderboard (query: `?limit=N`, max 50) |

### League Seasons (Themed/Cosmetic)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/leagues/league-seasons/` | List all themed league seasons |
| GET | `/api/leagues/league-seasons/{id}/` | League season detail |
| GET | `/api/leagues/league-seasons/current/` | Current active league season |
| POST | `/api/leagues/league-seasons/current/join/` | Join the current league season |
| GET | `/api/leagues/league-seasons/{id}/leaderboard/` | League season leaderboard (cached 5 min) |
| POST | `/api/leagues/league-seasons/{id}/claim-rewards/` | Claim end-of-season rewards |

---

## Services (LeagueService)

All ranking business logic is encapsulated in `LeagueService` (`services.py`):

### Core Methods

| Method | Description |
|--------|-------------|
| `get_user_league(user)` | Determine league based on user's total XP |
| `update_standing(user)` | Recalculate standing after XP change (atomic). Creates standing if needed, recalculates all ranks, assigns to group on creation or tier change |
| `get_leaderboard(league, limit, season)` | Retrieve ranked user list. If league is None, returns global leaderboard |
| `promote_demote_users()` | End-of-week league tier changes based on current XP (atomic). Returns `{promoted, demoted}` counts |
| `calculate_season_rewards(season)` | Create reward records for all users when season ends (atomic) |
| `get_nearby_ranks(user, count)` | Users ranked above and below. Returns `{above, current, below}` |
| `increment_tasks_completed(user)` | Increment tasks_completed counter for active standing |
| `increment_dreams_completed(user)` | Increment dreams_completed counter for active standing |

### Auto-Grouping Methods

| Method | Description |
|--------|-------------|
| `assign_user_to_group(standing, season, league)` | Assign a standing to the best-fit group (fewest members under max). Creates a new group if none have room. Handles tier changes by removing old membership first. Uses `select_for_update` for concurrency safety. |
| `rebalance_league_groups(season, league)` | Rebalance all groups for a season+league. Round-robin by XP rank. Returns `{groups_active, groups_deactivated, members_moved}`. |
| `compute_season_end_promotions(season)` | Compute promotion/relegation counts based on SeasonConfig thresholds. Returns `{promoted, relegated, neutral}`. |
| `create_next_season(ended_season)` | Auto-create the next season, carry over standings, assign groups. Returns the new Season or None if disabled. |
| `get_group_leaderboard(group, limit)` | Leaderboard for a specific group, ranked by XP. |

### Internal Methods

- `_recalculate_ranks(season)` -- Dense ranking of all standings by XP descending

---

## Celery Tasks

All tasks are in the `social` queue (`apps.leagues.tasks.*`).

### Scheduled Tasks (Celery Beat)

| Task | Schedule | Description |
|------|----------|-------------|
| `check_season_end` | Daily at 12:05 AM | Checks if the active season has ended. Sets status to `processing` and chains `process_season_end`. |
| `create_daily_rank_snapshots` | Daily at 11:55 PM | Creates a `RankSnapshot` for every active standing. Idempotent (uses `update_or_create`). |
| `send_league_change_notifications` | Weekly, Sunday at 11:00 PM | Runs promotion/demotion cycle and sends notifications to affected users. |
| `rebalance_groups_task` | Weekly, Monday at 3:00 AM | Rebalances groups across all leagues in the active season. |
| `auto_activate_pending_seasons` | Hourly at :00 | Activates pending seasons whose `start_date` has arrived. Deactivates any existing active season first. |

### Chained Tasks (Triggered by Events)

| Task | Triggered By | Description |
|------|-------------|-------------|
| `process_season_end(season_id)` | `check_season_end` | Computes rewards, promotion/relegation, sends notifications, marks season ended, then chains `create_next_season_task`. |
| `create_next_season_task(ended_season_id)` | `process_season_end` | Creates the next season via `LeagueService.create_next_season()` if `auto_create_next_season` is enabled. |
| `send_league_change_notifications(season_id)` | `process_season_end` | Sends promotion/demotion push notifications. |

---

## Serializers

| Serializer | Purpose |
|------------|---------|
| `LeagueSerializer` | Full league details with computed `tier_order` |
| `LeagueStandingSerializer` | Standing with user public info (`display_name`, `avatar_url`, `level`, `badges`), league info, and stats. Never exposes dreams |
| `SeasonSerializer` | Season with computed `is_current`, `has_ended`, `days_remaining`, `seconds_remaining`, `ends_at` |
| `SeasonRewardSerializer` | Reward with nested `season_name`, `league_name`, `league_tier`, `league_rewards` |
| `LeaderboardEntrySerializer` | Lightweight entry: `rank`, `user_id`, `user_display_name`, `user_avatar_url`, `user_level`, `league_name`, `league_tier`, `league_color_hex`, `xp`, `tasks_completed`, `badges_count`, `is_current_user` |
| `LeagueGroupSerializer` | Group info: `id`, `season`, `league`, `group_number`, `is_active`, `member_count` |
| `LeagueSeasonSerializer` | Themed league season with participation info |
| `SeasonParticipantSerializer` | Participant XP, rank, and claim status |

---

## Management Commands

| Command | Description |
|---------|-------------|
| `seed_leagues` | Seeds the database with the 7 default league tiers (Bronze through Legend) with XP ranges, colors, icons, and descriptions. Idempotent. |

---

## Quick Start Checklist

For a fresh deployment, complete these steps in order:

1. Run `python manage.py seed_leagues` to create the 7 default league tiers.
2. Go to `/admin/leagues/seasonconfig/` and create the singleton config (or adjust defaults).
3. Go to `/admin/leagues/season/` and create a season with status `active` (or `pending` with a future start date).
4. Verify Celery Beat is running -- it handles season activation, season end, group rebalancing, and rank snapshots automatically.
5. As users earn XP, standings and groups are created automatically by `LeagueService.update_standing()`.

No manual group creation is needed. The system handles it.
