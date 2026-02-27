# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("notifications", "0007_alter_userdevice_device_name"),
    ]

    operations = [
        migrations.AlterField(
            model_name="notification",
            name="notification_type",
            field=models.CharField(
                choices=[
                    ("reminder", "Reminder"),
                    ("motivation", "Motivation"),
                    ("progress", "Progress"),
                    ("achievement", "Achievement"),
                    ("check_in", "Check In"),
                    ("rescue", "Rescue"),
                    ("buddy", "Buddy"),
                    ("missed_call", "Missed Call"),
                    ("system", "System"),
                    ("dream_completed", "Dream Completed"),
                    ("weekly_report", "Weekly Report"),
                ],
                db_index=True,
                max_length=20,
            ),
        ),
    ]
