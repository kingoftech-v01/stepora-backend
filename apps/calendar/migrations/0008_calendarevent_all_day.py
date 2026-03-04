from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('calendar', '0007_calendarevent_google_event_id'),
    ]

    operations = [
        migrations.AddField(
            model_name='calendarevent',
            name='all_day',
            field=models.BooleanField(
                default=False,
                help_text='Whether this is an all-day event.',
            ),
        ),
    ]
