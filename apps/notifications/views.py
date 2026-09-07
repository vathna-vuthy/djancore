from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import generics, permissions, status, views, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.notifications.models import NotificationLog, NotificationTemplate
from apps.notifications.providers.registry import ProviderRegistry
from apps.notifications.serializers import (
    NotificationLogSerializer,
    NotificationTemplateSerializer,
    ProviderInfoSerializer,
    RescheduleNotificationSerializer,
    SendNotificationSerializer,
    SendTemplateNotificationSerializer,
)
from apps.notifications.services import NotificationService


@extend_schema_view(
    list=extend_schema(
        tags=["Notifications"],
        summary="List notification templates",
        description="Retrieve a paginated list of notification templates.",
    ),
    create=extend_schema(
        tags=["Notifications"],
        summary="Create notification template",
        description="Create a new notification template with customizable subject and body templates.",
    ),
    retrieve=extend_schema(
        tags=["Notifications"],
        summary="Get notification template details",
        description="Retrieve details of a specific notification template by UUID.",
    ),
    update=extend_schema(
        tags=["Notifications"],
        summary="Update notification template",
        description="Update an existing notification template.",
    ),
    partial_update=extend_schema(
        tags=["Notifications"],
        summary="Partially update notification template",
        description="Partially update an existing notification template.",
    ),
    destroy=extend_schema(
        tags=["Notifications"],
        summary="Soft-delete notification template",
        description="Soft delete a notification template.",
    ),
)
class NotificationTemplateViewSet(viewsets.ModelViewSet):
    """ViewSet for managing notification templates (Admin only)."""

    queryset = NotificationTemplate.objects.all().order_by("code")
    serializer_class = NotificationTemplateSerializer
    permission_classes = [permissions.IsAdminUser]
    search_fields = ["code", "name", "subject_template", "body_template"]
    filterset_fields = ["channel", "is_active"]
    ordering_fields = ["code", "name", "created_at"]

    @extend_schema(
        tags=["Notifications"],
        summary="Restore soft-deleted notification template",
        description="Restore a previously soft-deleted notification template.",
        request=None,
    )
    @action(detail=True, methods=["post"])
    def restore(self, request, pk=None):
        """Restore a soft-deleted notification template."""
        template_obj = NotificationTemplate.all_objects.get(pk=pk)
        template_obj.restore()
        return Response(
            {"message": f"Template '{template_obj.code}' restored successfully."}
        )


@extend_schema_view(
    list=extend_schema(
        tags=["Notifications"],
        summary="List notification delivery logs",
        description="Retrieve a paginated list of notification delivery logs.",
    ),
    retrieve=extend_schema(
        tags=["Notifications"],
        summary="Get notification delivery log details",
        description="Retrieve details of a specific delivery log by UUID.",
    ),
)
class NotificationLogViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for inspecting and managing notification delivery logs."""

    queryset = NotificationLog.objects.all().order_by("-created_at")
    serializer_class = NotificationLogSerializer
    permission_classes = [permissions.IsAuthenticated]
    search_fields = ["recipient", "subject", "error_message"]
    filterset_fields = ["channel", "status", "template"]
    ordering_fields = ["created_at", "scheduled_for", "sent_at"]

    def get_queryset(self):
        user = self.request.user
        if user.is_staff or user.is_superuser:
            return NotificationLog.objects.all().order_by("-created_at")
        return NotificationLog.objects.filter(user=user).order_by("-created_at")

    @extend_schema(
        tags=["Notifications"],
        summary="Cancel scheduled notification",
        description="Cancel a notification that is currently scheduled for future delivery.",
        request=None,
    )
    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        """Cancel a pending scheduled notification."""
        try:
            log = NotificationService.cancel_scheduled(pk)
            return Response(
                {
                    "message": "Scheduled notification cancelled successfully.",
                    "data": NotificationLogSerializer(log).data,
                },
                status=status.HTTP_200_OK,
            )
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except NotificationLog.DoesNotExist:
            return Response(
                {"error": "Notification log not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

    @extend_schema(
        tags=["Notifications"],
        summary="Reschedule notification",
        description="Update the scheduled delivery time for a scheduled or cancelled notification.",
        request=RescheduleNotificationSerializer,
        responses={200: NotificationLogSerializer},
    )
    @action(detail=True, methods=["post"])
    def reschedule(self, request, pk=None):
        """Reschedule a notification for a new future delivery datetime."""
        serializer = RescheduleNotificationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        new_time = serializer.validated_data["scheduled_for"]

        try:
            log = NotificationService.reschedule(pk, new_time)
            return Response(
                {
                    "message": "Notification rescheduled successfully.",
                    "data": NotificationLogSerializer(log).data,
                },
                status=status.HTTP_200_OK,
            )
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except NotificationLog.DoesNotExist:
            return Response(
                {"error": "Notification log not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

    @extend_schema(
        tags=["Notifications"],
        summary="Retry sending notification",
        description="Immediately re-attempt dispatching a failed or cancelled notification.",
        request=None,
        responses={200: NotificationLogSerializer},
    )
    @action(detail=True, methods=["post"])
    def retry(self, request, pk=None):
        """Retry sending a notification immediately."""
        try:
            log = NotificationService.retry_failed(pk)
            return Response(
                {
                    "message": "Notification retry dispatched.",
                    "data": NotificationLogSerializer(log).data,
                },
                status=status.HTTP_200_OK,
            )
        except NotificationLog.DoesNotExist:
            return Response(
                {"error": "Notification log not found."},
                status=status.HTTP_404_NOT_FOUND,
            )


@extend_schema(
    tags=["Notifications"],
    summary="Send direct notification",
    description="Send or schedule a direct ad-hoc notification via a selected communication channel.",
    request=SendNotificationSerializer,
    responses={201: NotificationLogSerializer},
)
class SendNotificationView(generics.GenericAPIView):
    """Endpoint to send or schedule an ad-hoc notification."""

    serializer_class = SendNotificationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        log = NotificationService.send(
            recipient=data["recipient"],
            channel=data["channel"],
            subject=data.get("subject", ""),
            body=data["body"],
            context=data.get("context", {}),
            scheduled_for=data.get("scheduled_for"),
            user=request.user,
        )

        return Response(
            NotificationLogSerializer(log).data,
            status=status.HTTP_201_CREATED,
        )


@extend_schema(
    tags=["Notifications"],
    summary="Send template notification",
    description="Send or schedule a notification rendered from a registered template.",
    request=SendTemplateNotificationSerializer,
    responses={201: NotificationLogSerializer},
)
class SendTemplateNotificationView(generics.GenericAPIView):
    """Endpoint to send or schedule a template-rendered notification."""

    serializer_class = SendTemplateNotificationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            log = NotificationService.send_template(
                recipient=data["recipient"],
                template_code=data["template_code"],
                context=data.get("context", {}),
                scheduled_for=data.get("scheduled_for"),
                user=request.user,
            )
            return Response(
                NotificationLogSerializer(log).data,
                status=status.HTTP_201_CREATED,
            )
        except ValueError as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )


@extend_schema(
    tags=["Notifications"],
    summary="List available providers",
    description="Retrieve all registered notification channel providers and their configuration status.",
    responses={200: ProviderInfoSerializer(many=True)},
)
class AvailableProvidersView(views.APIView):
    """Endpoint to inspect available notification providers and channels."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, *args, **kwargs):
        providers = [
            {
                "channel": channel,
                "configured": info["configured"],
                "class_name": info["class_name"],
            }
            for channel, info in ProviderRegistry.list_providers().items()
        ]
        serializer = ProviderInfoSerializer(providers, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
