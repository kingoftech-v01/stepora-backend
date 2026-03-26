"""
Add consent_accepted_at, consent_version, and date_of_birth fields to User model.

Security audit fixes:
- V-333: GDPR consent not recorded with timestamp/version
- V-343: No age verification / COPPA compliance
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="consent_accepted_at",
            field=models.DateTimeField(
                blank=True,
                help_text="Timestamp when the user accepted terms of service and privacy policy.",
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="user",
            name="consent_version",
            field=models.CharField(
                blank=True,
                default="",
                help_text="Version of the terms/privacy policy the user accepted (e.g. '2026-03-26').",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="user",
            name="date_of_birth",
            field=models.DateField(
                blank=True,
                help_text="Date of birth for age verification (COPPA compliance: must be 13+).",
                null=True,
            ),
        ),
    ]
