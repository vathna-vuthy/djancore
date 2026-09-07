import datetime
from io import StringIO

from django.core import mail
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from apps.notifications.models import (
    ChannelChoices,
    DeliveryStatus,
    NotificationLog,
)
from apps.notifications.services import NotificationService


class SchedulerTest(TestCase):
    def test_process_due_notifications(self):
        past_time = timezone.now() - datetime.timedelta(minutes=10)
        future_time = timezone.now() + datetime.timedelta(hours=2)

        # 1. Due notification
        due_log = NotificationLog.objects.create(
            recipient="due@example.com",
            channel=ChannelChoices.EMAIL,
            subject="Due Subject",
            body="Due Body",
            status=DeliveryStatus.SCHEDULED,
            scheduled_for=past_time,
        )

        # 2. Future notification (should not be processed)
        future_log = NotificationLog.objects.create(
            recipient="future@example.com",
            channel=ChannelChoices.EMAIL,
            subject="Future Subject",
            body="Future Body",
            status=DeliveryStatus.SCHEDULED,
            scheduled_for=future_time,
        )

        # 3. Cancelled notification (should not be processed)
        cancelled_log = NotificationLog.objects.create(
            recipient="cancelled@example.com",
            channel=ChannelChoices.EMAIL,
            subject="Cancelled Subject",
            body="Cancelled Body",
            status=DeliveryStatus.CANCELLED,
            scheduled_for=past_time,
        )

        count = NotificationService.process_due_notifications(batch_size=50)
        self.assertEqual(count, 1)

        due_log.refresh_from_db()
        future_log.refresh_from_db()
        cancelled_log.refresh_from_db()

        self.assertEqual(due_log.status, DeliveryStatus.SENT)
        self.assertEqual(future_log.status, DeliveryStatus.SCHEDULED)
        self.assertEqual(cancelled_log.status, DeliveryStatus.CANCELLED)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["due@example.com"])

    def test_management_command_single_run(self):
        past_time = timezone.now() - datetime.timedelta(minutes=5)
        NotificationLog.objects.create(
            recipient="cmd@example.com",
            channel=ChannelChoices.EMAIL,
            subject="Cmd Subject",
            body="Cmd Body",
            status=DeliveryStatus.SCHEDULED,
            scheduled_for=past_time,
        )

        out = StringIO()
        call_command("process_scheduled_notifications", stdout=out)
        output = out.getvalue()

        self.assertIn("Processed 1 due scheduled notifications", output)
        self.assertEqual(len(mail.outbox), 1)
