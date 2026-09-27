import datetime
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.core import mail
from django.test import TestCase
from django.utils import timezone

from apps.notifications.models import (
    ChannelChoices,
    DeliveryStatus,
    NotificationLog,
    NotificationTemplate,
)
from apps.notifications.providers.base import NotificationResult
from apps.notifications.services import NotificationService

User = get_user_model()


class NotificationServiceTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="user@example.com",
            password="testpassword123",
        )
        self.template = NotificationTemplate.objects.create(
            code="WELCOME_EMAIL",
            name="Welcome Email",
            channel=ChannelChoices.EMAIL,
            subject_template="Welcome to {{ app_name }}, {{ username }}!",
            body_template="Hi {{ username }},\nThank you for signing up for {{ app_name }}.",
        )

    def test_render_content(self):
        rendered = NotificationService.render_content(
            "Hello {{ name }}! Your balance is ${{ balance }}.",
            {"name": "Alice", "balance": 100},
        )
        self.assertEqual(rendered, "Hello Alice! Your balance is $100.")

    def test_send_immediate_email(self):
        log = NotificationService.send(
            recipient="test@example.com",
            channel=ChannelChoices.EMAIL,
            subject="Test Subject",
            body="Test Body",
            user=self.user,
        )
        self.assertEqual(log.status, DeliveryStatus.SENT)
        self.assertIsNotNone(log.sent_at)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].subject, "Test Subject")
        self.assertEqual(mail.outbox[0].to, ["test@example.com"])

    def test_send_template(self):
        log = NotificationService.send_template(
            recipient="bob@example.com",
            template_code="WELCOME_EMAIL",
            context={"app_name": "Djancore", "username": "bob"},
            user=self.user,
        )
        self.assertEqual(log.status, DeliveryStatus.SENT)
        self.assertEqual(log.subject, "Welcome to Djancore, bob!")
        self.assertIn("Thank you for signing up for Djancore.", log.body)
        self.assertEqual(log.template, self.template)

    def test_send_template_not_found(self):
        with self.assertRaises(ValueError):
            NotificationService.send_template(
                recipient="bob@example.com",
                template_code="NON_EXISTENT",
            )

    def test_send_scheduled_future(self):
        future_time = timezone.now() + datetime.timedelta(hours=2)
        log = NotificationService.send(
            recipient="bob@example.com",
            channel=ChannelChoices.EMAIL,
            subject="Scheduled Subject",
            body="Scheduled Body",
            scheduled_for=future_time,
        )
        self.assertEqual(log.status, DeliveryStatus.SCHEDULED)
        self.assertEqual(log.scheduled_for, future_time)
        self.assertIsNone(log.sent_at)
        # Should not have sent mail immediately
        self.assertEqual(len(mail.outbox), 0)

    def test_cancel_scheduled(self):
        future_time = timezone.now() + datetime.timedelta(hours=2)
        log = NotificationService.send(
            recipient="bob@example.com",
            channel=ChannelChoices.EMAIL,
            subject="To Cancel",
            body="Cancel Body",
            scheduled_for=future_time,
        )
        cancelled = NotificationService.cancel_scheduled(log.id)
        self.assertEqual(cancelled.status, DeliveryStatus.CANCELLED)

    def test_cancel_non_scheduled_fails(self):
        log = NotificationService.send(
            recipient="bob@example.com",
            channel=ChannelChoices.EMAIL,
            subject="Immediate",
            body="Body",
        )
        with self.assertRaises(ValueError):
            NotificationService.cancel_scheduled(log.id)

    def test_reschedule(self):
        future_time1 = timezone.now() + datetime.timedelta(hours=2)
        future_time2 = timezone.now() + datetime.timedelta(hours=5)

        log = NotificationService.send(
            recipient="bob@example.com",
            channel=ChannelChoices.EMAIL,
            subject="To Reschedule",
            body="Reschedule Body",
            scheduled_for=future_time1,
        )
        rescheduled = NotificationService.reschedule(log.id, future_time2)
        self.assertEqual(rescheduled.scheduled_for, future_time2)
        self.assertEqual(rescheduled.status, DeliveryStatus.SCHEDULED)

    def test_reschedule_in_past_fails(self):
        future_time = timezone.now() + datetime.timedelta(hours=2)
        past_time = timezone.now() - datetime.timedelta(hours=1)

        log = NotificationService.send(
            recipient="bob@example.com",
            channel=ChannelChoices.EMAIL,
            subject="Past Reschedule",
            body="Body",
            scheduled_for=future_time,
        )
        with self.assertRaises(ValueError):
            NotificationService.reschedule(log.id, past_time)

    def test_retry_failed(self):
        log = NotificationLog.objects.create(
            recipient="retry@example.com",
            channel=ChannelChoices.EMAIL,
            subject="Retry Subject",
            body="Retry Body",
            status=DeliveryStatus.FAILED,
            error_message="Previous error",
        )
        retried = NotificationService.retry_failed(log.id)
        self.assertEqual(retried.status, DeliveryStatus.SENT)
        self.assertEqual(retried.error_message, "")
        self.assertEqual(len(mail.outbox), 1)

    def test_soft_delete_template_and_log(self):
        self.template.delete()
        self.assertTrue(self.template.is_deleted)
        self.assertEqual(NotificationTemplate.objects.count(), 0)
        self.assertEqual(NotificationTemplate.all_objects.count(), 1)

        self.template.restore()
        self.assertFalse(self.template.is_deleted)
        self.assertEqual(NotificationTemplate.objects.count(), 1)

    def test_render_content_empty_returns_empty(self):
        self.assertEqual(NotificationService.render_content("", {"a": 1}), "")

    def test_render_content_malformed_returns_raw_string(self):
        malformed = "{{ unclosed"
        self.assertEqual(NotificationService.render_content(malformed, {}), malformed)

    def test_send_anonymous_user_stored_as_null(self):
        log = NotificationService.send(
            recipient="anon@example.com",
            channel=ChannelChoices.EMAIL,
            subject="Anon",
            body="Anon Body",
            user=AnonymousUser(),
        )
        self.assertIsNone(log.user)
        self.assertEqual(log.status, DeliveryStatus.SENT)

    def test_send_past_scheduled_for_dispatches_immediately(self):
        past_time = timezone.now() - datetime.timedelta(hours=1)
        log = NotificationService.send(
            recipient="past@example.com",
            channel=ChannelChoices.EMAIL,
            subject="Past Schedule",
            body="Past Body",
            scheduled_for=past_time,
        )
        self.assertEqual(log.status, DeliveryStatus.SENT)
        self.assertIsNone(log.scheduled_for)
        self.assertEqual(len(mail.outbox), 1)

    def test_send_template_inactive_template_fails(self):
        self.template.is_active = False
        self.template.save(update_fields=["is_active"])

        with self.assertRaises(ValueError):
            NotificationService.send_template(
                recipient="bob@example.com",
                template_code="WELCOME_EMAIL",
            )

    def test_send_template_scheduled_future_not_dispatched(self):
        future_time = timezone.now() + datetime.timedelta(hours=3)
        log = NotificationService.send_template(
            recipient="bob@example.com",
            template_code="WELCOME_EMAIL",
            context={"app_name": "Djancore", "username": "bob"},
            scheduled_for=future_time,
        )
        self.assertEqual(log.status, DeliveryStatus.SCHEDULED)
        self.assertEqual(log.scheduled_for, future_time)
        self.assertEqual(log.template, self.template)
        self.assertEqual(len(mail.outbox), 0)

    def test_cancel_nonexistent_log_raises(self):
        with self.assertRaises(NotificationLog.DoesNotExist):
            NotificationService.cancel_scheduled("00000000-0000-0000-0000-000000000000")

    def test_reschedule_nonexistent_log_raises(self):
        with self.assertRaises(NotificationLog.DoesNotExist):
            NotificationService.reschedule(
                "00000000-0000-0000-0000-000000000000",
                timezone.now() + datetime.timedelta(hours=1),
            )

    def test_retry_nonexistent_log_raises(self):
        with self.assertRaises(NotificationLog.DoesNotExist):
            NotificationService.retry_failed("00000000-0000-0000-0000-000000000000")

    def test_retry_cancelled_log_dispatches(self):
        log = NotificationLog.objects.create(
            recipient="cancelled@example.com",
            channel=ChannelChoices.EMAIL,
            subject="Cancelled",
            body="Cancelled Body",
            status=DeliveryStatus.CANCELLED,
        )
        retried = NotificationService.retry_failed(log.id)
        self.assertEqual(retried.status, DeliveryStatus.SENT)
        self.assertEqual(len(mail.outbox), 1)

    def test_dispatch_stores_payload_context(self):
        log = NotificationService.send(
            recipient="ctx@example.com",
            channel=ChannelChoices.EMAIL,
            subject="Ctx",
            body="Ctx Body",
            context={"order_id": 42},
        )
        self.assertEqual(log.payload, {"order_id": 42})

    def test_send_recipient_is_stripped(self):
        log = NotificationService.send(
            recipient="  padded@example.com  ",
            channel=ChannelChoices.EMAIL,
            subject="Pad",
            body="Pad Body",
        )
        self.assertEqual(log.recipient, "padded@example.com")


