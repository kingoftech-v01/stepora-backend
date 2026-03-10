"""
URL configuration for the Blog system.

Routes:
    /posts/                    - List published posts (filterable)
    /posts/<slug>/             - Retrieve a single post by slug
    /posts/search/?q=<query>   - Full-text search across posts
    /categories/               - List all categories
    /tags/                     - List all tags
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import CategoryViewSet, PostViewSet, TagViewSet

router = DefaultRouter()
router.register(r"posts", PostViewSet, basename="blog-post")
router.register(r"categories", CategoryViewSet, basename="blog-category")
router.register(r"tags", TagViewSet, basename="blog-tag")

urlpatterns = [
    path("", include(router.urls)),
]
