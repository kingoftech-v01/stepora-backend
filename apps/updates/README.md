# App Updates (OTA)

Self-hosted Over-The-Air web bundle update system for Stepora mobile apps (Capacitor).

## Purpose

Deliver web bundle updates to native mobile apps without going through App Store / Play Store review. The backend stores versioned ZIP bundles in a dedicated S3 bucket. Mobile clients poll for updates at startup and from the App Version settings screen.

## Models

### AppBundle

| Field | Type | Description |
|-------|------|-------------|
| `bundle_id` | CharField(50), unique | Auto-generated: `b-YYYYMMDD-HHMMSS` |
| `min_app_version` | PositiveIntegerField | Minimum native versionCode required |
| `platform` | CharField(10) | `all`, `android`, or `ios` |
| `strategy` | CharField(10) | `silent` (apply on next restart) or `notify` (prompt user) |
| `bundle_file` | FileField | ZIP of frontend dist/, stored in `ReleasesStorage` (dedicated S3 bucket) |
| `checksum` | CharField(128) | SHA-256 hex digest (auto-computed on save if empty) |
| `signature` | TextField | RSA signature (base64) for code signing |
| `message` | CharField(255) | Optional message shown with `notify` strategy |
| `is_active` | BooleanField | Only active bundles are served to clients |
| `created_at` | DateTimeField | Auto-set on creation |

**Ordering:** `-created_at` (most recent first)

**Key behaviors:**
- `save()` auto-computes `checksum` via SHA-256 if field is empty and file is present
- `compute_checksum()` reads the file in 8KB chunks
- `_generate_bundle_id()` uses `timezone.now()` for sortable, unique IDs
- `_bundle_upload_path()` stores as `bundles/<bundle_id>.zip` regardless of upload filename

## API Endpoints

### GET /api/v1/updates/check/

**Permission:** `AllowAny` (public, no auth required)

**Query Parameters:**
| Param | Type | Description |
|-------|------|-------------|
| `platform` | string | `android` or `ios` -- filters bundles by platform |
| `app_version` | string | Native versionCode -- filters by `min_app_version <= value` |
| `bundle_id` | string | Currently installed bundle ID -- returns 204 if already current |

**Response 200 (update available):**
```json
{
  "bundle_id": "b-20260322-120000",
  "url": "https://s3.../bundles/b-20260322-120000.zip?X-Amz-...",
  "strategy": "notify",
  "checksum": "abc123...",
  "signature": "base64...",
  "message": "Bug fixes and improvements",
  "min_app_version": 5
}
```

**Response 204 (no update):** Empty body, returned when:
- No active bundles exist
- No bundles match platform/version filters
- Client already has the latest bundle (`bundle_id` matches)

**Filtering logic:**
1. Only `is_active=True` bundles considered
2. If `app_version > 0`: filter `min_app_version <= app_version`
3. If `platform` is `android` or `ios`: filter `platform IN ('all', <platform>)`
4. First result (most recent by `-created_at`) is returned
5. Empty strings for `checksum`, `signature`, `message` returned as `null`

### POST /api/v1/updates/upload/

**Permission:** `IsAdminUser` (staff/superuser only)

**Content-Type:** `multipart/form-data`

**Fields:**
| Field | Required | Default | Description |
|-------|----------|---------|-------------|
| `file` | Yes | -- | ZIP bundle file (must end in `.zip`) |
| `strategy` | No | `notify` | `silent` or `notify` (invalid values default to `notify`) |
| `platform` | No | `all` | `all`, `android`, or `ios` (invalid values default to `all`) |
| `min_app_version` | No | `1` | Integer (invalid values default to `1`) |
| `message` | No | `""` | Optional update message |
| `signature` | No | `""` | RSA signature (base64) |

**Response 201 (success):**
```json
{
  "bundle_id": "b-20260322-120000",
  "checksum": "abc123...",
  "url": "https://s3.../bundles/...",
  "strategy": "notify",
  "platform": "all",
  "signed": false,
  "created_at": "2026-03-22T12:00:00+00:00"
}
```

**Response 400 (error):**
- No file provided
- File is not a `.zip` archive
- Signature required but not provided (when `OTA_PUBLIC_KEY_PATH` is set)
- Invalid signature (when code signing is enabled)

