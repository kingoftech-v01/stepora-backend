"""
Celery tasks for the Calendar app.

Handles recurring event instance generation.
"""

import logging
from datetime import timedelta
from dateutil.relativedelta import relativedelta

from celery import shared_task
from django.utils import timezone

from .models import CalendarEvent

logger = logging.getLogger(__name__)


@shared_task(name='apps.calendar.tasks.generate_recurring_events')
def generate_recurring_events():
    """
    Generate instances of recurring events for the next 2 weeks.

    Runs nightly via Celery beat. For each recurring parent event,
    creates child instances based on the recurrence_rule JSON.
    """
    now = timezone.now()
    horizon = now + timedelta(days=14)

    parent_events = CalendarEvent.objects.filter(
        is_recurring=True,
        recurrence_rule__isnull=False,
        status='scheduled',
        parent_event__isnull=True,  # Only top-level recurring events
    ).select_related('user', 'task')

    total_created = 0

    for parent in parent_events:
        rule = parent.recurrence_rule
        if not rule:
            continue

        frequency = rule.get('frequency', 'weekly')
        interval = rule.get('interval', 1)
        end_date_str = rule.get('end_date')

        # Determine recurrence end
        recurrence_end = horizon
        if end_date_str:
            try:
                from datetime import datetime
                parsed_end = datetime.fromisoformat(end_date_str.replace('Z', '+00:00'))
                if parsed_end < recurrence_end:
                    recurrence_end = parsed_end
            except (ValueError, TypeError):
                pass

        # Find the latest existing instance to know where to continue from
        latest_instance = CalendarEvent.objects.filter(
            parent_event=parent
        ).order_by('-start_time').first()

        if latest_instance:
            last_start = latest_instance.start_time
        else:
            last_start = parent.start_time

        # Calculate event duration
        duration = parent.end_time - parent.start_time

        # Generate next instances
        current = last_start
        while True:
            current = _next_occurrence(current, frequency, interval)

            if current > recurrence_end:
                break

            if current <= now:
                continue

            # Check if instance already exists at this time
            exists = CalendarEvent.objects.filter(
                parent_event=parent,
                start_time=current,
            ).exists()

            if not exists:
                CalendarEvent.objects.create(
                    user=parent.user,
                    task=parent.task,
                    title=parent.title,
                    description=parent.description,
                    start_time=current,
                    end_time=current + duration,
                    location=parent.location,
                    reminder_minutes_before=parent.reminder_minutes_before,
                    status='scheduled',
                    is_recurring=False,
                    parent_event=parent,
                )
                total_created += 1

    logger.info("Generated %d recurring event instances", total_created)
    return total_created


def _next_occurrence(current, frequency, interval):
    """Calculate the next occurrence based on frequency and interval."""
    if frequency == 'daily':
        return current + timedelta(days=interval)
    elif frequency == 'weekly':
        return current + timedelta(weeks=interval)
    elif frequency == 'monthly':
        return current + relativedelta(months=interval)
    else:
        return current + timedelta(weeks=interval)


@shared_task(bind=True, max_retries=3)
def sync_google_calendar(self, integration_id):
    """
    Bidirectional sync with Google Calendar.

    1. Push new/updated DreamPlanner events to Google.
    2. Pull new/updated events from Google Calendar.
    """
    from .models import GoogleCalendarIntegration
    from integrations.google_calendar import GoogleCalendarService
    from datetime import datetime as dt

    try:
        integration = GoogleCalendarIntegration.objects.select_related('user').get(
            id=integration_id, sync_enabled=True,
        )
    except GoogleCalendarIntegration.DoesNotExist:
        logger.warning("Integration %s not found or disabled", integration_id)
        return

    service = GoogleCalendarService(integration=integration)
    user = integration.user

    # --- Push local events to Google ---
    # Events modified since last sync that don't have a google_event_id yet
    events_to_push = CalendarEvent.objects.filter(
        user=user,
        status='scheduled',
    )
    if integration.last_sync_at:
        events_to_push = events_to_push.filter(updated_at__gt=integration.last_sync_at)

    pushed = 0
    for event in events_to_push:
        try:
            service.push_event(event)
            pushed += 1
        except Exception as e:
            logger.error("Failed to push event %s to Google: %s", event.id, e)

    # --- Pull events from Google ---
    try:
        google_events = service.pull_events()
    except Exception as e:
        logger.error("Failed to pull events from Google for %s: %s", user.email, e)
        raise self.retry(exc=e, countdown=60)

    pulled = 0
    for ge in google_events:
        if ge.get('status') == 'cancelled':
            continue

        start = ge.get('start', {})
        end = ge.get('end', {})

        start_str = start.get('dateTime') or start.get('date')
        end_str = end.get('dateTime') or end.get('date')
        if not start_str or not end_str:
            continue

        try:
            start_dt = dt.fromisoformat(start_str.replace('Z', '+00:00'))
            end_dt = dt.fromisoformat(end_str.replace('Z', '+00:00'))
        except (ValueError, TypeError):
            continue

        # Upsert by google_event_id field
        google_id = ge['id']
        existing = CalendarEvent.objects.filter(
            user=user,
            google_event_id=google_id,
        ).first()

        if existing:
            existing.title = ge.get('summary', 'Untitled')
            existing.description = ge.get('description', '')
            existing.start_time = start_dt
            existing.end_time = end_dt
            existing.location = ge.get('location', '')
            existing.save(update_fields=[
                'title', 'description', 'start_time', 'end_time', 'location', 'updated_at'
            ])
        else:
            CalendarEvent.objects.create(
                user=user,
                title=ge.get('summary', 'Untitled'),
                description=ge.get('description', ''),
                start_time=start_dt,
                end_time=end_dt,
                location=ge.get('location', ''),
                status='scheduled',
                google_event_id=google_id,
            )
            pulled += 1

    logger.info("Google Calendar sync for %s: pushed=%d, pulled=%d", user.email, pushed, pulled)
