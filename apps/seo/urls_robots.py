"""
Root-level robots.txt URL.

Separate from the main SEO urls so it can be mounted at /robots.txt
(crawlers expect this at the domain root, not under /api/).
"""

from django.urls import path

from .views import RobotsTxtView

urlpatterns = [
    path("", RobotsTxtView.as_view(), name="robots-txt-root"),
]
