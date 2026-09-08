from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import permissions, viewsets
from rest_framework.decorators import action

from apps.api_keys.models import APIKey
from apps.api_keys.serializers import (
    APIKeyCreatedResponseSerializer,
    APIKeySerializer,
    CreateAPIKeySerializer,
    RotateAPIKeyResponseSerializer,
    RotateAPIKeySerializer,
)
from apps.core.responses import ApiResponse


@extend_schema_view(
    list=extend_schema(
        tags=["API Keys"],
        summary="List API keys",
        description="Retrieve a paginated list of API keys for the authenticated user.",
    ),
    retrieve=extend_schema(
        tags=["API Keys"],
        summary="Get API key details",
        description="Retrieve metadata for a specific API key.",
    ),
    create=extend_schema(
        tags=["API Keys"],
        summary="Create API key",
        description="Generate a new Developer API Key. The full raw secret is returned only once in this response.",
        request=CreateAPIKeySerializer,
        responses={201: APIKeyCreatedResponseSerializer},
    ),
    partial_update=extend_schema(
        tags=["API Keys"],
        summary="Update API key",
        description="Update metadata, expiration, active status, IP whitelist, or scoped permissions for an API key.",
    ),
    destroy=extend_schema(
        tags=["API Keys"],
        summary="Revoke (soft-delete) API key",
        description="Revoke an API key by soft-deleting it, immediately disabling its access.",
    ),
)
class APIKeyViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing Developer API Keys.
    Users can inspect, create, update, rotate, and revoke their API keys.
    """

    queryset = APIKey.objects.all().order_by("-created_at")
    serializer_class = APIKeySerializer
    permission_classes = [permissions.IsAuthenticated]
    search_fields = ["name", "prefix"]
    filterset_fields = ["is_active"]
    ordering_fields = ["created_at", "last_used_at", "name"]
    http_method_names = ["get", "post", "patch", "delete"]

    def get_queryset(self):
        user = self.request.user
        if user.is_staff or user.is_superuser:
            return APIKey.objects.all().order_by("-created_at")
        return APIKey.objects.filter(user=user).order_by("-created_at")

    def create(self, request, *args, **kwargs):
        serializer = CreateAPIKeySerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        api_key, raw_key = serializer.save()

        return ApiResponse.created(
            data={
                "key": APIKeySerializer(api_key, context={"request": request}).data,
                "raw_key": raw_key,
            },
            message="API key created successfully. Store the raw key securely as it cannot be retrieved again.",
        )

    @extend_schema(
        tags=["API Keys"],
        summary="Rotate API key",
        description="Rotate the secret key for this API key. Invalidates the previous secret and returns the new raw secret key.",
        request=RotateAPIKeySerializer,
        responses={200: RotateAPIKeyResponseSerializer},
    )
    @action(detail=True, methods=["post"])
    def rotate(self, request, pk=None):
        api_key = self.get_object()
        serializer = RotateAPIKeySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        key_type = serializer.validated_data.get("key_type", "live")

        new_raw_key = api_key.rotate(key_type=key_type)

        return ApiResponse.success(
            data={
                "key": APIKeySerializer(api_key, context={"request": request}).data,
                "raw_key": new_raw_key,
            },
            message="API key rotated successfully. Store the new raw key securely.",
        )

    @extend_schema(
        tags=["API Keys"],
        summary="Restore soft-deleted API key",
        description="Restore a previously revoked/soft-deleted API key.",
        request=None,
    )
    @action(detail=True, methods=["post"])
    def restore(self, request, pk=None):
        api_key = APIKey.all_objects.get(pk=pk)
        # Check permissions if not staff
        if (
            not request.user.is_staff
            and not request.user.is_superuser
            and api_key.user != request.user
        ):
            return ApiResponse.forbidden(
                message="You do not have permission to restore this key."
            )

        api_key.restore()
        return ApiResponse.success(
            message=f"API key '{api_key.name}' restored successfully."
        )
