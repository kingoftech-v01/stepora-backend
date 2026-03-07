from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0009_update_unique_constraints'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='persona',
            field=models.JSONField(
                blank=True,
                help_text='User persona for AI calibration: {available_hours_per_week, preferred_schedule, budget_range, fitness_level, learning_style, typical_day, occupation, astrological_sign, global_motivation, global_constraints}',
                null=True,
            ),
        ),
    ]