class NotificationDispatchFailureTest(TestCase):
    """Failure branches of NotificationService._dispatch_log."""

    def test_unregistered_channel_marks_failed(self):
        log = NotificationService.send(
            recipient="+1234567890",
            channel=ChannelChoices.SMS,
            subject="SMS",
            body="SMS Body",
        )
        self.assertEqual(log.status, DeliveryStatus.FAILED)
        self.assertIn("No provider registered", log.error_message)
        self.assertIsNone(log.sent_at)

    def test_provider_failure_result_marks_failed(self):
        failing_provider = MagicMock()
        failing_provider.send.return_value = NotificationResult(
            success=False, error="SMTP connection refused"
        )
        with patch(
            "apps.notifications.services.ProviderRegistry.get",
            return_value=failing_provider,
        ):
            log = NotificationService.send(
                recipient="fail@example.com",
                channel=ChannelChoices.EMAIL,
                subject="Fail",
                body="Fail Body",
            )

        self.assertEqual(log.status, DeliveryStatus.FAILED)
        self.assertEqual(log.error_message, "SMTP connection refused")
        self.assertIsNone(log.sent_at)
        self.assertEqual(len(mail.outbox), 0)

    def test_provider_failure_without_error_message_defaults(self):
        failing_provider = MagicMock()
        failing_provider.send.return_value = NotificationResult(success=False)
        with patch(
            "apps.notifications.services.ProviderRegistry.get",
            return_value=failing_provider,
        ):
            log = NotificationService.send(
                recipient="fail@example.com",
                channel=ChannelChoices.EMAIL,
                subject="Fail",
                body="Fail Body",
            )

        self.assertEqual(log.status, DeliveryStatus.FAILED)
        self.assertEqual(log.error_message, "Provider dispatch failed.")

    def test_provider_exception_marks_failed(self):
        raising_provider = MagicMock()
        raising_provider.send.side_effect = RuntimeError("boom")
        with patch(
            "apps.notifications.services.ProviderRegistry.get",
            return_value=raising_provider,
        ):
            log = NotificationService.send(
                recipient="boom@example.com",
                channel=ChannelChoices.EMAIL,
                subject="Boom",
                body="Boom Body",
            )

        self.assertEqual(log.status, DeliveryStatus.FAILED)
        self.assertEqual(log.error_message, "boom")

    def test_provider_receives_log_payload_as_context(self):
        provider = MagicMock()
        provider.send.return_value = NotificationResult(success=True)
        with patch(
            "apps.notifications.services.ProviderRegistry.get",
            return_value=provider,
        ):
            NotificationService.send(
                recipient="ctx@example.com",
                channel=ChannelChoices.EMAIL,
                subject="Ctx",
                body="Ctx Body",
                context={"token": "abc"},
            )

        _, kwargs = provider.send.call_args
        self.assertEqual(kwargs["context"], {"token": "abc"})
        self.assertEqual(kwargs["recipient"], "ctx@example.com")
        self.assertEqual(kwargs["subject"], "Ctx")

    def test_retry_failed_channel_marks_failed_again(self):
        log = NotificationLog.objects.create(
            recipient="+1234567890",
            channel=ChannelChoices.SLACK,
            subject="Slack",
            body="Slack Body",
            status=DeliveryStatus.FAILED,
            error_message="old error",
        )
        retried = NotificationService.retry_failed(log.id)
        self.assertEqual(retried.status, DeliveryStatus.FAILED)
        self.assertIn("No provider registered", retried.error_message)
