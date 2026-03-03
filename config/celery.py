"""
Celery configuration for DreamPlanner backend.
"""

import os
from celery import Celery
from celery.schedules import crontab

# Set default Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')

app = Celery('dreamplanner')

# Load config from Django settings with namespace CELERY
app.config_from_object('django.conf:settings', namespace='CELERY')

# Auto-discover tasks in all installed apps
app.autodiscover_tasks()

# Periodic tasks schedule
app.conf.beat_schedule = {
    # === Notification Tasks ===

    # Process pending notifications every minute
    'process-pending-notifications': {
        'task': 'apps.notifications.tasks.process_pending_notifications',
        'schedule': 60.0,  # Every 60 seconds
    },

    # Send reminder notifications every 15 minutes
    'send-reminder-notifications': {
        'task': 'apps.notifications.tasks.send_reminder_notifications',
        'schedule': 900.0,  # Every 15 minutes
    },

    # Generate daily motivation at 8 AM
    'generate-daily-motivation': {
        'task': 'apps.notifications.tasks.generate_daily_motivation',
        'schedule': crontab(hour=8, minute=0),
    },

    # Send weekly progress report on Sunday at 10 AM
    'send-weekly-report': {
        'task': 'apps.notifications.tasks.send_weekly_report',
        'schedule': crontab(day_of_week=0, hour=10, minute=0),
    },

    # Check for inactive users daily at 9 AM (Rescue Mode)
    'check-inactive-users': {
        'task': 'apps.notifications.tasks.check_inactive_users',
        'schedule': crontab(hour=9, minute=0),
    },

    # Clean up old notifications weekly on Monday at 2 AM
    'cleanup-old-notifications': {
        'task': 'apps.notifications.tasks.cleanup_old_notifications',
        'schedule': crontab(day_of_week=1, hour=2, minute=0),
    },

    # Expire ringing calls that were not answered within 30 seconds
    'expire-ringing-calls': {
        'task': 'apps.notifications.tasks.expire_ringing_calls',
        'schedule': 15.0,  # Every 15 seconds
    },

    # Check for tasks due in the next 3 minutes and send FCM push
    'check-due-tasks': {
        'task': 'apps.notifications.tasks.check_due_tasks',
        'schedule': 180.0,  # Every 3 minutes
    },

    # === Dream Tasks ===

    # Update dream progress daily at 3 AM
    'update-dream-progress': {
        'task': 'apps.dreams.tasks.update_dream_progress',
        'schedule': crontab(hour=3, minute=0),
    },

    # Check overdue tasks daily at 10 AM
    'check-overdue-tasks': {
        'task': 'apps.dreams.tasks.check_overdue_tasks',
        'schedule': crontab(hour=10, minute=0),
    },

    # Clean up abandoned dreams weekly on Sunday at 3 AM
    'cleanup-abandoned-dreams': {
        'task': 'apps.dreams.tasks.cleanup_abandoned_dreams',
        'schedule': crontab(day_of_week=0, hour=3, minute=0),
    },

    # Smart archive: pause inactive dreams daily at 4 AM
    'smart-archive-dreams': {
        'task': 'apps.dreams.tasks.smart_archive_dreams',
        'schedule': crontab(hour=4, minute=0),
    },

    # === Calendar Tasks ===

    # Generate recurring event instances nightly at 1 AM
    'generate-recurring-events': {
        'task': 'apps.calendar.tasks.generate_recurring_events',
        'schedule': crontab(hour=1, minute=0),
    },

    # === Buddy Tasks ===

    # Send buddy check-in reminders daily at 11 AM
    'send-buddy-checkin-reminders': {
        'task': 'apps.buddies.tasks.send_buddy_checkin_reminders',
        'schedule': crontab(hour=11, minute=0),
    },

    # Expire pending buddy requests daily at 2 AM
    'expire-pending-buddy-requests': {
        'task': 'apps.buddies.tasks.expire_pending_buddy_requests',
        'schedule': crontab(hour=2, minute=0),
    },

    # === League Tasks ===

    # Check if the active season has ended (daily at 12:05 AM)
    'check-season-end': {
        'task': 'apps.leagues.tasks.check_season_end',
        'schedule': crontab(hour=0, minute=5),
    },

    # Create daily rank snapshots at 11:55 PM
    'create-daily-rank-snapshots': {
        'task': 'apps.leagues.tasks.create_daily_rank_snapshots',
        'schedule': crontab(hour=23, minute=55),
    },

    # Weekly promotion/demotion cycle on Sunday at 11 PM
    'weekly-league-promotions': {
        'task': 'apps.leagues.tasks.send_league_change_notifications',
        'schedule': crontab(day_of_week=0, hour=23, minute=0),
    },

    # === User Tasks ===

    # Hard-delete accounts soft-deleted 30+ days ago (GDPR)
    'hard-delete-expired-accounts': {
        'task': 'apps.users.tasks.hard_delete_expired_accounts',
        'schedule': crontab(hour=3, minute=30),
    },
}

# Task configuration
app.conf.task_routes = {
    'apps.notifications.tasks.*': {'queue': 'notifications'},
    'apps.dreams.tasks.*': {'queue': 'dreams'},
    'apps.social.tasks.*': {'queue': 'social'},
    'apps.buddies.tasks.*': {'queue': 'social'},
    'apps.leagues.tasks.*': {'queue': 'social'},
    'apps.circles.tasks.*': {'queue': 'social'},
    'apps.calendar.tasks.*': {'queue': 'dreams'},
    'apps.subscriptions.tasks.*': {'queue': 'notifications'},
    'apps.conversations.tasks.*': {'queue': 'integrations'},
    'apps.users.tasks.*': {'queue': 'notifications'},
    'integrations.*': {'queue': 'integrations'},
}

@app.task(bind=True)
def debug_task(self):
    """Debug task for testing Celery"""
    print(f'Request: {self.request!r}')
