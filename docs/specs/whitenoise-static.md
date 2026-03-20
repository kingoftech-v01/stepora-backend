# WhiteNoise Static Files + StaticFilesStorage Fix

## Evaluation

### Current State
- **WhiteNoise is already in `requirements/base.txt`** (`whitenoise>=6.5.0`, installed as 6.12.0)
- **WhiteNoise middleware is already in `base.py`** (`whitenoise.middleware.WhiteNoiseMiddleware`, line 80)
- **Production `STORAGES["staticfiles"]`** uses `StaticFilesStorage` (plain, no compression/manifest)
- **Dockerfile** runs `collectstatic --noinput --clear` at build time
- **ASGI**: daphne serves the app; WhiteNoise middleware works as Django middleware (sync-to-async adapted by Django automatically)
- **Media files**: already on S3 via `storages.backends.s3boto3.S3Boto3Storage`

### Is WhiteNoise the right choice for AWS ECS?

**YES, WhiteNoise is the correct choice for this setup.** Reasons:

1. **Static files are admin-only**: This is a REST API backend. The only static files are Django Admin CSS/JS and DRF browsable API assets. There is no frontend bundle served from this container.
2. **Volume is minimal**: A few hundred KB of admin static files. Not worth S3/CloudFront infrastructure for this.
3. **Zero additional infra**: WhiteNoise serves files directly from the container's filesystem. No S3 bucket, no CloudFront distribution, no extra cost.
4. **Already partially configured**: WhiteNoise middleware is in base.py, dependency is in requirements. Just the storage backend is wrong.
5. **ASGI compatible**: WhiteNoise middleware works with daphne via Django's built-in sync-to-async middleware adaptation. No ASGI-specific wrapper needed (the `WhiteNoise(application)` ASGI wrapping pattern is an alternative but not required when using the Django middleware approach).

### What needs fixing

1. **`STORAGES["staticfiles"]` backend in production.py**: Currently uses `StaticFilesStorage` (plain). Should use `whitenoise.storage.CompressedManifestStaticFilesStorage` for gzip/brotli pre-compression and cache-busting hashes. This is the whole point of WhiteNoise — serve compressed, cache-friendly static files.
2. **Fallback safety**: `CompressedManifestStaticFilesStorage` can crash during `collectstatic` if static files reference missing assets. Add a safe fallback that catches `ValueError` from manifest misses.
3. **Cache headers**: WhiteNoise defaults are good (immutable files get `Cache-Control: max-age=315360000, public, immutable`), but we should explicitly set `WHITENOISE_MAX_AGE` for non-hashed files.

### Alternative: S3/CloudFront for static files
**NOT recommended** for this use case:
- Adds complexity (need `django-storages` S3 backend for staticfiles, CloudFront origin for static prefix)
- Extra cost for negligible traffic (admin panel only)
- Requires `collectstatic` to upload to S3 during deploy (slower CI/CD)
- Already have media on S3 — static files are a different concern

## Implementation

### Changes

1. **`config/settings/base.py`**: Add `WHITENOISE_MAX_AGE` and `STORAGES` with `CompressedManifestStaticFilesStorage`
2. **`config/settings/production.py`**: Override staticfiles backend to use WhiteNoise compressed storage; keep media on S3
3. No ASGI changes needed — middleware approach works

### Test Plan
- Verify `STORAGES["staticfiles"]` backend is `CompressedManifestStaticFilesStorage` in production
- Verify WhiteNoise middleware is in MIDDLEWARE list
- Verify `STATIC_ROOT` is set
- Verify `WHITENOISE_MAX_AGE` is configured
- Verify media storage remains S3 in production
- Verify development settings use plain StaticFilesStorage (no WhiteNoise compression needed for dev)
