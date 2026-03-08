"""
Dedicated S3 storage backend for release artifacts.

Bucket structure:
  dreamplanner-releases/
  ├── bundles/          # OTA web bundles (.zip)
  ├── backups/          # Database backups (.sql.gz)
  └── builds/           # Native app builds
      ├── android/      # APK/AAB files
      └── ios/          # IPA files

Configuration (environment variables):
  AWS_RELEASES_BUCKET       — S3 bucket name (default: dreamplanner-releases)
  AWS_RELEASES_REGION       — AWS region (default: same as main S3)
  AWS_RELEASES_CUSTOM_DOMAIN — Optional CloudFront domain for downloads

Uses the same AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY as the main S3.
"""

import os

from django.conf import settings
from storages.backends.s3boto3 import S3Boto3Storage


class ReleasesStorage(S3Boto3Storage):
    """S3 storage backend dedicated to release artifacts (bundles, backups, builds)."""

    def __init__(self, **kwargs):
        kwargs.setdefault("bucket_name", os.getenv(
            "AWS_RELEASES_BUCKET", "dreamplanner-releases"
        ))
        kwargs.setdefault("region_name", os.getenv(
            "AWS_RELEASES_REGION",
            getattr(settings, "AWS_S3_REGION_NAME", "eu-west-1"),
        ))
        custom_domain = os.getenv("AWS_RELEASES_CUSTOM_DOMAIN")
        if custom_domain:
            kwargs.setdefault("custom_domain", custom_domain)
        # Files in this bucket should be readable by the app
        kwargs.setdefault("default_acl", "private")
        kwargs.setdefault("querystring_auth", True)
        kwargs.setdefault("querystring_expire", 3600)  # 1h signed URLs
        super().__init__(**kwargs)
