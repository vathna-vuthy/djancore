from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _

from apps.iam.models import Permission, Role, User, UserGroup


@admin.action(description="Restore selected items")
def restore_selected(modeladmin, request, queryset):
    for obj in queryset:
        obj.restore()


@admin.register(Permission)
class PermissionAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "action",
        "resource",
        "effect",
        "is_deleted",
        "created_at",
    )
    list_filter = ("effect", "is_deleted", "created_at")
    search_fields = ("name", "action", "resource", "description")
    actions = [restore_selected]
    readonly_fields = ("id", "created_at", "updated_at", "deleted_at")


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "is_system",
        "is_deleted",
        "created_at",
    )
    list_filter = ("is_system", "is_deleted", "created_at")
    search_fields = ("name", "description")
    filter_horizontal = ("permissions", "users")
    actions = [restore_selected]
    readonly_fields = ("id", "created_at", "updated_at", "deleted_at")


@admin.register(UserGroup)
class UserGroupAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "is_deleted",
        "created_at",
    )
    list_filter = ("is_deleted", "created_at")
    search_fields = ("name", "description")
    filter_horizontal = ("roles", "permissions", "members")
    actions = [restore_selected]
    readonly_fields = ("id", "created_at", "updated_at", "deleted_at")


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        (
            _("Personal info"),
            {"fields": ("first_name", "last_name", "phone")},
        ),
        (
            _("Permissions & Access"),
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                ),
            },
        ),
        (
            _("Audit & Soft-Delete"),
            {
                "fields": (
                    "is_deleted",
                    "deleted_at",
                    "last_login",
                    "date_joined",
                    "created_at",
                    "updated_at",
                ),
            },
        ),
    )
    readonly_fields = (
        "id",
        "date_joined",
        "last_login",
        "created_at",
        "updated_at",
        "deleted_at",
    )
    list_display = (
        "email",
        "first_name",
        "last_name",
        "is_staff",
        "is_active",
        "is_deleted",
        "created_at",
    )
    list_filter = ("is_staff", "is_superuser", "is_active", "is_deleted")
    search_fields = ("email", "first_name", "last_name")
    ordering = ("-created_at",)
    actions = [restore_selected]
