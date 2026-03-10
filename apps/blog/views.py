"""
Views for the Blog system.

Provides read-only ViewSets for blog posts, categories, and tags.
Posts are publicly accessible (AllowAny) since the blog is a content
marketing channel visible to unauthenticated visitors.
"""

import logging

from django.db.models import F
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.filters import SearchFilter, OrderingFilter
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .models import Category, Tag, Post
from .serializers import (
    CategorySerializer,
    TagSerializer,
    PostListSerializer,
    PostDetailSerializer,
)

logger = logging.getLogger(__name__)


class PostViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read-only ViewSet for blog posts.

    list:
        Returns published posts, filterable by category slug, tag slug,
        and featured flag. Supports search on title and excerpt.

    retrieve:
        Returns a single post by slug and increments the view count.

    search:
        Full-text search across title, excerpt, and content.
    """

    permission_classes = [AllowAny]
    lookup_field = 'slug'
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ['title', 'excerpt']
    ordering_fields = ['published_at', 'views_count', 'read_time_minutes']
    ordering = ['-published_at']

    def get_queryset(self):
        qs = Post.published.select_related('category', 'author').prefetch_related('tags')

        # Filter by category slug
        category_slug = self.request.query_params.get('category')
        if category_slug:
            qs = qs.filter(category__slug=category_slug)

        # Filter by tag slug
        tag_slug = self.request.query_params.get('tag')
        if tag_slug:
            qs = qs.filter(tags__slug=tag_slug)

        # Filter by featured
        featured = self.request.query_params.get('featured')
        if featured is not None:
            qs = qs.filter(featured=featured.lower() in ('true', '1', 'yes'))

        return qs.distinct()

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return PostDetailSerializer
        return PostListSerializer

    def retrieve(self, request, *args, **kwargs):
        """Retrieve a post by slug and increment views atomically."""
        instance = self.get_object()
        Post.objects.filter(pk=instance.pk).update(views_count=F('views_count') + 1)
        instance.refresh_from_db()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], url_path='search')
    def search(self, request):
        """
        Full-text search across published posts.

        Query param: ?q=<search term>
        Searches title, excerpt, and content fields.
        """
        query = request.query_params.get('q', '').strip()
        if not query:
            return Response(
                {'detail': 'Query parameter "q" is required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        qs = (
            Post.published
            .select_related('category', 'author')
            .prefetch_related('tags')
            .filter(
                models_Q_title_excerpt_content(query)
            )
            .distinct()
        )

        page = self.paginate_queryset(qs)
        if page is not None:
            serializer = PostListSerializer(page, many=True, context={'request': request})
            return self.get_paginated_response(serializer.data)

        serializer = PostListSerializer(qs, many=True, context={'request': request})
        return Response(serializer.data)


def models_Q_title_excerpt_content(query):
    """Build a Q filter for searching across title, excerpt, and content."""
    from django.db.models import Q
    return (
        Q(title__icontains=query)
        | Q(excerpt__icontains=query)
        | Q(content__icontains=query)
    )


class CategoryViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read-only ViewSet for blog categories.

    Returns all categories ordered by their display order.
    """

    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [AllowAny]
    pagination_class = None  # Categories are few; return all at once


class TagViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read-only ViewSet for blog tags.

    Returns all tags ordered alphabetically.
    """

    queryset = Tag.objects.all()
    serializer_class = TagSerializer
    permission_classes = [AllowAny]
    pagination_class = None  # Tags are relatively few; return all at once
