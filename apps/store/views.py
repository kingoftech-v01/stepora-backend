"""
Views for the Store app.

Provides API endpoints for browsing the store catalog, viewing item details,
managing user inventory, and processing purchases through Stripe.
Store browsing is publicly accessible; purchases and inventory management
require authentication.
"""

import logging

from django.utils import timezone
from django.utils.decorators import method_decorator
from django.utils.translation import gettext as _
from django.views.decorators.cache import cache_page
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import OpenApiResponse, extend_schema, extend_schema_view
from rest_framework import status, views, viewsets
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.permissions import AllowAny, IsAdminUser, IsAuthenticated
from rest_framework.response import Response

from core.permissions import CanUseStore

from .models import (
    Gift,
    RefundRequest,
    StoreCategory,
    StoreItem,
    UserInventory,
    Wishlist,
)
from .serializers import (
    EquipSerializer,
    GiftSendSerializer,
    GiftSerializer,
    ItemPreviewSerializer,
    PurchaseConfirmSerializer,
    PurchaseSerializer,
    RefundProcessSerializer,
    RefundRequestDisplaySerializer,
    RefundRequestSerializer,
    StoreCategoryDetailSerializer,
    StoreCategorySerializer,
    StoreItemDetailSerializer,
    StoreItemSerializer,
    UserInventorySerializer,
    WishlistSerializer,
    XPPurchaseSerializer,
)
from .services import (
    InsufficientXPError,
    InventoryNotFoundError,
    ItemAlreadyOwnedError,
    ItemNotActiveError,
    ItemNotFoundError,
    PaymentVerificationError,
    StoreService,
    StoreServiceError,
)

logger = logging.getLogger(__name__)


