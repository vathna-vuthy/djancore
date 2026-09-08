from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from apps.api_keys.models import APIKey


@admin.action(description=_("Restore selected API keys"))
def restore_selected_api_keys(modeladmin, request, queryset):
    for obj in queryset:
        obj.restore()


@admin.register(APIKey)
class APIKeyAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "prefix",
        "user",
        "is_active",
        "is_expired",
        "is_deleted",
        "last_used_at",
        "created_at",
    )
    list_filter = ("is_active", "is_deleted", "created_at")
    search_fields = ("name", "prefix", "user__email")
    readonly_fields = (
        "id",
        "prefix",
        "hashed_key",
        "last_used_at",
        "last_used_ip",
        "created_at",
        "updated_at",
        "deleted_at",
    )
    filter_horizontal = ("roles", "permissions")
    actions = [restore_selected_api_keys]

    fieldsets = (
        (
            None,
            {
                "fields": (
                    "name",
                    "prefix",
                    "user",
                    "is_active",
                )
            },
        ),
        (
            _("Security & Scopes"),
            {
                "fields": (
                    "roles",
                    "permissions",
                    "allowed_ips",
                    "rate_limit",
                    "expires_at",
                )
            },
        ),
        (
            _("Usage & Audit"),
            {
                "fields": (
                    "last_used_at",
                    "last_used_ip",
                    "hashed_key",
                    "id",
                    "is_deleted",
                    "deleted_at",
                    "created_at",
                    "updated_at",
                )
            },
        ),
    )
