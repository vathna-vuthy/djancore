from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.views import APIView

from apps.core.responses import ApiResponse
from apps.throttling.engine import SlidingWindowRateLimiter
from apps.throttling.models import IPBlocklist, ThrottlingRule
from apps.throttling.serializers import (
    BlockIPRequestSerializer,
    IPBlocklistSerializer,
    ThrottlingRuleSerializer,
    ThrottlingUsageSerializer,
)
from apps.throttling.services import ThrottlingService


@extend_schema_view(
    list=extend_schema(
        tags=["Throttling & Abuse Prevention"],
        summary="List throttling rules",
        description="List all configured dynamic rate limiting rules.",
    ),
    create=extend_schema(
        tags=["Throttling & Abuse Prevention"],
        summary="Create throttling rule",
        description="Define a new rate limit rule with scope, limits, and optional path/method filters.",
    ),
    retrieve=extend_schema(
        tags=["Throttling & Abuse Prevention"],
        summary="Get throttling rule",
        description="Inspect details of a specific rate limiting rule.",
    ),
    update=extend_schema(
        tags=["Throttling & Abuse Prevention"],
        summary="Update throttling rule",
        description="Update rate limit parameters.",
    ),
    partial_update=extend_schema(
        tags=["Throttling & Abuse Prevention"],
        summary="Partially update throttling rule",
    ),
    destroy=extend_schema(
        tags=["Throttling & Abuse Prevention"],
        summary="Delete throttling rule",
        description="Soft-delete a rate limiting rule and purge cached rules.",
    ),
)
class ThrottlingRuleViewSet(viewsets.ModelViewSet):
    """
    Admin ViewSet for managing dynamic rate limiting rules.
    """

    queryset = ThrottlingRule.objects.all().order_by("name")
    serializer_class = ThrottlingRuleSerializer
    permission_classes = [permissions.IsAdminUser]
    search_fields = ["name", "path_pattern", "description"]
    filterset_fields = ["scope_type", "is_active"]
    ordering_fields = ["name", "rate_limit", "period_seconds", "created_at"]

    def perform_create(self, serializer):
        serializer.save()
        ThrottlingService.invalidate_rule_cache()

    def perform_update(self, serializer):
        serializer.save()
        ThrottlingService.invalidate_rule_cache()

    def perform_destroy(self, instance):
        super().perform_destroy(instance)
        ThrottlingService.invalidate_rule_cache()

    @extend_schema(
        tags=["Throttling & Abuse Prevention"],
        summary="Restore throttling rule",
        description="Restore a soft-deleted rate limiting rule.",
        request=None,
    )
    @action(detail=True, methods=["post"])
    def restore(self, request, pk=None):
        rule = ThrottlingRule.all_objects.get(pk=pk)
        rule.restore()
        ThrottlingService.invalidate_rule_cache()
        return ApiResponse.success(
            data=ThrottlingRuleSerializer(rule).data,
            message=f"Throttling rule '{rule.name}' restored successfully.",
        )


