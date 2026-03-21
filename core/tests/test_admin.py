"""
Tests for Django admin registrations and admin view functionality.

Verifies that:
- All project models are registered in admin
- Admin changelist views load without errors
- Search fields work on all admin classes
- Filters work
- Key admin actions work
"""

import pytest
from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from django.test import RequestFactory
from django.urls import reverse

User = get_user_model()


# ── Models that should be registered ────────────────────────────────────

# Comprehensive list of all project models that have admin registrations.
# Inline-only models (PromotionPlanDiscount, LeagueGroupMembership) are
# excluded since they do not appear as top-level registrations.
EXPECTED_ADMIN_MODELS = [
    # users
    ("users", "User"),
    ("users", "EmailChangeRequest"),
    # core.auth
    ("dp_auth", "EmailAddress"),
    ("dp_auth", "SocialAccount"),
    # dreams
    ("dreams", "Dream"),
    ("dreams", "DreamTemplate"),
    ("dreams", "DreamCollaborator"),
    ("dreams", "SharedDream"),
    ("dreams", "VisionBoardImage"),
    ("dreams", "DreamTag"),
    ("dreams", "DreamTagging"),
    ("dreams", "DreamJournal"),
    ("dreams", "ProgressPhoto"),
    # plans
    ("plans", "DreamMilestone"),
    ("plans", "Goal"),
    ("plans", "Task"),
    ("plans", "Obstacle"),
    ("plans", "CalibrationResponse"),
    ("plans", "PlanCheckIn"),
    ("plans", "DreamProgressSnapshot"),
    ("plans", "FocusSession"),
    # subscriptions
    ("subscriptions", "StripeCustomer"),
    ("subscriptions", "SubscriptionPlan"),
    ("subscriptions", "Subscription"),
    ("subscriptions", "StripeWebhookEvent"),
    ("subscriptions", "Promotion"),
    ("subscriptions", "PromotionRedemption"),
    ("subscriptions", "PromotionChangeLog"),
    # friends
    ("friends", "Friendship"),
    ("friends", "UserFollow"),
    ("friends", "BlockedUser"),
    ("friends", "ReportedUser"),
    # circles
    ("circles", "Circle"),
    ("circles", "CircleMembership"),
    ("circles", "CirclePost"),
    ("circles", "CircleChallenge"),
    ("circles", "PostReaction"),
    ("circles", "CircleInvitation"),
    ("circles", "ChallengeProgress"),
    ("circles", "CircleMessage"),
    ("circles", "CircleCall"),
    ("circles", "CircleCallParticipant"),
    ("circles", "CirclePoll"),
    ("circles", "PollOption"),
    ("circles", "PollVote"),
    # gamification
    ("gamification", "GamificationProfile"),
    ("gamification", "Achievement"),
    ("gamification", "UserAchievement"),
    ("gamification", "DailyActivity"),
    ("gamification", "HabitChain"),
    # social
    ("social", "ActivityFeedItem"),
    ("social", "Story"),
    ("social", "StoryView"),
    ("social", "ActivityLike"),
    ("social", "ActivityComment"),
    ("social", "DreamPost"),
    ("social", "DreamPostLike"),
    ("social", "DreamPostComment"),
    ("social", "DreamEncouragement"),
    ("social", "SocialEvent"),
    ("social", "SocialEventRegistration"),
    ("social", "RecentSearch"),
    ("social", "SavedPost"),
    ("social", "PostReaction"),
    # ai
    ("ai", "AIConversation"),
    ("ai", "AIMessage"),
    ("ai", "ConversationSummary"),
    ("ai", "ConversationBranch"),
    ("ai", "ChatMemory"),
    ("ai", "ConversationTemplate"),
    # buddies
    ("buddies", "BuddyPairing"),
    ("buddies", "BuddyEncouragement"),
    ("buddies", "AccountabilityContract"),
    ("buddies", "ContractCheckIn"),
    # chat
    ("chat", "ChatConversation"),
    ("chat", "ChatMessage"),
    ("chat", "Call"),
    ("chat", "MessageReadStatus"),
    # notifications
    ("notifications", "Notification"),
    ("notifications", "NotificationTemplate"),
    ("notifications", "NotificationBatch"),
    ("notifications", "UserDevice"),
    ("notifications", "WebPushSubscription"),
    # referrals
    ("referrals", "ReferralCode"),
    ("referrals", "Referral"),
    ("referrals", "ReferralReward"),
    # calendar
    ("calendar", "CalendarEvent"),
    ("calendar", "TimeBlock"),
    ("calendar", "TimeBlockTemplate"),
    ("calendar", "CalendarShare"),
    ("calendar", "GoogleCalendarIntegration"),
    ("calendar", "RecurrenceException"),
    ("calendar", "Habit"),
    ("calendar", "HabitCompletion"),
    # leagues
    ("leagues", "League"),
    ("leagues", "Season"),
    ("leagues", "LeagueStanding"),
    ("leagues", "SeasonReward"),
    ("leagues", "RankSnapshot"),
    ("leagues", "LeagueSeason"),
    ("leagues", "SeasonParticipant"),
    ("leagues", "SeasonConfig"),
    ("leagues", "LeagueGroup"),
    # store
    ("store", "StoreCategory"),
    ("store", "StoreItem"),
    ("store", "UserInventory"),
    ("store", "Wishlist"),
    ("store", "Gift"),
    ("store", "RefundRequest"),
    # updates
    ("updates", "AppBundle"),
]


