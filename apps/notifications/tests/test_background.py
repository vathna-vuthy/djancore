import datetime
from importlib.util import find_spec
from unittest import skipUnless
from unittest.mock import patch

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.core import mail
from django.db import transaction
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.iam.tests.helpers import grant_permissions
from apps.notifications.models import (
    DeliveryStatus,
    NotificationLog,
    NotificationTemplate,
)
from apps.notifications.providers.base import NotificationResult
from apps.notifications.services import NotificationService

HAS_CELERY = find_spec("celery") is not None
if HAS_CELERY:
    from apps.notifications.tasks import deliver_notification


@override_settings(CELERY_ENABLED=True)
@skipUnless(HAS_CELERY, "Install the celery extra to test background delivery")
class BackgroundNotificationTest(TestCase):
    def test_send_waits_for_commit_without_sending_email(self):
        with self.captureOnCommitCallbacks() as callbacks:
            log = NotificationService.send(
                recipient="queued@example.com",
                channel="email",
                subject="Background",
                body="Deliver from a worker",
            )
        self.assertEqual(log.status, DeliveryStatus.PENDING)
        self.assertEqual(len(mail.outbox), 0)
        self.assertEqual(len(callbacks), 1)

    def test_publish_after_commit_and_deliver_once(self):
        with patch.object(deliver_notification, "apply_async") as publish:
            with self.captureOnCommitCallbacks(execute=True):
                log = NotificationService.send(
                    recipient="queued@example.com",
                    channel="email",
                    subject="Queued",
                    body="Body",
                    from_email="custom@example.com",
                )
                publish.assert_not_called()
            publish.assert_called_once_with(
                args=[str(log.pk)],
                kwargs={"from_email": "custom@example.com"},
                retry=False,
            )
        deliver_notification.run(str(log.pk), from_email="custom@example.com")
        deliver_notification.run(str(log.pk))
        log.refresh_from_db()
        self.assertEqual(log.status, DeliveryStatus.SENT)
        self.assertIsNotNone(log.sent_at)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].from_email, "custom@example.com")

    def test_rollback_does_not_publish(self):
        with patch.object(deliver_notification, "apply_async") as publish:
            with self.captureOnCommitCallbacks(execute=True), transaction.atomic():
                NotificationService.send(
                    recipient="rollback@example.com",
                    channel="email",
                    body="Body",
                    subject="",
                )
                transaction.set_rollback(True)
            publish.assert_not_called()
        self.assertFalse(NotificationLog.objects.exists())

    def test_broker_failure_records_failed_delivery_without_sending(self):
        with (
            patch.object(
                deliver_notification, "apply_async", side_effect=ConnectionError
            ),
            self.assertLogs("apps.notifications.services", level="ERROR"),
            self.captureOnCommitCallbacks(execute=True),
        ):
            log = NotificationService.send(
                recipient="failed@example.com",
                channel="email",
                subject="",
                body="Body",
            )
        log.refresh_from_db()
        self.assertEqual(log.status, DeliveryStatus.FAILED)
        self.assertIn("Could not queue", log.error_message)
        self.assertEqual(len(mail.outbox), 0)

    def test_telegram_only_contacts_provider_from_worker(self):
        with patch(
            "apps.notifications.providers.telegram.TelegramNotificationProvider.send",
            return_value=NotificationResult(success=True),
        ) as send:
            log = NotificationService.send(
                recipient="123456",
                channel="telegram",
                subject="",
                body="Hello",
            )
            send.assert_not_called()
            deliver_notification.run(str(log.pk))
            send.assert_called_once()
        log.refresh_from_db()
        self.assertEqual(log.status, DeliveryStatus.SENT)

    def test_worker_records_provider_failure(self):
        log = NotificationService.send(
            recipient="123456",
            channel="telegram",
            subject="",
            body="Hello",
        )
        with patch(
            "apps.notifications.providers.telegram.TelegramNotificationProvider.send",
            return_value=NotificationResult(success=False, error="Unavailable"),
        ):
            deliver_notification.run(str(log.pk))
        log.refresh_from_db()
        self.assertEqual(log.status, DeliveryStatus.FAILED)
        self.assertEqual(log.error_message, "Unavailable")

    def test_worker_skips_deleted_cancelled_and_scheduled_logs(self):
        for state in (DeliveryStatus.CANCELLED, DeliveryStatus.SCHEDULED):
            log = NotificationLog.objects.create(
                recipient="skip@example.com",
                channel="email",
                body="Body",
                status=state,
            )
            deliver_notification.run(str(log.pk))
            log.refresh_from_db()
            self.assertEqual(log.status, state)
        log = NotificationService.send(
            recipient="deleted@example.com",
            channel="email",
            subject="",
            body="Body",
        )
        log.delete()
        deliver_notification.run(str(log.pk))
        self.assertEqual(len(mail.outbox), 0)

    def test_future_schedule_is_not_published(self):
        with self.captureOnCommitCallbacks() as callbacks:
            log = NotificationService.send(
                recipient="future@example.com",
                channel="email",
                subject="",
                body="Body",
                scheduled_for=timezone.now() + datetime.timedelta(hours=1),
            )
        self.assertEqual(log.status, DeliveryStatus.SCHEDULED)
        self.assertEqual(callbacks, [])

    def test_failed_retry_is_queued(self):
        log = NotificationLog.objects.create(
            recipient="retry@example.com",
            channel="email",
            body="Body",
            status=DeliveryStatus.FAILED,
            error_message="Previous failure",
        )
        with self.captureOnCommitCallbacks() as callbacks:
            retried = NotificationService.retry_failed(log.pk)
        self.assertEqual(retried.status, DeliveryStatus.PENDING)
        self.assertEqual(retried.error_message, "")
        self.assertEqual(len(callbacks), 1)
        self.assertEqual(len(mail.outbox), 0)

    def test_admin_restores_templates(self):
        template = NotificationTemplate.objects.create(code="RESTORE", name="Restore")
        template.delete()
        model_admin = admin.site._registry[NotificationTemplate]
        with patch.object(model_admin, "message_user"):
            model_admin.restore_selected(
                None,
                NotificationTemplate.all_objects.filter(pk=template.pk),
            )
        template.refresh_from_db()
        self.assertFalse(template.is_deleted)

    def test_admin_only_retries_failed_logs(self):
        failed = NotificationLog.objects.create(
            recipient="failed@example.com",
            channel="email",
            body="Body",
            status=DeliveryStatus.FAILED,
        )
        pending = NotificationLog.objects.create(
            recipient="pending@example.com",
            channel="email",
            body="Body",
        )
        model_admin = admin.site._registry[NotificationLog]
        with (
            patch.object(model_admin, "message_user"),
            self.captureOnCommitCallbacks() as callbacks,
        ):
            model_admin.retry_selected_failed(None, NotificationLog.objects.all())
        failed.refresh_from_db()
        pending.refresh_from_db()
        self.assertEqual(failed.status, DeliveryStatus.PENDING)
        self.assertEqual(pending.status, DeliveryStatus.PENDING)
        self.assertEqual(len(callbacks), 1)
        self.assertEqual(len(mail.outbox), 0)

    def test_api_cannot_retry_pending_or_another_users_notification(self):
        user = get_user_model().objects.create_user(
            email="owner@example.com", password="test"
        )
        other = get_user_model().objects.create_user(
            email="other@example.com", password="test"
        )
        grant_permissions(user, "notifications:logs:retry")
        grant_permissions(other, "notifications:logs:retry")
        client = APIClient()
        client.force_authenticate(user)
        log = NotificationLog.objects.create(
            recipient="owner@example.com",
            channel="email",
            body="Body",
            user=user,
        )
        route = reverse("notifications:log-retry", kwargs={"pk": log.pk})
        with self.captureOnCommitCallbacks() as callbacks:
            response = client.post(route)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(callbacks, [])
        client.force_authenticate(other)
        self.assertEqual(client.post(route).status_code, 404)

    def test_api_direct_and_template_return_pending(self):
        user = get_user_model().objects.create_user(
            email="api@example.com", password="test"
        )
        grant_permissions(user, "notifications:send", "notifications:send_template")
        client = APIClient()
        client.force_authenticate(user)
        NotificationTemplate.objects.create(
            code="BACKGROUND",
            name="Background",
            channel="email",
            subject_template="Hi {{ name }}",
            body_template="Hello {{ name }}",
        )
        payloads = [
            (
                "notifications:send",
                {"recipient": "api@example.com", "channel": "email", "body": "Direct"},
            ),
            (
                "notifications:send-template",
                {
                    "recipient": "api@example.com",
                    "template_code": "BACKGROUND",
                    "context": {"name": "Alice"},
                },
            ),
        ]
        for route, payload in payloads:
            with self.captureOnCommitCallbacks() as callbacks:
                response = client.post(reverse(route), payload, format="json")
            self.assertEqual(response.status_code, 201)
            self.assertEqual(response.data["status"], "PENDING")
            self.assertEqual(len(callbacks), 1)
        self.assertEqual(response.data["subject"], "Hi Alice")
        self.assertEqual(len(mail.outbox), 0)
