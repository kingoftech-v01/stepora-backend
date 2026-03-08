"""
Add missing feature flag fields and ai_calibration_daily_limit to SubscriptionPlan.

New fields:
- has_store: gating for store purchases
- has_social_feed: gating for activity feed access
- has_circle_create: separate from has_circles (read/join) — gates circle creation
- ai_calibration_daily_limit: was previously hardcoded via getattr fallback
"""

from django.db import migrations, models


def update_existing_plans(apps, schema_editor):
    """Set correct values for new fields on existing plans.

    Also fixes has_circles for premium: previously False (incorrectly), now
    True so premium users can join/read circles (creating still requires pro
    via the new has_circle_create field).
    """
    SubscriptionPlan = apps.get_model('subscriptions', 'SubscriptionPlan')

    # Free plan: no store, no social feed, no circle create, no calibration
    SubscriptionPlan.objects.filter(slug='free').update(
        has_store=False,
        has_social_feed=False,
        has_circle_create=False,
        has_circles=False,
        ai_calibration_daily_limit=0,
    )

    # Premium plan: store + social feed + circles (join only) + calibration
    # NOTE: has_circles intentionally changed from False → True (was incorrect)
    SubscriptionPlan.objects.filter(slug='premium').update(
        has_store=True,
        has_social_feed=True,
        has_circle_create=False,
        has_circles=True,
        ai_calibration_daily_limit=50,
    )

    # Pro plan: everything
    SubscriptionPlan.objects.filter(slug='pro').update(
        has_store=True,
        has_social_feed=True,
        has_circle_create=True,
        has_circles=True,
        ai_calibration_daily_limit=50,
    )


class Migration(migrations.Migration):

    dependencies = [
        ('subscriptions', '0008_referral'),
    ]

    operations = [
        migrations.AddField(
            model_name='subscriptionplan',
            name='has_store',
            field=models.BooleanField(
                default=False,
                help_text='Access to store purchases',
            ),
        ),
        migrations.AddField(
            model_name='subscriptionplan',
            name='has_social_feed',
            field=models.BooleanField(
                default=False,
                help_text='Access to the social activity feed',
            ),
        ),
        migrations.AddField(
            model_name='subscriptionplan',
            name='has_circle_create',
            field=models.BooleanField(
                default=False,
                help_text='Can create new circles (separate from joining)',
            ),
        ),
        migrations.AddField(
            model_name='subscriptionplan',
            name='ai_calibration_daily_limit',
            field=models.IntegerField(
                default=0,
                help_text='Daily calibration questions limit. 0=no access.',
            ),
        ),
        migrations.RunPython(
            update_existing_plans,
            migrations.RunPython.noop,
        ),
    ]
