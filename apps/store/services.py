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
from django.db.models import F

from .models import StoreItem, UserInventory, Gift, RefundRequest

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


class InsufficientXPError(StoreServiceError):
    """Raised when a user does not have enough XP for a purchase."""
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
                description=f'Stepora Store: {item.name}',
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
        # Lock-based check to prevent duplicate inventory from concurrent requests
        if UserInventory.objects.select_for_update().filter(user=user, item=item).exists():
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

    @staticmethod
    @transaction.atomic
    def purchase_with_xp(user, item):
        """
        Purchase a store item using XP.

        Deducts XP from the user and creates an inventory entry.

        Args:
            user: The User instance making the purchase.
            item: The StoreItem instance to purchase.

        Returns:
            UserInventory: The newly created inventory entry.

        Raises:
            ItemNotActiveError: If the item is not currently active.
            ItemAlreadyOwnedError: If the user already owns this item.
            InsufficientXPError: If the user doesn't have enough XP.
        """
        if not item.is_active:
            raise ItemNotActiveError(
                f'Item "{item.name}" is not available for purchase.'
            )

        if item.xp_price <= 0:
            raise ItemNotActiveError(
                f'Item "{item.name}" cannot be purchased with XP.'
            )

        # Lock the user row to prevent race conditions on XP
        from django.contrib.auth import get_user_model
        User = get_user_model()
        locked_user = User.objects.select_for_update().get(id=user.id)

        if UserInventory.objects.filter(user=user, item=item).exists():
            raise ItemAlreadyOwnedError(
                f'You already own "{item.name}".'
            )

        if locked_user.xp < item.xp_price:
            raise InsufficientXPError(
                f'Insufficient XP. You have {locked_user.xp} XP but need {item.xp_price} XP.'
            )

        # Deduct XP atomically
        User.objects.filter(id=user.id).update(xp=F('xp') - item.xp_price)
        user.refresh_from_db(fields=['xp'])

        # Create inventory entry
        inventory_entry = UserInventory.objects.create(
            user=user,
            item=item,
            stripe_payment_intent_id='',
            is_equipped=False,
        )

        logger.info(
            'XP purchase: user %s acquired item %s for %d XP',
            user.id,
            item.id,
            item.xp_price,
        )

        return inventory_entry

    @staticmethod
    @transaction.atomic
    def send_gift(sender, recipient, item, message=''):
        """
        Send a store item as a gift to another user.

        Creates a Stripe PaymentIntent for the sender, and a Gift record.

        Args:
            sender: User sending the gift.
            recipient: User receiving the gift.
            item: StoreItem to gift.
            message: Optional personal message.

        Returns:
            dict with gift_id and client_secret for Stripe payment.
        """
        if not item.is_active:
            raise ItemNotActiveError(f'Item "{item.name}" is not available.')

        if sender == recipient:
            raise StoreServiceError('You cannot gift an item to yourself.')

        # Check if recipient already owns the item
        if UserInventory.objects.filter(user=recipient, item=item).exists():
            raise ItemAlreadyOwnedError(f'{recipient.display_name or "Recipient"} already owns "{item.name}".')

        amount_cents = int(item.price * 100)

        try:
            payment_intent = stripe.PaymentIntent.create(
                amount=amount_cents,
                currency='usd',
                metadata={
                    'user_id': str(sender.id),
                    'recipient_id': str(recipient.id),
                    'item_id': str(item.id),
                    'type': 'gift',
                },
                description=f'Stepora Gift: {item.name} to {recipient.email}',
                receipt_email=sender.email,
            )
        except stripe.error.StripeError as e:
            raise PaymentVerificationError(f'Payment failed: {str(e)}')

        gift = Gift.objects.create(
            sender=sender,
            recipient=recipient,
            item=item,
            message=message,
            stripe_payment_intent_id=payment_intent.id,
        )

        logger.info(
            'Gift created: %s from %s to %s (item: %s)',
            gift.id, sender.id, recipient.id, item.id,
        )

        return {
            'gift_id': str(gift.id),
            'client_secret': payment_intent.client_secret,
            'payment_intent_id': payment_intent.id,
            'amount': amount_cents,
        }

    @staticmethod
    @transaction.atomic
    def claim_gift(user, gift_id):
        """
        Claim a gift and add the item to the recipient's inventory.

        Args:
            user: User claiming the gift.
            gift_id: UUID of the Gift to claim.

        Returns:
            UserInventory entry for the claimed item.
        """
        try:
            gift = Gift.objects.select_related('item').get(
                id=gift_id, recipient=user, is_claimed=False,
            )
        except Gift.DoesNotExist:
            raise ItemNotFoundError('Gift not found or already claimed.')

        # Check if user already owns the item (edge case)
        if UserInventory.objects.filter(user=user, item=gift.item).exists():
            raise ItemAlreadyOwnedError(f'You already own "{gift.item.name}".')

        from django.utils import timezone as tz
        gift.is_claimed = True
        gift.claimed_at = tz.now()
        gift.save(update_fields=['is_claimed', 'claimed_at'])

        inventory_entry = UserInventory.objects.create(
            user=user,
            item=gift.item,
            stripe_payment_intent_id=gift.stripe_payment_intent_id,
            is_equipped=False,
        )

        logger.info('Gift %s claimed by user %s', gift_id, user.id)
        return inventory_entry

    @staticmethod
    def request_refund(user, inventory_id, reason):
        """
        Request a refund for a purchased item.

        Args:
            user: User requesting the refund.
            inventory_id: UUID of the UserInventory entry.
            reason: Reason for the refund.

        Returns:
            RefundRequest instance.
        """
        try:
            inventory_entry = UserInventory.objects.select_related('item').get(
                id=inventory_id, user=user,
            )
        except UserInventory.DoesNotExist:
            raise InventoryNotFoundError('Item not found in your inventory.')

        if not inventory_entry.stripe_payment_intent_id:
            raise StoreServiceError('This item was not purchased with money and cannot be refunded.')

        # Check for existing pending refund
        existing = RefundRequest.objects.filter(
            inventory_entry=inventory_entry, status='pending',
        ).exists()
        if existing:
            raise StoreServiceError('A refund request is already pending for this item.')

        refund_request = RefundRequest.objects.create(
            user=user,
            inventory_entry=inventory_entry,
            reason=reason,
        )

        logger.info(
            'Refund request created: %s by user %s for item %s',
            refund_request.id, user.id, inventory_entry.item.name,
        )

        return refund_request

    @staticmethod
    @transaction.atomic
    def process_refund(refund_request_id, approve=True, admin_notes=''):
        """
        Process a refund request (admin action).

        If approved, issues Stripe refund and removes item from inventory.

        Args:
            refund_request_id: UUID of the RefundRequest.
            approve: Whether to approve or reject.
            admin_notes: Admin notes for the decision.

        Returns:
            Updated RefundRequest instance.
        """
        try:
            refund_req = RefundRequest.objects.select_related(
                'inventory_entry', 'inventory_entry__item',
            ).get(id=refund_request_id, status='pending')
        except RefundRequest.DoesNotExist:
            raise ItemNotFoundError('Refund request not found or already processed.')

        refund_req.admin_notes = admin_notes

        if not approve:
            refund_req.status = 'rejected'
            refund_req.save(update_fields=['status', 'admin_notes', 'updated_at'])
            return refund_req

        # Issue Stripe refund
        payment_intent_id = refund_req.inventory_entry.stripe_payment_intent_id
        if payment_intent_id:
            try:
                refund = stripe.Refund.create(payment_intent=payment_intent_id)
                refund_req.stripe_refund_id = refund.id
            except stripe.error.StripeError as e:
                logger.error('Stripe refund failed for %s: %s', refund_request_id, e)
                raise PaymentVerificationError(f'Stripe refund failed: {str(e)}')

        # Remove item from inventory
        refund_req.inventory_entry.delete()
        refund_req.status = 'refunded'
        refund_req.save(update_fields=['status', 'stripe_refund_id', 'admin_notes', 'updated_at'])

        logger.info('Refund processed: %s', refund_request_id)
        return refund_req
