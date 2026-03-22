# Store App

Django application for the in-app cosmetic store, supporting categorized items with rarity tiers, Stripe one-time payment processing, user inventory management, and item equipping.

## Overview

The Store app provides a marketplace for cosmetic items such as Badge Frames, Theme Skins, Avatar Decorations, Chat Bubbles, Streak Shields, and XP Boosters. Items are organized into categories, have rarity tiers (Common through Legendary), and are purchased via Stripe PaymentIntents. Users can equip one item of each type at a time.

## Models

### StoreCategory

Groups store items into browsable categories.

| Field | Type | Description |
|-------|------|-------------|
| id | UUID | Primary key |
| name | CharField(100) | Category display name, unique |
| slug | SlugField(100) | URL-friendly slug, unique |
| description | TextField | Description shown to users |
| icon | CharField(255) | Icon identifier or URL |
| display_order | Integer | Sort order in the store (default: 0) |
| is_active | Boolean | Whether visible in the store (default: True) |

**DB table:** `store_categories`

### StoreItem

Individual purchasable cosmetic item.

| Field | Type | Description |
|-------|------|-------------|
| id | UUID | Primary key |
| category | FK(StoreCategory) | Parent category (related_name: `items`) |
| name | CharField(200) | Item display name |
| slug | SlugField(200) | URL-friendly slug, unique |
| description | TextField | Item description |
| image_url | URLField(500) | Preview image URL |
| stripe_price_id | CharField(255) | Stripe Price ID for one-time payment |
| price | Decimal(10,2) | Price in USD (min: 0.00) |
| xp_price | Integer | Price in XP for XP-based purchasing (nullable, 0 = not purchasable with XP) |
| item_type | CharField(30) | One of: `badge_frame`, `theme_skin`, `avatar_decoration`, `chat_bubble`, `streak_shield`, `xp_booster` |
| rarity | CharField(20) | One of: `common`, `rare`, `epic`, `legendary` (default: `common`) |
| metadata | JSONField | Additional item data (colors, animation settings, duration) |
| is_active | Boolean | Whether available for purchase (default: True) |
| available_from | DateTimeField | Start of limited-time availability window (nullable) |
| available_until | DateTimeField | End of limited-time availability window (nullable) |
| created_at | DateTimeField | Auto-set on creation |

**DB table:** `store_items`

#### Item Types

| Type | Display Name |
|------|-------------|
| `badge_frame` | Badge Frame |
| `theme_skin` | Theme Skin |
| `avatar_decoration` | Avatar Decoration |
| `chat_bubble` | Chat Bubble |
| `streak_shield` | Streak Shield |
| `xp_booster` | XP Booster |

#### Rarity Tiers

| Rarity | Display Name |
|--------|-------------|
| `common` | Common |
| `rare` | Rare |
| `epic` | Epic |
| `legendary` | Legendary |

### UserInventory

Tracks items purchased and owned by a user.

| Field | Type | Description |
|-------|------|-------------|
| id | UUID | Primary key |
| user | FK(User) | Item owner (related_name: `inventory`) |
| item | FK(StoreItem) | Purchased item (related_name: `owners`) |
| purchased_at | DateTimeField | Auto-set on creation |
| stripe_payment_intent_id | CharField(255) | Stripe PaymentIntent ID for audit |
| is_equipped | Boolean | Whether currently equipped (default: False) |

**DB table:** `user_inventory`
**Constraint:** `unique_together = [['user', 'item']]` (each user can own an item only once)

### Wishlist

Tracks items a user has saved for later.

| Field | Type | Description |
|-------|------|-------------|
| id | UUID | Primary key |
| user | FK(User) | User (related_name: `wishlist`) |
| item | FK(StoreItem) | Wishlisted item (related_name: `wishlisted_by`) |
| created_at | DateTimeField | Auto-set on creation |

**DB table:** `store_wishlist`
**Constraint:** `unique_together = [['user', 'item']]`

### Gift

Allows users to purchase and send items to other users.

| Field | Type | Description |
|-------|------|-------------|
| id | UUID | Primary key |
| sender | FK(User) | Gift sender (related_name: `gifts_sent`) |
| recipient | FK(User) | Gift recipient (related_name: `gifts_received`) |
| item | FK(StoreItem) | Gifted item |
| message | TextField | Optional gift message |
| is_claimed | Boolean | Whether recipient has claimed the gift (default: False) |
| claimed_at | DateTimeField | Claim timestamp (nullable) |
| stripe_payment_intent_id | CharField(255) | Stripe PaymentIntent ID |
| created_at | DateTimeField | Auto-set on creation |

