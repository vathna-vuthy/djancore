from rest_framework import serializers

from apps.audit.models import AuditLog


class AuditLogSerializer(serializers.ModelSerializer):
    """Read-only serializer for inspecting immutable audit trail records."""

    actor_email = serializers.EmailField(
        source="actor.email", read_only=True, default=None
    )

    class Meta:
        model = AuditLog
        fields = [
            "id",
            "actor",
            "actor_email",
            "actor_repr",
            "action",
            "resource_type",
            "resource_id",
            "resource_repr",
            "message",
            "changes",
            "metadata",
            "ip_address",
            "user_agent",
            "request_id",
            "created_at",
        ]
        read_only_fields = fields
