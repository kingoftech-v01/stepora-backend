"""
No-op migration: focus_block was already added in 0010_recurrenceexception.

This migration originally duplicated the AddField from 0010. It is now
empty to allow clean migrations from a fresh database.
"""

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('calendar', '0011_timeblocktemplate_presets'),
    ]

    operations = [
        # focus_block field and index already created in 0010
    ]
