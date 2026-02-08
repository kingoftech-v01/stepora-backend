# Subscription Screen - TODO

## Current Status
- subscription_screen.dart: Shows plans with features, upgrade button opens Stripe checkout in browser

## Placeholders to Fix
- [x] **Fix checkout redirect**: Use `url_launcher` package to open Stripe checkout URL in browser instead of showing Snackbar
- [x] **Add cancel subscription**: Button for current subscribers; call `POST /api/subscriptions/subscription/cancel/`
- [x] **Add reactivate subscription**: Button for cancelled-but-active subscribers; call `POST /api/subscriptions/subscription/reactivate/`

## Missing Functionality
- [x] Add billing portal access: Button to open Stripe portal; call `POST /api/subscriptions/subscription/portal/`
- [x] Show subscription end date for active subscribers
- [x] Show cancellation status ("Cancels on {date}") for pending cancellation
- [x] Add subscription sync button (force refresh from Stripe)

## Small Improvements
- [ ] Add feature comparison table between tiers
- [ ] Add "Most Popular" badge on recommended plan
- [ ] Show savings percentage for yearly vs monthly pricing
