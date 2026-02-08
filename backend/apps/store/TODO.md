# Store App - TODO

## Planned Features

- [ ] **Purchase history endpoint** - Add an API endpoint for users to view their complete purchase history with timestamps, payment amounts, and items acquired. Include pagination and date range filtering.

- [ ] **Gifting system** - Allow users to purchase store items as gifts for other users. Implement a gifting flow with Stripe PaymentIntents, a gift notification to the recipient, and a gift acceptance/claim mechanism.

- [ ] **XP-based purchasing** - Implement an alternative purchase method using accumulated XP points instead of real money. Define XP-to-currency conversion rates per rarity tier and add an XP balance check before purchase.

- [ ] **Refund handling** - Implement refund support via Stripe Refund API. Handle refund webhooks to remove items from user inventory. Add a refund request endpoint with admin approval workflow.

- [ ] **Limited-time badges** - Add support for time-limited store items that are only available during specific date ranges. Include countdown timers in the API response and automatic deactivation when the availability window closes.

## Improvements

- [ ] **Bulk equip management** - Add an endpoint to view and manage all equipped items in a single request, allowing users to swap entire loadouts at once.

- [ ] **Item previews** - Add a preview mechanism so users can see how cosmetic items look before purchasing (e.g., badge frame preview on their profile).

- [ ] **Wishlist** - Allow users to save items to a wishlist for later purchase. Notify users when wishlisted items go on sale or are about to be removed.

- [ ] **Store analytics** - Track popular items, conversion rates, and revenue per category. Provide admin endpoints for store performance metrics.

- [ ] **Discount/sale pricing** - Support temporary price reductions with original and sale prices displayed. Integrate with a scheduling system for automated sales events.
