"""
Serializers for the Store app.

Provides DRF serializers for store categories, items, user inventory,
and the purchase flow. Includes validation logic for purchase requests
and nested serialization for category browsing with embedded items.
"""

from rest_framework import serializers

from .models import StoreCategory, StoreItem, UserInventory


class StoreItemSerializer(serializers.ModelSerializer):
    """
    Serializer for store items.

    Provides a complete representation of a store item including its
    rarity and item type display names, category reference, and pricing.
    """

    rarity_display = serializers.CharField(
        source='get_rarity_display',
        read_only=True
    )
    item_type_display = serializers.CharField(
        source='get_item_type_display',
        read_only=True
    )
    category_name = serializers.CharField(
        source='category.name',
        read_only=True
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
            'is_active',
            'created_at',
        ]
        read_only_fields = ['id', 'created_at']


class StoreItemDetailSerializer(StoreItemSerializer):
    """
    Extended serializer for store item detail view.

    Includes the total number of owners (purchase count) to show
    item popularity, and whether the current requesting user
    already owns the item.
    """

    owners_count = serializers.SerializerMethodField()
    is_owned = serializers.SerializerMethodField()

    class Meta(StoreItemSerializer.Meta):
        fields = StoreItemSerializer.Meta.fields + [
            'owners_count',
            'is_owned',
        ]

    def get_owners_count(self, obj):
        """Return the total number of users who own this item."""
        return obj.owners.count()

    def get_is_owned(self, obj):
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

    items_count = serializers.SerializerMethodField()

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

    def get_items_count(self, obj):
        """Return the number of active items in this category."""
        return obj.items.filter(is_active=True).count()


class StoreCategoryDetailSerializer(StoreCategorySerializer):
    """
    Detailed serializer for a single store category.

    Includes the full list of active items nested within the category
    for the category detail/browse view.
    """

    items = StoreItemSerializer(many=True, read_only=True, source='active_items')

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

    item = StoreItemSerializer(read_only=True)
    item_id = serializers.UUIDField(source='item.id', read_only=True)

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
