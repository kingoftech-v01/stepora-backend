"""
Tests for the Store app.

Comprehensive test suite covering models, serializers, services, views,
and the full purchase flow with mocked Stripe interactions. Organized
into test classes by component for clarity.
"""

import uuid
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch, MagicMock

import pytest
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.users.models import User
from apps.store.models import StoreCategory, StoreItem, UserInventory
from apps.store.services import (
    StoreService,
    ItemNotFoundError,
    ItemAlreadyOwnedError,
    ItemNotActiveError,
    PaymentVerificationError,
    InventoryNotFoundError,
)
from apps.store.serializers import (
    StoreCategorySerializer,
    StoreItemSerializer,
    StoreItemDetailSerializer,
    UserInventorySerializer,
    PurchaseSerializer,
    PurchaseConfirmSerializer,
)


# ---------------------------------------------------------------------------
# Fixtures and helpers
# ---------------------------------------------------------------------------

@pytest.fixture
def store_user(db):
    """Create and return a premium test user for store tests.

    Uses a premium subscription so that purchase-related views gated by
    the ``CanUseStore`` permission (premium+ required) are accessible.
    """
    return User.objects.create(
        email=f'store_{uuid.uuid4().hex[:8]}@example.com',
        display_name='Store Test User',
        subscription='premium',
        subscription_ends=timezone.now() + timedelta(days=30),
    )


@pytest.fixture
def other_user(db):
    """Create a second test user for ownership tests."""
    return User.objects.create(
        email=f'other_{uuid.uuid4().hex[:8]}@example.com',
        display_name='Other Test User',
    )


@pytest.fixture
def auth_client(store_user):
    """Return an authenticated API client for store_user."""
    client = APIClient()
    client.force_authenticate(user=store_user)
    return client


@pytest.fixture
def category_badge_frames(db):
    """Create and return the Badge Frames category."""
    return StoreCategory.objects.create(
        name='Badge Frames',
        slug='badge-frames',
        description='Customize your badge frame.',
        icon='badge-frame',
        display_order=1,
        is_active=True,
    )


@pytest.fixture
def category_power_ups(db):
    """Create and return the Power-ups category."""
    return StoreCategory.objects.create(
        name='Power-ups',
        slug='power-ups',
        description='Boost your progress.',
        icon='power-up',
        display_order=5,
        is_active=True,
    )


@pytest.fixture
def inactive_category(db):
    """Create and return an inactive category."""
    return StoreCategory.objects.create(
        name='Archived Items',
        slug='archived-items',
        description='No longer available.',
        icon='archive',
        display_order=99,
        is_active=False,
    )


@pytest.fixture
def gold_frame(category_badge_frames):
    """Create and return the Gold Frame store item."""
    return StoreItem.objects.create(
        category=category_badge_frames,
        name='Gold Frame',
        slug='gold-frame',
        description='A golden frame.',
        price=Decimal('2.99'),
        item_type='badge_frame',
        rarity='rare',
        stripe_price_id='price_gold_test',
        metadata={'color': '#FFD700'},
    )


@pytest.fixture
def diamond_frame(category_badge_frames):
    """Create and return the Diamond Frame store item."""
    return StoreItem.objects.create(
        category=category_badge_frames,
        name='Diamond Frame',
        slug='diamond-frame',
        description='A diamond frame.',
        price=Decimal('4.99'),
        item_type='badge_frame',
        rarity='epic',
        stripe_price_id='price_diamond_test',
        metadata={'color': '#B9F2FF'},
    )


@pytest.fixture
def rainbow_frame(category_badge_frames):
    """Create and return the Rainbow Frame (legendary) store item."""
    return StoreItem.objects.create(
        category=category_badge_frames,
        name='Rainbow Frame',
        slug='rainbow-frame',
        description='A legendary rainbow frame.',
        price=Decimal('9.99'),
        item_type='badge_frame',
        rarity='legendary',
        stripe_price_id='price_rainbow_test',
        metadata={'animation': 'rainbow-cycle'},
    )


@pytest.fixture
def streak_shield(category_power_ups):
    """Create and return the Streak Shield power-up item."""
    return StoreItem.objects.create(
        category=category_power_ups,
        name='Streak Shield',
        slug='streak-shield',
        description='Protect your streak.',
        price=Decimal('0.99'),
        item_type='streak_shield',
        rarity='common',
        stripe_price_id='price_shield_test',
        metadata={'duration_days': 1},
    )


@pytest.fixture
def inactive_item(category_badge_frames):
    """Create and return an inactive store item."""
    return StoreItem.objects.create(
        category=category_badge_frames,
        name='Retired Frame',
        slug='retired-frame',
        description='No longer available.',
        price=Decimal('1.00'),
        item_type='badge_frame',
        rarity='common',
        is_active=False,
    )