**Signature verification:**
- If `OTA_PUBLIC_KEY_PATH` is configured and signature is provided: verifies RSA-PKCS1v15-SHA256
- If key is configured but no signature: rejects with 400
- If no key configured: accepts any upload (signature optional)

**Backward-compatible URL:** Both `/api/v1/updates/` and `/api/updates/` prefixes work.

## Frontend Screens

### AppVersionScreen (`/app-version`)
- Located at `src/pages/profile/AppVersionScreen/`
- Three device variants: Mobile, Tablet, Desktop
- Shared hook: `useAppVersionScreen.js`
- Shows: app version, build number, platform info, API version, last sync time
- **OTA update button:** Check for updates -> Download -> Install (or auto-apply for silent)
- **Store update button:** Opens Play Store / App Store when native store update is available
- **Service worker updates:** Web platform uses Service Worker update detection
- **Bundle ID display:** Shows current OTA bundle ID on native platforms

### UpdateReadyModal (`src/components/shared/UpdateReadyModal.jsx`)
- Global modal triggered by `dp-update-ready` custom event
- Shows when OTA download completes with `notify` strategy
- "Restart Now" button calls `applyUpdate()` to reload with new bundle
- "Later" button dismisses (bundle applies on next cold start)

### liveUpdate Service (`src/services/liveUpdate.js`)
- Event-driven architecture with subscriber pattern (`onUpdateEvent`)
- OTA: `checkForOTAUpdate()` -> `downloadUpdate()` -> `applyUpdate()`
- Store: `checkStoreUpdate()`, `openAppStore()`, `performImmediateStoreUpdate()`
- Utilities: `getCurrentBundle()`, `resetToDefault()`, `getDownloadedBundles()`
- Uses `@capawesome/capacitor-live-update` (OTA) and `@capawesome/capacitor-app-update` (store)

## Business Rules

1. **Public check, admin upload:** Anyone can check for updates; only staff can upload bundles.
2. **Platform targeting:** Bundles can target `all`, `android`, or `ios`. Clients on android see `all` + `android` bundles.
3. **Version gating:** `min_app_version` prevents old native shells from loading incompatible web bundles.
4. **Deduplication:** If client's `bundle_id` matches the latest, returns 204 (no update).
5. **Strategy:** `silent` = auto-apply on next restart; `notify` = show modal, user decides.
6. **Code signing:** Optional RSA-2048 signature verification. When enabled, unsigned uploads are rejected.
7. **Storage:** Bundles stored in dedicated S3 bucket (`stepora-releases`) with signed URLs (1h expiry).
8. **Ordering:** Most recent bundle is always served (no rollback via API -- deactivate via admin).

## Security

- RSA-2048 asymmetric code signing (optional, enabled via `OTA_PUBLIC_KEY_PATH`)
- Triple verification: deploy script signs -> Django verifies -> Capacitor plugin re-verifies
- Dedicated S3 bucket (separate from user media)
- Pre-signed URLs with 1h expiry
- Admin-only upload (DRF `IsAdminUser` permission)
- SHA-256 checksum integrity verification

## Settings

```python
# config/settings/production.py
OTA_PUBLIC_KEY_PATH = os.getenv('OTA_PUBLIC_KEY_PATH', '')
```

## Admin

Registered in Django admin with:
- **List display:** bundle_id, platform, strategy, min_app_version, is_active, created_at
- **List filters:** is_active, platform, strategy
- **Editable in list:** is_active, strategy (quick toggle without opening detail)
- **Search:** bundle_id, message
- **Fieldsets:** Main (id, file, checksum), Targeting (platform, version), Behavior (strategy, message, active), Info (created_at)

## Test Coverage

- **Backend:** `apps/updates/tests/test_updates_complete.py` -- 91 tests, 96%+ coverage
  - Model: fields, defaults, __str__, checksum, save, Meta, choices, ordering
  - UpdateCheckView: filtering, dedup, permissions, edge cases, combined filters
  - BundleUploadView: auth, validation, defaults, strategy/platform, checksum, signature
  - Signature verification: _verify_signature, _get_public_key
  - Admin registration, apps config, URL routing
- **Frontend:** `useAppVersionScreen.test.js` -- 26 tests
  - Initial state, mounted animation, stagger helper
  - Info items, lastSyncLabel, apiVersionLabel
  - handleCheckUpdate (SW paths), handleInstallUpdate, handleOpenStore
  - Returned values completeness