@extend_schema_view(
    list=extend_schema(
        tags=["Throttling & Abuse Prevention"],
        summary="List IP blocklist",
        description="List all blacklisted IP addresses.",
    ),
    create=extend_schema(
        tags=["Throttling & Abuse Prevention"],
        summary="Block IP address",
        description="Manually add an IP address to the blocklist.",
    ),
    retrieve=extend_schema(
        tags=["Throttling & Abuse Prevention"],
        summary="Get IP blocklist entry",
    ),
    update=extend_schema(
        tags=["Throttling & Abuse Prevention"],
        summary="Update IP blocklist entry",
    ),
    partial_update=extend_schema(
        tags=["Throttling & Abuse Prevention"],
        summary="Partially update IP blocklist entry",
    ),
    destroy=extend_schema(
        tags=["Throttling & Abuse Prevention"],
        summary="Delete IP blocklist entry",
    ),
)
class IPBlocklistViewSet(viewsets.ModelViewSet):
    """
    Admin ViewSet for managing IP blocklist / blacklist entries.
    """

    queryset = IPBlocklist.objects.all().order_by("-created_at")
    serializer_class = IPBlocklistSerializer
    permission_classes = [permissions.IsAdminUser]
    search_fields = ["ip_address", "reason"]
    filterset_fields = ["is_active"]
    ordering_fields = ["created_at", "expires_at"]

    def perform_create(self, serializer):
        instance = serializer.save()
        ThrottlingService.block_ip(
            ip_address=instance.ip_address,
            reason=instance.reason,
        )

    def perform_destroy(self, instance):
        ThrottlingService.unblock_ip(instance.ip_address)
        super().perform_destroy(instance)

    @extend_schema(
        tags=["Throttling & Abuse Prevention"],
        summary="Quick block IP",
        description="Quick action to block an IP with optional expiration seconds.",
        request=BlockIPRequestSerializer,
    )
    @action(detail=False, methods=["post"], url_path="block")
    def block(self, request):
        serializer = BlockIPRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        ip = serializer.validated_data["ip_address"]
        reason = serializer.validated_data["reason"]
        duration = serializer.validated_data.get("duration_seconds")

        entry = ThrottlingService.block_ip(
            ip_address=ip,
            reason=reason,
            duration_seconds=duration,
        )
        return ApiResponse.success(
            data=IPBlocklistSerializer(entry).data,
            message=f"IP address {ip} has been blocked successfully.",
            status=status.HTTP_201_CREATED,
        )

    @extend_schema(
        tags=["Throttling & Abuse Prevention"],
        summary="Unblock IP",
        description="Unblock an IP address.",
        request=None,
    )
    @action(detail=True, methods=["post"])
    def unblock(self, request, pk=None):
        entry = self.get_object()
        ThrottlingService.unblock_ip(entry.ip_address)
        return ApiResponse.success(
            message=f"IP address {entry.ip_address} has been unblocked.",
        )


class ThrottlingUsageView(APIView):
    """
    Endpoint for clients to inspect their current rate limit quota usage and remaining allowance.
    """

    permission_classes = [permissions.AllowAny]

    @extend_schema(
        tags=["Throttling & Abuse Prevention"],
        summary="Inspect quota usage",
        description="Check current rate limit consumption and remaining allowance for the caller.",
        responses={200: ThrottlingUsageSerializer},
    )
    def get(self, request):
        client_ip = ThrottlingService.get_client_ip(request)
        user = getattr(request, "user", None)
        user_id = str(user.id) if user and user.is_authenticated else None
        tenant = getattr(request, "tenant", None)
        org_id = str(tenant.id) if tenant else None

        active_rules = ThrottlingService.get_active_rules()
        limits_data = []

        for rule in active_rules:
            ident = ThrottlingService.resolve_identifier(request, rule.scope_type)
            if ident is None:
                continue

            cache_key = SlidingWindowRateLimiter.make_cache_key(
                rule_id=str(rule.id),
                scope_type=rule.scope_type,
                identifier=ident,
            )

            current_count, remaining, reset = SlidingWindowRateLimiter.get_usage(
                key=cache_key,
                limit=rule.rate_limit,
                period_seconds=rule.period_seconds,
            )

            limits_data.append(
                {
                    "rule_name": rule.name,
                    "scope_type": rule.scope_type,
                    "limit": rule.rate_limit,
                    "period_seconds": rule.period_seconds,
                    "burst_limit": rule.burst_limit,
                    "used": current_count,
                    "remaining": remaining,
                    "reset_seconds": reset,
                }
            )

        data = {
            "client_ip": client_ip,
            "user_id": user_id,
            "organization_id": org_id,
            "active_rules_count": len(limits_data),
            "limits": limits_data,
        }
        return ApiResponse.success(data=data)
