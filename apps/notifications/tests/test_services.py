import datetime

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase
from django.utils import timezone

from apps.notifications.models import (
    ChannelChoices,
    DeliveryStatus,
    NotificationLog,
    NotificationTemplate,
)
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
