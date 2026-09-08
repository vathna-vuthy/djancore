from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

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