@pytest.fixture
def admin_user(db):
    """Create a superuser for admin access."""
    return User.objects.create_superuser(
        email="admin@test.com",
        password="adminpass123",
        display_name="Admin",
    )


@pytest.fixture
def admin_client(client, admin_user):
    """Return a logged-in Django test client with admin access."""
    client.force_login(admin_user)
    return client


@pytest.fixture
def request_factory():
    return RequestFactory()


@pytest.fixture
def admin_request(request_factory, admin_user):
    """Create a request with admin user for ModelAdmin method testing."""
    from django.contrib.messages.storage.fallback import FallbackStorage
    from django.contrib.sessions.backends.db import SessionStore

    request = request_factory.get("/admin/")
    request.user = admin_user
    # Add session and messages support (needed by admin actions)
    request.session = SessionStore()
    setattr(request, "_messages", FallbackStorage(request))
    return request


# ── Registration tests ──────────────────────────────────────────────────


@pytest.mark.django_db
class TestAdminRegistrations:
    """Verify all project models are registered in the Django admin."""

    def test_all_models_registered(self):
        """Verify all expected models have admin registrations."""
        from django.contrib.admin import site

        registered = {
            (m._meta.app_label, m.__name__) for m in site._registry.keys()
        }
        missing = []
        for app_label, model_name in EXPECTED_ADMIN_MODELS:
            if (app_label, model_name) not in registered:
                missing.append(f"{app_label}.{model_name}")
        assert not missing, f"Models not registered in admin: {missing}"

    def test_no_unexpected_project_models_unregistered(self):
        """All project models (apps.* / core.*) should be registered or explicitly inline-only."""
        from django.apps import apps
        from django.contrib.admin import site

        registered = {
            (m._meta.app_label, m.__name__) for m in site._registry.keys()
        }
        # Inline-only models that are expected to NOT be top-level registered
        inline_only = {
            ("subscriptions", "PromotionPlanDiscount"),
            ("leagues", "LeagueGroupMembership"),
        }
        unregistered = []
        for app_config in apps.get_app_configs():
            if not app_config.name.startswith(("apps.", "core.")):
                continue
            for model in app_config.get_models():
                key = (model._meta.app_label, model.__name__)
                if key not in registered and key not in inline_only:
                    unregistered.append(f"{key[0]}.{key[1]}")
        assert not unregistered, f"Project models not in admin: {unregistered}"


# ── Changelist view tests (admin pages load without errors) ─────────────


