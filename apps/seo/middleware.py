"""
SEO middleware for Stepora.

Adds performance and SEO-related headers to API responses:
- X-Robots-Tag: Controls search engine indexing per endpoint
- Cache-Control: Appropriate caching for static vs dynamic content
- ETag: Conditional responses for bandwidth savings
- Vary: Proper cache key variation
"""

import hashlib
import logging

from django.conf import settings
from django.utils.cache import patch_vary_headers

logger = logging.getLogger(__name__)


class SEOHeadersMiddleware:
    """
    Adds SEO and performance headers to every response.

    Headers added:
    - X-Robots-Tag: noindex for API responses (crawlers should index frontend, not API)
    - Cache-Control: Appropriate caching strategies per content type
    - ETag: Weak ETags for JSON responses to enable conditional requests
    - Vary: Accept-Encoding, Accept-Language for proper CDN/proxy caching
    """

    # Paths that serve public, cacheable content
    PUBLIC_CACHE_PREFIXES = (
        "/api/blog/",
        "/api/seo/",
    )

    # Paths that should be cached aggressively (static-like)
    STATIC_CACHE_PREFIXES = (
        "/static/",
    )

    # Paths that should never be cached
    NO_CACHE_PREFIXES = (
        "/api/auth/",
        "/api/v1/auth/",
        "/stepora-manage/",
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        path = request.path

        # --- X-Robots-Tag ---
        # API domain should not be indexed by search engines.
        # The frontend domain (stepora.app) is what crawlers should index.
        # Exception: sitemap.xml is referenced but should not appear in search.
        if path.startswith("/api/") or path.startswith("/health/"):
            response["X-Robots-Tag"] = "noindex, nofollow"
        elif path.startswith("/stepora-manage/"):
            response["X-Robots-Tag"] = "noindex, nofollow, noarchive"

        # --- Cache-Control ---
        # Only set if not already set by the view
        if "Cache-Control" not in response:
            if any(path.startswith(p) for p in self.NO_CACHE_PREFIXES):
                response["Cache-Control"] = (
                    "no-store, no-cache, must-revalidate, private"
                )
            elif any(path.startswith(p) for p in self.STATIC_CACHE_PREFIXES):
                response["Cache-Control"] = (
                    "public, max-age=31536000, immutable"
                )
            elif any(path.startswith(p) for p in self.PUBLIC_CACHE_PREFIXES):
                response["Cache-Control"] = (
                    "public, max-age=300, s-maxage=600, stale-while-revalidate=60"
                )
            elif path.startswith("/api/"):
                # Authenticated API responses: private, short cache
                response["Cache-Control"] = "private, no-cache"

        # --- ETag (weak) for JSON responses ---
        # Enables 304 Not Modified for bandwidth savings.
        # Only for successful GET responses with content.
        if (
            request.method == "GET"
            and response.status_code == 200
            and response.get("Content-Type", "").startswith("application/json")
            and hasattr(response, "content")
            and len(response.content) > 0
            and "ETag" not in response
        ):
            # Weak ETag based on content hash
            content_hash = hashlib.md5(response.content).hexdigest()  # noqa: S324
            etag = f'W/"{content_hash}"'
            response["ETag"] = etag

            # Check If-None-Match for conditional requests
            if_none_match = request.META.get("HTTP_IF_NONE_MATCH", "")
            if if_none_match == etag:
                response.status_code = 304
                response.content = b""
                # Keep headers but clear content
                if "Content-Length" in response:
                    response["Content-Length"] = "0"

        # --- Vary header ---
        # Ensure CDNs and proxies cache different versions for different
        # encodings and languages
        patch_vary_headers(response, ["Accept-Encoding", "Accept-Language"])

        return response


class CompressionHintMiddleware:
    """
    Ensures Accept-Encoding is properly communicated to upstream proxies.

    WhiteNoise and Django's GZipMiddleware handle actual compression.
    This middleware adds hints for CDNs (CloudFront) and reverse proxies
    (ALB, nginx) to serve compressed content when available.

    Note: Actual gzip/brotli compression is handled by:
    - WhiteNoise: for static files (pre-compressed .gz/.br files)
    - ALB/CloudFront: for dynamic responses (API JSON)
    - django.middleware.gzip.GZipMiddleware: fallback for local dev
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        # Signal to CDN/proxy that content varies by encoding
        patch_vary_headers(response, ["Accept-Encoding"])

        return response
