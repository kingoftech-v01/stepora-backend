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
    ActivityCommentDocument,
)

logger = logging.getLogger(__name__)

# Maximum results per index in global search
MAX_RESULTS = 50


class SearchService:
    """Elasticsearch-backed search across all DreamPlanner content."""

    @staticmethod
    def search_dreams(user, query, limit=MAX_RESULTS):
        """Search dreams by title/description for a specific user."""
        s = DreamDocument.search()
        s = s.filter('term', user_id=str(user.id))
        s = s.query(
            ESQ('multi_match', query=query, fields=['title^2', 'description'], fuzziness='AUTO')
        )
        s = s[:limit]
        response = s.execute()
        return [hit.meta.id for hit in response]

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
        """Search users by display_name."""
        s = UserDocument.search()
        s = s.query(ESQ('match', display_name={'query': query, 'fuzziness': 'AUTO'}))
        s = s[:limit]
        response = s.execute()
        return [hit.meta.id for hit in response]

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
    def search_circle_posts(query, circle_id=None, limit=MAX_RESULTS):
        """Search circle posts by content."""
        s = CirclePostDocument.search()
        if circle_id:
            s = s.filter('term', circle_id=str(circle_id))
        s = s.query(ESQ('match', content={'query': query, 'fuzziness': 'AUTO'}))
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
                   'messages', 'users', 'calendar', 'circles')
            limit: Max results per type

        Returns:
            Dict of {type: [id, ...]} for each searched type.
        """
        if not types:
            types = ['dreams', 'goals', 'tasks', 'messages', 'users', 'calendar']

        results = {}

        search_map = {
            'dreams': lambda: SearchService.search_dreams(user, query, limit),
            'goals': lambda: SearchService.search_goals(user, query, limit=limit),
            'tasks': lambda: SearchService.search_tasks(user, query, limit),
            'messages': lambda: SearchService.search_messages(user, query, limit=limit),
            'users': lambda: SearchService.search_users(query, limit),
            'calendar': lambda: SearchService.search_calendar(user, query, limit),
            'circles': lambda: SearchService.search_circle_posts(query, limit=limit),
        }

        for search_type in types:
            if search_type in search_map:
                try:
                    results[search_type] = search_map[search_type]()
                except Exception as e:
                    logger.warning('Search failed for type=%s: %s', search_type, e)
                    results[search_type] = []

        return results
