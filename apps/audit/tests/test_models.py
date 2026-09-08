from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.test import TestCase

from apps.audit.models import AuditAction, AuditLog

User = get_user_model()


class AuditModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="auditor@example.com",
            password="StrongPassword123!",
        )

    def test_audit_log_creation_and_auto_message_generation(self):
        # 1. CREATE action
        log_create = AuditLog.objects.create(
            actor=self.user,
            actor_repr=self.user.email,
            action=AuditAction.CREATE,
            resource_type="apps.iam.User",
            resource_id=str(self.user.id),
            resource_repr=self.user.email,
        )
        self.assertIn(
            "Actor auditor@example.com created User 'auditor@example.com'",
            log_create.message,
        )

        # 2. UPDATE action with field changes
        log_update = AuditLog.objects.create(
            actor=self.user,
            actor_repr=self.user.email,
            action=AuditAction.UPDATE,
            resource_type="apps.system_config.SystemConfig",
            resource_id="ENABLE_MFA",
            resource_repr="ENABLE_MFA",
            changes={"value": {"old": "false", "new": "true"}},
        )
        self.assertIn(
            "Actor auditor@example.com updated SystemConfig 'ENABLE_MFA'",
            log_update.message,
        )
        self.assertIn("(Fields modified: value)", log_update.message)

        # 3. LOGIN action
        log_login = AuditLog.objects.create(
            actor=self.user,
            actor_repr=self.user.email,
            action=AuditAction.LOGIN,
        )
        self.assertEqual(log_login.message, "Actor auditor@example.com logged in.")

    def test_custom_message_preservation(self):
        log = AuditLog.objects.create(
            actor=self.user,
            actor_repr=self.user.email,
            action=AuditAction.CUSTOM,
            message="Custom security incident detected on gateway.",
        )
        self.assertEqual(log.message, "Custom security incident detected on gateway.")

    def test_immutability_enforcement_on_instance_save_and_delete(self):
        log = AuditLog.objects.create(
            actor=self.user,
            action=AuditAction.CREATE,
            resource_type="TestResource",
        )

        # Updating existing record must raise PermissionDenied
        log.actor_repr = "Modified Actor"
        with self.assertRaises(PermissionDenied):
            log.save()

        # Deleting existing record must raise PermissionDenied
        with self.assertRaises(PermissionDenied):
            log.delete()

    def test_immutability_enforcement_on_queryset_bulk_operations(self):
        AuditLog.objects.create(
            actor=self.user,
            action=AuditAction.CREATE,
            resource_type="BulkTest",
        )
        qs = AuditLog.objects.filter(resource_type="BulkTest")

        # Bulk delete must raise PermissionDenied
        with self.assertRaises(PermissionDenied):
            qs.delete()

        # Bulk update must raise PermissionDenied
        with self.assertRaises(PermissionDenied):
            qs.update(actor_repr="Hacked")
