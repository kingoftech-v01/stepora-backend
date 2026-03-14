"""
Dedicated S3 storage backend for release artifacts.

Bucket structure:
  stepora-releases/
  ├── bundles/          # OTA web bundles (.zip)
  ├── backups/          # Database backups (.sql.gz)
  └── builds/           # Native app builds
      ├── android/      # APK/AAB files
      └── ios/          # IPA files

Configuration (environment variables):
  AWS_RELEASES_BUCKET       — S3 bucket name (default: stepora-releases)
  AWS_RELEASES_REGION       — AWS region (default: same as main S3)
  AWS_RELEASES_CUSTOM_DOMAIN — Optional CloudFront domain for downloads

Uses the same AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY as the main S3.
"""

import os

import boto3
from botocore.config import Config
from django.conf import settings
from storages.backends.s3boto3 import S3Boto3Storage

# ── Pre-signed URL generation for private media ─────────────────

_s3_client = None


def _get_s3_client():
    global _s3_client
    if _s3_client is None:
        region = getattr(settings, "AWS_S3_REGION_NAME", "eu-west-3")
        _s3_client = boto3.client(
            "s3",
            region_name=region,
            config=Config(signature_version="s3v4"),
        )
    return _s3_client


def presigned_url(file_field, expires_in=3600):
    """Generate a pre-signed URL for a private S3 object.

    Args:
        file_field: Django FieldFile (ImageField/FileField value).
        expires_in: URL lifetime in seconds (default 1 hour).

    Returns:
        Pre-signed URL string, or empty string if no file.
    """
    if not file_field:
        return ""
    bucket = getattr(settings, "AWS_STORAGE_BUCKET_NAME", None)
    if not bucket:
        # Local dev — return relative URL
        return file_field.url
    key = f"{getattr(settings, 'AWS_MEDIA_LOCATION', 'media')}/{file_field.name}"
    return _get_s3_client().generate_presigned_url(
        "get_object",
        Params={"Bucket": bucket, "Key": key},
        ExpiresIn=expires_in,
    )


class ReleasesStorage(S3Boto3Storage):
    """S3 storage backend dedicated to release artifacts (bundles, backups, builds)."""

    def __init__(self, **kwargs):
        kwargs.setdefault(
            "bucket_name", os.getenv("AWS_RELEASES_BUCKET", "stepora-releases")
        )
        kwargs.setdefault(
            "region_name",
            os.getenv(
                "AWS_RELEASES_REGION",
                getattr(settings, "AWS_S3_REGION_NAME", "eu-west-1"),
            ),
        )
        custom_domain = os.getenv("AWS_RELEASES_CUSTOM_DOMAIN")
        if custom_domain:
            kwargs.setdefault("custom_domain", custom_domain)
        # Files in this bucket should be readable by the app
        kwargs.setdefault("default_acl", "private")
        kwargs.setdefault("querystring_auth", True)
        kwargs.setdefault("querystring_expire", 3600)  # 1h signed URLs
        super().__init__(**kwargs)