@pytest.mark.django_db
class TestAdminChangelistViews:
    """Verify that admin changelist views load without errors (HTTP 200)."""

    # Test a representative set of key admin changelist pages.
    @pytest.mark.parametrize(
        "url_name",
        [
            "admin:users_user_changelist",
            "admin:users_emailchangerequest_changelist",
            "admin:dreams_dream_changelist",
            "admin:dreams_dreamtemplate_changelist",
            "admin:plans_goal_changelist",
            "admin:plans_task_changelist",
            "admin:plans_dreammilestone_changelist",
            "admin:plans_obstacle_changelist",
            "admin:plans_focussession_changelist",
            "admin:subscriptions_subscriptionplan_changelist",
            "admin:subscriptions_subscription_changelist",
            "admin:subscriptions_stripecustomer_changelist",
            "admin:subscriptions_promotion_changelist",
            "admin:subscriptions_stripewebhookevent_changelist",
            "admin:friends_friendship_changelist",
            "admin:friends_userfollow_changelist",
            "admin:circles_circle_changelist",
            "admin:circles_circlepost_changelist",
            "admin:circles_circlechallenge_changelist",
            "admin:circles_circlepoll_changelist",
            "admin:gamification_gamificationprofile_changelist",
            "admin:gamification_achievement_changelist",
            "admin:social_activityfeeditem_changelist",
            "admin:social_dreampost_changelist",
            "admin:social_story_changelist",
            "admin:ai_aiconversation_changelist",
            "admin:ai_aimessage_changelist",
            "admin:ai_chatmemory_changelist",
            "admin:buddies_buddypairing_changelist",
            "admin:buddies_accountabilitycontract_changelist",
            "admin:chat_chatconversation_changelist",
            "admin:chat_call_changelist",
            "admin:notifications_notification_changelist",
            "admin:notifications_notificationbatch_changelist",
            "admin:notifications_userdevice_changelist",
            "admin:referrals_referralcode_changelist",
            "admin:calendar_calendarevent_changelist",
            "admin:calendar_timeblock_changelist",
            "admin:calendar_habit_changelist",
            "admin:leagues_league_changelist",
            "admin:leagues_season_changelist",
            "admin:leagues_leaguestanding_changelist",
            "admin:leagues_leaguegroup_changelist",
            "admin:leagues_seasonconfig_changelist",
            "admin:store_storecategory_changelist",
            "admin:store_storeitem_changelist",
            "admin:store_userinventory_changelist",
            "admin:updates_appbundle_changelist",
            "admin:dp_auth_emailaddress_changelist",
            "admin:dp_auth_socialaccount_changelist",
        ],
    )
    def test_changelist_loads(self, admin_client, url_name):
        """Admin changelist page returns HTTP 200."""
        url = reverse(url_name)
        response = admin_client.get(url)
        assert response.status_code == 200


# ── Search field tests ──────────────────────────────────────────────────


@pytest.mark.django_db
class TestAdminSearch:
    """Verify that searching on admin changelists does not error."""

    @pytest.mark.parametrize(
        "url_name,query",
        [
            ("admin:users_user_changelist", "test@example.com"),
            ("admin:dreams_dream_changelist", "marathon"),
            ("admin:plans_goal_changelist", "fitness"),
            ("admin:plans_task_changelist", "read"),
            ("admin:subscriptions_subscriptionplan_changelist", "free"),
            ("admin:subscriptions_subscription_changelist", "test@example.com"),
            ("admin:friends_friendship_changelist", "test@example.com"),
            ("admin:circles_circle_changelist", "runners"),
            ("admin:gamification_achievement_changelist", "streak"),
            ("admin:social_activityfeeditem_changelist", "test@example.com"),
            ("admin:social_dreampost_changelist", "progress"),
            ("admin:ai_aiconversation_changelist", "test@example.com"),
            ("admin:buddies_buddypairing_changelist", "test@example.com"),
            ("admin:chat_chatconversation_changelist", "test@example.com"),
            ("admin:notifications_notification_changelist", "reminder"),
            ("admin:referrals_referralcode_changelist", "ABC123"),
            ("admin:calendar_calendarevent_changelist", "meeting"),
            ("admin:leagues_league_changelist", "bronze"),
            ("admin:store_storeitem_changelist", "avatar"),
            ("admin:updates_appbundle_changelist", "com.stepora"),
        ],
    )
    def test_search_works(self, admin_client, url_name, query):
        """Admin search returns HTTP 200 (no field lookup errors)."""
        url = reverse(url_name)
        response = admin_client.get(url, {"q": query})
        assert response.status_code == 200


