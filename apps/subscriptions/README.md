# Subscriptions App

Django application for managing subscription billing through Stripe, including customer mapping, plan definitions with feature gating, and subscription lifecycle management.

## Overview

The Subscriptions app integrates Stripe for recurring billing. It defines three subscription tiers (Free, Premium, Pro) that gate access to platform features such as AI coaching, Dream Buddies, Circles, Vision Boards, and Leagues. Stripe webhooks keep the local subscription state synchronized with Stripe's billing system.

## Models

### StripeCustomer

Maps a DreamPlanner user to a Stripe customer. Created automatically when needed during checkout.

| Field | Type | Description |
|-------|------|-------------|
| id | UUID | Primary key |
| user | OneToOne(User) | DreamPlanner user (related_name: `stripe_customer`) |
| stripe_customer_id | CharField(255) | Stripe customer ID (`cus_xxxxx`), unique, indexed |
| created_at | DateTimeField | Auto-set on creation |
| updated_at | DateTimeField | Auto-set on update |

**DB table:** `stripe_customers`

### SubscriptionPlan

Defines available subscription plans with feature flags and resource limits.

| Field | Type | Description |
|-------|------|-------------|
| id | UUID | Primary key |
| name | CharField(50) | Plan display name (Free, Premium, Pro), unique |
| slug | SlugField(50) | URL-safe identifier (`free`, `premium`, `pro`), unique |
| stripe_price_id | CharField(255) | Stripe Price ID (`price_xxxxx`). Empty for free tier |
| price_monthly | Decimal(6,2) | Monthly price in USD (default: 0) |
| features | JSONField | JSON object describing plan features for display |
| dream_limit | Integer | Max active dreams allowed. -1 for unlimited (default: 3) |
| has_ai | Boolean | Access to AI coaching (default: False) |
| has_buddy | Boolean | Access to Dream Buddy matching (default: False) |
| has_circles | Boolean | Access to Dream Circles (default: False) |
| has_vision_board | Boolean | Access to AI Vision Board generation (default: False) |
| has_league | Boolean | Access to competitive leagues (default: False) |
| ai_chat_daily_limit | Integer | Daily AI chat limit (default: 0) |
| ai_plan_daily_limit | Integer | Daily AI plan generation limit (default: 0) |
| ai_image_daily_limit | Integer | Daily AI image generation limit (default: 0) |
| ai_voice_daily_limit | Integer | Daily AI voice limit (default: 0) |
| ai_background_daily_limit | Integer | Daily AI background limit (default: 3) |
| trial_period_days | Integer | Trial period duration in days (default: 0) |
| has_ads | Boolean | Whether ads are shown (default: True) |
| is_active | Boolean | Whether plan is available for purchase (default: True) |
| created_at | DateTimeField | Auto-set on creation |
| updated_at | DateTimeField | Auto-set on update |

**DB table:** `subscription_plans`

**Properties:**
- `is_free` - Returns True if `price_monthly == 0`
- `has_unlimited_dreams` - Returns True if `dream_limit == -1`

**Class methods:**
- `seed_plans()` - Idempotent method to create/update the three default plans (Free, Premium, Pro)

#### Default Plan Configuration

| Plan | Price | Dreams | AI | Buddy | Circles | Vision | League | Ads |
|------|-------|--------|-----|-------|---------|--------|--------|-----|
| Free | $0/mo | 3 | No | No | No | No | No | Yes |
| Premium | $14.99/mo | 10 | Yes | Yes | No | No | Yes | No |
| Pro | $29.99/mo | Unlimited | Yes | Yes | Yes | Yes | Yes | No |

### Subscription

Tracks an active subscription linking a user to a plan via Stripe.

| Field | Type | Description |
|-------|------|-------------|
| id | UUID | Primary key |
| user | OneToOne(User) | Subscriber (related_name: `active_subscription`) |
| plan | FK(SubscriptionPlan) | Subscription plan (related_name: `subscriptions`) |
| stripe_subscription_id | CharField(255) | Stripe Subscription ID (`sub_xxxxx`), unique, indexed |
| status | CharField(30) | Status: `active`, `past_due`, `canceled`, `incomplete`, `incomplete_expired`, `trialing`, `unpaid`, `paused` |
| current_period_start | DateTimeField | Start of current billing period (nullable) |
| current_period_end | DateTimeField | End of current billing period (nullable) |
| cancel_at_period_end | Boolean | If True, cancels at end of period (default: False) |
| canceled_at | DateTimeField | When cancellation was requested (nullable) |
| created_at | DateTimeField | Auto-set on creation |
| updated_at | DateTimeField | Auto-set on update |

**DB table:** `subscriptions`

**Properties:**
- `is_active` - Returns True if status is `active` or `trialing`

## API Endpoints

### Subscription Plans (Public)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/plans/` | List all active subscription plans |
| GET | `/plans/{slug}/` | Get plan detail by slug |

**ViewSet:** `SubscriptionPlanViewSet` (ReadOnlyModelViewSet)
- Permission: `AllowAny`
- Lookup field: `slug`

