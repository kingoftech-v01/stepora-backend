"""
Add event_timezone CharField to CalendarEvent for per-event timezone override.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('calendar', '0015_calendar_share_model'),
    ]

    operations = [
        migrations.AddField(
            model_name='calendarevent',
            name='event_timezone',
            field=models.CharField(
                blank=True,
                default='',
                help_text='Optional timezone override for this event (e.g. America/New_York). Empty = use user home timezone.',
                max_length=50,
            ),
        ),
    ]
