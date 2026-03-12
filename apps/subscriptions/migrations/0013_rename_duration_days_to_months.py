from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("subscriptions", "0012_promotion_nullable_end_date_duration"),
    ]

    operations = [
        migrations.RenameField(
            model_name="promotion",
            old_name="duration_days",
            new_name="duration_months",
        ),
        migrations.AlterField(
            model_name="promotion",
            name="duration_months",
            field=models.PositiveIntegerField(
                blank=True,
                help_text="How many months the discount lasts after redemption (e.g. 2, 3, 4 months).",
                null=True,
            ),
        ),
        migrations.AlterField(
            model_name="promotion",
            name="end_date",
            field=models.DateTimeField(
                blank=True,
                help_text="Deadline to redeem the promotion. After this date, users can no longer use it.",
                null=True,
            ),
        ),
    ]
