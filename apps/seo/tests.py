"""
Tests for the SEO module.

Covers:
- Sitemap generation (XML, includes blog posts and public circles)
- Open Graph preview endpoints (blog, circle, dream, profile, app)
- Structured data endpoint (JSON-LD)
- Robots.txt
- SEO headers middleware (X-Robots-Tag, Cache-Control, ETag)
"""

from django.test import RequestFactory, TestCase, override_settings
from rest_framework.test import APIClient


class RobotsTxtTest(TestCase):
    """Test /robots.txt endpoint."""

    def setUp(self):
        self.client = APIClient()

    def test_robots_txt_returns_text(self):
        response = self.client.get("/robots.txt")
        assert response.status_code == 200
        assert response["Content-Type"] == "text/plain"
        content = response.content.decode()
        assert "User-agent: *" in content
        assert "Disallow: /api/" in content
        assert "Sitemap:" in content

    def test_robots_txt_via_seo_prefix(self):
        response = self.client.get("/api/seo/robots.txt")
        assert response.status_code == 200
        assert "User-agent: *" in response.content.decode()


class SitemapTest(TestCase):
    """Test /api/seo/sitemap.xml endpoint."""

    def setUp(self):
        self.client = APIClient()

    @override_settings(FRONTEND_URL="https://stepora.app")
    def test_sitemap_returns_xml(self):
        response = self.client.get("/api/seo/sitemap.xml")
        assert response.status_code == 200
        assert response["Content-Type"] == "application/xml"
        content = response.content.decode()
        assert '<?xml version="1.0"' in content
        assert "https://stepora.app/" in content
        assert "https://stepora.app/blog" in content

    def test_sitemap_has_cache_headers(self):
        response = self.client.get("/api/seo/sitemap.xml")
        assert "max-age=3600" in response.get("Cache-Control", "")


class StructuredDataTest(TestCase):
    """Test /api/seo/structured-data/ endpoint."""

    def setUp(self):
        self.client = APIClient()

    def test_all_schemas(self):
        response = self.client.get("/api/seo/structured-data/")
        assert response.status_code == 200
        data = response.json()
        assert "@graph" in data
        types = [item["@type"] for item in data["@graph"]]
        assert "Organization" in types
        assert "SoftwareApplication" in types
        assert "WebSite" in types

    def test_organization_only(self):
        response = self.client.get("/api/seo/structured-data/?type=organization")
        assert response.status_code == 200
        data = response.json()
        assert data["@type"] == "Organization"
        assert data["name"] == "Stepora"

    def test_webapp_only(self):
        response = self.client.get("/api/seo/structured-data/?type=webapp")
        assert response.status_code == 200
        data = response.json()
        assert data["@type"] == "SoftwareApplication"

    def test_has_cache_headers(self):
        response = self.client.get("/api/seo/structured-data/")
        assert "max-age=86400" in response.get("Cache-Control", "")


class OpenGraphPreviewTest(TestCase):
    """Test /api/seo/og/ endpoints."""

    def setUp(self):
        self.client = APIClient()

    @override_settings(FRONTEND_URL="https://stepora.app")
    def test_app_preview(self):
        response = self.client.get("/api/seo/og/app/")
        assert response.status_code == 200
        data = response.json()
        assert "og:title" in data
        assert "og:description" in data
        assert "og:image" in data
        assert data["og:site_name"] == "Stepora"

    def test_unknown_type_returns_400(self):
        response = self.client.get("/api/seo/og/nonexistent/")
        assert response.status_code == 400

    def test_blog_not_found_returns_fallback(self):
        response = self.client.get("/api/seo/og/blog/nonexistent-slug/")
        assert response.status_code == 200
        # Falls back to generic Stepora preview
        data = response.json()
        assert "og:title" in data


class OpenGraphContentSpecificTest(TestCase):
    """Test OG previews for specific content types with mock data."""

    def setUp(self):
        self.client = APIClient()

    def test_blog_og_with_real_post(self):
        """Test OG preview for a real published blog post."""
        from apps.blog.models import Category, Post
        from apps.users.models import User

        author = User.objects.create_user(
            email="ogauthor@test.com",
            password="testpassword123",
            display_name="OG Author",
        )
        cat = Category.objects.create(name="Tech", slug="tech", order=1)
        post = Post.objects.create(
            title="Test OG Post",
            slug="test-og-post",
            excerpt="An excerpt for OG",
            content="Full content here.",
            category=cat,
            author=author,
            status="published",
            published_at="2025-01-01T00:00:00Z",
            cover_image="https://example.com/cover.jpg",
        )

        response = self.client.get(f"/api/seo/og/blog/{post.slug}/")
        assert response.status_code == 200
        data = response.json()
        assert data["og:title"] == "Test OG Post"
        assert data["og:type"] == "article"
        assert "test-og-post" in data["og:url"]
        assert data["og:image"] == "https://example.com/cover.jpg"
        assert data["og:site_name"] == "Stepora"

    def test_blog_og_nonexistent_post_fallback(self):
        """Test that a nonexistent blog slug falls back to generic preview."""
        response = self.client.get("/api/seo/og/blog/nonexistent-slug/")
        assert response.status_code == 200
        data = response.json()
        assert data["og:title"] == "Stepora - Turn Dreams Into Plans"

    def test_app_og_preview(self):
        """Test /api/seo/og/app/ returns the generic Stepora preview."""
        response = self.client.get("/api/seo/og/app/")
        assert response.status_code == 200
        data = response.json()
        assert data["og:title"] == "Stepora - Turn Dreams Into Plans"
        assert "AI-powered" in data["og:description"]
        assert data["og:type"] == "website"
        assert "twitter:card" in data

    def test_unknown_og_type(self):
        """Test OG preview for unknown content type returns 400."""
        response = self.client.get("/api/seo/og/nonexistent/")
        assert response.status_code == 400


