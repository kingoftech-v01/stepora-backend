"""
Add focus_block boolean field to TimeBlock model.

Marks a time block as a focus/DND block that suppresses notifications
and integrates with the calendar focus mode system.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('calendar', '0011_timeblocktemplate_presets'),
    ]

    operations = [
        migrations.AddField(
            model_name='timeblock',
            name='focus_block',
            field=models.BooleanField(
                default=False,
                help_text='Whether this time block is a focus/DND block that suppresses notifications.',
            ),
        ),
        migrations.AddIndex(
            model_name='timeblock',
            index=models.Index(
                fields=['user', 'focus_block', 'is_active'],
                name='time_blocks_user_id_focus_idx',
            ),
        ),
    ]
