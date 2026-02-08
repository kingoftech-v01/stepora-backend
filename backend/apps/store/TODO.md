# Store App - TODO

## Completed

- [x] **Purchase history endpoint** - API endpoint for users to view their complete purchase history with timestamps, payment amounts, and items acquired. Includes pagination and date range filtering.

- [x] **Gifting system** - Users can purchase store items as gifts for other users. Gifting flow with Gift model, send/claim mechanism, and gift notification to the recipient.

- [x] **XP-based purchasing** - Alternative purchase method using accumulated XP points instead of real money. XP-to-currency conversion rates per rarity tier with XP balance check before purchase.

- [x] **Refund handling** - Refund support via RefundRequest model with admin approval workflow. Handles refund processing and item removal from user inventory.

- [x] **Wishlist** - Users can save items to a wishlist for later purchase (Wishlist model + CRUD endpoints). Notifications when wishlisted items go on sale or are about to be removed.

- [x] **Limited-time badges** - Support for time-limited store items that are only available during specific date ranges (available_from/available_until on StoreItem). Automatic deactivation when the availability window closes.

## Planned Improvements

- [ ] **Bulk equip management** - Add an endpoint to view and manage all equipped items in a single request, allowing users to swap entire loadouts at once.

- [ ] **Item previews** - Add a preview mechanism so users can see how cosmetic items look before purchasing (e.g., badge frame preview on their profile).

- [ ] **Store analytics** - Track popular items, conversion rates, and revenue per category. Provide admin endpoints for store performance metrics.

- [ ] **Discount/sale pricing** - Support temporary price reductions with original and sale prices displayed. Integrate with a scheduling system for automated sales events.