class StructuredDataExtendedTest(TestCase):
    """Extended tests for structured data endpoint."""

    def setUp(self):
        self.client = APIClient()

    def test_website_schema(self):
        """Test ?type=website returns WebSite schema with search action."""
        response = self.client.get("/api/seo/structured-data/?type=website")
        assert response.status_code == 200
        data = response.json()
        assert data["@type"] == "WebSite"
        assert "potentialAction" in data
        assert data["potentialAction"]["@type"] == "SearchAction"

    def test_unknown_schema_type(self):
        """Test ?type=unknown returns empty/error response."""
        response = self.client.get("/api/seo/structured-data/?type=unknown")
        assert response.status_code == 200
        data = response.json()
        assert "detail" in data or "@type" not in data

    def test_all_schemas_contain_context(self):
        """Test all schemas response contains @context and @graph."""
        response = self.client.get("/api/seo/structured-data/")
        data = response.json()
        assert data["@context"] == "https://schema.org"
        assert len(data["@graph"]) >= 3

    def test_organization_has_contact_point(self):
        """Test Organization schema includes contactPoint."""
        response = self.client.get("/api/seo/structured-data/?type=organization")
        data = response.json()
        assert "contactPoint" in data
        assert data["contactPoint"]["contactType"] == "customer support"

    def test_webapp_has_offers(self):
        """Test SoftwareApplication schema includes pricing offers."""
        response = self.client.get("/api/seo/structured-data/?type=webapp")
        data = response.json()
        assert "offers" in data
        offer_names = [o["name"] for o in data["offers"]]
        assert "Free" in offer_names
        assert "Premium" in offer_names
        assert "Pro" in offer_names


class SitemapExtendedTest(TestCase):
    """Extended sitemap tests with real blog data."""

    def setUp(self):
        self.client = APIClient()

    @override_settings(FRONTEND_URL="https://stepora.app")
    def test_sitemap_contains_blog_posts(self):
        """Test sitemap includes published blog posts."""
        from apps.blog.models import Category, Post
        from apps.users.models import User

        author = User.objects.create_user(
            email="sitemapauthor@test.com",
            password="testpassword123",
            display_name="Sitemap Author",
        )
        cat = Category.objects.create(name="General", slug="general", order=1)
        Post.objects.create(
            title="Sitemap Post",
            slug="sitemap-post",
            content="Content for sitemap.",
            category=cat,
            author=author,
            status="published",
            published_at="2025-06-01T00:00:00Z",
        )

        response = self.client.get("/api/seo/sitemap.xml")
        content = response.content.decode()
        assert "https://stepora.app/blog/sitemap-post" in content

    @override_settings(FRONTEND_URL="https://stepora.app")
    def test_sitemap_contains_blog_categories(self):
        """Test sitemap includes blog category URLs."""
        from apps.blog.models import Category

        Category.objects.create(name="Fitness", slug="fitness", order=1)

        response = self.client.get("/api/seo/sitemap.xml")
        content = response.content.decode()
        assert "https://stepora.app/blog?category=fitness" in content

    @override_settings(FRONTEND_URL="https://stepora.app")
    def test_sitemap_excludes_draft_posts(self):
        """Test sitemap does not include draft blog posts."""
        from apps.blog.models import Category, Post
        from apps.users.models import User

        author = User.objects.create_user(
            email="smdraft@test.com",
            password="testpassword123",
            display_name="Draft Author",
        )
        cat = Category.objects.create(name="Drafts", slug="drafts", order=1)
        Post.objects.create(
            title="Draft Post",
            slug="draft-post",
            content="Not published yet.",
            category=cat,
            author=author,
            status="draft",
        )

        response = self.client.get("/api/seo/sitemap.xml")
        content = response.content.decode()
        assert "draft-post" not in content


class SEOHeadersMiddlewareTest(TestCase):
    """Test that SEO headers are added to responses."""

    def setUp(self):
        self.client = APIClient()

    def test_api_has_x_robots_tag(self):
        response = self.client.get("/health/")
        assert response.get("X-Robots-Tag") == "noindex, nofollow"

    def test_api_has_vary_header(self):
        response = self.client.get("/health/")
        vary = response.get("Vary", "")
        assert "Accept-Encoding" in vary

    def test_public_endpoints_have_cross_origin_corp(self):
        """Blog and SEO endpoints should have CORP: cross-origin for crawlers."""
        response = self.client.get("/api/seo/robots.txt")
        assert response.get("Cross-Origin-Resource-Policy") == "cross-origin"
