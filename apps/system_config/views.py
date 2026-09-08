from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import generics, permissions, views, viewsets
from rest_framework.decorators import action

from apps.core.responses import ApiResponse
from apps.system_config.models import SystemConfig
from apps.system_config.serializers import (
    BulkUpdateConfigSerializer,
    SystemConfigSerializer,
)
from apps.system_config.services import ConfigService


@extend_schema_view(
    list=extend_schema(
        tags=["System Config"],
        summary="List system configurations",
        description="Retrieve a paginated list of all system configurations.",
    ),
    create=extend_schema(
        tags=["System Config"],
        summary="Create system configuration",
        description="Create a new dynamic configuration setting.",
    ),
    retrieve=extend_schema(
        tags=["System Config"],
        summary="Get system configuration details",
        description="Retrieve a specific configuration setting by UUID.",
    ),
    update=extend_schema(
        tags=["System Config"],
        summary="Update system configuration",
        description="Update an existing configuration setting.",
    ),
    partial_update=extend_schema(
        tags=["System Config"],
        summary="Partially update system configuration",
        description="Partially update an existing configuration setting.",
    ),
    destroy=extend_schema(
        tags=["System Config"],
        summary="Soft-delete system configuration",
        description="Soft delete a configuration setting.",
    ),
)
class SystemConfigViewSet(viewsets.ModelViewSet):
    """ViewSet for managing system configurations (Staff only)."""

    queryset = SystemConfig.objects.all().order_by("group", "key")
    serializer_class = SystemConfigSerializer
    permission_classes = [permissions.IsAdminUser]
    search_fields = ["key", "description", "group"]
    filterset_fields = ["group", "data_type", "is_secret", "is_public"]
    ordering_fields = ["key", "group", "created_at"]

    @extend_schema(
        tags=["System Config"],
        summary="Restore soft-deleted configuration",
        description="Restore a previously soft-deleted configuration.",
        request=None,
    )
    @action(detail=True, methods=["post"])
    def restore(self, request, pk=None):
        """Restore a soft-deleted configuration setting."""
        config_obj = SystemConfig.all_objects.get(pk=pk)
        config_obj.restore()
        return ApiResponse.success(
            message=f"Config '{config_obj.key}' restored successfully."
        )

    @extend_schema(
        tags=["System Config"],
        summary="Purge configuration cache",
        description="Purge all cached configuration values from the cache engine.",
        request=None,
    )
    @action(detail=False, methods=["post"], url_path="purge-cache")
    def purge_cache(self, request):
        """Manually purge all cached configuration settings."""
        ConfigService.purge_cache()
        return ApiResponse.success(message="System config cache purged successfully.")


@extend_schema(
    tags=["System Config"],
    summary="Get public system configurations",
    description="Retrieve all public system settings as a key-value dictionary (open to unauthenticated clients).",
    responses={200: dict},
)
class PublicConfigView(views.APIView):
    """Public endpoint returning all public system configurations."""

    permission_classes = [permissions.AllowAny]

    def get(self, request, *args, **kwargs):
        configs = ConfigService.get_public_configs()
        return ApiResponse.success(data=configs)


@extend_schema(
    tags=["System Config"],
    summary="Bulk update system configurations",
    description="Update multiple configuration keys and values in a single atomic request.",
    request=BulkUpdateConfigSerializer,
)
class BulkUpdateConfigView(generics.GenericAPIView):
    """Endpoint for updating multiple configurations at once (Staff only)."""

    serializer_class = BulkUpdateConfigSerializer
    permission_classes = [permissions.IsAdminUser]

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        updated = serializer.save()
        return ApiResponse.success(
            data={"updated_keys": [c.key for c in updated]},
            message=f"Successfully updated {len(updated)} configurations.",
        )
