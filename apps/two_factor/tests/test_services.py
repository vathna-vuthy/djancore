from unittest import mock

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.test import TestCase
from rest_framework.exceptions import ValidationError

from apps.audit.models import AuditAction, AuditLog
from apps.two_factor.models import TOTPDevice
from apps.two_factor.services import TwoFactorService
from apps.two_factor.totp import TOTP

User = get_user_model()


class TwoFactorServiceTests(TestCase):
    """Unit tests for TwoFactorService."""

    def setUp(self):
        self.user = User.objects.create_user(
            email="testuser@example.com",
            password="StrongPassword123!",
            first_name="Test",
            last_name="User",
        )

    def test_setup_device(self):
        device, raw_secret, recovery_codes = TwoFactorService.setup_device(self.user)
        self.assertIsNotNone(device.pk)
        self.assertFalse(device.is_confirmed)
        self.assertEqual(len(raw_secret), 32)
        self.assertEqual(len(recovery_codes), 8)
        self.assertEqual(device.recovery_codes.count(), 8)

        # Calling setup again replaces unconfirmed device
        device2, _, _ = TwoFactorService.setup_device(self.user)
        self.assertEqual(device.pk, device2.pk)
        self.assertEqual(device2.recovery_codes.count(), 8)

    def test_setup_device_when_already_confirmed(self):
        _, raw_secret, _ = TwoFactorService.setup_device(self.user)
        valid_code = TOTP.generate_code(raw_secret)
        TwoFactorService.confirm_device(self.user, valid_code)

        # In our implementation setup_device overwrites secret and resets confirmed to False
        device3, _, _ = TwoFactorService.setup_device(self.user)
        self.assertFalse(device3.is_confirmed)

    def test_confirm_device(self):
        device, raw_secret, _ = TwoFactorService.setup_device(self.user)
        valid_code = TOTP.generate_code(raw_secret)

        success = TwoFactorService.confirm_device(self.user, valid_code)
        self.assertTrue(success)

        device.refresh_from_db()
        self.assertTrue(device.is_confirmed)
        self.assertIsNotNone(device.last_verified_at)
        self.assertTrue(TwoFactorService.is_2fa_enabled(self.user))

    def test_confirm_device_with_invalid_code(self):
        TwoFactorService.setup_device(self.user)
        success = TwoFactorService.confirm_device(self.user, "000000")
        self.assertFalse(success)
        self.assertFalse(TwoFactorService.is_2fa_enabled(self.user))

    def test_verify_code_totp_and_replay(self):
        _, raw_secret, _ = TwoFactorService.setup_device(self.user)
        valid_code = TOTP.generate_code(raw_secret)
        TwoFactorService.confirm_device(self.user, valid_code)

        # Immediately reusing the exact same code should fail due to replay protection
        is_replay_valid = TwoFactorService.verify_code(self.user, valid_code)
        self.assertFalse(is_replay_valid)

    def test_verify_code_recovery_code(self):
        _, raw_secret, recovery_codes = TwoFactorService.setup_device(self.user)
        valid_code = TOTP.generate_code(raw_secret)
        TwoFactorService.confirm_device(self.user, valid_code)

        test_code = recovery_codes[0]
        # Use recovery code to authenticate
        self.assertTrue(TwoFactorService.verify_code(self.user, test_code))

        # Check recovery code marked as used
        device = TOTPDevice.objects.get(user=self.user)
        used_count = device.recovery_codes.filter(is_used=True).count()
        self.assertEqual(used_count, 1)

        # Attempting to use the exact same recovery code again must fail
        self.assertFalse(TwoFactorService.verify_code(self.user, test_code))

    def test_disable_2fa(self):
        _, raw_secret2, recovery_codes2 = TwoFactorService.setup_device(
            User.objects.create_user(
                email="user2@example.com",
                password="StrongPassword123!",
                first_name="User",
                last_name="Two",
            )
        )
        user2 = User.objects.get(email="user2@example.com")
        code2 = TOTP.generate_code(raw_secret2)
        TwoFactorService.confirm_device(user2, code2)

        # Disable using first recovery code
        self.assertTrue(TwoFactorService.disable_2fa(user2, recovery_codes2[0]))
        self.assertFalse(TwoFactorService.is_2fa_enabled(user2))
        self.assertFalse(TOTPDevice.objects.filter(user=user2).exists())

    def test_regenerate_recovery_codes(self):
        device, raw_secret, old_codes = TwoFactorService.setup_device(self.user)
        valid_code = TOTP.generate_code(raw_secret)
        TwoFactorService.confirm_device(self.user, valid_code)

        # Regenerate using recovery code
        new_codes = TwoFactorService.regenerate_recovery_codes(self.user, old_codes[0])
        self.assertEqual(len(new_codes), 8)
        self.assertEqual(device.recovery_codes.filter(is_used=False).count(), 8)

        # Old codes should no longer work
        self.assertFalse(TwoFactorService.verify_code(self.user, old_codes[1]))
        # New code should work
        self.assertTrue(TwoFactorService.verify_code(self.user, new_codes[0]))

    def test_challenge_token_lifecycle(self):
        token = TwoFactorService.create_challenge_token(self.user)
        self.assertIsInstance(token, str)

        verified_user = TwoFactorService.verify_challenge_token(token)
        self.assertEqual(verified_user, self.user)

        # Invalid token returns None
        self.assertIsNone(
            TwoFactorService.verify_challenge_token("invalid:token:value")
        )


