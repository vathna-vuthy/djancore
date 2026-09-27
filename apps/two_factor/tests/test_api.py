from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.two_factor.models import TOTPDevice
from apps.two_factor.services import TwoFactorService
from apps.two_factor.totp import TOTP

User = get_user_model()


class TwoFactorAPITests(APITestCase):
    """Integration API tests for 2FA lifecycle and login challenge."""

    def setUp(self):
        self.password = "SuperSecurePass123!"
        self.user = User.objects.create_user(
            email="developer@example.com",
            password=self.password,
            first_name="Dev",
            last_name="User",
        )
        self.status_url = reverse("two_factor:two-factor-status-view")
        self.setup_url = reverse("two_factor:two-factor-setup")
        self.confirm_url = reverse("two_factor:two-factor-confirm")
        self.disable_url = reverse("two_factor:two-factor-disable")
        self.regenerate_url = reverse("two_factor:two-factor-regenerate-codes")
        self.challenge_url = reverse("two_factor:two-factor-challenge")
        self.login_url = reverse("iam:login")

    def test_status_unauthenticated(self):
        response = self.client.get(self.status_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_status_when_disabled(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.status_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data["data"]["is_enabled"])
        self.assertEqual(response.data["data"]["remaining_recovery_codes"], 0)

    def test_setup_and_confirm_flow(self):
        self.client.force_authenticate(user=self.user)

        # 1. Initiate setup
        setup_resp = self.client.post(self.setup_url)
        self.assertEqual(setup_resp.status_code, status.HTTP_200_OK)
        secret = setup_resp.data["data"]["secret"]
        otpauth_url = setup_resp.data["data"]["otpauth_url"]
        recovery_codes = setup_resp.data["data"]["recovery_codes"]

        self.assertIsNotNone(secret)
        self.assertIn("otpauth://totp/", otpauth_url)
        self.assertEqual(len(recovery_codes), 8)

        # 2. Confirm with invalid code
        confirm_fail = self.client.post(self.confirm_url, {"code": "000000"})
        self.assertEqual(confirm_fail.status_code, status.HTTP_400_BAD_REQUEST)

        # 3. Confirm with valid code
        valid_code = TOTP.generate_code(secret)
        confirm_resp = self.client.post(self.confirm_url, {"code": valid_code})
        self.assertEqual(confirm_resp.status_code, status.HTTP_200_OK)

        # 4. Check status now active
        status_resp = self.client.get(self.status_url)
        self.assertTrue(status_resp.data["data"]["is_enabled"])
        self.assertEqual(status_resp.data["data"]["remaining_recovery_codes"], 8)

    def test_login_flow_with_2fa_and_challenge(self):
        # 1. Enable 2FA on user
        _, secret, recovery_codes = TwoFactorService.setup_device(self.user)
        valid_code = TOTP.generate_code(secret)
        TwoFactorService.confirm_device(self.user, valid_code)

        # 2. Perform regular login
        login_resp = self.client.post(
            self.login_url,
            {"username": self.user.email, "password": self.password},
        )
        self.assertEqual(login_resp.status_code, status.HTTP_200_OK)
        self.assertTrue(login_resp.data.get("requires_2fa"))
        challenge_token = login_resp.data.get("challenge_token")
        self.assertIsNotNone(challenge_token)
        self.assertNotIn("token", login_resp.data)

        # 3. Attempt challenge with invalid code
        challenge_fail = self.client.post(
            self.challenge_url,
            {"challenge_token": challenge_token, "code": "000000"},
        )
        self.assertEqual(challenge_fail.status_code, status.HTTP_400_BAD_REQUEST)

        # 4. Complete challenge with recovery code
        challenge_ok = self.client.post(
            self.challenge_url,
            {"challenge_token": challenge_token, "code": recovery_codes[0]},
        )
        self.assertEqual(challenge_ok.status_code, status.HTTP_200_OK)
        self.assertIn("token", challenge_ok.data)
        self.assertEqual(challenge_ok.data["user"]["email"], self.user.email)

    def test_regenerate_codes_endpoint(self):
        _, secret, recovery_codes = TwoFactorService.setup_device(self.user)
        valid_code = TOTP.generate_code(secret)
        TwoFactorService.confirm_device(self.user, valid_code)

        self.client.force_authenticate(user=self.user)
        resp = self.client.post(self.regenerate_url, {"code": recovery_codes[0]})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        new_codes = resp.data["data"]["recovery_codes"]
        self.assertEqual(len(new_codes), 8)
        self.assertNotEqual(new_codes, recovery_codes)

    def test_disable_2fa_endpoint(self):
        _, secret, recovery_codes = TwoFactorService.setup_device(self.user)
        valid_code = TOTP.generate_code(secret)
        TwoFactorService.confirm_device(self.user, valid_code)

        self.client.force_authenticate(user=self.user)
        resp = self.client.post(self.disable_url, {"code": recovery_codes[0]})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        status_resp = self.client.get(self.status_url)
        self.assertFalse(status_resp.data["data"]["is_enabled"])


class TwoFactorAPIAccessControlTests(APITestCase):
    """Authentication, validation, and hardening tests for the 2FA API surface."""

    def setUp(self):
        self.user = User.objects.create_user(
            email="access@example.com",
            password="SuperSecurePass123!",
            first_name="Access",
            last_name="User",
        )
        self.status_url = reverse("two_factor:two-factor-status-view")
        self.setup_url = reverse("two_factor:two-factor-setup")
        self.confirm_url = reverse("two_factor:two-factor-confirm")
        self.disable_url = reverse("two_factor:two-factor-disable")
        self.regenerate_url = reverse("two_factor:two-factor-regenerate-codes")
        self.challenge_url = reverse("two_factor:two-factor-challenge")
        self.login_url = reverse("iam:login")

    def _enroll(self) -> tuple[str, list[str]]:
        _, secret, recovery_codes = TwoFactorService.setup_device(self.user)
        TwoFactorService.confirm_device(self.user, TOTP.generate_code(secret))
        return secret, recovery_codes

    def _next_totp_code(self, secret: str) -> str:
        """Code for the step after the one consumed during confirm (avoids replay)."""
        device = TOTPDevice.objects.get(user=self.user)
        assert device.last_used_step is not None
        return TOTP.generate_code(secret, time_step=device.last_used_step + 1)

    def test_protected_endpoints_require_authentication(self):
        protected = [
            ("get", self.status_url),
            ("post", self.setup_url),
            ("post", self.confirm_url),
            ("post", self.disable_url),
            ("post", self.regenerate_url),
        ]
        for method, url in protected:
            with self.subTest(url=url, method=method):
                resp = getattr(self.client, method)(url, {"code": "123456"})
                self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_confirm_requires_code_field(self):
        self.client.force_authenticate(user=self.user)
        resp = self.client.post(self.confirm_url, {})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("code", resp.data["errors"])

    def test_confirm_rejects_oversized_code(self):
        self.client.force_authenticate(user=self.user)
        resp = self.client.post(self.confirm_url, {"code": "1" * 33})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_challenge_requires_both_fields(self):
        resp = self.client.post(self.challenge_url, {})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("challenge_token", resp.data["errors"])
        self.assertIn("code", resp.data["errors"])

    def test_challenge_rejects_invalid_token(self):
        resp = self.client.post(
            self.challenge_url,
            {"challenge_token": "garbage-token", "code": "123456"},
        )
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_status_reports_pending_setup(self):
        TwoFactorService.setup_device(self.user)
        self.client.force_authenticate(user=self.user)

        resp = self.client.get(self.status_url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertFalse(resp.data["data"]["is_enabled"])
        self.assertEqual(resp.data["data"]["remaining_recovery_codes"], 0)

    def test_setup_response_shape_and_code_format(self):
        self.client.force_authenticate(user=self.user)
        resp = self.client.post(self.setup_url)
        data = resp.data["data"]

        self.assertEqual(len(data["recovery_codes"]), 8)
        self.assertEqual(len(set(data["recovery_codes"])), 8)
        for code in data["recovery_codes"]:
            self.assertRegex(code, r"^[0-9A-F]{4}-[0-9A-F]{4}$")

        self.assertIn(f"secret={data['secret']}", data["otpauth_url"])
        self.assertIn(self.user.email.replace("@", "%40"), data["otpauth_url"])
        self.assertEqual(len(data["secret"]), 32)

    def test_disable_with_invalid_code_returns_400(self):
        self._enroll()
        self.client.force_authenticate(user=self.user)

        resp = self.client.post(self.disable_url, {"code": "000000"})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

        status_resp = self.client.get(self.status_url)
        self.assertTrue(status_resp.data["data"]["is_enabled"])

    def test_regenerate_with_invalid_code_returns_400(self):
        self._enroll()
        self.client.force_authenticate(user=self.user)

        resp = self.client.post(self.regenerate_url, {"code": "000000"})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_status_remaining_codes_decrements_after_use(self):
        _, recovery_codes = self._enroll()
        TwoFactorService.verify_code(self.user, recovery_codes[0])

        self.client.force_authenticate(user=self.user)
        resp = self.client.get(self.status_url)
        self.assertEqual(resp.data["data"]["remaining_recovery_codes"], 7)

    def test_challenge_with_totp_code_and_replay_rejected(self):
        secret, _ = self._enroll()
        token = TwoFactorService.create_challenge_token(self.user)
        totp_code = self._next_totp_code(secret)

        first = self.client.post(
            self.challenge_url, {"challenge_token": token, "code": totp_code}
        )
        self.assertEqual(first.status_code, status.HTTP_200_OK)
        self.assertEqual(first.data["user"]["email"], self.user.email)
        auth_token = first.data["token"]

        # Same TOTP code cannot be replayed inside its 30-second window
        replay = self.client.post(
            self.challenge_url, {"challenge_token": token, "code": totp_code}
        )
        self.assertEqual(replay.status_code, status.HTTP_400_BAD_REQUEST)

        # Returned token authenticates against protected endpoints
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {auth_token}")
        status_resp = self.client.get(self.status_url)
        self.assertEqual(status_resp.status_code, status.HTTP_200_OK)

    def test_challenge_token_cannot_be_used_for_second_user(self):
        other = User.objects.create_user(
            email="other@example.com",
            password="SuperSecurePass123!",
            first_name="Other",
            last_name="User",
        )
        _, secret, other_codes = TwoFactorService.setup_device(other)
        TwoFactorService.confirm_device(other, TOTP.generate_code(secret))

        # Token belongs to self.user who has no confirmed device
        token = TwoFactorService.create_challenge_token(self.user)
        resp = self.client.post(
            self.challenge_url, {"challenge_token": token, "code": other_codes[0]}
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_login_without_2fa_returns_token_immediately(self):
        resp = self.client.post(
            self.login_url,
            {"username": self.user.email, "password": "SuperSecurePass123!"},
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertFalse(resp.data.get("requires_2fa"))
        self.assertIn("token", resp.data)

    def test_login_with_unconfirmed_setup_skips_challenge(self):
        TwoFactorService.setup_device(self.user)
        resp = self.client.post(
            self.login_url,
            {"username": self.user.email, "password": "SuperSecurePass123!"},
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertFalse(resp.data.get("requires_2fa"))
        self.assertIn("token", resp.data)

    def test_full_login_flow_with_totp_code(self):
        secret, _ = self._enroll()

        login_resp = self.client.post(
            self.login_url,
            {"username": self.user.email, "password": "SuperSecurePass123!"},
        )
        self.assertTrue(login_resp.data.get("requires_2fa"))

        challenge_resp = self.client.post(
            self.challenge_url,
            {
                "challenge_token": login_resp.data["challenge_token"],
                "code": self._next_totp_code(secret),
            },
        )
        self.assertEqual(challenge_resp.status_code, status.HTTP_200_OK)
        self.assertIn("token", challenge_resp.data)
