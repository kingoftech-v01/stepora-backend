# Social Feed Algorithm & CRUD Permissions Spec

## Overview
The social feed uses a 3-tier algorithm to rank and display posts, combined with
ownership-based CRUD permissions and post visibility controls.

## Feed Algorithm (3 Tiers)

### Tier 0 — Own Posts (merged into Tier 1)
- All posts by the current user (any visibility).
- Merged chronologically with Tier 1 results.

### Tier 1 — Friends (highest priority, ~8 per page)
- Posts from accepted friends.
- All visibility levels except `private`.
- Blocked users excluded.

### Tier 2 — Friends of Friends (medium priority, ~4 per page)
- Public posts only from 2nd-degree connections.
- Capped at 500 user IDs to limit query cost.
- Excludes self, Tier 1, and blocked users.

### Tier 3 — Follows + Trending (lowest priority, ~3 per page)
- Public posts from followed users not in Tier 1/2.
- Trending: high-engagement public posts from the last 7 days,
  ordered by likes_count + comments_count.

### Interleaving Pattern
Per page of 15: `T1 T1 T2 T1 T1 T3 T1 T1 T2 T1 T3 T1 T2 T1 T3`
Fallback fills from other tiers when a tier is exhausted.

### Exclusions
- Blocked users (both directions).
- Private posts from non-owners.
- Posts linked to non-public dreams (unless own).

## CRUD Permissions

| Action  | Who               | Behaviour                           |
|---------|-------------------|-------------------------------------|
| Create  | Any authenticated | Creates post owned by request.user  |
| Read    | Any authenticated | Filtered by visibility rules        |
| Update  | Owner only        | 403 PermissionDenied for non-owners |
| Delete  | Owner only        | 403 PermissionDenied for non-owners |

### Editable Fields (Update)
- `content` (sanitized)
- `visibility` (public / followers / private)
- `post_type` (regular / achievement / milestone / event)
- `gofundme_url` (sanitized)

## Post Visibility

| Value      | Who can see                               |
|------------|-------------------------------------------|
| `public`   | Everyone (appears in Tier 2/3)            |
| `followers`| Friends + followers of the author         |
| `private`  | Only the post author                      |

## Serializer: `is_owner` Field
- Boolean field computed per-request.
- `True` when `request.user == post.user`.
- Used by the frontend to show edit/delete controls.

## Frontend Behaviour
- Own posts show a 3-dot menu (MoreHorizontal) with Edit and Delete options.
- Edit opens CreatePostModal pre-filled with post content/visibility.
- Delete shows a confirmation modal before executing.
- Visibility icon (Globe/Users/Lock) shown on each post card.
- Visibility selector available on post creation and edit.
