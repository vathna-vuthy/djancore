from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.webhooks.models import WebhookDelivery, WebhookEndpoint, WebhookStatus

User = get_user_model()


class WebhookAPITests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="api_webhook_user@example.com",
            password="StrongPassword123!",
        )
        self.client.force_authenticate(user=self.user)

        self.endpoint = WebhookEndpoint.objects.create(
            user=self.user,
            target_url="https://api.example.com/events",
            description="My Primary Webhook",
            events=["user.registered", "iam.*"],
        )

    def test_list_webhook_endpoints(self):
        url = reverse("webhooks:endpoint-list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["success"])
        self.assertEqual(len(response.data["data"]), 1)
        self.assertEqual(response.data["data"][0]["id"], str(self.endpoint.id))
        self.assertNotIn("secret", response.data["data"][0])
        self.assertIn("masked_secret", response.data["data"][0])

    def test_create_webhook_endpoint(self):
        url = reverse("webhooks:endpoint-list")
        payload = {
            "target_url": "https://api.example.com/new-receiver",
            "description": "Payment Events",
            "events": ["billing.invoice.paid", "billing.subscription.*"],
            "timeout_seconds": 15,
            "max_retries": 5,
        }
        response = self.client.post(url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data["success"])
        # Full raw secret is returned on creation
        self.assertIn("secret", response.data["data"])
        self.assertTrue(response.data["data"]["secret"].startswith("djc_whsec_"))

        # Verify in database
        new_id = response.data["data"]["id"]
        created = WebhookEndpoint.objects.get(id=new_id)
        self.assertEqual(created.user, self.user)
        self.assertEqual(created.target_url, "https://api.example.com/new-receiver")
        self.assertEqual(created.max_retries, 5)

    def test_retrieve_webhook_endpoint_masks_secret(self):
        url = reverse("webhooks:endpoint-detail", kwargs={"pk": self.endpoint.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertNotIn("secret", response.data["data"])
        self.assertTrue(
            response.data["data"]["masked_secret"].startswith("djc_whsec_••••••••")
        )

    def test_partial_update_webhook_endpoint(self):
        url = reverse("webhooks:endpoint-detail", kwargs={"pk": self.endpoint.id})
        payload = {
            "description": "Updated Description",
            "is_active": False,
        }
        response = self.client.patch(url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.endpoint.refresh_from_db()
        self.assertEqual(self.endpoint.description, "Updated Description")
        self.assertFalse(self.endpoint.is_active)

    def test_destroy_and_restore_webhook_endpoint(self):
        url = reverse("webhooks:endpoint-detail", kwargs={"pk": self.endpoint.id})
        # Soft delete
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.endpoint.refresh_from_db()
        self.assertTrue(self.endpoint.is_deleted)

        # Restore
        restore_url = reverse(
            "webhooks:endpoint-restore", kwargs={"pk": self.endpoint.id}
        )
        restore_res = self.client.post(restore_url)
        self.assertEqual(restore_res.status_code, status.HTTP_200_OK)
        self.endpoint.refresh_from_db()
        self.assertFalse(self.endpoint.is_deleted)

    def test_rotate_signing_secret(self):
        url = reverse(
            "webhooks:endpoint-rotate-secret", kwargs={"pk": self.endpoint.id}
        )
        old_secret = self.endpoint.secret
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("secret", response.data["data"])
        self.assertNotEqual(old_secret, response.data["data"]["secret"])
        self.endpoint.refresh_from_db()
        self.assertEqual(self.endpoint.secret, response.data["data"]["secret"])

    @patch("urllib.request.urlopen")
    def test_ping_endpoint_action(self, mock_urlopen):
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.read.return_value = b'{"ok": true}'
        mock_response.headers = {}
        mock_urlopen.return_value.__enter__.return_value = mock_response

        url = reverse("webhooks:endpoint-ping", kwargs={"pk": self.endpoint.id})
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("delivery", response.data["data"])
        self.assertEqual(
            response.data["data"]["delivery"]["status"], WebhookStatus.SUCCESS
        )

    def test_delivery_logs_and_retry_action(self):
        delivery = WebhookDelivery.objects.create(
            endpoint=self.endpoint,
            event_type="iam.user.created",
            payload={"email": "newuser@example.com"},
            status=WebhookStatus.FAILED,
            error_message="502 Bad Gateway",
        )

        # List deliveries
        list_url = reverse("webhooks:delivery-list")
        list_res = self.client.get(list_url)
        self.assertEqual(list_res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(list_res.data["data"]), 1)

        # Retrieve delivery detail
        detail_url = reverse("webhooks:delivery-detail", kwargs={"pk": delivery.id})
        detail_res = self.client.get(detail_url)
        self.assertEqual(detail_res.status_code, status.HTTP_200_OK)
        self.assertEqual(detail_res.data["data"]["event_type"], "iam.user.created")

        # Retry delivery
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_response = MagicMock()
            mock_response.status = 200
            mock_response.read.return_value = b'{"success": true}'
            mock_response.headers = {}
            mock_urlopen.return_value.__enter__.return_value = mock_response

            retry_url = reverse("webhooks:delivery-retry", kwargs={"pk": delivery.id})
            retry_res = self.client.post(retry_url)
            self.assertEqual(retry_res.status_code, status.HTTP_200_OK)
            self.assertEqual(retry_res.data["data"]["status"], WebhookStatus.SUCCESS)