@extend_schema_view(
    list=extend_schema(
        summary="List store categories",
        description="Retrieve all active store categories with item counts. Public endpoint.",
        tags=["Store"],
    ),
    retrieve=extend_schema(
        summary="Get category details",
        description="Retrieve a single category with its active items. Public endpoint.",
        tags=["Store"],
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
    lookup_field = "slug"
    filter_backends = [SearchFilter, OrderingFilter]
    search_fields = ["name", "description"]
    ordering_fields = ["display_order", "name"]
    ordering = ["display_order"]

    def get_queryset(self):
        """Return only active categories."""
        if getattr(self, "swagger_fake_view", False):
            return StoreCategory.objects.none()
        return StoreCategory.objects.filter(is_active=True).prefetch_related("items")

    def get_serializer_class(self):
        """Return the appropriate serializer based on the action."""
        if self.action == "retrieve":
            return StoreCategoryDetailSerializer
        return StoreCategorySerializer


@extend_schema_view(
    list=extend_schema(
        summary="List store items",
        description="Retrieve all active store items with filtering and search. Public endpoint.",
        tags=["Store"],
    ),
    retrieve=extend_schema(
        summary="Get item details",
        description="Retrieve detailed information about a specific store item. Public endpoint.",
        tags=["Store"],
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
    lookup_field = "slug"
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]

    @method_decorator(cache_page(300))  # Cache for 5 minutes
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    filterset_fields = ["category__slug", "item_type", "rarity"]
    search_fields = ["name", "description"]
    ordering_fields = ["price", "created_at", "name", "rarity"]
    ordering = ["category", "price"]

    def get_queryset(self):
        """Return only active store items within their availability window."""
        if getattr(self, "swagger_fake_view", False):
            return StoreItem.objects.none()
        now = timezone.now()
        qs = StoreItem.objects.filter(is_active=True).select_related("category")

        # Filter out items outside their availability window
        qs = qs.exclude(available_from__isnull=False, available_from__gt=now)
        qs = qs.exclude(available_until__isnull=False, available_until__lt=now)

        return qs

    def get_serializer_class(self):
        """Return the appropriate serializer based on the action."""
        if self.action == "retrieve":
            return StoreItemDetailSerializer
        return StoreItemSerializer

    @extend_schema(
        summary="Get featured items",
        description=(
            "Retrieve a curated list of featured store items. "
            "Returns legendary and epic items as featured selections."
        ),
        tags=["Store"],
        responses={200: StoreItemSerializer(many=True)},
    )
    @action(detail=False, methods=["get"])
    def featured(self, request):
        """
        Return featured store items.

        Featured items are selected from epic and legendary rarity tiers,
        limited to 10 items for the storefront highlight section.
        """
        featured_items = (
            self.get_queryset()
            .filter(rarity__in=["epic", "legendary"])
            .order_by("-rarity", "-created_at")[:10]
        )

        serializer = StoreItemSerializer(
            featured_items,
            many=True,
            context={"request": request},
        )
        return Response(serializer.data)

    @extend_schema(
        summary="Get item preview",
        description=(
            "Retrieve the preview/try-before-buy configuration for a specific "
            "store item. Returns preview_type and preview_data needed to render "
            "a live preview of the item (theme colors, chat bubble styles, "
            "profile backgrounds, avatar frames, etc.)."
        ),
        tags=["Store"],
        responses={
            200: ItemPreviewSerializer,
            404: OpenApiResponse(description="Item not found or has no preview data."),
        },
    )
    @action(detail=True, methods=["get"])
    def preview(self, request, slug=None):
        """
        Return the preview configuration for a store item.

        Used by the frontend try-before-buy modal to render a live
        preview of themes, chat bubbles, avatar frames, etc.
        """
        item = self.get_object()

        if not item.preview_type and not item.preview_data:
            return Response(
                {"error": _("No preview available for this item.")},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = ItemPreviewSerializer(
            item,
            context={"request": request},
        )
        return Response(serializer.data)


@extend_schema_view(
    list=extend_schema(
        summary="List user inventory",
        description="Retrieve all items owned by the authenticated user.",
        tags=["Store"],
    ),
    retrieve=extend_schema(
        summary="Get inventory item details",
        description="Retrieve details of a specific owned item.",
        tags=["Store"],
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
    filterset_fields = ["is_equipped", "item__item_type"]
    ordering_fields = ["purchased_at", "is_equipped"]
    ordering = ["-purchased_at"]

    def get_queryset(self):
        """Return inventory items for the authenticated user."""
        if getattr(self, "swagger_fake_view", False):
            return UserInventory.objects.none()
        return StoreService.get_user_inventory(self.request.user)

    @extend_schema(
        summary="Equip inventory item",
        description=(
            "Equip an item from the user inventory. Automatically unequips "
            "any other equipped item of the same type."
        ),
        tags=["Store"],
        request=EquipSerializer,
        responses={
            200: UserInventorySerializer,
            400: OpenApiResponse(description="Validation error"),
            404: OpenApiResponse(description="Item not found in inventory"),
        },
    )
    @action(detail=True, methods=["post"])
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
            if serializer.validated_data["equip"]:
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
                    context={"request": request},
                ).data,
                status=status.HTTP_200_OK,
            )

        except InventoryNotFoundError as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_404_NOT_FOUND,
            )

    @extend_schema(
        summary="Purchase history",
        description="Retrieve paginated purchase history for the authenticated user.",
        tags=["Store"],
        responses={200: UserInventorySerializer(many=True)},
    )
    @action(detail=False, methods=["get"])
    def history(self, request):
        """Return purchase history ordered by purchase date."""
        queryset = self.get_queryset().order_by("-purchased_at")
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = UserInventorySerializer(
                page, many=True, context={"request": request}
            )
            return self.get_paginated_response(serializer.data)
        serializer = UserInventorySerializer(
            queryset, many=True, context={"request": request}
        )
        return Response(serializer.data)


@extend_schema_view(
    list=extend_schema(
        summary="List wishlist items",
        description="Retrieve all items on the authenticated user's wishlist.",
        tags=["Store"],
    ),
    create=extend_schema(
        summary="Add to wishlist",
        description="Add a store item to the authenticated user's wishlist.",
        tags=["Store"],
        responses={
            201: WishlistSerializer,
            400: OpenApiResponse(description="Validation error."),
        },
    ),
    destroy=extend_schema(
        summary="Remove from wishlist",
        description="Remove an item from the authenticated user's wishlist.",
        tags=["Store"],
        responses={
            204: None,
            404: OpenApiResponse(description="Wishlist item not found."),
        },
    ),
)
class WishlistViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing the user's wishlist.

    Provides list, create, and delete operations for wishlist items.
    """

    serializer_class = WishlistSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "post", "delete", "head", "options"]

    def get_queryset(self):
        """Return wishlist items for the authenticated user."""
        if getattr(self, "swagger_fake_view", False):
            return Wishlist.objects.none()
        return Wishlist.objects.filter(user=self.request.user).select_related(
            "item", "item__category"
        )

    def create(self, request, *args, **kwargs):
        """Add item to wishlist."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        item = StoreItem.objects.get(id=serializer.validated_data["item_id"])
        wishlist_entry = Wishlist.objects.create(user=request.user, item=item)
        return Response(
            WishlistSerializer(wishlist_entry, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )


class PurchaseView(views.APIView):
    """API view for initiating store purchases via Stripe. Requires premium+."""

    permission_classes = [IsAuthenticated, CanUseStore]
    throttle_scope = "store_purchase"  # SECURITY: rate limit purchase attempts (5/min)

    @extend_schema(
        summary="Initiate purchase",
        description=(
            "Create a Stripe PaymentIntent for purchasing a store item. "
            "Returns the client secret needed to complete payment on the "
            "client side using Stripe SDK."
        ),
        tags=["Store"],
        request=PurchaseSerializer,
        responses={
            201: OpenApiResponse(description="Payment intent created successfully"),
            400: OpenApiResponse(description="Validation error"),
            403: OpenApiResponse(description="Subscription required."),
            409: OpenApiResponse(description="Item already owned"),
            502: OpenApiResponse(description="Payment service error."),
        },
    )
    def post(self, request):
        """Create a Stripe PaymentIntent for a store item purchase."""
        serializer = PurchaseSerializer(
            data=request.data,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)

        item_id = serializer.validated_data["item_id"]

        try:
            item = StoreItem.objects.get(id=item_id)
        except StoreItem.DoesNotExist:
            return Response(
                {"error": _("Store item not found.")},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            result = StoreService.create_payment_intent(
                user=request.user,
                item=item,
            )
            return Response(result, status=status.HTTP_201_CREATED)

        except ItemAlreadyOwnedError as e:
            return Response({"error": str(e)}, status=status.HTTP_409_CONFLICT)

        except ItemNotActiveError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        except PaymentVerificationError as e:
            logger.error("Payment intent creation failed: %s", str(e))
            return Response({"error": str(e)}, status=status.HTTP_502_BAD_GATEWAY)


class PurchaseConfirmView(views.APIView):
    """API view for confirming a purchase after Stripe payment completion. Requires premium+."""

    permission_classes = [IsAuthenticated, CanUseStore]
    throttle_scope = "store_purchase"  # SECURITY: rate limit confirm attempts (5/min)

    @extend_schema(
        summary="Confirm purchase",
        description=(
            "Confirm a store purchase after the client-side Stripe payment "
            "has succeeded. Verifies the payment with Stripe and adds the "
            "item to the user inventory."
        ),
        tags=["Store"],
        request=PurchaseConfirmSerializer,
        responses={
            200: UserInventorySerializer,
            400: OpenApiResponse(
                description="Validation error or payment not completed"
            ),
            403: OpenApiResponse(description="Subscription required."),
            404: OpenApiResponse(description="Item not found"),
            409: OpenApiResponse(description="Item already owned"),
            502: OpenApiResponse(description="Payment service error."),
        },
    )
    def post(self, request):
        """Confirm a purchase and add the item to the user's inventory."""
        serializer = PurchaseConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        item_id = serializer.validated_data["item_id"]
        payment_intent_id = serializer.validated_data["payment_intent_id"]

        try:
            item = StoreItem.objects.get(id=item_id)
        except StoreItem.DoesNotExist:
            return Response(
                {"error": _("Store item not found.")},
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
                    context={"request": request},
                ).data,
                status=status.HTTP_200_OK,
            )

        except ItemAlreadyOwnedError as e:
            return Response({"error": str(e)}, status=status.HTTP_409_CONFLICT)

        except PaymentVerificationError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class XPPurchaseView(views.APIView):
    """API view for purchasing store items with XP. Requires premium+."""

    permission_classes = [IsAuthenticated, CanUseStore]

    @extend_schema(
        summary="Purchase with XP",
        description="Purchase a store item using XP instead of real money.",
        tags=["Store"],
        request=XPPurchaseSerializer,
        responses={
            200: UserInventorySerializer,
            400: OpenApiResponse(
                description="Insufficient XP or item not purchasable with XP"
            ),
            403: OpenApiResponse(description="Subscription required."),
            404: OpenApiResponse(description="Item not found"),
            409: OpenApiResponse(description="Item already owned"),
        },
    )
    def post(self, request):
        """Purchase a store item with XP."""
        serializer = XPPurchaseSerializer(
            data=request.data,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)

        item_id = serializer.validated_data["item_id"]

        try:
            item = StoreItem.objects.get(id=item_id)
        except StoreItem.DoesNotExist:
            return Response(
                {"error": _("Store item not found.")},
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
                    context={"request": request},
                ).data,
                status=status.HTTP_200_OK,
            )

        except ItemAlreadyOwnedError as e:
            return Response({"error": str(e)}, status=status.HTTP_409_CONFLICT)

        except ItemNotActiveError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        except InsufficientXPError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class GiftSendView(views.APIView):
    """Send a store item as a gift to another user. Requires premium+."""

    permission_classes = [IsAuthenticated, CanUseStore]

    @extend_schema(
        summary="Send gift",
        description="Purchase a store item and gift it to another user.",
        tags=["Store"],
        request=GiftSendSerializer,
        responses={
            201: dict,
            400: OpenApiResponse(description="Validation error."),
            403: OpenApiResponse(description="Subscription required."),
            404: OpenApiResponse(description="Resource not found."),
            502: OpenApiResponse(description="Payment service error."),
        },
    )
    def post(self, request):
        from apps.users.models import User

        serializer = GiftSendSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            item = StoreItem.objects.get(id=serializer.validated_data["item_id"])
        except StoreItem.DoesNotExist:
            return Response(
                {"error": _("Item not found.")}, status=status.HTTP_404_NOT_FOUND
            )

        try:
            recipient = User.objects.get(id=serializer.validated_data["recipient_id"])
        except User.DoesNotExist:
            return Response(
                {"error": _("Recipient not found.")}, status=status.HTTP_404_NOT_FOUND
            )

        try:
            result = StoreService.send_gift(
                sender=request.user,
                recipient=recipient,
                item=item,
                message=serializer.validated_data.get("message", ""),
            )
            return Response(result, status=status.HTTP_201_CREATED)

        except (ItemAlreadyOwnedError, ItemNotActiveError, StoreServiceError) as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except PaymentVerificationError as e:
            return Response({"error": str(e)}, status=status.HTTP_502_BAD_GATEWAY)


class GiftClaimView(views.APIView):
    """Claim a received gift."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Claim gift",
        description="Claim a gift and add the item to your inventory.",
        tags=["Store"],
        request=None,
        responses={
            200: UserInventorySerializer,
            400: OpenApiResponse(description="Validation error."),
            404: OpenApiResponse(description="Resource not found."),
        },
    )
    def post(self, request, gift_id):
        try:
            inventory_entry = StoreService.claim_gift(request.user, gift_id)
            return Response(
                UserInventorySerializer(
                    inventory_entry, context={"request": request}
                ).data,
            )
        except (ItemNotFoundError, ItemAlreadyOwnedError) as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class GiftListView(views.APIView):
    """List pending gifts for the current user."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="List my gifts",
        description="List pending (unclaimed) gifts received by the current user.",
        tags=["Store"],
        responses={200: GiftSerializer(many=True)},
    )
    def get(self, request):
        gifts = Gift.objects.filter(
            recipient=request.user,
            is_claimed=False,
        ).select_related("sender", "item", "item__category")
        serializer = GiftSerializer(gifts, many=True)
        return Response(serializer.data)


class RefundRequestView(views.APIView):
    """Request a refund for a purchased item."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Request refund",
        description="Submit a refund request for a purchased store item.",
        tags=["Store"],
        request=RefundRequestSerializer,
        responses={201: RefundRequestDisplaySerializer},
    )
    def post(self, request):
        serializer = RefundRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            refund_req = StoreService.request_refund(
                user=request.user,
                inventory_id=serializer.validated_data["inventory_id"],
                reason=serializer.validated_data["reason"],
            )
            return Response(
                RefundRequestDisplaySerializer(refund_req).data,
                status=status.HTTP_201_CREATED,
            )
        except (InventoryNotFoundError, StoreServiceError) as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @extend_schema(
        summary="List refund requests",
        description="List all refund requests for the current user.",
        tags=["Store"],
        responses={200: RefundRequestDisplaySerializer(many=True)},
    )
    def get(self, request):
        requests_qs = RefundRequest.objects.filter(
            user=request.user,
        ).select_related("inventory_entry", "inventory_entry__item")
        serializer = RefundRequestDisplaySerializer(requests_qs, many=True)
        return Response(serializer.data)


class RefundAdminView(views.APIView):
    """Admin-only endpoint for processing (approving/rejecting) refund requests."""

    permission_classes = [IsAuthenticated, IsAdminUser]

    @extend_schema(
        summary="List all refund requests (admin)",
        description="Retrieve all refund requests. Admin only.",
        tags=["Store Admin"],
        responses={200: RefundRequestDisplaySerializer(many=True)},
    )
    def get(self, request):
        refund_qs = RefundRequest.objects.select_related(
            "user",
            "inventory_entry",
            "inventory_entry__item",
        ).order_by("-created_at")

        status_filter = request.query_params.get("status")
        if status_filter:
            refund_qs = refund_qs.filter(status=status_filter)

        # Limit results to prevent unbounded queries
        limit = min(int(request.query_params.get("limit", 100)), 500)
        offset = max(int(request.query_params.get("offset", 0)), 0)
        total = refund_qs.count()
        refund_qs = refund_qs[offset : offset + limit]

        serializer = RefundRequestDisplaySerializer(refund_qs, many=True)
        return Response(
            {
                "count": total,
                "results": serializer.data,
            }
        )

    @extend_schema(
        summary="Process refund request (admin)",
        description="Approve or reject a pending refund request.",
        tags=["Store Admin"],
        request=RefundProcessSerializer,
        responses={
            200: RefundRequestDisplaySerializer,
            400: OpenApiResponse(description="Validation error or invalid state."),
            404: OpenApiResponse(description="Refund request not found."),
        },
    )
    def post(self, request):
        serializer = RefundProcessSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        refund_id = serializer.validated_data["refund_id"]

        try:
            refund_req = RefundRequest.objects.select_related(
                "inventory_entry",
                "inventory_entry__item",
                "user",
            ).get(id=refund_id)
        except RefundRequest.DoesNotExist:
            return Response(
                {"error": _("Refund request not found.")},
                status=status.HTTP_404_NOT_FOUND,
            )

        if refund_req.status != "pending":
            return Response(
                {"error": _("Only pending refund requests can be processed.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        action = serializer.validated_data["action"]
        admin_notes = serializer.validated_data.get("admin_notes", "")

        if action == "approve":
            try:
                StoreService.process_refund(
                    refund_request_id=refund_req.id,
                    approve=True,
                    admin_notes=admin_notes,
                )
                refund_req.refresh_from_db()
            except StoreServiceError as e:
                return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        else:
            try:
                StoreService.process_refund(
                    refund_request_id=refund_req.id,
                    approve=False,
                    admin_notes=admin_notes,
                )
                refund_req.refresh_from_db()
            except StoreServiceError as e:
                return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        logger.info(
            "Admin %s %sd refund request %s for user %s",
            request.user.email,
            action,
            refund_req.id,
            refund_req.user.email,
        )

        return Response(
            RefundRequestDisplaySerializer(refund_req).data,
            status=status.HTTP_200_OK,
        )
