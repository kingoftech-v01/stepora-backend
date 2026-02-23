"""
Views for the Store app.

Provides API endpoints for browsing the store catalog, viewing item details,
managing user inventory, and processing purchases through Stripe.
Store browsing is publicly accessible; purchases and inventory management
require authentication.
"""

import logging

from django.utils import timezone
from rest_framework import viewsets, status, views
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.filters import SearchFilter, OrderingFilter
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiResponse

from .models import StoreCategory, StoreItem, UserInventory, Wishlist, Gift, RefundRequest
from .serializers import (
    StoreCategorySerializer,
    StoreCategoryDetailSerializer,
    StoreItemSerializer,
    StoreItemDetailSerializer,
    UserInventorySerializer,
    PurchaseSerializer,
    PurchaseConfirmSerializer,
    EquipSerializer,
    WishlistSerializer,
    XPPurchaseSerializer,
    GiftSendSerializer,
    GiftSerializer,
    RefundRequestSerializer,
    RefundRequestDisplaySerializer,
)
from .services import (
    StoreService,
    StoreServiceError,
    ItemNotFoundError,
    ItemAlreadyOwnedError,
    ItemNotActiveError,
    PaymentVerificationError,
    InventoryNotFoundError,
    InsufficientXPError,
)

from core.permissions import CanUseStore

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
    Limited-time items are filtered by availability window.
    """

    permission_classes = [AllowAny]
    lookup_field = 'slug'
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['category__slug', 'item_type', 'rarity']
    search_fields = ['name', 'description']
    ordering_fields = ['price', 'created_at', 'name', 'rarity']
    ordering = ['category', 'price']

    def get_queryset(self):
        """Return only active store items within their availability window."""
        now = timezone.now()
        qs = StoreItem.objects.filter(
            is_active=True
        ).select_related('category')

        # Filter out items outside their availability window
        qs = qs.exclude(available_from__isnull=False, available_from__gt=now)
        qs = qs.exclude(available_until__isnull=False, available_until__lt=now)

        return qs

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
    actions for equipping/unequipping items and purchase history.
    Requires authentication.
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

    @extend_schema(
        summary='Purchase history',
        description='Retrieve paginated purchase history for the authenticated user.',
        tags=['Store'],
        responses={200: UserInventorySerializer(many=True)},
    )
    @action(detail=False, methods=['get'])
    def history(self, request):
        """Return purchase history ordered by purchase date."""
        queryset = self.get_queryset().order_by('-purchased_at')
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = UserInventorySerializer(page, many=True, context={'request': request})
            return self.get_paginated_response(serializer.data)
        serializer = UserInventorySerializer(queryset, many=True, context={'request': request})
        return Response(serializer.data)


class WishlistViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing the user's wishlist.

    Provides list, create, and delete operations for wishlist items.
    """

    serializer_class = WishlistSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ['get', 'post', 'delete', 'head', 'options']

    def get_queryset(self):
        """Return wishlist items for the authenticated user."""
        return Wishlist.objects.filter(
            user=self.request.user
        ).select_related('item', 'item__category')

    def create(self, request, *args, **kwargs):
        """Add item to wishlist."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        item = StoreItem.objects.get(id=serializer.validated_data['item_id'])
        wishlist_entry = Wishlist.objects.create(user=request.user, item=item)
        return Response(
            WishlistSerializer(wishlist_entry, context={'request': request}).data,
            status=status.HTTP_201_CREATED,
        )


class PurchaseView(views.APIView):
    """API view for initiating store purchases via Stripe. Requires premium+."""

    permission_classes = [IsAuthenticated, CanUseStore]

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
            201: OpenApiResponse(description='Payment intent created successfully'),
            400: OpenApiResponse(description='Validation error'),
            409: OpenApiResponse(description='Item already owned'),
        },
    )
    def post(self, request):
        """Create a Stripe PaymentIntent for a store item purchase."""
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
            return Response({'error': str(e)}, status=status.HTTP_409_CONFLICT)

        except ItemNotActiveError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

        except PaymentVerificationError as e:
            logger.error('Payment intent creation failed: %s', str(e))
            return Response({'error': str(e)}, status=status.HTTP_502_BAD_GATEWAY)


class PurchaseConfirmView(views.APIView):
    """API view for confirming a purchase after Stripe payment completion. Requires premium+."""

    permission_classes = [IsAuthenticated, CanUseStore]

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
        """Confirm a purchase and add the item to the user's inventory."""
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
            return Response({'error': str(e)}, status=status.HTTP_409_CONFLICT)

        except PaymentVerificationError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class XPPurchaseView(views.APIView):
    """API view for purchasing store items with XP. Requires premium+."""

    permission_classes = [IsAuthenticated, CanUseStore]

    @extend_schema(
        summary='Purchase with XP',
        description='Purchase a store item using XP instead of real money.',
        tags=['Store'],
        request=XPPurchaseSerializer,
        responses={
            200: UserInventorySerializer,
            400: OpenApiResponse(description='Insufficient XP or item not purchasable with XP'),
            404: OpenApiResponse(description='Item not found'),
            409: OpenApiResponse(description='Item already owned'),
        },
    )
    def post(self, request):
        """Purchase a store item with XP."""
        serializer = XPPurchaseSerializer(
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
            inventory_entry = StoreService.purchase_with_xp(
                user=request.user,
                item=item,
            )
            return Response(
                UserInventorySerializer(
                    inventory_entry,
                    context={'request': request},
                ).data,
                status=status.HTTP_200_OK,
            )

        except ItemAlreadyOwnedError as e:
            return Response({'error': str(e)}, status=status.HTTP_409_CONFLICT)

        except ItemNotActiveError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

        except InsufficientXPError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class GiftSendView(views.APIView):
    """Send a store item as a gift to another user. Requires premium+."""

    permission_classes = [IsAuthenticated, CanUseStore]

    @extend_schema(
        summary='Send gift',
        description='Purchase a store item and gift it to another user.',
        tags=['Store'],
        request=GiftSendSerializer,
        responses={201: dict, 400: OpenApiResponse(description='Error')},
    )
    def post(self, request):
        from apps.users.models import User

        serializer = GiftSendSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            item = StoreItem.objects.get(id=serializer.validated_data['item_id'])
        except StoreItem.DoesNotExist:
            return Response({'error': 'Item not found.'}, status=status.HTTP_404_NOT_FOUND)

        try:
            recipient = User.objects.get(id=serializer.validated_data['recipient_id'])
        except User.DoesNotExist:
            return Response({'error': 'Recipient not found.'}, status=status.HTTP_404_NOT_FOUND)

        try:
            result = StoreService.send_gift(
                sender=request.user,
                recipient=recipient,
                item=item,
                message=serializer.validated_data.get('message', ''),
            )
            return Response(result, status=status.HTTP_201_CREATED)

        except (ItemAlreadyOwnedError, ItemNotActiveError, StoreServiceError) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except PaymentVerificationError as e:
            return Response({'error': str(e)}, status=status.HTTP_502_BAD_GATEWAY)


class GiftClaimView(views.APIView):
    """Claim a received gift."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary='Claim gift',
        description='Claim a gift and add the item to your inventory.',
        tags=['Store'],
        responses={200: UserInventorySerializer},
    )
    def post(self, request, gift_id):
        try:
            inventory_entry = StoreService.claim_gift(request.user, gift_id)
            return Response(
                UserInventorySerializer(inventory_entry, context={'request': request}).data,
            )
        except (ItemNotFoundError, ItemAlreadyOwnedError) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class GiftListView(views.APIView):
    """List pending gifts for the current user."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary='List my gifts',
        description='List pending (unclaimed) gifts received by the current user.',
        tags=['Store'],
        responses={200: GiftSerializer(many=True)},
    )
    def get(self, request):
        gifts = Gift.objects.filter(
            recipient=request.user, is_claimed=False,
        ).select_related('sender', 'item', 'item__category')
        serializer = GiftSerializer(gifts, many=True)
        return Response(serializer.data)


class RefundRequestView(views.APIView):
    """Request a refund for a purchased item."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary='Request refund',
        description='Submit a refund request for a purchased store item.',
        tags=['Store'],
        request=RefundRequestSerializer,
        responses={201: RefundRequestDisplaySerializer},
    )
    def post(self, request):
        serializer = RefundRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            refund_req = StoreService.request_refund(
                user=request.user,
                inventory_id=serializer.validated_data['inventory_id'],
                reason=serializer.validated_data['reason'],
            )
            return Response(
                RefundRequestDisplaySerializer(refund_req).data,
                status=status.HTTP_201_CREATED,
            )
        except (InventoryNotFoundError, StoreServiceError) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @extend_schema(
        summary='List refund requests',
        description='List all refund requests for the current user.',
        tags=['Store'],
        responses={200: RefundRequestDisplaySerializer(many=True)},
    )
    def get(self, request):
        requests_qs = RefundRequest.objects.filter(
            user=request.user,
        ).select_related('inventory_entry', 'inventory_entry__item')
        serializer = RefundRequestDisplaySerializer(requests_qs, many=True)
        return Response(serializer.data)
