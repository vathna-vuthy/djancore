from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import permissions, viewsets

from apps.audit.models import AuditLog
from apps.audit.serializers import AuditLogSerializer
from apps.core.responses import ApiResponse


@extend_schema_view(
    list=extend_schema(
        tags=["Audit Trails"],
        summary="List audit logs",
        description="Retrieve a paginated list of immutable security and entity audit trails.",
    ),
    retrieve=extend_schema(
        tags=["Audit Trails"],
        summary="Get audit log details",
        description="Retrieve full event details, auto-generated message, before/after diffs, and client metadata.",
    ),
)
class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for inspecting immutable audit logs and compliance history.
    """

    queryset = AuditLog.objects.select_related("actor").all().order_by("-created_at")
    serializer_class = AuditLogSerializer
    permission_classes = [permissions.IsAuthenticated]
    search_fields = [
        "resource_type",
        "resource_id",
        "resource_repr",
        "message",
        "actor_repr",
        "request_id",
    ]
    filterset_fields = ["action", "resource_type", "actor"]
    ordering_fields = ["created_at", "action", "resource_type"]

    def get_queryset(self):
        user = self.request.user
        qs = AuditLog.objects.select_related("actor").all().order_by("-created_at")
        if not user.is_staff and not user.is_superuser:
            qs = qs.filter(actor=user)
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
