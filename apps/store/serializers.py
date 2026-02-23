"""
Serializers for the Store app.

Provides DRF serializers for store categories, items, user inventory,
and the purchase flow. Includes validation logic for purchase requests
and nested serialization for category browsing with embedded items.
"""

from rest_framework import serializers

from core.sanitizers import sanitize_text
from .models import StoreCategory, StoreItem, UserInventory, Wishlist, Gift, RefundRequest


class StoreItemSerializer(serializers.ModelSerializer):
    """
    Serializer for store items.

    Provides a complete representation of a store item including its
    rarity and item type display names, category reference, and pricing.
    """

    rarity_display = serializers.CharField(
        source='get_rarity_display',
        read_only=True,
        help_text='Human-readable rarity label.',
    )
    item_type_display = serializers.CharField(
        source='get_item_type_display',
        read_only=True,
        help_text='Human-readable item type label.',
    )
    category_name = serializers.CharField(
        source='category.name',
        read_only=True,
        help_text='Name of the parent category.',
    )

    class Meta:
        model = StoreItem
        fields = [
            'id',
            'category',
            'category_name',
            'name',
            'slug',
            'description',
            'image_url',
            'price',
            'item_type',
            'item_type_display',
            'rarity',
            'rarity_display',
            'metadata',
            'xp_price',
            'available_from',
            'available_until',
            'is_active',
            'created_at',
        ]
        read_only_fields = ['id', 'created_at']
        extra_kwargs = {
            'id': {'help_text': 'Unique identifier for the store item.'},
            'category': {'help_text': 'Category this item belongs to.'},
            'name': {'help_text': 'Display name of the item.'},
            'slug': {'help_text': 'URL-friendly slug for the item.'},
            'description': {'help_text': 'Full description of the item.'},
            'image_url': {'help_text': 'URL of the item image.'},
            'price': {'help_text': 'Price in cents for Stripe payment.'},
            'item_type': {'help_text': 'Type classification of the item.'},
            'rarity': {'help_text': 'Rarity tier of the item.'},
            'metadata': {'help_text': 'Additional JSON metadata for the item.'},
            'xp_price': {'help_text': 'XP cost to purchase this item.'},
            'available_from': {'help_text': 'Start date when item becomes available.'},
            'available_until': {'help_text': 'End date when item is no longer available.'},
            'is_active': {'help_text': 'Whether the item is currently listed.'},
            'created_at': {'help_text': 'Timestamp when the item was created.'},
        }


class StoreItemDetailSerializer(StoreItemSerializer):
    """
    Extended serializer for store item detail view.

    Includes the total number of owners (purchase count) to show
    item popularity, and whether the current requesting user
    already owns the item.
    """

    owners_count = serializers.SerializerMethodField(
        help_text='Total number of users who own this item.',
    )
    is_owned = serializers.SerializerMethodField(
        help_text='Whether the current user owns this item.',
    )

    class Meta(StoreItemSerializer.Meta):
        fields = StoreItemSerializer.Meta.fields + [
            'owners_count',
            'is_owned',
        ]

    def get_owners_count(self, obj) -> int:
        """Return the total number of users who own this item."""
        return obj.owners.count()

    def get_is_owned(self, obj) -> bool:
        """Check whether the requesting user already owns this item."""
        request = self.context.get('request')
        if request and hasattr(request, 'user') and request.user.is_authenticated:
            return UserInventory.objects.filter(
                user=request.user,
                item=obj
            ).exists()
        return False


class StoreCategorySerializer(serializers.ModelSerializer):
    """
    Serializer for store categories.

    Provides basic category information for listing views.
    """

    items_count = serializers.SerializerMethodField(
        help_text='Number of active items in this category.',
    )

    class Meta:
        model = StoreCategory
        fields = [
            'id',
            'name',
            'slug',
            'description',
            'icon',
            'display_order',
            'is_active',
            'items_count',
        ]
        read_only_fields = ['id']
        extra_kwargs = {
            'id': {'help_text': 'Unique identifier for the category.'},
            'name': {'help_text': 'Display name of the category.'},
            'slug': {'help_text': 'URL-friendly slug for the category.'},
            'description': {'help_text': 'Brief description of the category.'},
            'icon': {'help_text': 'Icon identifier for the category.'},
            'display_order': {'help_text': 'Sort order for category listing.'},
            'is_active': {'help_text': 'Whether the category is visible in the store.'},
        }

    def get_items_count(self, obj) -> int:
        """Return the number of active items in this category."""
        return obj.items.filter(is_active=True).count()


