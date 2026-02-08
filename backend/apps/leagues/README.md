# Leagues App

Django application implementing a competitive ranking system with 7-tier leagues, seasonal competitions, leaderboards, and season rewards.

## Overview

The Leagues app provides a gamification layer with XP-based league tiers, seasonal standings, and leaderboard views. Users earn XP through task and dream completions and are ranked within their league. The system supports global, league-specific, and friends leaderboards. Privacy is enforced by design: leaderboards expose scores and badges but never user dreams.

### League Tiers (by XP)

| Tier | XP Range |
|------|----------|
| Bronze | 0 - 499 XP |
| Silver | 500 - 1,499 XP |
| Gold | 1,500 - 3,499 XP |
| Platinum | 3,500 - 6,999 XP |
| Diamond | 7,000 - 11,999 XP |
| Master | 12,000 - 19,999 XP |
| Legend | 20,000+ XP |

## Models

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
- `tier_order` - Numeric sort order (0=bronze through 6=legend)

**Methods:**
- `contains_xp(xp)` - Check if a given XP value falls within this league's range

**Class attribute:**
- `TIER_ORDER` - Dict mapping tier strings to numeric order values

### Season

Represents a competitive season with defined start and end dates.

| Field | Type | Description |
|-------|------|-------------|
| id | UUID | Primary key |
| name | CharField(200) | Display name (e.g., "Season 1 - Winter 2026") |
| start_date | DateTimeField | Season start |
| end_date | DateTimeField | Season end |
| is_active | Boolean | Whether currently active (only one should be active at a time) |
| rewards | JSONField | List of available rewards for this season |
| created_at | DateTimeField | Auto-set on creation |
| updated_at | DateTimeField | Auto-set on update |

**DB table:** `seasons`

**Properties:**
- `is_current` - True if current time falls within start/end dates
- `has_ended` - True if season end date has passed
- `days_remaining` - Number of days left in the season

**Class methods:**
- `get_active_season()` - Return the currently active season or None

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
**Constraint:** `unique_together = [['user', 'season']]`

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
**Constraint:** `unique_together = [['user', 'season', 'snapshot_date']]`

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
**Constraint:** `unique_together = [['season', 'user']]`

**Methods:**
- `claim()` - Mark reward as claimed with timestamp

## API Endpoints

### Leagues

| Method | Path | Description |
|--------|------|-------------|
| GET | `/leagues/` | List all league tiers (no pagination) |
| GET | `/leagues/{id}/` | League detail |

**ViewSet:** `LeagueViewSet` (ReadOnlyModelViewSet)
- Permission: `IsAuthenticated`

### Leaderboards

| Method | Path | Description |
|--------|------|-------------|
| GET | `/leaderboard/global/` | Top 100 users by XP (query: `?limit=N`, max 100) |
| GET | `/leaderboard/league/` | Users in same league (query: `?league_id=UUID&limit=N`) |
| GET | `/leaderboard/friends/` | Friends leaderboard (via DreamBuddy model) |
| GET | `/leaderboard/me/` | Current user's standing (creates if missing) |
| GET | `/leaderboard/nearby/` | Users ranked above/below (query: `?count=N`, max 10) |

**ViewSet:** `LeaderboardViewSet` (GenericViewSet)
- Permission: `IsAuthenticated`

### Seasons

| Method | Path | Description |
|--------|------|-------------|
| GET | `/seasons/` | List all seasons |
| GET | `/seasons/{id}/` | Season detail |
| GET | `/seasons/current/` | Current active season |
| GET | `/seasons/past/` | Past (inactive) seasons |
| GET | `/seasons/my-rewards/` | Current user's season rewards |
| POST | `/seasons/{id}/claim-reward/` | Claim rewards for a completed season |

**ViewSet:** `SeasonViewSet` (ReadOnlyModelViewSet + custom actions)
- Permission: `IsAuthenticated`

## Serializers

| Serializer | Purpose |
|------------|---------|
| `LeagueSerializer` | Full league details with computed `tier_order` |
| `LeagueStandingSerializer` | Standing with user public info (`display_name`, `avatar_url`, `level`, `badges`), league info, and stats. Never exposes dreams |
| `SeasonSerializer` | Season with computed `is_current`, `has_ended`, `days_remaining` |
| `SeasonRewardSerializer` | Reward with nested `season_name`, `league_name`, `league_tier`, `league_rewards` |
| `LeaderboardEntrySerializer` | Lightweight entry for leaderboard lists: `rank`, `user_id`, `user_display_name`, `user_avatar_url`, `user_level`, `league_name`, `league_tier`, `league_color_hex`, `xp`, `tasks_completed`, `badges_count`, `is_current_user` |

## Services (LeagueService)

All ranking business logic is encapsulated in `LeagueService`:

| Method | Description |
|--------|-------------|
| `get_user_league(user)` | Determine league based on user's XP |
| `update_standing(user)` | Recalculate standing after XP change (atomic). Creates standing if needed, recalculates all ranks |
| `get_leaderboard(league, limit, season)` | Retrieve ranked user list. If league is None, returns global leaderboard |
| `promote_demote_users()` | End-of-week league tier changes based on current XP (atomic). Returns `{promoted, demoted}` counts. Sends promotion/demotion notifications to affected users |
| `calculate_season_rewards(season)` | Create reward records for all users when season ends (atomic). Deactivates the season |
| `take_daily_rank_snapshots()` | Creates a RankSnapshot for every active standing in the current season |
| `get_nearby_ranks(user, count)` | Users ranked above and below. Returns `{above, current, below}` |
| `increment_tasks_completed(user)` | Increment tasks_completed counter for active standing |
| `increment_dreams_completed(user)` | Increment dreams_completed counter for active standing |

### Internal Methods

- `_recalculate_ranks(season)` - Recalculate ranks for all standings in a season by XP descending

## Admin

All four models are registered with Django admin:

- **LeagueAdmin** - Fieldsets for basic info, XP range, appearance, rewards
- **SeasonAdmin** - Shows `days_remaining` in list. Includes `LeagueStandingInline` for viewing standings within a season
- **LeagueStandingAdmin** - Filter by league and season. Search by user email/display name
- **SeasonRewardAdmin** - Filter by claimed status, league achieved, season
- **RankSnapshotAdmin** - Filter by season, league, date. Search by user email/display name

## Management Commands

| Command | Description |
|---------|-------------|
| `seed_leagues` | Seeds the database with the 7 default league tiers (Bronze through Legend) with XP ranges, colors, icons, and descriptions. Idempotent |

## Celery Tasks

| Task | Description |
|------|-------------|
| `check_season_end` | Runs on a schedule to detect when the active season has ended. Automatically triggers reward calculation and season deactivation |
| `take_daily_rank_snapshots` | Creates daily RankSnapshot records for all active standings. Runs once per day |
| `send_promotion_demotion_notifications` | Sends push notifications to users who have been promoted or demoted after weekly league tier changes |
