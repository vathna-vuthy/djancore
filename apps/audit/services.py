import copy
import logging
from typing import Any

from django.db import models

from apps.audit.context import (
    get_current_actor,
    get_current_actor_repr,
    get_current_ip,
    get_current_request_id,
    get_current_user_agent,
)
from apps.audit.models import AuditAction, AuditLog

logger = logging.getLogger(__name__)

SENSITIVE_FIELD_NAMES = {
    "password",
    "secret",
    "hashed_key",
    "token",
    "key",
    "raw_key",
    "auth_token",
    "access_token",
    "refresh_token",
    "api_key",
}


class AuditService:
    """
    Central orchestration service for recording security and entity audit logs.
    """

    @classmethod
    def record(
        cls,
        action: str | AuditAction,
        resource_type: str,
        resource_id: str = "",
        resource_repr: str = "",
        changes: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
        actor: Any | None = None,
        actor_repr: str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        request_id: str | None = None,
        message: str = "",
    ) -> AuditLog:
        """
        Record a new immutable audit log. Automatically pulls missing metadata
        from active request contextvars if not explicitly supplied.
        """
        resolved_actor = actor if actor is not None else get_current_actor()
        resolved_actor_repr = (
            actor_repr if actor_repr is not None else get_current_actor_repr()
        )
        resolved_ip = ip_address if ip_address is not None else get_current_ip()
        resolved_user_agent = (
            user_agent if user_agent is not None else get_current_user_agent()
        )
        resolved_request_id = (
            request_id if request_id is not None else (get_current_request_id() or "")
        )

        log = AuditLog.objects.create(
            actor=resolved_actor,
            actor_repr=resolved_actor_repr,
            action=str(action),
            resource_type=resource_type,
            resource_id=str(resource_id),
            resource_repr=resource_repr,
            changes=changes or {},
            metadata=metadata or {},
            ip_address=resolved_ip,
            user_agent=resolved_user_agent,
            request_id=resolved_request_id,
            message=message,
        )
        return log

    @classmethod
    def calculate_diff(
        cls,
        old_data: dict[str, Any],
        new_data: dict[str, Any],
        ignored_fields: set[str] | None = None,
    ) -> dict[str, dict[str, Any]]:
        """
        Calculate before/after field changes between two dictionary snapshots,
        automatically masking sensitive values like passwords or secret keys.
        """
        ignored = (
            set(ignored_fields)
            if ignored_fields
            else {"updated_at", "last_used_at", "created_at"}
        )
        diff: dict[str, dict[str, Any]] = {}
        all_keys = set(old_data.keys()).union(set(new_data.keys()))

        for key in all_keys:
            if key in ignored:
                continue

            old_val = old_data.get(key)
            new_val = new_data.get(key)

            if old_val != new_val:
                # Mask sensitive fields
                is_sensitive = any(
                    sensitive in key.lower() for sensitive in SENSITIVE_FIELD_NAMES
                )
                if is_sensitive:
                    diff[key] = {
                        "old": "******" if old_val is not None else None,
                        "new": "******" if new_val is not None else None,
                    }
                else:
                    diff[key] = {
                        "old": old_val,
                        "new": new_val,
                    }

        return diff

    @classmethod
    def serialize_model_instance(cls, instance: models.Model) -> dict[str, Any]:
        """Convert a model instance into a JSON-serializable dictionary snapshot."""
        snapshot: dict[str, Any] = {}
        for field in instance._meta.concrete_fields:
            name = field.name
            try:
                val = getattr(instance, name)
                if isinstance(val, (int, float, str, bool, type(None))):
                    snapshot[name] = val
                elif isinstance(val, (list, dict)):
                    snapshot[name] = copy.deepcopy(val)
                else:
                    snapshot[name] = str(val)
            except Exception:
                pass
        return snapshot
