import uuid
from typing import Self

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.db import models


class AuditAction(models.TextChoices):
    CREATE = "CREATE", "Create"
    UPDATE = "UPDATE", "Update"
    DELETE = "DELETE", "Delete"
    LOGIN = "LOGIN", "Login"
    LOGOUT = "LOGOUT", "Logout"
    PASSWORD_CHANGE = "PASSWORD_CHANGE", "Password Change"
    PERMISSION_CHANGE = "PERMISSION_CHANGE", "Permission Change"
    CONFIG_CHANGE = "CONFIG_CHANGE", "Config Change"
    CUSTOM = "CUSTOM", "Custom Action"


class ImmutableQuerySet(models.QuerySet):
    """QuerySet that prevents bulk deletion or updates on audit log records."""

    def delete(self):
        raise PermissionDenied("Audit logs are append-only and cannot be bulk deleted.")

    def update(self, **kwargs):
        raise PermissionDenied(
            "Audit logs are append-only and cannot be bulk modified."
        )


class ImmutableManager(models.Manager):
    def get_queryset(self) -> ImmutableQuerySet:
        return ImmutableQuerySet(self.model, using=self._db)


class AuditLog(models.Model):
    """
    Immutable, append-only security audit log recording actors, actions,
    model state diffs, IP addresses, and auto-generated human-readable messages.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_logs",
        help_text="User who initiated this action (null if anonymous or system).",
    )
    actor_repr = models.CharField(
        max_length=255,
        default="System",
        help_text="Human-readable representation of actor or service.",
    )
    action = models.CharField(
        max_length=50,
        choices=AuditAction.choices,
        default=AuditAction.CUSTOM,
        db_index=True,
        help_text="Type of action performed.",
    )
    resource_type = models.CharField(
        max_length=150,
        db_index=True,
        help_text="Resource model or component name (e.g. 'apps.iam.User').",
    )
    resource_id = models.CharField(
        max_length=150,
        blank=True,
        default="",
        db_index=True,
        help_text="Primary key or unique identifier of the targeted resource.",
    )
    resource_repr = models.CharField(
        max_length=255,
        blank=True,
        default="",
        help_text="Human-readable title or label of the targeted resource.",
    )
    message = models.TextField(
        blank=True,
        default="",
        help_text="Auto-generated or custom human-readable sentence summarizing the event.",
    )
    changes = models.JSONField(
        default=dict,
        blank=True,
        help_text="Captured diff of modified fields (old vs new values).",
    )
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional request context (e.g. HTTP method, path, query params).",
    )
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        help_text="Originating client IP address.",
    )
    user_agent = models.TextField(
        blank=True,
        default="",
        help_text="Client User-Agent header.",
    )
    request_id = models.CharField(
        max_length=64,
        blank=True,
        default="",
        db_index=True,
        help_text="HTTP request correlation ID for end-to-end tracing.",
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        help_text="Timestamp when the audit event occurred.",
    )

    objects = ImmutableManager()

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Audit Log"
        verbose_name_plural = "Audit Logs"
        indexes = [
            models.Index(fields=["resource_type", "resource_id"]),
            models.Index(fields=["actor", "-created_at"]),
            models.Index(fields=["action", "-created_at"]),
        ]

    def __str__(self) -> str:
        return (
            self.message
            or f"{self.actor_repr} -> {self.action} on {self.resource_type}"
        )

    def generate_human_readable_message(self) -> str:
        """Auto-generate a clear, human-readable sentence describing this audit event."""
        actor_name = self.actor_repr or "System"
        target_name = f"'{self.resource_repr}'" if self.resource_repr else ""
        resource_label = (
            self.resource_type.split(".")[-1] if self.resource_type else "resource"
        )

        action_verbs = {
            AuditAction.CREATE: "created",
            AuditAction.UPDATE: "updated",
            AuditAction.DELETE: "deleted",
            AuditAction.LOGIN: "logged in",
            AuditAction.LOGOUT: "logged out",
            AuditAction.PASSWORD_CHANGE: "changed password for",
            AuditAction.PERMISSION_CHANGE: "modified permissions for",
            AuditAction.CONFIG_CHANGE: "changed configuration",
            AuditAction.CUSTOM: f"performed {self.action.lower()} on",
        }
        verb = action_verbs.get(self.action, f"performed {self.action.lower()} on")

        if self.action in (AuditAction.LOGIN, AuditAction.LOGOUT):
            return f"Actor {actor_name} {verb}."

        target_desc = f"{resource_label} {target_name}".strip()
        msg = f"Actor {actor_name} {verb} {target_desc}."

        if (
            self.action == AuditAction.UPDATE
            and isinstance(self.changes, dict)
            and self.changes
        ):
            changed_keys = list(self.changes.keys())
            if changed_keys:
                msg += f" (Fields modified: {', '.join(changed_keys)})"

        return msg

    def save(self, *args, **kwargs) -> Self:  # type: ignore[override]
        """Enforce append-only immutability and auto-generate message if omitted."""
        if self.pk and not self._state.adding:
            raise PermissionDenied(
                "AuditLog records are append-only and cannot be modified."
            )

        if not self.message:
            self.message = self.generate_human_readable_message()

        super().save(*args, **kwargs)
        return self

    def delete(self, *args, **kwargs):
        """Enforce immutability: records cannot be deleted."""
        raise PermissionDenied("AuditLog records are immutable and cannot be deleted.")
