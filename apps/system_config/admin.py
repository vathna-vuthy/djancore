from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from apps.system_config.models import SystemConfig
from apps.system_config.services import ConfigService


@admin.action(description=_("Purge cache for selected configurations"))
def purge_config_cache(modeladmin, request, queryset):
    for obj in queryset:
        obj.invalidate_cache()
    ConfigService.purge_cache()


@admin.action(description=_("Restore selected configurations"))
def restore_selected(modeladmin, request, queryset):
    for obj in queryset:
        obj.restore()


@admin.register(SystemConfig)
class SystemConfigAdmin(admin.ModelAdmin):
    list_display = (
        "key",
        "group",
        "data_type",
        "display_value_short",
        "is_secret",
        "is_public",
        "is_deleted",
        "updated_at",
    )
    list_filter = ("group", "data_type", "is_secret", "is_public", "is_deleted")
    search_fields = ("key", "description", "group")
    readonly_fields = ("id", "created_at", "updated_at", "deleted_at")
    actions = [purge_config_cache, restore_selected]

    fieldsets = (
        (
            None,
            {
                "fields": (
                    "key",
                    "group",
                    "data_type",
                    "raw_value",
                    "description",
                )
            },
        ),
        (
            _("Visibility & Protection"),
            {
                "fields": (
                    "is_secret",
                    "is_public",
                )
            },
        ),
        (
            _("Audit Timestamps"),
            {
                "fields": (
                    "id",
                    "is_deleted",
                    "deleted_at",
                    "created_at",
                    "updated_at",
                )
            },
        ),
    )

    @admin.display(description="Value")
    def display_value_short(self, obj: SystemConfig) -> str:
        if obj.is_secret:
            return obj.masked_value
        val = obj.raw_value
        return f"{val[:50]}..." if len(val) > 50 else val
