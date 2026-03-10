"""
Seed 18 achievement definitions covering dreams, tasks, streaks, social, and profile.
"""

from django.db import migrations


ACHIEVEMENTS = [
    # ── Dreams ────────────────────────────────────────────────────
    {
        "name": "Dream Starter",
        "description": "Create your very first dream.",
        "icon": "sparkles",
        "category": "dreams",
        "rarity": "common",
        "xp_reward": 25,
        "condition_type": "first_dream",
        "condition_value": 1,
    },
    {
        "name": "Dream Weaver",
        "description": "Create 5 dreams.",
        "icon": "cloud",
        "category": "dreams",
        "rarity": "uncommon",
        "xp_reward": 75,
        "condition_type": "dreams_created",
        "condition_value": 5,
    },
    {
        "name": "Dream Architect",
        "description": "Create 15 dreams.",
        "icon": "building",
        "category": "dreams",
        "rarity": "rare",
        "xp_reward": 200,
        "condition_type": "dreams_created",
        "condition_value": 15,
    },
    {
        "name": "Dream Achiever",
        "description": "Complete your first dream.",
        "icon": "check-circle",
        "category": "dreams",
        "rarity": "uncommon",
        "xp_reward": 100,
        "condition_type": "dreams_completed",
        "condition_value": 1,
    },
    {
        "name": "Dream Master",
        "description": "Complete 10 dreams.",
        "icon": "crown",
        "category": "dreams",
        "rarity": "epic",
        "xp_reward": 500,
        "condition_type": "dreams_completed",
        "condition_value": 10,
    },
    # ── Tasks ─────────────────────────────────────────────────────
    {
        "name": "First Steps",
        "description": "Complete your first 10 tasks.",
        "icon": "footprints",
        "category": "tasks",
        "rarity": "common",
        "xp_reward": 30,
        "condition_type": "tasks_completed",
        "condition_value": 10,
    },
    {
        "name": "Task Crusher",
        "description": "Complete 50 tasks.",
        "icon": "hammer",
        "category": "tasks",
        "rarity": "uncommon",
        "xp_reward": 100,
        "condition_type": "tasks_completed",
        "condition_value": 50,
    },
    {
        "name": "Centurion",
        "description": "Complete 100 tasks.",
        "icon": "shield",
        "category": "tasks",
        "rarity": "rare",
        "xp_reward": 250,
        "condition_type": "tasks_completed",
        "condition_value": 100,
    },
    {
        "name": "Unstoppable Force",
        "description": "Complete 500 tasks.",
        "icon": "rocket",
        "category": "tasks",
        "rarity": "legendary",
        "xp_reward": 1000,
        "condition_type": "tasks_completed",
        "condition_value": 500,
    },
    # ── Streaks ───────────────────────────────────────────────────
    {
        "name": "Week Warrior",
        "description": "Maintain a 7-day streak.",
        "icon": "flame",
        "category": "streaks",
        "rarity": "uncommon",
        "xp_reward": 50,
        "condition_type": "streak_days",
        "condition_value": 7,
    },
    {
        "name": "Monthly Marvel",
        "description": "Maintain a 30-day streak.",
        "icon": "calendar-check",
        "category": "streaks",
        "rarity": "rare",
        "xp_reward": 200,
        "condition_type": "streak_days",
        "condition_value": 30,
    },
    {
        "name": "Hundred Hero",
        "description": "Maintain a 100-day streak.",
        "icon": "zap",
        "category": "streaks",
        "rarity": "epic",
        "xp_reward": 500,
        "condition_type": "streak_days",
        "condition_value": 100,
    },
    {
        "name": "Eternal Flame",
        "description": "Maintain a 365-day streak.",
        "icon": "sun",
        "category": "streaks",
        "rarity": "legendary",
        "xp_reward": 2000,
        "condition_type": "streak_days",
        "condition_value": 365,
    },
    # ── Social ────────────────────────────────────────────────────
    {
        "name": "First Friend",
        "description": "Add your first friend.",
        "icon": "user-plus",
        "category": "social",
        "rarity": "common",
        "xp_reward": 25,
        "condition_type": "friends_count",
        "condition_value": 1,
    },
    {
        "name": "Social Butterfly",
        "description": "Add 10 friends.",
        "icon": "users",
        "category": "social",
        "rarity": "uncommon",
        "xp_reward": 75,
        "condition_type": "friends_count",
        "condition_value": 10,
    },
    {
        "name": "First Post",
        "description": "Create your first social post.",
        "icon": "message-square",
        "category": "social",
        "rarity": "common",
        "xp_reward": 20,
        "condition_type": "posts_created",
        "condition_value": 1,
    },
    {
        "name": "Fan Favourite",
        "description": "Receive 10 likes on your posts or dreams.",
        "icon": "heart",
        "category": "social",
        "rarity": "rare",
        "xp_reward": 150,
        "condition_type": "likes_received",
        "condition_value": 10,
    },
    # ── Profile ───────────────────────────────────────────────────
    {
        "name": "Identity Complete",
        "description": "Fill out every section of your profile.",
        "icon": "user-check",
        "category": "profile",
        "rarity": "uncommon",
        "xp_reward": 50,
        "condition_type": "profile_completed",
        "condition_value": 1,
    },
]


def seed_achievements(apps, schema_editor):
    Achievement = apps.get_model("users", "Achievement")
    for ach_data in ACHIEVEMENTS:
        Achievement.objects.get_or_create(
            name=ach_data["name"],
            defaults=ach_data,
        )


def reverse_seed(apps, schema_editor):
    Achievement = apps.get_model("users", "Achievement")
    names = [a["name"] for a in ACHIEVEMENTS]
    Achievement.objects.filter(name__in=names).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0010_add_rarity_progress_to_achievements"),
    ]

    operations = [
        migrations.RunPython(seed_achievements, reverse_seed),
    ]
