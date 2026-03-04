"""
Add calendar_preferences JSONField to User model.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0014_add_dreamer_type'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='calendar_preferences',
            field=models.JSONField(
                blank=True,
                help_text='Calendar preferences: {buffer_minutes: 0-60, min_event_duration: 15-120}',
                null=True,
            ),
        ),
    ]