# ── Filter tests ────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestAdminFilters:
    """Verify that admin list filters work correctly."""

    @pytest.mark.parametrize(
        "url_name,filter_params",
        [
            ("admin:users_user_changelist", {"is_staff": "1"}),
            ("admin:users_user_changelist", {"is_active": "1"}),
            ("admin:dreams_dream_changelist", {"status": "active"}),
            ("admin:dreams_dream_changelist", {"category": "health"}),
            ("admin:dreams_dreamtemplate_changelist", {"is_featured": "1"}),
            ("admin:plans_goal_changelist", {"status": "pending"}),
            ("admin:plans_task_changelist", {"status": "pending"}),
            ("admin:plans_focussession_changelist", {"completed": "1"}),
            ("admin:subscriptions_subscription_changelist", {"status": "active"}),
            ("admin:friends_friendship_changelist", {"status": "accepted"}),
            ("admin:circles_circle_changelist", {"is_public": "1"}),
            ("admin:circles_circlechallenge_changelist", {"status": "active"}),
            ("admin:gamification_achievement_changelist", {"is_active": "1"}),
            ("admin:social_dreampost_changelist", {"visibility": "public"}),
            ("admin:social_story_changelist", {"media_type": "image"}),
            ("admin:ai_aiconversation_changelist", {"is_active": "1"}),
            ("admin:buddies_buddypairing_changelist", {"status": "active"}),
            ("admin:chat_chatconversation_changelist", {"is_active": "1"}),
            ("admin:notifications_notification_changelist", {"status": "pending"}),
            ("admin:notifications_userdevice_changelist", {"platform": "android"}),
            ("admin:referrals_referralcode_changelist", {"is_active": "1"}),
            ("admin:calendar_timeblock_changelist", {"is_active": "1"}),
            ("admin:calendar_habit_changelist", {"is_active": "1"}),
            ("admin:leagues_season_changelist", {"is_active": "1"}),
            ("admin:store_storeitem_changelist", {"is_active": "1"}),
            ("admin:updates_appbundle_changelist", {"is_active": "1"}),
        ],
    )
    def test_filter_works(self, admin_client, url_name, filter_params):
        """Admin filter returns HTTP 200."""
        url = reverse(url_name)
        response = admin_client.get(url, filter_params)
        assert response.status_code == 200


# ── Admin actions tests ─────────────────────────────────────────────────


