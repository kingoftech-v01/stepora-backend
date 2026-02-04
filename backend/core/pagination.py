"""
Custom pagination classes for DRF.
"""

from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response


class StandardResultsSetPagination(PageNumberPagination):
    """Standard pagination with 20 items per page."""
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100

    def get_paginated_response(self, data):
        """Custom paginated response format."""
        return Response({
            'pagination': {
                'count': self.page.paginator.count,
                'next': self.get_next_link(),
                'previous': self.get_previous_link(),
                'page_size': self.page_size,
                'current_page': self.page.number,
                'total_pages': self.page.paginator.num_pages,
            },
            'results': data
        })


class LargeResultsSetPagination(PageNumberPagination):
    """Pagination for large datasets with 50 items per page."""
    page_size = 50
    page_size_query_param = 'page_size'
    max_page_size = 200
