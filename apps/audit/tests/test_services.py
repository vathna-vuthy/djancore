from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.audit.context import set_audit_context
from apps.audit.models import AuditAction
from apps.audit.services import AuditService

User = get_user_model()


class AuditServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="service_auditor@example.com",
            password="StrongPassword123!",
        )

    def test_record_with_explicit_params(self):
        log = AuditService.record(
            action=AuditAction.PASSWORD_CHANGE,
            resource_type="apps.iam.User",
            resource_id=str(self.user.id),
            resource_repr=self.user.email,
            actor=self.user,
            actor_repr=self.user.email,
            ip_address="198.51.100.2",
            user_agent="TestAgent/1.0",
            request_id="req-999",
        )
        self.assertEqual(log.action, AuditAction.PASSWORD_CHANGE)
        self.assertEqual(log.actor, self.user)
        self.assertEqual(log.ip_address, "198.51.100.2")
        self.assertEqual(log.request_id, "req-999")
        self.assertIn("changed password for", log.message)

    def test_record_with_context_fallback(self):
        set_audit_context(
            actor=self.user,
            actor_repr="context_user@example.com",
            ip_address="10.0.0.1",
            user_agent="ContextAgent",
            request_id="req-ctx-77",
        )

        log = AuditService.record(
            action=AuditAction.CONFIG_CHANGE,
            resource_type="apps.system_config.SystemConfig",
            resource_id="MAX_UPLOADS",
            resource_repr="MAX_UPLOADS",
        )
        self.assertEqual(log.actor, self.user)
        self.assertEqual(log.actor_repr, "context_user@example.com")
        self.assertEqual(log.ip_address, "10.0.0.1")
        self.assertEqual(log.request_id, "req-ctx-77")

    def test_calculate_diff_sensitive_field_masking(self):
        old_data = {
            "username": "alice",
            "password": "old_hashed_password_123",
            "api_key": "djc_live_secret123",
            "is_active": True,
        }
        new_data = {
            "username": "alice_renamed",
            "password": "new_hashed_password_456",
            "api_key": "djc_live_secret999",
            "is_active": False,
        }

        diff = AuditService.calculate_diff(old_data, new_data)

        # Standard field diffs
        self.assertEqual(diff["username"], {"old": "alice", "new": "alice_renamed"})
        self.assertEqual(diff["is_active"], {"old": True, "new": False})

        # Sensitive fields must be masked
        self.assertEqual(diff["password"], {"old": "******", "new": "******"})
        self.assertEqual(diff["api_key"], {"old": "******", "new": "******"})