@pytest.fixture
def owned_gold_frame(store_user, gold_frame):
    """Create an inventory entry for the store_user owning the gold frame."""
    return UserInventory.objects.create(
        user=store_user,
        item=gold_frame,
        stripe_payment_intent_id='pi_test_gold_owned',
        is_equipped=False,
    )


@pytest.fixture
def mock_stripe_payment_intent_create():
    """Mock stripe.PaymentIntent.create to return a fake intent."""
    with patch('apps.store.services.stripe.PaymentIntent.create') as mock_create:
        mock_create.return_value = MagicMock(
            id='pi_test_123456',
            client_secret='pi_test_123456_secret_abc',
            status='requires_payment_method',
        )
        yield mock_create


@pytest.fixture
def mock_stripe_payment_intent_retrieve_succeeded():
    """Mock stripe.PaymentIntent.retrieve to return a succeeded intent."""
    with patch('apps.store.services.stripe.PaymentIntent.retrieve') as mock_retrieve:
        mock_intent = MagicMock()
        mock_intent.id = 'pi_test_confirm_123'
        mock_intent.status = 'succeeded'
        mock_intent.amount = 299  # $2.99 in cents
        mock_intent.get.return_value = {
            'user_id': None,  # Will be set in individual tests
            'item_id': None,
        }
        mock_retrieve.return_value = mock_intent
        yield mock_retrieve, mock_intent


# ---------------------------------------------------------------------------
# Model tests
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestStoreCategoryModel:
    """Tests for the StoreCategory model."""

    def test_create_category(self, category_badge_frames):
        """Test creating a store category."""
        assert category_badge_frames.name == 'Badge Frames'
        assert category_badge_frames.slug == 'badge-frames'
        assert category_badge_frames.is_active is True
        assert category_badge_frames.display_order == 1

    def test_category_str_representation(self, category_badge_frames):
        """Test the string representation of a category."""
        assert str(category_badge_frames) == 'Badge Frames'

    def test_category_ordering(self, category_badge_frames, category_power_ups):
        """Test that categories are ordered by display_order."""
        categories = list(StoreCategory.objects.all())
        assert categories[0].display_order <= categories[-1].display_order

    def test_category_uuid_primary_key(self, category_badge_frames):
        """Test that category uses UUID as primary key."""
        assert isinstance(category_badge_frames.id, uuid.UUID)

    def test_category_unique_slug(self, category_badge_frames, db):
        """Test that category slugs must be unique."""
        from django.db import IntegrityError
        with pytest.raises(IntegrityError):
            StoreCategory.objects.create(
                name='Badge Frames Duplicate',
                slug='badge-frames',  # Duplicate slug
                display_order=2,
            )


@pytest.mark.django_db
class TestStoreItemModel:
    """Tests for the StoreItem model."""

    def test_create_item(self, gold_frame):
        """Test creating a store item."""
        assert gold_frame.name == 'Gold Frame'
        assert gold_frame.price == Decimal('2.99')
        assert gold_frame.item_type == 'badge_frame'
        assert gold_frame.rarity == 'rare'
        assert gold_frame.is_active is True

    def test_item_str_representation(self, gold_frame):
        """Test the string representation of a store item."""
        assert 'Gold Frame' in str(gold_frame)
        assert 'Rare' in str(gold_frame)
        assert '2.99' in str(gold_frame)

    def test_item_category_relationship(self, gold_frame, category_badge_frames):
        """Test that item is linked to its category."""
        assert gold_frame.category == category_badge_frames
        assert gold_frame in category_badge_frames.items.all()

    def test_item_uuid_primary_key(self, gold_frame):
        """Test that item uses UUID as primary key."""
        assert isinstance(gold_frame.id, uuid.UUID)

    def test_item_metadata_json_field(self, gold_frame):
        """Test that metadata is stored correctly as JSON."""
        assert gold_frame.metadata == {'color': '#FFD700'}

    def test_item_unique_slug(self, gold_frame, category_badge_frames, db):
        """Test that item slugs must be unique."""
        from django.db import IntegrityError
        with pytest.raises(IntegrityError):
            StoreItem.objects.create(
                category=category_badge_frames,
                name='Gold Frame Copy',
                slug='gold-frame',  # Duplicate slug
                price=Decimal('1.99'),
                item_type='badge_frame',
                rarity='common',
            )

    def test_item_type_choices(self, category_badge_frames):
        """Test that item_type accepts valid choices."""
        valid_types = ['badge_frame', 'theme_skin', 'avatar_decoration',
                       'chat_bubble', 'streak_shield', 'xp_booster']
        for item_type in valid_types:
            item = StoreItem.objects.create(
                category=category_badge_frames,
                name=f'Test {item_type}',
                slug=f'test-{item_type}',
                price=Decimal('1.00'),
                item_type=item_type,
                rarity='common',
            )
            assert item.item_type == item_type

    def test_rarity_choices(self, category_badge_frames):
        """Test that rarity accepts valid choices."""
        for rarity in ['common', 'rare', 'epic', 'legendary']:
            item = StoreItem.objects.create(
                category=category_badge_frames,
                name=f'Test {rarity}',
                slug=f'test-rarity-{rarity}',
                price=Decimal('1.00'),
                item_type='badge_frame',
                rarity=rarity,
            )
            assert item.rarity == rarity


