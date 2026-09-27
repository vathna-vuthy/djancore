from django.test import TestCase

from apps.notifications.models import (
    ChannelChoices,
    DeliveryStatus,
    NotificationLog,
    NotificationTemplate,
)
from apps.notifications.serializers import (
    NotificationLogSerializer,
    NotificationTemplateSerializer,
    RescheduleNotificationSerializer,
    SendNotificationSerializer,
    SendTemplateNotificationSerializer,
)


class SendNotificationSerializerTest(TestCase):
    def valid_payload(self, **overrides):
        payload = {
            "recipient": "a@example.com",
            "body": "Hello",
        }
        payload.update(overrides)
        return payload

    def test_valid_payload(self):
        serializer = SendNotificationSerializer(data=self.valid_payload())
        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.validated_data["channel"], ChannelChoices.EMAIL)
        self.assertEqual(serializer.validated_data["subject"], "")
        self.assertEqual(serializer.validated_data["context"], {})
        self.assertIsNone(serializer.validated_data["scheduled_for"])

    def test_missing_recipient(self):
        payload = self.valid_payload()
        del payload["recipient"]
        serializer = SendNotificationSerializer(data=payload)
        self.assertFalse(serializer.is_valid())
        self.assertIn("recipient", serializer.errors)

    def test_missing_body(self):
        payload = self.valid_payload()
        del payload["body"]
        serializer = SendNotificationSerializer(data=payload)
        self.assertFalse(serializer.is_valid())
        self.assertIn("body", serializer.errors)

    def test_invalid_channel(self):
        serializer = SendNotificationSerializer(
            data=self.valid_payload(channel="carrier-pigeon")
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn("channel", serializer.errors)

    def test_invalid_scheduled_for(self):
        serializer = SendNotificationSerializer(
            data=self.valid_payload(scheduled_for="not-a-date")
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn("scheduled_for", serializer.errors)

    def test_context_must_be_dict(self):
        serializer = SendNotificationSerializer(
            data=self.valid_payload(context="not-a-dict")
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn("context", serializer.errors)


class SendTemplateNotificationSerializerTest(TestCase):
    def test_valid_payload(self):
        serializer = SendTemplateNotificationSerializer(
            data={"recipient": "a@example.com", "template_code": "WELCOME"}
        )
        self.assertTrue(serializer.is_valid())

    def test_missing_template_code(self):
        serializer = SendTemplateNotificationSerializer(
            data={"recipient": "a@example.com"}
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn("template_code", serializer.errors)

    def test_missing_recipient(self):
        serializer = SendTemplateNotificationSerializer(
            data={"template_code": "WELCOME"}
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn("recipient", serializer.errors)


class RescheduleNotificationSerializerTest(TestCase):
    def test_missing_scheduled_for(self):
        serializer = RescheduleNotificationSerializer(data={})
        self.assertFalse(serializer.is_valid())
        self.assertIn("scheduled_for", serializer.errors)

    def test_valid_payload(self):
        serializer = RescheduleNotificationSerializer(
            data={"scheduled_for": "2030-01-01T00:00:00Z"}
        )
        self.assertTrue(serializer.is_valid())


class NotificationTemplateSerializerTest(TestCase):
    def test_valid_payload(self):
        serializer = NotificationTemplateSerializer(
            data={
                "code": "SER_TMPL",
                "name": "Serializer Template",
                "channel": "email",
                "subject_template": "Hi",
                "body_template": "Body",
            }
        )
        self.assertTrue(serializer.is_valid())
        template = serializer.save()
        self.assertTrue(template.is_active)

    def test_duplicate_code_rejected(self):
        NotificationTemplate.objects.create(
            code="DUP_CODE", name="Existing", body_template="Body"
        )
        serializer = NotificationTemplateSerializer(
            data={
                "code": "DUP_CODE",
                "name": "Another",
                "body_template": "Body",
            }
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn("code", serializer.errors)

    def test_invalid_channel_rejected(self):
        serializer = NotificationTemplateSerializer(
            data={
                "code": "BAD_CH",
                "name": "Bad",
                "channel": "pigeon",
                "body_template": "Body",
            }
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn("channel", serializer.errors)

    def test_missing_body_template_rejected(self):
        serializer = NotificationTemplateSerializer(
            data={"code": "NO_BODY", "name": "No Body"}
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn("body_template", serializer.errors)

    def test_read_only_fields_ignored(self):
        serializer = NotificationTemplateSerializer(
            data={
                "code": "RO_TMPL",
                "name": "Read Only",
                "body_template": "Body",
                "is_deleted": True,
                "created_at": "2000-01-01T00:00:00Z",
            }
        )
        self.assertTrue(serializer.is_valid())
        template = serializer.save()
        self.assertFalse(template.is_deleted)


class NotificationLogSerializerTest(TestCase):
    def setUp(self):
        self.template = NotificationTemplate.objects.create(
            code="SER_LOG_TMPL", name="Log Tmpl", body_template="Body"
        )

    def test_template_code_rendered(self):
        log = NotificationLog.objects.create(
            recipient="a@example.com",
            channel=ChannelChoices.EMAIL,
            body="Body",
            template=self.template,
        )
        data = NotificationLogSerializer(log).data
        self.assertEqual(data["template_code"], "SER_LOG_TMPL")

    def test_template_code_null_without_template(self):
        log = NotificationLog.objects.create(
            recipient="a@example.com",
            channel=ChannelChoices.EMAIL,
            body="Body",
        )
        data = NotificationLogSerializer(log).data
        self.assertIsNone(data["template_code"])

    def test_status_is_read_only(self):
        log = NotificationLog.objects.create(
            recipient="a@example.com",
            channel=ChannelChoices.EMAIL,
            body="Body",
            status=DeliveryStatus.PENDING,
        )
        serializer = NotificationLogSerializer(
            log, data={"status": DeliveryStatus.SENT}, partial=True
        )
        self.assertTrue(serializer.is_valid())
        serializer.save()
        log.refresh_from_db()
        self.assertEqual(log.status, DeliveryStatus.PENDING)