class StoreCategoryDetailSerializer(StoreCategorySerializer):
    """
    Detailed serializer for a single store category.

    Includes the full list of active items nested within the category
    for the category detail/browse view.
    """

    items = StoreItemSerializer(
        many=True, read_only=True, source='active_items',
        help_text='Active items belonging to this category.',
    )

    class Meta(StoreCategorySerializer.Meta):
        fields = StoreCategorySerializer.Meta.fields + ['items']

    def to_representation(self, instance):
        """Override to filter only active items in the nested list."""
        ret = super().to_representation(instance)
        # Filter items to only include active ones
        active_items = instance.items.filter(is_active=True)
        ret['items'] = StoreItemSerializer(
            active_items,
            many=True,
            context=self.context
        ).data
        return ret


class UserInventorySerializer(serializers.ModelSerializer):
    """
    Serializer for user inventory entries.

    Provides a complete view of an owned item, including nested
    item details for display in the user's inventory screen.
    """

    item = StoreItemSerializer(read_only=True, help_text='Nested store item details.')
    item_id = serializers.UUIDField(
        source='item.id', read_only=True,
        help_text='UUID of the owned store item.',
    )

    class Meta:
        model = UserInventory
        fields = [
            'id',
            'user',
            'item',
            'item_id',
            'purchased_at',
            'stripe_payment_intent_id',
            'is_equipped',
        ]
        read_only_fields = [
            'id',
            'user',
            'item',
            'purchased_at',
            'stripe_payment_intent_id',
        ]
        extra_kwargs = {
            'id': {'help_text': 'Unique identifier for the inventory entry.'},
            'user': {'help_text': 'Owner of this inventory entry.'},
            'purchased_at': {'help_text': 'Timestamp when the item was purchased.'},
            'stripe_payment_intent_id': {'help_text': 'Stripe PaymentIntent ID for the purchase.'},
            'is_equipped': {'help_text': 'Whether the item is currently equipped.'},
        }


class PurchaseSerializer(serializers.Serializer):
    """
    Serializer for initiating a store item purchase.

    Validates the item_id provided by the client and ensures
    the item exists, is active, and has not already been purchased
    by the requesting user.
    """

    item_id = serializers.UUIDField(
        help_text='UUID of the store item to purchase.'
    )

    def validate_item_id(self, value):
        """
        Validate that the item exists and is available for purchase.

        Raises:
            ValidationError: If the item does not exist or is inactive.
        """
        try:
            item = StoreItem.objects.get(id=value)
        except StoreItem.DoesNotExist:
            raise serializers.ValidationError('Store item not found.')

        if not item.is_active:
            raise serializers.ValidationError('This item is no longer available for purchase.')

        return value

    def validate(self, attrs):
        """
        Perform cross-field validation for the purchase request.

        Ensures the requesting user has not already purchased this item.

        Raises:
            ValidationError: If the user already owns the item.
        """
        request = self.context.get('request')
        if request and hasattr(request, 'user') and request.user.is_authenticated:
            already_owned = UserInventory.objects.filter(
                user=request.user,
                item_id=attrs['item_id']
            ).exists()
            if already_owned:
                raise serializers.ValidationError(
                    {'item_id': 'You already own this item.'}
                )

        return attrs


class PurchaseConfirmSerializer(serializers.Serializer):
    """
    Serializer for confirming a purchase after Stripe payment.

    Validates the item_id and payment_intent_id to finalize
    the purchase and add the item to the user's inventory.
    """

    item_id = serializers.UUIDField(
        help_text='UUID of the store item being purchased.'
    )
    payment_intent_id = serializers.CharField(
        max_length=255,
        help_text='Stripe PaymentIntent ID from the client-side payment flow.'
    )

    def validate_item_id(self, value):
        """Validate that the item exists."""
        try:
            StoreItem.objects.get(id=value)
        except StoreItem.DoesNotExist:
            raise serializers.ValidationError('Store item not found.')
        return value

    def validate_payment_intent_id(self, value):
        """Validate that the payment intent ID is properly formatted."""
        if not value.startswith('pi_'):
            raise serializers.ValidationError(
                'Invalid payment intent ID format.'
            )
        return value


class EquipSerializer(serializers.Serializer):
    """
    Serializer for equipping or unequipping an inventory item.

    Accepts the equip action to toggle the equipped state of an item.
    """

    equip = serializers.BooleanField(
        help_text='True to equip the item, False to unequip.'
    )