@pytest.mark.django_db
class TestUserInventoryModel:
    """Tests for the UserInventory model."""

    def test_create_inventory_entry(self, owned_gold_frame, store_user, gold_frame):
        """Test creating an inventory entry."""
        assert owned_gold_frame.user == store_user
        assert owned_gold_frame.item == gold_frame
        assert owned_gold_frame.is_equipped is False
        assert owned_gold_frame.stripe_payment_intent_id == 'pi_test_gold_owned'

    def test_inventory_str_representation(self, owned_gold_frame):
        """Test the string representation of an inventory entry."""
        result = str(owned_gold_frame)
        assert 'Gold Frame' in result

    def test_inventory_equipped_str(self, store_user, gold_frame):
        """Test string representation when item is equipped."""
        entry = UserInventory.objects.create(
            user=store_user,
            item=gold_frame,
            stripe_payment_intent_id='pi_test',
            is_equipped=True,
        )
        # Clean up duplicate if exists
        UserInventory.objects.filter(user=store_user, item=gold_frame).exclude(id=entry.id).delete()
        assert '[EQUIPPED]' in str(entry)

    def test_inventory_uuid_primary_key(self, owned_gold_frame):
        """Test that inventory entry uses UUID as primary key."""
        assert isinstance(owned_gold_frame.id, uuid.UUID)

    def test_unique_together_user_item(self, store_user, gold_frame, owned_gold_frame, db):
        """Test that a user cannot own the same item twice."""
        from django.db import IntegrityError
        with pytest.raises(IntegrityError):
            UserInventory.objects.create(
                user=store_user,
                item=gold_frame,
                stripe_payment_intent_id='pi_duplicate',
            )

    def test_cascade_delete_user(self, store_user, owned_gold_frame):
        """Test that inventory is deleted when user is deleted."""
        inventory_id = owned_gold_frame.id
        store_user.delete()
        assert not UserInventory.objects.filter(id=inventory_id).exists()

    def test_cascade_delete_item(self, gold_frame, owned_gold_frame):
        """Test that inventory is deleted when item is deleted."""
        inventory_id = owned_gold_frame.id
        gold_frame.delete()
        assert not UserInventory.objects.filter(id=inventory_id).exists()


# ---------------------------------------------------------------------------
# Service tests
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestStoreServiceCreatePaymentIntent:
    """Tests for StoreService.create_payment_intent."""

    def test_successful_payment_intent_creation(
        self, store_user, gold_frame, mock_stripe_payment_intent_create
    ):
        """Test successful creation of a Stripe PaymentIntent."""
        result = StoreService.create_payment_intent(store_user, gold_frame)

        assert result['client_secret'] == 'pi_test_123456_secret_abc'
        assert result['payment_intent_id'] == 'pi_test_123456'
        assert result['amount'] == 299

        # Verify Stripe was called with correct parameters
        mock_stripe_payment_intent_create.assert_called_once()
        call_kwargs = mock_stripe_payment_intent_create.call_args[1]
        assert call_kwargs['amount'] == 299
        assert call_kwargs['currency'] == 'usd'
        assert call_kwargs['metadata']['user_id'] == str(store_user.id)
        assert call_kwargs['metadata']['item_id'] == str(gold_frame.id)

    def test_inactive_item_raises_error(self, store_user, inactive_item):
        """Test that purchasing an inactive item raises ItemNotActiveError."""
        with pytest.raises(ItemNotActiveError):
            StoreService.create_payment_intent(store_user, inactive_item)

    def test_already_owned_item_raises_error(
        self, store_user, gold_frame, owned_gold_frame
    ):
        """Test that purchasing an already-owned item raises ItemAlreadyOwnedError."""
        with pytest.raises(ItemAlreadyOwnedError):
            StoreService.create_payment_intent(store_user, gold_frame)

    def test_stripe_error_raises_payment_error(self, store_user, gold_frame):
        """Test that Stripe API errors are wrapped in PaymentVerificationError."""
        import stripe
        with patch('apps.store.services.stripe.PaymentIntent.create') as mock_create:
            mock_create.side_effect = stripe.error.StripeError('Test error')
            with pytest.raises(PaymentVerificationError):
                StoreService.create_payment_intent(store_user, gold_frame)


