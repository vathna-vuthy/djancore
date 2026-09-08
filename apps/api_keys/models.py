import hashlib
import hmac
import ipaddress
import secrets
from typing import Any, Self

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.core.models import BaseModel


class APIKey(BaseModel):
    """
    Developer API Key model with secure hashed storage, IP filtering,
    optional expiration, and scoped IAM permission bindings.
    """

    name = models.CharField(
        max_length=150,
        help_text="Friendly label for identifying this API key.",
    )
    prefix = models.CharField(
        max_length=16,
        unique=True,
        db_index=True,
        help_text="Public key prefix used for O(1) database lookup.",
    )
    hashed_key = models.CharField(
        max_length=128,
        help_text="Cryptographically secure SHA-256 hash of the secret portion.",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="api_keys",
        help_text="Owner user account for this API key.",
    )
    roles = models.ManyToManyField(
        "iam.Role",
        blank=True,
        related_name="api_keys",
        help_text="Optional scoped roles limiting this key's access.",
    )
    permissions = models.ManyToManyField(
        "iam.Permission",
        blank=True,
        related_name="api_keys",
        help_text="Optional direct scoped permissions limiting this key's access.",
    )
    allowed_ips = models.JSONField(
        default=list,
        blank=True,
        help_text="List of allowed IP addresses or CIDR blocks (empty allows all).",
    )
    rate_limit = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Optional custom rate limit (requests per minute).",
    )
    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Optional expiration timestamp after which the key becomes invalid.",
    )
    last_used_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp of the most recent authenticated API request.",
    )
    last_used_ip = models.GenericIPAddressField(
        null=True,
        blank=True,
        help_text="Client IP address of the most recent authenticated API request.",
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Active status toggle for instant key revocation.",
    )

    class Meta(BaseModel.Meta):
        db_table = "api_keys"
        verbose_name = "API key"
        verbose_name_plural = "API keys"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.name} ({self.prefix}...)"

    @property
    def is_expired(self) -> bool:
        """Check if the key has passed its expiration datetime."""
        if self.expires_at is None:
            return False
        return timezone.now() >= self.expires_at

    @property
    def is_valid(self) -> bool:
        """Check if the key is active, not soft-deleted, and not expired."""
        return self.is_active and not self.is_deleted and not self.is_expired

    @classmethod
    def hash_secret(cls, secret: str) -> str:
        """Hash the secret portion using SHA-256."""
        return hashlib.sha256(secret.encode("utf-8")).hexdigest()

    @classmethod
    def generate_raw_components(cls, key_type: str = "live") -> tuple[str, str, str]:
        """
        Generate (prefix, secret, full_raw_key).
        Format: djc_{key_type}_{prefix}_{secret}
        """
        prefix = secrets.token_hex(4)  # 8 chars
        secret = secrets.token_urlsafe(24)  # 32 chars
        raw_key = f"djc_{key_type}_{prefix}_{secret}"
        return prefix, secret, raw_key

    @classmethod
    def generate_key(
        cls,
        user: Any,
        name: str,
        roles: list[Any] | None = None,
        permissions: list[Any] | None = None,
        allowed_ips: list[str] | None = None,
        expires_at: Any | None = None,
        key_type: str = "live",
    ) -> tuple[Self, str]:
        """
        Create a new APIKey instance and return (instance, raw_key_string).
        The raw_key is only returned once and cannot be retrieved later.
        """
        prefix, secret, raw_key = cls.generate_raw_components(key_type=key_type)
        hashed_key = cls.hash_secret(secret)

        api_key = cls.objects.create(
            user=user,
            name=name,
            prefix=prefix,
            hashed_key=hashed_key,
            allowed_ips=allowed_ips or [],
            expires_at=expires_at,
            is_active=True,
        )

        if roles:
            api_key.roles.set(roles)
        if permissions:
            api_key.permissions.set(permissions)

        return api_key, raw_key

    def verify_key(self, raw_key: str) -> bool:
        """
        Verify if the given raw key matches this APIKey instance.
        Expected format: djc_{type}_{prefix}_{secret}
        """
        parts = raw_key.split("_")
        if len(parts) < 4 or parts[0] != "djc":
            return False

        prefix = parts[2]
        secret = "_".join(parts[3:])

        if prefix != self.prefix:
            return False

        computed_hash = self.hash_secret(secret)
        return hmac.compare_digest(computed_hash, self.hashed_key)

    def rotate(self, key_type: str = "live") -> str:
        """
        Rotate the secret portion of the key, updating hashed_key and returning new raw_key.
        """
        prefix, secret, raw_key = self.generate_raw_components(key_type=key_type)
        self.prefix = prefix
        self.hashed_key = self.hash_secret(secret)
        self.save(update_fields=["prefix", "hashed_key", "updated_at"])
        return raw_key

    def check_ip(self, client_ip: str | None) -> bool:
        """
        Check if the incoming client IP is permitted according to allowed_ips.
        """
        if not self.allowed_ips:
            return True
        if not client_ip:
            return False

        try:
            client_addr = ipaddress.ip_address(client_ip)
        except ValueError:
            return False

        for pattern in self.allowed_ips:
            try:
                # Check for CIDR or exact IP match
                if "/" in pattern:
                    if client_addr in ipaddress.ip_network(pattern, strict=False):
                        return True
                elif client_addr == ipaddress.ip_address(pattern):
                    return True
            except ValueError:
                continue

        return False

    def record_usage(self, client_ip: str | None = None) -> None:
        """Update last_used_at and last_used_ip audit fields."""
        now = timezone.now()
        update_fields = ["last_used_at"]
        self.last_used_at = now

        if client_ip and self.last_used_ip != client_ip:
            self.last_used_ip = client_ip
            update_fields.append("last_used_ip")

        self.save(update_fields=update_fields)
