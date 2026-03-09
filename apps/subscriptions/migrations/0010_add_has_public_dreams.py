from django.db import migrations, models


def seed_has_public_dreams(apps, schema_editor):
    """Set has_public_dreams=True for premium and pro plans."""
    SubscriptionPlan = apps.get_model('subscriptions', 'SubscriptionPlan')
    SubscriptionPlan.objects.filter(slug__in=['premium', 'pro']).update(has_public_dreams=True)


class Migration(migrations.Migration):

    dependencies = [
        ('subscriptions', '0009_add_feature_flags_and_calibration'),
    ]

    operations = [
        migrations.AddField(
            model_name='subscriptionplan',
            name='has_public_dreams',
            field=models.BooleanField(default=False, help_text='Can make dreams publicly visible to other users'),
        ),
        migrations.RunPython(seed_has_public_dreams, migrations.RunPython.noop),
    ]
