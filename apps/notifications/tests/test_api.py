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


class NotificationLogAPITest(APITestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            email="owner@example.com", password="password123"
        )
        self.other = User.objects.create_user(
            email="other@example.com", password="password123"
        )
        self.staff = User.objects.create_user(
            email="staff@example.com",
            password="password123",
            is_staff=True,
        )

        self.template = NotificationTemplate.objects.create(
            code="LOG_TMPL",
            name="Log Template",
            channel=ChannelChoices.EMAIL,
            subject_template="Hi",
            body_template="Hello {{ name }}",
        )

        self.owner_log = NotificationLog.objects.create(
            recipient="owner@example.com",
            channel=ChannelChoices.EMAIL,
            subject="Owner Subject",
            body="Owner Body",
            status=DeliveryStatus.SENT,
            template=self.template,
            user=self.owner,
        )
        self.other_log = NotificationLog.objects.create(
            recipient="other@example.com",
            channel=ChannelChoices.EMAIL,
            subject="Other Subject",
            body="Other Body",
            status=DeliveryStatus.FAILED,
            error_message="boom",
            user=self.other,
        )

    def test_list_logs_scoped_to_user(self):
        self.client.force_authenticate(user=self.owner)
        response = self.client.get(reverse("notifications:log-list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data["data"]
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["id"], str(self.owner_log.pk))

    def test_staff_sees_all_logs(self):
        self.client.force_authenticate(user=self.staff)
        response = self.client.get(reverse("notifications:log-list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["meta"]["total_count"], 2)

    def test_retrieve_own_log_detail(self):
        self.client.force_authenticate(user=self.owner)
        url = reverse("notifications:log-detail", kwargs={"pk": self.owner_log.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["recipient"], "owner@example.com")
        self.assertEqual(response.data["template_code"], "LOG_TMPL")

    def test_retrieve_other_user_log_returns_404(self):
        self.client.force_authenticate(user=self.owner)
        url = reverse("notifications:log-detail", kwargs={"pk": self.other_log.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_logs_require_authentication(self):
        self.client.force_authenticate(user=None)
        response = self.client.get(reverse("notifications:log-list"))
        self.assertIn(
            response.status_code,
            (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN),
        )

    def test_filter_logs_by_status(self):
        self.client.force_authenticate(user=self.staff)
        response = self.client.get(
            reverse("notifications:log-list"), {"status": "FAILED"}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["meta"]["total_count"], 1)
        self.assertEqual(response.data["data"][0]["status"], DeliveryStatus.FAILED)

    def test_search_logs_by_recipient(self):
        self.client.force_authenticate(user=self.staff)
        response = self.client.get(
            reverse("notifications:log-list"), {"search": "other@example.com"}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["meta"]["total_count"], 1)
        self.assertEqual(response.data["data"][0]["recipient"], "other@example.com")


class NotificationAPIErrorTest(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="erroruser@example.com", password="password123"
        )
        self.client.force_authenticate(user=self.user)

        self.active_template = NotificationTemplate.objects.create(
            code="ACTIVE_TMPL",
            name="Active",
            channel=ChannelChoices.EMAIL,
            subject_template="Subj",
            body_template="Body",
        )
        self.inactive_template = NotificationTemplate.objects.create(
            code="INACTIVE_TMPL",
            name="Inactive",
            channel=ChannelChoices.EMAIL,
            subject_template="Subj",
            body_template="Body",
            is_active=False,
        )

    def test_send_invalid_channel_returns_400(self):
        payload = {
            "recipient": "a@example.com",
            "channel": "pigeon",
            "body": "Hello",
        }
        response = self.client.post(
            reverse("notifications:send"), payload, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("channel", response.data["errors"])

    def test_send_missing_body_returns_400(self):
        payload = {"recipient": "a@example.com", "channel": "email"}
        response = self.client.post(
            reverse("notifications:send"), payload, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("body", response.data["errors"])

    def test_send_requires_authentication(self):
        self.client.force_authenticate(user=None)
        payload = {
            "recipient": "a@example.com",
            "channel": "email",
            "body": "Hello",
        }
        response = self.client.post(
            reverse("notifications:send"), payload, format="json"
        )
        self.assertIn(
            response.status_code,
            (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN),
        )

    def test_send_template_unknown_code_returns_400(self):
        payload = {"recipient": "a@example.com", "template_code": "NOPE"}
        response = self.client.post(
            reverse("notifications:send-template"), payload, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)

    def test_send_template_inactive_returns_400(self):
        payload = {
            "recipient": "a@example.com",
            "template_code": "INACTIVE_TMPL",
        }
        response = self.client.post(
            reverse("notifications:send-template"), payload, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("INACTIVE_TMPL", response.data["error"])

    def test_cancel_non_scheduled_returns_400(self):
        log = NotificationLog.objects.create(
            recipient="a@example.com",
            channel=ChannelChoices.EMAIL,
            subject="Sent",
            body="Body",
            status=DeliveryStatus.SENT,
            user=self.user,
        )
        url = reverse("notifications:log-cancel", kwargs={"pk": log.pk})
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(response.data["success"])

    def test_cancel_unknown_log_returns_404(self):
        url = reverse(
            "notifications:log-cancel",
            kwargs={"pk": "00000000-0000-0000-0000-000000000000"},
        )
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_reschedule_missing_field_returns_400(self):
        log = NotificationLog.objects.create(
            recipient="a@example.com",
            channel=ChannelChoices.EMAIL,
            subject="Sched",
            body="Body",
            status=DeliveryStatus.SCHEDULED,
            scheduled_for=timezone.now() + datetime.timedelta(days=1),
            user=self.user,
        )
        url = reverse("notifications:log-reschedule", kwargs={"pk": log.pk})
        response = self.client.post(url, {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_reschedule_in_past_returns_400(self):
        log = NotificationLog.objects.create(
            recipient="a@example.com",
            channel=ChannelChoices.EMAIL,
            subject="Sched",
            body="Body",
            status=DeliveryStatus.SCHEDULED,
            scheduled_for=timezone.now() + datetime.timedelta(days=1),
            user=self.user,
        )
        url = reverse("notifications:log-reschedule", kwargs={"pk": log.pk})
        past = (timezone.now() - datetime.timedelta(days=1)).isoformat()
        response = self.client.post(url, {"scheduled_for": past}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_reschedule_unknown_log_returns_404(self):
        url = reverse(
            "notifications:log-reschedule",
            kwargs={"pk": "00000000-0000-0000-0000-000000000000"},
        )
        future = (timezone.now() + datetime.timedelta(days=1)).isoformat()
        response = self.client.post(url, {"scheduled_for": future}, format="json")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_retry_unknown_log_returns_404(self):
        url = reverse(
            "notifications:log-retry",
            kwargs={"pk": "00000000-0000-0000-0000-000000000000"},
        )
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class NotificationTemplateAPITest(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            email="tmpladmin@example.com", password="password123"
        )
        self.normal = User.objects.create_user(
            email="tmpluser@example.com", password="password123"
        )
        self.template = NotificationTemplate.objects.create(
            code="CRUD_TMPL",
            name="Crud Template",
            channel=ChannelChoices.EMAIL,
            subject_template="Hello",
            body_template="World",
        )

    def test_template_list_admin_required(self):
        self.client.force_authenticate(user=self.normal)
        response = self.client.get(reverse("notifications:template-list"))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        self.client.force_authenticate(user=self.admin)
        response = self.client.get(reverse("notifications:template-list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["meta"]["total_count"], 1)

    def test_template_retrieve(self):
        self.client.force_authenticate(user=self.admin)
        url = reverse("notifications:template-detail", kwargs={"pk": self.template.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["code"], "CRUD_TMPL")

    def test_template_update(self):
        self.client.force_authenticate(user=self.admin)
        url = reverse("notifications:template-detail", kwargs={"pk": self.template.pk})
        response = self.client.put(
            url,
            {
                "code": "CRUD_TMPL",
                "name": "Updated Name",
                "channel": "email",
                "subject_template": "New Subject",
                "body_template": "New Body",
                "is_active": False,
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.template.refresh_from_db()
        self.assertEqual(self.template.name, "Updated Name")
        self.assertFalse(self.template.is_active)

    def test_template_partial_update(self):
        self.client.force_authenticate(user=self.admin)
        url = reverse("notifications:template-detail", kwargs={"pk": self.template.pk})
        response = self.client.patch(url, {"name": "Patched"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.template.refresh_from_db()
        self.assertEqual(self.template.name, "Patched")
        self.assertEqual(self.template.body_template, "World")

    def test_template_destroy_soft_deletes(self):
        self.client.force_authenticate(user=self.admin)
        url = reverse("notifications:template-detail", kwargs={"pk": self.template.pk})
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        self.template.refresh_from_db()
        self.assertTrue(self.template.is_deleted)
        self.assertEqual(NotificationTemplate.objects.count(), 0)

    def test_template_duplicate_code_returns_400(self):
        self.client.force_authenticate(user=self.admin)
        payload = {
            "code": "CRUD_TMPL",
            "name": "Duplicate",
            "channel": "email",
            "subject_template": "S",
            "body_template": "B",
        }
        response = self.client.post(
            reverse("notifications:template-list"), payload, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("code", response.data["errors"])

    def test_template_create_requires_admin(self):
        self.client.force_authenticate(user=self.normal)
        payload = {
            "code": "FORBIDDEN_TMPL",
            "name": "Nope",
            "channel": "email",
            "subject_template": "S",
            "body_template": "B",
        }
        response = self.client.post(
            reverse("notifications:template-list"), payload, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(NotificationTemplate.objects.count(), 1)
