"""
Celery tasks for the Calendar app.

Handles recurring event instance generation and daily summary notifications.
"""

import logging
import random
import zoneinfo
from datetime import timedelta, datetime, time as dt_time
from dateutil.relativedelta import relativedelta

from celery import shared_task
from django.db.models import Q, Count
from django.utils import timezone
from django.utils.translation import gettext as _

from .models import CalendarEvent, TimeBlock

logger = logging.getLogger(__name__)


DAILY_SUMMARY_MESSAGES = [
    "Make today count -- you are building something amazing!",
    "Small steps every day lead to big results.",
    "Today is a new opportunity to move closer to your dreams.",
    "Stay focused, stay determined. You've got this!",
    "Every task you complete is a step towards your dream life.",
    "Your future self will thank you for the effort you put in today.",
    "Progress happens one day at a time. Let's make this one great!",
    "Believe in the power of a productive day.",
]


@shared_task(name='apps.calendar.tasks.send_daily_summaries')
def send_daily_summaries():
    """
    Generate and send daily morning summary notifications.

    Runs daily at 7:00 AM UTC. For each active user with
    daily_summary_enabled preference, gathers today's tasks, events,
    focus blocks, and overdue items, then creates a Notification record
    and sends a push notification via Firebase.
    """
    from apps.users.models import User
    from apps.notifications.models import Notification, UserDevice
    from apps.notifications.fcm_service import FCMService
    from apps.dreams.models import Task

    now = timezone.now()
    users = User.objects.filter(is_active=True)

    fcm = FCMService()
    sent_count = 0
    skipped_count = 0
    fcm_failed = 0

    for user in users.iterator():
        # Check if user has daily_summary_enabled preference
        prefs = user.notification_prefs or {}
        if not prefs.get('daily_summary_enabled', True):
            skipped_count += 1
            continue

        # Determine user's local "today" based on their timezone
        try:
            user_tz = zoneinfo.ZoneInfo(user.timezone)
        except Exception:
            user_tz = zoneinfo.ZoneInfo('UTC')

        user_now = now.astimezone(user_tz)
        user_today = user_now.date()
        day_of_week = user_today.weekday()  # 0=Monday

        # Build day boundaries in UTC for querying
        day_start_local = datetime.combine(user_today, dt_time.min).replace(
            tzinfo=user_tz
        )
        day_end_local = datetime.combine(user_today, dt_time.max).replace(
            tzinfo=user_tz
        )

        # --- Gather today's data ---

        # Tasks scheduled for today
        today_tasks = Task.objects.filter(
            goal__dream__user=user,
            goal__dream__status='active',
            scheduled_date__date=user_today,
        ).select_related('goal__dream')

        task_count = today_tasks.count()
        pending_tasks = today_tasks.filter(status='pending').count()
        completed_tasks = today_tasks.filter(status='completed').count()

        # Calendar events for today
        today_events = CalendarEvent.objects.filter(
            user=user,
            status='scheduled',
            start_time__date=user_today,
        )
        event_count = today_events.count()

        # Focus blocks for today's day of week
        focus_blocks = TimeBlock.objects.filter(
            user=user,
            day_of_week=day_of_week,
            is_active=True,
            focus_block=True,
        )
        focus_block_count = focus_blocks.count()

        # Overdue tasks (pending tasks with scheduled_date before today)
        overdue_tasks = Task.objects.filter(
            goal__dream__user=user,
            goal__dream__status='active',
            status='pending',
            scheduled_date__date__lt=user_today,
        )
        overdue_count = overdue_tasks.count()

        # Skip if user has absolutely nothing scheduled and no overdue items
        if task_count == 0 and event_count == 0 and overdue_count == 0:
            skipped_count += 1
            continue

        # --- Build notification content ---
        display_name = user.display_name or user.email.split('@')[0]
        title = "Good morning, %s!" % display_name

        body_parts = []
        if task_count > 0:
            body_parts.append(
                "%d task%s today" % (task_count, 's' if task_count != 1 else '')
            )
        if event_count > 0:
            body_parts.append(
                "%d event%s" % (event_count, 's' if event_count != 1 else '')
            )
        if focus_block_count > 0:
            body_parts.append(
                "%d focus block%s" % (
                    focus_block_count,
                    's' if focus_block_count != 1 else '',
                )
            )
        if overdue_count > 0:
            body_parts.append(
                "%d overdue" % overdue_count
            )

        body = " | ".join(body_parts)

        motivational_msg = random.choice(DAILY_SUMMARY_MESSAGES)

        data = {
            'screen': 'Calendar',
            'action': 'view_daily_summary',
            'type': 'daily_summary',
            'task_count': str(task_count),
            'event_count': str(event_count),
            'focus_block_count': str(focus_block_count),
            'overdue_count': str(overdue_count),
            'pending_tasks': str(pending_tasks),
            'completed_tasks': str(completed_tasks),
            'motivational_message': motivational_msg,
        }

        # --- Create Notification record ---
        Notification.objects.create(
            user=user,
            notification_type='daily_summary',
            title=title,
            body=body + ". " + motivational_msg,
            scheduled_for=now,
            status='sent',
            sent_at=now,
            data=data,
        )

        # --- Send push notification via FCM ---
        tokens = list(
            UserDevice.objects.filter(user=user, is_active=True)
            .values_list('fcm_token', flat=True)
        )
        if tokens:
            try:
                result = fcm.send_multicast(tokens, title, body, data=data)
                if result.invalid_tokens:
                    UserDevice.objects.filter(
                        fcm_token__in=result.invalid_tokens,
                    ).update(is_active=False)
            except Exception as exc:
                logger.error(
                    'FCM push failed for daily summary (user %s): %s',
                    user.id, exc, exc_info=True,
                )
                fcm_failed += 1

        sent_count += 1

    logger.info(
        'Daily summaries: sent=%d, skipped=%d, fcm_failed=%d.',
        sent_count, skipped_count, fcm_failed,
    )
    return {'sent': sent_count, 'skipped': skipped_count, 'fcm_failed': fcm_failed}


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
                    reminders=parent.reminders or [],
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
    direction = integration.sync_direction

    # --- Push local events to Google ---
    if direction in ('both', 'push_only'):
        from django.db.models import Q

        events_to_push = CalendarEvent.objects.filter(
            user=user,
            status='scheduled',
        )
        if integration.last_sync_at:
            events_to_push = events_to_push.filter(updated_at__gt=integration.last_sync_at)

        # Apply selective sync filters
        synced_ids = integration.synced_dream_ids or []
        push_filter = Q()

        if not integration.sync_tasks:
            # Exclude events linked to tasks
            push_filter &= Q(task__isnull=True)

        if not integration.sync_events:
            # Exclude standalone events (no task link)
            push_filter &= Q(task__isnull=False)

        events_to_push = events_to_push.filter(push_filter)

        # Filter by selected dream IDs when the list is non-empty
        if synced_ids:
            events_to_push = events_to_push.filter(
                Q(task__goal__dream__id__in=synced_ids) | Q(task__isnull=True)
            )

        pushed = 0
        for event in events_to_push:
            try:
                service.push_event(event)
                pushed += 1
            except Exception as e:
                logger.error("Failed to push event %s to Google: %s", event.id, e, exc_info=True)
                event.sync_status = 'error'
                event.last_sync_error = str(e)[:500]
                event.save(update_fields=['sync_status', 'last_sync_error'])
    else:
        pushed = 0

    # --- Pull events from Google ---
    if direction in ('both', 'pull_only'):
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
    else:
        pulled = 0

    logger.info("Google Calendar sync for %s: pushed=%d, pulled=%d", user.email, pushed, pulled)


