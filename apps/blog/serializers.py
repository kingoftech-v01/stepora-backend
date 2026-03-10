"""
Serializers for the Blog system.

These serializers handle blog posts, categories, and tags.
List serializers omit the full content body to keep payloads small;
detail serializers include everything.
"""

from rest_framework import serializers

from .models import Category, Tag, Post


class CategorySerializer(serializers.ModelSerializer):
    """Serializer for blog categories."""

    class Meta:
        model = Category
        fields = [
            'id',
            'name',
            'slug',
            'description',
            'icon',
            'order',
        ]
        read_only_fields = fields


class TagSerializer(serializers.ModelSerializer):
    """Serializer for blog tags."""

    class Meta:
        model = Tag
        fields = [
            'id',
            'name',
            'slug',
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
    publishedAt = serializers.DateTimeField(source='published_at', read_only=True)
    readTimeMinutes = serializers.IntegerField(source='read_time_minutes', read_only=True)
    coverImage = serializers.URLField(source='cover_image', read_only=True)

    class Meta:
        model = Post
        fields = [
            'id',
            'title',
            'slug',
            'excerpt',
            'category',
            'tags',
            'author',
            'coverImage',
            'publishedAt',
            'readTimeMinutes',
            'featured',
        ]
        read_only_fields = fields

    def get_author(self, obj) -> dict:
        """Return the author's public profile info."""
        return {
            'id': str(obj.author.id),
            'name': obj.author.display_name or 'Anonymous',
            'avatar': obj.author.avatar_url or '',
        }


class PostDetailSerializer(PostListSerializer):
    """
    Serializer for blog post detail views.

    Extends the list serializer with full content and view count.
    """

    viewsCount = serializers.IntegerField(source='views_count', read_only=True)
    createdAt = serializers.DateTimeField(source='created_at', read_only=True)
    updatedAt = serializers.DateTimeField(source='updated_at', read_only=True)

    class Meta(PostListSerializer.Meta):
        fields = PostListSerializer.Meta.fields + [
            'content',
            'viewsCount',
            'createdAt',
            'updatedAt',
        ]
        read_only_fields = fields
