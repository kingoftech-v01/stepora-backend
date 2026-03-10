"""
Django admin configuration for the Blog system.

Provides admin interfaces for managing blog categories, tags, and posts.
"""

from django.contrib import admin

from .models import Category, Tag, Post


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    """Admin interface for blog Category model."""

    list_display = ['name', 'slug', 'icon', 'order', 'created_at']
    list_filter = ['created_at']
    search_fields = ['name', 'slug', 'description']
    prepopulated_fields = {'slug': ('name',)}
    ordering = ['order', 'name']
    readonly_fields = ['created_at']

    fieldsets = (
        (None, {
            'fields': ('name', 'slug', 'description', 'icon', 'order'),
        }),
        ('Timestamps', {
            'fields': ('created_at',),
            'classes': ('collapse',),
        }),
    )


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    """Admin interface for blog Tag model."""

    list_display = ['name', 'slug']
    search_fields = ['name', 'slug']
    prepopulated_fields = {'slug': ('name',)}
    ordering = ['name']


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    """Admin interface for blog Post model."""

    list_display = [
        'title', 'slug', 'author', 'category', 'status',
        'featured', 'read_time_minutes', 'views_count', 'published_at',
    ]
    list_filter = ['status', 'featured', 'category', 'published_at', 'created_at']
    search_fields = ['title', 'slug', 'excerpt', 'content']
    prepopulated_fields = {'slug': ('title',)}
    ordering = ['-published_at']
    readonly_fields = ['views_count', 'created_at', 'updated_at']
    raw_id_fields = ['author']
    filter_horizontal = ['tags']

    fieldsets = (
        (None, {
            'fields': ('title', 'slug', 'excerpt', 'content'),
        }),
        ('Classification', {
            'fields': ('category', 'tags', 'author'),
        }),
        ('Media', {
            'fields': ('cover_image',),
        }),
        ('Publishing', {
            'fields': ('status', 'featured', 'read_time_minutes', 'published_at'),
        }),
        ('Stats & Timestamps', {
            'fields': ('views_count', 'created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )
