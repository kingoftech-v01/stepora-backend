"""
Custom DRF permissions for DreamPlanner.

Implements subscription-based access control for all features:
- Free: Limited dreams, no AI, no buddy, no circles, no vision, has ads
- Premium: Unlimited dreams, AI chat, plan generation, buddy, league, no ads
- Pro: Everything + vision boards, circles creation, advanced analytics
"""

from rest_framework import permissions


class IsEmailVerified(permissions.BasePermission):
    """
    Blocks access for users whose primary email is not verified.

    Returns 403 with a specific code so the frontend can show a
    "verify your email" gate instead of a generic error.

    Exempt paths (users need these before verifying):
    - /api/auth/          (login, register, verify-email, etc.)
    - /api/users/me/      (frontend needs user profile to check emailVerified)
    - /health/            (health checks)
    """

    message = 'Please verify your email address to use the platform.'
    code = 'email_not_verified'

    # Prefixes that are exempt from email verification
    _EXEMPT_PREFIXES = ('/api/auth/', '/health/', '/api/users/me/')

    def has_permission(self, request, view):
        # Skip for unauthenticated requests (let IsAuthenticated handle it)
        user = request.user
        if not user or not user.is_authenticated:
            return True

        # Skip for exempt paths
        path = request.path
        for prefix in self._EXEMPT_PREFIXES:
            if path.startswith(prefix):
                return True

        return user.emailaddress_set.filter(verified=True, primary=True).exists()


class IsOwner(permissions.BasePermission):
    """Permission to only allow owners of an object to access it."""

    def has_object_permission(self, request, view, obj):
        """Check if user is the owner of the object."""
        if hasattr(obj, 'user'):
            return obj.user == request.user
        if hasattr(obj, 'user1'):
            return obj.user1 == request.user or obj.user2 == request.user
        return False


class IsOwnerOrSharedWith(permissions.BasePermission):
    """Permission to allow owners and users the dream is shared with."""

    message = 'You do not have permission to access this resource.'

    def has_object_permission(self, request, view, obj):
        """Check if user is owner, shared-with, or collaborator."""
        if hasattr(obj, 'user') and obj.user == request.user:
            return True
        # Check SharedDream access
        try:
            from apps.dreams.models import SharedDream
            if SharedDream.objects.filter(
                dream=obj, shared_with=request.user
            ).exists():
                return True
        except Exception:
            pass
        # Check collaborator access
        try:
            from apps.dreams.models import DreamCollaborator
            if DreamCollaborator.objects.filter(
                dream=obj, user=request.user
            ).exists():
                return True
        except Exception:
            pass
        return False


class IsPremiumUser(permissions.BasePermission):
    """Permission to only allow premium or pro users."""

    message = 'This feature requires a Premium or Pro subscription.'

    def has_permission(self, request, view):
        """Check if user has premium or pro subscription."""
        return (
            request.user
            and request.user.is_authenticated
            and request.user.is_premium()
        )


class IsProUser(permissions.BasePermission):
    """Permission to only allow pro tier users."""

    message = 'This feature requires a Pro subscription.'

    def has_permission(self, request, view):
        """Check if user has pro subscription."""
        return (
            request.user
            and request.user.is_authenticated
            and request.user.subscription == 'pro'
        )


class CanCreateDream(permissions.BasePermission):
    """Permission to check if user can create another dream based on subscription."""

    message = 'You have reached the maximum number of active dreams for your subscription.'

    def has_permission(self, request, view):
        """Check dream creation limit based on subscription tier."""
        if request.method != 'POST':
            return True
        return (
            request.user
            and request.user.is_authenticated
            and request.user.can_create_dream()
        )


class CanUseAI(permissions.BasePermission):
    """Permission to restrict AI features to premium and pro users.

    Free users cannot use:
    - AI chat conversations
    - Dream plan generation
    - AI dream analysis
    - Motivational AI messages
    """

    message = 'AI features require a Premium or Pro subscription. Upgrade to unlock AI-powered dream planning.'

    def has_permission(self, request, view):
        """Check if user can access AI features."""
        return (
            request.user
            and request.user.is_authenticated
            and request.user.subscription in ('premium', 'pro')
        )


class CanUseBuddy(permissions.BasePermission):
    """Permission to restrict buddy matching to premium and pro users."""

    message = 'Dream Buddy matching requires a Premium or Pro subscription.'

    def has_permission(self, request, view):
        """Check if user can access buddy features."""
        return (
            request.user
            and request.user.is_authenticated
            and request.user.subscription in ('premium', 'pro')
        )


class CanUseCircles(permissions.BasePermission):
    """Permission to restrict circle creation to pro users.

    Joining existing circles is allowed for premium users.
    Creating circles requires pro subscription.
    """

    message = 'Creating circles requires a Pro subscription.'

    def has_permission(self, request, view):
        """Check if user can create circles (pro) or join (premium+)."""
        if request.method == 'POST':
            return (
                request.user
                and request.user.is_authenticated
                and request.user.subscription == 'pro'
            )
        # Reading/joining circles allowed for premium+
        return (
            request.user
            and request.user.is_authenticated
            and request.user.subscription in ('premium', 'pro')
        )


class CanUseVisionBoard(permissions.BasePermission):
    """Permission to restrict vision board generation to pro users."""

    message = 'Vision board generation requires a Pro subscription.'

    def has_permission(self, request, view):
        """Check if user can generate vision boards."""
        return (
            request.user
            and request.user.is_authenticated
            and request.user.subscription == 'pro'
        )


class CanUseLeague(permissions.BasePermission):
    """Permission to restrict league features to premium and pro users."""

    message = 'League features require a Premium or Pro subscription.'

    def has_permission(self, request, view):
        """Check if user can access league features."""
        return (
            request.user
            and request.user.is_authenticated
            and request.user.subscription in ('premium', 'pro')
        )


class CanUseStore(permissions.BasePermission):
    """Permission to restrict store purchases to premium and pro users.

    Browsing the store catalog is allowed for everyone (AllowAny on those views).
    Purchasing items (via Stripe, XP, or gifting) requires a paid subscription.
    """

    message = 'Store purchases require a Premium or Pro subscription.'

    def has_permission(self, request, view):
        """Check if user can make store purchases."""
        return (
            request.user
            and request.user.is_authenticated
            and request.user.subscription in ('premium', 'pro')
        )


class CanUseSocialFeed(permissions.BasePermission):
    """Permission to restrict the social activity feed to premium and pro users.

    Free users can only see encouragements received. Full feed requires premium+.
    """

    message = 'The full activity feed requires a Premium or Pro subscription.'

    def has_permission(self, request, view):
        """Check if user can access the full social feed."""
        return (
            request.user
            and request.user.is_authenticated
            and request.user.subscription in ('premium', 'pro')
        )
