import datetime

from django.contrib.auth import get_user_model
from django.core import mail
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.notifications.models import (
    ChannelChoices,
    DeliveryStatus,
    NotificationLog,
    NotificationTemplate,
)

User = get_user_model()


class NotificationAPITest(APITestCase):
    def setUp(self):
        self.admin_user = User.objects.create_superuser(
            email="admin@example.com",
            password="adminpassword123",
        )
        self.normal_user = User.objects.create_user(
            email="normal@example.com",
            password="userpassword123",
        )
        self.client.force_authenticate(user=self.normal_user)

        self.template = NotificationTemplate.objects.create(
            code="ORDER_CONFIRMATION",
            name="Order Confirmation",
            channel=ChannelChoices.EMAIL,
            subject_template="Order #{{ order_id }} Confirmed",
            body_template="Hi {{ name }}, your order #{{ order_id }} is on its way!",
        )

    def test_send_direct_notification(self):
        url = reverse("notifications:send")
        payload = {
            "recipient": "customer@example.com",
            "channel": "email",
            "subject": "Direct Test",
            "body": "This is a direct test.",
        }
        response = self.client.post(url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["recipient"], "customer@example.com")
        self.assertEqual(response.data["status"], DeliveryStatus.SENT)
        self.assertEqual(len(mail.outbox), 1)

    def test_send_scheduled_direct_notification(self):
        url = reverse("notifications:send")
        future_time = (timezone.now() + datetime.timedelta(days=1)).isoformat()
        payload = {
            "recipient": "customer@example.com",
            "channel": "email",
            "subject": "Scheduled Direct",
            "body": "This will arrive tomorrow.",
            "scheduled_for": future_time,
        }
        response = self.client.post(url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["status"], DeliveryStatus.SCHEDULED)
        self.assertEqual(len(mail.outbox), 0)

    def test_send_template_notification(self):
        url = reverse("notifications:send-template")
        payload = {
            "recipient": "customer@example.com",
            "template_code": "ORDER_CONFIRMATION",
            "context": {"order_id": "999", "name": "Alice"},
        }
        response = self.client.post(url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["subject"], "Order #999 Confirmed")
        self.assertIn("Alice", response.data["body"])
        self.assertEqual(len(mail.outbox), 1)

    def test_list_providers(self):
        url = reverse("notifications:providers")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        assert isinstance(response.data, list)
        channels = [p["channel"] for p in response.data]
        self.assertIn("email", channels)
        self.assertIn("telegram", channels)

    def test_template_crud_admin_required(self):
        url = reverse("notifications:template-list")
        payload = {
            "code": "NEW_TMPL",
            "name": "New Template",
            "channel": "email",
            "subject_template": "Hello",
            "body_template": "World",
        }
        # Normal user forbidden
        response = self.client.post(url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        # Admin user allowed
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.post(url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["code"], "NEW_TMPL")

    def test_template_restore(self):
        self.client.force_authenticate(user=self.admin_user)
        self.template.delete()
        self.assertTrue(self.template.is_deleted)

        url = reverse("notifications:template-restore", kwargs={"pk": self.template.pk})
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.template.refresh_from_db()
        self.assertFalse(self.template.is_deleted)

    def test_cancel_scheduled_api(self):
        future_time = timezone.now() + datetime.timedelta(days=1)
        log = NotificationLog.objects.create(
            recipient="test@example.com",
            channel=ChannelChoices.EMAIL,
            subject="Sched",
            body="Sched",
            status=DeliveryStatus.SCHEDULED,
            scheduled_for=future_time,
            user=self.normal_user,
        )

        url = reverse("notifications:log-cancel", kwargs={"pk": log.pk})
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        log.refresh_from_db()
        self.assertEqual(log.status, DeliveryStatus.CANCELLED)

    def test_reschedule_api(self):
        future_time1 = timezone.now() + datetime.timedelta(days=1)
        future_time2 = timezone.now() + datetime.timedelta(days=2)
        log = NotificationLog.objects.create(
            recipient="test@example.com",
            channel=ChannelChoices.EMAIL,
            subject="Sched",
            body="Sched",
            status=DeliveryStatus.SCHEDULED,
            scheduled_for=future_time1,
            user=self.normal_user,
        )

        url = reverse("notifications:log-reschedule", kwargs={"pk": log.pk})
        response = self.client.post(
            url, {"scheduled_for": future_time2.isoformat()}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        log.refresh_from_db()
        assert log.scheduled_for is not None
        self.assertEqual(log.scheduled_for.date(), future_time2.date())

    def test_retry_api(self):
        log = NotificationLog.objects.create(
            recipient="test@example.com",
            channel=ChannelChoices.EMAIL,
            subject="Retry",
            body="Retry",
            status=DeliveryStatus.FAILED,
            error_message="Network Error",
            user=self.normal_user,
        )

        url = reverse("notifications:log-retry", kwargs={"pk": log.pk})
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        log.refresh_from_db()
        self.assertEqual(log.status, DeliveryStatus.SENT)
        self.assertEqual(len(mail.outbox), 1)