@pytest.mark.django_db
class TestStoreServiceConfirmPurchase:
    """Tests for StoreService.confirm_purchase."""

    def test_successful_purchase_confirmation(
        self, store_user, gold_frame, mock_stripe_payment_intent_retrieve_succeeded
    ):
        """Test successful purchase confirmation."""
        mock_retrieve, mock_intent = mock_stripe_payment_intent_retrieve_succeeded
        mock_intent.amount = 299  # $2.99
        mock_intent.get.return_value = {
            'user_id': str(store_user.id),
            'item_id': str(gold_frame.id),
        }

        inventory = StoreService.confirm_purchase(
            store_user, gold_frame, 'pi_test_confirm_123'
        )

        assert inventory.user == store_user
        assert inventory.item == gold_frame
        assert inventory.stripe_payment_intent_id == 'pi_test_confirm_123'
        assert inventory.is_equipped is False

    def test_already_owned_raises_error(
        self, store_user, gold_frame, owned_gold_frame,
        mock_stripe_payment_intent_retrieve_succeeded
    ):
        """Test that confirming purchase for already-owned item raises error."""
        with pytest.raises(ItemAlreadyOwnedError):
            StoreService.confirm_purchase(
                store_user, gold_frame, 'pi_test_duplicate'
            )

    def test_failed_payment_raises_error(self, store_user, gold_frame):
        """Test that a non-succeeded payment intent raises error."""
        with patch('apps.store.services.stripe.PaymentIntent.retrieve') as mock_retrieve:
            mock_intent = MagicMock()
            mock_intent.status = 'requires_payment_method'
            mock_retrieve.return_value = mock_intent
            with pytest.raises(PaymentVerificationError, match='Payment has not been completed'):
                StoreService.confirm_purchase(
                    store_user, gold_frame, 'pi_test_failed'
                )

    def test_amount_mismatch_raises_error(self, store_user, gold_frame):
        """Test that mismatched payment amount raises error."""
        with patch('apps.store.services.stripe.PaymentIntent.retrieve') as mock_retrieve:
            mock_intent = MagicMock()
            mock_intent.status = 'succeeded'
            mock_intent.amount = 999  # Wrong amount
            mock_intent.get.return_value = {
                'user_id': str(store_user.id),
                'item_id': str(gold_frame.id),
            }
            mock_retrieve.return_value = mock_intent
            with pytest.raises(PaymentVerificationError, match='amount does not match'):
                StoreService.confirm_purchase(
                    store_user, gold_frame, 'pi_test_wrong_amount'
                )

    def test_user_mismatch_raises_error(self, store_user, gold_frame):
        """Test that mismatched user ID raises error."""
        with patch('apps.store.services.stripe.PaymentIntent.retrieve') as mock_retrieve:
            mock_intent = MagicMock()
            mock_intent.status = 'succeeded'
            mock_intent.amount = 299
            mock_intent.get.return_value = {
                'user_id': str(uuid.uuid4()),  # Different user
                'item_id': str(gold_frame.id),
            }
            mock_retrieve.return_value = mock_intent
            with pytest.raises(PaymentVerificationError, match='user mismatch'):
                StoreService.confirm_purchase(
                    store_user, gold_frame, 'pi_test_wrong_user'
                )

    def test_stripe_retrieve_error(self, store_user, gold_frame):
        """Test that Stripe retrieval error is handled."""
        import stripe
        with patch('apps.store.services.stripe.PaymentIntent.retrieve') as mock_retrieve:
            mock_retrieve.side_effect = stripe.error.StripeError('API down')
            with pytest.raises(PaymentVerificationError):
                StoreService.confirm_purchase(
                    store_user, gold_frame, 'pi_test_stripe_error'
                )


