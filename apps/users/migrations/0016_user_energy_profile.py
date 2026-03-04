"""
Add energy_profile JSONField to User model for energy-based task scheduling.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0015_user_calendar_preferences'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='energy_profile',
            field=models.JSONField(
                blank=True,
                help_text=(
                    'Energy profile for smart scheduling: '
                    '{"peak_hours": [{"start": 9, "end": 12}], '
                    '"low_energy_hours": [{"start": 13, "end": 14}], '
                    '"energy_pattern": "morning_person"|"night_owl"|"steady"}'
                ),
                null=True,
            ),
        ),
    ]
