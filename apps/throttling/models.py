from django.db import models
from django.utils import timezone

from apps.core.models import BaseModel


class ThrottlingScope(models.TextChoices):
    GLOBAL = "GLOBAL", "Global (All Traffic)"
    IP = "IP", "Client IP Address"
    USER = "USER", "Authenticated User"
    ORGANIZATION = "ORGANIZATION", "Organization Workspace"
    API_KEY = "API_KEY", "Developer API Key"


class ThrottlingRule(BaseModel):
    """
    Dynamic rate limiting rule evaluated across requests.
    Supports path pattern matching, HTTP method filtering, and burst allowances.
    """

    name = models.CharField(
        max_length=100,
        unique=True,
        help_text="Unique programmatic rule identifier (e.g., default_anon, auth_login, org_tier_pro).",
    )
    scope_type = models.CharField(
        max_length=20,
        choices=ThrottlingScope.choices,
        default=ThrottlingScope.IP,
        db_index=True,
        help_text="The subject dimension to throttle against.",
    )
    rate_limit = models.PositiveIntegerField(
        help_text="Maximum number of requests permitted within the time period.",
    )
    period_seconds = models.PositiveIntegerField(
        default=60,
        help_text="Rolling sliding window duration in seconds (e.g., 60 for 1 minute, 3600 for 1 hour).",
    )
    burst_limit = models.PositiveIntegerField(
        default=0,
        help_text="Optional instantaneous burst allowance over standard quota (0 = disabled).",
    )
    path_pattern = models.CharField(
        max_length=255,
        blank=True,
        default="",
        help_text="Optional regex or wildcard URL pattern (e.g., /api/v1/iam/auth/*). Blank applies to all endpoints.",
    )
    http_methods = models.CharField(
        max_length=50,
        blank=True,
        default="",
        help_text="Comma-separated HTTP methods (e.g., POST,PUT,DELETE). Blank matches all methods.",
    )
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        help_text="Whether this throttling rule is actively enforced.",
    )
    description = models.TextField(
        blank=True,
        default="",
        help_text="Human-readable description of this rate limit rule.",
    )

    class Meta:
        db_table = "throttle_rules"
        ordering = ["-created_at"]
        verbose_name = "Throttling Rule"
        verbose_name_plural = "Throttling Rules"

    def __str__(self) -> str:
        return f"{self.name} ({self.rate_limit} req / {self.period_seconds}s [{self.scope_type}])"


class IPBlocklist(BaseModel):
    """
    Blacklisted IP address entry for early rejection and anti-abuse defense.
    """

    ip_address = models.GenericIPAddressField(
        db_index=True,
        help_text="IPv4 or IPv6 address blocked from accessing the API.",
    )
    reason = models.CharField(
        max_length=255,
        help_text="Reason for blacklisting (e.g., Excessive 401 login attempts, DDoS, credential stuffing).",
    )
    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        help_text="Expiration timestamp for temporary blocks. Leave null for permanent ban.",
    )
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        help_text="Whether this IP blacklist entry is active.",
    )

    class Meta:
        db_table = "throttle_ip_blocklist"
        ordering = ["-created_at"]
        verbose_name = "IP Blocklist Entry"
        verbose_name_plural = "IP Blocklist Entries"

    def __str__(self) -> str:
        expiry_info = f"expires {self.expires_at}" if self.expires_at else "permanent"
        return f"{self.ip_address} - {self.reason} ({expiry_info})"

    @property
    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        return timezone.now() >= self.expires_at
