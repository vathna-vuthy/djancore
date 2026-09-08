from rest_framework import serializers

from apps.throttling.models import IPBlocklist, ThrottlingRule


class ThrottlingRuleSerializer(serializers.ModelSerializer):
    """Serializer for ThrottlingRule CRUD."""

    class Meta:
        model = ThrottlingRule
        fields = [
            "id",
            "name",
            "scope_type",
            "rate_limit",
            "period_seconds",
            "burst_limit",
            "path_pattern",
            "http_methods",
            "is_active",
            "description",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class IPBlocklistSerializer(serializers.ModelSerializer):
    """Serializer for IPBlocklist entries."""

    is_expired = serializers.BooleanField(read_only=True)

    class Meta:
        model = IPBlocklist
        fields = [
            "id",
            "ip_address",
            "reason",
            "expires_at",
            "is_active",
            "is_expired",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "is_expired", "created_at", "updated_at"]


class BlockIPRequestSerializer(serializers.Serializer):
    """Serializer for blocking an IP address."""

    ip_address = serializers.IPAddressField()
    reason = serializers.CharField(max_length=255)
    duration_seconds = serializers.IntegerField(
        required=False,
        allow_null=True,
        min_value=1,
        help_text="Block duration in seconds. Omit for permanent block.",
    )


class ThrottlingUsageSerializer(serializers.Serializer):
    """Serializer for current quota usage report."""

    client_ip = serializers.IPAddressField()
    user_id = serializers.CharField(allow_null=True)
    organization_id = serializers.CharField(allow_null=True)
    active_rules_count = serializers.IntegerField()
    limits = serializers.ListField(child=serializers.DictField())
