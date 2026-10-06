"""Worker delivery tasks, imported only when the Celery extra is installed."""

from typing import Any

from django.db import transaction

from apps.notifications.models import DeliveryStatus, NotificationLog
from apps.notifications.services import NotificationService
from config.celery import app


@app.task(ignore_result=True)
def deliver_notification(log_id: str, **kwargs: Any) -> None:
    # Lock through dispatch so concurrent tasks cannot send the same pending log.
    with transaction.atomic():
        log = (
            NotificationLog.objects.select_for_update()
            .filter(pk=log_id, status=DeliveryStatus.PENDING)
            .first()
        )
        if log is not None:
            NotificationService._dispatch_log(log, **kwargs)