@pytest.mark.django_db
class TestAdminActions:
    """Test key admin actions work correctly."""

    def test_set_plan_free_action(self, admin_request):
        """set_plan_free action changes user subscription plan to free."""
        from apps.subscriptions.models import Subscription, SubscriptionPlan
        from apps.users.admin import UserAdmin, set_plan_free

        # Ensure plans exist
        SubscriptionPlan.seed_plans()

        user = User.objects.create_user(
            email="action-test@example.com",
            password="testpass123",
            display_name="Action Test",
        )
        # Give user a premium subscription (use update_or_create since signal may have created one)
        premium_plan = SubscriptionPlan.objects.get(slug="premium")
        Subscription.objects.update_or_create(
            user=user, defaults={"plan": premium_plan, "status": "active"}
        )

        site = AdminSite()
        model_admin = UserAdmin(User, site)
        queryset = User.objects.filter(pk=user.pk)

        set_plan_free(model_admin, admin_request, queryset)

        sub = Subscription.objects.get(user=user)
        free_plan = SubscriptionPlan.objects.get(slug="free")
        assert sub.plan == free_plan
        assert sub.status == "active"

    def test_set_plan_premium_action(self, admin_request):
        """set_plan_premium action creates/updates subscription to premium."""
        from apps.subscriptions.models import Subscription, SubscriptionPlan
        from apps.users.admin import UserAdmin, set_plan_premium

        SubscriptionPlan.seed_plans()

        user = User.objects.create_user(
            email="action-premium@example.com",
            password="testpass123",
            display_name="Premium Action",
        )
        site = AdminSite()
        model_admin = UserAdmin(User, site)
        queryset = User.objects.filter(pk=user.pk)

        set_plan_premium(model_admin, admin_request, queryset)

        sub = Subscription.objects.get(user=user)
        premium_plan = SubscriptionPlan.objects.get(slug="premium")
        assert sub.plan == premium_plan

    def test_set_plan_pro_action(self, admin_request):
        """set_plan_pro action creates subscription to pro."""
        from apps.subscriptions.models import Subscription, SubscriptionPlan
        from apps.users.admin import UserAdmin, set_plan_pro

        SubscriptionPlan.seed_plans()

        user = User.objects.create_user(
            email="action-pro@example.com",
            password="testpass123",
            display_name="Pro Action",
        )
        site = AdminSite()
        model_admin = UserAdmin(User, site)
        queryset = User.objects.filter(pk=user.pk)

        set_plan_pro(model_admin, admin_request, queryset)

        sub = Subscription.objects.get(user=user)
        pro_plan = SubscriptionPlan.objects.get(slug="pro")
        assert sub.plan == pro_plan

    def test_change_plan_nonexistent_plan(self, admin_request):
        """_change_plan with invalid slug shows error message."""
        from apps.users.admin import UserAdmin, _change_plan

        user = User.objects.create_user(
            email="action-invalid@example.com",
            password="testpass123",
            display_name="Invalid Plan",
        )
        site = AdminSite()
        model_admin = UserAdmin(User, site)
        queryset = User.objects.filter(pk=user.pk)

        # Should not raise, just show error message
        _change_plan(model_admin, admin_request, queryset, "nonexistent-plan")

    def test_notification_mark_as_sent_action(self, admin_request):
        """mark_as_sent action updates notification status."""
        from apps.notifications.admin import NotificationAdmin
        from apps.notifications.models import Notification

        user = User.objects.create_user(
            email=f"notif-action-{__import__('uuid').uuid4().hex[:8]}@example.com",
            password="testpass123",
            display_name="Notif Action",
        )
        from django.utils import timezone

        notif = Notification.objects.create(
            user=user,
            notification_type="reminder",
            title="Test",
            body="Test body",
            scheduled_for=timezone.now(),
            status="pending",
        )

        site = AdminSite()
        model_admin = NotificationAdmin(Notification, site)
        queryset = Notification.objects.filter(pk=notif.pk)

        model_admin.mark_as_sent(admin_request, queryset)

        notif.refresh_from_db()
        assert notif.status == "sent"

    def test_notification_mark_as_cancelled_action(self, admin_request):
        """mark_as_cancelled action updates notification status."""
        from apps.notifications.admin import NotificationAdmin
        from apps.notifications.models import Notification

        user = User.objects.create_user(
            email=f"notif-cancel-{__import__('uuid').uuid4().hex[:8]}@example.com",
            password="testpass123",
            display_name="Cancel Action",
        )
        from django.utils import timezone

        notif = Notification.objects.create(
            user=user,
            notification_type="reminder",
            title="Test",
            body="Test body",
            scheduled_for=timezone.now(),
            status="pending",
        )

        site = AdminSite()
        model_admin = NotificationAdmin(Notification, site)
        queryset = Notification.objects.filter(pk=notif.pk)

        model_admin.mark_as_cancelled(admin_request, queryset)

        notif.refresh_from_db()
        assert notif.status == "cancelled"


# ── Admin custom method tests ───────────────────────────────────────────


