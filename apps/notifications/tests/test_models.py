from django.test import TestCase

from apps.notifications.models import (
    ChannelChoices,
    DeliveryStatus,
    NotificationLog,
    NotificationTemplate,
)


class NotificationTemplateModelTest(TestCase):
    def setUp(self):
        self.template = NotificationTemplate.objects.create(
            code="MODEL_TEST",
            name="Model Test",
            channel=ChannelChoices.EMAIL,
            subject_template="Subject",
            body_template="Body",
        )

    def test_defaults(self):
        self.assertTrue(self.template.is_active)
        self.assertFalse(self.template.is_deleted)
        self.assertIsNone(self.template.deleted_at)
        self.assertIsNotNone(self.template.created_at)
        self.assertIsNotNone(self.template.updated_at)

    def test_default_channel_is_email(self):
        template = NotificationTemplate.objects.create(
            code="DEFAULT_CHANNEL", name="Default", body_template="Body"
        )
        self.assertEqual(template.channel, ChannelChoices.EMAIL)

    def test_str_representation(self):
        self.assertEqual(str(self.template), "[EMAIL] Model Test (MODEL_TEST)")

    def test_code_is_unique(self):
        from django.db import IntegrityError

        with self.assertRaises(IntegrityError):
            NotificationTemplate.objects.create(
                code="MODEL_TEST",
                name="Duplicate",
                body_template="Body",
            )

    def test_soft_delete_hides_from_default_manager(self):
        self.template.delete()
        self.assertEqual(NotificationTemplate.objects.count(), 0)
        self.assertEqual(NotificationTemplate.all_objects.count(), 1)

        self.template.restore()
        self.assertEqual(NotificationTemplate.objects.count(), 1)

    def test_ordering_by_channel_then_code(self):
        NotificationTemplate.objects.create(
            code="AAA", name="A", channel=ChannelChoices.TELEGRAM, body_template="B"
        )
        NotificationTemplate.objects.create(
            code="ZZZ", name="Z", channel=ChannelChoices.EMAIL, body_template="B"
        )
        codes = list(NotificationTemplate.objects.values_list("code", flat=True))
        self.assertEqual(codes, ["MODEL_TEST", "ZZZ", "AAA"])


class NotificationLogModelTest(TestCase):
    def setUp(self):
        self.template = NotificationTemplate.objects.create(
            code="LOG_TMPL", name="Log Tmpl", body_template="Body"
        )
        self.log = NotificationLog.objects.create(
            recipient="log@example.com",
            channel=ChannelChoices.EMAIL,
            subject="Log Subject",
            body="Log Body",
            template=self.template,
            payload={"key": "value"},
        )

    def test_defaults(self):
        self.assertEqual(self.log.status, DeliveryStatus.PENDING)
        self.assertEqual(self.log.payload, {"key": "value"})
        self.assertIsNone(self.log.scheduled_for)
        self.assertIsNone(self.log.sent_at)
        self.assertIsNone(self.log.user)
        self.assertEqual(self.log.error_message, "")
        self.assertFalse(self.log.is_deleted)

    def test_str_representation(self):
        self.assertEqual(str(self.log), "[email] to log@example.com (PENDING)")

    def test_ordering_newest_first(self):
        newer = NotificationLog.objects.create(
            recipient="newer@example.com",
            channel=ChannelChoices.EMAIL,
            body="Newer",
        )
        logs = list(NotificationLog.objects.all())
        self.assertEqual(logs[0].pk, newer.pk)
        self.assertEqual(logs[1].pk, self.log.pk)

    def test_hard_delete_template_sets_log_template_null(self):
        self.template.hard_delete()
        self.log.refresh_from_db()
        self.assertIsNone(self.log.template)

    def test_soft_delete_template_keeps_log_template(self):
        self.template.delete()
        self.log.refresh_from_db()
        self.assertIsNotNone(self.log.template)

    def test_soft_deleted_log_hidden_from_default_manager(self):
        self.log.delete()
        self.assertEqual(NotificationLog.objects.count(), 0)
        self.assertEqual(NotificationLog.all_objects.count(), 1)
