"""
SEO views for Stepora.

Endpoints:
- /api/seo/sitemap.xml          - Dynamic XML sitemap for public content
- /api/seo/og/<type>/<id>/      - Open Graph metadata for social sharing previews
- /api/seo/structured-data/     - JSON-LD structured data (Organization, WebApplication)
- /api/seo/robots.txt           - Dynamic robots.txt for the API domain
"""

import logging
from xml.etree.ElementTree import Element, SubElement, tostring

from django.conf import settings
from django.http import HttpResponse
from django.utils import timezone
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

logger = logging.getLogger(__name__)

FRONTEND_URL = getattr(settings, "FRONTEND_URL", "https://stepora.app")


class SitemapView(APIView):
    """
    Generate a dynamic XML sitemap for publicly indexable content.

    Includes:
    - Static pages (home, about, pricing, etc.)
    - Blog posts (published)
    - Public circles
    - Public dream posts (if any)

    Returns XML with Content-Type: application/xml.
    """

    permission_classes = [AllowAny]
    throttle_classes = []  # No rate limiting on sitemap

    def get(self, request):
        urlset = Element("urlset")
        urlset.set("xmlns", "http://www.sitemaps.org/schemas/sitemap/0.9")

        now = timezone.now().strftime("%Y-%m-%d")

        # -- Static pages --
        static_pages = [
            {"loc": "/", "changefreq": "weekly", "priority": "1.0"},
            {"loc": "/about", "changefreq": "monthly", "priority": "0.8"},
            {"loc": "/pricing", "changefreq": "monthly", "priority": "0.8"},
            {"loc": "/blog", "changefreq": "daily", "priority": "0.9"},
            {"loc": "/login", "changefreq": "yearly", "priority": "0.3"},
            {"loc": "/register", "changefreq": "yearly", "priority": "0.5"},
        ]

        for page in static_pages:
            url_el = SubElement(urlset, "url")
            SubElement(url_el, "loc").text = f"{FRONTEND_URL}{page['loc']}"
            SubElement(url_el, "lastmod").text = now
            SubElement(url_el, "changefreq").text = page["changefreq"]
            SubElement(url_el, "priority").text = page["priority"]

        # -- Blog posts --
        try:
            from apps.blog.models import Post

            published_posts = Post.published.values_list(
                "slug", "updated_at"
            ).order_by("-published_at")[:1000]

            for slug, updated_at in published_posts:
                url_el = SubElement(urlset, "url")
                SubElement(url_el, "loc").text = f"{FRONTEND_URL}/blog/{slug}"
                SubElement(url_el, "lastmod").text = updated_at.strftime("%Y-%m-%d")
                SubElement(url_el, "changefreq").text = "weekly"
                SubElement(url_el, "priority").text = "0.7"
        except Exception:
            logger.debug("Could not fetch blog posts for sitemap", exc_info=True)

        # -- Blog categories --
        try:
            from apps.blog.models import Category

            for slug in Category.objects.values_list("slug", flat=True):
                url_el = SubElement(urlset, "url")
                SubElement(url_el, "loc").text = (
                    f"{FRONTEND_URL}/blog?category={slug}"
                )
                SubElement(url_el, "changefreq").text = "weekly"
                SubElement(url_el, "priority").text = "0.6"
        except Exception:
            logger.debug("Could not fetch blog categories for sitemap", exc_info=True)

        # -- Public circles --
        try:
            from apps.circles.models import Circle

            public_circles = Circle.objects.filter(is_public=True).values_list(
                "id", "updated_at"
            ).order_by("-created_at")[:500]

            for circle_id, updated_at in public_circles:
                url_el = SubElement(urlset, "url")
                SubElement(url_el, "loc").text = (
                    f"{FRONTEND_URL}/circles/{circle_id}"
                )
                SubElement(url_el, "lastmod").text = updated_at.strftime("%Y-%m-%d")
                SubElement(url_el, "changefreq").text = "weekly"
                SubElement(url_el, "priority").text = "0.5"
        except Exception:
            logger.debug("Could not fetch circles for sitemap", exc_info=True)

        xml_content = tostring(urlset, encoding="unicode", xml_declaration=False)
        xml_output = '<?xml version="1.0" encoding="UTF-8"?>\n' + xml_content

        return HttpResponse(
            xml_output,
            content_type="application/xml",
            headers={
                "Cache-Control": "public, max-age=3600, s-maxage=3600",
                "X-Robots-Tag": "noindex",  # Don't index the sitemap itself
            },
        )


