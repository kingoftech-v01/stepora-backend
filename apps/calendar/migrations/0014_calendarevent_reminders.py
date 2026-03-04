"""
Add reminders JSONField and reminders_sent JSONField to CalendarEvent
for supporting multiple custom notification timings per event.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('calendar', '0013_calendarevent_sync_status'),
    ]

    operations = [
        migrations.AddField(
            model_name='calendarevent',
            name='reminders',
            field=models.JSONField(
                blank=True,
                default=list,
                help_text='List of reminders: [{minutes_before: int, type: "push"|"email"}]',
            ),
        ),
        migrations.AddField(
            model_name='calendarevent',
            name='reminders_sent',
            field=models.JSONField(
                blank=True,
                default=list,
                help_text='List of reminder keys already sent, e.g. ["15_2026-03-04T10:00:00"]',
            ),
        ),
    ]
