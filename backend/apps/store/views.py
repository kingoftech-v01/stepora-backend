"""
Views for the Store app.

Provides API endpoints for browsing the store catalog, viewing item details,
managing user inventory, and processing purchases through Stripe.
Store browsing is publicly accessible; purchases and inventory management
require authentication.
"""

import logging

from rest_framework import viewsets, status, views
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.filters import SearchFilter, OrderingFilter
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiResponse

from .models import StoreCategory, StoreItem, UserInventory
from .serializers import (
    StoreCategorySerializer,
    StoreCategoryDetailSerializer,
    StoreItemSerializer,
    StoreItemDetailSerializer,
    UserInventorySerializer,
    PurchaseSerializer,
    PurchaseConfirmSerializer,
    EquipSerializer,
)
from .services import (
    StoreService,
    ItemNotFoundError,
    ItemAlreadyOwnedError,
    ItemNotActiveError,
    PaymentVerificationError,
    InventoryNotFoundError,
)

logger = logging.getLogger(__name__)


@extend_schema_view(
    list=extend_schema(
        summary='List store categories',
        description='Retrieve all active store categories with item counts. Public endpoint.',
        tags=['Store'],
    ),
    retrieve=extend_schema(
        summary='Get category details',
        description='Retrieve a single category with its active items. Public endpoint.',
        tags=['Store'],
    ),
)
class StoreCategoryViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for browsing store categories.

    Provides list and detail endpoints for store categories.
    The list view returns categories with item counts; the detail
    view includes the full list of active items in the category.
    Both endpoints are publicly accessible for browsing.
    """

    permission_classes = [AllowAny]
    lookup_field = 'slug'
    filter_backends = [SearchFilter, OrderingFilter]
    search_fields = ['name', 'description']
    ordering_fields = ['display_order', 'name']
    ordering = ['display_order']

    def get_queryset(self):
        """Return only active categories."""
        return StoreCategory.objects.filter(
            is_active=True
        ).prefetch_related('items')

    def get_serializer_class(self):
        """Return the appropriate serializer based on the action."""
        if self.action == 'retrieve':
            return StoreCategoryDetailSerializer
        return StoreCategorySerializer


@extend_schema_view(
    list=extend_schema(
        summary='List store items',
        description='Retrieve all active store items with filtering and search. Public endpoint.',
        tags=['Store'],
    ),
    retrieve=extend_schema(
        summary='Get item details',
        description='Retrieve detailed information about a specific store item. Public endpoint.',
        tags=['Store'],
    ),
)
class StoreItemViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for browsing store items.

    Provides list and detail endpoints for store items with filtering
    by category, item type, and rarity. Includes a custom action for
    featured items. Both endpoints are publicly accessible for browsing.
    """

    permission_classes = [AllowAny]
    lookup_field = 'slug'
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['category__slug', 'item_type', 'rarity']
    search_fields = ['name', 'description']
    ordering_fields = ['price', 'created_at', 'name', 'rarity']
    ordering = ['category', 'price']

    def get_queryset(self):
        """Return only active store items with related category."""
        return StoreItem.objects.filter(
            is_active=True
        ).select_related('category')

    def get_serializer_class(self):
        """Return the appropriate serializer based on the action."""
        if self.action == 'retrieve':
            return StoreItemDetailSerializer
        return StoreItemSerializer

    @extend_schema(
        summary='Get featured items',
        description=(
            'Retrieve a curated list of featured store items. '
            'Returns legendary and epic items as featured selections.'
        ),
        tags=['Store'],
        responses={200: StoreItemSerializer(many=True)},
    )
    @action(detail=False, methods=['get'])
    def featured(self, request):
        """
        Return featured store items.

        Featured items are selected from epic and legendary rarity tiers,
        limited to 10 items for the storefront highlight section.
        """
        featured_items = self.get_queryset().filter(
            rarity__in=['epic', 'legendary']
        ).order_by('-rarity', '-created_at')[:10]

        serializer = StoreItemSerializer(
            featured_items,
            many=True,
            context={'request': request},
        )
        return Response(serializer.data)


