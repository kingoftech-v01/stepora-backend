# Calendar App

Django application for calendar management, task scheduling, time blocks, conflict detection, and Google Calendar integration.

## Overview

The Calendar app manages:

- **CalendarEvent** - Calendar events linked to dream tasks with conflict detection
- **TimeBlock** - Recurring weekly time blocks for scheduling preferences
- **GoogleCalendarIntegration** - OAuth2 bidirectional sync with Google Calendar + iCal feed export

## Models

### CalendarEvent

Calendar event for task scheduling.

| Field | Type | Description |
|-------|------|-------------|
| id | UUID | Primary key |
| user | FK(User) | Owner (related_name: `calendar_events`) |
| task | FK(Task) | Associated dream task (nullable, related_name: `calendar_events`) |
| title | CharField(255) | Event title |
| description | TextField | Description (blank) |
| start_time | DateTimeField | Start time (indexed) |
| end_time | DateTimeField | End time |
| location | CharField(255) | Location/context (blank) |
| reminder_minutes_before | IntegerField | Reminder offset in minutes (default: 15) |
| status | CharField(20) | `scheduled`, `completed`, `cancelled`, `rescheduled` (default: `scheduled`) |
| is_recurring | BooleanField | Whether this is a recurring event (default: False) |
| recurrence_rule | JSONField | Recurrence config (nullable): `{frequency: "daily\|weekly\|monthly", interval: 1, end_date: "ISO"}` |
| parent_event | FK(self) | Parent event for recurring instances (nullable, related_name: `recurring_instances`) |
| created_at | DateTimeField | Auto-set on creation |
| updated_at | DateTimeField | Auto-set on update |

**DB table:** `calendar_events`
**Ordering:** `['start_time']`
**Indexes:** `(user, start_time)`, `status`

### TimeBlock

User-defined weekly time blocks for scheduling preferences.

| Field | Type | Description |
|-------|------|-------------|
| id | UUID | Primary key |
| user | FK(User) | Owner (related_name: `time_blocks`) |
| block_type | CharField(20) | `work`, `personal`, `family`, `exercise`, `blocked` |
| day_of_week | IntegerField | 0=Monday, 6=Sunday |
| start_time | TimeField | Start time |
| end_time | TimeField | End time |
| is_active | BooleanField | Whether block is active (default: True) |
| created_at | DateTimeField | Auto-set on creation |
| updated_at | DateTimeField | Auto-set on update |

**DB table:** `time_blocks`
**Ordering:** `['day_of_week', 'start_time']`

### GoogleCalendarIntegration

OAuth2 integration for bidirectional Google Calendar sync.

| Field | Type | Description |
|-------|------|-------------|
| id | UUID | Primary key |
| user | OneToOne(User) | Linked user (related_name: `google_calendar`) |
| access_token | TextField | OAuth2 access token |
| refresh_token | TextField | OAuth2 refresh token |
| token_expiry | DateTimeField | Token expiration timestamp |
| calendar_id | CharField(255) | Google Calendar ID (default: `primary`) |
| sync_enabled | BooleanField | Whether sync is active (default: True) |
| last_sync_at | DateTimeField | Last successful sync timestamp (nullable) |
| sync_token | CharField(500) | Google incremental sync token (blank) |
| ical_feed_token | CharField(64) | Secret token for iCal feed URL (unique, auto-generated on save) |
| created_at | DateTimeField | Auto-set on creation |
| updated_at | DateTimeField | Auto-set on update |

**DB table:** `google_calendar_integrations`

## API Endpoints

### Calendar Events (CRUD)

