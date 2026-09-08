import fnmatch
import secrets
import uuid
from typing import Self

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.core.models import BaseModel


class WebhookStatus(models.TextChoices):
    PENDING = "PENDING", "Pending"
    SUCCESS = "SUCCESS", "Success"
    FAILED = "FAILED", "Failed"


class WebhookEndpoint(BaseModel):
    """
    Webhook target endpoint configured by an application user or tenant.
    Receives real-time HTTP POST notifications when subscribed events fire.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="webhook_endpoints",
        help_text="Owner user account for this webhook subscription.",
    )
    target_url = models.URLField(
        max_length=1024,
        help_text="Destination HTTPS or HTTP URL to receive webhook event payloads.",
    )
    description = models.CharField(
        max_length=255,
        blank=True,
        default="",
        help_text="Friendly label or description for this webhook endpoint.",
    )
    secret = models.CharField(
        max_length=128,
        help_text="Shared secret key used to compute HMAC-SHA256 payload signatures (prefixed with djc_whsec_).",
    )
    events = models.JSONField(
        default=list,
        blank=True,
        help_text="List of subscribed event topics, e.g. ['user.registered', 'api_key.created'] or ['*'] for all events.",
    )
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        help_text="Whether this endpoint is actively receiving webhook events.",
    )
    custom_headers = models.JSONField(
        default=dict,
        blank=True,
        help_text="Optional custom key-value headers to include with outbound requests.",
    )
    timeout_seconds = models.PositiveIntegerField(
        default=10,
        help_text="HTTP request timeout in seconds (default: 10).",
    )
    max_retries = models.PositiveIntegerField(
        default=3,
        help_text="Maximum retry attempts allowed on delivery failure (default: 3).",
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Webhook Endpoint"
        verbose_name_plural = "Webhook Endpoints"

    def __str__(self) -> str:
        return f"{self.target_url} ({'active' if self.is_active else 'inactive'})"

    @staticmethod
    def generate_secret() -> str:
        """Generate a cryptographically secure webhook signing secret."""
        return f"djc_whsec_{secrets.token_hex(24)}"

    def save(self, *args, **kwargs):
        if not self.secret:
            self.secret = self.generate_secret()
        super().save(*args, **kwargs)

    def rotate_secret(self) -> str:
        """Rotate the webhook secret key and save immediately."""
        new_secret = self.generate_secret()
        self.secret = new_secret
        self.save(update_fields=["secret", "updated_at"])
        return new_secret

    @property
    def masked_secret(self) -> str:
        """Return a masked representation of the webhook secret for safe display."""
        if not self.secret:
            return ""
        if len(self.secret) <= 14:
            return "djc_whsec_••••••••"
        return f"djc_whsec_••••••••{self.secret[-4:]}"

    def matches_event(self, event_type: str) -> bool:
        """
        Check if this endpoint subscribes to the given event type.
        Supports exact match ('user.created'), wildcard ('*'), or prefix patterns ('user.*').
        """
        if not self.events:
            return False

        for pattern in self.events:
            if pattern == "*" or pattern == event_type:
                return True
            if fnmatch.fnmatch(event_type, pattern):
                return True
        return False


class WebhookDelivery(BaseModel):
    """
    Audit log and delivery record for each outbound webhook dispatch attempt.
    Stores payload, headers, response status code, latency, and error diagnostics.
    """

    endpoint = models.ForeignKey(
        WebhookEndpoint,
        on_delete=models.CASCADE,
        related_name="deliveries",
        help_text="The target endpoint receiving this webhook delivery.",
    )
    event_type = models.CharField(
        max_length=100,
        db_index=True,
        help_text="Event topic name, e.g. 'user.registered' or 'system.test_ping'.",
    )
    event_id = models.UUIDField(
        default=uuid.uuid4,
        db_index=True,
        help_text="Unique event UUID used for deduplication and client idempotency.",
    )
    payload = models.JSONField(
        default=dict,
        help_text="Exact JSON payload dispatched in the HTTP request body.",
    )
    status = models.CharField(
        max_length=20,
        choices=WebhookStatus.choices,
        default=WebhookStatus.PENDING,
        db_index=True,
        help_text="Current delivery status (PENDING, SUCCESS, FAILED).",
    )
    response_status_code = models.IntegerField(
        null=True,
        blank=True,
        help_text="HTTP status code returned by the destination endpoint.",
    )
    response_headers = models.JSONField(
        default=dict,
        blank=True,
        help_text="HTTP response headers returned by the destination endpoint.",
    )
    response_body = models.TextField(
        default="",
        blank=True,
        help_text="Response body or error details returned by destination endpoint.",
    )
    duration_ms = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Request round-trip latency in milliseconds.",
    )
    attempt = models.PositiveIntegerField(
        default=1,
        help_text="Current delivery attempt count.",
    )
    error_message = models.TextField(
        default="",
        blank=True,
        help_text="Diagnostic failure message (e.g. connection timeout, DNS error).",
    )
    sent_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when HTTP dispatch was executed.",
    )
    next_retry_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Scheduled timestamp for next retry attempt on failure.",
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Webhook Delivery"
        verbose_name_plural = "Webhook Deliveries"
        indexes = [
            models.Index(fields=["endpoint", "-created_at"]),
            models.Index(fields=["status", "next_retry_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.event_type} -> {self.endpoint.target_url} [{self.status}]"

    def mark_success(
        self,
        status_code: int,
        headers: dict,
        body: str,
        duration_ms: int,
    ) -> Self:
        """Record successful delivery response."""
        self.status = WebhookStatus.SUCCESS
        self.response_status_code = status_code
        self.response_headers = headers
        self.response_body = body[:5000]  # Cap storage to prevent database bloat
        self.duration_ms = duration_ms
        self.error_message = ""
        self.sent_at = timezone.now()
        self.next_retry_at = None
        self.save()
        return self

    def mark_failure(
        self,
        error_message: str,
        status_code: int | None = None,
        headers: dict | None = None,
        body: str = "",
        duration_ms: int | None = None,
        retry_delay_seconds: int | None = None,
    ) -> Self:
        """Record failed delivery response and calculate next retry schedule."""
        self.status = WebhookStatus.FAILED
        self.error_message = error_message
        self.response_status_code = status_code
        if headers is not None:
            self.response_headers = headers
        self.response_body = body[:5000]
        self.duration_ms = duration_ms
        self.sent_at = timezone.now()

        if retry_delay_seconds and self.attempt < self.endpoint.max_retries:
            self.next_retry_at = timezone.now() + timezone.timedelta(
                seconds=retry_delay_seconds
            )
        else:
            self.next_retry_at = None

        self.save()
        return self
