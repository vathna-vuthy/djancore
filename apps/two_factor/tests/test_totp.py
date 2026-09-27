import base64
import time
from unittest import mock

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


class TOTPRFC6238ComplianceTests(TestCase):
    """Conformance tests against the official RFC 6238 SHA-1 test vectors.

    RFC 6238 Appendix B publishes 8-digit OTPs; this implementation truncates
    to 6 digits, so expected values are the low 6 digits of each vector.
    """

    # base32("12345678901234567890") — the ASCII seed from RFC 4226 Appendix D
    RFC_SECRET = "GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ"

    RFC_VECTORS = [
        (1, "287082"),  # T=59        -> 94287082
        (37037036, "081804"),  # T=1111111109 -> 07081804
        (37037037, "050471"),  # T=1111111111 -> 14050471
        (41152263, "005924"),  # T=1234567890 -> 89005924
        (66666666, "279037"),  # T=2000000000 -> 69279037
        (666666666, "353130"),  # T=20000000000 -> 65353130
    ]

    def test_rfc6238_vectors(self):
        for time_step, expected in self.RFC_VECTORS:
            with self.subTest(time_step=time_step):
                code = TOTP.generate_code(self.RFC_SECRET, time_step=time_step)
                self.assertEqual(code, expected)

    def test_rfc6238_vectors_verify(self):
        for time_step, expected in self.RFC_VECTORS:
            with self.subTest(time_step=time_step):
                # Freeze the clock inside the vector's own 30-second window
                with mock.patch(
                    "apps.two_factor.totp.time.time",
                    return_value=float(time_step * TOTP.INTERVAL),
                ):
                    is_valid, step = TOTP.verify_code(
                        self.RFC_SECRET,
                        expected,
                        window=0,
                        last_used_step=time_step - 1,
                    )
                self.assertTrue(is_valid)
                self.assertEqual(step, time_step)

    def test_codes_with_leading_zero_are_zero_padded(self):
        code = TOTP.generate_code(self.RFC_SECRET, time_step=41152263)
        self.assertEqual(code, "005924")
        self.assertEqual(len(code), 6)


class TOTPInputHandlingTests(TestCase):
    """Edge cases around secret normalization, windows, and malformed input."""

    def test_verify_accepts_lowercase_and_padded_secret(self):
        secret = TOTP.generate_secret()
        code = TOTP.generate_code(secret)

        lowered = secret.lower()
        padded = f"  {lowered}  "
        is_valid, _ = TOTP.verify_code(padded, code, window=1)
        self.assertTrue(is_valid)

    def test_verify_rejects_wrong_secret(self):
        code = TOTP.generate_code(TOTP.generate_secret())
        is_valid, _ = TOTP.verify_code(TOTP.generate_secret(), code, window=1)
        self.assertFalse(is_valid)

    def test_window_zero_rejects_clock_drift(self):
        secret = TOTP.generate_secret()
        current_step = int(time.time() // TOTP.INTERVAL)

        past_code = TOTP.generate_code(secret, time_step=current_step - 1)
        is_valid, _ = TOTP.verify_code(secret, past_code, window=0)
        self.assertFalse(is_valid)

        # The exact current-step code still verifies with window=0
        current_code = TOTP.generate_code(secret, time_step=current_step)
        is_valid_now, _ = TOTP.verify_code(secret, current_code, window=0)
        self.assertTrue(is_valid_now)

    def test_verify_rejects_codes_outside_future_window(self):
        secret = TOTP.generate_secret()
        current_step = int(time.time() // TOTP.INTERVAL)

        future_code = TOTP.generate_code(secret, time_step=current_step + 2)
        is_valid, _ = TOTP.verify_code(secret, future_code, window=1)
        self.assertFalse(is_valid)

    def test_verify_rejects_empty_and_overlong_codes(self):
        secret = TOTP.generate_secret()
        self.assertEqual(TOTP.verify_code(secret, "", window=1), (False, None))
        self.assertEqual(TOTP.verify_code(secret, "1234567", window=1), (False, None))
        self.assertEqual(
            TOTP.verify_code(secret, "123456789012", window=1), (False, None)
        )

    def test_verify_rejects_non_digit_lookalikes(self):
        secret = TOTP.generate_secret()
        for bad in ["12345a", "12 345", "1234.5", "１２３４５６", "-12345"]:  # noqa: RUF001
            with self.subTest(code=bad):
                is_valid, _ = TOTP.verify_code(secret, bad, window=1)
                self.assertFalse(is_valid)

    def test_verify_strips_surrounding_whitespace(self):
        secret = TOTP.generate_secret()
        code = TOTP.generate_code(secret)
        is_valid, _ = TOTP.verify_code(secret, f"  {code}\n", window=1)
        self.assertTrue(is_valid)

    def test_generate_secret_respects_custom_byte_length(self):
        for byte_length in (10, 16, 32):
            with self.subTest(byte_length=byte_length):
                secret = TOTP.generate_secret(byte_length)
                padded = secret + "=" * ((8 - len(secret) % 8) % 8)
                self.assertEqual(len(base64.b32decode(padded)), byte_length)

    def test_generate_secret_is_unique_per_call(self):
        secrets_seen = {TOTP.generate_secret() for _ in range(10)}
        self.assertEqual(len(secrets_seen), 10)

    def test_generate_code_stable_for_same_step(self):
        secret = TOTP.generate_secret()
        codes = {TOTP.generate_code(secret, time_step=123456) for _ in range(5)}
        self.assertEqual(len(codes), 1)

    def test_provisioning_uri_percent_encodes_special_characters(self):
        uri = TOTP.get_provisioning_uri(
            secret="JBSWY3DPEHPK3PXP",
            account_name="john doe+tag@example.com",
            issuer="ACME Co",
        )
        self.assertIn("ACME%20Co:john%20doe%2Btag%40example.com", uri)
        self.assertIn("issuer=ACME%20Co", uri)
        self.assertIn("secret=JBSWY3DPEHPK3PXP", uri)

    def test_provisioning_uri_normalizes_secret_whitespace(self):
        uri = TOTP.get_provisioning_uri(
            secret=" jbswy3dpehpk3pxp ",
            account_name="user@example.com",
        )
        self.assertIn("secret=JBSWY3DPEHPK3PXP", uri)
