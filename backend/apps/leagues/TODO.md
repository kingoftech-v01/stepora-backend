# Leagues App - TODO

## Completed

- [x] **Promotion/demotion notifications** - Push notifications sent to users when they are promoted to a higher league or demoted to a lower one. Includes the old and new league names and any rewards unlocked (Celery task).

- [x] **Historical rank tracking** - Historical rank snapshots stored (RankSnapshot model + daily snapshots) so users can view their rank progression over time. API endpoint to retrieve rank history as a time series for charting in the mobile app.

- [x] **Season transition automation** - Automated season transitions via Celery beat (check_season_end task): detects when the active season's `end_date` has passed, calls `calculate_season_rewards()`, deactivates the old season, and activates the next season.

- [x] **Seed data management command** - Django management command (`python manage.py seed_leagues`) to populate the 7 default leagues with their XP ranges, colors, and icons. Idempotent for safe re-runs.

- [x] **Dense ranking** - Dense ranking so users with the same XP share the same rank position rather than receiving arbitrarily ordered sequential ranks.

## Planned Improvements

- [ ] **League-specific rewards** - Define and distribute concrete rewards (store items, XP bonuses, badges) when users reach each league tier, beyond just the JSON `rewards` field.

- [ ] **Rank caching** - Cache leaderboard results in Redis to reduce database load from frequent leaderboard queries. Invalidate on XP changes.

- [ ] **Leaderboard pagination** - Add pagination to leaderboard endpoints for leagues with many participants, rather than relying solely on the `limit` parameter.

- [ ] **Season creation admin action** - Add a Django admin action to create a new season with sensible defaults and automatically link it as the next season after the current one ends.
