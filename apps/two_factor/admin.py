from django.contrib import admin
from django.utils.html import format_html

from apps.two_factor.models import RecoveryCode, TOTPDevice


class RecoveryCodeInline(admin.TabularInline):
    model = RecoveryCode
    extra = 0
    readonly_fields = ("hashed_code", "is_used", "used_at", "created_at")
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(TOTPDevice)
class TOTPDeviceAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "confirmed_badge",
        "last_verified_at",
        "remaining_recovery_codes",
        "created_at",
    )
    list_filter = ("is_confirmed", "created_at")
    search_fields = ("user__email", "user__first_name", "user__last_name")
    readonly_fields = (
        "id",
        "user",
        "last_used_step",
        "is_confirmed",
        "last_verified_at",
        "created_at",
        "updated_at",
    )
    inlines = [RecoveryCodeInline]

    @admin.display(description="Status")
    def confirmed_badge(self, obj):
        if obj.is_confirmed:
            return format_html(
                '<span style="background-color: #10B981; color: white; padding: 3px 8px; border-radius: 4px; font-weight: bold; font-size: 11px;">Active</span>'
            )
        return format_html(
            '<span style="background-color: #F59E0B; color: white; padding: 3px 8px; border-radius: 4px; font-weight: bold; font-size: 11px;">Pending</span>'
        )

    @admin.display(description="Recovery Codes Remaining")
    def remaining_recovery_codes(self, obj):
        count = obj.recovery_codes.filter(is_used=False).count()
        total = obj.recovery_codes.count()
        return f"{count}/{total}"


@admin.register(RecoveryCode)
class RecoveryCodeAdmin(admin.ModelAdmin):
    list_display = ("device", "is_used", "used_at", "created_at")
    list_filter = ("is_used", "created_at")
    search_fields = ("device__user__email",)
    readonly_fields = (
        "id",
        "device",
        "hashed_code",
        "is_used",
        "used_at",
        "created_at",
    )
