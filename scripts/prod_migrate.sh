#!/bin/bash
# =============================================================================
# Stepora Production DB Migration — Preserves Users, Resets Everything Else
# =============================================================================
#
# Context:
#   The modular architecture has fresh migrations (36 files across 17 apps).
#   In production, we need to keep user-related data but wipe all other
#   content (dreams, plans, social, notifications, etc.).
#
# What is PRESERVED:
#   - users.User (all user accounts + profiles)
#   - dp_auth.EmailAddress (email verification records)
#   - dp_auth.SocialAccount (Google/Apple OAuth links)
#   - subscriptions.StripeCustomer (Stripe customer mappings)
#   - subscriptions.SubscriptionPlan (plan definitions)
#   - subscriptions.Subscription (user subscription records)
#   - Django auth tables (permissions, groups)
#   - Django admin/sessions/contenttypes
#
# What is WIPED:
#   - ai, buddies, calendar, chat, circles, dreams, friends, gamification,
#     leagues, notifications, plans, referrals, social, store, updates
#
# Usage (via ECS exec):
#   TASK_ID=$(aws ecs list-tasks --cluster stepora --service-name stepora-backend \
#     --query 'taskArns[0]' --output text | awk -F/ '{print $NF}')
#   aws ecs execute-command --cluster stepora --task $TASK_ID \
#     --container backend --interactive --command "bash scripts/prod_migrate.sh"
#
# Safety: Requires explicit confirmation. Creates a JSON backup before any changes.
# =============================================================================

set -e

# --- Colors for output ---
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No color

echo ""
echo "================================================================"
echo "  Stepora Production DB Migration"
echo "  Preserves users + subscriptions, resets everything else"
echo "================================================================"
echo ""

# --- Pre-flight checks ---
if [ -z "$DJANGO_SETTINGS_MODULE" ] && [ -z "$DJANGO_SECRET_KEY" ]; then
    echo -e "${RED}ERROR: Not running in a Django environment.${NC}"
    echo "This script must be run inside the ECS container or with Django env vars set."
    exit 1
fi

# --- Confirmation ---
if [ "$1" != "--yes" ]; then
    echo -e "${YELLOW}WARNING: This will permanently delete all non-user data.${NC}"
    echo ""
    echo "  PRESERVED: users, email addresses, social accounts,"
    echo "             stripe customers, subscription plans, subscriptions"
    echo ""
    echo "  DELETED:   dreams, plans, chat, circles, friends, leagues,"
    echo "             gamification, notifications, social posts, etc."
    echo ""
    read -p "Type 'RESET' to confirm: " CONFIRM
    if [ "$CONFIRM" != "RESET" ]; then
        echo "Aborted."
        exit 0
    fi
fi

BACKUP_DIR="/tmp/stepora_migration_backup"
mkdir -p "$BACKUP_DIR"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# =========================================================================
# Step 1: Backup user-related data
# =========================================================================
echo ""
echo -e "${GREEN}[1/6] Backing up user-related data...${NC}"

python manage.py dumpdata \
    users.User \
    dp_auth.EmailAddress \
    dp_auth.SocialAccount \
    subscriptions.StripeCustomer \
    subscriptions.SubscriptionPlan \
    subscriptions.Subscription \
    auth.Permission \
    auth.Group \
    contenttypes.ContentType \
    --indent 2 \
    --output "$BACKUP_DIR/users_backup_${TIMESTAMP}.json" \
    2>/dev/null || {
        echo -e "${RED}ERROR: dumpdata failed. Aborting.${NC}"
        exit 1
    }

