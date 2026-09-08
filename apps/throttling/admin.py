from django.contrib import admin

from apps.throttling.models import IPBlocklist, ThrottlingRule
from apps.throttling.services import ThrottlingService


@admin.register(ThrottlingRule)
class ThrottlingRuleAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "scope_type",
        "rate_limit",
        "period_seconds",
        "burst_limit",
        "is_active",
        "created_at",
    )
    list_filter = ("scope_type", "is_active", "created_at")
    search_fields = ("name", "path_pattern", "description")
    readonly_fields = ("id", "created_at", "updated_at")
    actions = ["activate_rules", "deactivate_rules", "purge_rule_cache"]

    @admin.action(description="Activate selected throttling rules")
    def activate_rules(self, request, queryset):
        queryset.update(is_active=True)
        ThrottlingService.invalidate_rule_cache()

    @admin.action(description="Deactivate selected throttling rules")
    def deactivate_rules(self, request, queryset):
        queryset.update(is_active=False)
        ThrottlingService.invalidate_rule_cache()

    @admin.action(description="Purge rate limit rules cache")
    def purge_rule_cache(self, request, queryset):
        ThrottlingService.invalidate_rule_cache()
        self.message_user(request, "Throttling rule cache purged successfully.")

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        ThrottlingService.invalidate_rule_cache()

    def delete_model(self, request, obj):
        super().delete_model(request, obj)
        ThrottlingService.invalidate_rule_cache()


@admin.register(IPBlocklist)
class IPBlocklistAdmin(admin.ModelAdmin):
    list_display = ("ip_address", "reason", "is_active", "expires_at", "created_at")
    list_filter = ("is_active", "expires_at", "created_at")
    search_fields = ("ip_address", "reason")
    readonly_fields = ("id", "created_at", "updated_at")
    actions = ["unblock_ips"]

    @admin.action(description="Unblock selected IP addresses")
    def unblock_ips(self, request, queryset):
        for entry in queryset:
            ThrottlingService.unblock_ip(entry.ip_address)
        self.message_user(request, "Selected IP addresses have been unblocked.")