class WishlistSerializer(serializers.ModelSerializer):
    """Serializer for wishlist entries."""

    item = StoreItemSerializer(read_only=True, help_text='Nested store item details.')
    item_id = serializers.UUIDField(
        write_only=True,
        help_text='UUID of the store item to add to the wishlist.',
    )

    class Meta:
        model = Wishlist
        fields = ['id', 'user', 'item', 'item_id', 'created_at']
        read_only_fields = ['id', 'user', 'created_at']
        extra_kwargs = {
            'id': {'help_text': 'Unique identifier for the wishlist entry.'},
            'user': {'help_text': 'User who owns this wishlist entry.'},
            'created_at': {'help_text': 'Timestamp when the item was wishlisted.'},
        }

    def validate_item_id(self, value):
        """Validate that the item exists and is active."""
        try:
            item = StoreItem.objects.get(id=value)
        except StoreItem.DoesNotExist:
            raise serializers.ValidationError('Store item not found.')
        if not item.is_active:
            raise serializers.ValidationError('This item is not available.')
        return value

    def validate(self, attrs):
        """Check if already wishlisted."""
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            if Wishlist.objects.filter(user=request.user, item_id=attrs['item_id']).exists():
                raise serializers.ValidationError({'item_id': 'Item already in your wishlist.'})
        return attrs


class XPPurchaseSerializer(serializers.Serializer):
    """Serializer for purchasing an item with XP."""

    item_id = serializers.UUIDField(
        help_text='UUID of the store item to purchase with XP.'
    )

    def validate_item_id(self, value):
        """Validate that the item exists, is active, and supports XP purchase."""
        try:
            item = StoreItem.objects.get(id=value)
        except StoreItem.DoesNotExist:
            raise serializers.ValidationError('Store item not found.')
        if not item.is_active:
            raise serializers.ValidationError('This item is not available for purchase.')
        if item.xp_price <= 0:
            raise serializers.ValidationError('This item cannot be purchased with XP.')
        return value


class GiftSendSerializer(serializers.Serializer):
    """Serializer for sending a gift to another user."""

    item_id = serializers.UUIDField(help_text='UUID of the store item to gift.')
    recipient_id = serializers.UUIDField(help_text='UUID of the recipient user.')
    message = serializers.CharField(
        max_length=500, required=False, default='',
        help_text='Optional personal message.',
    )

    def validate_message(self, value):
        return sanitize_text(value)


class GiftSerializer(serializers.ModelSerializer):
    """Serializer for displaying gift details."""

    item = StoreItemSerializer(read_only=True, help_text='Nested store item details.')
    sender_name = serializers.CharField(
        source='sender.display_name', read_only=True,
        help_text='Display name of the gift sender.',
    )
    recipient_name = serializers.CharField(
        source='recipient.display_name', read_only=True,
        help_text='Display name of the gift recipient.',
    )

    class Meta:
        model = Gift
        fields = [
            'id', 'sender', 'sender_name', 'recipient', 'recipient_name',
            'item', 'message', 'is_claimed', 'claimed_at', 'created_at',
        ]
        read_only_fields = fields
        extra_kwargs = {
            'id': {'help_text': 'Unique identifier for the gift.'},
            'sender': {'help_text': 'User who sent the gift.'},
            'recipient': {'help_text': 'User who received the gift.'},
            'message': {'help_text': 'Personal message attached to the gift.'},
            'is_claimed': {'help_text': 'Whether the recipient has claimed the gift.'},
            'claimed_at': {'help_text': 'Timestamp when the gift was claimed.'},
            'created_at': {'help_text': 'Timestamp when the gift was sent.'},
        }


class RefundRequestSerializer(serializers.Serializer):
    """Serializer for requesting a refund."""

    inventory_id = serializers.UUIDField(help_text='UUID of the inventory entry to refund.')
    reason = serializers.CharField(
        max_length=2000,
        help_text='Reason for the refund request.',
    )

    def validate_reason(self, value):
        return sanitize_text(value)


class RefundRequestDisplaySerializer(serializers.ModelSerializer):
    """Serializer for displaying refund request details."""

    item_name = serializers.CharField(
        source='inventory_entry.item.name', read_only=True,
        help_text='Name of the item being refunded.',
    )

    class Meta:
        model = RefundRequest
        fields = [
            'id', 'user', 'inventory_entry', 'item_name',
            'reason', 'status', 'admin_notes',
            'created_at', 'updated_at',
        ]
        read_only_fields = fields
        extra_kwargs = {
            'id': {'help_text': 'Unique identifier for the refund request.'},
            'user': {'help_text': 'User who submitted the refund request.'},
            'inventory_entry': {'help_text': 'Inventory entry being refunded.'},
            'reason': {'help_text': 'Reason provided for the refund.'},
            'status': {'help_text': 'Current status of the refund request.'},
            'admin_notes': {'help_text': 'Notes from admin reviewing the request.'},
            'created_at': {'help_text': 'Timestamp when the request was submitted.'},
            'updated_at': {'help_text': 'Timestamp when the request was last updated.'},
        }
