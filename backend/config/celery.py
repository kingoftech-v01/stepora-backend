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
}

# Task configuration
app.conf.task_routes = {
    'apps.notifications.tasks.*': {'queue': 'notifications'},
    'apps.dreams.tasks.*': {'queue': 'dreams'},
    'integrations.*': {'queue': 'integrations'},
}

@app.task(bind=True)
def debug_task(self):
    """Debug task for testing Celery"""
    print(f'Request: {self.request!r}')
