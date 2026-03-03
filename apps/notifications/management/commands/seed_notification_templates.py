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
            {
                'name': 'buddy_message',
                'notification_type': 'buddy',
                'title_template': 'New Buddy Message',
                'body_template': '{buddy_name} sent you a message. Tap to read!',
                'is_active': True,
            },
            {
                'name': 'circle_call',
                'notification_type': 'social',
                'title_template': 'Circle Call Started',
                'body_template': '{caller_name} started a {call_type} call in {circle_name}. Join now!',
                'is_active': True,
            },
            {
                'name': 'circle_message',
                'notification_type': 'social',
                'title_template': 'New Circle Message',
                'body_template': '{sender_name} sent a message in {circle_name}.',
                'is_active': True,
            },
            {
                'name': 'dream_post_like',
                'notification_type': 'social',
                'title_template': 'Someone Liked Your Post',
                'body_template': '{liker_name} liked your dream post. Keep sharing your journey!',
                'is_active': True,
            },
            {
                'name': 'dream_post_comment',
                'notification_type': 'social',
                'title_template': 'New Comment on Your Post',
                'body_template': '{commenter_name} commented: "{comment_preview}"',
                'is_active': True,
            },
            {
                'name': 'dream_post_encouragement',
                'notification_type': 'social',
                'title_template': 'You Received Encouragement!',
                'body_template': '{encourager_name} sent you a "{encouragement_type}" on your dream post!',
                'is_active': True,
            },
            {
                'name': 'dream_post_share',
                'notification_type': 'social',
                'title_template': 'Your Post Was Shared',
                'body_template': '{sharer_name} shared your dream post with their followers!',
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
