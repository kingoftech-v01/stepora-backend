# Store Screen - TODO

## Current Status
- store_screen.dart: Shows items grid with purchase confirmation, inventory, and equip/unequip

## Placeholders to Fix
- [x] **Add purchase confirmation dialog**: Show item name, price, and confirm/cancel before calling purchase API
- [x] **Add inventory display**: "My Items" tab showing owned items from `GET /api/store/inventory/`
- [x] **Add equip/unequip UI**: Toggle button on owned items; call `POST /api/store/inventory/{id}/equip/`

## Missing Functionality
- [x] Add category filtering: Load categories from `GET /api/store/categories/`, show as filter chips
- [x] Add featured items section at top: Load from `GET /api/store/items/featured/` (epic/legendary rarity)
- [x] Add item detail bottom sheet with full description, rarity badge, type icon

## Small Improvements
- [x] Add rarity-based visual styling (color borders: common=grey, rare=blue, epic=purple, legendary=gold)
- [x] Add "Equipped" badge on currently equipped items
- [x] Add purchase success animation/feedback
- [ ] Show user's coin/currency balance if applicable
