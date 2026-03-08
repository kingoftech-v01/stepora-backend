"""
Data migration: copy rows from allauth tables to dp_auth tables.
Only runs if the allauth tables exist (safe for fresh installs).
"""

from django.db import migrations


def migrate_email_addresses(apps, schema_editor):
    """Copy email addresses from allauth's account_emailaddress table."""
    connection = schema_editor.connection
    with connection.cursor() as cursor:
        # Check if allauth table exists
        cursor.execute(
            "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'account_emailaddress')"
        )
        if not cursor.fetchone()[0]:
            return

        cursor.execute("""
            INSERT INTO dp_auth_email_address (user_id, email, verified, "primary", created_at)
            SELECT user_id, email, verified, "primary", NOW()
            FROM account_emailaddress
            ON CONFLICT (user_id, email) DO NOTHING
        """)


def migrate_social_accounts(apps, schema_editor):
    """Copy social accounts from allauth's socialaccount_socialaccount table."""
    connection = schema_editor.connection
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'socialaccount_socialaccount')"
        )
        if not cursor.fetchone()[0]:
            return

        cursor.execute("""
            INSERT INTO dp_auth_social_account (user_id, provider, uid, extra_data, created_at, last_login)
            SELECT user_id, provider, uid, extra_data,
                   COALESCE(date_joined, NOW()),
                   COALESCE(last_login, NOW())
            FROM socialaccount_socialaccount
            ON CONFLICT (provider, uid) DO NOTHING
        """)


class Migration(migrations.Migration):

    dependencies = [
        ('dp_auth', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(migrate_email_addresses, migrations.RunPython.noop),
        migrations.RunPython(migrate_social_accounts, migrations.RunPython.noop),
    ]
