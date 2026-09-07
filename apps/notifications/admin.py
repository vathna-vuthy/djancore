from django.contrib import admin, messages
from django.utils.translation import gettext_lazy as _

from apps.notifications.models import NotificationLog, NotificationTemplate
from apps.notifications.services import NotificationService


@admin.register(NotificationTemplate)
class NotificationTemplateAdmin(admin.ModelAdmin):
    """Admin interface for managing Notification Templates."""

    list_display = [
        "code",
        "name",
        "channel",
        "is_active",
        "is_deleted",
        "created_at",
        "updated_at",
    ]
    list_filter = ["channel", "is_active", "is_deleted"]
    search_fields = ["code", "name", "subject_template", "body_template"]
    readonly_fields = ["id", "created_at", "updated_at", "deleted_at"]
    actions = ["restore_selected"]

    @admin.action(description=_("Restore selected soft-deleted templates"))
    def restore_selected(self, request, queryset):
        restored = 0
        for obj in queryset:
            if obj.is_deleted:
                obj.restore()
                restored += 1
        self.message_user(
            request,
            f"{restored} template(s) restored successfully.",
            messages.SUCCESS,
        )


@admin.register(NotificationLog)
class NotificationLogAdmin(admin.ModelAdmin):
    """Admin interface for reviewing and managing Notification Delivery Logs."""

    list_display = [
        "id",
        "recipient",
        "channel",
        "status",
        "scheduled_for",
        "sent_at",
        "template",
        "is_deleted",
        "created_at",
    ]
    list_filter = ["channel", "status", "is_deleted", "created_at"]
    search_fields = ["recipient", "subject", "error_message"]
    readonly_fields = [
        "id",
        "created_at",
        "updated_at",
        "sent_at",
        "deleted_at",
    ]
    actions = ["retry_selected_failed", "restore_selected"]

    @admin.action(description=_("Retry sending selected failed notifications"))
    def retry_selected_failed(self, request, queryset):
        retried = 0
        for obj in queryset:
            NotificationService.retry_failed(obj.id)
            retried += 1
        self.message_user(
            request,
            f"{retried} notification(s) retried.",
            messages.SUCCESS,
        )

    @admin.action(description=_("Restore selected soft-deleted logs"))
    def restore_selected(self, request, queryset):
        restored = 0
        for obj in queryset:
            if obj.is_deleted:
                obj.restore()
                restored += 1
        self.message_user(
            request,
            f"{restored} log(s) restored successfully.",
            messages.SUCCESS,
        )
