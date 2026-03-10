"""
Data migration: create 3 default TimeBlockTemplate presets.
"""

from django.db import migrations


PRESET_TEMPLATES = [
    {
        'name': '9-to-5 Worker',
        'description': 'Traditional work schedule with Mon-Fri 9am-5pm work blocks and personal evenings.',
        'blocks': [
            # Monday-Friday: Work 9am-5pm
            {'block_type': 'work', 'day_of_week': 0, 'start_time': '09:00', 'end_time': '17:00'},
            {'block_type': 'work', 'day_of_week': 1, 'start_time': '09:00', 'end_time': '17:00'},
            {'block_type': 'work', 'day_of_week': 2, 'start_time': '09:00', 'end_time': '17:00'},
            {'block_type': 'work', 'day_of_week': 3, 'start_time': '09:00', 'end_time': '17:00'},
            {'block_type': 'work', 'day_of_week': 4, 'start_time': '09:00', 'end_time': '17:00'},
            # Monday-Friday: Personal evenings 18:00-22:00
            {'block_type': 'personal', 'day_of_week': 0, 'start_time': '18:00', 'end_time': '22:00'},
            {'block_type': 'personal', 'day_of_week': 1, 'start_time': '18:00', 'end_time': '22:00'},
            {'block_type': 'personal', 'day_of_week': 2, 'start_time': '18:00', 'end_time': '22:00'},
            {'block_type': 'personal', 'day_of_week': 3, 'start_time': '18:00', 'end_time': '22:00'},
            {'block_type': 'personal', 'day_of_week': 4, 'start_time': '18:00', 'end_time': '22:00'},
        ],
    },
    {
        'name': 'Student Schedule',
        'description': 'Study blocks in the mornings, exercise in the afternoon, and personal time in the evening.',
        'blocks': [
            # Monday-Friday: Study mornings 8am-12pm
            {'block_type': 'work', 'day_of_week': 0, 'start_time': '08:00', 'end_time': '12:00'},
            {'block_type': 'work', 'day_of_week': 1, 'start_time': '08:00', 'end_time': '12:00'},
            {'block_type': 'work', 'day_of_week': 2, 'start_time': '08:00', 'end_time': '12:00'},
            {'block_type': 'work', 'day_of_week': 3, 'start_time': '08:00', 'end_time': '12:00'},
            {'block_type': 'work', 'day_of_week': 4, 'start_time': '08:00', 'end_time': '12:00'},
            # Monday-Friday: Exercise afternoon 14:00-15:30
            {'block_type': 'exercise', 'day_of_week': 0, 'start_time': '14:00', 'end_time': '15:30'},
            {'block_type': 'exercise', 'day_of_week': 1, 'start_time': '14:00', 'end_time': '15:30'},
            {'block_type': 'exercise', 'day_of_week': 2, 'start_time': '14:00', 'end_time': '15:30'},
            {'block_type': 'exercise', 'day_of_week': 3, 'start_time': '14:00', 'end_time': '15:30'},
            {'block_type': 'exercise', 'day_of_week': 4, 'start_time': '14:00', 'end_time': '15:30'},
            # Monday-Friday: Personal evening 19:00-22:00
            {'block_type': 'personal', 'day_of_week': 0, 'start_time': '19:00', 'end_time': '22:00'},
            {'block_type': 'personal', 'day_of_week': 1, 'start_time': '19:00', 'end_time': '22:00'},
            {'block_type': 'personal', 'day_of_week': 2, 'start_time': '19:00', 'end_time': '22:00'},
            {'block_type': 'personal', 'day_of_week': 3, 'start_time': '19:00', 'end_time': '22:00'},
            {'block_type': 'personal', 'day_of_week': 4, 'start_time': '19:00', 'end_time': '22:00'},
        ],
    },
    {
        'name': 'Flexible Freelancer',
        'description': 'Deep work blocks in the morning, meetings midday, and creative time in the afternoon.',
        'blocks': [
            # Monday-Friday: Deep work mornings 7:00-11:00
            {'block_type': 'work', 'day_of_week': 0, 'start_time': '07:00', 'end_time': '11:00'},
            {'block_type': 'work', 'day_of_week': 1, 'start_time': '07:00', 'end_time': '11:00'},
            {'block_type': 'work', 'day_of_week': 2, 'start_time': '07:00', 'end_time': '11:00'},
            {'block_type': 'work', 'day_of_week': 3, 'start_time': '07:00', 'end_time': '11:00'},
            {'block_type': 'work', 'day_of_week': 4, 'start_time': '07:00', 'end_time': '11:00'},
            # Monday-Friday: Meetings/calls midday 12:00-14:00
            {'block_type': 'blocked', 'day_of_week': 0, 'start_time': '12:00', 'end_time': '14:00'},
            {'block_type': 'blocked', 'day_of_week': 1, 'start_time': '12:00', 'end_time': '14:00'},
            {'block_type': 'blocked', 'day_of_week': 2, 'start_time': '12:00', 'end_time': '14:00'},
            {'block_type': 'blocked', 'day_of_week': 3, 'start_time': '12:00', 'end_time': '14:00'},
            {'block_type': 'blocked', 'day_of_week': 4, 'start_time': '12:00', 'end_time': '14:00'},
            # Monday-Friday: Creative afternoon 15:00-18:00
            {'block_type': 'personal', 'day_of_week': 0, 'start_time': '15:00', 'end_time': '18:00'},
            {'block_type': 'personal', 'day_of_week': 1, 'start_time': '15:00', 'end_time': '18:00'},
            {'block_type': 'personal', 'day_of_week': 2, 'start_time': '15:00', 'end_time': '18:00'},
            {'block_type': 'personal', 'day_of_week': 3, 'start_time': '15:00', 'end_time': '18:00'},
            {'block_type': 'personal', 'day_of_week': 4, 'start_time': '15:00', 'end_time': '18:00'},
        ],
    },
]


def create_presets(apps, schema_editor):
    User = apps.get_model('users', 'User')
    TimeBlockTemplate = apps.get_model('calendar', 'TimeBlockTemplate')

    # Get or create a system user for presets
    system_user, _ = User.objects.get_or_create(
        email='system@stepora.app',
        defaults={
            'is_staff': True,
            'is_active': False,
            'display_name': 'System',
        },
    )

    for preset in PRESET_TEMPLATES:
        TimeBlockTemplate.objects.get_or_create(
            name=preset['name'],
            is_preset=True,
            defaults={
                'user': system_user,
                'description': preset['description'],
                'blocks': preset['blocks'],
            },
        )


def remove_presets(apps, schema_editor):
    TimeBlockTemplate = apps.get_model('calendar', 'TimeBlockTemplate')
    TimeBlockTemplate.objects.filter(is_preset=True).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('calendar', '0010_recurrenceexception'),
        ('users', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(create_presets, remove_presets),
    ]
