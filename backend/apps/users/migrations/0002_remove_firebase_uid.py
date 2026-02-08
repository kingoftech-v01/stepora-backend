# Migration to remove firebase_uid field (migrated to django-allauth)

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0001_initial"),
    ]

    operations = [
        migrations.RemoveIndex(
            model_name="user",
            name="users_firebas_361636_idx",
        ),
        migrations.RemoveField(
            model_name="user",
            name="firebase_uid",
        ),
    ]
