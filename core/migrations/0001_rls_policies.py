"""
Add PostgreSQL Row-Level Security (RLS) policies for critical tables.

Security audit 1015: Data isolation relies entirely on Django ORM queryset
filtering (user=request.user). RLS adds a database-level safety net so that
even direct DB access (admin, ECS exec, debugging) cannot bypass access
controls unless the session variable ``app.current_user_id`` is explicitly set.

IMPORTANT:
- RLS only applies when the session role is the application user (not the
  superuser/rds_superuser). Direct admin connections bypass RLS by design.
- The Django application must SET app.current_user_id on each connection.
  This is handled by the DatabaseRouter / connection middleware.
- These policies are additive (defense-in-depth). The application MUST still
  enforce access control at the ORM/view layer.

Tables covered: dreams, goals, tasks, ai_conversations, ai_messages
"""

from django.db import migrations

# RLS policies for user-owned tables.
# Each policy restricts SELECT/INSERT/UPDATE/DELETE to the row's owner user,
# identified by the session variable app.current_user_id (set per-connection).

ENABLE_RLS_SQL = """
-- Dreams: user_id column
ALTER TABLE dreams ENABLE ROW LEVEL SECURITY;
ALTER TABLE dreams FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS dreams_user_isolation ON dreams;
CREATE POLICY dreams_user_isolation ON dreams
    USING (user_id::text = current_setting('app.current_user_id', TRUE))
    WITH CHECK (user_id::text = current_setting('app.current_user_id', TRUE));

-- Goals: user is via dream -> user_id
-- Goals belong to dreams; enforce that the parent dream belongs to the user.
ALTER TABLE goals ENABLE ROW LEVEL SECURITY;
ALTER TABLE goals FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS goals_user_isolation ON goals;
CREATE POLICY goals_user_isolation ON goals
    USING (
        EXISTS (
            SELECT 1 FROM dreams
            WHERE dreams.id = goals.dream_id
              AND dreams.user_id::text = current_setting('app.current_user_id', TRUE)
        )
    );

-- Tasks: user is via goal -> dream -> user_id
ALTER TABLE tasks ENABLE ROW LEVEL SECURITY;
ALTER TABLE tasks FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tasks_user_isolation ON tasks;
CREATE POLICY tasks_user_isolation ON tasks
    USING (
        EXISTS (
            SELECT 1 FROM goals
            JOIN dreams ON dreams.id = goals.dream_id
            WHERE goals.id = tasks.goal_id
              AND dreams.user_id::text = current_setting('app.current_user_id', TRUE)
        )
    );

-- AI Conversations: user_id column
ALTER TABLE ai_conversations ENABLE ROW LEVEL SECURITY;
ALTER TABLE ai_conversations FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS ai_conversations_user_isolation ON ai_conversations;
CREATE POLICY ai_conversations_user_isolation ON ai_conversations
    USING (user_id::text = current_setting('app.current_user_id', TRUE))
    WITH CHECK (user_id::text = current_setting('app.current_user_id', TRUE));

-- AI Messages: user is via conversation -> user_id
ALTER TABLE ai_messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE ai_messages FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS ai_messages_user_isolation ON ai_messages;
CREATE POLICY ai_messages_user_isolation ON ai_messages
    USING (
        EXISTS (
            SELECT 1 FROM ai_conversations
            WHERE ai_conversations.id = ai_messages.conversation_id
              AND ai_conversations.user_id::text = current_setting('app.current_user_id', TRUE)
        )
    );
"""

DISABLE_RLS_SQL = """
DROP POLICY IF EXISTS dreams_user_isolation ON dreams;
ALTER TABLE dreams DISABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS goals_user_isolation ON goals;
ALTER TABLE goals DISABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS tasks_user_isolation ON tasks;
ALTER TABLE tasks DISABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS ai_conversations_user_isolation ON ai_conversations;
ALTER TABLE ai_conversations DISABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS ai_messages_user_isolation ON ai_messages;
ALTER TABLE ai_messages DISABLE ROW LEVEL SECURITY;
"""


class Migration(migrations.Migration):
    """Add RLS policies for defense-in-depth data isolation."""

    # This migration has no model dependencies — it runs after the tables exist.
    # Use run_before to ensure it runs after the relevant app migrations.
    dependencies = [
        ("dreams", "0002_initial"),
        ("plans", "0001_initial"),
        ("ai", "0001_initial"),
    ]

    operations = [
        migrations.RunSQL(
            sql=ENABLE_RLS_SQL,
            reverse_sql=DISABLE_RLS_SQL,
            state_operations=[],
        ),
    ]
