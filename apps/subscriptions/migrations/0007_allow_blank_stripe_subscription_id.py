from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('subscriptions', '0006_subscription_pending_plan_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='subscription',
            name='stripe_subscription_id',
            field=models.CharField(
                blank=True,
                db_index=True,
                default='',
                help_text='Stripe Subscription ID (sub_xxxxx). Empty for free-tier subscriptions.',
                max_length=255,
            ),
        ),
    ]
