"""
URL configuration for the Store app.

Routes:
    /categories/           - List store categories
    /categories/<slug>/    - Category detail with items
    /items/                - List store items
    /items/<slug>/         - Item detail
    /items/featured/       - Featured items
    /inventory/            - User inventory
    /inventory/<id>/equip/ - Equip/unequip item
    /inventory/history/    - Purchase history
    /wishlist/             - Wishlist CRUD
    /purchase/             - Initiate Stripe purchase
    /purchase/confirm/     - Confirm Stripe purchase
    /purchase/xp/          - Purchase with XP
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    GiftClaimView,
    GiftListView,
    GiftSendView,
    PurchaseConfirmView,
    PurchaseView,
    RefundAdminView,
    RefundRequestView,
    StoreCategoryViewSet,
    StoreItemViewSet,
    UserInventoryViewSet,
    WishlistViewSet,
    XPPurchaseView,
)

router = DefaultRouter()
router.register(r"categories", StoreCategoryViewSet, basename="store-category")
router.register(r"items", StoreItemViewSet, basename="store-item")
router.register(r"inventory", UserInventoryViewSet, basename="user-inventory")
router.register(r"wishlist", WishlistViewSet, basename="store-wishlist")

urlpatterns = [
    path("", include(router.urls)),
    path("purchase/", PurchaseView.as_view(), name="store-purchase"),
    path(
        "purchase/confirm/",
        PurchaseConfirmView.as_view(),
        name="store-purchase-confirm",
    ),
    path("purchase/xp/", XPPurchaseView.as_view(), name="store-purchase-xp"),
    # Gifting
    path("gifts/send/", GiftSendView.as_view(), name="store-gift-send"),
    path(
        "gifts/<uuid:gift_id>/claim/", GiftClaimView.as_view(), name="store-gift-claim"
    ),
    path("gifts/", GiftListView.as_view(), name="store-gift-list"),
    # Refunds
    path("refunds/", RefundRequestView.as_view(), name="store-refund"),
    # Admin refund management
    path("admin/refunds/", RefundAdminView.as_view(), name="store-refund-admin"),
]