**ViewSet:** `CalendarEventViewSet` (ModelViewSet)
- Permission: `IsAuthenticated`
- Users can only see/modify their own events
- Create and update include automatic **conflict detection** (see below)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/events/` | List all events for current user |
| POST | `/events/` | Create event (with conflict detection) |
| GET | `/events/{id}/` | Get event detail |
| PUT/PATCH | `/events/{id}/` | Update event (with conflict detection) |
| DELETE | `/events/{id}/` | Delete event |
| PATCH | `/events/{id}/reschedule/` | Reschedule to new times (also updates linked task) |

### Calendar Views

**ViewSet:** `CalendarViewSet` (ViewSet)
- Permission: `IsAuthenticated`

| Method | Path | Description |
|--------|------|-------------|
| GET | `/view/?start={ISO}&end={ISO}` | Get tasks for a date range (returns dream/goal context) |
| GET | `/today/` | Get tasks scheduled for today |
| POST | `/reschedule/` | Reschedule a task (body: `{"task_id": "UUID", "new_date": "ISO"}`) |
| GET | `/suggest-time-slots/?date=YYYY-MM-DD&duration_mins=N` | Find optimal open time slots |

### Time Blocks (CRUD)

**ViewSet:** `TimeBlockViewSet` (ModelViewSet)
- Permission: `IsAuthenticated`

| Method | Path | Description |
|--------|------|-------------|
| GET | `/timeblocks/` | List time blocks |
| POST | `/timeblocks/` | Create time block |
| GET | `/timeblocks/{id}/` | Get time block detail |
| PUT/PATCH | `/timeblocks/{id}/` | Update time block |
| DELETE | `/timeblocks/{id}/` | Delete time block |

### Google Calendar Integration

| Method | Path | Description |
|--------|------|-------------|
| GET | `/google/auth/` | Get Google OAuth2 authorization URL |
| POST | `/google/callback/` | Handle OAuth2 callback (body: `{"code": "..."}`) |
| POST | `/google/sync/` | Trigger manual bidirectional sync (queues Celery task) |
| POST | `/google/disconnect/` | Disconnect Google Calendar integration |

### iCal Feed

| Method | Path | Description |
|--------|------|-------------|
| GET | `/ical-feed/{feed_token}/` | Export calendar as iCal (subscribable, no auth required) |

- Permission: `AllowAny` (authenticated by secret `feed_token`)
- Returns `text/calendar` with events from -30 days to +90 days
- Compatible with Apple Calendar, Outlook, Google Calendar subscriptions

## Conflict Detection

Create, update, and reschedule operations automatically detect overlapping events:

1. Checks for existing `scheduled` events overlapping the requested time range
2. If conflicts found and `force=false` (default): returns **409 Conflict** with:
   - `detail`: explanation message
   - `conflicts`: list of conflicting events
   - `hint`: "Set force=true to save anyway."
3. If `force=true`: saves despite conflicts

## Smart Time Slot Suggestions

The `suggest-time-slots` endpoint finds available slots considering:

1. **Existing events** for the target date
2. **Blocked time blocks** for the day of week
3. **Working hours** - slots between 8 AM and 10 PM only
4. **Buffer time** - configurable via `notification_prefs.buffer_minutes` (default: 15 min)
5. **Duration** - must be 5-480 minutes

Returns up to 10 available slots with start/end times.

## Serializers

| Serializer | Purpose |
|------------|---------|
| `CalendarEventSerializer` | Read: full event with computed `task_title`, `goal_title`, `dream_title` |
| `CalendarEventCreateSerializer` | Write: create/update event with `force` flag, input sanitization (title, description, location) |
| `CalendarEventRescheduleSerializer` | Input: `start_time`, `end_time`, `force` for rescheduling |
| `SuggestTimeSlotsSerializer` | Input: `date`, `duration_mins` (5-480) |
| `TimeBlockSerializer` | Full time block with computed `day_name` |
| `CalendarTaskSerializer` | Task in calendar view: task/goal/dream IDs and titles, schedule, status |

## Celery Tasks

| Task | Schedule | Description |
|------|----------|-------------|
| `generate_recurring_events` | Nightly (Celery beat) | Creates child event instances for the next 2 weeks from recurring parent events. Supports daily, weekly, monthly frequencies with configurable intervals and end dates. |
| `sync_google_calendar` | On-demand + periodic | Bidirectional sync: pushes local events to Google, pulls Google events locally. Uses incremental sync. Retries up to 3 times on failure (60s backoff). |

## Admin

2 models registered with Django admin:

- **CalendarEventAdmin** - Filter by status, start_time, date. Search by title, description, user email, task title. Fieldsets: Basic Info, Timing, Details, Timestamps
- **TimeBlockAdmin** - Filter by block_type, day_of_week, is_active, date. Shows computed `day_name`. Search by user email. Ordered by user, day, time

## Integration with Dreams

When viewing tasks in the calendar, each task includes its parent goal and dream context (IDs and titles). When a CalendarEvent is rescheduled, the linked task's `scheduled_date` is also updated.

## Testing

```bash
pytest apps/calendar/tests.py -v
```

## Configuration

```python
# Google Calendar (required for integration)
GOOGLE_CALENDAR_REDIRECT_URI = 'https://...'

# User preferences used by scheduling
# user.notification_prefs.buffer_minutes -> slot buffer (default: 15)
# user.timezone -> timezone for calculations
# user.work_schedule -> work hours (JSON)
```

## Dependencies

- `python-dateutil` - `relativedelta` for monthly recurrence calculation
- `drf-spectacular` - OpenAPI schema generation
