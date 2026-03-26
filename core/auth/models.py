"""
Custom authentication models replacing django-allauth.

EmailAddress — tracks per-user email verification status.
SocialAccount — links OAuth provider identities to users.
LoginEvent — records login attempts with IP + User-Agent for anomaly detection.
"""

from django.conf import settings
from django.db import models


class EmailAddress(models.Model):
    """Tracks email addresses and their verification status for each user."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="email_addresses",
    )
    email = models.EmailField(max_length=254, db_index=True)
    verified = models.BooleanField(default=False)
    primary = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "dp_auth_email_address"
        unique_together = [("user", "email")]
        verbose_name_plural = "email addresses"

    def __str__(self):
        return f'{self.email} ({"verified" if self.verified else "unverified"})'

    def verify(self):
        if not self.verified:
            self.verified = True
            self.save(update_fields=["verified"])

    def set_as_primary(self):
        EmailAddress.objects.filter(user=self.user, primary=True).exclude(
            pk=self.pk
        ).update(primary=False)
        if not self.primary:
            self.primary = True
            self.save(update_fields=["primary"])


class SocialAccount(models.Model):
    """Links an OAuth provider identity (Google, Apple) to a user."""

    PROVIDER_CHOICES = [
        ("google", "Google"),
        ("apple", "Apple"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="social_accounts",
    )
    provider = models.CharField(max_length=30, choices=PROVIDER_CHOICES)
    uid = models.CharField(max_length=255)
    extra_data = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_login = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "dp_auth_social_account"
        unique_together = [("provider", "uid")]
        indexes = [
            models.Index(fields=["user", "provider"]),
        ]

    def __str__(self):
        return f"{self.provider}:{self.uid} → {self.user.email}"


class LoginEvent(models.Model):
    """Records login attempts with IP + User-Agent for anomaly detection (V-823).

    Stores every successful login so admins can review unusual activity
    (new device, new IP, geographic anomalies).
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="login_events",
    )
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True, default="")
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    login_method = models.CharField(
        max_length=30,
        choices=[
            ("password", "Password"),
            ("google", "Google"),
            ("apple", "Apple"),
            ("2fa", "Two-Factor"),
        ],
        default="password",
    )

    class Meta:
        db_table = "dp_auth_login_event"
        ordering = ["-timestamp"]
        indexes = [
            models.Index(fields=["user", "-timestamp"]),
            models.Index(fields=["ip_address"]),
        ]

    def __str__(self):
        return f"{self.user_id} from {self.ip_address} at {self.timestamp}"
