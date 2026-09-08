from django.contrib import admin, messages
from django.utils.html import format_html

from apps.webhooks.models import WebhookDelivery, WebhookEndpoint, WebhookStatus
from apps.webhooks.services import WebhookDispatcher


@admin.register(WebhookEndpoint)
class WebhookEndpointAdmin(admin.ModelAdmin):
    list_display = [
        "target_url",
        "user",
        "description",
        "is_active_badge",
        "events_summary",
        "is_deleted",
        "created_at",
    ]
    list_filter = ["is_active", "is_deleted", "created_at"]
    search_fields = ["target_url", "description", "user__email"]
    readonly_fields = [
        "id",
        "masked_secret_display",
        "created_at",
        "updated_at",
        "deleted_at",
    ]
    actions = [
        "restore_selected",
        "ping_selected",
        "activate_selected",
        "deactivate_selected",
    ]

    def get_queryset(self, request):
        return WebhookEndpoint.all_objects.all()

    @admin.display(description="Active")
    def is_active_badge(self, obj):
        color = "#28a745" if obj.is_active else "#dc3545"
        label = "Active" if obj.is_active else "Inactive"
        return format_html(
            '<span style="background-color: {}; color: #fff; padding: 2px 8px; border-radius: 4px; font-weight: 600; font-size: 11px;">{}</span>',
            color,
            label,
        )

    @admin.display(description="Subscribed Events")
    def events_summary(self, obj):
        if not obj.events:
            return "None"
        if "*" in obj.events:
            return format_html("<code>* (all events)</code>")
        return format_html(
            "<code>{}</code>",
            ", ".join(obj.events[:3]) + ("..." if len(obj.events) > 3 else ""),
        )

    @admin.display(description="Signing Secret")
    def masked_secret_display(self, obj):
        return obj.masked_secret

    @admin.action(description="Restore selected webhook endpoints")
    def restore_selected(self, request, queryset):
        restored = 0
        for item in queryset:
            if item.is_deleted:
                item.restore()
                restored += 1
        self.message_user(
            request,
            f"Successfully restored {restored} webhook endpoint(s).",
            messages.SUCCESS,
        )

    @admin.action(description="Send test ping to selected endpoints")
    def ping_selected(self, request, queryset):
        success = 0
        failed = 0
        for endpoint in queryset.filter(is_active=True, is_deleted=False):
            delivery = WebhookDispatcher.ping_endpoint(endpoint)
            if delivery.status == WebhookStatus.SUCCESS:
                success += 1
            else:
                failed += 1
        self.message_user(
            request,
            f"Pinged endpoints: {success} succeeded, {failed} failed.",
            messages.INFO,
        )

    @admin.action(description="Activate selected webhook endpoints")
    def activate_selected(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(
            request,
            f"Activated {updated} webhook endpoint(s).",
            messages.SUCCESS,
        )

    @admin.action(description="Deactivate selected webhook endpoints")
    def deactivate_selected(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(
            request,
            f"Deactivated {updated} webhook endpoint(s).",
            messages.SUCCESS,
        )


@admin.register(WebhookDelivery)
class WebhookDeliveryAdmin(admin.ModelAdmin):
    list_display = [
        "event_type",
        "target_url_display",
        "status_badge",
        "response_status_code",
        "duration_ms_display",
        "attempt",
        "sent_at",
        "created_at",
    ]
    list_filter = ["status", "event_type", "created_at"]
    search_fields = ["event_type", "endpoint__target_url", "error_message"]
    readonly_fields = [
        "id",
        "endpoint",
        "event_type",
        "event_id",
        "payload",
        "status",
        "response_status_code",
        "response_headers",
        "response_body",
        "duration_ms",
        "attempt",
        "error_message",
        "sent_at",
        "next_retry_at",
        "created_at",
        "updated_at",
    ]
    actions = ["retry_selected_deliveries"]

    @admin.display(description="Endpoint URL")
    def target_url_display(self, obj):
        return obj.endpoint.target_url

    @admin.display(description="Status")
    def status_badge(self, obj):
        color_map = {
            WebhookStatus.SUCCESS: "#28a745",
            WebhookStatus.FAILED: "#dc3545",
            WebhookStatus.PENDING: "#ffc107",
        }
        color = color_map.get(obj.status, "#6c757d")
        text_color = "#000" if obj.status == WebhookStatus.PENDING else "#fff"
        return format_html(
            '<span style="background-color: {}; color: {}; padding: 2px 8px; border-radius: 4px; font-weight: 600; font-size: 11px;">{}</span>',
            color,
            text_color,
            obj.status,
        )

    @admin.display(description="Latency")
    def duration_ms_display(self, obj):
        if obj.duration_ms is None:
            return "-"
        return f"{obj.duration_ms} ms"

    @admin.action(description="Retry selected webhook deliveries")
    def retry_selected_deliveries(self, request, queryset):
        success = 0
        failed = 0
        for delivery in queryset:
            updated = WebhookDispatcher.retry_delivery(delivery)
            if updated.status == WebhookStatus.SUCCESS:
                success += 1
            else:
                failed += 1
        self.message_user(
            request,
            f"Retried deliveries: {success} succeeded, {failed} failed.",
            messages.INFO,
        )