class TwoFactorServiceEdgeCaseTests(TestCase):
    """Error paths, guard clauses, and hardening tests for TwoFactorService."""

    def setUp(self):
        self.user = User.objects.create_user(
            email="edgecase@example.com",
            password="StrongPassword123!",
            first_name="Edge",
            last_name="Case",
        )

    def _enrolled_user(self) -> tuple[TOTPDevice, str, list[str]]:
        """Enroll 2FA for self.user and return (device, secret, recovery codes)."""
        device, secret, recovery_codes = TwoFactorService.setup_device(self.user)
        TwoFactorService.confirm_device(self.user, TOTP.generate_code(secret))
        return device, secret, recovery_codes

    def test_confirm_without_setup_raises(self):
        with self.assertRaises(ValidationError):
            TwoFactorService.confirm_device(self.user, "123456")

    def test_confirm_when_already_confirmed_short_circuits(self):
        self._enrolled_user()
        # Device already confirmed: no code check is performed
        self.assertTrue(TwoFactorService.confirm_device(self.user, "not-a-code"))

    def test_verify_code_without_device_returns_false(self):
        self.assertFalse(TwoFactorService.verify_code(self.user, "123456"))
        self.assertFalse(TwoFactorService.verify_code(self.user, "ABCD-1234"))

    def test_verify_code_with_unconfirmed_device_returns_false(self):
        _, secret, recovery_codes = TwoFactorService.setup_device(self.user)
        self.assertFalse(
            TwoFactorService.verify_code(self.user, TOTP.generate_code(secret))
        )
        self.assertFalse(TwoFactorService.verify_code(self.user, recovery_codes[0]))

    def test_verify_code_rejects_unknown_recovery_code(self):
        self._enrolled_user()
        self.assertFalse(TwoFactorService.verify_code(self.user, "DEAD-BEEF"))

    def test_verify_code_rejects_non_ascii_digits_without_crashing(self):
        # Regression: full-width digits previously raised TypeError in HMAC compare
        self._enrolled_user()
        for bad in ("１２３４５６", "¹²³⁴⁵⁶", "12345٦"):  # noqa: RUF001
            with self.subTest(code=bad):
                self.assertFalse(TwoFactorService.verify_code(self.user, bad))

    def test_verify_code_accepts_lowercase_recovery_code(self):
        _, _, recovery_codes = self._enrolled_user()
        raw = recovery_codes[0]
        self.assertTrue(TwoFactorService.verify_code(self.user, f"  {raw.lower()}  "))

    def test_verify_code_counts_remaining_recovery_codes(self):
        _, _, recovery_codes = self._enrolled_user()
        device = TOTPDevice.objects.get(user=self.user)
        self.assertEqual(device.recovery_codes.filter(is_used=False).count(), 8)

        TwoFactorService.verify_code(self.user, recovery_codes[0])
        self.assertEqual(device.recovery_codes.filter(is_used=False).count(), 7)

    def test_disable_with_invalid_code_keeps_device(self):
        self._enrolled_user()
        self.assertFalse(TwoFactorService.disable_2fa(self.user, "000000"))
        self.assertTrue(TOTPDevice.objects.filter(user=self.user).exists())
        self.assertTrue(TwoFactorService.is_2fa_enabled(self.user))

    def test_disable_without_any_setup_returns_false(self):
        self.assertFalse(TwoFactorService.disable_2fa(self.user, "123456"))

    def test_regenerate_with_invalid_code_raises(self):
        self._enrolled_user()
        with self.assertRaises(ValidationError):
            TwoFactorService.regenerate_recovery_codes(self.user, "000000")

    def test_regenerate_without_confirmed_device_raises(self):
        TwoFactorService.setup_device(self.user)
        with self.assertRaises(ValidationError):
            TwoFactorService.regenerate_recovery_codes(self.user, "123456")

    def test_is_2fa_enabled_for_anonymous_and_none(self):
        self.assertFalse(TwoFactorService.is_2fa_enabled(AnonymousUser()))
        self.assertFalse(TwoFactorService.is_2fa_enabled(None))

    def test_is_2fa_enabled_false_for_unconfirmed_setup(self):
        TwoFactorService.setup_device(self.user)
        self.assertFalse(TwoFactorService.is_2fa_enabled(self.user))

    def test_challenge_token_expired_returns_none(self):
        token = TwoFactorService.create_challenge_token(self.user)
        # max_age of -1 makes every previously signed token stale
        with mock.patch("apps.two_factor.services.CHALLENGE_TTL_SECONDS", -1):
            self.assertIsNone(TwoFactorService.verify_challenge_token(token))

    def test_challenge_token_for_inactive_user_returns_none(self):
        token = TwoFactorService.create_challenge_token(self.user)
        self.user.is_active = False
        self.user.save(update_fields=["is_active"])
        self.assertIsNone(TwoFactorService.verify_challenge_token(token))

    def test_challenge_token_tampered_returns_none(self):
        token = TwoFactorService.create_challenge_token(self.user)
        tampered = token[:-2] + ("AA" if not token.endswith("AA") else "BB")
        self.assertIsNone(TwoFactorService.verify_challenge_token(tampered))

    def test_challenge_token_with_wrong_salt_returns_none(self):
        from django.core import signing

        foreign = signing.dumps({"user_id": str(self.user.id)}, salt="some.other.salt")
        self.assertIsNone(TwoFactorService.verify_challenge_token(foreign))

    def test_setup_rotates_secret_on_re_setup(self):
        _, first_secret, _ = TwoFactorService.setup_device(self.user)
        device, second_secret, _ = TwoFactorService.setup_device(self.user)

        self.assertNotEqual(first_secret, second_secret)
        self.assertEqual(device.secret, second_secret)
        # The previously issued secret no longer produces verifiable codes
        old_code = TOTP.generate_code(first_secret)
        self.assertFalse(device.verify_totp_code(old_code))

    def test_reenable_2fa_after_disable(self):
        # Regression: disable_2fa() soft-deletes the device, which used to make
        # the next setup_device() hit the OneToOne unique constraint (500 error).
        _, secret, recovery_codes = self._enrolled_user()
        self.assertTrue(TwoFactorService.disable_2fa(self.user, recovery_codes[1]))

        device, new_secret, new_codes = TwoFactorService.setup_device(self.user)
        self.assertFalse(device.is_confirmed)
        self.assertFalse(device.is_deleted)
        self.assertNotEqual(secret, new_secret)
        self.assertEqual(len(new_codes), 8)

        self.assertTrue(
            TwoFactorService.confirm_device(self.user, TOTP.generate_code(new_secret))
        )
        self.assertTrue(TwoFactorService.is_2fa_enabled(self.user))

    def test_disabled_user_can_login_without_challenge(self):
        _, _, recovery_codes = self._enrolled_user()
        TwoFactorService.disable_2fa(self.user, recovery_codes[0])
        self.assertFalse(TwoFactorService.is_2fa_enabled(self.user))

    def test_audit_trail_recorded_for_lifecycle_events(self):
        _, _, recovery_codes = self._enrolled_user()
        TwoFactorService.disable_2fa(self.user, recovery_codes[0])

        logs = AuditLog.objects.filter(actor=self.user)
        messages = list(logs.values_list("message", flat=True))

        self.assertTrue(any("initiated 2FA setup" in m for m in messages))
        self.assertTrue(any("successfully enabled" in m for m in messages))
        self.assertTrue(
            any("disabled Two-Factor Authentication" in m for m in messages)
        )

        confirm_log = logs.filter(message__contains="successfully enabled").get()
        self.assertEqual(confirm_log.action, AuditAction.PERMISSION_CHANGE)
        self.assertEqual(confirm_log.resource_type, "apps.two_factor.TOTPDevice")
        self.assertIn(self.user.email, confirm_log.message)

    def test_audit_trail_recorded_for_recovery_code_login(self):
        _, _, recovery_codes = self._enrolled_user()
        TwoFactorService.verify_code(self.user, recovery_codes[0])

        log = AuditLog.objects.filter(
            actor=self.user, resource_type="apps.two_factor.RecoveryCode"
        ).get()
        self.assertIn("recovery code", log.message)
