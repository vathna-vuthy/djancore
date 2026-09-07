from rest_framework import serializers

from apps.notifications.models import (
    ChannelChoices,
    NotificationLog,
    NotificationTemplate,
)


class NotificationTemplateSerializer(serializers.ModelSerializer):
    """Serializer for NotificationTemplate CRUD."""

    class Meta:
        model = NotificationTemplate
        fields = [
            "id",
            "code",
            "name",
            "channel",
            "subject_template",
            "body_template",
            "is_active",
            "is_deleted",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "is_deleted", "created_at", "updated_at"]


class NotificationLogSerializer(serializers.ModelSerializer):
    """Serializer for notification audit and delivery logs."""

    template_code = serializers.CharField(
        source="template.code", read_only=True, allow_null=True
    )

    class Meta:
        model = NotificationLog
        fields = [
            "id",
            "recipient",
            "channel",
            "template",
            "template_code",
            "subject",
            "body",
            "payload",
            "status",
            "error_message",
            "scheduled_for",
            "sent_at",
            "user",
            "is_deleted",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "template_code",
            "status",
            "error_message",
            "sent_at",
            "is_deleted",
            "created_at",
            "updated_at",
        ]


class SendNotificationSerializer(serializers.Serializer):
    """Serializer for sending or scheduling direct notifications."""

    recipient = serializers.CharField(
        required=True,
        help_text="Target recipient address (email, phone, telegram chat_id).",
    )
    channel = serializers.ChoiceField(
        choices=ChannelChoices.choices,
        default=ChannelChoices.EMAIL,
        help_text="Communication channel to use.",
    )
    subject = serializers.CharField(
        required=False,
        default="",
        allow_blank=True,
        help_text="Notification subject or title.",
    )
    body = serializers.CharField(
        required=True,
        help_text="Notification body message.",
    )
    context = serializers.DictField(
        required=False,
        default=dict,
        help_text="Optional key-value context dictionary.",
    )
    scheduled_for = serializers.DateTimeField(
        required=False,
        allow_null=True,
        default=None,
        help_text="Optional future ISO datetime to schedule delivery.",
    )


class SendTemplateNotificationSerializer(serializers.Serializer):
    """Serializer for sending or scheduling template-based notifications."""

    recipient = serializers.CharField(
        required=True,
        help_text="Target recipient address.",
    )
    template_code = serializers.CharField(
        required=True,
        help_text="Unique code of the active NotificationTemplate.",
    )
    context = serializers.DictField(
        required=False,
        default=dict,
        help_text="Context variables to interpolate into the template.",
    )
    scheduled_for = serializers.DateTimeField(
        required=False,
        allow_null=True,
        default=None,
        help_text="Optional future ISO datetime to schedule delivery.",
    )


class RescheduleNotificationSerializer(serializers.Serializer):
    """Serializer for rescheduling a pending scheduled notification."""

    scheduled_for = serializers.DateTimeField(
        required=True,
        help_text="New future ISO datetime for scheduled delivery.",
    )


class ProviderInfoSerializer(serializers.Serializer):
    """Serializer describing available channel providers."""

    channel = serializers.CharField()
    configured = serializers.BooleanField()
    class_name = serializers.CharField()
