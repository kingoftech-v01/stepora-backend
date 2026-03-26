"""
Custom DRF permissions for Stepora.

All subscription-based permissions read from the user's active SubscriptionPlan
in the database (via User.get_active_plan()). This ensures feature access is
always driven by the plan configuration and can be changed without code deploys.

Status code semantics:
- 403 with code='subscription_required': user's plan doesn't include this feature
- 403 without special code: object-level ownership/role check failed
- 429: user has access but exceeded their usage quota (handled by throttles)
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

    message = "Please verify your email address to use the platform."
    code = "email_not_verified"

    # Prefixes that are exempt from email verification
    _EXEMPT_PREFIXES = ("/api/auth/", "/health/", "/api/users/me/")

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
        if hasattr(obj, "user"):
            return obj.user == request.user
        if hasattr(obj, "user1"):
            return obj.user1 == request.user or obj.user2 == request.user
        return False


class IsOwnerOrSharedWith(permissions.BasePermission):
    """Permission to allow owners and users the dream is shared with."""

    message = "You do not have permission to access this resource."

    def has_object_permission(self, request, view, obj):
        if hasattr(obj, "user") and obj.user == request.user:
            return True
        try:
            from apps.dreams.models import SharedDream

            if SharedDream.objects.filter(dream=obj, shared_with=request.user).exists():
                return True
        except (ImportError, AttributeError):
            pass
        try:
            from apps.dreams.models import DreamCollaborator

            if DreamCollaborator.objects.filter(dream=obj, user=request.user).exists():
                return True
        except (ImportError, AttributeError):
            pass
        return False


# ---------------------------------------------------------------------------
# Subscription-gated permissions
#
# Each permission reads its corresponding boolean field from SubscriptionPlan.
# The `required_tier` is a UI hint for the upgrade modal — it does NOT control
# access (the DB plan field does). It can be set dynamically in has_permission.
# ---------------------------------------------------------------------------


class IsPremiumUser(permissions.BasePermission):
    """Permission to only allow premium or pro users."""

    message = "This feature requires a higher-tier plan."
    code = "subscription_required"
    required_tier = "premium"
    feature_name = "Premium Features"

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        plan = request.user.get_active_plan()
        return plan is not None and plan.slug in ("premium", "pro")


class IsProUser(permissions.BasePermission):
    """Permission to only allow pro tier users."""

    message = "This feature requires a higher-tier plan."
    code = "subscription_required"
    required_tier = "pro"
    feature_name = "Pro Features"

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        plan = request.user.get_active_plan()
        return plan is not None and plan.slug == "pro"


class CanCreateDream(permissions.BasePermission):
    """Permission to check if user can create another dream based on plan."""

    message = "You have reached the maximum number of active dreams for your plan. Upgrade to create more."
    code = "subscription_required"
    required_tier = "premium"
    feature_name = "Dream Creation"

    def has_permission(self, request, view):
        if request.method != "POST":
            return True
        if not request.user or not request.user.is_authenticated:
            return False
        plan = request.user.get_active_plan()
        if not plan:
            return False
        if plan.dream_limit == -1:
            return True
        from apps.dreams.models import Dream

        active_dreams = Dream.objects.filter(user=request.user, status="active").count()
        if active_dreams < plan.dream_limit:
            return True
        # Set required_tier dynamically based on current plan
        if plan.slug == "premium":
            self.required_tier = "pro"
        else:
            self.required_tier = "premium"
        return False


class CanUseAI(permissions.BasePermission):
    """Permission to restrict AI features based on plan's has_ai flag."""

    message = "AI features are not available on your current plan. Upgrade to unlock AI-powered dream planning."
    code = "subscription_required"
    required_tier = "premium"
    feature_name = "AI Coaching"

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        plan = request.user.get_active_plan()
        return plan is not None and plan.has_ai


class CanUseBuddy(permissions.BasePermission):
    """Permission to restrict buddy matching based on plan's has_buddy flag."""

    message = "Dream Buddy matching is not available on your current plan."
    code = "subscription_required"
    required_tier = "premium"
    feature_name = "Dream Buddy"

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        plan = request.user.get_active_plan()
        return plan is not None and plan.has_buddy


class CanUseCircles(permissions.BasePermission):
    """Permission to restrict circles based on plan flags.

    Creating circles: requires has_circle_create (pro).
    Joining/reading: requires has_circles (premium+).
    """

    message = "Dream Circles are not available on your current plan."
    code = "subscription_required"
    required_tier = "premium"
    feature_name = "Dream Circles"

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        plan = request.user.get_active_plan()
        if not plan:
            return False
        # Circle creation (POST to the list endpoint) requires has_circle_create.
        # Other POST actions (join, post, react, vote, invite, chat, call)
        # only require has_circles (premium+).
        is_circle_create = (
            request.method == "POST"
            and getattr(view, "action", None) == "create"
        )
        if is_circle_create:
            if not plan.has_circle_create:
                self.required_tier = "pro"
                self.message = "Creating circles is not available on your current plan."
                return False
            return True
        if not plan.has_circles:
            self.required_tier = "premium"
            return False
        return True


class CanUseVisionBoard(permissions.BasePermission):
    """Permission to restrict vision board based on plan's has_vision_board flag."""

    message = "Vision board generation is not available on your current plan."
    code = "subscription_required"
    required_tier = "pro"
    feature_name = "Vision Board"

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        plan = request.user.get_active_plan()
        return plan is not None and plan.has_vision_board


class CanUseLeague(permissions.BasePermission):
    """Permission to restrict league features based on plan's has_league flag."""

    message = "League features are not available on your current plan."
    code = "subscription_required"
    required_tier = "premium"
    feature_name = "Leagues"

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        plan = request.user.get_active_plan()
        return plan is not None and plan.has_league


class CanUseStore(permissions.BasePermission):
    """Permission to restrict store purchases based on plan's has_store flag.

    Browsing the store catalog is allowed for everyone (AllowAny on those views).
    """

    message = "Store purchases are not available on your current plan."
    code = "subscription_required"
    required_tier = "premium"
    feature_name = "Store Purchases"

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        plan = request.user.get_active_plan()
        return plan is not None and plan.has_store


class CanUseSocialFeed(permissions.BasePermission):
    """Permission to restrict the social activity feed based on plan's has_social_feed flag."""

    message = "The full activity feed is not available on your current plan."
    code = "subscription_required"
    required_tier = "premium"
    feature_name = "Activity Feed"

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        plan = request.user.get_active_plan()
        return plan is not None and plan.has_social_feed


class CanMakePublicDream(permissions.BasePermission):
    """Permission to restrict making dreams public based on plan's has_public_dreams flag."""

    message = "Making dreams public requires a Premium or Pro plan."
    code = "subscription_required"
    required_tier = "premium"
    feature_name = "Public Dreams"

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        plan = request.user.get_active_plan()
        return plan is not None and plan.has_public_dreams
