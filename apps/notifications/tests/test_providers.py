import json
from unittest.mock import MagicMock, patch

from django.core import mail
from django.test import TestCase, override_settings

from apps.notifications.providers.base import (
    BaseNotificationProvider,
    NotificationResult,
)
from apps.notifications.providers.email import EmailNotificationProvider
from apps.notifications.providers.registry import ProviderRegistry
from apps.notifications.providers.telegram import TelegramNotificationProvider


class EmailNotificationProviderTest(TestCase):
    def setUp(self):
        self.provider = EmailNotificationProvider()

    def test_email_send_success(self):
        result = self.provider.send(
            recipient="test@example.com",
            subject="Welcome!",
            body="Hello world",
        )
        self.assertTrue(result.success)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].subject, "Welcome!")
        self.assertEqual(mail.outbox[0].to, ["test@example.com"])
        self.assertEqual(mail.outbox[0].body, "Hello world")

    @patch(
        "django.core.mail.EmailMultiAlternatives.send",
        side_effect=Exception("SMTP connection failed"),
    )
    def test_email_send_failure(self, mock_send):
        result = self.provider.send(
            recipient="test@example.com",
            subject="Fail Test",
            body="Fail Body",
        )
        self.assertFalse(result.success)
        self.assertIn("SMTP connection failed", result.error)

    def test_email_is_configured(self):
        self.assertTrue(self.provider.is_configured())

    def test_email_send_uses_system_config(self):
        from apps.system_config.services import set_config

        set_config(
            "DEFAULT_FROM_EMAIL", "system-config-sender@example.com", group="email"
        )
        result = self.provider.send(
            recipient="test@example.com",
            subject="Dynamic Config Test",
            body="Body content",
        )
        self.assertTrue(result.success)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].from_email, "system-config-sender@example.com")


class TelegramNotificationProviderTest(TestCase):
    def setUp(self):
        self.provider = TelegramNotificationProvider()

    @override_settings(TELEGRAM_BOT_TOKEN="mock-token-123")
    @patch("urllib.request.urlopen")
    def test_telegram_send_success(self, mock_urlopen):
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.read.return_value = json.dumps({"ok": True}).encode("utf-8")
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response

        result = self.provider.send(
            recipient="12345678",
            subject="",
            body="Hello from Telegram",
        )
        self.assertTrue(result.success)
        self.assertTrue(mock_urlopen.called)

    @override_settings(TELEGRAM_BOT_TOKEN="")
    def test_telegram_send_not_configured(self):
        result = self.provider.send(
            recipient="12345678",
            subject="",
            body="Hello",
        )
        self.assertFalse(result.success)
        self.assertIn("TELEGRAM_BOT_TOKEN is not configured", result.error)

    @patch("urllib.request.urlopen")
    def test_telegram_send_uses_system_config(self, mock_urlopen):
        from apps.system_config.services import set_config

        set_config(
            "TELEGRAM_BOT_TOKEN",
            "sys-config-token-456",
            group="telegram",
            is_secret=True,
        )
        set_config("TELEGRAM_API_URL", "https://custom.telegram.api", group="telegram")

        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.read.return_value = json.dumps(
            {"ok": True, "result": {"message_id": 42}}
        ).encode("utf-8")
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response

        result = self.provider.send(
            recipient="12345678",
            subject="",
            body="System config body",
        )
        self.assertTrue(result.success)
        self.assertEqual(result.provider_message_id, "42")
        self.assertTrue(self.provider.is_configured())

        # Verify request URL used custom api url and token
        called_req = mock_urlopen.call_args[0][0]
        self.assertIn(
            "https://custom.telegram.api/botsys-config-token-456/sendMessage",
            called_req.full_url,
        )


class ProviderRegistryTest(TestCase):
    def test_provider_registry_lookup(self):
        email_provider = ProviderRegistry.get("email")
        self.assertIsNotNone(email_provider)
        self.assertIsInstance(email_provider, EmailNotificationProvider)

        telegram_provider = ProviderRegistry.get("telegram")
        self.assertIsNotNone(telegram_provider)
        self.assertIsInstance(telegram_provider, TelegramNotificationProvider)

        none_provider = ProviderRegistry.get("sms")
        self.assertIsNone(none_provider)

    def test_provider_registry_list(self):
        providers = ProviderRegistry.list_providers()
        self.assertIn("email", providers)
        self.assertIn("telegram", providers)
        self.assertIn("configured", providers["email"])
        self.assertIn("class_name", providers["email"])

    def test_custom_provider_registration(self):
        class MockProvider(BaseNotificationProvider):
            def send(self, recipient, subject, body, context=None, **kwargs):
                return NotificationResult(success=True)

            def is_configured(self):
                return True

        ProviderRegistry.register("mock_channel", MockProvider)
        provider = ProviderRegistry.get("mock_channel")
        self.assertIsNotNone(provider)
        assert provider is not None
        self.assertTrue(provider.is_configured())