@shared_task(name='apps.calendar.tasks.check_and_send_reminders')
def check_and_send_reminders():
    """
    Check for calendar event reminders due in the next minute and send
    push notifications. Runs every 60 seconds via Celery beat.

    For each scheduled event, iterates over its `reminders` list (or falls
    back to the legacy `reminder_minutes_before` field). If the reminder
    time falls within the current 60-second window and has not been sent
    yet (tracked via `reminders_sent`), creates a Notification record and
    sends a push notification via FCM.
    """
    from apps.notifications.models import Notification, UserDevice
    from apps.notifications.fcm_service import FCMService

    now = timezone.now()
    window_end = now + timedelta(seconds=60)

    # Look ahead for events starting within the next 28 days (max reminder)
    # to find any that have reminders due right now.
    max_lookahead = now + timedelta(days=28, minutes=1)

    events = CalendarEvent.objects.filter(
        status='scheduled',
        start_time__gt=now,
        start_time__lte=max_lookahead,
    ).select_related('user')

    fcm = FCMService()
    sent_count = 0
    skipped_count = 0

    for event in events.iterator():
        user = event.user
        if not user.is_active:
            continue

        # Skip events that are currently snoozed
        if event.snoozed_until and event.snoozed_until > now:
            skipped_count += 1
            continue

        # Build the effective reminders list: prefer the new JSON field,
        # fall back to the legacy single-value integer field.
        reminders_list = event.reminders or []
        if not reminders_list and event.reminder_minutes_before:
            reminders_list = [
                {"minutes_before": event.reminder_minutes_before, "type": "push"}
            ]

        if not reminders_list:
            continue

        already_sent = list(event.reminders_sent or [])
        new_sends = []

        for reminder in reminders_list:
            minutes_before = reminder.get("minutes_before", 0)
            reminder_type = reminder.get("type", "push")

            # Calculate when this reminder should fire
            reminder_time = event.start_time - timedelta(minutes=minutes_before)

            # Check if reminder_time falls within [now, window_end)
            if not (now <= reminder_time < window_end):
                continue

            # Build a unique key to prevent duplicate sends
            reminder_key = "%d_%s" % (minutes_before, event.start_time.isoformat())

            if reminder_key in already_sent:
                skipped_count += 1
                continue

            # Build human-readable label for the reminder time
            if minutes_before == 0:
                time_label = "now"
            elif minutes_before < 60:
                time_label = "%d min" % minutes_before
            elif minutes_before < 1440:
                hours = minutes_before // 60
                time_label = "%d hr%s" % (hours, 's' if hours != 1 else '')
            else:
                days = minutes_before // 1440
                time_label = "%d day%s" % (days, 's' if days != 1 else '')

            title = _("Reminder: %(event_title)s") % {'event_title': event.title}
            body = _("Starting in %(time)s") % {'time': time_label}

            data = {
                'type': 'event_reminder',
                'notification_type': 'reminder',
                'event_id': str(event.id),
                'screen': 'Calendar',
                'action': 'view_event',
                'minutes_before': str(minutes_before),
            }

            # Create Notification record
            Notification.objects.create(
                user=user,
                notification_type='reminder',
                title=title,
                body=body,
                scheduled_for=now,
                data=data,
            )

            # Send FCM push to all user devices
            if reminder_type == "push":
                tokens = list(
                    UserDevice.objects.filter(user=user, is_active=True)
                    .values_list('fcm_token', flat=True)
                )
                for token in tokens:
                    try:
                        fcm.send_to_token(
                            token=token,
                            title=title,
                            body=body,
                            data=data,
                        )
                    except Exception as e:
                        logger.warning(
                            "FCM send failed for event reminder %s: %s",
                            event.id, e,
                        )

            new_sends.append(reminder_key)
            sent_count += 1

        # Persist sent keys to avoid duplicates on next run
        if new_sends:
            already_sent.extend(new_sends)
            event.reminders_sent = already_sent
            event.save(update_fields=['reminders_sent'])

    if sent_count or skipped_count:
        logger.info(
            "Event reminders: sent=%d, skipped_duplicate=%d",
            sent_count, skipped_count,
        )
    return {'sent': sent_count, 'skipped': skipped_count}
