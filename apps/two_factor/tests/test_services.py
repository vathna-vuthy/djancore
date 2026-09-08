from django.contrib.auth import get_user_model
from django.test import TestCase

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
