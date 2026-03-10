"""
Add sync_status and last_sync_error fields to CalendarEvent model
for tracking Google Calendar synchronisation state per event.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('calendar', '0012_timeblock_focus_block'),
    ]

    operations = [
        migrations.AddField(
            model_name='calendarevent',
            name='sync_status',
            field=models.CharField(
                choices=[
                    ('local', 'Local only'),
                    ('synced', 'Synced'),
                    ('pending', 'Pending sync'),
                    ('error', 'Sync error'),
                ],
                db_index=True,
                default='local',
                help_text='Google Calendar sync status for this event.',
                max_length=10,
            ),
        ),
        migrations.AddField(
            model_name='calendarevent',
            name='last_sync_error',
            field=models.TextField(
                blank=True,
                default='',
                help_text='Last sync error message, if any.',
            ),
        ),
    ]
