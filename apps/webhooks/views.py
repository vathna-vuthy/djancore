from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action

from apps.core.responses import ApiResponse
from apps.webhooks.models import WebhookDelivery, WebhookEndpoint
from apps.webhooks.serializers import (
    WebhookDeliverySerializer,
    WebhookEndpointSerializer,
    WebhookPingResponseSerializer,
    WebhookRotateSecretSerializer,
)
from apps.webhooks.services import WebhookDispatcher


@extend_schema_view(
    list=extend_schema(
        tags=["Webhooks"],
        summary="List webhook endpoints",
        description="Retrieve all registered webhook endpoints for the authenticated user.",
    ),
    retrieve=extend_schema(
        tags=["Webhooks"],
        summary="Get webhook endpoint details",
        description="Retrieve configuration and masked secret for a specific webhook endpoint.",
    ),
    create=extend_schema(
        tags=["Webhooks"],
        summary="Create webhook endpoint",
        description="Register a new webhook target endpoint with event subscriptions. The raw signing secret is returned only once in this creation response.",
    ),
    partial_update=extend_schema(
        tags=["Webhooks"],
        summary="Update webhook endpoint",
        description="Update target URL, subscribed events, active status, timeout, or custom headers.",
    ),
    destroy=extend_schema(
        tags=["Webhooks"],
        summary="Delete (soft-delete) webhook endpoint",
        description="Soft-delete a webhook endpoint, immediately disabling event delivery.",
    ),
)
class WebhookEndpointViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing Webhook Endpoints.
    Allows subscribing to events, pinging endpoints, rotating signing secrets, and inspecting logs.
    """

    queryset = WebhookEndpoint.objects.all().order_by("-created_at")
    serializer_class = WebhookEndpointSerializer
    permission_classes = [permissions.IsAuthenticated]
    search_fields = ["target_url", "description"]
    filterset_fields = ["is_active"]
    ordering_fields = ["created_at", "target_url"]
    http_method_names = ["get", "post", "patch", "delete"]

    def get_queryset(self):
        user = self.request.user
        qs = WebhookEndpoint.objects.all().order_by("-created_at")
        if not user.is_staff and not user.is_superuser:
            qs = qs.filter(user=user)
        return qs

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()
        data = serializer.data
        data["secret"] = instance.secret
        return ApiResponse.created(
            data=data,
            message="Webhook endpoint created successfully. Save your signing secret securely.",
        )

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(queryset, many=True)
        return ApiResponse.success(data=serializer.data)

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return ApiResponse.success(data=serializer.data)

    def partial_update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return ApiResponse.success(
            data=serializer.data,
            message="Webhook endpoint updated successfully.",
        )

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.delete()
        return ApiResponse.success(
            message="Webhook endpoint deleted successfully.",
        )

    @extend_schema(
        tags=["Webhooks"],
        summary="Test ping webhook endpoint",
        description="Dispatches an immediate mock 'system.ping' event to test destination connectivity.",
        responses={200: WebhookPingResponseSerializer},
    )
    @action(detail=True, methods=["post"], url_path="ping")
    def ping(self, request, pk=None):
        endpoint = self.get_object()
        delivery = WebhookDispatcher.ping_endpoint(endpoint)
        serializer = WebhookDeliverySerializer(delivery)
        return ApiResponse.success(
            data={"delivery": serializer.data},
            message=f"Ping dispatched with status: {delivery.status}",
        )

    @extend_schema(
        tags=["Webhooks"],
        summary="Rotate webhook signing secret",
        description="Generates a new HMAC-SHA256 signing secret key, invalidating the previous secret.",
        responses={200: WebhookRotateSecretSerializer},
    )
    @action(detail=True, methods=["post"], url_path="rotate-secret")
    def rotate_secret(self, request, pk=None):
        endpoint = self.get_object()
        new_secret = endpoint.rotate_secret()
        return ApiResponse.success(
            data={"secret": new_secret},
            message="Signing secret rotated successfully. Remember to update your destination verification code.",
        )

    @extend_schema(
        tags=["Webhooks"],
        summary="Restore soft-deleted webhook endpoint",
        description="Restores a previously deleted webhook endpoint.",
    )
    @action(detail=True, methods=["post"], url_path="restore")
    def restore(self, request, pk=None):
        user = self.request.user
        qs = WebhookEndpoint.all_objects.all()
        if not user.is_staff and not user.is_superuser:
            qs = qs.filter(user=user)
        try:
            endpoint = qs.get(pk=pk)
        except WebhookEndpoint.DoesNotExist:
            return ApiResponse.not_found(
                message="Webhook endpoint not found.",
            )

        if not endpoint.is_deleted:
            return ApiResponse.error(
                message="Webhook endpoint is not deleted.",
                status=status.HTTP_400_BAD_REQUEST,
            )

        endpoint.restore()
        serializer = self.get_serializer(endpoint)
        return ApiResponse.success(
            data=serializer.data,
            message="Webhook endpoint restored successfully.",
        )


@extend_schema_view(
    list=extend_schema(
        tags=["Webhooks"],
        summary="List webhook deliveries",
        description="Retrieve delivery attempt logs across all endpoints for the user.",
    ),
    retrieve=extend_schema(
        tags=["Webhooks"],
        summary="Get webhook delivery details",
        description="Retrieve payload, HTTP status code, response headers, response body, and timing for a specific delivery.",
    ),
)
class WebhookDeliveryViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for inspecting outbound webhook delivery logs and triggering manual retries.
    """

    queryset = (
        WebhookDelivery.objects.select_related("endpoint").all().order_by("-created_at")
    )
    serializer_class = WebhookDeliverySerializer
    permission_classes = [permissions.IsAuthenticated]
    search_fields = ["event_type", "endpoint__target_url", "error_message"]
    filterset_fields = ["status", "event_type", "endpoint"]
    ordering_fields = ["created_at", "duration_ms", "sent_at"]

    def get_queryset(self):
        user = self.request.user
        qs = (
            WebhookDelivery.objects.select_related("endpoint")
            .all()
            .order_by("-created_at")
        )
        if not user.is_staff and not user.is_superuser:
            qs = qs.filter(endpoint__user=user)
        return qs

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(queryset, many=True)
        return ApiResponse.success(data=serializer.data)

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return ApiResponse.success(data=serializer.data)

    @extend_schema(
        tags=["Webhooks"],
        summary="Retry webhook delivery",
        description="Manually re-attempts an outbound HTTP delivery for a failed or pending webhook event.",
        responses={200: WebhookDeliverySerializer},
    )
    @action(detail=True, methods=["post"], url_path="retry")
    def retry(self, request, pk=None):
        delivery = self.get_object()
        updated_delivery = WebhookDispatcher.retry_delivery(delivery)
        serializer = self.get_serializer(updated_delivery)
        return ApiResponse.success(
            data=serializer.data,
            message=f"Webhook delivery re-attempted. Status: {updated_delivery.status}",
        )
