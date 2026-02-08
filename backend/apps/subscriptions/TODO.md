# Subscriptions App - TODO

## Planned Features

- [ ] **Trial period support** - Allow plans to offer a free trial period (e.g., 7-day or 14-day trial) before the first charge. Integrate with Stripe's `trial_period_days` parameter in checkout session creation.

- [ ] **Invoice history endpoint** - Add an API endpoint for users to view their past invoices and payment history. Fetch data from Stripe's Invoice API and cache locally for faster retrieval.

- [ ] **Coupon/promo code support** - Implement coupon and promotional code functionality. Allow users to apply promo codes during checkout and display discounted pricing. Integrate with Stripe Coupons and Promotion Codes APIs.

- [ ] **Email receipts** - Send email receipts to users upon successful subscription payments and renewals. Integrate with Stripe's receipt email feature or implement custom email sending via Django's email backend.

- [ ] **Subscription analytics** - Build an admin dashboard and API endpoints for subscription metrics: MRR (Monthly Recurring Revenue), churn rate, plan distribution, conversion rates from free to paid tiers, and average revenue per user.

## Improvements

- [ ] **Stripe webhook retry handling** - Add idempotency checks to webhook handlers to safely handle Stripe's automatic retry delivery of failed webhook events.

- [ ] **Plan migration validation** - Add validation logic to prevent downgrades that would exceed new plan limits (e.g., user with 8 active dreams downgrading to Free with a limit of 3).

- [ ] **Subscription status email notifications** - Send emails when subscription status changes (payment failed, upcoming renewal, cancellation confirmed, subscription expired).

- [ ] **Annual billing option** - Add yearly pricing with a discount alongside monthly pricing. Requires additional `stripe_price_id` field or a separate pricing model.