**DB table:** `store_gifts`

### RefundRequest

Tracks refund requests for purchased items.

| Field | Type | Description |
|-------|------|-------------|
| id | UUID | Primary key |
| user | FK(User) | Requesting user (related_name: `refund_requests`) |
| inventory_entry | FK(UserInventory) | Item to refund |
| reason | TextField | Refund reason |
| status | CharField(20) | `pending`, `approved`, `rejected`, `refunded` (default: `pending`) |
| stripe_refund_id | CharField(255) | Stripe refund ID (blank) |
| admin_notes | TextField | Internal admin notes (blank) |
| created_at | DateTimeField | Auto-set on creation |
| updated_at | DateTimeField | Auto-set on update |

**DB table:** `store_refund_requests`

## API Endpoints

### Store Categories (Public)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/categories/` | List active categories with item counts |
| GET | `/categories/{slug}/` | Category detail with active items |

**ViewSet:** `StoreCategoryViewSet` (ReadOnlyModelViewSet)
- Permission: `AllowAny`
- Lookup field: `slug`
- Search fields: `name`, `description`
- Ordering fields: `display_order`, `name`

### Store Items (Public)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/items/` | List active items with filtering |
| GET | `/items/{slug}/` | Item detail with owner count and ownership status |
| GET | `/items/featured/` | Featured items (epic + legendary, max 10) |

**ViewSet:** `StoreItemViewSet` (ReadOnlyModelViewSet)
- Permission: `AllowAny`
- Lookup field: `slug`
- Filter fields: `category__slug`, `item_type`, `rarity`
- Search fields: `name`, `description`
- Ordering fields: `price`, `created_at`, `name`, `rarity`

### User Inventory (Authenticated)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/inventory/` | List owned items |
| GET | `/inventory/{id}/` | Owned item detail |
| POST | `/inventory/{id}/equip/` | Equip or unequip an item (body: `{"equip": true/false}`) |

**ViewSet:** `UserInventoryViewSet` (ReadOnlyModelViewSet + custom actions)
- Permission: `IsAuthenticated`
- Filter fields: `is_equipped`, `item__item_type`
- Ordering fields: `purchased_at`, `is_equipped`

### Wishlist (Authenticated)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/wishlist/` | List wishlisted items |
| POST | `/wishlist/` | Add item to wishlist (body: `{"item_id": "UUID"}`) |
| DELETE | `/wishlist/{id}/` | Remove item from wishlist |

### Store Items -- Preview (Public)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/items/{slug}/preview/` | Try-before-buy preview config (theme colors, frame styles, etc.) |

### Gifts (Authenticated + CanUseStore for send)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/gifts/send/` | Purchase and send an item as a gift (body: `{"item_id": "UUID", "recipient_id": "UUID", "message": "text"}`) |
| GET | `/gifts/` | List unclaimed gifts received by the current user |
| POST | `/gifts/{id}/claim/` | Claim a received gift (adds to inventory) |

### Refunds (Authenticated)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/refunds/` | Request a refund (body: `{"inventory_id": "UUID", "reason": "text"}`) |
| GET | `/refunds/` | List user's refund requests |

### Refunds -- Admin (IsAdminUser)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/admin/refunds/` | List all refund requests (filterable by `?status=pending`) |
| POST | `/admin/refunds/` | Approve or reject (body: `{"refund_id": "UUID", "action": "approve|reject", "admin_notes": "text"}`) |

### Purchase Flow (Authenticated + CanUseStore)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/purchase/` | Create Stripe PaymentIntent for an item (body: `{"item_id": "UUID"}`) |
| POST | `/purchase/confirm/` | Confirm purchase after payment succeeds (body: `{"item_id": "UUID", "payment_intent_id": "pi_..."}`) |
| POST | `/purchase/xp/` | Purchase an item using XP (body: `{"item_id": "UUID"}`) |
| GET | `/inventory/history/` | Get purchase history |

**Views:** `PurchaseView`, `PurchaseConfirmView`, `XPPurchaseView` (APIView)
- Permission: `IsAuthenticated` + `CanUseStore` (premium+ subscription required)

## Serializers

