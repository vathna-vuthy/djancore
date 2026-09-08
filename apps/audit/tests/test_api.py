from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.audit.models import AuditAction, AuditLog

User = get_user_model()


class AuditAPITests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="user_auditee@example.com",
            password="StrongPassword123!",
        )
        self.staff_user = User.objects.create_user(
            email="staff_auditor@example.com",
            password="StrongPassword123!",
            is_staff=True,
        )

        # Create logs
        self.user_log = AuditLog.objects.create(
            actor=self.user,
            actor_repr=self.user.email,
            action=AuditAction.LOGIN,
            resource_type="apps.iam.User",
            resource_id=str(self.user.id),
            resource_repr=self.user.email,
        )
        self.staff_log = AuditLog.objects.create(
            actor=self.staff_user,
            actor_repr=self.staff_user.email,
            action=AuditAction.CONFIG_CHANGE,
            resource_type="apps.system_config.SystemConfig",
            resource_id="SITE_NAME",
            resource_repr="SITE_NAME",
        )

    def test_list_logs_user_scoping(self):
        self.client.force_authenticate(user=self.user)
        url = reverse("audit:log-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["success"])
        # Regular user only sees their own 1 log
        self.assertEqual(len(response.data["data"]), 1)
        self.assertEqual(response.data["data"][0]["id"], str(self.user_log.id))
        self.assertIn("message", response.data["data"][0])

    def test_list_logs_staff_sees_all(self):
        self.client.force_authenticate(user=self.staff_user)
        url = reverse("audit:log-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["success"])
        # Staff sees all 2 logs
        self.assertEqual(len(response.data["data"]), 2)

    def test_filter_logs_by_action(self):
        self.client.force_authenticate(user=self.staff_user)
        url = reverse("audit:log-list")
        response = self.client.get(url, {"action": "CONFIG_CHANGE"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["data"]), 1)
        self.assertEqual(response.data["data"][0]["action"], "CONFIG_CHANGE")

    def test_retrieve_log_detail(self):
        self.client.force_authenticate(user=self.user)
        url = reverse("audit:log-detail", kwargs={"pk": self.user_log.id})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["data"]["id"], str(self.user_log.id))
        self.assertEqual(
            response.data["data"]["message"],
            "Actor user_auditee@example.com logged in.",
        )

    def test_disallow_mutations_on_audit_logs(self):
        self.client.force_authenticate(user=self.staff_user)
        url = reverse("audit:log-list")

        # POST is not allowed
        post_res = self.client.post(url, {"action": "HACK"}, format="json")
        self.assertEqual(post_res.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

        # DELETE is not allowed
        detail_url = reverse("audit:log-detail", kwargs={"pk": self.user_log.id})
        del_res = self.client.delete(detail_url)
        self.assertEqual(del_res.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
