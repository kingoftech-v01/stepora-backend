"""
URL configuration for the Buddies system.

Routes:
    /current                - Get current buddy pairing
    /<id>/progress          - Get progress comparison
    /find-match             - Find a compatible buddy
    /ai-matches             - AI-powered buddy matching with compatibility scoring
    /pair                   - Create a pairing
    /<id>/accept            - Accept a pending pairing
    /<id>/reject            - Reject a pending pairing
    /<id>/encourage         - Send encouragement
    /history                - Get pairing history
    /<id>/                  - End (DELETE) a pairing
    /contracts/             - List / create contracts
    /contracts/<id>/accept/ - Accept a contract
    /contracts/<id>/check-in/ - Submit a check-in
    /contracts/<id>/progress/ - View progress
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import BuddyViewSet, ContractViewSet

router = DefaultRouter()
router.register(r"", BuddyViewSet, basename="buddy")

contract_router = DefaultRouter()
contract_router.register(r"", ContractViewSet, basename="contract")

urlpatterns = [
    path("contracts/", include(contract_router.urls)),
    path("", include(router.urls)),
]
