"""
Elasticsearch document classes for DreamPlanner.

Each document maps encrypted Django model fields to searchable ES text fields.
The prepare_<field>() methods read the decrypted value from the model instance
and pass it to Elasticsearch as plaintext for indexing.
"""

from django_elasticsearch_dsl import Document, fields, Index
from django_elasticsearch_dsl.registries import registry

from apps.dreams.models import Dream, Goal, Task
from apps.conversations.models import Message, Conversation, ConversationSummary
from apps.users.models import User
from apps.calendar.models import CalendarEvent
from apps.circles.models import Circle, CirclePost, CircleChallenge
from apps.social.models import ActivityComment


# ── Dream index ────────────────────────────────────────────────────

@registry.register_document
class DreamDocument(Document):
    title = fields.TextField()
    description = fields.TextField()
    user_id = fields.KeywordField()
    status = fields.KeywordField()
    category = fields.KeywordField()

    class Index:
        name = 'dreamplanner_dreams'
        settings = {'number_of_shards': 1, 'number_of_replicas': 0}

    class Django:
        model = Dream
        fields = []

    def prepare_title(self, instance):
        return instance.title or ''

    def prepare_description(self, instance):
        return instance.description or ''

    def prepare_user_id(self, instance):
        return str(instance.user_id)


# ── Goal index ─────────────────────────────────────────────────────

@registry.register_document
class GoalDocument(Document):
    title = fields.TextField()
    description = fields.TextField()
    dream_id = fields.KeywordField()
    user_id = fields.KeywordField()
    status = fields.KeywordField()

    class Index:
        name = 'dreamplanner_goals'
        settings = {'number_of_shards': 1, 'number_of_replicas': 0}

    class Django:
        model = Goal
        fields = []

    def prepare_title(self, instance):
        return instance.title or ''

    def prepare_description(self, instance):
        return instance.description or ''

    def prepare_dream_id(self, instance):
        return str(instance.dream_id)

    def prepare_user_id(self, instance):
        return str(instance.dream.user_id)


# ── Task index ─────────────────────────────────────────────────────

@registry.register_document
class TaskDocument(Document):
    title = fields.TextField()
    description = fields.TextField()
    goal_id = fields.KeywordField()
    user_id = fields.KeywordField()
    status = fields.KeywordField()

    class Index:
        name = 'dreamplanner_tasks'
        settings = {'number_of_shards': 1, 'number_of_replicas': 0}

    class Django:
        model = Task
        fields = []

    def prepare_title(self, instance):
        return instance.title or ''

    def prepare_description(self, instance):
        return instance.description or ''

    def prepare_goal_id(self, instance):
        return str(instance.goal_id)

    def prepare_user_id(self, instance):
        return str(instance.goal.dream.user_id)


# ── Message index ──────────────────────────────────────────────────

@registry.register_document
class MessageDocument(Document):
    content = fields.TextField()
    conversation_id = fields.KeywordField()
    user_id = fields.KeywordField()
    role = fields.KeywordField()
    created_at = fields.DateField()

    class Index:
        name = 'dreamplanner_messages'
        settings = {'number_of_shards': 1, 'number_of_replicas': 0}

    class Django:
        model = Message
        fields = []

    def prepare_content(self, instance):
        return instance.content or ''

    def prepare_conversation_id(self, instance):
        return str(instance.conversation_id)

    def prepare_user_id(self, instance):
        return str(instance.conversation.user_id)

    def prepare_created_at(self, instance):
        return instance.created_at


# ── User index ─────────────────────────────────────────────────────

@registry.register_document
class UserDocument(Document):
    display_name = fields.TextField()
    user_id = fields.KeywordField()

    class Index:
        name = 'dreamplanner_users'
        settings = {'number_of_shards': 1, 'number_of_replicas': 0}

    class Django:
        model = User
        fields = []

    def prepare_display_name(self, instance):
        return instance.display_name or ''

    def prepare_user_id(self, instance):
        return str(instance.id)


# ── Calendar index ─────────────────────────────────────────────────

@registry.register_document
class CalendarEventDocument(Document):
    title = fields.TextField()
    description = fields.TextField()
    location = fields.TextField()
    user_id = fields.KeywordField()
    start_time = fields.DateField()

    class Index:
        name = 'dreamplanner_calendar'
        settings = {'number_of_shards': 1, 'number_of_replicas': 0}

    class Django:
        model = CalendarEvent
        fields = []

    def prepare_title(self, instance):
        return instance.title or ''

    def prepare_description(self, instance):
        return instance.description or ''

    def prepare_location(self, instance):
        return instance.location or ''

    def prepare_user_id(self, instance):
        return str(instance.user_id)

    def prepare_start_time(self, instance):
        return instance.start_time


# ── Circle content index ──────────────────────────────────────────

@registry.register_document
class CirclePostDocument(Document):
    content = fields.TextField()
    circle_id = fields.KeywordField()
    author_id = fields.KeywordField()
    created_at = fields.DateField()

    class Index:
        name = 'dreamplanner_circle_posts'
        settings = {'number_of_shards': 1, 'number_of_replicas': 0}

    class Django:
        model = CirclePost
        fields = []

    def prepare_content(self, instance):
        return instance.content or ''

    def prepare_circle_id(self, instance):
        return str(instance.circle_id)

    def prepare_author_id(self, instance):
        return str(instance.author_id)

    def prepare_created_at(self, instance):
        return instance.created_at


@registry.register_document
class CircleChallengeDocument(Document):
    title = fields.TextField()
    description = fields.TextField()
    circle_id = fields.KeywordField()

    class Index:
        name = 'dreamplanner_circle_challenges'
        settings = {'number_of_shards': 1, 'number_of_replicas': 0}

    class Django:
        model = CircleChallenge
        fields = []

    def prepare_title(self, instance):
        return instance.title or ''

    def prepare_description(self, instance):
        return instance.description or ''

    def prepare_circle_id(self, instance):
        return str(instance.circle_id)


# ── Social (activity comments) index ──────────────────────────────

@registry.register_document
class ActivityCommentDocument(Document):
    text = fields.TextField()
    user_id = fields.KeywordField()
    activity_id = fields.KeywordField()

    class Index:
        name = 'dreamplanner_activity_comments'
        settings = {'number_of_shards': 1, 'number_of_replicas': 0}

    class Django:
        model = ActivityComment
        fields = []

    def prepare_text(self, instance):
        return instance.text or ''

    def prepare_user_id(self, instance):
        return str(instance.user_id)

    def prepare_activity_id(self, instance):
        return str(instance.activity_id)