class OpenGraphPreviewView(APIView):
    """
    Return Open Graph metadata for social sharing previews.

    Endpoints:
      GET /api/seo/og/blog/<slug>/
      GET /api/seo/og/circle/<uuid>/
      GET /api/seo/og/dream/<uuid>/
      GET /api/seo/og/profile/<uuid>/
      GET /api/seo/og/app/

    Returns JSON with og:title, og:description, og:image, og:url, og:type
    that the frontend (or a prerender service) can inject into <meta> tags.
    """

    permission_classes = [AllowAny]
    throttle_classes = []

    def get(self, request, content_type, identifier=None):
        handler = {
            "blog": self._og_blog,
            "circle": self._og_circle,
            "dream": self._og_dream,
            "profile": self._og_profile,
            "app": self._og_app,
        }.get(content_type)

        if not handler:
            return Response(
                {"detail": f"Unknown content type: {content_type}"},
                status=400,
            )

        try:
            og_data = handler(identifier)
        except Exception as e:
            logger.warning("OG preview error for %s/%s: %s", content_type, identifier, e)
            og_data = self._og_fallback()

        # Add common OG properties
        og_data.setdefault("og:site_name", "Stepora")
        og_data.setdefault("og:locale", "en_US")
        og_data.setdefault("twitter:card", "summary_large_image")
        og_data.setdefault("twitter:site", "@stepora")

        return Response(
            og_data,
            headers={
                "Cache-Control": "public, max-age=1800, s-maxage=3600",
            },
        )

    def _og_blog(self, slug):
        from apps.blog.models import Post

        post = Post.published.select_related("author", "category").get(slug=slug)
        return {
            "og:title": post.title,
            "og:description": post.excerpt[:200] if post.excerpt else post.title,
            "og:image": post.cover_image or f"{FRONTEND_URL}/og-default.png",
            "og:url": f"{FRONTEND_URL}/blog/{post.slug}",
            "og:type": "article",
            "article:published_time": (
                post.published_at.isoformat() if post.published_at else ""
            ),
            "article:author": post.author.display_name or "Stepora",
            "article:section": post.category.name if post.category else "",
        }

    def _og_circle(self, circle_id):
        from apps.circles.models import Circle

        circle = Circle.objects.get(id=circle_id, is_public=True)
        member_count = circle.member_count
        return {
            "og:title": f"{circle.name} - Dream Circle",
            "og:description": (
                f"Join {member_count} members in this {circle.get_category_display()} circle on Stepora. "
                f"Share goals, track progress, and stay accountable together."
            ),
            "og:image": f"{FRONTEND_URL}/og-circle.png",
            "og:url": f"{FRONTEND_URL}/circles/{circle.id}",
            "og:type": "website",
        }

    def _og_dream(self, dream_id):
        from apps.dreams.models import Dream

        dream = Dream.objects.get(id=dream_id, is_public=True)
        progress = int(dream.progress_percentage)
        return {
            "og:title": f"Dream: {dream.title}",
            "og:description": (
                f"{progress}% complete | Category: {dream.category or 'General'} | "
                f"Track your dreams and goals with Stepora."
            ),
            "og:image": dream.vision_image_url or f"{FRONTEND_URL}/og-dream.png",
            "og:url": f"{FRONTEND_URL}/dreams/{dream.id}",
            "og:type": "website",
        }

    def _og_profile(self, user_id):
        from apps.users.models import User

        user = User.objects.get(id=user_id, profile_visibility="public")
        dream_count = user.dreams.filter(is_public=True).count()
        return {
            "og:title": f"{user.display_name or 'Stepora User'} on Stepora",
            "og:description": (
                f"{user.bio[:150] + '...' if len(user.bio) > 150 else user.bio}"
                if user.bio
                else f"Dreamer with {dream_count} public dreams on Stepora."
            ),
            "og:image": user.avatar_url or f"{FRONTEND_URL}/og-profile.png",
            "og:url": f"{FRONTEND_URL}/profile/{user.id}",
            "og:type": "profile",
        }

    def _og_app(self, _identifier=None):
        return self._og_fallback()

    def _og_fallback(self):
        return {
            "og:title": "Stepora - Turn Dreams Into Plans",
            "og:description": (
                "AI-powered goal management app. Set dreams, get personalized plans, "
                "track progress, and stay accountable with Dream Circles and AI coaching."
            ),
            "og:image": f"{FRONTEND_URL}/og-default.png",
            "og:url": FRONTEND_URL,
            "og:type": "website",
        }


