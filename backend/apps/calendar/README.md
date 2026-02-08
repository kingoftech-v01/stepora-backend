# Calendar App

Django application for calendar management and scheduling.

## Overview

The Calendar app manages task scheduling:
- **CalendarEvent** - Calendar event
- **TimeBlock** - Recurring time blocks (preferences)

## Models

### CalendarEvent

| Field | Type | Description |
|-------|------|-------------|
| id | UUID | Unique identifier |
| user | FK(User) | Owner |
| task | FK(Task) | Associated task (optional) |
| title | CharField(255) | Event title |
| description | TextField | Description |
| start_time | DateTime | Start |
| end_time | DateTime | End |
| location | CharField(255) | Location/context |
| reminder_minutes_before | Integer | Reminder before (minutes) |
| status | CharField | scheduled, completed, cancelled, rescheduled |
| recurrence_rule | CharField | iCal RRULE string for recurring events (e.g., `FREQ=WEEKLY;BYDAY=MO,WE,FR`) |
| parent_event | FK(CalendarEvent) | Parent event for recurring event instances (nullable, self-referential) |

### GoogleCalendarIntegration

OAuth2 integration for bidirectional Google Calendar sync.

| Field | Type | Description |
|-------|------|-------------|
| id | UUID | Unique identifier |
| user | OneToOne(User) | Linked user |
| google_calendar_id | CharField | Google Calendar ID |
| access_token | TextField | Encrypted OAuth2 access token |
| refresh_token | TextField | Encrypted OAuth2 refresh token |
| token_expiry | DateTime | Token expiration timestamp |
| sync_enabled | Boolean | Whether sync is active |
| last_synced_at | DateTime | Last successful sync timestamp |

### TimeBlock

| Field | Type | Description |
|-------|------|-------------|
| id | UUID | Unique identifier |
| user | FK(User) | Owner |
| block_type | CharField | Block type |
| day_of_week | Integer | 0=Monday, 6=Sunday |
| start_time | TimeField | Start time |
| end_time | TimeField | End time |
| is_active | Boolean | Active block |

**Block types:**
- `work` - Work
- `personal` - Personal
- `family` - Family
- `exercise` - Exercise
- `blocked` - Blocked (unavailable)

## API Endpoints

### Events
- `GET /api/calendar/` - List events
- `GET /api/calendar/?date=2024-01-15` - Events for a specific day
- `GET /api/calendar/?start=2024-01-01&end=2024-01-31` - Date range
- `POST /api/calendar/` - Create an event
- `GET /api/calendar/{id}/` - Detail
- `PUT /api/calendar/{id}/` - Update
- `DELETE /api/calendar/{id}/` - Delete
- `POST /api/calendar/{id}/reschedule/` - Reschedule

### Special Views
- `GET /api/calendar/today/` - Today's events
- `GET /api/calendar/week/` - This week's events
- `GET /api/calendar/overdue/` - Overdue tasks
- `POST /api/calendar/auto-schedule/` - Automatic scheduling
- `GET /api/calendar/conflicts/` - Detect scheduling conflicts
- `GET /api/calendar/suggest-slots/` - Smart time slot suggestions based on availability and preferences
- `GET /api/calendar/ical-feed/` - Export calendar as iCal feed (subscribable URL)

### Google Calendar Integration
- `POST /api/calendar/google/connect/` - Initiate Google Calendar OAuth2 flow
- `POST /api/calendar/google/callback/` - Handle OAuth2 callback
- `POST /api/calendar/google/sync/` - Trigger bidirectional sync
- `DELETE /api/calendar/google/disconnect/` - Disconnect Google Calendar integration

### Time Blocks
- `GET /api/time-blocks/` - List blocks
- `POST /api/time-blocks/` - Create a block
- `PUT /api/time-blocks/{id}/` - Update
- `DELETE /api/time-blocks/{id}/` - Delete

## Serializers

- `CalendarEventSerializer` - Full event with task
- `CalendarEventListSerializer` - List version
- `TimeBlockSerializer` - Time block

## Smart Scheduling

Auto-scheduling takes into account:
1. **TimeBlocks** - Respects availability blocks
2. **User preferences** - Work hours from profile
3. **Task duration** - Does not exceed available blocks
4. **Priority** - Schedules high-priority tasks first
5. **Deadlines** - Respects dream deadlines

## Scheduling Algorithm

```python
def auto_schedule_tasks(user, tasks):
    1. Retrieve active TimeBlocks
    2. For each day in the range:
       - Identify available slots
       - Filter unscheduled tasks
       - Assign tasks to slots
    3. Create corresponding CalendarEvents
```

## Testing

```bash
# Unit tests
python manage.py test apps.calendar

# With coverage
pytest apps/calendar/tests.py -v --cov=apps.calendar
```

## Configuration

Scheduling uses user preferences:
- `work_schedule` - Work hours (JSON)
- `timezone` - Timezone for calculations

## Celery Tasks

| Task | Description |
|------|-------------|
| `generate_recurring_events` | Creates future event instances from recurrence rules. Runs on a schedule to ensure recurring events are always populated ahead of time |
| `sync_google_calendar` | Performs bidirectional sync with Google Calendar for all users with active integrations |

## Integration with Dreams

When a task is completed:
1. The CalendarEvent status changes to `completed`
2. The underlying Task is marked as completed
3. XP is awarded to the user
4. The streak is updated
