from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("subscriptions", "0011_promotion_system"),
    ]

    operations = [
        migrations.AlterField(
            model_name="promotion",
            name="duration_days",
            field=models.PositiveIntegerField(
                blank=True,
                help_text="How long the discount lasts after redemption (in days). Auto-sets end_date if provided.",
                null=True,
            ),
        ),
        migrations.AlterField(
            model_name="promotion",
            name="end_date",
            field=models.DateTimeField(
                blank=True,
                help_text="When the promotion expires (auto-calculated from start_date + duration_days if left blank)",
                null=True,
            ),
        ),
    ]
