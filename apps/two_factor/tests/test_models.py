import datetime

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase

from apps.two_factor.models import RecoveryCode, TOTPDevice
from apps.two_factor.totp import TOTP

User = get_user_model()


class TOTPDeviceModelTests(TestCase):
    """Unit tests for the TOTPDevice model."""

    def setUp(self):
        self.user = User.objects.create_user(
            email="deviceuser@example.com",
            password="StrongPassword123!",
            first_name="Device",
            last_name="User",
        )
        self.raw_secret = TOTP.generate_secret()
        self.device = TOTPDevice.objects.create(
            user=self.user, encrypted_secret="placeholder"
        )
        self.device.set_secret(self.raw_secret)
        self.device.save(update_fields=["encrypted_secret"])

    def test_secret_is_encrypted_at_rest(self):
        self.assertNotIn(self.raw_secret, self.device.encrypted_secret)
        self.assertEqual(self.device.secret, self.raw_secret)

    def test_secret_property_decrypts_after_refresh(self):
        self.device.refresh_from_db()
        self.assertEqual(self.device.secret, self.raw_secret)

    def test_str_confirmed_and_unconfirmed(self):
        self.assertIn("Unconfirmed", str(self.device))
        self.device.is_confirmed = True
        self.assertIn("Confirmed", str(self.device))

    def test_one_device_per_user(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            TOTPDevice.objects.create(
                user=self.user,
                encrypted_secret=self.device.encrypted_secret,
            )

    def test_verify_totp_code_success_updates_last_used_step(self):
        code = TOTP.generate_code(self.raw_secret)
        self.assertTrue(self.device.verify_totp_code(code))
        self.assertIsNotNone(self.device.last_used_step)
        self.device.save(update_fields=["last_used_step", "updated_at"])

        # Replaying the same code inside the same step must now fail
        self.assertFalse(self.device.verify_totp_code(code))

    def test_verify_totp_code_rejects_invalid_code(self):
        self.assertFalse(self.device.verify_totp_code("000000"))
        self.assertFalse(self.device.verify_totp_code("abcdef"))
        self.assertFalse(self.device.verify_totp_code(""))
        self.assertIsNone(self.device.last_used_step)

    def test_verify_totp_code_works_on_unconfirmed_device(self):
        self.assertFalse(self.device.is_confirmed)
        code = TOTP.generate_code(self.raw_secret)
        self.assertTrue(self.device.verify_totp_code(code))

    def test_verify_totp_code_rejects_code_from_other_secret(self):
        other_secret = TOTP.generate_secret()
        foreign_code = TOTP.generate_code(other_secret)
        self.assertFalse(self.device.verify_totp_code(foreign_code))

    def test_get_provisioning_uri(self):
        uri = self.device.get_provisioning_uri(issuer="ACME")
        self.assertTrue(uri.startswith("otpauth://totp/ACME:"))
        self.assertIn(self.user.email.replace("@", "%40"), uri)
        self.assertIn(f"secret={self.raw_secret}", uri)
        self.assertIn("period=30", uri)

    def test_soft_delete_device_keeps_recovery_code_rows(self):
        RecoveryCode.objects.create(device=self.device, hashed_code="a" * 64)
        self.assertEqual(self.device.recovery_codes.count(), 1)

        self.device.delete()
        self.device.refresh_from_db()
        self.assertTrue(self.device.is_deleted)
        self.assertIsNotNone(self.device.deleted_at)

        # Hidden from the default manager, still present via all_objects
        self.assertFalse(TOTPDevice.objects.filter(pk=self.device.pk).exists())
        self.assertTrue(TOTPDevice.all_objects.filter(pk=self.device.pk).exists())
        self.assertEqual(RecoveryCode.objects.count(), 1)

    def test_hard_delete_device_cascades_recovery_codes(self):
        RecoveryCode.objects.create(device=self.device, hashed_code="a" * 64)
        self.assertEqual(RecoveryCode.all_objects.count(), 1)

        self.device.hard_delete()
        self.assertEqual(RecoveryCode.all_objects.count(), 0)

    def test_restore_returns_device_to_default_manager(self):
        self.device.delete()
        self.device.restore()
        self.assertFalse(self.device.is_deleted)
        self.assertIsNone(self.device.deleted_at)
        self.assertTrue(TOTPDevice.objects.filter(pk=self.device.pk).exists())


class RecoveryCodeModelTests(TestCase):
    """Unit tests for the RecoveryCode model."""

    def setUp(self):
        self.user = User.objects.create_user(
            email="recovery@example.com",
            password="StrongPassword123!",
            first_name="Recovery",
            last_name="User",
        )
        self.device = TOTPDevice.objects.create(user=self.user, encrypted_secret="x")
        self.code = RecoveryCode.objects.create(
            device=self.device,
            hashed_code=RecoveryCode.hash_code("ABCD-1234"),
        )

    def test_str_available_and_used(self):
        self.assertIn("Available", str(self.code))
        self.code.mark_used()
        self.assertIn("Used", str(self.code))

    def test_hash_code_normalization(self):
        canonical = RecoveryCode.hash_code("ABCD-1234")
        self.assertEqual(canonical, RecoveryCode.hash_code("abcd-1234"))
        self.assertEqual(canonical, RecoveryCode.hash_code("  abcd 1234  "))
        self.assertEqual(canonical, RecoveryCode.hash_code("ABCD1234"))
        self.assertEqual(len(canonical), 64)

    def test_hash_code_distinct_values(self):
        self.assertNotEqual(
            RecoveryCode.hash_code("ABCD-1234"), RecoveryCode.hash_code("ABCD-1235")
        )

    def test_mark_used_sets_timestamp(self):
        self.assertFalse(self.code.is_used)
        self.assertIsNone(self.code.used_at)

        self.code.mark_used()
        self.code.refresh_from_db()
        self.assertTrue(self.code.is_used)
        self.assertIsNotNone(self.code.used_at)

    def test_mark_used_twice_keeps_code_consumed(self):
        self.code.mark_used()
        first_used_at = self.code.used_at

        self.code.mark_used()
        self.code.refresh_from_db()
        self.assertTrue(self.code.is_used)
        # used_at is refreshed on every call, but the code stays consumed
        self.assertIsNotNone(self.code.used_at)
        self.assertGreaterEqual(self.code.used_at, first_used_at)

    def test_unused_lookup_by_hash(self):
        hashed = RecoveryCode.hash_code("ABCD-1234")
        found = self.device.recovery_codes.filter(
            hashed_code=hashed, is_used=False
        ).first()
        self.assertIsNotNone(found)

        self.code.mark_used()
        found_after = self.device.recovery_codes.filter(
            hashed_code=hashed, is_used=False
        ).first()
        self.assertIsNone(found_after)

    def test_default_timestamps_are_timezone_aware(self):
        self.assertIsNotNone(self.code.created_at)
        self.assertIsNotNone(self.code.created_at.utcoffset())
        self.assertEqual(self.code.created_at.utcoffset(), datetime.timedelta(0))
