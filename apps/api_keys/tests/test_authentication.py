import datetime

from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase
from django.utils import timezone
from rest_framework.exceptions import AuthenticationFailed, PermissionDenied

from apps.api_keys.authentication import APIKeyAuthentication
from apps.api_keys.models import APIKey

User = get_user_model()


class APIKeyAuthenticationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="authuser@example.com",
            password="Password123!",
        )
        self.auth = APIKeyAuthentication()
        self.factory = RequestFactory()
        self.api_key, self.raw_key = APIKey.generate_key(
            user=self.user,
            name="Main Auth Key",
        )

    def test_authenticate_via_x_api_key_header(self):
        """Test authenticating using X-API-Key header."""
        request = self.factory.get("/api/v1/iam/auth/me/", HTTP_X_API_KEY=self.raw_key)
        user, auth_obj = self.auth.authenticate(request) or (None, None)

        self.assertEqual(user, self.user)
        self.assertEqual(auth_obj, self.api_key)
        self.api_key.refresh_from_db()
        self.assertIsNotNone(self.api_key.last_used_at)

    def test_authenticate_via_authorization_api_key_header(self):
        """Test authenticating using Authorization: Api-Key <raw_key> header."""
        request = self.factory.get(
            "/api/v1/iam/auth/me/",
            HTTP_AUTHORIZATION=f"Api-Key {self.raw_key}",
        )
        user, auth_obj = self.auth.authenticate(request) or (None, None)

        self.assertEqual(user, self.user)
        self.assertEqual(auth_obj, self.api_key)

    def test_authenticate_invalid_key_fails(self):
        """Test authenticating with invalid key format or wrong secret."""
        # Malformed
        request1 = self.factory.get(
            "/api/v1/iam/auth/me/", HTTP_X_API_KEY="invalid-key"
        )
        with self.assertRaises(AuthenticationFailed):
            self.auth.authenticate(request1)

        # Wrong secret for existing prefix
        wrong_key = f"djc_live_{self.api_key.prefix}_wrongsecret123456789"
        request2 = self.factory.get("/api/v1/iam/auth/me/", HTTP_X_API_KEY=wrong_key)
        with self.assertRaises(AuthenticationFailed):
            self.auth.authenticate(request2)

    def test_authenticate_inactive_key_fails(self):
        """Test inactive API key is rejected."""
        self.api_key.is_active = False
        self.api_key.save()

        request = self.factory.get("/api/v1/iam/auth/me/", HTTP_X_API_KEY=self.raw_key)
        with self.assertRaises(AuthenticationFailed):
            self.auth.authenticate(request)

    def test_authenticate_expired_key_fails(self):
        """Test expired API key is rejected."""
        self.api_key.expires_at = timezone.now() - datetime.timedelta(minutes=5)
        self.api_key.save()

        request = self.factory.get("/api/v1/iam/auth/me/", HTTP_X_API_KEY=self.raw_key)
        with self.assertRaises(AuthenticationFailed):
            self.auth.authenticate(request)

    def test_authenticate_ip_whitelist_restriction(self):
        """Test that requests from unauthorized IPs are rejected with PermissionDenied."""
        self.api_key.allowed_ips = ["192.168.1.50"]
        self.api_key.save()

        # Request from blocked IP
        blocked_req = self.factory.get(
            "/api/v1/iam/auth/me/",
            HTTP_X_API_KEY=self.raw_key,
            REMOTE_ADDR="10.0.0.1",
        )
        with self.assertRaises(PermissionDenied):
            self.auth.authenticate(blocked_req)

        # Request from permitted IP
        allowed_req = self.factory.get(
            "/api/v1/iam/auth/me/",
            HTTP_X_API_KEY=self.raw_key,
            REMOTE_ADDR="192.168.1.50",
        )
        user, _ = self.auth.authenticate(allowed_req) or (None, None)
        self.assertEqual(user, self.user)
