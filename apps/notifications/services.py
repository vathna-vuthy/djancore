import datetime
import logging
from typing import Any

from django.db import transaction
from django.template import Context, Template
from django.utils import timezone

from apps.notifications.models import (
    DeliveryStatus,
    NotificationLog,
    NotificationTemplate,
)
from apps.notifications.providers.registry import ProviderRegistry

logger = logging.getLogger(__name__)


class NotificationService:
    """Core service managing template rendering, provider dispatching, and scheduled triggers."""

    @staticmethod
    def render_content(template_str: str, context: dict[str, Any]) -> str:
        """Render string containing template placeholders using Django Template engine."""
        if not template_str:
            return ""
        try:
            django_template = Template(template_str)
            return django_template.render(Context(context))
        except Exception as e:
            logger.warning("Error rendering template string: %s", e)
            return template_str

    @classmethod
    def send(
        cls,
        recipient: str,
        channel: str,
        subject: str,
        body: str,
        context: dict[str, Any] | None = None,
        scheduled_for: datetime.datetime | None = None,
        template: NotificationTemplate | None = None,
        user: Any = None,
        **kwargs: Any,
    ) -> NotificationLog:
        """
        Send or schedule a notification.

        If scheduled_for is in the future, the message is saved with status SCHEDULED.
        Otherwise, it is dispatched immediately via the registered channel provider.
        """
        context = context or {}
        now = timezone.now()
        is_future_scheduled = scheduled_for is not None and scheduled_for > now

        log = NotificationLog.objects.create(
            recipient=recipient.strip(),
            channel=channel.lower(),
            template=template,
            subject=subject,
            body=body,
            payload=context,
            status=DeliveryStatus.SCHEDULED
            if is_future_scheduled
            else DeliveryStatus.PENDING,
            scheduled_for=scheduled_for if is_future_scheduled else None,
            user=user if user and user.is_authenticated else None,
        )

        if is_future_scheduled:
            logger.info(
                "Notification %s scheduled for %s to %s [%s]",
                log.id,
                scheduled_for,
                recipient,
                channel,
            )
            return log

        # Dispatch immediately
        return cls._dispatch_log(log, **kwargs)

    @classmethod
    def send_template(
        cls,
        recipient: str,
        template_code: str,
        context: dict[str, Any] | None = None,
        scheduled_for: datetime.datetime | None = None,
        user: Any = None,
        **kwargs: Any,
    ) -> NotificationLog:
        """Send a notification rendered from an active NotificationTemplate."""
        context = context or {}
        try:
            tmpl = NotificationTemplate.objects.get(code=template_code, is_active=True)
        except NotificationTemplate.DoesNotExist:
            raise ValueError(
                f"Active notification template with code '{template_code}' not found."
            ) from None

        rendered_subject = cls.render_content(tmpl.subject_template, context)
        rendered_body = cls.render_content(tmpl.body_template, context)

        return cls.send(
            recipient=recipient,
            channel=tmpl.channel,
            subject=rendered_subject,
            body=rendered_body,
            context=context,
            scheduled_for=scheduled_for,
            template=tmpl,
            user=user,
            **kwargs,
        )

    @classmethod
    def _dispatch_log(cls, log: NotificationLog, **kwargs: Any) -> NotificationLog:
        """Internal helper to dispatch a NotificationLog instance via its channel provider."""
        provider = ProviderRegistry.get(log.channel)
        if not provider:
            log.status = DeliveryStatus.FAILED
            log.error_message = f"No provider registered for channel '{log.channel}'."
            log.save(update_fields=["status", "error_message", "updated_at"])
            return log

        try:
            result = provider.send(
                recipient=log.recipient,
                subject=log.subject,
                body=log.body,
                context=log.payload,
                **kwargs,
            )

            if result.success:
                log.status = DeliveryStatus.SENT
                log.sent_at = timezone.now()
                log.error_message = ""
            else:
                log.status = DeliveryStatus.FAILED
                log.error_message = result.error or "Provider dispatch failed."
        except Exception as e:
            logger.exception("Error executing provider for log %s: %s", log.id, e)
            log.status = DeliveryStatus.FAILED
            log.error_message = str(e)

        log.save(update_fields=["status", "sent_at", "error_message", "updated_at"])
        return log

    @classmethod
    def process_due_notifications(cls, batch_size: int = 100) -> int:
        """
        Fetch and process due scheduled notifications using atomic row locking.
        Safe for concurrent executions across multiple workers or cron jobs.
        """
        now = timezone.now()
        processed_count = 0

        with transaction.atomic():
            due_logs = list(
                NotificationLog.objects.select_for_update(skip_locked=True)
                .filter(
                    status=DeliveryStatus.SCHEDULED,
                    scheduled_for__lte=now,
                    is_deleted=False,
                )
                .order_by("scheduled_for")[:batch_size]
            )

            for log in due_logs:
                cls._dispatch_log(log)
                processed_count += 1

        return processed_count

    @classmethod
    def cancel_scheduled(cls, log_id: Any) -> NotificationLog:
        """Cancel a pending scheduled notification."""
        log = NotificationLog.objects.get(id=log_id)
        if log.status != DeliveryStatus.SCHEDULED:
            raise ValueError(
                f"Cannot cancel notification with status '{log.status}'. Only SCHEDULED can be cancelled."
            )
        log.status = DeliveryStatus.CANCELLED
        log.save(update_fields=["status", "updated_at"])
        return log

    @classmethod
    def reschedule(
        cls, log_id: Any, new_scheduled_for: datetime.datetime
    ) -> NotificationLog:
        """Reschedule a pending notification for a new target delivery time."""
        now = timezone.now()
        if new_scheduled_for <= now:
            raise ValueError("new_scheduled_for must be a future datetime.")

        log = NotificationLog.objects.get(id=log_id)
        if log.status not in (DeliveryStatus.SCHEDULED, DeliveryStatus.CANCELLED):
            raise ValueError(
                f"Cannot reschedule notification with status '{log.status}'."
            )

        log.scheduled_for = new_scheduled_for
        log.status = DeliveryStatus.SCHEDULED
        log.save(update_fields=["scheduled_for", "status", "updated_at"])
        return log

    @classmethod
    def retry_failed(cls, log_id: Any) -> NotificationLog:
        """Retry sending a failed or cancelled notification immediately."""
        log = NotificationLog.objects.get(id=log_id)
        return cls._dispatch_log(log)
