# Store Screen - TODO

## Current Status
- store_screen.dart: Shows items grid, purchase button works but no confirmation dialog

## Placeholders to Fix
- [ ] **Add purchase confirmation dialog**: Show item name, price, and confirm/cancel before calling purchase API
- [ ] **Add inventory display**: "My Items" tab or AppBar action showing owned items from `GET /api/store/inventory/`
- [ ] **Add equip/unequip UI**: Toggle button on owned items; call `POST /api/store/inventory/{id}/equip/`

## Missing Functionality
- [ ] Add category filtering: Load categories from `GET /api/store/categories/`, show as filter chips
- [ ] Add featured items section at top: Load from `GET /api/store/items/featured/` (epic/legendary rarity)
- [ ] Add item detail bottom sheet with full description, rarity badge, type icon

## Small Improvements
- [ ] Add rarity-based visual styling (color borders: common=grey, rare=blue, epic=purple, legendary=gold)
- [ ] Add "Equipped" badge on currently equipped items
- [ ] Add purchase success animation/feedback
- [ ] Show user's coin/currency balance if applicable