@extend_schema_view(
    list=extend_schema(
        summary='List user inventory',
        description='Retrieve all items owned by the authenticated user.',
        tags=['Store'],
    ),
    retrieve=extend_schema(
        summary='Get inventory item details',
        description='Retrieve details of a specific owned item.',
        tags=['Store'],
    ),
)
class UserInventoryViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for managing the authenticated user's inventory.

    Provides list and detail views for owned items, plus custom
    actions for equipping and unequipping items. Requires authentication.
    """

    serializer_class = UserInventorySerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['is_equipped', 'item__item_type']
    ordering_fields = ['purchased_at', 'is_equipped']
    ordering = ['-purchased_at']

    def get_queryset(self):
        """Return inventory items for the authenticated user."""
        return StoreService.get_user_inventory(self.request.user)

    @extend_schema(
        summary='Equip inventory item',
        description=(
            'Equip an item from the user inventory. Automatically unequips '
            'any other equipped item of the same type.'
        ),
        tags=['Store'],
        request=EquipSerializer,
        responses={
            200: UserInventorySerializer,
            400: OpenApiResponse(description='Validation error'),
            404: OpenApiResponse(description='Item not found in inventory'),
        },
    )
    @action(detail=True, methods=['post'])
    def equip(self, request, pk=None):
        """
        Equip or unequip an inventory item.

        Accepts a JSON body with {"equip": true/false} to toggle
        the equipped state. Only one item of each type can be
        equipped at a time.
        """
        serializer = EquipSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            if serializer.validated_data['equip']:
                inventory_entry = StoreService.equip_item(
                    user=request.user,
                    inventory_id=pk,
                )
            else:
                inventory_entry = StoreService.unequip_item(
                    user=request.user,
                    inventory_id=pk,
                )

            return Response(
                UserInventorySerializer(
                    inventory_entry,
                    context={'request': request},
                ).data,
                status=status.HTTP_200_OK,
            )

        except InventoryNotFoundError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_404_NOT_FOUND,
            )


class PurchaseView(views.APIView):
    """
    API view for initiating and confirming store purchases.

    Provides two endpoints:
    - POST /purchase/ : Create a Stripe PaymentIntent for an item
    - POST /purchase/confirm/ : Confirm the purchase after payment succeeds

    Both endpoints require authentication.
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary='Initiate purchase',
        description=(
            'Create a Stripe PaymentIntent for purchasing a store item. '
            'Returns the client secret needed to complete payment on the '
            'client side using Stripe SDK.'
        ),
        tags=['Store'],
        request=PurchaseSerializer,
        responses={
            201: OpenApiResponse(
                description='Payment intent created successfully',
            ),
            400: OpenApiResponse(description='Validation error'),
            409: OpenApiResponse(description='Item already owned'),
        },
    )
    def post(self, request):
        """
        Create a Stripe PaymentIntent for a store item purchase.

        The client receives a client_secret to complete the payment
        flow using Stripe's mobile SDK.
        """
        serializer = PurchaseSerializer(
            data=request.data,
            context={'request': request},
        )
        serializer.is_valid(raise_exception=True)

        item_id = serializer.validated_data['item_id']

        try:
            item = StoreItem.objects.get(id=item_id)
        except StoreItem.DoesNotExist:
            return Response(
                {'error': 'Store item not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            result = StoreService.create_payment_intent(
                user=request.user,
                item=item,
            )
            return Response(result, status=status.HTTP_201_CREATED)

        except ItemAlreadyOwnedError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_409_CONFLICT,
            )

        except ItemNotActiveError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        except PaymentVerificationError as e:
            logger.error('Payment intent creation failed: %s', str(e))
            return Response(
                {'error': str(e)},
                status=status.HTTP_502_BAD_GATEWAY,
            )


class PurchaseConfirmView(views.APIView):
    """
    API view for confirming a purchase after Stripe payment completion.

    Verifies the payment intent with Stripe and adds the item
    to the user's inventory upon successful verification.
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary='Confirm purchase',
        description=(
            'Confirm a store purchase after the client-side Stripe payment '
            'has succeeded. Verifies the payment with Stripe and adds the '
            'item to the user inventory.'
        ),
        tags=['Store'],
        request=PurchaseConfirmSerializer,
        responses={
            200: UserInventorySerializer,
            400: OpenApiResponse(description='Validation error or payment not completed'),
            404: OpenApiResponse(description='Item not found'),
            409: OpenApiResponse(description='Item already owned'),
        },
    )
    def post(self, request):
        """
        Confirm a purchase and add the item to the user's inventory.

        Verifies the Stripe PaymentIntent status and creates the
        inventory entry if payment was successful.
        """
        serializer = PurchaseConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        item_id = serializer.validated_data['item_id']
        payment_intent_id = serializer.validated_data['payment_intent_id']

        try:
            item = StoreItem.objects.get(id=item_id)
        except StoreItem.DoesNotExist:
            return Response(
                {'error': 'Store item not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            inventory_entry = StoreService.confirm_purchase(
                user=request.user,
                item=item,
                payment_intent_id=payment_intent_id,
            )

            return Response(
                UserInventorySerializer(
                    inventory_entry,
                    context={'request': request},
                ).data,
                status=status.HTTP_200_OK,
            )

        except ItemAlreadyOwnedError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_409_CONFLICT,
            )

        except PaymentVerificationError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )
