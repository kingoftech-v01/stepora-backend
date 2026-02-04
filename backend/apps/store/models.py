"""
Models for the Store app.

Defines the data models for the in-app cosmetic store, including categories
of purchasable items, individual store items with Stripe integration, and
user inventory tracking for purchased and equipped items.
"""

import uuid
from decimal import Decimal

from django.db import models
from django.core.validators import MinValueValidator

from apps.users.models import User


class StoreCategory(models.Model):
    """
    Category grouping for store items.

    Organizes cosmetic items into browsable categories such as
    Badge Frames, Theme Skins, Avatar Decorations, Chat Bubbles,
    and Power-ups. Each category has a display order for consistent
    UI presentation.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text='Unique identifier for the category.'
    )
    name = models.CharField(
        max_length=100,
        unique=True,
        help_text='Display name of the category.'
    )
    slug = models.SlugField(
        max_length=100,
        unique=True,
        help_text='URL-friendly slug for the category.'
    )
    description = models.TextField(
        blank=True,
        default='',
        help_text='Description of the category shown to users.'
    )
    icon = models.CharField(
        max_length=255,
        blank=True,
        default='',
        help_text='Icon identifier or URL for the category.'
    )
    display_order = models.IntegerField(
        default=0,
        help_text='Order in which the category appears in the store.'
    )
    is_active = models.BooleanField(
        default=True,
        help_text='Whether the category is visible in the store.'
    )

    class Meta:
        db_table = 'store_categories'
        ordering = ['display_order', 'name']
        verbose_name = 'Store Category'
        verbose_name_plural = 'Store Categories'
        indexes = [
            models.Index(fields=['slug']),
            models.Index(fields=['is_active', 'display_order']),
        ]

    def __str__(self):
        return self.name


class StoreItem(models.Model):
    """
    Individual purchasable cosmetic item in the store.

    Represents a single cosmetic item that users can purchase via Stripe
    one-time payment. Items belong to a category, have a rarity tier,
    and are linked to a Stripe price ID for payment processing.
    """

    ITEM_TYPE_CHOICES = [
        ('badge_frame', 'Badge Frame'),
        ('theme_skin', 'Theme Skin'),
        ('avatar_decoration', 'Avatar Decoration'),
        ('chat_bubble', 'Chat Bubble'),
        ('streak_shield', 'Streak Shield'),
        ('xp_booster', 'XP Booster'),
    ]

    RARITY_CHOICES = [
        ('common', 'Common'),
        ('rare', 'Rare'),
        ('epic', 'Epic'),
        ('legendary', 'Legendary'),
    ]

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text='Unique identifier for the store item.'
    )
    category = models.ForeignKey(
        StoreCategory,
        on_delete=models.CASCADE,
        related_name='items',
        help_text='Category this item belongs to.'
    )
    name = models.CharField(
        max_length=200,
        help_text='Display name of the item.'
    )
    slug = models.SlugField(
        max_length=200,
        unique=True,
        help_text='URL-friendly slug for the item.'
    )
    description = models.TextField(
        blank=True,
        default='',
        help_text='Description of the item shown to users.'
    )
    image_url = models.URLField(
        max_length=500,
        blank=True,
        default='',
        help_text='URL to the item preview image.'
    )
    stripe_price_id = models.CharField(
        max_length=255,
        blank=True,
        default='',
        help_text='Stripe Price ID for one-time payment processing.'
    )
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text='Price of the item in USD.'
    )
    item_type = models.CharField(
        max_length=30,
        choices=ITEM_TYPE_CHOICES,
        db_index=True,
        help_text='Type of cosmetic item.'
    )
    rarity = models.CharField(
        max_length=20,
        choices=RARITY_CHOICES,
        default='common',
        db_index=True,
        help_text='Rarity tier of the item affecting visual presentation.'
    )
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text='Additional item metadata (e.g., colors, animation settings, duration).'
    )
    is_active = models.BooleanField(
        default=True,
        help_text='Whether the item is available for purchase.'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text='Timestamp when the item was added to the store.'
    )

    class Meta:
        db_table = 'store_items'
        ordering = ['category', 'price']
        verbose_name = 'Store Item'
        verbose_name_plural = 'Store Items'
        indexes = [
            models.Index(fields=['slug']),
            models.Index(fields=['item_type']),
            models.Index(fields=['rarity']),
            models.Index(fields=['is_active', 'item_type']),
            models.Index(fields=['category', 'is_active']),
            models.Index(fields=['price']),
        ]

    def __str__(self):
        return f"{self.name} ({self.get_rarity_display()}) - ${self.price}"


class UserInventory(models.Model):
    """
    Tracks items purchased and owned by a user.

    Each record represents a single purchase of a store item by a user,
    recording the Stripe payment intent ID for auditability. Users can
    equip or unequip items, with only one item of each type active at
    a time.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text='Unique identifier for this inventory entry.'
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='inventory',
        help_text='User who owns this item.'
    )
    item = models.ForeignKey(
        StoreItem,
        on_delete=models.CASCADE,
        related_name='owners',
        help_text='The store item that was purchased.'
    )
    purchased_at = models.DateTimeField(
        auto_now_add=True,
        help_text='Timestamp when the item was purchased.'
    )
    stripe_payment_intent_id = models.CharField(
        max_length=255,
        blank=True,
        default='',
        help_text='Stripe PaymentIntent ID for the purchase transaction.'
    )
    is_equipped = models.BooleanField(
        default=False,
        help_text='Whether the item is currently equipped/active for the user.'
    )

    class Meta:
        db_table = 'user_inventory'
        ordering = ['-purchased_at']
        verbose_name = 'User Inventory'
        verbose_name_plural = 'User Inventories'
        unique_together = [['user', 'item']]
        indexes = [
            models.Index(fields=['user', 'is_equipped']),
            models.Index(fields=['user', 'item']),
            models.Index(fields=['stripe_payment_intent_id']),
        ]

    def __str__(self):
        equipped_str = ' [EQUIPPED]' if self.is_equipped else ''
        return f"{self.user.email} - {self.item.name}{equipped_str}"
