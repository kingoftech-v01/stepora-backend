"""
Add notification_timing JSONField to User model for AI-optimized notification scheduling.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0016_user_energy_profile'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='notification_timing',
            field=models.JSONField(
                blank=True,
                help_text=(
                    'AI-optimized notification timing preferences: '
                    '{"optimal_times": [{"notification_type": "reminder", "best_hour": 9, '
                    '"best_day": "weekday", "reason": "..."}], '
                    '"quiet_hours": {"start": 22, "end": 7}, '
                    '"engagement_score": 0.85, '
                    '"last_optimized": "2026-03-01T12:00:00Z"}'
                ),
                null=True,
            ),
        ),
    ]
