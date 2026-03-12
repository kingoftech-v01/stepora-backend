import uuid
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("subscriptions", "0013_rename_duration_days_to_months"),
    ]

    operations = [
        migrations.CreateModel(
            name="PromotionChangeLog",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "action",
                    models.CharField(
                        choices=[
                            ("coupon_created", "Coupon Created"),
                            ("coupon_recreated", "Coupon Recreated"),
                            ("coupon_deleted", "Coupon Deleted"),
                            ("promotion_updated", "Promotion Updated"),
                        ],
                        max_length=30,
                    ),
                ),
                (
                    "old_stripe_coupon_id",
                    models.CharField(blank=True, default="", max_length=255),
                ),
                (
                    "new_stripe_coupon_id",
                    models.CharField(blank=True, default="", max_length=255),
                ),
                (
                    "details",
                    models.JSONField(
                        blank=True,
                        default=dict,
                        help_text="Snapshot of changed values",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "promotion",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="change_logs",
                        to="subscriptions.promotion",
                    ),
                ),
                (
                    "plan_discount",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="change_logs",
                        to="subscriptions.promotionplandiscount",
                    ),
                ),
            ],
            options={
                "db_table": "promotion_change_logs",
                "ordering": ["-created_at"],
            },
        ),
    ]
