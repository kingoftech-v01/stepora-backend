"""
URL configuration for the Store app.

Defines the URL routing for store browsing, item details, user inventory
management, and the purchase flow endpoints. Uses DRF routers for
ViewSets and explicit paths for the purchase API views.
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    StoreCategoryViewSet,
    StoreItemViewSet,
    UserInventoryViewSet,
    PurchaseView,
    PurchaseConfirmView,
)

router = DefaultRouter()
router.register(r'categories', StoreCategoryViewSet, basename='store-category')
router.register(r'items', StoreItemViewSet, basename='store-item')
router.register(r'inventory', UserInventoryViewSet, basename='user-inventory')

urlpatterns = [
    path('', include(router.urls)),
    path('purchase/', PurchaseView.as_view(), name='store-purchase'),
    path('purchase/confirm/', PurchaseConfirmView.as_view(), name='store-purchase-confirm'),
]
