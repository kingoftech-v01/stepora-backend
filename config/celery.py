"""
Celery configuration for Stepora backend.
"""

import os

from celery import Celery
from celery.schedules import crontab

# Set default Django settings
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")

app = Celery("stepora")

# Load config from Django settings with namespace CELERY
app.config_from_object("django.conf:settings", namespace="CELERY")

# Auto-discover tasks in all installed apps
app.autodiscover_tasks()

# Periodic tasks schedule
app.conf.beat_schedule = {
    # === Notification Tasks ===
    # Process pending notifications every minute
    "process-pending-notifications": {
        "task": "apps.notifications.tasks.process_pending_notifications",
        "schedule": 60.0,  # Every 60 seconds
    },
    # Send reminder notifications every 15 minutes
    "send-reminder-notifications": {
        "task": "apps.notifications.tasks.send_reminder_notifications",
        "schedule": 900.0,  # Every 15 minutes
    },
    # Generate daily motivation at 8 AM
    "generate-daily-motivation": {
        "task": "apps.notifications.tasks.generate_daily_motivation",
        "schedule": crontab(hour=8, minute=0),
    },
    # Send weekly progress digest on Monday at 9 AM (email + push)
    "send-weekly-digest": {
        "task": "notifications.send_weekly_digests",
        "schedule": crontab(day_of_week=1, hour=9, minute=0),
    },
    # Check for inactive users daily at 9 AM (Rescue Mode)
    "check-inactive-users": {
        "task": "apps.notifications.tasks.check_inactive_users",
        "schedule": crontab(hour=9, minute=0),
    },
    # Clean up old notifications weekly on Monday at 2 AM
    "cleanup-old-notifications": {
        "task": "apps.notifications.tasks.cleanup_old_notifications",
        "schedule": crontab(day_of_week=1, hour=2, minute=0),
    },
    # Expire ringing calls that were not answered within 30 seconds
    "expire-ringing-calls": {
        "task": "apps.notifications.tasks.expire_ringing_calls",
        "schedule": 15.0,  # Every 15 seconds
    },
    # Check for tasks due in the next 3 minutes and send FCM push
    "check-due-tasks": {
        "task": "apps.notifications.tasks.check_due_tasks",
        "schedule": 180.0,  # Every 3 minutes
    },
    # === Dream Tasks ===
    # Update dream progress daily at 3 AM
    "update-dream-progress": {
        "task": "apps.dreams.tasks.update_dream_progress",
        "schedule": crontab(hour=3, minute=0),
    },
    # Check overdue tasks daily at 10 AM
    "check-overdue-tasks": {
        "task": "apps.dreams.tasks.check_overdue_tasks",
        "schedule": crontab(hour=10, minute=0),
    },
    # Clean up abandoned dreams weekly on Sunday at 3 AM
    "cleanup-abandoned-dreams": {
        "task": "apps.dreams.tasks.cleanup_abandoned_dreams",
        "schedule": crontab(day_of_week=0, hour=3, minute=0),
    },
    # Smart archive: pause inactive dreams daily at 4 AM
    "smart-archive-dreams": {
        "task": "apps.dreams.tasks.smart_archive_dreams",
        "schedule": crontab(hour=4, minute=0),
    },
    # AI check-ins for adaptive plans (runs daily, fans out as needed)
    "run-biweekly-checkins": {
        "task": "apps.dreams.tasks.run_biweekly_checkins",
        "schedule": crontab(hour=6, minute=0),
    },
    # Expire unanswered interactive check-ins and run autonomously
    "expire-stale-checkins": {
        "task": "apps.dreams.tasks.expire_stale_checkins",
        "schedule": crontab(hour="*/4", minute=15),
    },
    # === Calendar Tasks ===
    # Check and send calendar event reminders every minute
    "check-and-send-reminders": {
        "task": "apps.calendar.tasks.check_and_send_reminders",
        "schedule": 60.0,  # Every 60 seconds
    },
    # Generate recurring event instances nightly at 1 AM
    "generate-recurring-events": {
        "task": "apps.calendar.tasks.generate_recurring_events",
        "schedule": crontab(hour=1, minute=0),
    },
    # Send daily morning summary notifications at 7 AM UTC
    "send-daily-summaries": {
        "task": "apps.calendar.tasks.send_daily_summaries",
        "schedule": crontab(hour=7, minute=0),
    },
    # === Buddy Tasks ===
    # Send buddy check-in reminders daily at 11 AM
    "send-buddy-checkin-reminders": {
        "task": "apps.buddies.tasks.send_buddy_checkin_reminders",
        "schedule": crontab(hour=11, minute=0),
    },
    # Expire pending buddy requests daily at 2 AM
    "expire-pending-buddy-requests": {
        "task": "apps.buddies.tasks.expire_pending_buddy_requests",
        "schedule": crontab(hour=2, minute=0),
    },
    # === League Tasks ===
    # Check if the active season has ended (daily at 12:05 AM)
    "check-season-end": {
        "task": "apps.leagues.tasks.check_season_end",
        "schedule": crontab(hour=0, minute=5),
    },
    # Create daily rank snapshots at 11:55 PM
    "create-daily-rank-snapshots": {
        "task": "apps.leagues.tasks.create_daily_rank_snapshots",
        "schedule": crontab(hour=23, minute=55),
    },
    # Weekly promotion/demotion cycle on Sunday at 11 PM
    "weekly-league-promotions": {
        "task": "apps.leagues.tasks.send_league_change_notifications",
        "schedule": crontab(day_of_week=0, hour=23, minute=0),
    },
    # Rebalance league groups weekly on Monday at 3 AM
    "rebalance-league-groups": {
        "task": "apps.leagues.tasks.rebalance_groups_task",
        "schedule": crontab(day_of_week=1, hour=3, minute=0),
    },
    # Auto-activate pending seasons (hourly check)
    "auto-activate-pending-seasons": {
        "task": "apps.leagues.tasks.auto_activate_pending_seasons",
        "schedule": crontab(minute=0),  # Every hour at :00
    },
    # Update all league standings 4x/day (12 AM, 6 AM, 12 PM, 6 PM)
    "update-all-standings": {
        "task": "apps.leagues.tasks.update_all_standings",
        "schedule": crontab(hour="0,6,12,18", minute=0),
    },
    # === Social Tasks ===
    # Expire stories older than 24h (hourly)
    "expire-stories": {
        "task": "apps.social.tasks.expire_stories",
        "schedule": crontab(minute=10),  # Every hour at :10
    },
    # Update social event statuses (every 15 minutes)
    "update-event-statuses": {
        "task": "apps.social.tasks.update_event_statuses",
        "schedule": 900.0,  # Every 15 minutes
    },
    # === Circle Tasks ===
    # Update challenge statuses (hourly)
    "update-challenge-statuses": {
        "task": "apps.circles.tasks.update_challenge_statuses",
        "schedule": crontab(minute=15),  # Every hour at :15
    },
    # Expire pending circle invitations (daily at 2:30 AM)
    "expire-circle-invitations": {
        "task": "apps.circles.tasks.expire_circle_invitations",
        "schedule": crontab(hour=2, minute=30),
    },
    # === Gamification Tasks ===
    # Reset broken streaks and send at-risk notifications daily at midnight UTC
    "check-broken-streaks": {
        "task": "apps.gamification.tasks.check_broken_streaks",
        "schedule": crontab(hour=0, minute=0),
    },
    # === User Tasks ===
    # Hard-delete accounts soft-deleted 30+ days ago (GDPR)
    "hard-delete-expired-accounts": {
        "task": "apps.users.tasks.hard_delete_expired_accounts",
        "schedule": crontab(hour=3, minute=30),
    },
    # Generate weekly progress reports every Sunday at 6 PM UTC
    "generate-weekly-reports": {
        "task": "apps.users.tasks.generate_weekly_reports",
        "schedule": crontab(day_of_week=0, hour=18, minute=0),
    },
    # Send accountability check-in prompts daily at 10 AM
    "send-accountability-checkins": {
        "task": "apps.users.tasks.send_accountability_checkins",
        "schedule": crontab(hour=10, minute=0),
    },
    # === Subscription Tasks ===
    # Send upgrade reminders to active free users (daily at 2 PM)
    "send-free-user-upgrade-reminders": {
        "task": "apps.subscriptions.tasks.send_free_user_upgrade_reminders",
        "schedule": crontab(hour=14, minute=0),
    },
    # === Security Tasks (V-1222, V-1223) ===
    # Check for auth failure anomalies every 15 minutes
    "check-auth-failure-anomalies": {
        "task": "core.tasks.check_auth_failure_anomalies",
        "schedule": 900.0,  # Every 15 minutes
    },
}

# Task configuration
app.conf.task_routes = {
    "core.tasks.*": {"queue": "notifications"},
    "core.auth.tasks.*": {"queue": "notifications"},
    "apps.notifications.tasks.*": {"queue": "notifications"},
    "apps.dreams.tasks.*": {"queue": "dreams"},
    "apps.social.tasks.*": {"queue": "social"},
    "apps.buddies.tasks.*": {"queue": "social"},
    "apps.leagues.tasks.*": {"queue": "social"},
    "apps.circles.tasks.*": {"queue": "social"},
    "apps.calendar.tasks.*": {"queue": "dreams"},
    "apps.subscriptions.tasks.*": {"queue": "notifications"},
    "apps.ai.tasks.*": {"queue": "integrations"},
    "apps.users.tasks.*": {"queue": "notifications"},
    "apps.plans.tasks.*": {"queue": "dreams"},
    "apps.gamification.tasks.*": {"queue": "notifications"},
    "apps.friends.tasks.*": {"queue": "social"},
    "apps.referrals.tasks.*": {"queue": "notifications"},
    "integrations.*": {"queue": "integrations"},
}


@app.task(bind=True)
def debug_task(self):
    """Debug task for testing Celery"""
    print(f"Request: {self.request!r}")