@pytest.mark.django_db
class TestAdminCustomMethods:
    """Test custom admin methods (computed columns, etc.)."""

    def test_circle_member_count(self):
        """CircleAdmin.member_count works."""
        from apps.circles.admin import CircleAdmin
        from apps.circles.models import Circle

        user = User.objects.create_user(
            email="circle-admin@test.com",
            password="testpass",
            display_name="Circle Admin",
        )
        circle = Circle.objects.create(
            name="Test Circle",
            description="Test",
            creator=user,
        )
        site = AdminSite()
        model_admin = CircleAdmin(Circle, site)
        # member_count calls the model property
        result = model_admin.member_count(circle)
        assert isinstance(result, int)

    def test_notification_batch_progress(self):
        """NotificationBatchAdmin.progress returns a string."""
        from apps.notifications.admin import NotificationBatchAdmin
        from apps.notifications.models import NotificationBatch

        batch = NotificationBatch(
            name="Test Batch",
            notification_type="system",
            total_scheduled=10,
            total_sent=3,
            total_failed=0,
        )
        site = AdminSite()
        model_admin = NotificationBatchAdmin(NotificationBatch, site)
        progress = model_admin.progress(batch)
        assert "30.0%" in progress

    def test_notification_batch_progress_zero(self):
        """NotificationBatchAdmin.progress handles 0 scheduled."""
        from apps.notifications.admin import NotificationBatchAdmin
        from apps.notifications.models import NotificationBatch

        batch = NotificationBatch(
            name="Empty Batch",
            notification_type="system",
            total_scheduled=0,
            total_sent=0,
            total_failed=0,
        )
        site = AdminSite()
        model_admin = NotificationBatchAdmin(NotificationBatch, site)
        assert model_admin.progress(batch) == "0%"

    def test_store_category_items_count(self):
        """StoreCategoryAdmin.items_count works."""
        from apps.store.admin import StoreCategoryAdmin
        from apps.store.models import StoreCategory

        cat = StoreCategory.objects.create(
            name="Test Cat", slug="test-cat", display_order=1
        )
        site = AdminSite()
        model_admin = StoreCategoryAdmin(StoreCategory, site)
        assert model_admin.items_count(cat) == 0

    def test_promotion_redemption_count(self):
        """PromotionAdmin.redemption_count works."""
        from apps.subscriptions.admin import PromotionAdmin
        from apps.subscriptions.models import Promotion

        from django.utils import timezone

        promo = Promotion.objects.create(
            name="Test Promo",
            discount_type="percentage",
            start_date=timezone.now(),
        )
        site = AdminSite()
        model_admin = PromotionAdmin(Promotion, site)
        assert model_admin.redemption_count(promo) == 0

    def test_promotion_redemption_admin_permissions(self):
        """PromotionRedemptionAdmin blocks add and change."""
        from apps.subscriptions.admin import PromotionRedemptionAdmin
        from apps.subscriptions.models import PromotionRedemption

        site = AdminSite()
        model_admin = PromotionRedemptionAdmin(PromotionRedemption, site)
        assert model_admin.has_add_permission(None) is False
        assert model_admin.has_change_permission(None) is False

    def test_promotion_changelog_admin_permissions(self):
        """PromotionChangeLogAdmin blocks add, change, and delete."""
        from apps.subscriptions.admin import PromotionChangeLogAdmin
        from apps.subscriptions.models import PromotionChangeLog

        site = AdminSite()
        model_admin = PromotionChangeLogAdmin(PromotionChangeLog, site)
        assert model_admin.has_add_permission(None) is False
        assert model_admin.has_change_permission(None) is False
        assert model_admin.has_delete_permission(None) is False

    def test_season_config_singleton_permission(self, admin_request):
        """SeasonConfigAdmin blocks add when config exists."""
        from apps.leagues.admin import SeasonConfigAdmin
        from apps.leagues.models import SeasonConfig

        site = AdminSite()
        model_admin = SeasonConfigAdmin(SeasonConfig, site)

        # Initially no config exists -- should allow add
        assert model_admin.has_add_permission(admin_request) is True

        # Create a config, now add should be blocked
        SeasonConfig.objects.create()
        assert model_admin.has_add_permission(admin_request) is False

        # Delete should always be blocked
        assert model_admin.has_delete_permission(admin_request) is False

    def test_time_block_day_name(self):
        """TimeBlockAdmin.day_name returns correct day string."""
        from apps.calendar.admin import TimeBlockAdmin
        from apps.calendar.models import TimeBlock

        user = User.objects.create_user(
            email="timeblock@test.com",
            password="testpass",
            display_name="TB User",
        )
        from datetime import time

        block = TimeBlock(
            user=user,
            day_of_week=0,
            start_time=time(9, 0),
            end_time=time(10, 0),
            block_type="work",
        )
        site = AdminSite()
        model_admin = TimeBlockAdmin(TimeBlock, site)
        assert model_admin.day_name(block) == "Monday"

    def test_time_block_template_block_count(self):
        """TimeBlockTemplateAdmin.block_count works."""
        from apps.calendar.admin import TimeBlockTemplateAdmin
        from apps.calendar.models import TimeBlockTemplate

        template = TimeBlockTemplate(
            name="Test Template",
            blocks=[{"start": "09:00", "end": "10:00"}],
        )
        site = AdminSite()
        model_admin = TimeBlockTemplateAdmin(TimeBlockTemplate, site)
        assert model_admin.block_count(template) == 1

        # Non-list blocks
        template2 = TimeBlockTemplate(name="Empty", blocks={})
        assert model_admin.block_count(template2) == 0