### Subscription Management (Authenticated)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/subscription/current/` | Get current user's subscription (404 if free tier) |
| POST | `/subscription/checkout/` | Create Stripe Checkout Session for plan upgrade |
| POST | `/subscription/portal/` | Create Stripe Billing Portal session |
| POST | `/subscription/cancel/` | Cancel subscription at period end |
| POST | `/subscription/reactivate/` | Reverse a pending cancellation |
| POST | `/subscription/sync/` | Force-sync subscription state from Stripe |
| GET | `/subscription/invoices/` | Get invoice history for current subscription |
| POST | `/subscription/apply-coupon/` | Apply a coupon or promo code to the subscription |

**ViewSet:** `SubscriptionViewSet` (GenericViewSet)
- Permission: `IsAuthenticated`

### Stripe Webhook

| Method | Path | Description |
|--------|------|-------------|
| POST | `/webhook/stripe/` | Receive and process Stripe webhook events |

**View:** `StripeWebhookView` (APIView)
- Permission: `AllowAny` (verified via Stripe signature)

## Serializers

| Serializer | Purpose |
|------------|---------|
| `SubscriptionPlanSerializer` | Full plan details with computed `is_free` and `has_unlimited_dreams` fields |
| `StripeCustomerSerializer` | Stripe customer mapping with `user_email` (admin/debug use) |
| `SubscriptionSerializer` | Subscription details with nested `SubscriptionPlanSerializer` and computed `is_active` |
| `SubscriptionCreateSerializer` | Input for checkout: `plan_slug`, optional `success_url`, `cancel_url`, `coupon_code`. Validates plan exists, is active, and is not the free tier |
| `InvoiceSerializer` | Invoice history entries for the `/invoices/` endpoint |

## Services (StripeService)

All Stripe API interactions are encapsulated in `StripeService`:

| Method | Description |
|--------|-------------|
| `create_customer(user)` | Create or return existing Stripe customer for a user |
| `create_checkout_session(user, plan, success_url, cancel_url)` | Create Stripe Checkout Session for subscription |
| `create_portal_session(user, return_url)` | Create Stripe Billing Portal session |
| `cancel_subscription(user)` | Cancel subscription at period end via Stripe API |
| `reactivate_subscription(user)` | Reverse pending cancellation via Stripe API |
| `sync_subscription_status(user)` | Force-sync local subscription from Stripe |
| `handle_webhook_event(payload, sig_header)` | Verify signature and dispatch webhook events |
| `list_invoices(user, limit)` | List invoice history for a user (default limit: 10) |
| `get_analytics()` | Get subscription analytics (MRR, counts, churn) |

### Webhook Event Handlers

| Stripe Event | Handler | Action |
|-------------|---------|--------|
| `checkout.session.completed` | `_handle_checkout_completed` | Create/update local subscription, sync user model |
| `invoice.paid` | `_handle_invoice_paid` | Update billing period on recurring payments |
| `invoice.payment_failed` | `_handle_invoice_payment_failed` | Mark subscription as `past_due` |
| `customer.subscription.updated` | `_handle_subscription_updated` | Mirror status/plan changes from Stripe |
| `customer.subscription.deleted` | `_handle_subscription_deleted` | Mark as canceled, revert user to free tier |

### Helper Functions

- `_timestamp_to_datetime(ts)` - Convert Unix timestamp to timezone-aware datetime
- `_sync_user_subscription(user, plan, period_end)` - Sync denormalized `subscription` and `subscription_ends` fields on the User model

## Configuration

### Environment Variables

| Variable | Description |
|----------|-------------|
| `STRIPE_SECRET_KEY` | Stripe API secret key |
| `STRIPE_WEBHOOK_SECRET` | Webhook endpoint signing secret for signature verification |
| `STRIPE_SUCCESS_URL` | Default redirect URL after successful checkout |
| `STRIPE_CANCEL_URL` | Default redirect URL if user cancels checkout |
| `STRIPE_PORTAL_RETURN_URL` | Default return URL when exiting the billing portal |

## Celery Tasks

| Task | Description |
|------|-------------|
| `send_payment_receipt_email` | Sends an email receipt after each successful payment/invoice |

## Signals

- **User post_save** - Automatically creates a `StripeCustomer` record when a new User is created (via `signals.py`)

## Subscription Analytics

Analytics accessible via `GET /subscription/analytics/` (admin only) and internal APIs:

- **MRR (Monthly Recurring Revenue)** - Sum of active subscription plan prices
- **Churn rate** - Percentage of subscriptions canceled over a time period
- **Conversion rate** - Percentage of free users who upgrade to paid plans
- **Trial-to-paid conversion** - Percentage of trialing users who convert to active subscriptions

## Coupon/Promo Code Support

Coupons and promo codes are managed through Stripe and can be applied during checkout or to existing subscriptions:

- Percentage-based discounts
- Fixed-amount discounts
- Duration-limited promotions (once, repeating, forever)
- Validated server-side via Stripe API before application

## Admin

All three models are registered with Django admin:

- **StripeCustomerAdmin** - Search by user email, display name, or Stripe customer ID
- **SubscriptionPlanAdmin** - Organized fieldsets for pricing, resource limits, feature flags, and display JSON. Slug auto-populated from name
- **SubscriptionAdmin** - Filter by status, plan, or cancellation state. Organized fieldsets for billing period and trial management
