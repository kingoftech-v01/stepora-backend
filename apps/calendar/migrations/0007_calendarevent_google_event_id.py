from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('calendar', '0006_alter_calendarevent_description_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='calendarevent',
            name='google_event_id',
            field=models.CharField(
                blank=True,
                db_index=True,
                default='',
                help_text='Google Calendar event ID for bidirectional sync.',
                max_length=255,
            ),
        ),
    ]
