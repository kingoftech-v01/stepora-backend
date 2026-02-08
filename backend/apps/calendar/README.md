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

## Integration with Dreams

When a task is completed:
1. The CalendarEvent status changes to `completed`
2. The underlying Task is marked as completed
3. XP is awarded to the user
4. The streak is updated
