from typing import Any

from django.db import models

from apps.audit.models import AuditAction
from apps.audit.services import AuditService


class AuditableModelMixin(models.Model):
    """
    Model mixin that automatically tracks and records audit logs with field diffs
    whenever a model instance is created, updated, or deleted.
    """

    class Meta:
        abstract = True

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._initial_state: dict[str, Any] = self._capture_audit_snapshot()

    def _capture_audit_snapshot(self) -> dict[str, Any]:
        """Capture field values for diff comparison."""
        if not self.pk:
            return {}
        return AuditService.serialize_model_instance(self)

    def save(self, *args: Any, **kwargs: Any) -> None:
        is_new = self.pk is None
        old_state = self._initial_state if not is_new else {}

        super().save(*args, **kwargs)

        new_state = AuditService.serialize_model_instance(self)
        resource_type = f"{self._meta.app_label}.{self.__class__.__name__}"
        resource_repr = str(self)[:255]

        if is_new:
            AuditService.record(
                action=AuditAction.CREATE,
                resource_type=resource_type,
                resource_id=str(self.pk),
                resource_repr=resource_repr,
                changes={"created": {"new": new_state}},
            )
        else:
            diff = AuditService.calculate_diff(old_state, new_state)
            if diff:
                AuditService.record(
                    action=AuditAction.UPDATE,
                    resource_type=resource_type,
                    resource_id=str(self.pk),
                    resource_repr=resource_repr,
                    changes=diff,
                )

        # Reset snapshot after save
        self._initial_state = new_state

    def delete(self, *args: Any, **kwargs: Any) -> tuple[int, dict[str, int]]:
        resource_type = f"{self._meta.app_label}.{self.__class__.__name__}"
        resource_id = str(self.pk)
        resource_repr = str(self)[:255]

        res = super().delete(*args, **kwargs)

        AuditService.record(
            action=AuditAction.DELETE,
            resource_type=resource_type,
            resource_id=resource_id,
            resource_repr=resource_repr,
            changes={"deleted": {"old": self._initial_state}},
        )
        return res
