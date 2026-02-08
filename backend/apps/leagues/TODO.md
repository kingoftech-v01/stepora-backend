# Leagues App - TODO

## Planned Features

- [ ] **Promotion/demotion notifications** - Send push notifications to users when they are promoted to a higher league or demoted to a lower one. Include the old and new league names and any rewards unlocked.

- [ ] **Historical rank tracking** - Store historical rank snapshots (daily or weekly) so users can view their rank progression over time. Add an API endpoint to retrieve rank history as a time series for charting in the mobile app.

- [ ] **Season transition automation** - Implement automated season transitions via Celery beat: detect when the active season's `end_date` has passed, call `calculate_season_rewards()`, deactivate the old season, and optionally activate the next season.

- [ ] **Seed data management command** - Create a Django management command (`python manage.py seed_leagues`) to populate the 7 default leagues with their XP ranges, colors, and icons. Make it idempotent for safe re-runs.

## Improvements

- [ ] **Dense ranking** - Switch from sequential ranking to dense ranking so users with the same XP share the same rank position rather than receiving arbitrarily ordered sequential ranks.

- [ ] **League-specific rewards** - Define and distribute concrete rewards (store items, XP bonuses, badges) when users reach each league tier, beyond just the JSON `rewards` field.

- [ ] **Rank caching** - Cache leaderboard results in Redis to reduce database load from frequent leaderboard queries. Invalidate on XP changes.

- [ ] **Leaderboard pagination** - Add pagination to leaderboard endpoints for leagues with many participants, rather than relying solely on the `limit` parameter.

- [ ] **Season creation admin action** - Add a Django admin action to create a new season with sensible defaults and automatically link it as the next season after the current one ends.
