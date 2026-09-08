from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.webhooks.models import WebhookDelivery, WebhookEndpoint, WebhookStatus

User = get_user_model()


class WebhookModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="webhook_tester@example.com",
            password="StrongPassword123!",
        )

    def test_webhook_endpoint_creation_and_secret(self):
        endpoint = WebhookEndpoint.objects.create(
            user=self.user,
            target_url="https://api.example.com/webhook",
            description="Production Webhook",
            events=["user.created", "order.*"],
        )
        self.assertTrue(endpoint.secret.startswith("djc_whsec_"))
        self.assertTrue(endpoint.is_active)
        self.assertIn("djc_whsec_••••••••", endpoint.masked_secret)
        self.assertTrue(endpoint.masked_secret.endswith(endpoint.secret[-4:]))

    def test_webhook_secret_rotation(self):
        endpoint = WebhookEndpoint.objects.create(
            user=self.user,
            target_url="https://api.example.com/webhook",
        )
        old_secret = endpoint.secret
        new_secret = endpoint.rotate_secret()
        self.assertNotEqual(old_secret, new_secret)
        self.assertEqual(endpoint.secret, new_secret)

    def test_matches_event(self):
        # Wildcard endpoint
        all_events_ep = WebhookEndpoint.objects.create(
            user=self.user,
            target_url="https://api.example.com/all",
            events=["*"],
        )
        self.assertTrue(all_events_ep.matches_event("user.created"))
        self.assertTrue(all_events_ep.matches_event("order.refunded"))

        # Specific and pattern endpoint
        scoped_ep = WebhookEndpoint.objects.create(
            user=self.user,
            target_url="https://api.example.com/scoped",
            events=["user.created", "order.*"],
        )
        self.assertTrue(scoped_ep.matches_event("user.created"))
        self.assertTrue(scoped_ep.matches_event("order.created"))
        self.assertTrue(scoped_ep.matches_event("order.completed"))
        self.assertFalse(scoped_ep.matches_event("user.updated"))
        self.assertFalse(scoped_ep.matches_event("billing.invoice"))

    def test_webhook_endpoint_soft_delete_and_restore(self):
        endpoint = WebhookEndpoint.objects.create(
            user=self.user,
            target_url="https://api.example.com/webhook",
        )
        endpoint.delete()
        self.assertFalse(WebhookEndpoint.objects.filter(id=endpoint.id).exists())
        self.assertTrue(WebhookEndpoint.all_objects.filter(id=endpoint.id).exists())

        endpoint.restore()
        self.assertTrue(WebhookEndpoint.objects.filter(id=endpoint.id).exists())

    def test_webhook_delivery_state_transitions(self):
        endpoint = WebhookEndpoint.objects.create(
            user=self.user,
            target_url="https://api.example.com/webhook",
            max_retries=3,
        )
        delivery = WebhookDelivery.objects.create(
            endpoint=endpoint,
            event_type="user.created",
            payload={"user_id": 123},
        )
        self.assertEqual(delivery.status, WebhookStatus.PENDING)

        # Test mark failure with retry delay
        delivery.mark_failure(
            error_message="Gateway Timeout",
            status_code=504,
            retry_delay_seconds=30,
        )
        self.assertEqual(delivery.status, WebhookStatus.FAILED)
        self.assertEqual(delivery.response_status_code, 504)
        self.assertIsNotNone(delivery.next_retry_at)

        # Test mark success
        delivery.mark_success(
            status_code=200,
            headers={"Content-Type": "application/json"},
            body='{"received": true}',
            duration_ms=45,
        )
        self.assertEqual(delivery.status, WebhookStatus.SUCCESS)
        self.assertEqual(delivery.response_status_code, 200)
        self.assertEqual(delivery.duration_ms, 45)
        self.assertIsNone(delivery.next_retry_at)
