from django.contrib import admin, messages
from django.utils.html import format_html

from apps.organizations.models import (
    InvitationStatus,
    Organization,
    OrganizationInvitation,
    OrganizationMember,
    OrganizationRole,
)


class OrganizationMemberInline(admin.TabularInline):
    model = OrganizationMember
    extra = 0
    fields = ["user", "role", "is_active", "joined_at"]
    readonly_fields = ["joined_at"]


class OrganizationInvitationInline(admin.TabularInline):
    model = OrganizationInvitation
    extra = 0
    fields = ["email", "role", "status", "expires_at", "created_at"]
    readonly_fields = ["created_at"]


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "slug",
        "owner",
        "members_count_display",
        "is_active_badge",
        "is_deleted",
        "created_at",
    ]
    list_filter = ["is_active", "is_deleted", "created_at"]
    search_fields = ["name", "slug", "owner__email", "description"]
    readonly_fields = ["id", "created_at", "updated_at", "deleted_at"]
    inlines = [OrganizationMemberInline, OrganizationInvitationInline]
    actions = ["restore_selected", "activate_selected", "deactivate_selected"]

    def get_queryset(self, request):
        return Organization.all_objects.all()

    @admin.display(description="Members")
    def members_count_display(self, obj):
        count = obj.members.filter(is_active=True, is_deleted=False).count()
        return format_html("<strong>{}</strong>", count)

    @admin.display(description="Active")
    def is_active_badge(self, obj):
        color = "#28a745" if obj.is_active else "#dc3545"
        label = "Active" if obj.is_active else "Inactive"
        return format_html(
            '<span style="background-color: {}; color: #fff; padding: 2px 8px; border-radius: 4px; font-weight: 600; font-size: 11px;">{}</span>',
            color,
            label,
        )

    @admin.action(description="Restore selected organizations")
    def restore_selected(self, request, queryset):
        restored = 0
        for item in queryset:
            if item.is_deleted:
                item.restore()
                restored += 1
        self.message_user(
            request,
            f"Successfully restored {restored} organization(s).",
            messages.SUCCESS,
        )

    @admin.action(description="Activate selected organizations")
    def activate_selected(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(
            request,
            f"Activated {updated} organization(s).",
            messages.SUCCESS,
        )

    @admin.action(description="Deactivate selected organizations")
    def deactivate_selected(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(
            request,
            f"Deactivated {updated} organization(s).",
            messages.SUCCESS,
        )


@admin.register(OrganizationMember)
class OrganizationMemberAdmin(admin.ModelAdmin):
    list_display = [
        "user",
        "organization",
        "role_badge",
        "is_active",
        "joined_at",
        "is_deleted",
    ]
    list_filter = ["role", "is_active", "is_deleted", "organization"]
    search_fields = ["user__email", "organization__name"]
    readonly_fields = ["id", "joined_at", "created_at", "updated_at", "deleted_at"]

    @admin.display(description="Role")
    def role_badge(self, obj):
        color_map = {
            OrganizationRole.OWNER: "#6f42c1",
            OrganizationRole.ADMIN: "#007bff",
            OrganizationRole.MEMBER: "#28a745",
            OrganizationRole.BILLING: "#fd7e14",
            OrganizationRole.VIEWER: "#6c757d",
        }
        color = color_map.get(obj.role, "#6c757d")
        return format_html(
            '<span style="background-color: {}; color: #fff; padding: 2px 8px; border-radius: 4px; font-weight: 600; font-size: 11px;">{}</span>',
            color,
            obj.role,
        )


@admin.register(OrganizationInvitation)
class OrganizationInvitationAdmin(admin.ModelAdmin):
    list_display = [
        "email",
        "organization",
        "role",
        "status_badge",
        "invited_by",
        "expires_at",
        "created_at",
    ]
    list_filter = ["status", "role", "organization"]
    search_fields = ["email", "token", "organization__name", "invited_by__email"]
    readonly_fields = [
        "id",
        "token",
        "accepted_at",
        "created_at",
        "updated_at",
        "deleted_at",
    ]

    @admin.display(description="Status")
    def status_badge(self, obj):
        color_map = {
            InvitationStatus.ACCEPTED: "#28a745",
            InvitationStatus.PENDING: "#ffc107",
            InvitationStatus.DECLINED: "#dc3545",
            InvitationStatus.EXPIRED: "#6c757d",
            InvitationStatus.REVOKED: "#343a40",
        }
        color = color_map.get(obj.status, "#6c757d")
        text_color = "#000" if obj.status == InvitationStatus.PENDING else "#fff"
        return format_html(
            '<span style="background-color: {}; color: {}; padding: 2px 8px; border-radius: 4px; font-weight: 600; font-size: 11px;">{}</span>',
            color,
            text_color,
            obj.status,
        )