| Serializer | Purpose |
|------------|---------|
| `StoreItemSerializer` | Item with `rarity_display`, `item_type_display`, `category_name`, `preview_type_display` |
| `StoreItemDetailSerializer` | Extends StoreItemSerializer with `owners_count` and `is_owned` |
| `StoreCategorySerializer` | Category with computed `items_count` |
| `StoreCategoryDetailSerializer` | Category with nested active items list |
| `UserInventorySerializer` | Inventory entry with nested `StoreItemSerializer` |
| `PurchaseSerializer` | Input: `item_id` (UUID). Validates item exists, is active, and not already owned |
| `PurchaseConfirmSerializer` | Input: `item_id` (UUID) + `payment_intent_id` (must start with `pi_`) |
| `XPPurchaseSerializer` | Input: `item_id` (UUID). Validates item exists, is active, and has xp_price > 0 |
| `EquipSerializer` | Input: `equip` (boolean) |
| `WishlistSerializer` | Input: `item_id` (UUID). Validates item exists and not already wishlisted |
| `GiftSendSerializer` | Input: `item_id`, `recipient_id` (UUIDs), optional `message`. Sanitizes message |
| `GiftSerializer` | Read-only display with nested item + sender/recipient names |
| `ItemPreviewSerializer` | Preview config with `preview_type`, `preview_data`, `is_owned` |
| `RefundRequestSerializer` | Input: `inventory_id` (UUID), `reason` (sanitized) |
| `RefundRequestDisplaySerializer` | Read-only display with `item_name`, status, admin notes |
| `RefundProcessSerializer` | Admin input: `refund_id` (UUID), `action` (approve/reject), optional `admin_notes` |

## Services (StoreService)

All store business logic is encapsulated in `StoreService`:

| Method | Description |
|--------|-------------|
| `create_payment_intent(user, item)` | Create Stripe PaymentIntent; returns `client_secret`, `payment_intent_id`, `amount` |
| `confirm_purchase(user, item, payment_intent_id)` | Verify payment with Stripe and create inventory entry (atomic) |
| `purchase_with_xp(user, item)` | Deduct XP and create inventory entry (atomic, row-level locking) |
| `get_user_inventory(user)` | Return queryset of user's inventory with prefetched relations |
| `equip_item(user, inventory_id)` | Equip item, auto-unequip others of same type (atomic) |
| `unequip_item(user, inventory_id)` | Unequip an item |
| `send_gift(sender, recipient, item, message)` | Create Stripe PaymentIntent + Gift record (atomic) |
| `claim_gift(user, gift_id)` | Claim gift, create inventory entry, mark gift claimed (atomic) |
| `request_refund(user, inventory_id, reason)` | Create RefundRequest (guards: ownership, paid purchase, no duplicate pending) |
| `process_refund(refund_request_id, approve, admin_notes)` | Approve (Stripe refund + delete inventory) or reject (atomic) |

### Custom Exceptions

| Exception | Description |
|-----------|-------------|
| `StoreServiceError` | Base exception for all store errors |
| `ItemNotFoundError` | Item does not exist |
| `ItemAlreadyOwnedError` | User already owns the item |
| `ItemNotActiveError` | Item is not available for purchase |
| `PaymentVerificationError` | Stripe payment verification failed |
| `InventoryNotFoundError` | Inventory entry not found |
| `InsufficientXPError` | User does not have enough XP for the purchase |

### Payment Verification

The `confirm_purchase` method performs four checks before granting the item:
1. User does not already own the item (race condition guard)
2. PaymentIntent status is `succeeded`
3. PaymentIntent amount matches the item price
4. PaymentIntent metadata `user_id` matches the requesting user

## Configuration

### Environment Variables

| Variable | Description |
|----------|-------------|
| `STRIPE_SECRET_KEY` | Stripe API secret key (shared with subscriptions app) |

## Admin

All six models are registered with Django admin:

- **StoreCategoryAdmin** - Includes `StoreItemInline` for editing items within categories. Shows `items_count`
- **StoreItemAdmin** - List-editable `is_active` and `price` fields. Shows `owners_count`. Filter by item type, rarity, category
- **UserInventoryAdmin** - Filter by equipped status, item type, rarity. Search by user email, item name, or payment intent ID
- **WishlistAdmin** - Filter by item type, rarity, date. Search by user email, item name
- **GiftAdmin** - Filter by claimed status, item type, date. Search by sender/recipient email, item name
- **RefundRequestAdmin** - Filter by status, date. Read-only user/inventory/reason fields; editable status, admin_notes, stripe_refund_id
