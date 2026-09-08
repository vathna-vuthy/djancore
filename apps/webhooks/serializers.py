from urllib.parse import urlparse

from rest_framework import serializers

from apps.webhooks.models import WebhookDelivery, WebhookEndpoint


class WebhookEndpointSerializer(serializers.ModelSerializer):
    """Serializer for viewing, creating, and updating Webhook Endpoints."""

    masked_secret = serializers.CharField(read_only=True)
    secret = serializers.CharField(
        read_only=True,
        help_text="The signing secret for this endpoint. Only populated on initial creation.",
    )

    class Meta:
        model = WebhookEndpoint
        fields = [
            "id",
            "target_url",
            "description",
            "secret",
            "masked_secret",
            "events",
            "is_active",
            "custom_headers",
            "timeout_seconds",
            "max_retries",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "secret", "masked_secret", "created_at", "updated_at"]

    def validate_target_url(self, value: str) -> str:
        parsed = urlparse(value)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            raise serializers.ValidationError(
                "A valid HTTP or HTTPS destination URL is required."
            )
        return value

    def validate_events(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError(
                "Events must be a list of event topic strings."
            )
        if not value:
            raise serializers.ValidationError(
                "At least one event topic or '*' wildcard must be specified."
            )
        for item in value:
            if not isinstance(item, str) or not item.strip():
                raise serializers.ValidationError(
                    "Event names must be non-empty strings."
                )
        return value

    def create(self, validated_data):
        user = self.context["request"].user
        validated_data["user"] = user
        return super().create(validated_data)

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        ret.pop("secret", None)
        return ret


class WebhookRotateSecretSerializer(serializers.Serializer):
    """Response serializer for rotating a webhook signing secret."""

    secret = serializers.CharField(
        help_text="The newly rotated webhook secret key (djc_whsec_...)."
    )
    message = serializers.CharField(
        default="Signing secret rotated successfully. Update your destination verification code."
    )


class WebhookDeliverySerializer(serializers.ModelSerializer):
    """Serializer for inspecting webhook delivery logs."""

    endpoint_id = serializers.UUIDField(source="endpoint.id", read_only=True)
    target_url = serializers.CharField(source="endpoint.target_url", read_only=True)

    class Meta:
        model = WebhookDelivery
        fields = [
            "id",
            "endpoint_id",
            "target_url",
            "event_type",
            "event_id",
            "payload",
            "status",
            "response_status_code",
            "response_headers",
            "response_body",
            "duration_ms",
            "attempt",
            "error_message",
            "sent_at",
            "next_retry_at",
            "created_at",
        ]
        read_only_fields = fields


class WebhookPingResponseSerializer(serializers.Serializer):
    """Response serializer for test ping deliveries."""

    delivery = WebhookDeliverySerializer()
    message = serializers.CharField()
