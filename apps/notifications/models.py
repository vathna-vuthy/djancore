from django.conf import settings
from django.db import models

from apps.core.models import BaseModel


class ChannelChoices(models.TextChoices):
    EMAIL = "email", "Email"
    TELEGRAM = "telegram", "Telegram"
    SMS = "sms", "SMS"
    SLACK = "slack", "Slack"
    WEBHOOK = "webhook", "Webhook"


class DeliveryStatus(models.TextChoices):
    PENDING = "PENDING", "Pending"
    SCHEDULED = "SCHEDULED", "Scheduled"
    SENT = "SENT", "Sent"
    FAILED = "FAILED", "Failed"
    CANCELLED = "CANCELLED", "Cancelled"


class NotificationTemplate(BaseModel):
    """Reusable message template for notifications."""

    code = models.CharField(
        max_length=100,
        unique=True,
        db_index=True,
        help_text="Unique template identifier (e.g. WELCOME_EMAIL, OTP_SMS).",
    )
    name = models.CharField(max_length=150)
    channel = models.CharField(
        max_length=20,
        choices=ChannelChoices.choices,
        default=ChannelChoices.EMAIL,
    )
    subject_template = models.CharField(
        max_length=255,
        blank=True,
        help_text="Subject template supporting {{ variable }} placeholders.",
    )
    body_template = models.TextField(
        help_text="Body content template supporting {{ variable }} placeholders.",
    )
    is_active = models.BooleanField(default=True)

    class Meta(BaseModel.Meta):
        db_table = "noti_templates"
        verbose_name = "notification template"
        verbose_name_plural = "notification templates"
        ordering = ["channel", "code"]

    def __str__(self) -> str:
        return f"[{self.channel.upper()}] {self.name} ({self.code})"


class NotificationLog(BaseModel):
    """Audit log and state tracker for sent and scheduled notifications."""

    recipient = models.CharField(
        max_length=255,
        db_index=True,
        help_text="Recipient destination (email address, telegram chat_id, phone).",
    )
    channel = models.CharField(
        max_length=20,
        choices=ChannelChoices.choices,
        db_index=True,
    )
    template = models.ForeignKey(
        NotificationTemplate,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="logs",
    )
    subject = models.CharField(max_length=255, blank=True)
    body = models.TextField()
    payload = models.JSONField(
        default=dict,
        blank=True,
        help_text="Context variables or metadata passed during dispatch.",
    )
    status = models.CharField(
        max_length=20,
        choices=DeliveryStatus.choices,
        default=DeliveryStatus.PENDING,
        db_index=True,
    )
    error_message = models.TextField(blank=True)
    scheduled_for = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        help_text="Target dispatch time if this is a scheduled notification.",
    )
    sent_at = models.DateTimeField(null=True, blank=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="notification_logs",
    )

    class Meta(BaseModel.Meta):
        db_table = "noti_logs"
        verbose_name = "notification log"
        verbose_name_plural = "notification logs"
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["status", "scheduled_for"],
                name="notif_status_sched_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"[{self.channel}] to {self.recipient} ({self.status})"
