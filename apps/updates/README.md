# App Updates (OTA)

Self-hosted Over-The-Air web bundle update system for Stepora mobile apps.

## Models

### AppBundle
- `bundle_id` — Auto-generated (`b-YYYYMMDD-HHMMSS`)
- `bundle_file` — ZIP stored in dedicated S3 bucket (`ReleasesStorage`)
- `checksum` — SHA-256 hex digest (auto-computed)
- `signature` — RSA signature base64 (for code signing)
- `strategy` — `silent` (next restart) or `notify` (prompt user)
- `platform` — `all`, `android`, or `ios`
- `min_app_version` — Minimum native versionCode
- `is_active` — Only active bundles are served

## API Endpoints

### GET /api/v1/updates/check/
Public. Returns latest compatible bundle or 204.

### POST /api/v1/updates/upload/
Admin only. Accepts multipart ZIP + metadata. Verifies RSA signature if `OTA_PUBLIC_KEY_PATH` is configured.

## Security

- RSA-2048 asymmetric code signing
- Triple verification: deploy script signs -> Django verifies -> Capacitor plugin re-verifies
- Dedicated S3 bucket (separate from user media)
- Signed URLs (1h expiry)

## Settings

```python
# config/settings/production.py
OTA_PUBLIC_KEY_PATH = os.getenv('OTA_PUBLIC_KEY_PATH', '')
```

See [OTA-UPDATES.md](../../../stepora-frontend/OTA-UPDATES.md) for complete documentation.
