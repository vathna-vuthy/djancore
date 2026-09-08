import base64
import time

from django.test import TestCase

from apps.two_factor.models import RecoveryCode
from apps.two_factor.totp import TOTP


class TOTPAlgorithmTests(TestCase):
    """Unit tests for RFC 6238 TOTP computation and recovery code utilities."""

    def test_generate_base32_secret(self):
        secret = TOTP.generate_secret()
        self.assertIsInstance(secret, str)
        # Check standard base32 characters decode without error
        padded = secret + "=" * ((8 - len(secret) % 8) % 8)
        decoded = base64.b32decode(padded)
        self.assertEqual(len(decoded), 20)

    def test_generate_totp_code_length_and_consistency(self):
        secret = TOTP.generate_secret()
        time_step = 56666666
        code = TOTP.generate_code(secret, time_step=time_step)
        self.assertEqual(len(code), 6)
        self.assertTrue(code.isdigit())

        # Exact same time step should generate exact same code
        code2 = TOTP.generate_code(secret, time_step=time_step)
        self.assertEqual(code, code2)

    def test_verify_totp_code_current_step(self):
        secret = TOTP.generate_secret()
        code = TOTP.generate_code(secret)

        is_valid, step = TOTP.verify_code(secret, code, window=1)
        self.assertTrue(is_valid)
        self.assertIsNotNone(step)

    def test_verify_totp_code_drift_tolerance(self):
        secret = TOTP.generate_secret()
        current_step = int(time.time() // 30)

        # Code from 1 step ago
        past_code = TOTP.generate_code(secret, time_step=current_step - 1)
        # Code from 1 step ahead
        future_code = TOTP.generate_code(secret, time_step=current_step + 1)

        # Window = 1 should match both
        valid_past, _ = TOTP.verify_code(secret, past_code, window=1)
        valid_future, _ = TOTP.verify_code(secret, future_code, window=1)
        self.assertTrue(valid_past)
        self.assertTrue(valid_future)

        # Code from 2 steps ago with window=1 should fail
        way_past_code = TOTP.generate_code(secret, time_step=current_step - 2)
        valid_way_past, _ = TOTP.verify_code(secret, way_past_code, window=1)
        self.assertFalse(valid_way_past)

    def test_verify_totp_code_replay_protection(self):
        secret = TOTP.generate_secret()
        code = TOTP.generate_code(secret)

        is_valid, step = TOTP.verify_code(secret, code, window=1)
        self.assertTrue(is_valid)
        self.assertIsNotNone(step)

        # Re-using code with last_used_step equal or greater than step must fail
        is_replay_valid, _ = TOTP.verify_code(
            secret, code, window=1, last_used_step=step
        )
        self.assertFalse(is_replay_valid)

    def test_verify_invalid_code(self):
        secret = TOTP.generate_secret()
        is_invalid, _ = TOTP.verify_code(secret, "abcdef", window=1)
        self.assertFalse(is_invalid)

        is_invalid_len, _ = TOTP.verify_code(secret, "12345", window=1)
        self.assertFalse(is_invalid_len)

    def test_recovery_code_hashing_and_verification(self):
        raw_code = "ABCD-1234"
        hashed = RecoveryCode.hash_code(raw_code)
        self.assertEqual(len(hashed), 64)

        # Same code normalized should match
        self.assertEqual(RecoveryCode.hash_code("abcd-1234"), hashed)
        self.assertEqual(RecoveryCode.hash_code(" ABCD 1234 "), hashed)

    def test_build_otpauth_uri(self):
        secret = "JBSWY3DPEHPK3PXP"
        uri = TOTP.get_provisioning_uri(
            secret=secret,
            account_name="test@example.com",
            issuer="djancore",
        )
        self.assertTrue(uri.startswith("otpauth://totp/"))
        self.assertIn("djancore:test%40example.com", uri)
        self.assertIn("secret=JBSWY3DPEHPK3PXP", uri)
        self.assertIn("issuer=djancore", uri)
        self.assertIn("algorithm=SHA1", uri)
        self.assertIn("digits=6", uri)
        self.assertIn("period=30", uri)