RECORD_COUNT=$(python -c "
import json
data = json.load(open('$BACKUP_DIR/users_backup_${TIMESTAMP}.json'))
print(len(data))
" 2>/dev/null || echo "?")
echo "  Backed up $RECORD_COUNT records to $BACKUP_DIR/users_backup_${TIMESTAMP}.json"

# Count users specifically
USER_COUNT=$(python manage.py shell -c "
from apps.users.models import User
print(User.objects.count())
" 2>/dev/null || echo "?")
echo "  Users: $USER_COUNT"

# =========================================================================
# Step 2: Drop tables for apps being reset (SQL)
# =========================================================================
echo ""
echo -e "${GREEN}[2/6] Dropping tables for non-user apps...${NC}"

python manage.py shell -c "
from django.db import connection
from django.apps import apps

apps_to_wipe = [
    'ai', 'buddies', 'calendar', 'chat', 'circles', 'dreams',
    'friends', 'gamification', 'leagues', 'notifications', 'plans',
    'referrals', 'social', 'store', 'updates',
]

cursor = connection.cursor()

# Get all tables belonging to the apps we want to wipe
tables_to_drop = []
for app_label in apps_to_wipe:
    try:
        app_config = apps.get_app_config(app_label)
        for model in app_config.get_models():
            tables_to_drop.append(model._meta.db_table)
    except LookupError:
        print(f'  WARNING: App {app_label} not found, skipping')

# Also check for django_celery_beat tables (will be recreated by migrate)
existing_tables = connection.introspection.table_names()
celery_beat_tables = [t for t in existing_tables if t.startswith('django_celery_beat')]
tables_to_drop.extend(celery_beat_tables)

# Filter to only tables that actually exist
tables_to_drop = [t for t in tables_to_drop if t in existing_tables]

if tables_to_drop:
    # Disable FK checks, drop tables, re-enable
    cursor.execute('SET CONSTRAINTS ALL DEFERRED;')
    for table in tables_to_drop:
        cursor.execute(f'DROP TABLE IF EXISTS \"{table}\" CASCADE;')
        print(f'  Dropped: {table}')

    # Clear migration records for wiped apps
    for app_label in apps_to_wipe:
        cursor.execute(
            'DELETE FROM django_migrations WHERE app = %s;',
            [app_label]
        )
        print(f'  Cleared migrations: {app_label}')

    # Also clear celery beat migration records
    cursor.execute(
        'DELETE FROM django_migrations WHERE app = %s;',
        ['django_celery_beat']
    )
    print('  Cleared migrations: django_celery_beat')
else:
    print('  No tables to drop (fresh database?)')
"

# =========================================================================
# Step 3: Clear stale content types
# =========================================================================
echo ""
echo -e "${GREEN}[3/6] Clearing stale content types...${NC}"

python manage.py shell -c "
from django.contrib.contenttypes.models import ContentType
apps_to_wipe = [
    'ai', 'buddies', 'calendar', 'chat', 'circles', 'dreams',
    'friends', 'gamification', 'leagues', 'notifications', 'plans',
    'referrals', 'social', 'store', 'updates',
]
deleted_count = ContentType.objects.filter(app_label__in=apps_to_wipe).delete()[0]
print(f'  Removed {deleted_count} stale content types')
"

# =========================================================================
# Step 4: Run fresh migrations
# =========================================================================
echo ""
echo -e "${GREEN}[4/6] Running migrations...${NC}"
python manage.py migrate --noinput

# =========================================================================
# Step 5: Seed reference data
# =========================================================================
echo ""
echo -e "${GREEN}[5/6] Seeding reference data...${NC}"

python manage.py seed_dream_templates 2>/dev/null && echo "  Dream templates seeded" || echo "  seed_dream_templates skipped"
python manage.py seed_leagues 2>/dev/null && echo "  Leagues seeded" || echo "  seed_leagues skipped"

# =========================================================================
# Step 6: Verify
# =========================================================================
echo ""
echo -e "${GREEN}[6/6] Verifying...${NC}"

python manage.py shell -c "
from apps.users.models import User
from core.auth.models import EmailAddress, SocialAccount

user_count = User.objects.count()
email_count = EmailAddress.objects.count()
social_count = SocialAccount.objects.count()

print(f'  Users:           {user_count}')
print(f'  Email addresses: {email_count}')
print(f'  Social accounts: {social_count}')

try:
    from apps.subscriptions.models import StripeCustomer, Subscription, SubscriptionPlan
    print(f'  Stripe customers: {StripeCustomer.objects.count()}')
    print(f'  Plans:            {SubscriptionPlan.objects.count()}')
    print(f'  Subscriptions:    {Subscription.objects.count()}')
except Exception as e:
    print(f'  Subscriptions check error: {e}')
"

echo ""
echo "================================================================"
echo -e "  ${GREEN}Migration complete!${NC}"
echo "  Users and subscriptions preserved. All other data reset."
echo "  Backup saved to: $BACKUP_DIR/users_backup_${TIMESTAMP}.json"
echo "================================================================"
echo ""
