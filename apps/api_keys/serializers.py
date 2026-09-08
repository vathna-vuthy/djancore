from typing import Any

from rest_framework import serializers

from apps.api_keys.models import APIKey
from apps.iam.models import Permission, Role
from apps.iam.serializers import PermissionSerializer, RoleSerializer


class APIKeySerializer(serializers.ModelSerializer):
    """Serializer for inspecting and updating API key metadata."""

    roles_detail = RoleSerializer(source="roles", many=True, read_only=True)
    permissions_detail = PermissionSerializer(
        source="permissions", many=True, read_only=True
    )
    is_expired = serializers.BooleanField(read_only=True)
    is_valid = serializers.BooleanField(read_only=True)

    class Meta:
        model = APIKey
        fields = [
            "id",
            "name",
            "prefix",
            "user",
            "roles",
            "roles_detail",
            "permissions",
            "permissions_detail",
            "allowed_ips",
            "rate_limit",
            "expires_at",
            "is_expired",
            "is_valid",
            "last_used_at",
            "last_used_ip",
            "is_active",
            "is_deleted",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "prefix",
            "user",
            "is_expired",
            "is_valid",
            "last_used_at",
            "last_used_ip",
            "is_deleted",
            "created_at",
            "updated_at",
        ]


class CreateAPIKeySerializer(serializers.Serializer):
    """Input serializer for generating a new Developer API Key."""

    name = serializers.CharField(
        max_length=150,
        required=True,
        help_text="Descriptive label for this API key.",
    )
    roles = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=Role.objects.filter(is_deleted=False),
        required=False,
        default=list,
        help_text="Optional list of Role UUIDs to scope this key.",
    )
    permissions = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=Permission.objects.filter(is_deleted=False),
        required=False,
        default=list,
        help_text="Optional list of Permission UUIDs to scope this key.",
    )
    allowed_ips = serializers.ListField(
        child=serializers.CharField(max_length=50),
        required=False,
        default=list,
        help_text="Allowed IP addresses or CIDR blocks (empty permits all).",
    )
    rate_limit = serializers.IntegerField(
        required=False,
        allow_null=True,
        min_value=1,
        help_text="Optional rate limit in requests per minute.",
    )
    expires_at = serializers.DateTimeField(
        required=False,
        allow_null=True,
        help_text="Optional expiration timestamp.",
    )
    key_type = serializers.ChoiceField(
        choices=["live", "test"],
        default="live",
        required=False,
        help_text="Environment prefix type ('live' or 'test').",
    )

    def create(self, validated_data: dict[str, Any]) -> tuple[APIKey, str]:
        user = self.context["request"].user
        name = validated_data["name"]
        roles = validated_data.get("roles", [])
        permissions = validated_data.get("permissions", [])
        allowed_ips = validated_data.get("allowed_ips", [])
        expires_at = validated_data.get("expires_at")
        key_type = validated_data.get("key_type", "live")

        api_key, raw_key = APIKey.generate_key(
            user=user,
            name=name,
            roles=roles,
            permissions=permissions,
            allowed_ips=allowed_ips,
            expires_at=expires_at,
            key_type=key_type,
        )
        return api_key, raw_key


class APIKeyCreatedResponseSerializer(serializers.Serializer):
    """Response serializer returned upon key creation containing the one-time raw secret."""

    key = APIKeySerializer(help_text="API key metadata object.")
    raw_key = serializers.CharField(
        help_text="Complete plaintext API key secret. Displayed only once."
    )
    message = serializers.CharField(default="API key created successfully.")


class RotateAPIKeySerializer(serializers.Serializer):
    """Input serializer for rotating an API key."""

    key_type = serializers.ChoiceField(
        choices=["live", "test"],
        default="live",
        required=False,
        help_text="Environment prefix type ('live' or 'test').",
    )


class RotateAPIKeyResponseSerializer(serializers.Serializer):
    """Response serializer returned upon rotating an API key with the new raw secret."""

    key = APIKeySerializer(help_text="Updated API key metadata object.")
    raw_key = serializers.CharField(
        help_text="New complete plaintext API key secret. Displayed only once."
    )
    message = serializers.CharField(default="API key rotated successfully.")
