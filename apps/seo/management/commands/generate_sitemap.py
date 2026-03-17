"""
Management command to generate a static sitemap XML file.

Usage:
    python manage.py generate_sitemap
    python manage.py generate_sitemap --output /path/to/sitemap.xml

This is useful for:
- Pre-generating sitemaps during deployment
- Uploading to S3/CloudFront for the frontend domain
- Submitting to Google Search Console
"""

import sys
from io import BytesIO
from xml.etree.ElementTree import Element, SubElement, tostring

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone


class Command(BaseCommand):
    help = "Generate a sitemap.xml for public Stepora content."

    def add_arguments(self, parser):
        parser.add_argument(
            "--output",
            type=str,
            default=None,
            help="Output file path (default: stdout)",
        )

    def handle(self, *args, **options):
        frontend_url = getattr(settings, "FRONTEND_URL", "https://stepora.app")
        now = timezone.now().strftime("%Y-%m-%d")

        urlset = Element("urlset")
        urlset.set("xmlns", "http://www.sitemaps.org/schemas/sitemap/0.9")

        count = 0

        # Static pages
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
            SubElement(url_el, "loc").text = f"{frontend_url}{page['loc']}"
            SubElement(url_el, "lastmod").text = now
            SubElement(url_el, "changefreq").text = page["changefreq"]
            SubElement(url_el, "priority").text = page["priority"]
            count += 1

        # Blog posts
        try:
            from apps.blog.models import Post

            posts = Post.published.values_list("slug", "updated_at").order_by(
                "-published_at"
            )[:5000]
            for slug, updated_at in posts:
                url_el = SubElement(urlset, "url")
                SubElement(url_el, "loc").text = f"{frontend_url}/blog/{slug}"
                SubElement(url_el, "lastmod").text = updated_at.strftime("%Y-%m-%d")
                SubElement(url_el, "changefreq").text = "weekly"
                SubElement(url_el, "priority").text = "0.7"
                count += 1
        except Exception as e:
            self.stderr.write(self.style.WARNING(f"Could not fetch blog posts: {e}"))

        # Blog categories
        try:
            from apps.blog.models import Category

            for slug in Category.objects.values_list("slug", flat=True):
                url_el = SubElement(urlset, "url")
                SubElement(url_el, "loc").text = (
                    f"{frontend_url}/blog?category={slug}"
                )
                SubElement(url_el, "changefreq").text = "weekly"
                SubElement(url_el, "priority").text = "0.6"
                count += 1
        except Exception as e:
            self.stderr.write(
                self.style.WARNING(f"Could not fetch blog categories: {e}")
            )

        # Public circles
        try:
            from apps.circles.models import Circle

            circles = Circle.objects.filter(is_public=True).values_list(
                "id", "updated_at"
            ).order_by("-created_at")[:1000]
            for circle_id, updated_at in circles:
                url_el = SubElement(urlset, "url")
                SubElement(url_el, "loc").text = (
                    f"{frontend_url}/circles/{circle_id}"
                )
                SubElement(url_el, "lastmod").text = updated_at.strftime("%Y-%m-%d")
                SubElement(url_el, "changefreq").text = "weekly"
                SubElement(url_el, "priority").text = "0.5"
                count += 1
        except Exception as e:
            self.stderr.write(self.style.WARNING(f"Could not fetch circles: {e}"))

        # Generate XML
        xml_content = tostring(urlset, encoding="unicode", xml_declaration=False)
        xml_output = '<?xml version="1.0" encoding="UTF-8"?>\n' + xml_content

        output_path = options.get("output")
        if output_path:
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(xml_output)
            self.stdout.write(
                self.style.SUCCESS(
                    f"Sitemap written to {output_path} ({count} URLs)"
                )
            )
        else:
            sys.stdout.write(xml_output)
            self.stderr.write(
                self.style.SUCCESS(f"Generated sitemap with {count} URLs")
            )
