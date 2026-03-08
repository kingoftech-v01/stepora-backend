import hashlib
from datetime import datetime

from django.db import models
from django.utils import timezone

from core.storage import ReleasesStorage


def _bundle_upload_path(instance, filename):
    """Store bundles as bundles/<bundle_id>.zip in the releases S3 bucket."""
    return f"bundles/{instance.bundle_id}.zip"


def _generate_bundle_id():
    """Auto-generate a unique, sortable bundle ID: b-YYYYMMDD-HHMMSS."""
    now = timezone.now()
    return now.strftime("b-%Y%m%d-%H%M%S")


class AppBundle(models.Model):
    """
    Represents a web bundle for OTA live updates.
    Each bundle is a zip of the frontend dist/ folder,
    stored in the dedicated releases S3 bucket.
    """

    STRATEGY_CHOICES = [
        ("silent", "Silent — apply on next restart"),
        ("notify", "Notify — show user a restart prompt"),
    ]

    PLATFORM_CHOICES = [
        ("all", "All platforms"),
        ("android", "Android only"),
        ("ios", "iOS only"),
    ]

    bundle_id = models.CharField(
        max_length=50, unique=True, default=_generate_bundle_id,
        help_text="Auto-generated unique identifier (e.g. b-20260308-153045)",
    )
    min_app_version = models.PositiveIntegerField(
        default=1,
        help_text="Minimum native versionCode required to apply this bundle",
    )
    platform = models.CharField(
        max_length=10, choices=PLATFORM_CHOICES, default="all",
    )
    strategy = models.CharField(
        max_length=10, choices=STRATEGY_CHOICES, default="notify",
    )
    bundle_file = models.FileField(
        upload_to=_bundle_upload_path,
        storage=ReleasesStorage,
        help_text="The zipped web bundle (dist/)",
    )
    checksum = models.CharField(
        max_length=128, blank=True, default="",
        help_text="SHA-256 hex digest of the zip file (auto-computed on upload)",
    )
    signature = models.TextField(
        blank=True, default="",
        help_text="RSA signature of the checksum (base64, for code signing)",
    )
    message = models.CharField(
        max_length=255, blank=True, default="",
        help_text="Optional message to show with notify strategy",
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Only active bundles are served to clients",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "App Bundle"
        verbose_name_plural = "App Bundles"

    def __str__(self):
        return f"Bundle {self.bundle_id} ({'active' if self.is_active else 'inactive'})"

    def compute_checksum(self):
        """Compute SHA-256 checksum of the bundle file."""
        if not self.bundle_file:
            return ""
        sha = hashlib.sha256()
        self.bundle_file.seek(0)
        for chunk in self.bundle_file.chunks(8192):
            sha.update(chunk)
        self.bundle_file.seek(0)
        return sha.hexdigest()

    def save(self, *args, **kwargs):
        # Auto-compute checksum if not provided
        if self.bundle_file and not self.checksum:
            self.checksum = self.compute_checksum()
        super().save(*args, **kwargs)
