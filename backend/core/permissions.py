"""
Custom DRF permissions for DreamPlanner.
"""

from rest_framework import permissions


class IsOwner(permissions.BasePermission):
    """Permission to only allow owners of an object to access it."""

    def has_object_permission(self, request, view, obj):
        """Check if user is the owner."""
        # Check if object has user attribute
        if hasattr(obj, 'user'):
            return obj.user == request.user
        return False


class IsPremiumUser(permissions.BasePermission):
    """Permission to only allow premium users."""

    message = 'This feature requires a premium subscription.'

    def has_permission(self, request, view):
        """Check if user has premium subscription."""
        return request.user and request.user.is_authenticated and request.user.is_premium()


class CanCreateDream(permissions.BasePermission):
    """Permission to check if user can create another dream."""

    message = 'You have reached the maximum number of active dreams for your subscription.'

    def has_permission(self, request, view):
        """Check if user can create another dream."""
        if request.method != 'POST':
            return True

        return request.user and request.user.is_authenticated and request.user.can_create_dream()
