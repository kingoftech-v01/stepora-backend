"""
Search service layer.

Provides methods that query Elasticsearch and return lists of IDs.
Every method tries ES first, then falls back to PostgreSQL icontains queries.
"""

import logging

from django.db.models import Q as DQ

logger = logging.getLogger(__name__)

MAX_RESULTS = 50

# Try importing ES — if unavailable, all searches use DB fallback directly.
try:
    from elasticsearch_dsl import Q as ESQ

    from apps.search.documents import (
        ActivityCommentDocument,
        CalendarEventDocument,
        CircleChallengeDocument,
        CirclePostDocument,
        DreamDocument,
        GoalDocument,
        MessageDocument,
        TaskDocument,
        UserDocument,
    )

    _ES_AVAILABLE = True
except Exception:
    _ES_AVAILABLE = False


def _es_search(build_fn, fallback_fn, label):
    """Run *build_fn* (ES query); on any failure run *fallback_fn* (DB query)."""
    if _ES_AVAILABLE:
        try:
            return build_fn()
        except Exception as e:
            logger.warning("ES %s failed, falling back to DB: %s", label, e)
    return fallback_fn()


class SearchService:
    """Search across all Stepora content with ES + DB fallback."""

    # ── Dreams ────────────────────────────────────────────────────────

    @staticmethod
    def search_dreams(user, query, limit=MAX_RESULTS):
        def es():
            s = DreamDocument.search()
            s = s.filter("term", user_id=str(user.id))
            s = s.query(ESQ("multi_match", query=query, fields=["title^2", "description"], fuzziness="AUTO"))
            return [hit.meta.id for hit in s[:limit].execute()]

        def db():
            from apps.dreams.models import Dream

            return list(
                Dream.objects.filter(
                    DQ(title__icontains=query) | DQ(description__icontains=query),
                    user=user,
                ).values_list("id", flat=True)[:limit]
            )

        return _es_search(es, db, "search_dreams")

    # ── Goals ─────────────────────────────────────────────────────────

    @staticmethod
    def search_goals(user, query, dream_id=None, limit=MAX_RESULTS):
        def es():
            s = GoalDocument.search()
            s = s.filter("term", user_id=str(user.id))
            if dream_id:
                s = s.filter("term", dream_id=str(dream_id))
            s = s.query(ESQ("multi_match", query=query, fields=["title^2", "description"], fuzziness="AUTO"))
            return [hit.meta.id for hit in s[:limit].execute()]

        def db():
            from apps.dreams.models import Goal

            qs = Goal.objects.filter(
                DQ(title__icontains=query) | DQ(description__icontains=query),
                dream__user=user,
            )
            if dream_id:
                qs = qs.filter(dream_id=dream_id)
            return list(qs.values_list("id", flat=True)[:limit])

        return _es_search(es, db, "search_goals")

    # ── Tasks ─────────────────────────────────────────────────────────

    @staticmethod
    def search_tasks(user, query, limit=MAX_RESULTS):
        def es():
            s = TaskDocument.search()
            s = s.filter("term", user_id=str(user.id))
            s = s.query(ESQ("multi_match", query=query, fields=["title^2", "description"], fuzziness="AUTO"))
            return [hit.meta.id for hit in s[:limit].execute()]

        def db():
            from apps.dreams.models import Task

            return list(
                Task.objects.filter(
                    DQ(title__icontains=query) | DQ(description__icontains=query),
                    goal__dream__user=user,
                ).values_list("id", flat=True)[:limit]
            )

        return _es_search(es, db, "search_tasks")

    # ── Messages ──────────────────────────────────────────────────────

    @staticmethod
    def search_messages(user, query, conversation_id=None, limit=MAX_RESULTS):
        def es():
            s = MessageDocument.search()
            s = s.filter("term", user_id=str(user.id))
            if conversation_id:
                s = s.filter("term", conversation_id=str(conversation_id))
            s = s.query(ESQ("match", content={"query": query, "fuzziness": "AUTO"}))
            s = s.sort("-created_at")
            return [hit.meta.id for hit in s[:limit].execute()]

        def db():
            from apps.conversations.models import Message

            qs = Message.objects.filter(
                content__icontains=query,
                conversation__user=user,
            )
            if conversation_id:
                qs = qs.filter(conversation_id=conversation_id)
            return list(qs.order_by("-created_at").values_list("id", flat=True)[:limit])

        return _es_search(es, db, "search_messages")

    # ── Users ─────────────────────────────────────────────────────────

    @staticmethod
    def search_users(query, limit=MAX_RESULTS):
        def es():
            s = UserDocument.search()
            s = s.query(ESQ("match", display_name={"query": query, "fuzziness": "AUTO"}))
            return [hit.meta.id for hit in s[:limit].execute()]

        def db():
            from apps.users.models import User

            return list(
                User.objects.filter(
                    display_name__icontains=query,
                    is_active=True,
                ).values_list("id", flat=True)[:limit]
            )

        return _es_search(es, db, "search_users")

    # ── Calendar Events ───────────────────────────────────────────────

    @staticmethod
    def search_calendar(user, query, limit=MAX_RESULTS):
        def es():
            s = CalendarEventDocument.search()
            s = s.filter("term", user_id=str(user.id))
            s = s.query(ESQ("multi_match", query=query, fields=["title^2", "description", "location"], fuzziness="AUTO"))
            return [hit.meta.id for hit in s[:limit].execute()]

        def db():
            from apps.calendar.models import CalendarEvent

            return list(
                CalendarEvent.objects.filter(
                    DQ(title__icontains=query) | DQ(description__icontains=query) | DQ(location__icontains=query),
                    user=user,
                ).values_list("id", flat=True)[:limit]
            )

        return _es_search(es, db, "search_calendar")

    # ── Circle Posts ──────────────────────────────────────────────────

    @staticmethod
    def search_circle_posts(query, user=None, circle_id=None, limit=MAX_RESULTS):
        def es():
            s = CirclePostDocument.search()
            if circle_id:
                s = s.filter("term", circle_id=str(circle_id))
            elif user:
                from apps.circles.models import CircleMembership

                cids = list(CircleMembership.objects.filter(user=user).values_list("circle_id", flat=True))
                if not cids:
                    return []
                s = s.filter("terms", circle_id=[str(c) for c in cids])
            s = s.query(ESQ("match", content={"query": query, "fuzziness": "AUTO"}))
            return [hit.meta.id for hit in s[:limit].execute()]

        def db():
            from apps.circles.models import CircleMembership, CirclePost

            qs = CirclePost.objects.filter(content__icontains=query)
            if circle_id:
                qs = qs.filter(circle_id=circle_id)
            elif user:
                cids = list(CircleMembership.objects.filter(user=user).values_list("circle_id", flat=True))
                if not cids:
                    return []
                qs = qs.filter(circle_id__in=cids)
            return list(qs.values_list("id", flat=True)[:limit])

        return _es_search(es, db, "search_circle_posts")

    # ── Circle Challenges ─────────────────────────────────────────────

    @staticmethod
    def search_circle_challenges(query, user=None, circle_id=None, limit=MAX_RESULTS):
        def es():
            s = CircleChallengeDocument.search()
            if circle_id:
                s = s.filter("term", circle_id=str(circle_id))
            elif user:
                from apps.circles.models import CircleMembership

                cids = list(CircleMembership.objects.filter(user=user).values_list("circle_id", flat=True))
                if not cids:
                    return []
                s = s.filter("terms", circle_id=[str(c) for c in cids])
            s = s.query(ESQ("multi_match", query=query, fields=["title^2", "description"], fuzziness="AUTO"))
            return [hit.meta.id for hit in s[:limit].execute()]

        def db():
            from apps.circles.models import CircleChallenge, CircleMembership

            qs = CircleChallenge.objects.filter(
                DQ(title__icontains=query) | DQ(description__icontains=query),
            )
            if circle_id:
                qs = qs.filter(circle_id=circle_id)
            elif user:
                cids = list(CircleMembership.objects.filter(user=user).values_list("circle_id", flat=True))
                if not cids:
                    return []
                qs = qs.filter(circle_id__in=cids)
            return list(qs.values_list("id", flat=True)[:limit])

        return _es_search(es, db, "search_circle_challenges")

    # ── Activity Comments ─────────────────────────────────────────────

    @staticmethod
    def search_activity_comments(user, query, limit=MAX_RESULTS):
        def es():
            s = ActivityCommentDocument.search()
            s = s.filter("term", user_id=str(user.id))
            s = s.query(ESQ("match", text={"query": query, "fuzziness": "AUTO"}))
            return [hit.meta.id for hit in s[:limit].execute()]

        def db():
            from apps.social.models import ActivityComment

            return list(
                ActivityComment.objects.filter(
                    text__icontains=query,
                    user=user,
                ).values_list("id", flat=True)[:limit]
            )

        return _es_search(es, db, "search_activity_comments")

    # ── Global Search ─────────────────────────────────────────────────

    @staticmethod
    def global_search(user, query, types=None, limit=10):
        if not types:
            types = [
                "dreams", "goals", "tasks", "messages", "users",
                "calendar", "circles", "circle_challenges", "activity_comments",
            ]

        search_map = {
            "dreams": lambda: SearchService.search_dreams(user, query, limit),
            "goals": lambda: SearchService.search_goals(user, query, limit=limit),
            "tasks": lambda: SearchService.search_tasks(user, query, limit),
            "messages": lambda: SearchService.search_messages(user, query, limit=limit),
            "users": lambda: SearchService.search_users(query, limit),
            "calendar": lambda: SearchService.search_calendar(user, query, limit),
            "circles": lambda: SearchService.search_circle_posts(query, user=user, limit=limit),
            "circle_challenges": lambda: SearchService.search_circle_challenges(query, user=user, limit=limit),
            "activity_comments": lambda: SearchService.search_activity_comments(user, query, limit=limit),
        }

        results = {}
        for search_type in types:
            fn = search_map.get(search_type)
            if fn:
                try:
                    results[search_type] = fn()
                except Exception as e:
                    logger.warning("Search failed for type=%s: %s", search_type, e)
                    results[search_type] = []

        return results
