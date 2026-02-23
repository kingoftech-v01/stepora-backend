"""Management command to seed notification templates."""

from django.core.management.base import BaseCommand
from apps.notifications.models import NotificationTemplate


class Command(BaseCommand):
    help = 'Seed notification templates for automated notifications'

    def handle(self, *args, **options):
        templates = [
            {
                'name': 'daily_motivation',
                'notification_type': 'motivation',
                'title_template': 'Daily Motivation',
                'body_template': "Keep going, {display_name}! You're on a {streak_days}-day streak. Every step counts toward your dreams.",
                'is_active': True,
            },
            {
                'name': 'streak_milestone',
                'notification_type': 'achievement',
                'title_template': 'Streak Milestone!',
                'body_template': "Amazing! You've reached a {streak_days}-day streak! Your consistency is paying off.",
                'is_active': True,
            },
            {
                'name': 'task_reminder',
                'notification_type': 'reminder',
                'title_template': 'Task Reminder',
                'body_template': "Don't forget: \"{task_title}\" is scheduled for today. You've got this!",
                'is_active': True,
            },
            {
                'name': 'weekly_report',
                'notification_type': 'report',
                'title_template': 'Your Weekly Progress',
                'body_template': 'This week: {tasks_completed} tasks completed, {xp_earned} XP earned. {message}',
                'is_active': True,
            },
            {
                'name': 'achievement_unlocked',
                'notification_type': 'achievement',
                'title_template': 'Achievement Unlocked!',
                'body_template': '{icon} You unlocked "{achievement_name}"! +{xp_reward} XP',
                'is_active': True,
            },
            {
                'name': 'buddy_checkin',
                'notification_type': 'social',
                'title_template': 'Buddy Check-in',
                'body_template': "Your buddy {buddy_name} completed a task today. Send them a message of encouragement!",
                'is_active': True,
            },
        ]

        count = 0
        for t in templates:
            _, created = NotificationTemplate.objects.update_or_create(
                name=t['name'],
                defaults=t,
            )
            action = 'Created' if created else 'Updated'
            self.stdout.write(f'  {action}: {t["name"]}')
            count += 1

        self.stdout.write(self.style.SUCCESS(f'Seeded {count} notification templates.'))
