# Subscriptions App - TODO

## Completed

- [x] **Trial period support** - Allow plans to offer a free trial period (e.g., 7-day or 14-day trial) before the first charge. Integrated with Stripe's `trial_period_days` parameter in checkout session creation.

- [x] **Invoice history endpoint** - API endpoint for users to view their past invoices and payment history. Fetches data from Stripe's Invoice API with local caching for faster retrieval.

- [x] **Coupon/promo code support** - Coupon and promotional code functionality. Users can apply promo codes during checkout with discounted pricing displayed. Integrated with Stripe Coupons and Promotion Codes APIs.

- [x] **Email receipts** - Email receipts sent to users upon successful subscription payments and renewals (Celery task).

- [x] **Subscription analytics** - Admin dashboard and API endpoints for subscription metrics: MRR (Monthly Recurring Revenue), churn rate, plan distribution, conversion rates from free to paid tiers, and average revenue per user.

## Planned Improvements

- [ ] **Stripe webhook retry handling** - Add idempotency checks to webhook handlers to safely handle Stripe's automatic retry delivery of failed webhook events.

- [ ] **Plan migration validation** - Add validation logic to prevent downgrades that would exceed new plan limits (e.g., user with 8 active dreams downgrading to Free with a limit of 3).

- [ ] **Subscription status email notifications** - Send emails when subscription status changes (payment failed, upcoming renewal, cancellation confirmed, subscription expired).

- [ ] **Annual billing option** - Add yearly pricing with a discount alongside monthly pricing. Requires additional `stripe_price_id` field or a separate pricing model.
