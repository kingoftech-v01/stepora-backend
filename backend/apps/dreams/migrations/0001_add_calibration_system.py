"""
Migration for adding the calibration question system.

Adds:
- calibration_status field to Dream model
- CalibrationResponse model for storing Q&A pairs
"""

import uuid
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
    ]

    operations = [
        # Add calibration_status field to Dream model
        migrations.AddField(
            model_name='dream',
            name='calibration_status',
            field=models.CharField(
                choices=[
                    ('pending', 'Pending'),
                    ('in_progress', 'In Progress'),
                    ('completed', 'Completed'),
                    ('skipped', 'Skipped'),
                ],
                default='pending',
                help_text='Status of the calibration questionnaire',
                max_length=20,
            ),
        ),
        # Create CalibrationResponse model
        migrations.CreateModel(
            name='CalibrationResponse',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('question', models.TextField(help_text='AI-generated calibration question')),
                ('answer', models.TextField(blank=True, help_text='User response to the question')),
                ('question_number', models.IntegerField(help_text='Order of question in the calibration flow')),
                ('category', models.CharField(
                    blank=True,
                    help_text='Question category: experience, timeline, resources, motivation, constraints, specifics, lifestyle, preferences',
                    max_length=30,
                )),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('dream', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='calibration_responses',
                    to='dreams.dream',
                )),
            ],
            options={
                'db_table': 'calibration_responses',
                'ordering': ['dream', 'question_number'],
                'indexes': [
                    models.Index(fields=['dream', 'question_number'], name='calibration_dream_qnum_idx'),
                ],
            },
        ),
    ]