class StructuredDataView(APIView):
    """
    Return JSON-LD structured data for search engine rich results.

    Serves Schema.org types:
    - Organization (for Stepora as a company)
    - WebApplication / SoftwareApplication (for the app itself)

    The frontend or a prerender service injects this as
    <script type="application/ld+json">.
    """

    permission_classes = [AllowAny]
    throttle_classes = []

    def get(self, request):
        schema_type = request.query_params.get("type", "all")

        schemas = []

        if schema_type in ("organization", "all"):
            schemas.append(self._organization_schema())

        if schema_type in ("webapp", "application", "all"):
            schemas.append(self._web_application_schema())

        if schema_type in ("website", "all"):
            schemas.append(self._website_schema())

        return Response(
            {"@context": "https://schema.org", "@graph": schemas}
            if len(schemas) > 1
            else schemas[0]
            if schemas
            else {"detail": "Unknown schema type"},
            headers={
                "Cache-Control": "public, max-age=86400, s-maxage=86400",
            },
        )

    def _organization_schema(self):
        return {
            "@context": "https://schema.org",
            "@type": "Organization",
            "name": "Stepora",
            "url": FRONTEND_URL,
            "logo": f"{FRONTEND_URL}/logo.png",
            "description": (
                "Stepora is an AI-powered dream and goal management platform "
                "that helps users turn their aspirations into actionable plans."
            ),
            "sameAs": [
                "https://twitter.com/stepora",
                "https://www.instagram.com/stepora",
            ],
            "contactPoint": {
                "@type": "ContactPoint",
                "email": "support@stepora.app",
                "contactType": "customer support",
                "availableLanguage": [
                    "English",
                    "French",
                    "Spanish",
                    "German",
                    "Portuguese",
                    "Italian",
                ],
            },
        }

    def _web_application_schema(self):
        return {
            "@context": "https://schema.org",
            "@type": "SoftwareApplication",
            "name": "Stepora",
            "applicationCategory": "LifestyleApplication",
            "operatingSystem": "Web, Android, iOS",
            "url": FRONTEND_URL,
            "description": (
                "AI-powered goal management app with personalized coaching, "
                "Dream Circles, vision boards, and smart scheduling."
            ),
            "offers": [
                {
                    "@type": "Offer",
                    "price": "0",
                    "priceCurrency": "USD",
                    "name": "Free",
                    "description": "Basic goal tracking with up to 3 dreams.",
                },
                {
                    "@type": "Offer",
                    "price": "19.99",
                    "priceCurrency": "USD",
                    "name": "Premium",
                    "description": (
                        "AI coaching, unlimited dreams, Dream Circles, and more."
                    ),
                },
                {
                    "@type": "Offer",
                    "price": "29.99",
                    "priceCurrency": "USD",
                    "name": "Pro",
                    "description": (
                        "Everything in Premium plus AI image generation, "
                        "advanced analytics, and priority support."
                    ),
                },
            ],
            "aggregateRating": {
                "@type": "AggregateRating",
                "ratingValue": "4.8",
                "ratingCount": "150",
                "bestRating": "5",
            },
            "featureList": [
                "AI-powered goal coaching",
                "Personalized action plans",
                "Dream Circles for group accountability",
                "Vision boards",
                "Smart calendar scheduling",
                "Progress tracking and analytics",
                "Push notifications and reminders",
                "Multi-language support (16 languages)",
            ],
        }

    def _website_schema(self):
        return {
            "@context": "https://schema.org",
            "@type": "WebSite",
            "name": "Stepora",
            "url": FRONTEND_URL,
            "description": "Turn your dreams into actionable plans with AI coaching.",
            "potentialAction": {
                "@type": "SearchAction",
                "target": {
                    "@type": "EntryPoint",
                    "urlTemplate": f"{FRONTEND_URL}/blog?q={{search_term_string}}",
                },
                "query-input": "required name=search_term_string",
            },
        }


class RobotsTxtView(APIView):
    """
    Serve a robots.txt for the API domain.

    The API domain (api.stepora.app) should NOT be indexed by search engines.
    Only the sitemap endpoint is referenced so crawlers can find public content
    URLs that point to the frontend domain (stepora.app).
    """

    permission_classes = [AllowAny]
    throttle_classes = []

    def get(self, request):
        api_base = request.build_absolute_uri("/")
        content = (
            "User-agent: *\n"
            "Disallow: /api/\n"
            "Disallow: /stepora-manage/\n"
            "Disallow: /health/\n"
            "\n"
            f"Sitemap: {api_base}api/seo/sitemap.xml\n"
        )
        return HttpResponse(
            content,
            content_type="text/plain",
            headers={
                "Cache-Control": "public, max-age=86400",
                "X-Robots-Tag": "noindex",
            },
        )
