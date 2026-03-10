"""
Add snoozed_until field to CalendarEvent for snooze-based notification suppression.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('calendar', '0015_calendar_share_model'),
    ]

    operations = [
        migrations.AddField(
            model_name='calendarevent',
            name='snoozed_until',
            field=models.DateTimeField(
                blank=True,
                null=True,
                help_text='If set, suppress in-app notification popups until this datetime.',
            ),
        ),
    ]
