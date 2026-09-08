import time
import urllib.error
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.webhooks.models import WebhookDelivery, WebhookEndpoint, WebhookStatus
from apps.webhooks.services import WebhookDispatcher, WebhookSignature

User = get_user_model()


class WebhookServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="dispatcher_test@example.com",
            password="StrongPassword123!",
        )
        self.endpoint = WebhookEndpoint.objects.create(
            user=self.user,
            target_url="https://webhook.site/mock-test",
            events=["order.*", "user.created"],
            secret="djc_whsec_secret1234567890abcdef",
        )

    def test_signature_generation_and_verification(self):
        payload_bytes = b'{"hello":"world"}'
        secret = "djc_whsec_my_test_secret"

        header, ts = WebhookSignature.generate_header(payload_bytes, secret)
        self.assertTrue(header.startswith(f"t={ts},v1="))

        # Verification succeeds with valid header
        self.assertTrue(
            WebhookSignature.verify_signature(payload_bytes, secret, header)
        )

        # Verification fails with tampered payload
        self.assertFalse(
            WebhookSignature.verify_signature(b'{"hello":"tampered"}', secret, header)
        )

        # Verification fails with tampered secret
        self.assertFalse(
            WebhookSignature.verify_signature(payload_bytes, "wrong_secret", header)
        )

        # Verification fails with expired timestamp
        old_header = f"t={int(time.time()) - 400},v1=fake_sig"
        self.assertFalse(
            WebhookSignature.verify_signature(
                payload_bytes, secret, old_header, tolerance_seconds=300
            )
        )

    @patch("urllib.request.urlopen")
    def test_deliver_webhook_success(self, mock_urlopen):
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.read.return_value = b'{"ok": true}'
        mock_response.headers = {"Content-Type": "application/json"}
        mock_urlopen.return_value.__enter__.return_value = mock_response

        delivery = WebhookDelivery.objects.create(
            endpoint=self.endpoint,
            event_type="user.created",
            payload={"user_id": 42, "email": "alice@example.com"},
        )

        result = WebhookDispatcher.deliver_webhook(delivery)
        self.assertEqual(result.status, WebhookStatus.SUCCESS)
        self.assertEqual(result.response_status_code, 200)
        self.assertIn("ok", result.response_body)
        self.assertIsNotNone(result.sent_at)
        self.assertIsNone(result.next_retry_at)

    @patch("urllib.request.urlopen")
    def test_deliver_webhook_http_error(self, mock_urlopen):
        http_err = urllib.error.HTTPError(
            url=self.endpoint.target_url,
            code=500,
            msg="Internal Server Error",
            hdrs=MagicMock(),
            fp=None,
        )
        mock_urlopen.side_effect = http_err

        delivery = WebhookDelivery.objects.create(
            endpoint=self.endpoint,
            event_type="user.created",
            payload={"user_id": 42},
        )

        result = WebhookDispatcher.deliver_webhook(delivery)
        self.assertEqual(result.status, WebhookStatus.FAILED)
        self.assertEqual(result.response_status_code, 500)
        self.assertIn("HTTP 500", result.error_message)
        self.assertIsNotNone(result.next_retry_at)

    @patch("urllib.request.urlopen")
    def test_deliver_webhook_network_timeout(self, mock_urlopen):
        mock_urlopen.side_effect = TimeoutError("Connection timed out")

        delivery = WebhookDelivery.objects.create(
            endpoint=self.endpoint,
            event_type="user.created",
            payload={"user_id": 42},
        )

        result = WebhookDispatcher.deliver_webhook(delivery)
        self.assertEqual(result.status, WebhookStatus.FAILED)
        self.assertIn("Network error", result.error_message)

    @patch("urllib.request.urlopen")
    def test_dispatch_event_routing(self, mock_urlopen):
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.read.return_value = b'{"received": true}'
        mock_response.headers = {}
        mock_urlopen.return_value.__enter__.return_value = mock_response

        # Create another endpoint that subscribes to unrelated event
        WebhookEndpoint.objects.create(
            user=self.user,
            target_url="https://api.example.com/unrelated",
            events=["billing.*"],
        )

        # Dispatch user.created event
        deliveries = WebhookDispatcher.dispatch_event(
            event_type="user.created",
            payload={"username": "alice"},
            user=self.user,
        )

        # Only self.endpoint should have received this delivery
        self.assertEqual(len(deliveries), 1)
        self.assertEqual(deliveries[0].endpoint, self.endpoint)
        self.assertEqual(deliveries[0].status, WebhookStatus.SUCCESS)

    @patch("urllib.request.urlopen")
    def test_ping_endpoint(self, mock_urlopen):
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.read.return_value = b'{"pong": true}'
        mock_response.headers = {}
        mock_urlopen.return_value.__enter__.return_value = mock_response

        delivery = WebhookDispatcher.ping_endpoint(self.endpoint)
        self.assertEqual(delivery.event_type, "system.ping")
        self.assertEqual(delivery.status, WebhookStatus.SUCCESS)

    @patch("urllib.request.urlopen")
    def test_retry_delivery(self, mock_urlopen):
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.read.return_value = b'{"ok": true}'
        mock_response.headers = {}
        mock_urlopen.return_value.__enter__.return_value = mock_response

        delivery = WebhookDelivery.objects.create(
            endpoint=self.endpoint,
            event_type="user.created",
            payload={"user_id": 42},
            status=WebhookStatus.FAILED,
            attempt=1,
        )

        retried = WebhookDispatcher.retry_delivery(delivery)
        self.assertEqual(retried.attempt, 2)
        self.assertEqual(retried.status, WebhookStatus.SUCCESS)
