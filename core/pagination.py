"""
Custom pagination classes for DRF.

StandardLimitOffsetPagination is the project-wide default.
It accepts ?limit= and ?offset= query params, which the frontend
already sends.  Response shape: { count, next, previous, results }.
"""

from rest_framework.pagination import LimitOffsetPagination, PageNumberPagination
from rest_framework.response import Response

# ── Default pagination (used by REST_FRAMEWORK setting) ──────────


class StandardLimitOffsetPagination(LimitOffsetPagination):
    """
    Default pagination for all list endpoints.
    Accepts ?limit=<n>&offset=<n>.
    Falls back to 20 items when no limit is supplied.
    """

    default_limit = 20
    max_limit = 100


class LargeLimitOffsetPagination(LimitOffsetPagination):
    """For endpoints that naturally return larger datasets (feed, messages)."""

    default_limit = 50
    max_limit = 200


# ── Legacy page-number pagination (kept for views that use it) ───


class StandardResultsSetPagination(PageNumberPagination):
    """Page-number pagination with 20 items per page."""

    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100

    def get_paginated_response(self, data):
        return Response(
            {
                "pagination": {
                    "count": self.page.paginator.count,
                    "next": self.get_next_link(),
                    "previous": self.get_previous_link(),
                    "page_size": self.page_size,
                    "current_page": self.page.number,
                    "total_pages": self.page.paginator.num_pages,
                },
                "results": data,
            }
        )


class LargeResultsSetPagination(PageNumberPagination):
    """Page-number pagination for large datasets (50/page)."""

    page_size = 50
    page_size_query_param = "page_size"
    max_page_size = 200
