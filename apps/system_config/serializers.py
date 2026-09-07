from typing import Any

from rest_framework import serializers

from apps.system_config.models import ConfigDataType, SystemConfig
from apps.system_config.services import ConfigService


class SystemConfigSerializer(serializers.ModelSerializer):
    """Serializer for SystemConfig with secret masking and typed representation."""

    typed_value = serializers.SerializerMethodField()
    display_value = serializers.SerializerMethodField()

    class Meta:
        model = SystemConfig
        fields = [
            "id",
            "key",
            "raw_value",
            "typed_value",
            "display_value",
            "data_type",
            "group",
            "description",
            "is_secret",
            "is_public",
            "is_deleted",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "typed_value",
            "display_value",
            "is_deleted",
            "created_at",
            "updated_at",
        ]

    def get_typed_value(self, obj: SystemConfig) -> Any:
        request = self.context.get("request")
        if obj.is_secret and (not request or not request.user.is_superuser):
            return "******"
        return obj.typed_value

    def get_display_value(self, obj: SystemConfig) -> str:
        request = self.context.get("request")
        if obj.is_secret and (not request or not request.user.is_superuser):
            return obj.masked_value
        return obj.raw_value

    def validate(self, attrs):
        data_type = attrs.get(
            "data_type", getattr(self.instance, "data_type", ConfigDataType.STRING)
        )
        raw_val = attrs.get("raw_value")

        if raw_val is not None:
            # Validate casting
            if data_type == ConfigDataType.INTEGER:
                try:
                    int(raw_val)
                except ValueError:
                    raise serializers.ValidationError(
                        {"raw_value": "Value must be a valid integer."}
                    ) from None
            elif data_type == ConfigDataType.FLOAT:
                try:
                    float(raw_val)
                except ValueError:
                    raise serializers.ValidationError(
                        {"raw_value": "Value must be a valid float number."}
                    ) from None
            elif data_type == ConfigDataType.JSON:
                import json

                try:
                    json.loads(raw_val)
                except json.JSONDecodeError:
                    raise serializers.ValidationError(
                        {"raw_value": "Value must be valid JSON format."}
                    ) from None

        return attrs


class BulkConfigItemSerializer(serializers.Serializer):
    """Single item in a bulk configuration update."""

    key = serializers.CharField(required=True)
    value = serializers.CharField(required=True, allow_blank=True)


class BulkUpdateConfigSerializer(serializers.Serializer):
    """Serializer for updating multiple configs at once."""

    configs = serializers.ListField(
        child=BulkConfigItemSerializer(),
        allow_empty=False,
    )

    def save(self, **kwargs) -> list[SystemConfig]:
        updated = []
        for item in self.validated_data["configs"]:
            key = item["key"]
            val = item["value"]
            try:
                cfg = SystemConfig.objects.get(key=key)
                cfg.raw_value = val
                cfg.save()
                updated.append(cfg)
            except SystemConfig.DoesNotExist:
                continue
        ConfigService.purge_cache()
        return updated
