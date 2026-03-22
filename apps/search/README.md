# Search App

Global search across all Stepora content with Elasticsearch and PostgreSQL DB fallback.

## Architecture

```
GlobalSearchView (API)
  |
  v
SearchService.global_search(user, query, types, limit)
  |
  ├── search_dreams(user, query)
  ├── search_goals(user, query, dream_id?)
  ├── search_tasks(user, query)
  ├── search_messages(user, query, conversation_id?)
  ├── search_users(query)
  ├── search_calendar(user, query)
  ├── search_circle_posts(query, user?, circle_id?)
  ├── search_circle_challenges(query, user?, circle_id?)
  └── search_activity_comments(user, query)
          |
          v
    _es_search(es_fn, db_fn, label)
       ├── Try Elasticsearch first
       └── Fall back to PostgreSQL icontains
```

## API Endpoint

```
GET /api/search/?q=<query>&type=<types>
```

- **Authentication**: Required (IsAuthenticated)
- **Rate limit**: `search` scope (15/minute production, 10000/minute test)
- **Minimum query**: 2 characters
- **Types**: Comma-separated. Default: all types.
  - `dreams`, `goals`, `tasks`, `messages`, `users`, `calendar`, `circles`, `circle_challenges`, `activity_comments`
- **Limit**: 10 results per type

### Response format

```json
{
  "dreams": [{"id": "uuid", "title": "...", "status": "active"}],
  "goals":  [{"id": "uuid", "title": "...", "dream_id": "uuid"}],
  "tasks":  [{"id": "uuid", "title": "...", "goal_id": "uuid"}],
  "messages": [{"id": "uuid", "content": "...", "conversation_id": "uuid", "role": "user"}],
  "users":  [{"id": "uuid", "display_name": "...", "avatar_url": "..."}],
  "calendar": [{"id": "uuid", "title": "...", "start_time": "ISO8601"}],
  "circles": [{"id": "uuid", "content": "...", "circle_id": "uuid", "circle_name": "..."}]
}
```

Empty categories are omitted from the response.

### Security

- Dreams, goals, tasks, messages, calendar events: scoped to the requesting user.
- Circle posts: scoped to circles the user is a member of.
- Users: public search (active users only).
- Message content truncated to 200 characters.

## Elasticsearch Documents

Defined in `documents.py`. Each document maps encrypted Django model fields to searchable ES text fields using `prepare_<field>()` methods.

| Document | Index Name | Model | Searchable Fields |
|----------|-----------|-------|-------------------|
| DreamDocument | stepora_dreams | Dream | title, description |
| GoalDocument | stepora_goals | Goal | title, description |
| TaskDocument | stepora_tasks | Task | title, description |
| MessageDocument | stepora_messages | AIMessage | content |
| UserDocument | stepora_users | User | display_name |
| CalendarEventDocument | stepora_calendar | CalendarEvent | title, description, location |
| CirclePostDocument | stepora_circle_posts | CirclePost | content |
| CircleChallengeDocument | stepora_circle_challenges | CircleChallenge | title, description |
| ActivityCommentDocument | stepora_activity_comments | ActivityComment | text |

## DB Fallback

When Elasticsearch is unavailable (`_ES_AVAILABLE = False` or connection errors), all searches fall back to PostgreSQL `icontains` queries. Note: encrypted fields (title, display_name, etc.) may not match with `icontains` when encrypted; the fallback is a best-effort mechanism.

Production currently runs with `ELASTICSEARCH_DSL_AUTOSYNC = False` (no ES instance on ECS).

## Management Commands

```bash
# Create missing indexes and populate them (idempotent, safe for startup)
python manage.py ensure_search_index

# Rebuild all indexes from scratch (destructive, for maintenance)
python manage.py rebuild_search_index
python manage.py rebuild_search_index --models=dream,user
```

## Recent Searches

Recent search history is managed by `RecentSearchViewSet` in `apps.social` (not in this app):

```
GET  /api/social/recent-searches/list/
POST /api/social/recent-searches/add/
DEL  /api/social/recent-searches/clear/
DEL  /api/social/recent-searches/<id>/remove/
```

The frontend GlobalSearch component uses localStorage for recent searches. The UserSearchScreen uses the backend API.

## Frontend Integration

- `GlobalSearch.jsx`: Full-screen overlay with debounced search, triggered from home screen header.
- Searches all 9 backend types: dreams, messages, users, goals, tasks, calendar, circles, circle_challenges, activity_comments.
- Results navigate to the appropriate detail page.
- i18n keys: `search.placeholder`, `search.cancel`, `search.recent`, `search.noResults`, `search.emptyState`, `search.category.*`.

## Tests

```bash
# Run all search tests
DJANGO_SETTINGS_MODULE=config.settings.testing python -m pytest apps/search/tests/ --no-cov

# Run comprehensive test file
DJANGO_SETTINGS_MODULE=config.settings.testing python -m pytest apps/search/tests/test_search_complete.py --no-cov
```

### Test coverage

- **test_search_complete.py** (81 tests): Auth, validation, type filtering, result hydration for all 7 response types, cross-user isolation, _es_search helper, all 9 SearchService methods, global_search, management commands, rate limiting/permissions.
- **test_search_views.py** (17 tests): GlobalSearchView API tests.
- **test_search_services.py** (26 tests): SearchService and _es_search tests.
- **test_unit.py** (15 tests): Unit tests with mocked DB queries.
- **Frontend**: `GlobalSearch.test.jsx` (19 tests): Render states, API calls, debounce, result display, navigation, recent searches, error handling.
