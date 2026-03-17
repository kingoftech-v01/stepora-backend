"""
URL configuration for the SEO module.

Routes:
    /sitemap.xml                  - Dynamic XML sitemap
    /og/<type>/                   - Open Graph preview (app-level)
    /og/<type>/<identifier>/      - Open Graph preview for specific content
    /structured-data/             - JSON-LD structured data
    /robots.txt                   - Robots.txt for API domain
"""

from django.urls import path

from .views import (
    OpenGraphPreviewView,
    RobotsTxtView,
    SitemapView,
    StructuredDataView,
)

urlpatterns = [
    path(
        "sitemap.xml",
        SitemapView.as_view(),
        name="seo-sitemap",
    ),
    path(
        "og/<str:content_type>/",
        OpenGraphPreviewView.as_view(),
        name="seo-og-preview-generic",
    ),
    path(
        "og/<str:content_type>/<str:identifier>/",
        OpenGraphPreviewView.as_view(),
        name="seo-og-preview",
    ),
    path(
        "structured-data/",
        StructuredDataView.as_view(),
        name="seo-structured-data",
    ),
    path(
        "robots.txt",
        RobotsTxtView.as_view(),
        name="seo-robots-txt",
    ),
]
