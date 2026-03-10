"""
Search service layer.

Provides methods that query Elasticsearch and return Django QuerySets
(or lists of IDs) for use in views and serializers.
"""

import logging
from elasticsearch_dsl import Q as ESQ

from apps.search.documents import (
    DreamDocument,
    GoalDocument,
    TaskDocument,
    MessageDocument,
    UserDocument,
    CalendarEventDocument,
    CirclePostDocument,
    CircleChallengeDocument,
    ActivityCommentDocument,
)

logger = logging.getLogger(__name__)

# Maximum results per index in global search
MAX_RESULTS = 50


class SearchService:
    """Elasticsearch-backed search across all Stepora content."""

    @staticmethod
    def search_dreams(user, query, limit=MAX_RESULTS):
        """Search dreams by title/description for a specific user, with DB fallback."""
        try:
            s = DreamDocument.search()
            s = s.filter('term', user_id=str(user.id))
            s = s.query(
                ESQ('multi_match', query=query, fields=['title^2', 'description'], fuzziness='AUTO')
            )
            s = s[:limit]
            response = s.execute()
            return [hit.meta.id for hit in response]
        except Exception as e:
            logger.warning('ES search_dreams failed, falling back to DB: %s', e)
            from apps.dreams.models import Dream
            from django.db.models import Q as DQ
            return list(
                Dream.objects.filter(
                    DQ(title__icontains=query) | DQ(description__icontains=query),
                    user=user,
                ).values_list('id', flat=True)[:limit]
            )

    @staticmethod
    def search_goals(user, query, dream_id=None, limit=MAX_RESULTS):
        """Search goals by title/description."""
        s = GoalDocument.search()
        s = s.filter('term', user_id=str(user.id))
        if dream_id:
            s = s.filter('term', dream_id=str(dream_id))
        s = s.query(
            ESQ('multi_match', query=query, fields=['title^2', 'description'], fuzziness='AUTO')
        )
        s = s[:limit]
        response = s.execute()
        return [hit.meta.id for hit in response]

    @staticmethod
    def search_tasks(user, query, limit=MAX_RESULTS):
        """Search tasks by title/description."""
        s = TaskDocument.search()
        s = s.filter('term', user_id=str(user.id))
        s = s.query(
            ESQ('multi_match', query=query, fields=['title^2', 'description'], fuzziness='AUTO')
        )
        s = s[:limit]
        response = s.execute()
        return [hit.meta.id for hit in response]

    @staticmethod
    def search_messages(user, query, conversation_id=None, limit=MAX_RESULTS):
        """Search messages by content for a specific user."""
        s = MessageDocument.search()
        s = s.filter('term', user_id=str(user.id))
        if conversation_id:
            s = s.filter('term', conversation_id=str(conversation_id))
        s = s.query(ESQ('match', content={'query': query, 'fuzziness': 'AUTO'}))
        s = s.sort('-created_at')
        s = s[:limit]
        response = s.execute()
        return [hit.meta.id for hit in response]

    @staticmethod
    def search_users(query, limit=MAX_RESULTS):
        """Search users by display_name, with DB fallback if ES fails."""
        try:
            s = UserDocument.search()
            s = s.query(ESQ('match', display_name={'query': query, 'fuzziness': 'AUTO'}))
            s = s[:limit]
            response = s.execute()
            return [hit.meta.id for hit in response]
        except Exception as e:
            logger.warning('ES search_users failed, falling back to DB: %s', e)
            from apps.users.models import User
            # Fallback: plain DB query on display_name (works for unencrypted or
            # partially-matching values; limited vs full-text ES search)
            return list(
                User.objects.filter(
                    display_name__icontains=query, is_active=True,
                ).values_list('id', flat=True)[:limit]
            )

    @staticmethod
    def search_calendar(user, query, limit=MAX_RESULTS):
        """Search calendar events by title/description/location."""
        s = CalendarEventDocument.search()
        s = s.filter('term', user_id=str(user.id))
        s = s.query(
            ESQ('multi_match', query=query, fields=['title^2', 'description', 'location'], fuzziness='AUTO')
        )
        s = s[:limit]
        response = s.execute()
        return [hit.meta.id for hit in response]

    @staticmethod
    def search_circle_posts(query, user=None, circle_id=None, limit=MAX_RESULTS):
        """Search circle posts by content, scoped to user's circles."""
        s = CirclePostDocument.search()
        if circle_id:
            s = s.filter('term', circle_id=str(circle_id))
        elif user:
            # Only search posts in circles the user is a member of
            from apps.circles.models import CircleMembership
            user_circle_ids = list(
                CircleMembership.objects.filter(user=user).values_list('circle_id', flat=True)
            )
            if not user_circle_ids:
                return []
            s = s.filter('terms', circle_id=[str(cid) for cid in user_circle_ids])
        s = s.query(ESQ('match', content={'query': query, 'fuzziness': 'AUTO'}))
        s = s[:limit]
        response = s.execute()
        return [hit.meta.id for hit in response]

    @staticmethod
    def search_circle_challenges(query, user=None, circle_id=None, limit=MAX_RESULTS):
        """Search circle challenges by title/description, scoped to user's circles."""
        s = CircleChallengeDocument.search()
        if circle_id:
            s = s.filter('term', circle_id=str(circle_id))
        elif user:
            from apps.circles.models import CircleMembership
            user_circle_ids = list(
                CircleMembership.objects.filter(user=user).values_list('circle_id', flat=True)
            )
            if not user_circle_ids:
                return []
            s = s.filter('terms', circle_id=[str(cid) for cid in user_circle_ids])
        s = s.query(
            ESQ('multi_match', query=query, fields=['title^2', 'description'], fuzziness='AUTO')
        )
        s = s[:limit]
        response = s.execute()
        return [hit.meta.id for hit in response]

    @staticmethod
    def search_activity_comments(user, query, limit=MAX_RESULTS):
        """Search activity comments by text for a specific user."""
        s = ActivityCommentDocument.search()
        s = s.filter('term', user_id=str(user.id))
        s = s.query(ESQ('match', text={'query': query, 'fuzziness': 'AUTO'}))
        s = s[:limit]
        response = s.execute()
        return [hit.meta.id for hit in response]

    @staticmethod
    def global_search(user, query, types=None, limit=10):
        """
        Search across all indexes.

        Args:
            user: The requesting user
            query: Search query string
            types: Optional list of types to search ('dreams', 'goals', 'tasks',
                   'messages', 'users', 'calendar', 'circles',
                   'circle_challenges', 'activity_comments')
            limit: Max results per type

        Returns:
            Dict of {type: [id, ...]} for each searched type.
        """
        if not types:
            types = ['dreams', 'goals', 'tasks', 'messages', 'users', 'calendar', 'circles', 'circle_challenges', 'activity_comments']

        results = {}

        search_map = {
            'dreams': lambda: SearchService.search_dreams(user, query, limit),
            'goals': lambda: SearchService.search_goals(user, query, limit=limit),
            'tasks': lambda: SearchService.search_tasks(user, query, limit),
            'messages': lambda: SearchService.search_messages(user, query, limit=limit),
            'users': lambda: SearchService.search_users(query, limit),
            'calendar': lambda: SearchService.search_calendar(user, query, limit),
            'circles': lambda: SearchService.search_circle_posts(query, user=user, limit=limit),
            'circle_challenges': lambda: SearchService.search_circle_challenges(query, user=user, limit=limit),
            'activity_comments': lambda: SearchService.search_activity_comments(user, query, limit=limit),
        }

        for search_type in types:
            if search_type in search_map:
                try:
                    results[search_type] = search_map[search_type]()
                except Exception as e:
                    logger.warning('Search failed for type=%s: %s', search_type, e)
                    results[search_type] = []

        return results
