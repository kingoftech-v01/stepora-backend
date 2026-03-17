"""
Serializers for the Blog system.

These serializers handle blog posts, categories, and tags.
List serializers omit the full content body to keep payloads small;
detail serializers include everything.
"""

from rest_framework import serializers

from .models import Category, Post, Tag


class CategorySerializer(serializers.ModelSerializer):
    """Serializer for blog categories."""

    class Meta:
        model = Category
        fields = [
            "id",
            "name",
            "slug",
            "description",
            "icon",
            "order",
        ]
        read_only_fields = fields


class TagSerializer(serializers.ModelSerializer):
    """Serializer for blog tags."""

    class Meta:
        model = Tag
        fields = [
            "id",
            "name",
            "slug",
        ]
        read_only_fields = fields


class PostListSerializer(serializers.ModelSerializer):
    """
    Serializer for blog post list views.

    Omits the full content body to keep list payloads lightweight.
    Includes author info, category, and tags.
    """

    category = CategorySerializer(read_only=True)
    tags = TagSerializer(many=True, read_only=True)
    author = serializers.SerializerMethodField()
    published_at = serializers.DateTimeField(read_only=True)
    read_time_minutes = serializers.IntegerField(read_only=True)
    cover_image = serializers.URLField(read_only=True)

    class Meta:
        model = Post
        fields = [
            "id",
            "title",
            "slug",
            "excerpt",
            "category",
            "tags",
            "author",
            "cover_image",
            "published_at",
            "read_time_minutes",
            "featured",
        ]
        read_only_fields = fields

    def get_author(self, obj) -> dict:
        """Return the author's public profile info."""
        return {
            "id": str(obj.author.id),
            "name": obj.author.display_name or "Anonymous",
            "avatar": obj.author.get_effective_avatar_url(),
        }


class PostDetailSerializer(PostListSerializer):
    """
    Serializer for blog post detail views.

    Extends the list serializer with full content, view count, and SEO metadata.
    The ``seo`` field provides Open Graph and JSON-LD data that the frontend
    can inject into ``<meta>`` and ``<script type="application/ld+json">`` tags
    for rich social sharing previews and search engine structured data.
    """

    views_count = serializers.IntegerField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)
    seo = serializers.SerializerMethodField()

    class Meta(PostListSerializer.Meta):
        fields = PostListSerializer.Meta.fields + [
            "content",
            "views_count",
            "created_at",
            "updated_at",
            "seo",
        ]
        read_only_fields = fields

    def get_seo(self, obj) -> dict:
        """Return SEO metadata for this blog post."""
        from django.conf import settings

        frontend_url = getattr(settings, "FRONTEND_URL", "https://stepora.app")
        canonical_url = f"{frontend_url}/blog/{obj.slug}"
        description = obj.excerpt[:160] if obj.excerpt else obj.title

        return {
            "canonical_url": canonical_url,
            "og": {
                "title": obj.title,
                "description": description,
                "image": obj.cover_image or f"{frontend_url}/og-default.png",
                "url": canonical_url,
                "type": "article",
                "site_name": "Stepora",
            },
            "json_ld": {
                "@context": "https://schema.org",
                "@type": "BlogPosting",
                "headline": obj.title,
                "description": description,
                "image": obj.cover_image or f"{frontend_url}/og-default.png",
                "url": canonical_url,
                "datePublished": (
                    obj.published_at.isoformat() if obj.published_at else ""
                ),
                "dateModified": obj.updated_at.isoformat() if obj.updated_at else "",
                "author": {
                    "@type": "Person",
                    "name": obj.author.display_name or "Stepora",
                },
                "publisher": {
                    "@type": "Organization",
                    "name": "Stepora",
                    "logo": {
                        "@type": "ImageObject",
                        "url": f"{frontend_url}/logo.png",
                    },
                },
                "mainEntityOfPage": {
                    "@type": "WebPage",
                    "@id": canonical_url,
                },
            },
        }
