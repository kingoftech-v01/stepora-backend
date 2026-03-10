# League Season Auto-Grouping Architecture Blueprint

## Overview
Automatic group management within leagues, with configurable seasons, promotion/relegation, and admin controls.

## Key Design Decisions
- **Group-within-League model**: `LeagueGroup` + `LeagueGroupMembership` junction tables
- **Built on `Season`/`LeagueStanding`** (primary competitive layer), not `LeagueSeason` (cosmetic)
- **`SeasonConfig` singleton** for all admin-configurable parameters
- **Round-robin by XP rank** for balanced group distribution

## New Models

### SeasonConfig (singleton)
- `season_duration_days` (default 180)
- `group_target_size` (default 20), `group_max_size` (30), `group_min_size` (5)
- `promotion_xp_threshold` (1000), `relegation_xp_threshold` (100)
- `auto_create_next_season` (True)

### LeagueGroup
- FK to Season + League, `group_number`, `is_active`
- Unique on (season, league, group_number)

### LeagueGroupMembership
- FK to LeagueGroup, OneToOne to LeagueStanding
- Tracks `joined_at`, `promoted_from_group`

### Season modifications
- Add `status` field: pending/active/processing/ended
- Add `duration_days` stored at creation time

## Algorithms
- **assign_user_to_group**: Find group with fewest members under max_size, or create new
- **rebalance_league_groups**: Count members → compute desired groups → round-robin redistribute by XP rank → delete empty groups
- **Season end**: promote (xp >= threshold), relegate (xp < threshold), create next season, rebalance all groups

## Build Sequence
Phase 1: DB Models → Phase 2: Service Layer → Phase 3: Celery Tasks → Phase 4: Serializers/Views → Phase 5: Admin → Phase 6: Frontend

## Frontend
- Live countdown (days/hours/minutes/seconds) on SeasonDetail
- Group info card with rank within group
- Promotion/relegation pill indicators
- New GroupLeaderboard page at /leagues/group/:groupId

See full blueprint in agent output: /tmp/claude-0/-root/tasks/ae85fbf8af72e5703.output