@pytest.mark.django_db
class TestStoreServiceInventory:
    """Tests for StoreService inventory management methods."""

    def test_get_user_inventory(self, store_user, owned_gold_frame):
        """Test retrieving a user's inventory."""
        inventory = StoreService.get_user_inventory(store_user)
        assert inventory.count() == 1
        assert inventory.first().item.name == 'Gold Frame'

    def test_get_empty_inventory(self, store_user):
        """Test retrieving inventory for user with no items."""
        inventory = StoreService.get_user_inventory(store_user)
        assert inventory.count() == 0

    def test_equip_item(self, store_user, owned_gold_frame):
        """Test equipping an item."""
        result = StoreService.equip_item(store_user, owned_gold_frame.id)
        assert result.is_equipped is True

    def test_equip_item_unequips_same_type(
        self, store_user, gold_frame, diamond_frame, category_badge_frames
    ):
        """Test that equipping an item unequips others of the same type."""
        inv_gold = UserInventory.objects.create(
            user=store_user,
            item=gold_frame,
            stripe_payment_intent_id='pi_gold',
            is_equipped=True,
        )
        inv_diamond = UserInventory.objects.create(
            user=store_user,
            item=diamond_frame,
            stripe_payment_intent_id='pi_diamond',
            is_equipped=False,
        )

        # Equip diamond - should unequip gold
        StoreService.equip_item(store_user, inv_diamond.id)

        inv_gold.refresh_from_db()
        inv_diamond.refresh_from_db()

        assert inv_gold.is_equipped is False
        assert inv_diamond.is_equipped is True

    def test_equip_nonexistent_item_raises_error(self, store_user):
        """Test equipping a non-existent inventory item raises error."""
        fake_id = uuid.uuid4()
        with pytest.raises(InventoryNotFoundError):
            StoreService.equip_item(store_user, fake_id)

    def test_equip_other_users_item_raises_error(
        self, other_user, owned_gold_frame
    ):
        """Test that a user cannot equip another user's item."""
        with pytest.raises(InventoryNotFoundError):
            StoreService.equip_item(other_user, owned_gold_frame.id)

    def test_unequip_item(self, store_user, gold_frame):
        """Test unequipping an item."""
        inv = UserInventory.objects.create(
            user=store_user,
            item=gold_frame,
            stripe_payment_intent_id='pi_test',
            is_equipped=True,
        )
        result = StoreService.unequip_item(store_user, inv.id)
        assert result.is_equipped is False

    def test_unequip_nonexistent_raises_error(self, store_user):
        """Test unequipping a non-existent item raises error."""
        with pytest.raises(InventoryNotFoundError):
            StoreService.unequip_item(store_user, uuid.uuid4())


# ---------------------------------------------------------------------------
# View tests
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestStoreCategoryViewSet:
    """Tests for the StoreCategoryViewSet endpoints."""

    def test_list_categories(self, client, category_badge_frames, category_power_ups):
        """Test listing active categories (public endpoint)."""
        response = client.get('/api/store/categories/')
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        # Paginated response
        results = data.get('results', data)
        assert len(results) >= 2

    def test_list_excludes_inactive_categories(
        self, client, category_badge_frames, inactive_category
    ):
        """Test that inactive categories are excluded from listing."""
        response = client.get('/api/store/categories/')
        data = response.json()
        results = data.get('results', data)
        slugs = [c['slug'] for c in results]
        assert 'archived-items' not in slugs

    def test_retrieve_category_by_slug(self, client, category_badge_frames, gold_frame):
        """Test retrieving a single category by slug with items."""
        response = client.get(f'/api/store/categories/{category_badge_frames.slug}/')
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data['name'] == 'Badge Frames'
        assert 'items' in data

    def test_category_is_public(self, client, category_badge_frames):
        """Test that categories are accessible without authentication."""
        response = client.get('/api/store/categories/')
        assert response.status_code == status.HTTP_200_OK


@pytest.mark.django_db
class TestStoreItemViewSet:
    """Tests for the StoreItemViewSet endpoints."""

    def test_list_items(self, client, gold_frame, diamond_frame, streak_shield):
        """Test listing active store items."""
        response = client.get('/api/store/items/')
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        results = data.get('results', data)
        assert len(results) >= 3

    def test_list_excludes_inactive_items(self, client, gold_frame, inactive_item):
        """Test that inactive items are excluded from listing."""
        response = client.get('/api/store/items/')
        data = response.json()
        results = data.get('results', data)
        slugs = [i['slug'] for i in results]
        assert 'retired-frame' not in slugs

    def test_retrieve_item_by_slug(self, client, gold_frame):
        """Test retrieving a single item by slug."""
        response = client.get(f'/api/store/items/{gold_frame.slug}/')
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data['name'] == 'Gold Frame'
        assert data['price'] == '2.99'
        assert data['rarity'] == 'rare'

    def test_filter_items_by_item_type(self, client, gold_frame, streak_shield):
        """Test filtering items by item_type."""
        response = client.get('/api/store/items/?item_type=badge_frame')
        data = response.json()
        results = data.get('results', data)
        for item in results:
            assert item['item_type'] == 'badge_frame'

    def test_filter_items_by_rarity(self, client, gold_frame, diamond_frame):
        """Test filtering items by rarity."""
        response = client.get('/api/store/items/?rarity=epic')
        data = response.json()
        results = data.get('results', data)
        for item in results:
            assert item['rarity'] == 'epic'

    def test_featured_items(self, client, gold_frame, diamond_frame, rainbow_frame):
        """Test the featured items endpoint returns epic/legendary items."""
        response = client.get('/api/store/items/featured/')
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        # Featured should include epic and legendary items
        for item in data:
            assert item['rarity'] in ['epic', 'legendary']

    def test_items_are_public(self, client, gold_frame):
        """Test that items are accessible without authentication."""
        response = client.get('/api/store/items/')
        assert response.status_code == status.HTTP_200_OK

    def test_search_items(self, client, gold_frame, diamond_frame):
        """Test searching items by name."""
        response = client.get('/api/store/items/?search=Gold')
        data = response.json()
        results = data.get('results', data)
        assert len(results) >= 1
        assert any('Gold' in item['name'] for item in results)


