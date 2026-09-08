from django.contrib import admin
from django.utils.html import format_html

from apps.audit.models import AuditAction, AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = [
        "created_at",
        "action_badge",
        "actor_repr",
        "resource_type_display",
        "resource_repr",
        "message",
        "ip_address",
    ]
    list_filter = ["action", "resource_type", "created_at"]
    search_fields = [
        "message",
        "actor_repr",
        "resource_type",
        "resource_repr",
        "resource_id",
        "ip_address",
        "request_id",
    ]
    readonly_fields = [
        "id",
        "actor",
        "actor_repr",
        "action",
        "resource_type",
        "resource_id",
        "resource_repr",
        "message",
        "changes",
        "metadata",
        "ip_address",
        "user_agent",
        "request_id",
        "created_at",
    ]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.display(description="Action")
    def action_badge(self, obj):
        color_map = {
            AuditAction.CREATE: "#28a745",
            AuditAction.UPDATE: "#007bff",
            AuditAction.DELETE: "#dc3545",
            AuditAction.LOGIN: "#17a2b8",
            AuditAction.LOGOUT: "#6c757d",
            AuditAction.PASSWORD_CHANGE: "#ffc107",
            AuditAction.PERMISSION_CHANGE: "#6f42c1",
            AuditAction.CONFIG_CHANGE: "#fd7e14",
            AuditAction.CUSTOM: "#20c997",
        }
        color = color_map.get(obj.action, "#6c757d")
        text_color = "#000" if obj.action == AuditAction.PASSWORD_CHANGE else "#fff"
        return format_html(
            '<span style="background-color: {}; color: {}; padding: 2px 8px; border-radius: 4px; font-weight: 600; font-size: 11px;">{}</span>',
            color,
            text_color,
            obj.action,
        )

    @admin.display(description="Resource")
    def resource_type_display(self, obj):
        if not obj.resource_type:
            return "-"
        return obj.resource_type.split(".")[-1]
