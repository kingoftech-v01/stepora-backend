"""Management command to seed achievements."""

from django.core.management.base import BaseCommand
from apps.users.models import Achievement


class Command(BaseCommand):
    help = 'Seed the achievement definitions for the gamification system'

    def handle(self, *args, **options):
        achievements = [
            # Streaks
            {'name': 'Week Warrior', 'description': 'Maintain a 7-day activity streak.', 'icon': 'fire', 'category': 'streaks', 'condition_type': 'streak_days', 'condition_value': 7, 'xp_reward': 50},
            {'name': 'Fortnight Fighter', 'description': 'Maintain a 14-day activity streak.', 'icon': 'flame', 'category': 'streaks', 'condition_type': 'streak_days', 'condition_value': 14, 'xp_reward': 100},
            {'name': 'Month Marathon', 'description': 'Maintain a 30-day activity streak.', 'icon': 'medal', 'category': 'streaks', 'condition_type': 'streak_days', 'condition_value': 30, 'xp_reward': 250},
            {'name': 'Century Streak', 'description': 'Maintain a 100-day activity streak.', 'icon': 'trophy', 'category': 'streaks', 'condition_type': 'streak_days', 'condition_value': 100, 'xp_reward': 1000},
            # Dreams
            {'name': 'First Dream', 'description': 'Create your very first dream.', 'icon': 'star', 'category': 'dreams', 'condition_type': 'first_dream', 'condition_value': 1, 'xp_reward': 25},
            {'name': 'Dream Achiever', 'description': 'Complete 5 dreams.', 'icon': 'crown', 'category': 'dreams', 'condition_type': 'dreams_completed', 'condition_value': 5, 'xp_reward': 200},
            {'name': 'Dream Master', 'description': 'Complete 20 dreams.', 'icon': 'gem', 'category': 'dreams', 'condition_type': 'dreams_completed', 'condition_value': 20, 'xp_reward': 500},
            {'name': 'Visionary', 'description': 'Create a vision board for a dream.', 'icon': 'image', 'category': 'dreams', 'condition_type': 'vision_created', 'condition_value': 1, 'xp_reward': 50},
            # Tasks
            {'name': 'Task Starter', 'description': 'Complete your first task.', 'icon': 'check', 'category': 'tasks', 'condition_type': 'tasks_completed', 'condition_value': 1, 'xp_reward': 10},
            {'name': 'Task Master', 'description': 'Complete 100 tasks.', 'icon': 'zap', 'category': 'tasks', 'condition_type': 'tasks_completed', 'condition_value': 100, 'xp_reward': 300},
            {'name': 'Early Bird', 'description': 'Complete a task before 8am.', 'icon': 'sunrise', 'category': 'tasks', 'condition_type': 'early_task', 'condition_value': 1, 'xp_reward': 25},
            {'name': 'Night Owl', 'description': 'Complete a task after 10pm.', 'icon': 'moon', 'category': 'tasks', 'condition_type': 'late_task', 'condition_value': 1, 'xp_reward': 25},
            # Social
            {'name': 'Social Butterfly', 'description': 'Have 10 friends.', 'icon': 'users', 'category': 'social', 'condition_type': 'friends_count', 'condition_value': 10, 'xp_reward': 100},
            {'name': 'Team Player', 'description': 'Join a dream circle.', 'icon': 'people', 'category': 'social', 'condition_type': 'circles_joined', 'condition_value': 1, 'xp_reward': 50},
            {'name': 'First Buddy', 'description': 'Get matched with an accountability buddy.', 'icon': 'handshake', 'category': 'social', 'condition_type': 'first_buddy', 'condition_value': 1, 'xp_reward': 50},
            # Special
            {'name': 'Level 10', 'description': 'Reach level 10.', 'icon': 'award', 'category': 'special', 'condition_type': 'level_reached', 'condition_value': 10, 'xp_reward': 200},
            {'name': 'XP Hunter', 'description': 'Earn 5,000 total XP.', 'icon': 'target', 'category': 'special', 'condition_type': 'xp_earned', 'condition_value': 5000, 'xp_reward': 500},
        ]

        count = 0
        for ach_data in achievements:
            _, created = Achievement.objects.update_or_create(
                name=ach_data['name'],
                defaults=ach_data,
            )
            action = 'Created' if created else 'Updated'
            self.stdout.write(f'  {action}: {ach_data["icon"]} {ach_data["name"]}')
            count += 1

        self.stdout.write(self.style.SUCCESS(f'Seeded {count} achievements.'))