@pytest.mark.django_db
class TestUserInventoryViewSet:
    """Tests for the UserInventoryViewSet endpoints."""

    def test_list_inventory_authenticated(self, auth_client, owned_gold_frame):
        """Test listing inventory for authenticated user."""
        response = auth_client.get('/api/store/inventory/')
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        results = data.get('results', data)
        assert len(results) == 1

    def test_list_inventory_unauthenticated(self, client):
        """Test that unauthenticated users cannot access inventory."""
        response = client.get('/api/store/inventory/')
        assert response.status_code in [
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
        ]

    def test_inventory_shows_only_own_items(
        self, auth_client, owned_gold_frame, other_user, diamond_frame
    ):
        """Test that inventory only shows the authenticated user's items."""
        # Create inventory for another user
        UserInventory.objects.create(
            user=other_user,
            item=diamond_frame,
            stripe_payment_intent_id='pi_other',
        )

        response = auth_client.get('/api/store/inventory/')
        data = response.json()
        results = data.get('results', data)
        assert len(results) == 1
        assert results[0]['item']['name'] == 'Gold Frame'

    def test_equip_item_via_api(self, auth_client, owned_gold_frame):
        """Test equipping an item through the API."""
        response = auth_client.post(
            f'/api/store/inventory/{owned_gold_frame.id}/equip/',
            {'equip': True},
            format='json',
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.json()['is_equipped'] is True

    def test_unequip_item_via_api(self, auth_client, store_user, gold_frame):
        """Test unequipping an item through the API."""
        inv = UserInventory.objects.create(
            user=store_user,
            item=gold_frame,
            stripe_payment_intent_id='pi_test',
            is_equipped=True,
        )
        response = auth_client.post(
            f'/api/store/inventory/{inv.id}/equip/',
            {'equip': False},
            format='json',
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.json()['is_equipped'] is False

    def test_equip_nonexistent_inventory(self, auth_client):
        """Test equipping a non-existent inventory item returns 404."""
        fake_id = uuid.uuid4()
        response = auth_client.post(
            f'/api/store/inventory/{fake_id}/equip/',
            {'equip': True},
            format='json',
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_filter_inventory_by_equipped(
        self, auth_client, store_user, gold_frame, diamond_frame
    ):
        """Test filtering inventory by equipped status."""
        UserInventory.objects.create(
            user=store_user,
            item=gold_frame,
            stripe_payment_intent_id='pi_1',
            is_equipped=True,
        )
        UserInventory.objects.create(
            user=store_user,
            item=diamond_frame,
            stripe_payment_intent_id='pi_2',
            is_equipped=False,
        )

        response = auth_client.get('/api/store/inventory/?is_equipped=true')
        data = response.json()
        results = data.get('results', data)
        for inv in results:
            assert inv['is_equipped'] is True


@pytest.mark.django_db
class TestPurchaseView:
    """Tests for the PurchaseView endpoint."""

    def test_create_payment_intent(
        self, auth_client, gold_frame, mock_stripe_payment_intent_create
    ):
        """Test creating a payment intent for a store item."""
        response = auth_client.post(
            '/api/store/purchase/',
            {'item_id': str(gold_frame.id)},
            format='json',
        )
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert 'client_secret' in data
        assert 'payment_intent_id' in data
        assert 'amount' in data

    def test_purchase_unauthenticated(self, client, gold_frame):
        """Test that unauthenticated users cannot purchase."""
        response = client.post(
            '/api/store/purchase/',
            {'item_id': str(gold_frame.id)},
            format='json',
        )
        assert response.status_code in [
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
        ]

    def test_purchase_nonexistent_item(self, auth_client):
        """Test purchasing a non-existent item returns validation error."""
        response = auth_client.post(
            '/api/store/purchase/',
            {'item_id': str(uuid.uuid4())},
            format='json',
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_purchase_already_owned_item(
        self, auth_client, gold_frame, owned_gold_frame
    ):
        """Test purchasing an already-owned item returns error."""
        response = auth_client.post(
            '/api/store/purchase/',
            {'item_id': str(gold_frame.id)},
            format='json',
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_purchase_inactive_item(
        self, auth_client, inactive_item, mock_stripe_payment_intent_create
    ):
        """Test purchasing an inactive item returns error."""
        response = auth_client.post(
            '/api/store/purchase/',
            {'item_id': str(inactive_item.id)},
            format='json',
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_purchase_missing_item_id(self, auth_client):
        """Test that missing item_id returns validation error."""
        response = auth_client.post(
            '/api/store/purchase/',
            {},
            format='json',
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
class TestPurchaseConfirmView:
    """Tests for the PurchaseConfirmView endpoint."""

    def test_confirm_purchase_success(
        self, auth_client, store_user, gold_frame,
        mock_stripe_payment_intent_retrieve_succeeded,
    ):
        """Test successful purchase confirmation."""
        mock_retrieve, mock_intent = mock_stripe_payment_intent_retrieve_succeeded
        mock_intent.amount = 299
        mock_intent.get.return_value = {
            'user_id': str(store_user.id),
            'item_id': str(gold_frame.id),
        }

        response = auth_client.post(
            '/api/store/purchase/confirm/',
            {
                'item_id': str(gold_frame.id),
                'payment_intent_id': 'pi_test_confirm_123',
            },
            format='json',
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data['item']['name'] == 'Gold Frame'
        assert data['is_equipped'] is False

        # Verify inventory was created
        assert UserInventory.objects.filter(
            user=store_user,
            item=gold_frame,
        ).exists()

    def test_confirm_unauthenticated(self, client, gold_frame):
        """Test that unauthenticated users cannot confirm purchase."""
        response = client.post(
            '/api/store/purchase/confirm/',
            {
                'item_id': str(gold_frame.id),
                'payment_intent_id': 'pi_test',
            },
            format='json',
        )
        assert response.status_code in [
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
        ]

    def test_confirm_invalid_payment_intent_format(self, auth_client, gold_frame):
        """Test that invalid payment intent ID format is rejected."""
        response = auth_client.post(
            '/api/store/purchase/confirm/',
            {
                'item_id': str(gold_frame.id),
                'payment_intent_id': 'invalid_format',
            },
            format='json',
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_confirm_already_owned_item(
        self, auth_client, gold_frame, owned_gold_frame,
        mock_stripe_payment_intent_retrieve_succeeded,
    ):
        """Test confirming purchase for already-owned item returns error."""
        response = auth_client.post(
            '/api/store/purchase/confirm/',
            {
                'item_id': str(gold_frame.id),
                'payment_intent_id': 'pi_test_duplicate',
            },
            format='json',
        )
        assert response.status_code == status.HTTP_409_CONFLICT

    def test_confirm_nonexistent_item(self, auth_client):
        """Test confirming purchase for non-existent item returns error."""
        response = auth_client.post(
            '/api/store/purchase/confirm/',
            {
                'item_id': str(uuid.uuid4()),
                'payment_intent_id': 'pi_test_noitem',
            },
            format='json',
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_confirm_failed_payment(self, auth_client, gold_frame):
        """Test confirming a failed payment returns error."""
        with patch('apps.store.services.stripe.PaymentIntent.retrieve') as mock_retrieve:
            mock_intent = MagicMock()
            mock_intent.status = 'requires_payment_method'
            mock_retrieve.return_value = mock_intent

            response = auth_client.post(
                '/api/store/purchase/confirm/',
                {
                    'item_id': str(gold_frame.id),
                    'payment_intent_id': 'pi_test_failed_payment',
                },
                format='json',
            )
            assert response.status_code == status.HTTP_400_BAD_REQUEST


# ---------------------------------------------------------------------------
# Serializer tests
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestSerializers:
    """Tests for store serializers."""

    def test_store_item_serializer(self, gold_frame):
        """Test StoreItemSerializer output."""
        serializer = StoreItemSerializer(gold_frame)
        data = serializer.data
        assert data['name'] == 'Gold Frame'
        assert data['price'] == '2.99'
        assert data['rarity'] == 'rare'
        assert data['rarity_display'] == 'Rare'
        assert data['item_type_display'] == 'Badge Frame'
        assert data['category_name'] == 'Badge Frames'

    def test_store_category_serializer(self, category_badge_frames, gold_frame):
        """Test StoreCategorySerializer output."""
        serializer = StoreCategorySerializer(category_badge_frames)
        data = serializer.data
        assert data['name'] == 'Badge Frames'
        assert data['items_count'] == 1

    def test_user_inventory_serializer(self, owned_gold_frame):
        """Test UserInventorySerializer output."""
        serializer = UserInventorySerializer(owned_gold_frame)
        data = serializer.data
        assert data['is_equipped'] is False
        assert data['item']['name'] == 'Gold Frame'

    def test_purchase_serializer_valid(self, gold_frame):
        """Test PurchaseSerializer with valid data."""
        serializer = PurchaseSerializer(data={'item_id': str(gold_frame.id)})
        assert serializer.is_valid()

    def test_purchase_serializer_invalid_item(self):
        """Test PurchaseSerializer with non-existent item."""
        serializer = PurchaseSerializer(data={'item_id': str(uuid.uuid4())})
        assert not serializer.is_valid()
        assert 'item_id' in serializer.errors

    def test_purchase_serializer_inactive_item(self, inactive_item):
        """Test PurchaseSerializer rejects inactive items."""
        serializer = PurchaseSerializer(data={'item_id': str(inactive_item.id)})
        assert not serializer.is_valid()

    def test_purchase_confirm_serializer_valid(self, gold_frame):
        """Test PurchaseConfirmSerializer with valid data."""
        serializer = PurchaseConfirmSerializer(data={
            'item_id': str(gold_frame.id),
            'payment_intent_id': 'pi_test_valid',
        })
        assert serializer.is_valid()

    def test_purchase_confirm_serializer_invalid_pi_format(self, gold_frame):
        """Test PurchaseConfirmSerializer rejects invalid payment intent format."""
        serializer = PurchaseConfirmSerializer(data={
            'item_id': str(gold_frame.id),
            'payment_intent_id': 'invalid_no_pi_prefix',
        })
        assert not serializer.is_valid()
        assert 'payment_intent_id' in serializer.errors


# ---------------------------------------------------------------------------
# Full purchase flow integration test
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestFullPurchaseFlow:
    """End-to-end test for the complete purchase flow."""

    def test_complete_purchase_flow(self, auth_client, store_user, gold_frame):
        """
        Test the complete purchase flow:
        1. Browse store items
        2. Create payment intent
        3. Confirm purchase
        4. View in inventory
        5. Equip item
        """
        # Step 1: Browse items
        response = auth_client.get('/api/store/items/')
        assert response.status_code == status.HTTP_200_OK

        # Step 2: Create payment intent
        with patch('apps.store.services.stripe.PaymentIntent.create') as mock_create:
            mock_create.return_value = MagicMock(
                id='pi_flow_test_123',
                client_secret='pi_flow_test_123_secret',
                status='requires_payment_method',
            )

            response = auth_client.post(
                '/api/store/purchase/',
                {'item_id': str(gold_frame.id)},
                format='json',
            )
            assert response.status_code == status.HTTP_201_CREATED
            payment_data = response.json()
            assert payment_data['payment_intent_id'] == 'pi_flow_test_123'

        # Step 3: Confirm purchase (simulate successful Stripe payment)
        with patch('apps.store.services.stripe.PaymentIntent.retrieve') as mock_retrieve:
            mock_intent = MagicMock()
            mock_intent.id = 'pi_flow_test_123'
            mock_intent.status = 'succeeded'
            mock_intent.amount = 299
            mock_intent.get.return_value = {
                'user_id': str(store_user.id),
                'item_id': str(gold_frame.id),
            }
            mock_retrieve.return_value = mock_intent

            response = auth_client.post(
                '/api/store/purchase/confirm/',
                {
                    'item_id': str(gold_frame.id),
                    'payment_intent_id': 'pi_flow_test_123',
                },
                format='json',
            )
            assert response.status_code == status.HTTP_200_OK
            inventory_data = response.json()
            inventory_id = inventory_data['id']

        # Step 4: View inventory
        response = auth_client.get('/api/store/inventory/')
        assert response.status_code == status.HTTP_200_OK
        inv_data = response.json()
        results = inv_data.get('results', inv_data)
        assert len(results) == 1
        assert results[0]['item']['name'] == 'Gold Frame'

        # Step 5: Equip item
        response = auth_client.post(
            f'/api/store/inventory/{inventory_id}/equip/',
            {'equip': True},
            format='json',
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.json()['is_equipped'] is True

        # Verify database state
        inventory = UserInventory.objects.get(id=inventory_id)
        assert inventory.is_equipped is True
        assert inventory.user == store_user
        assert inventory.item == gold_frame
