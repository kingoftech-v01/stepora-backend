"""
Service layer for the Store app.

Encapsulates all business logic for the in-app store, including
Stripe payment intent creation, purchase confirmation with payment
verification, inventory management, and item equip/unequip logic.
All Stripe interactions are isolated here for testability.
"""

import logging
import os

import stripe
from django.db import transaction

from .models import StoreItem, UserInventory

logger = logging.getLogger(__name__)

# Configure Stripe with the secret key from environment
stripe.api_key = os.environ.get('STRIPE_SECRET_KEY', '')


class StoreServiceError(Exception):
    """Base exception for store service errors."""
    pass


class ItemNotFoundError(StoreServiceError):
    """Raised when a requested store item does not exist."""
    pass


class ItemAlreadyOwnedError(StoreServiceError):
    """Raised when a user attempts to purchase an item they already own."""
    pass


class ItemNotActiveError(StoreServiceError):
    """Raised when a user attempts to purchase an inactive item."""
    pass


class PaymentVerificationError(StoreServiceError):
    """Raised when Stripe payment verification fails."""
    pass


class InventoryNotFoundError(StoreServiceError):
    """Raised when an inventory entry does not exist."""
    pass


class StoreService:
    """
    Service class for all store-related business operations.

    Provides methods for creating Stripe payment intents, confirming
    purchases, managing user inventory, and equipping/unequipping items.
    All database operations use atomic transactions where appropriate
    to maintain data integrity.
    """

    @staticmethod
    def create_payment_intent(user, item):
        """
        Create a Stripe PaymentIntent for a store item purchase.

        Initiates a one-time payment flow by creating a PaymentIntent
        with the item's price. The client secret is returned so the
        mobile app can complete payment on the client side using
        Stripe's SDK.

        Args:
            user: The User instance initiating the purchase.
            item: The StoreItem instance to purchase.

        Returns:
            dict: Contains 'client_secret', 'payment_intent_id', and
                  'amount' for the client-side payment flow.

        Raises:
            ItemNotActiveError: If the item is not currently active.
            ItemAlreadyOwnedError: If the user already owns this item.
            PaymentVerificationError: If Stripe API call fails.
        """
        if not item.is_active:
            raise ItemNotActiveError(
                f'Item "{item.name}" is not available for purchase.'
            )

        # Check if user already owns this item
        if UserInventory.objects.filter(user=user, item=item).exists():
            raise ItemAlreadyOwnedError(
                f'You already own "{item.name}".'
            )

        # Convert price to cents for Stripe (Stripe uses smallest currency unit)
        amount_cents = int(item.price * 100)

        try:
            payment_intent = stripe.PaymentIntent.create(
                amount=amount_cents,
                currency='usd',
                metadata={
                    'user_id': str(user.id),
                    'item_id': str(item.id),
                    'item_name': item.name,
                    'item_type': item.item_type,
                },
                description=f'DreamPlanner Store: {item.name}',
                receipt_email=user.email,
            )

            logger.info(
                'Payment intent created: %s for user %s, item %s ($%s)',
                payment_intent.id,
                user.id,
                item.id,
                item.price,
            )

            return {
                'client_secret': payment_intent.client_secret,
                'payment_intent_id': payment_intent.id,
                'amount': amount_cents,
            }

        except stripe.error.StripeError as e:
            logger.error(
                'Stripe error creating payment intent for user %s, item %s: %s',
                user.id,
                item.id,
                str(e),
            )
            raise PaymentVerificationError(
                f'Payment processing failed: {str(e)}'
            )

    @staticmethod
    @transaction.atomic
    def confirm_purchase(user, item, payment_intent_id):
        """
        Confirm a purchase after successful Stripe payment.

        Verifies the payment intent status with Stripe, then creates
        a UserInventory record to grant the item to the user. Uses
        an atomic transaction to ensure data consistency.

        Args:
            user: The User instance completing the purchase.
            item: The StoreItem instance being purchased.
            payment_intent_id: The Stripe PaymentIntent ID to verify.

        Returns:
            UserInventory: The newly created inventory entry.

        Raises:
            ItemAlreadyOwnedError: If the user already owns this item.
            PaymentVerificationError: If payment verification fails.
        """
        # Check if user already owns this item (race condition guard)
        if UserInventory.objects.filter(user=user, item=item).exists():
            raise ItemAlreadyOwnedError(
                f'You already own "{item.name}".'
            )

        # Verify payment intent with Stripe
        try:
            payment_intent = stripe.PaymentIntent.retrieve(payment_intent_id)
        except stripe.error.StripeError as e:
            logger.error(
                'Stripe error retrieving payment intent %s: %s',
                payment_intent_id,
                str(e),
            )
            raise PaymentVerificationError(
                f'Unable to verify payment: {str(e)}'
            )

        # Verify payment was successful
        if payment_intent.status != 'succeeded':
            logger.warning(
                'Payment intent %s has status %s (expected "succeeded") '
                'for user %s, item %s',
                payment_intent_id,
                payment_intent.status,
                user.id,
                item.id,
            )
            raise PaymentVerificationError(
                f'Payment has not been completed. Status: {payment_intent.status}'
            )

        # Verify the payment amount matches the item price
        expected_amount = int(item.price * 100)
        if payment_intent.amount != expected_amount:
            logger.error(
                'Payment amount mismatch for intent %s: expected %d, got %d',
                payment_intent_id,
                expected_amount,
                payment_intent.amount,
            )
            raise PaymentVerificationError(
                'Payment amount does not match item price.'
            )

        # Verify metadata matches
        intent_metadata = payment_intent.get('metadata', {})
        if intent_metadata.get('user_id') != str(user.id):
            logger.error(
                'Payment intent %s user mismatch: expected %s, got %s',
                payment_intent_id,
                user.id,
                intent_metadata.get('user_id'),
            )
            raise PaymentVerificationError(
                'Payment verification failed: user mismatch.'
            )

        # Create inventory entry
        inventory_entry = UserInventory.objects.create(
            user=user,
            item=item,
            stripe_payment_intent_id=payment_intent_id,
            is_equipped=False,
        )

        logger.info(
            'Purchase confirmed: user %s acquired item %s (payment: %s)',
            user.id,
            item.id,
            payment_intent_id,
        )

        return inventory_entry

    @staticmethod
    def get_user_inventory(user):
        """
        Retrieve all items owned by a user.

        Returns a queryset of UserInventory entries with related
        item and category data pre-fetched for optimal performance.

        Args:
            user: The User instance whose inventory to retrieve.

        Returns:
            QuerySet[UserInventory]: The user's inventory entries
                ordered by purchase date (newest first).
        """
        return UserInventory.objects.filter(
            user=user
        ).select_related(
            'item',
            'item__category',
        ).order_by('-purchased_at')

    @staticmethod
    @transaction.atomic
    def equip_item(user, inventory_id):
        """
        Equip an item from the user's inventory.

        Unequips any other items of the same type (e.g., only one
        badge frame can be equipped at a time), then equips the
        specified item.

        Args:
            user: The User instance equipping the item.
            inventory_id: UUID of the UserInventory entry to equip.

        Returns:
            UserInventory: The updated inventory entry with is_equipped=True.

        Raises:
            InventoryNotFoundError: If the inventory entry does not exist
                or does not belong to the user.
        """
        try:
            inventory_entry = UserInventory.objects.select_related('item').get(
                id=inventory_id,
                user=user,
            )
        except UserInventory.DoesNotExist:
            raise InventoryNotFoundError(
                'Item not found in your inventory.'
            )

        # Unequip all other items of the same type for this user
        UserInventory.objects.filter(
            user=user,
            item__item_type=inventory_entry.item.item_type,
            is_equipped=True,
        ).exclude(
            id=inventory_id,
        ).update(is_equipped=False)

        # Equip the selected item
        inventory_entry.is_equipped = True
        inventory_entry.save(update_fields=['is_equipped'])

        logger.info(
            'User %s equipped item %s (type: %s)',
            user.id,
            inventory_entry.item.id,
            inventory_entry.item.item_type,
        )

        return inventory_entry

    @staticmethod
    def unequip_item(user, inventory_id):
        """
        Unequip an item from the user's inventory.

        Args:
            user: The User instance unequipping the item.
            inventory_id: UUID of the UserInventory entry to unequip.

        Returns:
            UserInventory: The updated inventory entry with is_equipped=False.

        Raises:
            InventoryNotFoundError: If the inventory entry does not exist
                or does not belong to the user.
        """
        try:
            inventory_entry = UserInventory.objects.get(
                id=inventory_id,
                user=user,
            )
        except UserInventory.DoesNotExist:
            raise InventoryNotFoundError(
                'Item not found in your inventory.'
            )

        inventory_entry.is_equipped = False
        inventory_entry.save(update_fields=['is_equipped'])

        logger.info(
            'User %s unequipped item %s',
            user.id,
            inventory_entry.item_id,
        )

        return inventory_entry
