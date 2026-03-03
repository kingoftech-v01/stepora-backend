"""
Django admin configuration for the Store app.

Registers all store models with the Django admin interface,
providing rich list displays, filters, search, and inline editing
for efficient store management.
"""

from django.contrib import admin

from .models import StoreCategory, StoreItem, UserInventory, Wishlist, Gift, RefundRequest


class StoreItemInline(admin.TabularInline):
    """Inline admin for StoreItems within a StoreCategory."""

    model = StoreItem
    extra = 0
    fields = ['name', 'slug', 'item_type', 'rarity', 'price', 'is_active']
    readonly_fields = ['slug']
    show_change_link = True


@admin.register(StoreCategory)
class StoreCategoryAdmin(admin.ModelAdmin):
    """Admin interface for StoreCategory model."""

    list_display = [
        'name',
        'slug',
        'display_order',
        'is_active',
        'items_count',
    ]
    list_filter = ['is_active']
    search_fields = ['name', 'description']
    ordering = ['display_order', 'name']
    prepopulated_fields = {'slug': ('name',)}
    inlines = [StoreItemInline]

    fieldsets = (
        ('Basic Info', {
            'fields': ('name', 'slug', 'description', 'icon'),
        }),
        ('Display', {
            'fields': ('display_order', 'is_active'),
        }),
    )

    def items_count(self, obj):
        """Return the number of items in this category."""
        return obj.items.count()

    items_count.short_description = 'Items'


@admin.register(StoreItem)
class StoreItemAdmin(admin.ModelAdmin):
    """Admin interface for StoreItem model."""

    list_display = [
        'name',
        'category',
        'item_type',
        'rarity',
        'price',
        'stripe_price_id',
        'is_active',
        'owners_count',
        'created_at',
    ]
    list_filter = [
        'is_active',
        'item_type',
        'rarity',
        'category',
    ]
    search_fields = ['name', 'description', 'stripe_price_id']
    ordering = ['category', 'price']
    prepopulated_fields = {'slug': ('name',)}
    readonly_fields = ['created_at']
    list_editable = ['is_active', 'price']

    fieldsets = (
        ('Basic Info', {
            'fields': ('category', 'name', 'slug', 'description', 'image_url'),
        }),
        ('Pricing & Stripe', {
            'fields': ('price', 'stripe_price_id'),
        }),
        ('Classification', {
            'fields': ('item_type', 'rarity'),
        }),
        ('Configuration', {
            'fields': ('metadata', 'is_active'),
        }),
        ('Timestamps', {
            'fields': ('created_at',),
            'classes': ('collapse',),
        }),
    )

    def owners_count(self, obj):
        """Return the number of users who own this item."""
        return obj.owners.count()

    owners_count.short_description = 'Owners'


@admin.register(UserInventory)
class UserInventoryAdmin(admin.ModelAdmin):
    """Admin interface for UserInventory model."""

    list_display = [
        'user',
        'item',
        'is_equipped',
        'stripe_payment_intent_id',
        'purchased_at',
    ]
    list_filter = [
        'is_equipped',
        'item__item_type',
        'item__rarity',
        'purchased_at',
    ]
    search_fields = [
        'user__email',
        'user__display_name',
        'item__name',
        'stripe_payment_intent_id',
    ]
    ordering = ['-purchased_at']
    readonly_fields = ['purchased_at']
    raw_id_fields = ['user', 'item']

    fieldsets = (
        ('Ownership', {
            'fields': ('user', 'item', 'is_equipped'),
        }),
        ('Payment', {
            'fields': ('stripe_payment_intent_id',),
        }),
        ('Timestamps', {
            'fields': ('purchased_at',),
            'classes': ('collapse',),
        }),
    )


@admin.register(Wishlist)
class WishlistAdmin(admin.ModelAdmin):
    """Admin interface for Wishlist model."""

    list_display = ['user', 'item', 'created_at']
    list_filter = ['item__item_type', 'item__rarity', 'created_at']
    search_fields = ['user__email', 'user__display_name', 'item__name']
    ordering = ['-created_at']
    readonly_fields = ['created_at']
    raw_id_fields = ['user', 'item']

    fieldsets = (
        ('Wishlist Entry', {
            'fields': ('user', 'item'),
        }),
        ('Timestamps', {
            'fields': ('created_at',),
            'classes': ('collapse',),
        }),
    )


@admin.register(Gift)
class GiftAdmin(admin.ModelAdmin):
    """Admin interface for Gift model."""

    list_display = [
        'sender', 'recipient', 'item', 'is_claimed', 'claimed_at', 'created_at',
    ]
    list_filter = ['is_claimed', 'item__item_type', 'item__rarity', 'created_at']
    search_fields = [
        'sender__email', 'recipient__email', 'item__name', 'stripe_payment_intent_id',
    ]
    ordering = ['-created_at']
    readonly_fields = ['created_at', 'claimed_at']
    raw_id_fields = ['sender', 'recipient', 'item']

    fieldsets = (
        ('Gift Details', {
            'fields': ('sender', 'recipient', 'item', 'message'),
        }),
        ('Payment', {
            'fields': ('stripe_payment_intent_id',),
        }),
        ('Status', {
            'fields': ('is_claimed', 'claimed_at'),
        }),
        ('Timestamps', {
            'fields': ('created_at',),
            'classes': ('collapse',),
        }),
    )


@admin.register(RefundRequest)
class RefundRequestAdmin(admin.ModelAdmin):
    """Admin interface for RefundRequest model."""

    list_display = [
        'user', 'item_name', 'status', 'stripe_refund_id', 'created_at', 'updated_at',
    ]
    list_filter = ['status', 'created_at']
    search_fields = [
        'user__email', 'user__display_name',
        'inventory_entry__item__name', 'stripe_refund_id',
    ]
    ordering = ['-created_at']
    readonly_fields = ['created_at', 'updated_at', 'user', 'inventory_entry', 'reason']

    fieldsets = (
        ('Request Details', {
            'fields': ('user', 'inventory_entry', 'reason'),
        }),
        ('Admin Review', {
            'fields': ('status', 'admin_notes', 'stripe_refund_id'),
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    def item_name(self, obj):
        return obj.inventory_entry.item.name

    item_name.short_description = 'Item'
