# Subscription Screen - TODO

## Current Status
- subscription_screen.dart: Shows plans with features, "Upgrade" button creates checkout but displays URL in Snackbar instead of opening browser

## Placeholders to Fix
- [ ] **Fix checkout redirect**: Use `url_launcher` package to open Stripe checkout URL in browser instead of showing Snackbar
- [ ] **Add cancel subscription**: Button for current subscribers; call `POST /api/subscriptions/subscription/cancel/`
- [ ] **Add reactivate subscription**: Button for cancelled-but-active subscribers; call `POST /api/subscriptions/subscription/reactivate/`

## Missing Functionality
- [ ] Add billing portal access: Button to open Stripe portal; call `POST /api/subscriptions/subscription/portal/`
- [ ] Show subscription end date for active subscribers
- [ ] Show cancellation status ("Cancels on {date}") for pending cancellation
- [ ] Add subscription sync button (force refresh from Stripe)

## Small Improvements
- [ ] Add feature comparison table between tiers
- [ ] Add "Most Popular" badge on recommended plan
- [ ] Show savings percentage for yearly vs monthly pricing
